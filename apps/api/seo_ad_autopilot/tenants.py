"""Multi-tenant workspace isolation — Phase 2 (GAP-015).

Provides:
- TenantContext: ContextVar-based per-request tenant isolation
- TenantMiddleware: extracts tenant from X-Tenant-ID header or JWT sub-claim
- TenantResolver: maps API keys / OAuth tokens to tenant IDs
- get_tenant_id(): access current tenant from anywhere in the call stack
- Tenant model: workspace metadata

Design:
- Tenant ID is propagated via ContextVar (no thread-local, async-safe)
- All DB queries should filter by tenant_id (enforcement via SQLAlchemy event or manual)
- Public endpoints (health, docs) bypass tenant resolution
- Invalid/missing tenant returns 401 (configurable)
"""

from __future__ import annotations

import os
import uuid
from contextvars import ContextVar
from typing import Any, Callable, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


# ── Context var ───────────────────────────────────────────────────────────────

_tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
_tenant_meta_var: ContextVar[dict] = ContextVar("tenant_meta", default={})


def get_tenant_id() -> str:
    """Return current request's tenant ID (empty string = public/single-tenant mode)."""
    return _tenant_id_var.get()


def get_tenant_meta() -> dict:
    """Return current tenant metadata dict."""
    return _tenant_meta_var.get()


def set_tenant(tenant_id: str, meta: Optional[dict] = None) -> None:
    """Explicitly set tenant context (useful for background tasks)."""
    _tenant_id_var.set(tenant_id)
    _tenant_meta_var.set(meta or {})


# ── Tenant model ──────────────────────────────────────────────────────────────

class Tenant:
    """Workspace/tenant metadata."""

    def __init__(
        self,
        tenant_id: str,
        name: str = "",
        plan: str = "free",       # free | pro | enterprise
        rate_limit_multiplier: float = 1.0,
        allowed_agents: Optional[list[str]] = None,
        custom_rules: Optional[dict] = None,
        locale: str = "en",
    ) -> None:
        self.tenant_id             = tenant_id
        self.name                  = name
        self.plan                  = plan
        self.rate_limit_multiplier = rate_limit_multiplier
        self.allowed_agents        = allowed_agents       # None = all agents allowed
        self.custom_rules          = custom_rules or {}
        self.locale                = locale

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id":             self.tenant_id,
            "name":                  self.name,
            "plan":                  self.plan,
            "rate_limit_multiplier": self.rate_limit_multiplier,
            "allowed_agents":        self.allowed_agents,
            "locale":                self.locale,
        }


# ── In-memory tenant registry (replace with DB for production) ────────────────

class TenantRegistry:
    """In-memory tenant store. Replace with async DB lookup in production."""

    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._api_keys: dict[str, str] = {}   # api_key → tenant_id

        # Default system tenant for single-tenant / no-auth deployments
        system_tenant = Tenant(
            tenant_id="system",
            name="System",
            plan="enterprise",
            rate_limit_multiplier=10.0,
        )
        self.register(system_tenant)

    def register(self, tenant: Tenant) -> None:
        self._tenants[tenant.tenant_id] = tenant

    def get(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)

    def register_api_key(self, api_key: str, tenant_id: str) -> None:
        self._api_keys[api_key] = tenant_id

    def resolve_api_key(self, api_key: str) -> Optional[str]:
        return self._api_keys.get(api_key)

    def create(
        self,
        name: str,
        plan: str = "free",
        **kwargs: Any,
    ) -> Tenant:
        tenant_id = str(uuid.uuid4())
        tenant    = Tenant(tenant_id=tenant_id, name=name, plan=plan, **kwargs)
        self.register(tenant)
        return tenant

    def list_all(self) -> list[dict]:
        return [t.to_dict() for t in self._tenants.values()]


# Module-level singleton registry
registry = TenantRegistry()


# ── Tenant resolution helpers ─────────────────────────────────────────────────

def _resolve_from_header(request: Request) -> Optional[str]:
    """Extract tenant ID from X-Tenant-ID header."""
    return request.headers.get("X-Tenant-ID")


def _resolve_from_api_key(request: Request) -> Optional[str]:
    """Resolve tenant from X-API-Key or Authorization: Bearer <api_key> header."""
    # X-API-Key header
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return registry.resolve_api_key(api_key)

    # Authorization: Bearer <token>
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        # Try as API key first
        tenant_id = registry.resolve_api_key(token)
        if tenant_id:
            return tenant_id
        # Try as JWT sub-claim (simplified — replace with proper JWT validation)
        try:
            import base64, json as _json
            payload_b64 = token.split(".")[1]
            # Add padding
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
            return payload.get("tenant_id") or payload.get("sub")
        except Exception:
            pass

    return None


_MULTI_TENANT_ENABLED = os.getenv("MULTI_TENANT", "false").lower() in ("1", "true", "yes")
_BYPASS_PATHS = {"/health", "/healthz", "/ready", "/docs", "/openapi.json", "/api/health"}


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract and validate tenant context for every request.

    In single-tenant mode (MULTI_TENANT=false, default):
    - Sets tenant_id to "system" for all requests (no auth required)

    In multi-tenant mode (MULTI_TENANT=true):
    - Resolves tenant from X-Tenant-ID header or API key
    - Returns 401 if tenant cannot be resolved (except bypass paths)
    """

    def __init__(
        self,
        app: ASGIApp,
        require_tenant: bool = _MULTI_TENANT_ENABLED,
    ) -> None:
        super().__init__(app)
        self._require_tenant = require_tenant

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Bypass tenant resolution for public paths
        if path in _BYPASS_PATHS:
            token = _tenant_id_var.set("system")
            try:
                return await call_next(request)
            finally:
                _tenant_id_var.reset(token)

        if not self._require_tenant:
            # Single-tenant mode: use "system" tenant
            token = _tenant_id_var.set("system")
            meta_token = _tenant_meta_var.set({"plan": "enterprise"})
            try:
                return await call_next(request)
            finally:
                _tenant_id_var.reset(token)
                _tenant_meta_var.reset(meta_token)

        # Multi-tenant: resolve tenant ID
        tenant_id = (
            _resolve_from_header(request)
            or _resolve_from_api_key(request)
        )

        if not tenant_id:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "tenant_required",
                    "message": "Tenant identification required. Provide X-Tenant-ID header or API key.",
                },
            )

        tenant = registry.get(tenant_id)
        if not tenant:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "tenant_not_found",
                    "message": f"Tenant '{tenant_id}' not found.",
                },
            )

        token      = _tenant_id_var.set(tenant_id)
        meta_token = _tenant_meta_var.set(tenant.to_dict())
        try:
            response = await call_next(request)
            response.headers["X-Tenant-ID"] = tenant_id
            return response
        finally:
            _tenant_id_var.reset(token)
            _tenant_meta_var.reset(meta_token)
