# -*- coding: utf-8 -*-
"""Stripe Subscription + API Quota Gateway Middleware - Epic-08 / US-08-02.

Strategy:
1. Resolve caller plan_tier from Bearer JWT or X-API-Key (fallback to free).
2. Look up the plan daily limit.
3. Check sliding-window counter.
4. If payment failed -> 402.
5. If quota exhausted -> 429.
"""

import hashlib
import json
import os
import time
from collections import defaultdict, deque
from typing import Callable, Optional

import stripe
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

_STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
_STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
_JWT_SECRET = os.getenv("JWT_SECRET", "")
_QUOTA_DISABLED = os.getenv("QUOTA_DISABLED", "false").lower() == "true"

if _STRIPE_SECRET_KEY:
    stripe.api_key = _STRIPE_SECRET_KEY

_PLAN_DAILY_LIMITS = {
    "free": 1000,
    "starter": 20000,
    "growth": 50000,
    "pro": 50000,
    "scale": 200000,
    "team": 200000,
    "enterprise": 0,
}

_quota_override_raw = os.getenv("QUOTA_OVERRIDE_JSON", "{}")
try:
    _quota_override = json.loads(_quota_override_raw)
    for _tier, _limit in _quota_override.items():
        _PLAN_DAILY_LIMITS[_tier] = int(_limit)
except Exception:
    pass

_GUARDED_PREFIXES = (
    "/api/agents/",
    "/api/content/",
    "/api/search/",
    "/api/rank/",
    "/api/competitor/",
    "/api/ads/",
    "/api/ecommerce/",
    "/api/keywords/",
)

_EXEMPT_EXACT = frozenset({
    "/health",
    "/healthz",
    "/ready",
    "/api/health",
    "/api/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/billing/webhook",
    "/api/billing/plans",
    "/api/billing/checkout",
})

_WINDOW_SECONDS = 86400

class _DailyWindowStore:
    def __init__(self):
        self._windows = defaultdict(deque)

    def _family(self, path: str):
        for prefix in _GUARDED_PREFIXES:
            if path.startswith(prefix):
                return prefix
        return path.split("/")[1] if "/" in path[1:] else path

    def check_and_record(self, identity: str, path: str, daily_limit: int):
        if daily_limit == 0:
            return True, -1, time.time() + _WINDOW_SECONDS

        now = time.time()
        key = (identity, self._family(path))
        window = self._windows[key]
        cutoff = now - _WINDOW_SECONDS
        while window and window[0] <= cutoff:
            window.popleft()

        count = len(window)
        reset_at = (window[0] + _WINDOW_SECONDS) if window else (now + _WINDOW_SECONDS)

        if count >= daily_limit:
            return False, 0, reset_at

        window.append(now)
        return True, daily_limit - count - 1, reset_at

_store = _DailyWindowStore()

def _decode_jwt_plan(token: str):
    try:
        import jwt
        payload = jwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
        sub = str(payload.get("sub", "anonymous"))
        tier = str(payload.get("plan_tier", payload.get("planTier", "free"))).lower()
        return sub, tier
    except Exception:
        return "anonymous", "free"

def _resolve_identity(request: Request):
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if token:
            sub, tier = _decode_jwt_plan(token)
            return sub, tier.lower(), True

    api_key = request.headers.get("x-api-key", "").strip()
    if api_key:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        tier = _lookup_stripe_plan_for_api_key(api_key)
        return f"key:{key_hash}", tier, tier != "suspended"

    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
    return f"ip:{ip}", "free", True

def _lookup_stripe_plan_for_api_key(api_key: str):
    if not _STRIPE_SECRET_KEY:
        return "free"
    try:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        customers = stripe.Customer.search(
            query=f'metadata["api_key_hash"]:"{key_hash}"',
            limit=1,
        )
        if not customers.data:
            return "free"
        customer = customers.data[0]
        subscriptions = stripe.Subscription.list(
            customer=customer.id, status="active", limit=1
        )
        if not subscriptions.data:
            overdue = stripe.Subscription.list(
                customer=customer.id, status="past_due", limit=1
            )
            return "suspended" if overdue.data else "free"
        sub = subscriptions.data[0]
        tier = (
            sub.get("metadata", {}).get("plan_tier")
            or sub["items"]["data"][0]["price"].get("metadata", {}).get("plan_tier", "free")
        )
        return str(tier).lower()
    except Exception:
        return "free"

class SubscriptionQuotaMiddleware(BaseHTTPMiddleware):
    @staticmethod
    def _is_guarded(path: str) -> bool:
        if path in _EXEMPT_EXACT:
            return False
        return any(path.startswith(p) for p in _GUARDED_PREFIXES)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if _QUOTA_DISABLED or not self._is_guarded(path):
            return await call_next(request)

        identity, plan_tier, subscription_active = _resolve_identity(request)

        if not subscription_active:
            return JSONResponse(
                status_code=402,
                content={
                    "error": "payment_required",
                    "message": "Your subscription is inactive or payment has failed. Please update your payment method to continue.",
                    "upgrade_url": "/pricing",
                },
                headers={
                    "X-Subscription-Status": "inactive",
                    "X-Plan-Tier": plan_tier,
                },
            )

        daily_limit = _PLAN_DAILY_LIMITS.get(plan_tier, _PLAN_DAILY_LIMITS["free"])
        allowed, remaining, reset_at = _store.check_and_record(identity, path, daily_limit)

        if not allowed:
            retry_after = max(1, int(reset_at - time.time()))
            return JSONResponse(
                status_code=429,
                content={
                    "error": "quota_exceeded",
                    "message": f"Daily API quota exhausted for plan '{plan_tier}'. Quota resets in {retry_after // 3600}h {(retry_after % 3600) // 60}m. Upgrade your plan for higher limits.",
                    "plan_tier": plan_tier,
                    "daily_limit": daily_limit,
                    "retry_after": retry_after,
                    "upgrade_url": "/pricing",
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-Quota-Limit": str(daily_limit),
                    "X-Quota-Remaining": "0",
                    "X-Quota-Reset": str(int(reset_at)),
                    "X-Plan-Tier": plan_tier,
                },
            )

        response = await call_next(request)
        response.headers["X-Quota-Limit"] = str(daily_limit) if daily_limit else "unlimited"
        response.headers["X-Quota-Remaining"] = str(remaining) if remaining >= 0 else "unlimited"
        response.headers["X-Quota-Reset"] = str(int(reset_at))
        response.headers["X-Plan-Tier"] = plan_tier
        return response
