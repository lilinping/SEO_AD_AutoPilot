"""Competitor service facade around competitor analysis skills."""
from __future__ import annotations

from typing import Any

from ..skills import CompetitorKeywordGapSkill, ContentGapAnalysisSkill, SkillInput
from ._helpers import service_result


class CompetitorService:
    """Run keyword-gap and content-gap competitor analysis."""

    def __init__(self, db=None, cache=None) -> None:
        self._db = db
        self._cache = cache

    async def run(self, **kwargs) -> dict[str, Any]:
        action = str(kwargs.pop("action", "keyword_gap"))
        context = kwargs.pop("context", {}) or {}
        if not context.get("competitor_data") and kwargs.get("competitors"):
            context["competitor_data"] = {c: {"keyword_positions": {}} for c in kwargs.get("competitors", [])}
        skill = ContentGapAnalysisSkill() if action in {"content_gap", "content"} else CompetitorKeywordGapSkill()
        output = skill.execute(SkillInput(url=kwargs.get("url", ""), params=kwargs, context=context))
        result = dict(output.result)
        if output.success and "total_gap_keywords" in result:
            result["gap_count"] = result["total_gap_keywords"]
        return service_result("competitor", output.success, result, output.error, output.execution_time_ms)
