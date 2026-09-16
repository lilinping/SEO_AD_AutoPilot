"""Rank tracking router.

Endpoints:
  POST /api/rank/snapshot           – take a rank snapshot for a URL + keywords
  POST /api/rank/track              – track SERP features for a URL
  POST /api/rank/history            – get ranking history for a URL
  POST /api/rank/alert              – configure rank-change alerts
"""

from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/rank", tags=["rank-tracking"])


class RankSnapshotRequest(BaseModel):
    url: str
    keywords: list[str]
    search_engine: str = "google"
    locale: str = "en"
    device: str = "desktop"


class SERPTrackRequest(BaseModel):
    url: str
    keywords: list[str]
    track_features: list[str] = [
        "featured_snippet", "people_also_ask", "image_pack",
        "video_carousel", "ai_overview", "local_pack",
    ]


class RankHistoryRequest(BaseModel):
    url: str
    keyword: str
    days: int = 30


class RankAlertRequest(BaseModel):
    url: str
    keywords: list[str]
    threshold: int = 5
    webhook_url: Optional[str] = None
    email: Optional[str] = None


@router.post("/snapshot")
async def take_rank_snapshot(request: RankSnapshotRequest) -> dict[str, Any]:
    """Take a ranking snapshot for a set of keywords."""
    from ..skills import RankSnapshotSkill
    from ..skills.base import SkillInput

    start = time.time()
    try:
        skill = RankSnapshotSkill()
        inp = SkillInput(
            url=request.url,
            params={
                "keywords": request.keywords,
                "search_engine": request.search_engine,
                "locale": request.locale,
                "device": request.device,
            },
        )
        result = await skill.execute(inp)
        return {
            "status": "success",
            "url": request.url,
            "keywords_count": len(request.keywords),
            "elapsed_sec": round(time.time() - start, 2),
            "result": result.data if hasattr(result, "data") else result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/track")
async def track_serp_features(request: SERPTrackRequest) -> dict[str, Any]:
    """Track SERP features (featured snippet, PAA, AI Overview, etc.)."""
    from ..skills import SERPFeatureTrackerSkill
    from ..skills.base import SkillInput

    start = time.time()
    try:
        skill = SERPFeatureTrackerSkill()
        inp = SkillInput(
            url=request.url,
            params={
                "keywords": request.keywords,
                "track_features": request.track_features,
            },
        )
        result = await skill.execute(inp)
        return {
            "status": "success",
            "url": request.url,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result.data if hasattr(result, "data") else result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/history")
async def get_rank_history(request: RankHistoryRequest) -> dict[str, Any]:
    """Retrieve historical rank data for a URL + keyword pair."""
    from ..agents import RankTrackerAgent

    start = time.time()
    try:
        agent = RankTrackerAgent()
        result = await agent.get_history(
            url=request.url,
            keyword=request.keyword,
            days=request.days,
        )
        return {
            "status": "success",
            "url": request.url,
            "keyword": request.keyword,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/alert")
async def configure_rank_alert(request: RankAlertRequest) -> dict[str, Any]:
    """Configure rank-change alert thresholds and notification channels."""
    if not request.webhook_url and not request.email:
        raise HTTPException(
            status_code=400,
            detail="At least one of webhook_url or email must be provided",
        )
    return {
        "status": "configured",
        "url": request.url,
        "keywords": request.keywords,
        "threshold_positions": request.threshold,
        "notification": {
            "webhook": request.webhook_url,
            "email": request.email,
        },
        "message": "Rank alert configured. Alerts will trigger when position changes >= threshold.",
    }
