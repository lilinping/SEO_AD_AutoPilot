"""UX Reviewer Agent - Layout and user experience review."""

from __future__ import annotations

from typing import Any, Optional

from .base import Agent, AgentOutput, AgentRole, SiteContext


class UXReviewerAgent(Agent):
    """UX Reviewer Agent - reviews proposed changes for UX impact.
    
    This agent is responsible for:
    - Reviewing proposed content modules for UX impact
    - Checking style consistency
    - Identifying exclusion zones
    - Assessing conversion path interference
    - Validating mobile experience
    """
    
    def __init__(self):
        super().__init__()
        self._role = AgentRole.UX_REVIEWER
    
    def analyze(self, context: SiteContext) -> AgentOutput:
        """Review UX impact of proposed changes."""
        raw_data = context.raw_data
        strategies = context.opportunities or []
        
        # Analyze current UX
        current_ux = self._analyze_current_ux(raw_data)
        
        # Review proposed changes
        ux_review = self._review_proposed_changes(strategies, raw_data)
        
        # Identify exclusion zones
        exclusion_zones = self._identify_exclusion_zones(raw_data)
        
        # Assess conversion impact
        conversion_impact = self._assess_conversion_impact(strategies, raw_data)
        
        # Check mobile experience
        mobile_assessment = self._assess_mobile_experience(raw_data)
        
        content = {
            "current_ux_score": current_ux.get("score", 50),
            "ux_review": ux_review,
            "exclusion_zones": exclusion_zones,
            "conversion_impact": conversion_impact,
            "mobile_assessment": mobile_assessment,
            "recommendations": self._generate_ux_recommendations(
                current_ux,
                ux_review,
                exclusion_zones,
                conversion_impact,
                mobile_assessment,
            ),
        }
        
        return self._create_output(
            content=content,
            confidence=0.8,
            risk_score=ux_review.get("risk_score", 0.2),
            reasoning="Reviewed UX impact of proposed changes",
        )
    
    def challenge(self, other_output: AgentOutput, context: SiteContext) -> Optional[dict[str, Any]]:
        """Challenge if changes would harm UX."""
        if other_output.agent_role == AgentRole.STRATEGIST:
            strategies = other_output.content.get("strategies", [])
            
            # Check for high-risk changes
            high_risk = [
                s for s in strategies
                if s.get("ux_risk", "low") == "high"
            ]
            
            if high_risk:
                return {
                    "type": "ux_risk_detected",
                    "reason": f"{len(high_risk)} strategies have high UX risk",
                    "suggestion": "Review and mitigate UX risks before proceeding",
                    "high_risk_count": len(high_risk),
                }
        
        return None
    
    def _analyze_current_ux(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze current UX of the site."""
        score = 50.0
        
        # Check for navigation
        if raw_data.get("has_navigation"):
            score += 10
        
        # Check for mobile responsiveness
        if raw_data.get("is_mobile_friendly"):
            score += 15
        
        # Check for accessibility
        if raw_data.get("has_aria_labels"):
            score += 10
        
        return {
            "score": min(100.0, score),
            "strengths": [],
            "weaknesses": [],
        }
    
    def _review_proposed_changes(
        self,
        strategies: list[dict[str, Any]],
        raw_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Review proposed changes for UX impact."""
        risk_score = 0.1
        issues = []
        
        for strategy in strategies:
            # Check for content injection risks
            if "content" in strategy.get("type", ""):
                risk_score += 0.1
                issues.append({
                    "strategy": strategy.get("title", "Unknown"),
                    "issue": "Content injection may affect layout",
                    "severity": "medium",
                })
            
            # Check for ad placement risks
            if "ad" in strategy.get("type", ""):
                risk_score += 0.15
                issues.append({
                    "strategy": strategy.get("title", "Unknown"),
                    "issue": "Ad placement may interfere with content",
                    "severity": "high",
                })
        
        return {
            "risk_score": min(1.0, risk_score),
            "issues": issues,
            "total_issues": len(issues),
        }
    
    def _identify_exclusion_zones(self, raw_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Identify exclusion zones where changes should not be made."""
        zones = []
        
        # Standard exclusion zones
        zones.append({
            "selector": "header, nav, .navigation",
            "reason": "Navigation should not be modified",
            "priority": "high",
        })
        
        zones.append({
            "selector": ".cta, .buy-button, .checkout",
            "reason": "Conversion elements should not be modified",
            "priority": "high",
        })
        
        zones.append({
            "selector": "footer",
            "reason": "Footer should not be modified",
            "priority": "medium",
        })
        
        # Check for custom exclusion zones
        if raw_data.get("custom_exclusion_zones"):
            zones.extend(raw_data["custom_exclusion_zones"])
        
        return zones
    
    def _assess_conversion_impact(
        self,
        strategies: list[dict[str, Any]],
        raw_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Assess impact on conversion paths."""
        impact_score = 0.0
        risks = []
        
        for strategy in strategies:
            # Check if strategy affects conversion elements
            if strategy.get("affects_cta", False):
                impact_score += 0.2
                risks.append({
                    "strategy": strategy.get("title", "Unknown"),
                    "risk": "May affect CTA visibility",
                })
        
        return {
            "impact_score": min(1.0, impact_score),
            "risks": risks,
            "recommendation": "A/B test changes before full rollout" if risks else "No significant conversion risks",
        }
    
    def _assess_mobile_experience(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Assess mobile experience."""
        score = 50.0
        
        if raw_data.get("is_mobile_friendly"):
            score += 20
        
        if raw_data.get("has_viewport_meta"):
            score += 10
        
        return {
            "score": min(100.0, score),
            "issues": [],
            "recommendations": [],
        }
    
    def _generate_ux_recommendations(
        self,
        current_ux: dict[str, Any],
        ux_review: dict[str, Any],
        exclusion_zones: list[dict[str, Any]],
        conversion_impact: dict[str, Any],
        mobile_assessment: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate UX recommendations."""
        recommendations = []
        
        if ux_review.get("risk_score", 0) > 0.3:
            recommendations.append({
                "type": "risk_mitigation",
                "priority": "high",
                "title": "Mitigate UX Risks",
                "description": "Review and address identified UX risks",
            })
        
        if conversion_impact.get("impact_score", 0) > 0.2:
            recommendations.append({
                "type": "conversion_protection",
                "priority": "high",
                "title": "Protect Conversion Paths",
                "description": "Ensure changes don't interfere with conversion elements",
            })
        
        if mobile_assessment.get("score", 50) < 70:
            recommendations.append({
                "type": "mobile_optimization",
                "priority": "medium",
                "title": "Improve Mobile Experience",
                "description": "Optimize for mobile devices",
            })
        
        return recommendations
