"""Structured request logging middleware with request_id injection.

Phase 1 P1 (GAP-012):
- Injects X-Request-ID header into every request/response
- Logs structured JSON: method, path, status, duration_ms, request_id
- Uses contextvars so request_id is accessible from any downstream coroutine
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# ── Context var ──────────────────────────────────────────────────────────────

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id_var.get()


# ── Structured formatter ──────────────────────────────────────────────────────

class _StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base: dict[str, Any] = {
            "ts":     self.formatTime(record, self.datefmt),
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
        }
        rid = get_request_id()
        if rid:
            base["request_id"] = rid
        for key in ("method", "path", "status", "duration_ms", "error"):
            if hasattr(record, key):
                base[key] = getattr(record, key)
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)


def configure_structured_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for h in root.handlers[:]:
        root.removeHandler(h)
    handler = logging.StreamHandler()
    handler.setFormatter(_StructuredFormatter())
    root.addHandler(handler)
    for noisy in ("uvicorn.access", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ── Middleware ────────────────────────────────────────────────────────────────

class RequestLoggerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, log_bodies: bool = False) -> None:
        super().__init__(app)
        self._log_bodies = log_bodies
        self._logger = logging.getLogger("seo_ad_autopilot.access")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = _request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            ms = round((time.perf_counter() - start) * 1000, 1)
            self._logger.error(
                "Unhandled exception",
                extra={"method": request.method, "path": request.url.path,
                       "status": 500, "duration_ms": ms, "error": str(exc)},
                exc_info=True,
            )
            _request_id_var.reset(token)
            raise
        ms = round((time.perf_counter() - start) * 1000, 1)
        status = response.status_code
        lvl = logging.ERROR if status >= 500 else (logging.WARNING if status >= 400 else logging.INFO)
        self._logger.log(lvl, f"{request.method} {request.url.path} -> {status}",
                         extra={"method": request.method, "path": request.url.path,
                                "status": status, "duration_ms": ms})
        response.headers["X-Request-ID"] = request_id
        _request_id_var.reset(token)
        return response
