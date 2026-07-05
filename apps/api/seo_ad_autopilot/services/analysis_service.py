"""Analysis Service — GAP-007.

Extracted from service.py: site analysis orchestration logic.
Wraps CoordinatorAgent with caching, task persistence, and webhook callbacks.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Optional


class AnalysisService:
    """Orchestrates full-site SEO analysis pipeline."""

    def __init__(self, db=None, cache=None) -> None:
        self._db    = db
        self._cache = cache
        self._tasks: dict[str, dict] = {}

    async def run(
        self,
        url: str,
        agent_filter: Optional[list[str]] = None,
        dry_run: bool = False,
        locale: str = "en",
        timeout_sec: int = 120,
        webhook_url: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run full analysis and return AnalysisReport dict."""
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {"status": "running", "url": url, "started_at": time.time()}

        try:
            from ..agents.coordinator import CoordinatorAgent
            coordinator = CoordinatorAgent()
            report = await coordinator.async_analyze(
                url=url,
                agent_filter=agent_filter,
                dry_run=dry_run,
                locale=locale,
                timeout_sec=timeout_sec,
            )
            result = report.to_dict()
            self._tasks[task_id].update({"status": "complete", "result": result})

            if webhook_url:
                asyncio.create_task(self._notify_webhook(webhook_url, task_id, result))

            return {"task_id": task_id, "status": "complete", **result}
        except Exception as exc:
            self._tasks[task_id].update({"status": "error", "error": str(exc)})
            raise

    def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        return self._tasks.get(task_id)

    @staticmethod
    async def _notify_webhook(url: str, task_id: str, payload: dict) -> None:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json={"task_id": task_id, "event": "complete", "data": payload})
        except Exception:
            pass
