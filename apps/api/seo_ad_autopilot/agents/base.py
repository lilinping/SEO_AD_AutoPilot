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
    
    def get_debate_summary(self) -> dict[str, Any]:
        """Get summary of all debates."""
        return {
            "total_debates": len(self._debates),
            "avg_consensus": sum(d.consensus_score for d in self._debates) / max(len(self._debates), 1),
            "avg_confidence": sum(d.final_confidence for d in self._debates) / max(len(self._debates), 1),
            "topics": [d.topic for d in self._debates],
        }
