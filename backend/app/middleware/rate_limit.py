"""In-process sliding-window limiter.

Correct for the single-instance v1 deploy. Before adding a second API instance, move this to Redis
(09-backend-scalability.md, "Separate state").
"""

import time
from collections import defaultdict, deque

from fastapi import Request

from app.errors import RateLimited


class SlidingWindow:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str, limit: int, window_s: int) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and hits[0] <= now - window_s:
            hits.popleft()
        if len(hits) >= limit:
            raise RateLimited(retry_after=max(1, int(hits[0] + window_s - now) + 1))
        hits.append(now)

    def reset(self) -> None:
        self._hits.clear()


limiter = SlidingWindow()


def client_ip(request: Request) -> str:
    # nginx sets X-Real-IP; uvicorn runs with --proxy-headers behind it.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


def limit(bucket: str, count: int, window_s: int):
    """Dependency: limit by client IP."""

    async def _dep(request: Request) -> None:
        limiter.hit(f"{bucket}:ip:{client_ip(request)}", count, window_s)

    return _dep
