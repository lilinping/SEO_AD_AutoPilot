"""Crawl service facade around the crawler skill."""
from __future__ import annotations

from typing import Any

from ..skills import SiteCrawlerSkill, SkillInput
from ._helpers import service_result


class CrawlService:
    """Run crawl operations through the shared skill interface."""

    def __init__(self, db=None, cache=None) -> None:
        self._db = db
        self._cache = cache

    async def run(self, **kwargs) -> dict[str, Any]:
        url = kwargs.get("url") or kwargs.get("target_url") or ""
        skill = SiteCrawlerSkill()
        output = skill.execute(SkillInput(url=url, params={**kwargs, "url": url}))
        if not output.success and url:
            return service_result("crawl", True, {"url": url, "warning": output.error}, output.error, output.execution_time_ms)
        return service_result("crawl", output.success, output.result, output.error, output.execution_time_ms)
