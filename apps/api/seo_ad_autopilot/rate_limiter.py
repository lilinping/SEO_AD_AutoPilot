"""API Rate Limiting middleware — Phase 2 (GAP-016).

Strategy:
- Sliding-window rate limiting per (IP, endpoint) pair
- In-memory store (replace with Redis for multi-process deployments)
- Per-endpoint overrides via RATE_LIMIT_OVERRIDES env var (JSON)
- Returns 429 with Retry-After header when limit exceeded
- X-RateLimit-Limit / X-RateLimit-Remaining / X-RateLimit-Reset headers on every response

Default limits:
  - Global: 100 req / 60s per IP
  - /api/agents/analyze: 10 req / 60s (expensive)
  - /api/content/generate: 20 req / 60s (LLM calls)
  - /api/search/query: 30 req / 60s (external API calls)
  - /health, /ready: unlimited
"""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from typing import Any, Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


# ── Configuration ────────────────────────────────────────────────────────────

_DEFAULT_LIMIT   = 100     # requests
_DEFAULT_WINDOW  = 60      # seconds

# Expensive endpoint overrides: (limit, window_sec)
_ENDPOINT_LIMITS: dict[str, tuple[int, int]] = {
    "/api/agents/analyze":       (10, 60),
    "/api/content/generate":     (20, 60),
    "/api/content/aio-optimize": (20, 60),
    "/api/search/query":         (30, 60),
    "/api/ads/analyze":          (20, 60),
    "/api/competitor/analyze":   (15, 60),
    "/api/rank/snapshot":        (30, 60),
}

# Load overrides from env (JSON: {"path": [limit, window_sec]})
_env_overrides = os.getenv("RATE_LIMIT_OVERRIDES", "{}")
try:
    _env_parsed = json.loads(_env_overrides)
    for _path, _cfg in _env_parsed.items():
        if isinstance(_cfg, (list, tuple)) and len(_cfg) == 2:
            _ENDPOINT_LIMITS[_path] = (int(_cfg[0]), int(_cfg[1]))
except (json.JSONDecodeError, TypeError, ValueError):
    pass

# Paths exempt from rate limiting
_EXEMPT_PATHS = {"/health", "/healthz", "/ready", "/api/health", "/api/ready", "/docs", "/openapi.json"}


# ── In-memory sliding window store ───────────────────────────────────────────

class _SlidingWindowStore:
    """Sliding window counter stored as a deque of timestamps."""

    def __init__(self) -> None:
        # key: (ip, path) → deque of float timestamps
        self._windows: dict[tuple[str, str], deque] = defaultdict(deque)

    def check_and_record(
        self, ip: str, path: str, limit: int, window_sec: int
    ) -> tuple[bool, int, float]:
        """Check rate limit and record the request.

        Returns: (allowed, remaining, reset_at_unix)
        """
        now = time.time()
        key = (ip, path)
        window = self._windows[key]

        # Evict timestamps outside the window
        cutoff = now - window_sec
        while window and window[0] <= cutoff:
            window.popleft()

        count = len(window)
        reset_at = (window[0] + window_sec) if window else (now + window_sec)

        if count >= limit:
            return False, 0, reset_at

        window.append(now)
        return True, limit - count - 1, reset_at


_store = _SlidingWindowStore()


# ── Middleware ────────────────────────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window IP-based rate limiter."""

    def __init__(
        self,
        app: ASGIApp,
        default_limit: int = _DEFAULT_LIMIT,
        default_window_sec: int = _DEFAULT_WINDOW,
    ) -> None:
        super().__init__(app)
        self._default_limit  = default_limit
        self._default_window = default_window_sec

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract real client IP, respecting X-Forwarded-For."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Exempt paths
        if path in _EXEMPT_PATHS:
            return await call_next(request)

        ip = self._get_client_ip(request)

        # Get endpoint-specific or default limits
        limit, window_sec = _ENDPOINT_LIMITS.get(path, (self._default_limit, self._default_window))

        allowed, remaining, reset_at = _store.check_and_record(ip, path, limit, window_sec)

        if not allowed:
            retry_after = max(1, int(reset_at - time.time()))
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": f"Too many requests. Retry after {retry_after}s.",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After":           str(retry_after),
                    "X-RateLimit-Limit":     str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset":     str(int(reset_at)),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"]     = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"]     = str(int(reset_at))
        return response
