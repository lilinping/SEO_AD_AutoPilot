"""WebSocket real-time progress push for long-running agent tasks.

Phase 1 P1 (GAP-014 / US-05-01):
- /api/v1/ws/analysis/{task_id}  — subscribe to progress events for a task
- POST /api/tasks          — enqueue a new analysis task (returns task_id)
- GET  /api/tasks/{id}     — poll task status (for non-WS clients)

Progress event schema:
{
  "task_id":     "uuid4",
  "event":       "agent_started" | "agent_completed" | "debate_round" | "analysis_complete" | "error",
  "percent":     0-100,
  "message":     "...",
  "data":        {...}             // event-specific payload
}
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/ws", tags=["websocket"])
_api_router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# ── Event model ───────────────────────────────────────────────────────────────

@dataclass
class ProgressEvent:
    task_id:  str
    event:    str                      # agent_started | agent_completed | debate_round | analysis_complete | error
    percent:  int = 0
    message:  str = ""
    agent:    Optional[str] = None
    data:     dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


# ── In-memory task registry ───────────────────────────────────────────────────

class _TaskRegistry:
    """Thread-safe in-memory task registry with per-task asyncio queues."""

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}    # task_id → metadata
        self._queues: dict[str, asyncio.Queue] = {}    # task_id → Queue[ProgressEvent]

    def create(self, task_id: str, url: str, params: dict[str, Any]) -> None:
        self._tasks[task_id] = {
            "task_id": task_id,
            "url":     url,
            "params":  params,
            "status":  "queued",
            "percent": 0,
            "result":  None,
            "error":   None,
        }
        self._queues[task_id] = asyncio.Queue(maxsize=512)

    def get(self, task_id: str) -> Optional[dict[str, Any]]:
        return self._tasks.get(task_id)

    def update(self, task_id: str, **kwargs: Any) -> None:
        if task_id in self._tasks:
            self._tasks[task_id].update(kwargs)

    async def push(self, event: ProgressEvent) -> None:
        q = self._queues.get(event.task_id)
        if q:
            self.update(event.task_id, percent=event.percent, status=event.event)
            await q.put(event)

    async def subscribe(self, task_id: str):
        """Async generator that yields ProgressEvent objects until done."""
        q = self._queues.get(task_id)
        if not q:
            return
        while True:
            event: ProgressEvent = await q.get()
            yield event
            if event.event in ("analysis_complete", "error"):
                break


# Module-level singleton
registry = _TaskRegistry()


# ── Analysis task runner ──────────────────────────────────────────────────────

async def _run_analysis_task(task_id: str, url: str, params: dict[str, Any]) -> None:
    """Run the coordinator analysis pipeline and push progress events."""
    try:
        from .agents.coordinator import CoordinatorAgent

        await registry.push(ProgressEvent(
            task_id=task_id, event="agent_started", percent=5,
            message=f"Analysis started for {url}",
        ))

        coordinator = CoordinatorAgent()

        # Patch coordinator to emit progress events during parallel agent execution
        original_gather = asyncio.gather

        async def _gather_with_progress(*coros, **kw):
            """Wrap asyncio.gather to emit per-agent progress events."""
            total = len(coros)
            completed = 0

            async def _wrap(coro, idx: int):
                nonlocal completed
                result = await coro
                completed += 1
                pct = 5 + int(70 * completed / total)
                await registry.push(ProgressEvent(
                    task_id=task_id,
                    event="agent_completed",
                    percent=pct,
                    message=f"Agent {idx + 1}/{total} completed",
                    data={"agent_index": idx},
                ))
                return result

            wrapped = [_wrap(c, i) for i, c in enumerate(coros)]
            return await original_gather(*wrapped, **kw)

        # Temporarily patch asyncio.gather within this task scope
        # (non-invasive: no global monkey-patching)
        import sys
        # Save reference to patch
        old_gather = asyncio.gather
        asyncio.gather = _gather_with_progress

        try:
            report = await coordinator.async_analyze(
                url=url,
                agent_filter=params.get("agent_filter"),
                dry_run=params.get("dry_run", False),
                locale=params.get("locale", "en"),
                timeout_sec=params.get("timeout_sec", 60),
            )
        finally:
            # Restore original gather
            asyncio.gather = old_gather

        # If there are debate rounds, emit debate_round events
        if hasattr(report, "debates") and report.debates:
            for debate in report.debates:
                await registry.push(ProgressEvent(
                    task_id=task_id,
                    event="debate_round",
                    percent=80,
                    message=f"Debate round completed: {debate.topic}",
                    data={
                        "topic": debate.topic,
                        "proposer": debate.proposer.value if hasattr(debate.proposer, "value") else str(debate.proposer),
                        "consensus_score": debate.consensus_score,
                    },
                ))

        registry.update(
            task_id,
            status="complete",
            percent=100,
            result=report.to_dict(),
        )
        await registry.push(ProgressEvent(
            task_id=task_id, event="analysis_complete", percent=100,
            message="Analysis complete",
            data={"elapsed_sec": report.elapsed_sec},
        ))

    except Exception as exc:  # noqa: BLE001
        registry.update(task_id, status="error", error=str(exc))
        await registry.push(ProgressEvent(
            task_id=task_id, event="error", percent=0,
            message=str(exc),
        ))


# ── Request / response models ─────────────────────────────────────────────────

class CreateTaskRequest(BaseModel):
    url: str
    agent_filter: Optional[list[str]] = None
    dry_run: bool = False
    locale: str = "en"
    timeout_sec: int = 60


# ── REST endpoints ────────────────────────────────────────────────────────────

@_api_router.post("")
async def create_task(request: CreateTaskRequest) -> dict[str, Any]:
    """Enqueue a new analysis task. Returns task_id for WS subscription."""
    task_id = str(uuid.uuid4())
    params = request.model_dump(exclude={"url"})
    registry.create(task_id, request.url, params)

    # Fire-and-forget background task
    asyncio.create_task(_run_analysis_task(task_id, request.url, params))

    return {
        "task_id": task_id,
        "status": "queued",
        "ws_url": f"/api/v1/ws/analysis/{task_id}",
        "poll_url": f"/api/tasks/{task_id}",
    }


@_api_router.get("/{task_id}")
async def get_task(task_id: str) -> dict[str, Any]:
    """Poll task status (alternative to WebSocket for simple clients)."""
    task = registry.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")
    return task


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/analysis/{task_id}")
async def ws_progress(websocket: WebSocket, task_id: str) -> None:
    """Stream real-time progress events for a running analysis task."""
    await websocket.accept()

    task = registry.get(task_id)
    if not task:
        await websocket.send_json({"event": "error", "message": f"Task {task_id!r} not found"})
        await websocket.close(code=4004)
        return

    try:
        async for event in registry.subscribe(task_id):
            await websocket.send_json(event.to_json())
            if event.event in ("analysis_complete", "error"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# Expose both routers for registration in app.py
all_ws_routers = [router, _api_router]
