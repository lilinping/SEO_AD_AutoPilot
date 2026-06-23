"""Strategist Agent - Strategy synthesis and prioritization."""

from __future__ import annotations

from typing import Any, Optional

from .base import Agent, AgentOutput, AgentRole, SiteContext


class StrategistAgent(Agent):
    """Strategist Agent - synthesizes findings from other agents into actionable strategies.
    
    This agent is responsible for:
    - Combining insights from Sniffer, Query, and GEO agents
    - Prioritizing opportunities by impact and effort
    - Creating execution plans
    - Defining success metrics
    - Risk assessment
    """
    
    def __init__(self):
        super().__init__()
        self._role = AgentRole.STRATEGIST
    
    def analyze(self, context: SiteContext) -> AgentOutput:
        """Synthesize strategies from all agent outputs."""
        # Collect all opportunities
        all_opportunities = context.opportunities or []
        
        # Prioritize opportunities
        prioritized = self._prioritize_opportunities(all_opportunities, context)
        
        # Create execution plan
        execution_plan = self._create_execution_plan(prioritized)
        
        # Define success metrics
        success_metrics = self._define_success_metrics(prioritized)
        
        # Risk assessment
        risk_assessment = self._assess_risks(prioritized, context)
        
        content = {
            "strategies": prioritized,
            "execution_plan": execution_plan,
            "success_metrics": success_metrics,
            "risk_assessment": risk_assessment,
            "estimated_timeline": self._estimate_timeline(prioritized),
            "resource_requirements": self._estimate_resources(prioritized),
        }
        
        return self._create_output(
            content=content,
            confidence=0.75,
            risk_score=risk_assessment.get("overall_risk", 0.3),
            reasoning=f"Synthesized {len(prioritized)} strategies from {len(all_opportunities)} opportunities",
        )
    
    def challenge(self, other_output: AgentOutput, context: SiteContext) -> Optional[dict[str, Any]]:
        """Challenge if strategies don't align with site capabilities."""
        if other_output.agent_role == AgentRole.SNIFFER:
            site_profile = other_output.content
            maturity_score = site_profile.get("maturity_score", 50)
            
            # Check if strategies match site maturity
            strategies = self._prioritize_opportunities(context.opportunities or [], context)
            advanced_strategies = [
                s for s in strategies
                if s.get("complexity", "low") == "high"
            ]
            
            if advanced_strategies and maturity_score < 60:
                return {
                    "type": "maturity_mismatch",
                    "reason": "Advanced strategies require higher site maturity",
                    "suggestion": "Start with simpler strategies first",
                    "advanced_count": len(advanced_strategies),
                    "maturity_score": maturity_score,
                }
        
        return None
    
    def _prioritize_opportunities(
        self,
        opportunities: list[dict[str, Any]],
        context: SiteContext,
    ) -> list[dict[str, Any]]:
        """Prioritize opportunities by impact and effort."""
        # Score each opportunity
        scored = []
        for opp in opportunities:
            impact = self._estimate_impact(opp, context)
            effort = self._estimate_effort(opp, context)
            score = impact / max(effort, 1)
            
            scored.append({
                **opp,
                "impact_score": impact,
                "effort_score": effort,
                "priority_score": score,
            })
        
        # Sort by priority score
        return sorted(scored, key=lambda x: x["priority_score"], reverse=True)
    
    def _estimate_impact(self, opportunity: dict[str, Any], context: SiteContext) -> float:
        """Estimate impact of an opportunity (0-100)."""
        base_impact = 50.0
        
        # Adjust based on opportunity type
        opp_type = opportunity.get("type", "")
        if "schema" in opp_type:
            base_impact += 20
        if "citation" in opp_type:
            base_impact += 25
        if "entity" in opp_type:
            base_impact += 15
        
        # Adjust based on engine
        engine = opportunity.get("engine", "")
        if "chatgpt" in engine or "perplexity" in engine:
            base_impact += 10  # GEO is high-value
        
        return min(100.0, base_impact)
    
    def _estimate_effort(self, opportunity: dict[str, Any], context: SiteContext) -> float:
        """Estimate effort required (0-100)."""
        base_effort = 30.0
        
        # Adjust based on opportunity type
        opp_type = opportunity.get("type", "")
        if "schema" in opp_type:
            base_effort += 20
        if "content" in opp_type:
            base_effort += 30
        if "technical" in opp_type:
            base_effort += 25
        
        return min(100.0, base_effort)
    
    def _create_execution_plan(self, strategies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Create an execution plan."""
        plan = []
        
        for i, strategy in enumerate(strategies[:10]):  # Top 10 strategies
            plan.append({
                "step": i + 1,
                "strategy": strategy.get("title", "Unknown"),
                "type": strategy.get("type", "unknown"),
                "priority": strategy.get("priority", "medium"),
                "estimated_days": self._estimate_days(strategy),
                "dependencies": [],
            })
        
        return plan
    
    def _define_success_metrics(self, strategies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Define success metrics."""
        metrics = []
        
        # SEO metrics
        metrics.append({
            "name": "Organic Traffic",
            "target": "+20%",
            "timeline": "3 months",
            "measurement": "Google Analytics / Search Console",
        })
        
        # GEO metrics
        metrics.append({
            "name": "AI Search Visibility",
            "target": "Appear in 50% of relevant AI queries",
            "timeline": "2 months",
            "measurement": "Manual testing with ChatGPT/Perplexity",
        })
        
        # Technical metrics
        metrics.append({
            "name": "Core Web Vitals",
            "target": "All green",
            "timeline": "1 month",
            "measurement": "PageSpeed Insights",
        })
        
        return metrics
    
    def _assess_risks(
        self,
        strategies: list[dict[str, Any]],
        context: SiteContext,
    ) -> dict[str, Any]:
        """Assess risks of the strategies."""
        risks = []
        overall_risk = 0.2
        
        # Check for high-risk strategies
        high_risk = [s for s in strategies if s.get("risk_level") == "high"]
        if high_risk:
            risks.append({
                "type": "high_risk_strategies",
                "count": len(high_risk),
                "mitigation": "Require human approval for high-risk changes",
            })
            overall_risk += 0.2
        
        # Check for technical risks
        technical = [s for s in strategies if "technical" in s.get("type", "")]
        if technical:
            risks.append({
                "type": "technical_complexity",
                "count": len(technical),
                "mitigation": "Test in staging environment first",
            })
            overall_risk += 0.1
        
        return {
            "risks": risks,
            "overall_risk": min(1.0, overall_risk),
        }
    
    def _estimate_timeline(self, strategies: list[dict[str, Any]]) -> str:
        """Estimate overall timeline."""
        total_days = sum(self._estimate_days(s) for s in strategies[:5])
        
        if total_days <= 7:
            return "1 week"
        elif total_days <= 30:
            return "1 month"
        elif total_days <= 90:
            return "3 months"
        else:
            return "6+ months"
    
    def _estimate_days(self, strategy: dict[str, Any]) -> int:
        """Estimate days for a single strategy."""
        effort = strategy.get("effort_score", 50)
        
        if effort < 30:
            return 1
        elif effort < 60:
            return 3
        elif effort < 80:
            return 7
        else:
            return 14
    
    def _estimate_resources(self, strategies: list[dict[str, Any]]) -> dict[str, Any]:
        """Estimate resource requirements."""
        return {
            "development_hours": sum(self._estimate_days(s) * 8 for s in strategies[:5]),
            "content_hours": len([s for s in strategies if "content" in s.get("type", "")]) * 4,
            "seo_hours": len([s for s in strategies if "schema" in s.get("type", "")]) * 2,
        }
