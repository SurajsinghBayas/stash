"""Typed errors and the single handler that turns them into the standard error body."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("stash.errors")


class AppError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status: int | None = None,
                 headers: dict[str, str] | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status:
            self.status = status
        self.headers = headers


class ValidationFailed(AppError):
    status, code = 400, "validation_error"


class Unauthorized(AppError):
    status, code = 401, "unauthorized"


class Forbidden(AppError):
    status, code = 403, "forbidden"


class NotFound(AppError):
    status, code = 404, "not_found"

    def __init__(self, message: str = "Not found", **kw):
        super().__init__(message, **kw)


class Conflict(AppError):
    status, code = 409, "conflict"


class RateLimited(AppError):
    status, code = 429, "rate_limited"

    def __init__(self, retry_after: int):
        super().__init__(f"Too many requests. Try again in {retry_after} seconds.",
                         headers={"Retry-After": str(retry_after)})
        self.retry_after = retry_after


class ServiceUnavailable(AppError):
    status, code = 503, "service_unavailable"


def _body(code: str, message: str, request: Request, **extra) -> dict:
    return {"error": {"code": code, "message": message,
                      "request_id": getattr(request.state, "request_id", None), **extra}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message, request), status_code=exc.status, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query", "path"))
        message = f"{field}: {first.get('msg', 'invalid')}" if field else first.get("msg", "Invalid input")
        return JSONResponse(_body("validation_error", message, request), status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(_body(code, str(exc.detail), request), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        log.exception("unhandled error", extra={"request_id": getattr(request.state, "request_id", None)})
        return JSONResponse(_body("internal_error", "Something went wrong", request), status_code=500)
