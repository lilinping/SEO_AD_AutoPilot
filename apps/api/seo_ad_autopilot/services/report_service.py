"""Report service for assembling lightweight structured reports."""
from __future__ import annotations

import time
from typing import Any

from ._helpers import service_result


class ReportService:
    """Build structured report payloads from supplied sections."""

    def __init__(self, db=None, cache=None) -> None:
        self._db = db
        self._cache = cache

    async def run(self, **kwargs) -> dict[str, Any]:
        start = time.time()
        title = kwargs.get("title") or "SEO-AD AutoPilot Report"
        sections = kwargs.get("sections") or {}
        result = {
            "title": title,
            "sections": sections,
            "section_count": len(sections),
            "format": kwargs.get("format", "json"),
        }
        return service_result("report", True, result, execution_time_ms=int((time.time() - start) * 1000))
