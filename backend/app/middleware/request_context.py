"""Request id, access log, body-size cap, security headers and the Origin check for state-changing requests."""

import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings
from app.errors import AppError

log = logging.getLogger("stash.request")

MAX_JSON_BODY = 1024 * 1024
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
UNCAPPED_PREFIX = "/api/v1/_local_storage/"  # development uploads; S3 uploads never pass through the API

# On every API response. The page itself gets its headers (and the full CSP) from nginx; an API response is never
# a document, so it may not run scripts, be framed or be sniffed into one. Responses with user data are not cached
# unless the route chose a cache policy itself (images, public share pages).
SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"),
    (b"cross-origin-resource-policy", b"same-origin"),
]


class BodyTooLarge(AppError):
    status, code = 413, "payload_too_large"


def _json_error(code: str, message: str, request_id: str) -> bytes:
    import json

    return json.dumps({"error": {"code": code, "message": message, "request_id": request_id}}).encode()


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        incoming = headers.get("x-request-id", "")
        request_id = incoming if 0 < len(incoming) <= 64 and incoming.isprintable() else uuid.uuid4().hex[:16]
        scope.setdefault("state", {})["request_id"] = request_id
        method, path = scope["method"], scope["path"]
        started = time.perf_counter()
        status_holder = {"status": 500}

        async def reject(status: int, code: str, message: str) -> None:
            body = _json_error(code, message, request_id)
            await send({"type": "http.response.start", "status": status,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"x-request-id", request_id.encode())]})
            await send({"type": "http.response.body", "body": body})
            status_holder["status"] = status

        # A browser always sends Origin on cross-site writes; reject foreign ones (CSRF defence).
        origin = headers.get("origin")
        if method in UNSAFE_METHODS and origin and origin != settings.app_origin and not path.startswith(
            "/api/v1/email/unsubscribe"
        ):
            await reject(403, "bad_origin", "Request origin is not allowed")
            self._log(method, path, 403, started, request_id)
            return

        # Cap JSON bodies; uploads go straight to storage and never through this path. The declared length is
        # checked up front, and the bytes actually received are counted too, so a chunked body without a
        # Content-Length cannot slip past the cap.
        capped = not path.startswith(UNCAPPED_PREFIX)
        length = headers.get("content-length")
        if capped and length and length.isdigit() and int(length) > MAX_JSON_BODY:
            await reject(413, "payload_too_large", "Request body is larger than 1 MB")
            self._log(method, path, 413, started, request_id)
            return
        received, too_large = 0, False

        async def receive_capped() -> Message:
            nonlocal received, too_large
            message = await receive()
            if capped and message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_JSON_BODY:
                    too_large = True
                    raise BodyTooLarge("Request body is larger than 1 MB")
            return message

        async def send_wrapper(message: Message) -> None:
            if too_large:  # the framework turns the read error into a generic 400; answer with the real reason
                if message["type"] == "http.response.start":
                    await reject(413, "payload_too_large", "Request body is larger than 1 MB")
                return
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                out = message.setdefault("headers", [])
                present = {k.lower() for k, _ in out}
                out.append((b"x-request-id", request_id.encode()))
                out.extend(h for h in SECURITY_HEADERS if h[0] not in present)
                if b"cache-control" not in present:
                    out.append((b"cache-control", b"no-store"))
            await send(message)

        try:
            await self.app(scope, receive_capped, send_wrapper)
        finally:
            self._log(method, path, status_holder["status"], started, request_id)

    @staticmethod
    def _log(method: str, path: str, status: int, started: float, request_id: str) -> None:
        log.info("request", extra={"request_id": request_id, "method": method, "path": path,
                                   "status": status, "ms": round((time.perf_counter() - started) * 1000)})
