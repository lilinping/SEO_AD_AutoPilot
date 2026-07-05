"""Agent base class with BettaFish-style debate mechanism.

Enhanced from BettaFish's forum-style multi-agent collaboration:
- Multiple debate rounds with iterative refinement
- Moderator role for synthesis
- Confidence scoring and consensus building
- Debate history tracking
- Structured reasoning chains
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class AgentRole(str, Enum):
    """Agent roles in the analysis pipeline."""
    SNIFFER = "sniffer"
    QUERY = "query"
    GEO = "geo"
    STRATEGIST = "strategist"
    UX_REVIEWER = "ux_reviewer"
    COORDINATOR = "coordinator"
    MODERATOR = "moderator"
    POLICY_GUARD = "policy_guard"
    AIO_OPTIMIZER = "aio_optimizer"
    RANK_TRACKER = "rank_tracker"
    COMPETITOR_ANALYST = "competitor_analyst"


class DebateStance(str, Enum):
    """Debate stance options."""
    AGREE = "agree"
    PARTIALLY_AGREE = "partially_agree"
    DISAGREE = "disagree"
    ABSTAIN = "abstain"


@dataclass
class AgentOutput:
    """Structured output from an agent."""
    agent_role: AgentRole
    content: dict[str, Any]
    confidence: float = 0.0
    risk_score: float = 0.0
    needs_human_review: bool = False
    reasoning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DebateOpinion:
    """An agent's opinion on a topic."""
    agent_role: AgentRole
    stance: DebateStance
    reasoning: str
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    conditions: list[str] = field(default_factory=list)


@dataclass
class DebateRound:
    """A round of debate between agents."""
    round_id: str = field(default_factory=lambda: f"debate_{uuid4().hex[:8]}")
    topic: str = ""
    proposer: AgentRole = AgentRole.SNIFFER
    proposal: dict[str, Any] = field(default_factory=dict)
    opinions: list[DebateOpinion] = field(default_factory=list)
    resolution: dict[str, Any] = field(default_factory=dict)
    consensus_score: float = 0.0
    rounds_count: int = 0
    final_confidence: float = 0.0


@dataclass
class SiteContext:
    """Shared context for all agents."""
    url: str
    raw_data: dict[str, Any] = field(default_factory=dict)
    page_snapshots: list[dict[str, Any]] = field(default_factory=list)
    site_profile: Optional[dict[str, Any]] = None
    opportunities: list[dict[str, Any]] = field(default_factory=list)
    geo_analysis: Optional[dict[str, Any]] = None
    ad_analysis: Optional[dict[str, Any]] = None
    debates: list[DebateRound] = field(default_factory=list)
    debate_history: list[dict[str, Any]] = field(default_factory=list)


class Agent(ABC):
    """Base class for all agents."""
    
    def __init__(self):
        self._role: AgentRole = AgentRole.SNIFFER
    
    @property
    def role(self) -> AgentRole:
        return self._role
    
    @abstractmethod
    def analyze(self, context: SiteContext) -> AgentOutput:
        """Analyze the site and produce structured output."""
        pass
    
    def offer_opinion(
        self,
        topic: str,
        proposal: dict[str, Any],
        context: SiteContext,
        previous_opinions: list[DebateOpinion] = None,
    ) -> DebateOpinion:
        """Offer an opinion on a debate topic.
        
        Override this to implement agent-specific debate behavior.
        Default: abstain with no opinion.
        """
        return DebateOpinion(
            agent_role=self._role,
            stance=DebateStance.ABSTAIN,
            reasoning="No specific opinion on this topic",
        )
    
    def challenge(self, other_output: AgentOutput, context: SiteContext) -> Optional[dict[str, Any]]:
        """Challenge another agent's output. Return challenge details or None."""
        return None
    
    def defend(self, challenge: dict[str, Any], context: SiteContext) -> Optional[dict[str, Any]]:
        """Defend against a challenge. Return defense details or None."""
        return None
    
    def _create_output(
        self,
        content: dict[str, Any],
        confidence: float = 0.8,
        risk_score: float = 0.0,
        needs_human_review: bool = False,
        reasoning: str = "",
    ) -> AgentOutput:
        """Create a structured agent output."""
        return AgentOutput(
            agent_role=self._role,
            content=content,
            confidence=confidence,
            risk_score=risk_score,
            needs_human_review=needs_human_review,
            reasoning=reasoning,
        )


class DebateEngine:
    """Enhanced debate engine inspired by BettaFish's forum mechanism.
    
    Features:
    - Multi-round debates with iterative refinement
    - Confidence scoring based on agreement levels
    - Consensus building through opinion synthesis
    - Debate history for audit trail
    """
    
    def __init__(self, agents: list[Agent], max_rounds: int = 3):
        self._agents = {agent.role: agent for agent in agents}
        self._debates: list[DebateRound] = []
        self._max_rounds = max_rounds
    
    def run_debate(
        self,
        topic: str,
        proposal: dict[str, Any],
        proposer_role: AgentRole,
        context: SiteContext,
        participants: Optional[list[AgentRole]] = None,
    ) -> DebateRound:
        """Run a multi-round debate on a topic.
        
        Args:
            topic: The debate topic
            proposal: The initial proposal to debate
            proposer_role: Who made the proposal
            context: Shared context
            participants: Who participates (default: all agents except proposer)
        
        Returns:
            DebateRound with final resolution and consensus score
        """
        if participants is None:
            participants = [r for r in AgentRole if r != proposer_role and r != AgentRole.MODERATOR]
        
        all_opinions: list[DebateOpinion] = []
        current_consensus = 0.0
        
        for round_num in range(self._max_rounds):
            round_opinions = []
            
            for role in participants:
                agent = self._agents.get(role)
                if not agent:
                    continue
                
                opinion = agent.offer_opinion(
                    topic=topic,
                    proposal=proposal,
                    context=context,
                    previous_opinions=all_opinions,
                )
                round_opinions.append(opinion)
            
            all_opinions.extend(round_opinions)
            
            # Check if consensus reached
            current_consensus = self._calculate_consensus(all_opinions)
            if current_consensus >= 0.8:
                break
        
        # Synthesize final resolution
        resolution = self._synthesize_resolution(proposal, all_opinions)
        final_confidence = self._calculate_final_confidence(all_opinions)
        
        debate_round = DebateRound(
            topic=topic,
            proposer=proposer_role,
            proposal=proposal,
            opinions=all_opinions,
            resolution=resolution,
            consensus_score=current_consensus,
            rounds_count=min(round_num + 1, self._max_rounds),
            final_confidence=final_confidence,
        )
        
        self._debates.append(debate_round)
        context.debates.append(debate_round)
        context.debate_history.append({
            "topic": topic,
            "rounds": debate_round.rounds_count,
            "consensus": current_consensus,
            "confidence": final_confidence,
        })
        
        return debate_round
    
    def run_pairwise_debate(
        self,
        topic: str,
        proposer_role: AgentRole,
        challenger_role: AgentRole,
        context: SiteContext,
        proposer_output: Optional[AgentOutput] = None,
    ) -> DebateRound:
        """Run a pairwise debate between two agents (BettaFish style)."""
        proposer = self._agents.get(proposer_role)
        challenger = self._agents.get(challenger_role)
        
        if not proposer or not challenger:
            return DebateRound(topic=topic, proposer=proposer_role)
        
        # Get proposal
        if proposer_output:
            proposal = proposer_output.content
        else:
            output = proposer.analyze(context)
            proposal = output.content
        
        # Run multi-round debate
        return self.run_debate(
            topic=topic,
            proposal=proposal,
            proposer_role=proposer_role,
            context=context,
            participants=[challenger_role],
        )
    
    def weighted_consensus(
        self,
        opinions: list[DebateOpinion],
        role_weights: Optional[dict[AgentRole, float]] = None,
    ) -> float:
        """Weighted consensus: domain-expert roles carry more influence.

        Default weights give extra authority to POLICY_GUARD (hard gate)
        and STRATEGIST (ROI decisions).  Pass role_weights to override.
        """
        if not opinions:
            return 0.0

        _default: dict[str, float] = {
            "sniffer": 1.0,
            "query": 1.2,
            "strategist": 1.5,
            "ux_reviewer": 1.0,
            "policy_guard": 2.0,
            "aio_optimizer": 1.3,
        }
        wmap = (
            {r.value: w for r, w in role_weights.items()}
            if role_weights else _default
        )

        total_w = weighted_score = 0.0
        for op in opinions:
            wt = wmap.get(op.agent_role.value, 1.0)
            total_w += wt
            if op.stance == DebateStance.AGREE:
                raw = 1.0
            elif op.stance == DebateStance.PARTIALLY_AGREE:
                raw = 0.5
            else:
                raw = 0.0
            weighted_score += wt * raw * op.confidence

        return weighted_score / total_w if total_w else 0.0

    def _calculate_consensus(self, opinions: list[DebateOpinion]) -> float:
        """Calculate consensus score from opinions."""
        if not opinions:
            return 0.0
        
        agree_count = sum(1 for o in opinions if o.stance == DebateStance.AGREE)
        partial_count = sum(1 for o in opinions if o.stance == DebateStance.PARTIALLY_AGREE)
        disagree_count = sum(1 for o in opinions if o.stance == DebateStance.DISAGREE)
        
        total = len(opinions)
        if total == 0:
            return 0.0
        
        # Weighted score: agree=1.0, partial=0.5, disagree=0.0
        score = (agree_count * 1.0 + partial_count * 0.5) / total
        return score
    
    def _calculate_final_confidence(self, opinions: list[DebateOpinion]) -> float:
        """Calculate final confidence based on opinion strength and consensus."""
        if not opinions:
            return 0.0
        
        avg_confidence = sum(o.confidence for o in opinions) / len(opinions)
        consensus = self._calculate_consensus(opinions)
        
        # Confidence is average of individual confidence and consensus
        return (avg_confidence + consensus) / 2
    
    def _synthesize_resolution(
        self,
        proposal: dict[str, Any],
        opinions: list[DebateOpinion],
    ) -> dict[str, Any]:
        """Synthesize a final resolution from proposal and opinions."""
        if not opinions:
            return proposal
        
        # Collect all conditions and evidence
        all_conditions = []
        all_evidence = []
        
        for opinion in opinions:
            all_conditions.extend(opinion.conditions)
            all_evidence.extend(opinion.evidence)
        
        # Build resolution
        resolution = {
            **proposal,
            "_debate_resolution": True,
            "_opinions_count": len(opinions),
            "_consensus_score": self._calculate_consensus(opinions),
            "_conditions": list(set(all_conditions)),
            "_evidence": list(set(all_evidence)),
        }
        
        # If majority disagrees, add warning
        disagree_count = sum(1 for o in opinions if o.stance == DebateStance.DISAGREE)
        if disagree_count > len(opinions) / 2:
            resolution["_debate_warning"] = "Majority of agents disagree with proposal"
            resolution["_confidence_reduced"] = True
        
        return resolution
    
    def get_all_debates(self) -> list[DebateRound]:
        """Get all debate rounds."""
        return list(self._debates)
    


    def run_final_arbitration(
        self,
        debate_round: "DebateRound",
        context: "SiteContext",
        strategist_role: "AgentRole" = None,
        policy_guard_role: "AgentRole" = None,
    ) -> "DebateRound":
        """AGT-005 — 第3轮辩论：策略方 vs 合规终裁方。

        当前两轮辩论结束后 consensus_score < 0.6，或 resolution 包含 policy 风险时，
        触发第3轮。Strategist 代表 ROI/效益方，PolicyGuard 代表合规硬门槛方，
        最终以加权共识（policy_guard weight=2.0）决定是否放行。

        Args:
            debate_round: 前两轮的 DebateRound 结果（proposal / resolution 作为输入）
            context:      共享 SiteContext
            strategist_role:   策略方 AgentRole（默认 STRATEGIST）
            policy_guard_role: 合规方 AgentRole（默认 POLICY_GUARD）

        Returns:
            新的 DebateRound，resolution 含 arbitration_verdict 字段
        """
        from dataclasses import dataclass

        s_role = strategist_role  or AgentRole.STRATEGIST
        p_role = policy_guard_role or AgentRole.POLICY_GUARD

        strategist   = self._agents.get(s_role)
        policy_guard = self._agents.get(p_role)

        # ── 构造第3轮输入提案（从前两轮决议继承）─────────────────────────────
        arbitration_proposal: dict = {
            **debate_round.resolution,
            "_arbitration_round": True,
            "_prior_consensus":   debate_round.consensus_score,
            "_prior_confidence":  debate_round.final_confidence,
            "_arbitration_topic": (
                f"Should we proceed with: {debate_round.topic}? "
                f"(Prior consensus: {debate_round.consensus_score:.2f})"
            ),
        }

        opinions: list[DebateOpinion] = []

        # ── 策略方发言 ────────────────────────────────────────────────────────
        if strategist:
            try:
                strat_opinion = strategist.offer_opinion(
                    topic=f"[Round-3 Arbitration] {debate_round.topic}",
                    proposal=arbitration_proposal,
                    context=context,
                    previous_opinions=list(debate_round.opinions),
                )
                # 确保是策略方
                strat_opinion.agent_role = s_role
                opinions.append(strat_opinion)
            except Exception as exc:  # noqa: BLE001
                opinions.append(DebateOpinion(
                    agent_role=s_role,
                    stance=DebateStance.PARTIALLY_AGREE,
                    reasoning=f"Strategist error: {exc}",
                    confidence=0.5,
                ))

        # ── 合规终裁方发言（PolicyGuard 作为最终仲裁者）──────────────────────
        if policy_guard:
            try:
                pg_opinion = policy_guard.offer_opinion(
                    topic=f"[Round-3 Compliance Gate] {debate_round.topic}",
                    proposal=arbitration_proposal,
                    context=context,
                    previous_opinions=list(debate_round.opinions) + opinions,
                )
                pg_opinion.agent_role = p_role
                opinions.append(pg_opinion)
            except Exception as exc:  # noqa: BLE001
                opinions.append(DebateOpinion(
                    agent_role=p_role,
                    stance=DebateStance.ABSTAIN,
                    reasoning=f"PolicyGuard error: {exc}",
                    confidence=0.3,
                ))

        # ── 加权终裁共识（PolicyGuard weight=2.0，是策略方的2倍）─────────────
        weighted_score = self.weighted_consensus(
            opinions,
            role_weights={
                s_role: 1.0,
                p_role: 2.0,   # 合规方拥有否决权权重
            },
        )

        # ── 构建终裁决议 ──────────────────────────────────────────────────────
        policy_opinions = [o for o in opinions if o.agent_role == p_role]
        policy_blocks = any(
            o.stance == DebateStance.DISAGREE for o in policy_opinions
        )

        if policy_blocks:
            # PolicyGuard 明确否决 → 阻断执行
            verdict = "BLOCKED"
            verdict_reason = next(
                (o.reasoning for o in policy_opinions if o.stance == DebateStance.DISAGREE),
                "Policy compliance check failed",
            )
        elif weighted_score >= 0.6:
            verdict = "APPROVED"
            verdict_reason = (
                f"Weighted arbitration passed (score={weighted_score:.2f}). "
                "Proceed with recommended conditions."
            )
        else:
            verdict = "CONDITIONAL"
            verdict_reason = (
                f"Arbitration inconclusive (score={weighted_score:.2f}). "
                "Proceed only after manual review."
            )

        all_conditions = list({
            c
            for o in opinions
            for c in o.conditions
        })

        arbitration_resolution = {
            **arbitration_proposal,
            "arbitration_verdict":       verdict,
            "arbitration_reason":        verdict_reason,
            "arbitration_weighted_score": weighted_score,
            "arbitration_conditions":    all_conditions,
            "arbitration_policy_blocked": policy_blocks,
            "_debate_resolution":        True,
        }

        arb_round = DebateRound(
            topic=f"[Round-3 Arbitration] {debate_round.topic}",
            proposer=s_role,
            proposal=arbitration_proposal,
            opinions=opinions,
            resolution=arbitration_resolution,
            consensus_score=weighted_score,
            rounds_count=3,
            final_confidence=self._calculate_final_confidence(opinions),
        )

        self._debates.append(arb_round)
        context.debates.append(arb_round)
        context.debate_history.append({
            "topic":     arb_round.topic,
            "rounds":    3,
            "consensus": weighted_score,
            "confidence": arb_round.final_confidence,
            "verdict":   verdict,
        })

        return arb_round

    def get_debate_summary(self) -> dict[str, Any]:
        """Get summary of all debates."""
        return {
            "total_debates": len(self._debates),
            "avg_consensus": sum(d.consensus_score for d in self._debates) / max(len(self._debates), 1),
            "avg_confidence": sum(d.final_confidence for d in self._debates) / max(len(self._debates), 1),
            "topics": [d.topic for d in self._debates],
        }
