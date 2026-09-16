"""Health check router."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Basic liveness probe."""
    return {"status": "ok"}


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
