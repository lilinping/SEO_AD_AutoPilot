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
        # DB-005: persist task queue state (best-effort, non-fatal).
        self._persist_task(task_id, url, "running", 0, agent_filter, dry_run, locale)

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
            self._persist_task(task_id, url, "complete", 100, agent_filter, dry_run, locale, result=result)

            if webhook_url:
                asyncio.create_task(self._notify_webhook(webhook_url, task_id, result))

            return {"task_id": task_id, "status": "complete", **result}
        except Exception as exc:
            self._tasks[task_id].update({"status": "error", "error": str(exc)})
            self._persist_task(task_id, url, "error", 0, agent_filter, dry_run, locale, error=str(exc))
            raise

    def _persist_task(
        self,
        task_id: str,
        url: str,
        status: str,
        percent: int,
        agent_filter: Optional[list[str]],
        dry_run: bool,
        locale: str,
        result: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        if not self._db:
            return
        try:
            self._db.save_analysis_task(
                task_id=task_id,
                url=url,
                status=status,
                percent=percent,
                agent_filter=agent_filter,
                dry_run=dry_run,
                locale=locale,
                result=result,
                error=error,
            )
        except Exception:
            # Persistence is auxiliary; never break the analysis flow.
            pass

    def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        task = self._tasks.get(task_id)
        if task is not None:
            return task
        # DB-005: fall back to persisted state (survives process restarts).
        if self._db:
            try:
                return self._db.get_analysis_task(task_id)
            except Exception:
                return None
        return None


    @staticmethod
    async def _notify_webhook(url: str, task_id: str, payload: dict) -> None:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json={"task_id": task_id, "event": "complete", "data": payload})
        except Exception:
            pass
