"""Agent orchestration router.

Endpoints:
  POST /api/agents/analyze          – full multi-agent analysis
  POST /api/agents/debate           – run DebateEngine on a topic
  GET  /api/agents/list             – list available agents
"""

from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

router = APIRouter(prefix="/api/agents", tags=["agents"])


# ── Request / Response models ────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    url: str
    agent_filter: Optional[list[str]] = None   # e.g. ["sniffer", "query"]
    dry_run: bool = False
    locale: str = "en"
    timeout_sec: int = 120


class DebateRequest(BaseModel):
    topic: str
    context: dict[str, Any] = {}
    rounds: int = 2


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze(request: AnalyzeRequest) -> dict[str, Any]:
    """Run full multi-agent SEO analysis on a URL."""
    from ..agents import CoordinatorAgent

    start = time.time()
    try:
        coordinator = CoordinatorAgent()
        result = await coordinator.async_analyze(
            url=request.url,
            agent_filter=request.agent_filter,
            dry_run=request.dry_run,
            locale=request.locale,
            timeout_sec=request.timeout_sec,
        )
        return {
            "status": "success",
            "url": request.url,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result.to_dict(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/debate")
async def debate(request: DebateRequest) -> dict[str, Any]:
    """Run DebateEngine on a given topic with provided context."""
    from ..agents.base import DebateEngine, AgentRole

    start = time.time()
    try:
        engine = DebateEngine()
        result = engine.run(
            topic=request.topic,
            context=request.context,
            rounds=request.rounds,
        )
        return {
            "status": "success",
            "topic": request.topic,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/list")
async def list_agents() -> dict[str, Any]:
    """List all registered agent roles."""
    from ..agents.base import AgentRole

    return {
        "agents": [role.value for role in AgentRole],
        "count": len(AgentRole),
    }
