"""Ad service facade around ad platform auto-discovery."""
from __future__ import annotations

from typing import Any

from ._helpers import service_result


class AdService:
    """Analyze ad readiness and platform recommendations."""

    def __init__(self, db=None, cache=None) -> None:
        self._db = db
        self._cache = cache

    async def run(self, **kwargs) -> dict[str, Any]:
        from ..ad_platforms.auto_discovery import analyze_site_for_ads

        url = kwargs.get("url") or kwargs.get("target_url") or ""
        tenant_id = kwargs.get("tenant_id")
        site_data = dict(kwargs.get("site_data") or {})
        for key, value in kwargs.items():
            if key not in {"url", "target_url", "site_data", "tenant_id"}:
                site_data.setdefault(key, value)
        result = analyze_site_for_ads(url, site_data)

        # DB-006: persist recommendation history (best-effort, non-fatal).
        self._persist(url, result, site_data, tenant_id)

        return service_result("ad", True, result)

    def _persist(self, url: str, result: dict[str, Any], site_data: dict[str, Any], tenant_id: Any) -> None:
        if not self._db or not url:
            return
        try:
            platforms = result.get("recommendations") or result.get("suitable_platforms") or []
            self._db.save_ad_recommendation(
                url=url,
                platforms=platforms,
                site_data=site_data,
                tenant_id=tenant_id,
            )
        except Exception:
            # Persistence is auxiliary; never break the recommendation flow.
            pass

    def history(self, url: str | None = None, tenant_id: Any = None, limit: int = 50) -> list[dict[str, Any]]:
        """Return persisted recommendation history (DB-006)."""
        if not self._db:
            return []
        try:
            return self._db.list_ad_recommendations(url=url, tenant_id=tenant_id, limit=limit)
        except Exception:
            return []
