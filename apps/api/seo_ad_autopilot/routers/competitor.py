"""Competitor analysis router.

Endpoints:
  POST /api/competitor/keyword-gap   – keyword gap analysis vs competitors
  POST /api/competitor/content-gap   – content gap analysis
  POST /api/competitor/analyze       – full competitor analysis via agent
  POST /api/competitor/discover      – auto-discover competitors for a URL
"""

from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/competitor", tags=["competitor"])


class KeywordGapRequest(BaseModel):
    url: str
    competitor_urls: list[str]
    max_keywords: int = 100
    min_volume: int = 100


class ContentGapRequest(BaseModel):
    url: str
    competitor_urls: list[str]
    content_type: str = "all"


class CompetitorAnalyzeRequest(BaseModel):
    url: str
    competitor_urls: list[str] = []
    auto_discover: bool = True
    depth: str = "standard"


class CompetitorDiscoverRequest(BaseModel):
    url: str
    max_competitors: int = 10
    search_engine: str = "google"


@router.post("/keyword-gap")
async def keyword_gap_analysis(request: KeywordGapRequest) -> dict[str, Any]:
    """Find keyword opportunities your competitors rank for but you don't."""
    from ..skills import CompetitorKeywordGapSkill
    from ..skills.base import SkillInput

    start = time.time()
    try:
        skill = CompetitorKeywordGapSkill()
        inp = SkillInput(
            url=request.url,
            params={
                "competitor_urls": request.competitor_urls,
                "max_keywords": request.max_keywords,
                "min_volume": request.min_volume,
            },
        )
        result = await skill.execute(inp)
        return {
            "status": "success",
            "url": request.url,
            "competitors": request.competitor_urls,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result.data if hasattr(result, "data") else result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/content-gap")
async def content_gap_analysis(request: ContentGapRequest) -> dict[str, Any]:
    """Identify content topics your competitors cover that you don't."""
    from ..skills import ContentGapAnalysisSkill
    from ..skills.base import SkillInput

    start = time.time()
    try:
        skill = ContentGapAnalysisSkill()
        inp = SkillInput(
            url=request.url,
            params={
                "competitor_urls": request.competitor_urls,
                "content_type": request.content_type,
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


@router.post("/analyze")
async def analyze_competitors(request: CompetitorAnalyzeRequest) -> dict[str, Any]:
    """Run full competitor analysis via CompetitorAnalystAgent."""
    from ..agents import CompetitorAnalystAgent

    start = time.time()
    try:
        agent = CompetitorAnalystAgent()
        result = await agent.analyze(
            url=request.url,
            competitor_urls=request.competitor_urls,
            auto_discover=request.auto_discover,
            depth=request.depth,
        )
        return {
            "status": "success",
            "url": request.url,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/discover")
async def discover_competitors(request: CompetitorDiscoverRequest) -> dict[str, Any]:
    """Auto-discover top competitors for a given URL."""
    start = time.time()
    try:
        try:
            from ..competitor_discovery import CompetitorDiscovery
            discovery = CompetitorDiscovery()
            competitors = await discovery.find(
                url=request.url,
                max_results=request.max_competitors,
                search_engine=request.search_engine,
            )
        except (ImportError, AttributeError):
            from ..agents import CompetitorAnalystAgent
            agent = CompetitorAnalystAgent()
            res = await agent.analyze(
                url=request.url,
                auto_discover=True,
                depth="quick",
            )
            competitors = res.get("competitors_found", [])

        return {
            "status": "success",
            "url": request.url,
            "competitors": competitors,
            "count": len(competitors) if isinstance(competitors, list) else 0,
            "elapsed_sec": round(time.time() - start, 2),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
