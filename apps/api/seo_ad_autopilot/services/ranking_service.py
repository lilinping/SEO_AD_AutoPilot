"""Ranking service facade around rank tracking skills."""
from __future__ import annotations

from typing import Any

from ..skills import RankSnapshotSkill, SERPFeatureTrackerSkill, SkillInput
from ._helpers import service_result


class RankingService:
    """Create rank snapshots and SERP feature reports."""

    def __init__(self, db=None, cache=None) -> None:
        self._db = db
        self._cache = cache

    async def run(self, **kwargs) -> dict[str, Any]:
        action = str(kwargs.pop("action", "snapshot"))
        context = kwargs.pop("context", {}) or {}
        skill = SERPFeatureTrackerSkill() if action in {"features", "serp_features"} else RankSnapshotSkill()
        output = skill.execute(SkillInput(url=kwargs.get("url", ""), params=kwargs, context=context))
        result = dict(output.result)
        if output.success and action not in {"features", "serp_features"}:
            message = result.get("summary", "")
            result["summary"] = {"tracked_keywords": len(kwargs.get("keywords", [])), "message": message}
        return service_result("ranking", output.success, result, output.error, output.execution_time_ms)
