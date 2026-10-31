"""Fetch link metadata without letting a user point the server at internal addresses (SSRF).

- http/https only, ports 80/443 only
- every resolved address must be public (blocks 169.254.169.254, localhost, private ranges)
- redirects are followed by hand, max 3, and each hop is checked again
- 8 s timeout, 2 MB cap, text/html only

The readable article text (Markdown, headings kept) is extracted with trafilatura for the reader agent.
The EC2 instance also requires IMDSv2, so a plain GET cannot read instance credentials even if DNS changes
between the check and the request.
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx
import trafilatura

from app.services.safety.local import is_adult_domain

MAX_BYTES = 2 * 1024 * 1024
MAX_BODY_CHARS = 60_000
MAX_REDIRECTS = 3
TIMEOUT = httpx.Timeout(8.0, connect=3.0)
USER_AGENT = "StashBot/1.0 (+link previews)"


class BlockedURL(Exception):
    pass


async def _check_host(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise BlockedURL("scheme")
    if parts.port not in (None, 80, 443):
        raise BlockedURL("port")
    host = parts.hostname
    if is_adult_domain(host):
        raise BlockedURL("adult_domain")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, parts.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise BlockedURL("dns") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global or address.is_multicast:
            raise BlockedURL("private_address")


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title = ""
        self.icons: list[str] = []
        self._in_title = False
        self.done = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and "content" in a and key not in self.meta:
                self.meta[key] = a["content"].strip()
        elif tag == "title":
            self._in_title = True
        elif tag == "link" and "icon" in a.get("rel", "").lower() and a.get("href"):
            self.icons.append(a["href"])
        elif tag == "body":
            self.done = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "head":
            self.done = True

    def handle_data(self, data):
        if self._in_title and len(self.title) < 300:
            self.title += data


def _clean(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    value = " ".join(value.split())
    return value[:limit] or None


def _safe_url(value: str | None, base: str) -> str | None:
    if not value:
        return None
    absolute = urljoin(base, value.strip())
    return absolute if urlsplit(absolute).scheme in ("http", "https") and len(absolute) <= 2048 else None


def parse_metadata(html: str, final_url: str) -> dict:
    parser = _MetaParser()
    try:
        parser.feed(html)
    except Exception:  # malformed markup: keep whatever was parsed
        pass
    m = parser.meta
    host = urlsplit(final_url).hostname or ""
    return {
        "title": _clean(m.get("og:title") or m.get("twitter:title") or parser.title, 300),
        "description": _clean(m.get("og:description") or m.get("twitter:description") or m.get("description"), 600),
        "image": _safe_url(m.get("og:image") or m.get("twitter:image"), final_url),
        "site_name": _clean(m.get("og:site_name"), 100) or host.removeprefix("www."),
        "favicon": _safe_url(parser.icons[0] if parser.icons else "/favicon.ico", final_url),
    }


@dataclass
class Page:
    final_url: str
    meta: dict = field(default_factory=dict)
    body: str | None = None


def extract_body(html: str, url: str) -> str | None:
    text = trafilatura.extract(html, url=url, output_format="markdown", include_comments=False,
                               include_tables=True, include_images=False, favor_precision=True)
    return text[:MAX_BODY_CHARS] if text and text.strip() else None


async def fetch_page(url: str) -> Page:
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False,
                                 headers={"User-Agent": USER_AGENT, "Accept": "text/html"}) as client:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            await _check_host(current)
            async with client.stream("GET", current) as resp:
                if resp.is_redirect:
                    location = resp.headers.get("location")
                    if not location:
                        raise BlockedURL("bad_redirect")
                    current = urljoin(current, location)
                    continue
                if resp.status_code >= 400:
                    raise BlockedURL(f"http_{resp.status_code}")
                if "text/html" not in resp.headers.get("content-type", ""):
                    return Page(current, {"site_name": (urlsplit(current).hostname or "").removeprefix("www.")})
                body = bytearray()
                async for chunk in resp.aiter_bytes():
                    body.extend(chunk)
                    if len(body) >= MAX_BYTES:
                        break
                html = body.decode(resp.charset_encoding or "utf-8", errors="replace")
                text = await asyncio.to_thread(extract_body, html, current)
                return Page(current, parse_metadata(html, current), text)
        raise BlockedURL("too_many_redirects")


async def fetch_metadata(url: str) -> dict:
    return (await fetch_page(url)).meta
