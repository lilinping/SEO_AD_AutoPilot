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
        site_data = dict(kwargs.get("site_data") or {})
        for key, value in kwargs.items():
            if key not in {"url", "target_url", "site_data"}:
                site_data.setdefault(key, value)
        result = analyze_site_for_ads(url, site_data)
        return service_result("ad", True, result)
