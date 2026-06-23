"""Coordinator Agent - Workflow orchestration and skill execution."""

from __future__ import annotations

from typing import Any, Optional

from .base import Agent, AgentOutput, AgentRole, DebateRound, SiteContext


class CoordinatorAgent(Agent):
    """Coordinator Agent - orchestrates the entire workflow.
    
    This agent is responsible for:
    - Coordinating all other agents
    - Managing the debate process
    - Selecting appropriate skills
    - Creating execution sequences
    - Managing approval workflows
    """
    
    def __init__(self):
        super().__init__()
        self._role = AgentRole.COORDINATOR
    
    def analyze(self, context: SiteContext) -> AgentOutput:
        """Coordinate the entire analysis and execution workflow."""
        # Collect all agent outputs
        all_outputs = self._collect_agent_outputs(context)
        
        # Run debates if needed
        debates = self._run_debates(context)
        
        # Select skills to execute
        skills = self._select_skills(context, all_outputs)
        
        # Create execution sequence
        execution_sequence = self._create_execution_sequence(skills, context)
        
        # Determine approval requirements
        approval_requirements = self._determine_approval_requirements(skills)
        
        # Create monitoring plan
        monitoring_plan = self._create_monitoring_plan(skills, context)
        
        content = {
            "workflow_summary": self._create_workflow_summary(all_outputs, debates),
            "debates": [
                {
                    "topic": d.topic,
                    "proposer": d.proposer.value,
                    "challenger": d.challenger.value,
                    "resolution_summary": str(d.resolution)[:200],
                }
                for d in debates
            ],
            "selected_skills": skills,
            "execution_sequence": execution_sequence,
            "approval_requirements": approval_requirements,
            "monitoring_plan": monitoring_plan,
            "estimated_duration": self._estimate_duration(skills),
        }
        
        return self._create_output(
            content=content,
            confidence=0.85,
            risk_score=0.15,
            reasoning=f"Coordinated workflow with {len(skills)} skills and {len(debates)} debates",
        )
    
    def challenge(self, other_output: AgentOutput, context: SiteContext) -> Optional[dict[str, Any]]:
        """Challenge if workflow is not optimal."""
        # Coordinator doesn't challenge others, it synthesizes
        return None
    
    def _collect_agent_outputs(self, context: SiteContext) -> dict[str, Any]:
        """Collect outputs from all agents."""
        return {
            "site_profile": context.site_profile,
            "opportunities": context.opportunities,
            "geo_analysis": context.geo_analysis,
            "ad_analysis": context.ad_analysis,
        }
    
    def _run_debates(self, context: SiteContext) -> list[DebateRound]:
        """Run debates between agents."""
        # Check if debates are needed
        debates = context.debates or []
        
        # Run additional debates if there are conflicts
        if len(debates) < 2:
            # Run a debate between Query and GEO agents
            # This is a placeholder - actual implementation would use DebateEngine
            pass
        
        return debates
    
    def _select_skills(
        self,
        context: SiteContext,
        all_outputs: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Select appropriate skills based on analysis."""
        skills = []
        
        # Always include site analysis
        skills.append({
            "skill": "SiteCrawler",
            "params": {"url": context.url},
            "priority": "high",
            "requires_approval": False,
        })
        
        # Add SEO skills based on opportunities
        opportunities = all_outputs.get("opportunities", [])
        for opp in opportunities[:5]:  # Top 5 opportunities
            skill = self._map_opportunity_to_skill(opp)
            if skill:
                skills.append(skill)
        
        # Add GEO skills
        if all_outputs.get("geo_analysis"):
            skills.append({
                "skill": "GEOOptimizer",
                "params": {"url": context.url},
                "priority": "high",
                "requires_approval": False,
            })
        
        # Add ad skills if needed
        if all_outputs.get("ad_analysis"):
            skills.append({
                "skill": "AdSlotAuditor",
                "params": {"url": context.url},
                "priority": "medium",
                "requires_approval": False,
            })
        
        return skills
    
    def _map_opportunity_to_skill(self, opportunity: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Map an opportunity to a skill."""
        opp_type = opportunity.get("type", "")
        
        if "schema" in opp_type:
            return {
                "skill": "SchemaBuilder",
                "params": {"type": opp_type},
                "priority": opportunity.get("priority", "medium"),
                "requires_approval": True,
            }
        elif "content" in opp_type:
            return {
                "skill": "ContentGenerator",
                "params": {"type": opp_type},
                "priority": opportunity.get("priority", "medium"),
                "requires_approval": True,
            }
        elif "technical" in opp_type:
            return {
                "skill": "TechnicalSeoPatcher",
                "params": {"type": opp_type},
                "priority": opportunity.get("priority", "medium"),
                "requires_approval": True,
            }
        
        return None
    
    def _create_execution_sequence(
        self,
        skills: list[dict[str, Any]],
        context: SiteContext,
    ) -> list[dict[str, Any]]:
        """Create an execution sequence."""
        # Sort by priority and dependencies
        sequence = []
        
        # Phase 1: Analysis (no approval needed)
        analysis_skills = [s for s in skills if not s.get("requires_approval", False)]
        for skill in analysis_skills:
            sequence.append({
                "phase": 1,
                "step": len(sequence) + 1,
                "skill": skill["skill"],
                "params": skill["params"],
                "parallel": True,
            })
        
        # Phase 2: Execution (approval needed)
        execution_skills = [s for s in skills if s.get("requires_approval", False)]
        for skill in execution_skills:
            sequence.append({
                "phase": 2,
                "step": len(sequence) + 1,
                "skill": skill["skill"],
                "params": skill["params"],
                "parallel": False,
            })
        
        return sequence
    
    def _determine_approval_requirements(self, skills: list[dict[str, Any]]) -> dict[str, Any]:
        """Determine approval requirements."""
        requires_approval = [s for s in skills if s.get("requires_approval", False)]
        
        return {
            "total_skills": len(skills),
            "requires_approval": len(requires_approval),
            "auto_approved": len(skills) - len(requires_approval),
            "approval_threshold": "medium",
        }
    
    def _create_monitoring_plan(
        self,
        skills: list[dict[str, Any]],
        context: SiteContext,
    ) -> dict[str, Any]:
        """Create a monitoring plan."""
        return {
            "metrics_to_track": [
                "organic_traffic",
                "search_visibility",
                "core_web_vitals",
                "ai_search_mentions",
            ],
            "monitoring_frequency": "daily",
            "alert_thresholds": {
                "traffic_drop": 0.1,
                "performance_degradation": 0.2,
            },
        }
    
    def _estimate_duration(self, skills: list[dict[str, Any]]) -> str:
        """Estimate total duration."""
        # Simple estimation
        return f"{len(skills) * 2} hours"
    
    def _create_workflow_summary(
        self,
        all_outputs: dict[str, Any],
        debates: list[DebateRound],
    ) -> str:
        """Create a workflow summary."""
        return f"Analyzed site with {len(debates)} debates and generated optimization strategy"
