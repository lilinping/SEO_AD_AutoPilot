"""Keyword Research API endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Optional


router = APIRouter(prefix="/api/keywords", tags=["keywords"])


class KeywordResearchRequest(BaseModel):
    keyword: Optional[str] = None
    keywords: Optional[list[str]] = None
    seed: Optional[str] = None
    url: Optional[str] = None
    html: Optional[str] = None
    target_market: str = "US"
    language: str = "en"
    cluster: bool = True


@router.post("/research")
async def research_keywords(request: KeywordResearchRequest) -> dict[str, Any]:
    """Run keyword research analysis."""
    from ..skills.keyword_research import KeywordResearchSkill
    from ..skills.base import SkillInput
    import time

    start = time.time()
    try:
        skill = KeywordResearchSkill()
        params: dict[str, Any] = {}
        if request.keyword:
            params["keyword"] = request.keyword
        if request.keywords:
            params["keywords"] = request.keywords
        if request.seed:
            params["seed"] = request.seed
        if request.url:
            params["url"] = request.url
        if request.html:
            params["html"] = request.html
        params["target_market"] = request.target_market
        params["language"] = request.language
        params["cluster"] = request.cluster

        output = skill.execute(SkillInput(params=params))
        elapsed = int((time.time() - start) * 1000)

        if output.success:
            return {"success": True, "data": output.result, "execution_time_ms": elapsed}
        else:
            return {"success": False, "error": output.error, "execution_time_ms": elapsed}
    except Exception as e:
        return {"success": False, "error": str(e), "execution_time_ms": int((time.time() - start) * 1000)}
