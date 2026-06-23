"""Policy Guard Agent - SEO/广告合规检查.

Inspired by BettaFish's multi-agent collaboration:
- Rules-based compliance checking
- Risk assessment
-阻断项和人工复核项输出
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .base import Agent, AgentOutput, AgentRole, DebateOpinion, DebateStance, SiteContext


class ComplianceLevel(str, Enum):
    """合规级别."""
    PASS = "pass"
    WARNING = "warning"
    BLOCK = "block"
    HUMAN_REVIEW = "human_review"


class RiskCategory(str, Enum):
    """风险类别."""
    SEO_RISK = "seo_risk"
    AD_RISK = "ad_risk"
    CONTENT_RISK = "content_risk"
    SECURITY_RISK = "security_risk"
    UX_RISK = "ux_risk"


@dataclass
class ComplianceIssue:
    """合规问题."""
    category: RiskCategory
    level: ComplianceLevel
    message: str
    details: str = ""
    recommendation: str = ""


@dataclass
class PolicyCheckResult:
    """策略检查结果."""
    overall_level: ComplianceLevel
    issues: list[ComplianceIssue] = field(default_factory=list)
    blocked_items: list[str] = field(default_factory=list)
    warning_items: list[str] = field(default_factory=list)
    human_review_items: list[str] = field(default_factory=list)
    risk_score: float = 0.0


class PolicyGuardAgent(Agent):
    """Policy Guard Agent - 审核站点相关性、内容价值、广告政策、安全与隐私.
    
    This agent checks:
    - SEO compliance (no black-hat techniques)
    - Ad compliance (policy, UX impact)
    - Content quality (relevance, originality)
    - Security risks (script injection, data leakage)
    """
    
    def __init__(self):
        super().__init__()
        self._role = AgentRole.COORDINATOR  # Using coordinator role for now
    
    def analyze(self, context: SiteContext) -> AgentOutput:
        """Perform policy compliance check."""
        issues = []
        
        # Check SEO compliance
        seo_issues = self._check_seo_compliance(context)
        issues.extend(seo_issues)
        
        # Check ad compliance
        ad_issues = self._check_ad_compliance(context)
        issues.extend(ad_issues)
        
        # Check content quality
        content_issues = self._check_content_quality(context)
        issues.extend(content_issues)
        
        # Check security risks
        security_issues = self._check_security_risks(context)
        issues.extend(security_issues)
        
        # Calculate overall result
        result = self._calculate_result(issues)
        
        content = {
            "overall_level": result.overall_level.value,
            "risk_score": result.risk_score,
            "issues": [
                {
                    "category": issue.category.value,
                    "level": issue.level.value,
                    "message": issue.message,
                    "details": issue.details,
                    "recommendation": issue.recommendation,
                }
                for issue in result.issues
            ],
            "blocked_items": result.blocked_items,
            "warning_items": result.warning_items,
            "human_review_items": result.human_review_items,
        }
        
        return self._create_output(
            content=content,
            confidence=0.85,
            risk_score=result.risk_score,
            needs_human_review=result.overall_level == ComplianceLevel.HUMAN_REVIEW,
            reasoning="Policy compliance check completed",
        )
    
    def offer_opinion(
        self,
        topic: str,
        proposal: dict[str, Any],
        context: SiteContext,
        previous_opinions: list = None,
    ) -> DebateOpinion:
        """Offer opinion on policy-related proposals."""
        # Check if proposal has compliance issues
        has_issues = self._has_compliance_issues(proposal)
        
        if has_issues:
            return DebateOpinion(
                agent_role=self._role,
                stance=DebateStance.DISAGREE,
                reasoning="Proposal has compliance issues that need to be addressed",
                evidence=["Compliance check found violations"],
                confidence=0.8,
                conditions=["Fix compliance issues before proceeding"],
            )
        else:
            return DebateOpinion(
                agent_role=self._role,
                stance=DebateStance.AGREE,
                reasoning="Proposal passes compliance checks",
                evidence=["No compliance violations found"],
                confidence=0.85,
            )
    
    def _check_seo_compliance(self, context: SiteContext) -> list[ComplianceIssue]:
        """Check SEO compliance."""
        issues = []
        
        # Check for black-hat techniques
        raw_data = context.raw_data
        content = str(raw_data.get("content", "")).lower()
        
        # Check for keyword stuffing
        if content.count("keyword") > 5:
            issues.append(ComplianceIssue(
                category=RiskCategory.SEO_RISK,
                level=ComplianceLevel.WARNING,
                message="Potential keyword stuffing detected",
                recommendation="Reduce keyword density and focus on natural content",
            ))
        
        # Check for hidden text
        if "display:none" in content or "visibility:hidden" in content:
            issues.append(ComplianceIssue(
                category=RiskCategory.SEO_RISK,
                level=ComplianceLevel.BLOCK,
                message="Hidden text detected - violates search engine guidelines",
                recommendation="Remove hidden text elements",
            ))
        
        return issues
    
    def _check_ad_compliance(self, context: SiteContext) -> list[ComplianceIssue]:
        """Check ad compliance."""
        issues = []
        
        # Check for ad density
        raw_data = context.raw_data
        ad_count = raw_data.get("ad_count", 0)
        content_length = len(str(raw_data.get("content", "")))
        
        if content_length > 0 and ad_count / (content_length / 1000) > 5:
            issues.append(ComplianceIssue(
                category=RiskCategory.AD_RISK,
                level=ComplianceLevel.WARNING,
                message="High ad density detected",
                recommendation="Reduce ad density to improve user experience",
            ))
        
        return issues
    
    def _check_content_quality(self, context: SiteContext) -> list[ComplianceIssue]:
        """Check content quality."""
        issues = []
        
        # Check for thin content
        raw_data = context.raw_data
        content_length = len(str(raw_data.get("content", "")))
        
        if content_length < 300:
            issues.append(ComplianceIssue(
                category=RiskCategory.CONTENT_RISK,
                level=ComplianceLevel.WARNING,
                message="Thin content detected",
                recommendation="Add more valuable content to the page",
            ))
        
        return issues
    
    def _check_security_risks(self, context: SiteContext) -> list[ComplianceIssue]:
        """Check security risks."""
        issues = []
        
        # Check for external scripts
        raw_data = context.raw_data
        scripts = raw_data.get("scripts", [])
        
        external_scripts = [s for s in scripts if not s.startswith("/")]
        if len(external_scripts) > 3:
            issues.append(ComplianceIssue(
                category=RiskCategory.SECURITY_RISK,
                level=ComplianceLevel.WARNING,
                message="Multiple external scripts detected",
                recommendation="Review and minimize external script dependencies",
            ))
        
        return issues
    
    def _has_compliance_issues(self, proposal: dict[str, Any]) -> bool:
        """Check if proposal has compliance issues."""
        # Simple check for obvious issues
        proposal_str = str(proposal).lower()
        
        black_hat_terms = ["hidden", "cloaking", "doorway", "spam", "fake"]
        return any(term in proposal_str for term in black_hat_terms)
    
    def _calculate_result(self, issues: list[ComplianceIssue]) -> PolicyCheckResult:
        """Calculate overall compliance result."""
        blocked = [i.message for i in issues if i.level == ComplianceLevel.BLOCK]
        warnings = [i.message for i in issues if i.level == ComplianceLevel.WARNING]
        human_review = [i.message for i in issues if i.level == ComplianceLevel.HUMAN_REVIEW]
        
        # Determine overall level
        if blocked:
            overall_level = ComplianceLevel.BLOCK
        elif human_review:
            overall_level = ComplianceLevel.HUMAN_REVIEW
        elif warnings:
            overall_level = ComplianceLevel.WARNING
        else:
            overall_level = ComplianceLevel.PASS
        
        # Calculate risk score
        risk_score = 0.0
        for issue in issues:
            if issue.level == ComplianceLevel.BLOCK:
                risk_score += 30
            elif issue.level == ComplianceLevel.WARNING:
                risk_score += 10
            elif issue.level == ComplianceLevel.HUMAN_REVIEW:
                risk_score += 20
        
        risk_score = min(risk_score, 100)
        
        return PolicyCheckResult(
            overall_level=overall_level,
            issues=issues,
            blocked_items=blocked,
            warning_items=warnings,
            human_review_items=human_review,
            risk_score=risk_score,
        )
