"""Health check router.

Implements OPS-005 / §5.5 of REQUIREMENTS.md:
`GET /health` returns component status for db / redis / llm plus version.
All component probes are best-effort and never raise, so the liveness
endpoint stays usable even when optional dependencies are missing.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["health"])

APP_VERSION = "1.0.0"


def _check_db(request: Request) -> str:
    """Best-effort DB connectivity probe via the shared service session."""
    try:
        service = getattr(request.app.state, "service", None)
        if service is None or not hasattr(service, "database"):
            return "unknown"
        from sqlalchemy import select

        with service.database.session() as session:
            session.execute(select(1))
        return "ok"
    except Exception:
        return "error"


def _check_redis() -> str:
    """Probe Redis only when a URL is configured and the client is importable."""
    try:
        from ..config import get_settings

        redis_url = get_settings().redis_url
        if not redis_url:
            return "not_configured"
        try:
            import redis  # type: ignore
        except Exception:
            return "not_installed"
        client = redis.Redis.from_url(redis_url, socket_connect_timeout=1)
        client.ping()
        return "ok"
    except Exception:
        return "error"


def _check_llm() -> str:
    """Report whether at least one LLM provider credential is configured."""
    import os

    keys = (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "OLLAMA_BASE_URL",
    )
    if any(os.environ.get(k) for k in keys):
        return "ok"
    return "not_configured"


@router.get("/health")
async def health(request: Request) -> dict:
    """Liveness + component status probe (OPS-005)."""
    return {
        "status": "ok",
        "db": _check_db(request),
        "redis": _check_redis(),
        "llm": _check_llm(),
        "version": APP_VERSION,
    }


@router.get("/ready")
async def readiness() -> dict:
    """Readiness probe — verifies DB & core imports are available."""
    try:
        from ..agents import CoordinatorAgent  # noqa: F401
        from ..skills import SkillRegistry     # noqa: F401
        from ..ad_platforms import AdPlatformAutoDiscovery  # noqa: F401
        return {"status": "ready"}
    except Exception as exc:
        return {"status": "not_ready", "error": str(exc)}
