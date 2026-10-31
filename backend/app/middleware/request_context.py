"""Request id, access log, body-size cap and the Origin check for state-changing requests."""

import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings

log = logging.getLogger("stash.request")

MAX_JSON_BODY = 1024 * 1024
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


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

        # Cap JSON bodies; uploads go straight to storage and never through this path.
        length = headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_JSON_BODY and not path.startswith(
            "/api/v1/_local_storage/"
        ):
            await reject(413, "payload_too_large", "Request body is larger than 1 MB")
            self._log(method, path, 413, started, request_id)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            self._log(method, path, status_holder["status"], started, request_id)

    @staticmethod
    def _log(method: str, path: str, status: int, started: float, request_id: str) -> None:
        log.info("request", extra={"request_id": request_id, "method": method, "path": path,
                                   "status": status, "ms": round((time.perf_counter() - started) * 1000)})
