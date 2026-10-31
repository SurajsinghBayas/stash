"""The only module that talks to AI providers. Every input must be a `SafeText` from the safety gate."""

import base64
import json
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, TypeVar

import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.errors import ServiceUnavailable
from app.services.safety.service import SafeImage, SafeText

T = TypeVar("T", bound=BaseModel)

log = logging.getLogger("stash.ai")

VOYAGE = "https://api.voyageai.com/v1"
EMBED_DIMS = 1024


class AIUnavailable(ServiceUnavailable):
    code = "ai_unavailable"

    def __init__(self, message: str = "The assistant is unavailable right now. Try again in a moment."):
        super().__init__(message)


def _require_safe(values) -> None:
    for value in values:
        if not isinstance(value, SafeText):
            raise TypeError("AI providers only accept SafeText")


_http: httpx.AsyncClient | None = None


def _voyage() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(base_url=VOYAGE, timeout=15,
                                  headers={"Authorization": f"Bearer {settings.voyager_api_key}"})
    return _http


async def embed(texts: list[SafeText], input_type: Literal["document", "query"]) -> list[list[float]]:
    _require_safe(texts)
    if not settings.embeddings_configured:
        raise AIUnavailable("Embeddings are not configured")
    try:
        resp = await _voyage().post("/embeddings", json={
            "input": [t.value for t in texts], "model": settings.embed_model, "input_type": input_type,
            "output_dimension": EMBED_DIMS,
        })
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        log.warning("voyage embed failed", extra={"error": type(exc).__name__, "status": status})
        raise AIUnavailable() from exc
    rows = sorted(resp.json()["data"], key=lambda r: r["index"])
    return [r["embedding"] for r in rows]


async def rerank(query: SafeText, documents: list[SafeText], top_k: int) -> list[tuple[int, float]]:
    _require_safe([query, *documents])
    if not settings.embeddings_configured or not documents:
        return [(i, 0.0) for i in range(min(top_k, len(documents)))]
    try:
        resp = await _voyage().post("/rerank", json={
            "query": query.value, "documents": [d.value for d in documents], "model": settings.rerank_model,
            "top_k": top_k,
        })
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        log.warning("voyage rerank failed", extra={"error": type(exc).__name__, "status": status})
        raise AIUnavailable() from exc
    return [(r["index"], r["relevance_score"]) for r in resp.json()["data"]]


@dataclass
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    model: str | None = None

    def add(self, other: "Usage") -> None:
        self.input_tokens = (self.input_tokens or 0) + (other.input_tokens or 0)
        self.output_tokens = (self.output_tokens or 0) + (other.output_tokens or 0)


_openai: AsyncOpenAI | None = None


def _chat() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        _openai = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url,
                              timeout=30, max_retries=1)
    return _openai


def _messages(system: SafeText, messages: list[tuple[str, SafeText]]) -> list[dict]:
    return ([{"role": "system", "content": system.value}]
            + [{"role": role, "content": text.value} for role, text in messages])


async def chat_stream(system: SafeText, messages: list[tuple[str, SafeText]], *, max_tokens: int = 500,
                      usage: Usage | None = None, model: str | None = None,
                      fallback: str | None = None) -> AsyncIterator[str]:
    """Streams text. If `model` fails before its first token, `fallback` gets one try."""
    _require_safe([system, *(m for _, m in messages)])
    if not settings.chat_ai_configured:
        raise AIUnavailable()
    for attempt, name in enumerate(filter(None, [model or settings.chat_model, fallback])):
        started = False
        try:
            stream = await _chat().chat.completions.create(
                model=name, messages=_messages(system, messages), max_tokens=max_tokens, temperature=0.2,
                stream=True, stream_options={"include_usage": True},
            )
            async for chunk in stream:
                if chunk.usage and usage is not None:
                    usage.input_tokens = chunk.usage.prompt_tokens
                    usage.output_tokens = chunk.usage.completion_tokens
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    if not started and usage is not None:
                        usage.model = name
                    started = True
                    yield chunk.choices[0].delta.content
            return
        except Exception as exc:
            log.warning("chat call failed", extra={"error": type(exc).__name__, "model": name, "attempt": attempt})
            if started or not fallback or name == fallback:
                raise AIUnavailable() from exc


async def complete(system: SafeText, prompt: SafeText, *, max_tokens: int = 400,
                   model: str | None = None) -> tuple[str, Usage]:
    usage = Usage()
    parts = [p async for p in chat_stream(system, [("user", prompt)], max_tokens=max_tokens, usage=usage,
                                          model=model)]
    return "".join(parts), usage


def _json_from(text: str) -> object:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    if start < 0:
        raise ValueError("no JSON in reply")
    closing = "}" if text[start] == "{" else "]"
    return json.loads(text[start:text.rfind(closing) + 1])


async def _create(model: str, messages: list[dict], max_tokens: int, usage: Usage, **extra) -> str:
    resp = await _chat().chat.completions.create(model=model, messages=messages, max_tokens=max_tokens,
                                                 temperature=0, **extra)
    if resp.usage:
        usage.add(Usage(resp.usage.prompt_tokens, resp.usage.completion_tokens))
    usage.model = model
    return resp.choices[0].message.content or ""


async def chat_json(system: SafeText, prompt: SafeText, schema: type[T], *, model: str, max_tokens: int = 600,
                    usage: Usage | None = None, image: SafeImage | None = None) -> T:
    """One structured call. The reply is parsed and validated against `schema`; one repair try on bad JSON.
    Model output is untrusted: callers still run text fields through the output safety check."""
    _require_safe([system, prompt])
    if image is not None and not isinstance(image, SafeImage):
        raise TypeError("AI providers only accept SafeImage")
    if not settings.chat_ai_configured:
        raise AIUnavailable()
    usage = usage if usage is not None else Usage()
    content: str | list[dict] = prompt.value
    if image is not None:
        content = [{"type": "text", "text": prompt.value},
                   {"type": "image_url", "image_url": {"url": f"data:{image.mime};base64,"
                                                             + base64.b64encode(image.data).decode()}}]
    messages = [{"role": "system", "content": system.value}, {"role": "user", "content": content}]
    try:
        reply = await _create(model, messages, max_tokens, usage)
        try:
            return schema.model_validate(_json_from(reply))
        except (ValueError, ValidationError):
            messages += [{"role": "assistant", "content": reply[:2000]},
                         {"role": "user", "content": "That was not valid JSON for the requested shape. "
                                                     "Reply again with only the JSON object."}]
            return schema.model_validate(_json_from(await _create(model, messages, max_tokens, usage)))
    except (ValueError, ValidationError) as exc:
        log.warning("structured reply invalid", extra={"model": model, "schema": schema.__name__})
        raise AIUnavailable() from exc
    except AIUnavailable:
        raise
    except Exception as exc:
        log.warning("structured call failed", extra={"error": type(exc).__name__, "model": model})
        raise AIUnavailable() from exc
