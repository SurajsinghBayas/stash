"""One `ai_requests` row per agent call: which agent, model, prompt version, cards, tokens, latency, outcome.
Prompts and replies are not stored."""

import time
import uuid
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models import AIRequest
from app.services.ai.client import Usage


class Timer:
    def __init__(self) -> None:
        self.started = time.monotonic()

    @property
    def ms(self) -> int:
        return int((time.monotonic() - self.started) * 1000)


def record(session: AsyncSession, *, user_id: uuid.UUID, task: str, prompt_version: str, outcome: str,
           timer: Timer, usage: Usage | None = None, model: str = "", request_id: str | None = None,
           item_ids: Iterable[uuid.UUID] = ()) -> None:
    session.add(AIRequest(
        request_id=request_id, user_id=user_id, task=task, model=(usage.model if usage else None) or model or "-",
        prompt_version=prompt_version, item_ids=list(dict.fromkeys(item_ids)),
        input_tokens=usage.input_tokens if usage else None, output_tokens=usage.output_tokens if usage else None,
        latency_ms=timer.ms, outcome=outcome,
    ))
