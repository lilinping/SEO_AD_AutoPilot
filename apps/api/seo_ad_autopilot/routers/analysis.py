"""Site analysis router.

Endpoints:
  POST /api/analysis/site          – full site technical analysis
  POST /api/analysis/aio           – AIO optimizer analysis
  POST /api/analysis/geo           – GEO (Generative Engine Optimization) analysis
  POST /api/analysis/ux            – UX/conversion analysis
  GET  /api/analysis/report/{task} – fetch cached analysis report
"""

from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


# ── Request models ────────────────────────────────────────────────────────────

class SiteAnalysisRequest(BaseModel):
    url: str
    include_screenshots: bool = False
    locale: str = "en"


class AIORequest(BaseModel):
    url: str
    content: Optional[str] = None
    target_keywords: list[str] = []


class GEORequest(BaseModel):
    url: str
    content: Optional[str] = None
    target_ai_engines: list[str] = ["chatgpt", "perplexity", "gemini"]


class UXRequest(BaseModel):
    url: str
    conversion_goal: str = "lead"   # lead | sale | signup | engagement


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/site")
async def analyze_site(request: SiteAnalysisRequest) -> dict[str, Any]:
    """Run full technical SEO site analysis via SnifferAgent."""
    from ..agents import SnifferAgent

    start = time.time()
    try:
        agent = SnifferAgent()
        result = await agent.analyze(url=request.url, locale=request.locale)
        return {
            "status": "success",
            "url": request.url,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/aio")
async def analyze_aio(request: AIORequest) -> dict[str, Any]:
    """Run AI Overview optimization analysis via AIOOptimizerAgent."""
    from ..agents import AIOOptimizerAgent

    start = time.time()
    try:
        agent = AIOOptimizerAgent()
        result = await agent.analyze(
            url=request.url,
            content=request.content,
            target_keywords=request.target_keywords,
        )
        return {
            "status": "success",
            "url": request.url,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/geo")
async def analyze_geo(request: GEORequest) -> dict[str, Any]:
    """Run Generative Engine Optimization analysis via GEOAgent."""
    from ..agents import GEOAgent

    start = time.time()
    try:
        agent = GEOAgent()
        result = await agent.analyze(
            url=request.url,
            content=request.content,
            target_engines=request.target_ai_engines,
        )
        return {
            "status": "success",
            "url": request.url,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ux")
async def analyze_ux(request: UXRequest) -> dict[str, Any]:
    """Run UX/conversion analysis via UXReviewerAgent."""
    from ..agents import UXReviewerAgent

    start = time.time()
    try:
        agent = UXReviewerAgent()
        result = await agent.analyze(
            url=request.url,
            conversion_goal=request.conversion_goal,
        )
        return {
            "status": "success",
            "url": request.url,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
