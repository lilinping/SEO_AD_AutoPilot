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
    proposal: dict[str, Any] = {}
    proposer_role: str = "strategist"
    url: str = ""
    task_id: Optional[str] = None
    tenant_id: Optional[str] = None


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


def _resolve_role(name: str):
    """Map a role name to an AgentRole, defaulting to STRATEGIST."""
    from ..agents.base import AgentRole

    try:
        return AgentRole(name.lower())
    except ValueError:
        return AgentRole.STRATEGIST


def _build_debate_agents() -> list:
    """Instantiate the agents that participate in debates."""
    from ..agents import (
        SnifferAgent,
        QueryAgent,
        StrategistAgent,
        UXReviewerAgent,
        PolicyGuardAgent,
        AIOOptimizerAgent,
    )

    return [
        SnifferAgent(),
        QueryAgent(),
        StrategistAgent(),
        UXReviewerAgent(),
        PolicyGuardAgent(),
        AIOOptimizerAgent(),
    ]


def _persist_debate_log(request: "DebateRequest", debate_round: Any) -> None:
    """DB-007: persist the debate log for audit (best-effort, non-fatal)."""
    try:
        from ..db import Database

        db = Database()
        db.create_all()
        db.save_debate_log(
            topic=debate_round.topic or request.topic,
            proposer_role=debate_round.proposer.value,
            task_id=request.task_id,
            participants=[o.agent_role.value for o in debate_round.opinions],
            rounds=[
                {
                    "agent_role": o.agent_role.value,
                    "stance": o.stance.value,
                    "reasoning": o.reasoning,
                    "confidence": o.confidence,
                }
                for o in debate_round.opinions
            ],
            consensus_score=debate_round.consensus_score,
            resolution=str(debate_round.resolution),
            tenant_id=request.tenant_id,
        )
    except Exception:
        # Persistence is auxiliary; never break the debate flow.
        pass


@router.post("/debate")
async def debate(request: DebateRequest) -> dict[str, Any]:
    """Run a multi-agent debate on a topic and persist the log (DB-007)."""
    from ..agents.base import DebateEngine, SiteContext

    start = time.time()
    try:
        engine = DebateEngine(agents=_build_debate_agents(), max_rounds=max(1, request.rounds))
        context = SiteContext(url=request.url, raw_data=request.context)
        proposer_role = _resolve_role(request.proposer_role)
        proposal = request.proposal or {"topic": request.topic, **request.context}

        debate_round = engine.run_debate(
            topic=request.topic,
            proposal=proposal,
            proposer_role=proposer_role,
            context=context,
        )

        _persist_debate_log(request, debate_round)

        return {
            "status": "success",
            "topic": request.topic,
            "elapsed_sec": round(time.time() - start, 2),
            "result": {
                "round_id": debate_round.round_id,
                "topic": debate_round.topic,
                "proposer": debate_round.proposer.value,
                "consensus_score": debate_round.consensus_score,
                "final_confidence": debate_round.final_confidence,
                "rounds_count": debate_round.rounds_count,
                "resolution": debate_round.resolution,
                "opinions": [
                    {
                        "agent_role": o.agent_role.value,
                        "stance": o.stance.value,
                        "reasoning": o.reasoning,
                        "confidence": o.confidence,
                    }
                    for o in debate_round.opinions
                ],
            },
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
