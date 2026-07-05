"""Coordinator Agent – async workflow orchestration with parallel agent execution.

Phase 1 P1 changes (GAP-009 / AGT-002 / AGT-003 / AGT-006):
- async analyze() replacing sync analyze()
- asyncio.gather() for parallel agent execution
- agent_filter: run only a subset of agents
- dry_run=True: return plan without executing skills
- timeout_sec: per-agent timeout
- AnalysisReport: standardised output dataclass
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .base import (
    Agent,
    AgentOutput,
    AgentRole,
    DebateRound,
    SiteContext,
    DebateEngine,
)


# ── Output model ─────────────────────────────────────────────────────────────

@dataclass
class AnalysisReport:
    """Standardised full-pipeline analysis report."""

    url: str
    agent_outputs: dict[str, AgentOutput]       # role_value → AgentOutput
    debates: list[DebateRound]
    selected_skills: list[dict[str, Any]]
    execution_sequence: list[dict[str, Any]]
    approval_requirements: dict[str, Any]
    monitoring_plan: dict[str, Any]
    estimated_duration: str
    dry_run: bool = False
    elapsed_sec: float = 0.0
    confidence: float = 0.85
    risk_score: float = 0.15
    workflow_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "dry_run": self.dry_run,
            "elapsed_sec": self.elapsed_sec,
            "confidence": self.confidence,
            "risk_score": self.risk_score,
            "workflow_summary": self.workflow_summary,
            "agent_outputs": {
                k: {
                    "role": v.agent_role.value,
                    "confidence": v.confidence,
                    "risk_score": v.risk_score,
                    "needs_human_review": v.needs_human_review,
                    "content": v.content,
                    "reasoning": v.reasoning,
                }
                for k, v in self.agent_outputs.items()
            },
            "debates": [
                {
                    "topic": d.topic,
                    "proposer": d.proposer.value,
                    "consensus_score": d.consensus_score,
                    "resolution_summary": str(d.resolution)[:200],
                }
                for d in self.debates
            ],
            "selected_skills": self.selected_skills,
            "execution_sequence": self.execution_sequence,
            "approval_requirements": self.approval_requirements,
            "monitoring_plan": self.monitoring_plan,
            "estimated_duration": self.estimated_duration,
        }


# ── Agent registry ────────────────────────────────────────────────────────────

def _build_agent_registry() -> dict[AgentRole, Agent]:
    """Lazy-import all agents and return a role → instance mapping."""
    from .sniffer import SnifferAgent
    from .query import QueryAgent
    from .geo import GEOAgent
    from .strategist import StrategistAgent
    from .ux_reviewer import UXReviewerAgent
    from .policy_guard import PolicyGuardAgent
    from .aio_optimizer import AIOOptimizerAgent
    from .rank_tracker import RankTrackerAgent
    from .competitor_analyst import CompetitorAnalystAgent

    return {
        AgentRole.SNIFFER:            SnifferAgent(),
        AgentRole.QUERY:              QueryAgent(),
        AgentRole.GEO:                GEOAgent(),
        AgentRole.STRATEGIST:         StrategistAgent(),
        AgentRole.UX_REVIEWER:        UXReviewerAgent(),
        AgentRole.POLICY_GUARD:       PolicyGuardAgent(),
        AgentRole.AIO_OPTIMIZER:      AIOOptimizerAgent(),
        AgentRole.RANK_TRACKER:       RankTrackerAgent(),
        AgentRole.COMPETITOR_ANALYST: CompetitorAnalystAgent(),
    }


# ── Coordinator ───────────────────────────────────────────────────────────────

class CoordinatorAgent(Agent):
    """Coordinator Agent – orchestrates the entire analysis workflow.

    Key upgrades (Phase 1 P1):
    - Parallel agent execution via asyncio.gather
    - agent_filter: run only a named subset of agents
    - dry_run: return the plan without executing
    - timeout_sec: per-agent timeout (default 60s)
    - Returns AnalysisReport instead of raw AgentOutput
    """

    def __init__(self) -> None:
        super().__init__()
        self._role = AgentRole.COORDINATOR

    # ── Legacy sync interface (backwards-compatible) ──────────────────────────

    def analyze(self, context: SiteContext) -> AgentOutput:
        """Sync wrapper – runs the async pipeline in a new event loop."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already inside an event loop (e.g. FastAPI); create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(asyncio.run, self._async_analyze_context(context))
                    report = fut.result(timeout=120)
            else:
                report = loop.run_until_complete(self._async_analyze_context(context))
        except RuntimeError:
            report = asyncio.run(self._async_analyze_context(context))

        return self._create_output(
            content=report.to_dict(),
            confidence=report.confidence,
            risk_score=report.risk_score,
            reasoning=report.workflow_summary,
        )

    def challenge(
        self, other_output: AgentOutput, context: SiteContext
    ) -> Optional[dict[str, Any]]:
        return None   # Coordinator synthesises, doesn't challenge

    # ── Primary async interface ───────────────────────────────────────────────

    async def async_analyze(
        self,
        url: str,
        agent_filter: Optional[list[str]] = None,
        dry_run: bool = False,
        locale: str = "en",
        timeout_sec: int = 60,
    ) -> AnalysisReport:
        """Full async pipeline entry point called by the router."""
        start = time.time()

        context = SiteContext(
            url=url,
            raw_data={"locale": locale},
        )

        report = await self._async_analyze_context(
            context,
            agent_filter=agent_filter,
            dry_run=dry_run,
            timeout_sec=timeout_sec,
        )
        report.elapsed_sec = round(time.time() - start, 2)
        return report

    async def _async_analyze_context(
        self,
        context: SiteContext,
        agent_filter: Optional[list[str]] = None,
        dry_run: bool = False,
        timeout_sec: int = 60,
    ) -> AnalysisReport:
        start = time.time()

        # ── 1. Build agent registry ──────────────────────────────────────────
        registry = _build_agent_registry()

        # ── 2. Apply agent_filter ────────────────────────────────────────────
        if agent_filter:
            filter_set = {r.lower() for r in agent_filter}
            registry = {
                role: agent
                for role, agent in registry.items()
                if role.value.lower() in filter_set
            }

        # ── 3. Run agents in PARALLEL ────────────────────────────────────────
        agent_outputs: dict[str, AgentOutput] = {}
        if registry:
            async def _run_one(role: AgentRole, agent: Agent) -> tuple[str, AgentOutput]:
                try:
                    result = await asyncio.wait_for(
                        self._call_agent(agent, context),
                        timeout=timeout_sec,
                    )
                    return role.value, result
                except asyncio.TimeoutError:
                    return role.value, self._timeout_output(role)
                except Exception as exc:  # noqa: BLE001
                    return role.value, self._error_output(role, str(exc))

            pairs = await asyncio.gather(
                *[_run_one(role, agent) for role, agent in registry.items()]
            )
            agent_outputs = dict(pairs)

            # Write outputs back into context for debate engine
            context.site_profile   = agent_outputs.get("sniffer", AgentOutput(AgentRole.SNIFFER, {})).content
            context.geo_analysis   = agent_outputs.get("geo",     AgentOutput(AgentRole.GEO, {})).content
            context.ad_analysis    = agent_outputs.get("aio_optimizer", AgentOutput(AgentRole.AIO_OPTIMIZER, {})).content
            context.opportunities  = (
                agent_outputs.get("strategist", AgentOutput(AgentRole.STRATEGIST, {}))
                .content.get("opportunities", [])
            )

        # ── 4. Run debates ───────────────────────────────────────────────────
        debates: list[DebateRound] = []
        if not dry_run and len(registry) >= 3:
            try:
                debates = self._run_debates(context)
            except Exception:
                debates = []

        # ── 5. Select skills ─────────────────────────────────────────────────
        skills = self._select_skills(context, {
            "site_profile":  context.site_profile,
            "opportunities": context.opportunities,
            "geo_analysis":  context.geo_analysis,
            "ad_analysis":   context.ad_analysis,
        })

        # ── 6. Build execution sequence ──────────────────────────────────────
        execution_sequence   = self._create_execution_sequence(skills, context)
        approval_requirements = self._determine_approval_requirements(skills)
        monitoring_plan       = self._create_monitoring_plan(skills, context)

        # ── 7. Compute aggregate confidence ─────────────────────────────────
        confidences = [o.confidence for o in agent_outputs.values() if o.confidence > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.85
        risk_scores = [o.risk_score for o in agent_outputs.values()]
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.15

        return AnalysisReport(
            url=context.url,
            agent_outputs=agent_outputs,
            debates=debates,
            selected_skills=skills,
            execution_sequence=execution_sequence,
            approval_requirements=approval_requirements,
            monitoring_plan=monitoring_plan,
            estimated_duration=self._estimate_duration(skills),
            dry_run=dry_run,
            elapsed_sec=round(time.time() - start, 2),
            confidence=round(avg_confidence, 3),
            risk_score=round(avg_risk, 3),
            workflow_summary=(
                f"Analyzed {context.url} with {len(agent_outputs)} agents "
                f"({'dry-run' if dry_run else 'live'}), "
                f"{len(debates)} debates, {len(skills)} skills selected."
            ),
        )

    # ── Agent call helper ─────────────────────────────────────────────────────

    @staticmethod
    async def _call_agent(agent: Agent, context: SiteContext) -> AgentOutput:
        """Call agent.analyze(), transparently handles sync vs async."""
        if asyncio.iscoroutinefunction(agent.analyze):
            return await agent.analyze(context)
        # Run sync agents in a thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, agent.analyze, context)

    @staticmethod
    def _timeout_output(role: AgentRole) -> AgentOutput:
        return AgentOutput(
            agent_role=role,
            content={"error": "timeout"},
            confidence=0.0,
            risk_score=0.5,
            reasoning="Agent timed out",
        )

    @staticmethod
    def _error_output(role: AgentRole, msg: str) -> AgentOutput:
        return AgentOutput(
            agent_role=role,
            content={"error": msg},
            confidence=0.0,
            risk_score=0.5,
            reasoning=f"Agent raised exception: {msg}",
        )

    # ── Debate orchestration (unchanged from original) ────────────────────────

    def _run_debates(self, context: SiteContext) -> list[DebateRound]:
        from .sniffer import SnifferAgent
        from .query import QueryAgent
        from .strategist import StrategistAgent
        from .ux_reviewer import UXReviewerAgent

        debates: list[DebateRound] = list(context.debates or [])
        agents = [SnifferAgent(), QueryAgent(), StrategistAgent(), UXReviewerAgent()]
        engine = DebateEngine(agents=agents, max_rounds=2)

        # ── 特性开关：第3轮终裁（AGT-005）───────────────────────────────────
        import os as _os
        _round3_enabled = _os.getenv("FEATURE_DEBATE_ROUND3_ENABLED", "false").lower() == "true"

        top_opp = (context.opportunities or [{}])[0]
        readiness_debate = engine.run_debate(
            topic="Is the site technically ready for SEO/GEO optimisation?",
            proposal={
                "action": "optimise_site",
                "top_opportunity": top_opp,
                "url": context.url,
            },
            proposer_role=AgentRole.QUERY,
            context=context,
            participants=[AgentRole.SNIFFER, AgentRole.STRATEGIST, AgentRole.UX_REVIEWER],
        )
        debates.append(readiness_debate)

        opps = context.opportunities or []
        if len(opps) >= 3:
            content_n = sum(1 for o in opps if "content" in o.get("type", ""))
            tech_n    = sum(1 for o in opps if "technical" in o.get("type", ""))
            priority_debate = engine.run_debate(
                topic="Should we prioritise content or technical improvements first?",
                proposal={
                    "recommendation": "content_first" if content_n >= tech_n else "technical_first",
                    "content_opportunities": content_n,
                    "technical_opportunities": tech_n,
                },
                proposer_role=AgentRole.STRATEGIST,
                context=context,
                participants=[AgentRole.SNIFFER, AgentRole.QUERY, AgentRole.UX_REVIEWER],
            )
            debates.append(priority_debate)

        # ── AGT-005: 第3轮终裁 ─────────────────────────────────────────────
        if _round3_enabled and debates:
            last_debate = debates[-1]
            # 触发条件：共识分低 OR resolution 含 policy 风险
            needs_arbitration = (
                last_debate.consensus_score < 0.6
                or last_debate.resolution.get("_debate_warning")
                or any(
                    o.stance.value == "disagree"
                    for o in last_debate.opinions
                    if o.agent_role.value == "policy_guard"
                )
            )
            if needs_arbitration:
                from .policy_guard import PolicyGuardAgent
                from .strategist import StrategistAgent
                arb_agents = [
                    StrategistAgent(),
                    PolicyGuardAgent(),
                    *agents,
                ]
                arb_engine = DebateEngine(agents=arb_agents, max_rounds=1)
                arb_round = arb_engine.run_final_arbitration(
                    debate_round=last_debate,
                    context=context,
                )
                debates.append(arb_round)

        context.debates = debates
        return debates

    # ── Skill selection (unchanged) ───────────────────────────────────────────

    def _select_skills(
        self, context: SiteContext, all_outputs: dict[str, Any]
    ) -> list[dict[str, Any]]:
        skills: list[dict[str, Any]] = [
            {"skill": "SiteCrawler", "params": {"url": context.url}, "priority": "high", "requires_approval": False},
        ]
        for opp in (all_outputs.get("opportunities") or [])[:5]:
            skill = self._map_opportunity_to_skill(opp)
            if skill:
                skills.append(skill)
        if all_outputs.get("geo_analysis"):
            skills.append({"skill": "GEOOptimizer", "params": {"url": context.url}, "priority": "high", "requires_approval": False})
        if all_outputs.get("ad_analysis"):
            skills.append({"skill": "AdSlotAuditor", "params": {"url": context.url}, "priority": "medium", "requires_approval": False})
        return skills

    def _map_opportunity_to_skill(self, opportunity: dict[str, Any]) -> Optional[dict[str, Any]]:
        opp_type = opportunity.get("type", "")
        if "schema" in opp_type:
            return {"skill": "SchemaBuilder", "params": {"type": opp_type}, "priority": opportunity.get("priority", "medium"), "requires_approval": True}
        if "content" in opp_type:
            return {"skill": "ContentGenerator", "params": {"type": opp_type}, "priority": opportunity.get("priority", "medium"), "requires_approval": True}
        if "technical" in opp_type:
            return {"skill": "TechnicalSeoPatcher", "params": {"type": opp_type}, "priority": opportunity.get("priority", "medium"), "requires_approval": True}
        return None

    def _create_execution_sequence(self, skills: list[dict[str, Any]], context: SiteContext) -> list[dict[str, Any]]:
        sequence: list[dict[str, Any]] = []
        for skill in skills:
            if not skill.get("requires_approval"):
                sequence.append({"phase": 1, "step": len(sequence) + 1, "skill": skill["skill"], "params": skill["params"], "parallel": True})
        for skill in skills:
            if skill.get("requires_approval"):
                sequence.append({"phase": 2, "step": len(sequence) + 1, "skill": skill["skill"], "params": skill["params"], "parallel": False})
        return sequence

    def _determine_approval_requirements(self, skills: list[dict[str, Any]]) -> dict[str, Any]:
        requires = [s for s in skills if s.get("requires_approval")]
        return {"total_skills": len(skills), "requires_approval": len(requires), "auto_approved": len(skills) - len(requires), "approval_threshold": "medium"}

    def _create_monitoring_plan(self, skills: list[dict[str, Any]], context: SiteContext) -> dict[str, Any]:
        return {
            "metrics_to_track": ["organic_traffic", "search_visibility", "core_web_vitals", "ai_search_mentions"],
            "monitoring_frequency": "daily",
            "alert_thresholds": {"traffic_drop": 0.1, "performance_degradation": 0.2},
        }

    def _estimate_duration(self, skills: list[dict[str, Any]]) -> str:
        return f"{len(skills) * 2} hours"

    def _create_workflow_summary(self, all_outputs: dict[str, Any], debates: list[DebateRound]) -> str:
        return f"Analyzed site with {len(debates)} debates and generated optimization strategy"
