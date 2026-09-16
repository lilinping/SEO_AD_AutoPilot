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
        is_snapshot = action not in {"features", "serp_features"}
        skill = SERPFeatureTrackerSkill() if not is_snapshot else RankSnapshotSkill()
        output = skill.execute(SkillInput(url=kwargs.get("url", ""), params=kwargs, context=context))
        result = dict(output.result)
        if output.success and is_snapshot:
            message = result.get("summary", "")
            result["summary"] = {"tracked_keywords": len(kwargs.get("keywords", [])), "message": message}
            # DB-003: persist per-keyword rank snapshots (best-effort, non-fatal).
            self._persist_snapshot(kwargs, result)
        return service_result("ranking", output.success, result, output.error, output.execution_time_ms)

    def _persist_snapshot(self, kwargs: dict[str, Any], result: dict[str, Any]) -> None:
        url = kwargs.get("url", "")
        if not self._db or not url:
            return
        keyword_rows = (result.get("snapshot") or {}).get("keyword_rows") or []
        if not keyword_rows:
            return
        try:
            self._db.save_ranking_snapshots(
                url=url,
                keyword_rows=keyword_rows,
                search_engine=kwargs.get("search_engine", "google"),
                locale=kwargs.get("locale", "en"),
                device=kwargs.get("device", "desktop"),
                tenant_id=kwargs.get("tenant_id"),
            )
        except Exception:
            # Persistence is auxiliary; never break the ranking flow.
            pass

    def history(
        self,
        url: str | None = None,
        keyword: str | None = None,
        tenant_id: Any = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return persisted rank snapshot history (DB-003)."""
        if not self._db:
            return []
        try:
            return self._db.list_ranking_snapshots(
                url=url, keyword=keyword, tenant_id=tenant_id, limit=limit
            )
        except Exception:
            return []
