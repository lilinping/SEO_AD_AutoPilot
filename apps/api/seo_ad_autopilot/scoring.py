"""ScoringEngine — Unified scoring system per Architecture §6.2.

Implements the 5 required scores:
1. Relevant Score   — content relevance to core business
2. Value Score      — real user value (not just trend-chasing)
3. UX Score         — visual consistency and conversion path safety
4. Ad Fit Score     — page suitability for advertising
5. Risk Score       — combined content/tech/performance/compliance risk

Risk thresholds (Architecture §7.2):
- risk_score >= 80:  block auto-deploy, require human review
- risk_score 60-79:  allow preview + PR, default no auto-merge
- risk_score < 60:   auto-deploy allowed if policy permits
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Thresholds from Architecture doc ──────────────────────────────────────────

RISK_BLOCK_AUTO_DEPLOY = 80
RISK_REQUIRE_MANUAL_MERGE = 60
RELEVANCE_MIN_FOR_RECOMMEND = 70
VALUE_MIN_FOR_RECOMMEND = 50
UX_MIN_FOR_AUTO = 65
AD_FIT_MIN_FOR_PROCEED = 40


@dataclass
class ScoreResult:
    """A single score with metadata."""
    score: float  # 0-100
    label: str    # e.g. "relevant_score"
    factors: dict[str, float] = field(default_factory=dict)
    explanation: str = ""
    passed: bool = True
    threshold: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "label": self.label,
            "factors": {k: round(v, 3) for k, v in self.factors.items()},
            "explanation": self.explanation,
            "passed": self.passed,
            "threshold": self.threshold,
        }


@dataclass
class CompositeScore:
    """All 5 scores combined with deployment gate decision."""
    relevant: ScoreResult
    value: ScoreResult
    ux: ScoreResult
    ad_fit: ScoreResult
    risk: ScoreResult
    deployment_gate: str = "allow"  # allow | require_approval | block
    gate_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relevant_score": self.relevant.to_dict(),
            "value_score": self.value.to_dict(),
            "ux_score": self.ux.to_dict(),
            "ad_fit_score": self.ad_fit.to_dict(),
            "risk_score": self.risk.to_dict(),
            "deployment_gate": self.deployment_gate,
            "gate_reasons": self.gate_reasons,
        }


class ScoringEngine:
    """Unified scoring engine for SEO/AD proposals.

    Usage:
        engine = ScoringEngine()
        result = engine.score_proposal(
            site_profile={...},
            opportunity={...},
            page_snapshot={...},
            ad_analysis={...},
        )
        if result.deployment_gate == "block":
            ...
    """

    # ── Public API ────────────────────────────────────────────────────────────

    def score_proposal(
        self,
        site_profile: dict[str, Any] | None = None,
        opportunity: dict[str, Any] | None = None,
        page_snapshot: dict[str, Any] | None = None,
        ad_analysis: dict[str, Any] | None = None,
        ux_review: dict[str, Any] | None = None,
    ) -> CompositeScore:
        """Compute all 5 scores and deployment gate."""
        site_profile = site_profile or {}
        opportunity = opportunity or {}
        page_snapshot = page_snapshot or {}
        ad_analysis = ad_analysis or {}
        ux_review = ux_review or {}

        relevant = self.compute_relevant_score(site_profile, opportunity)
        value = self.compute_value_score(opportunity, site_profile)
        ux = self.compute_ux_score(page_snapshot, ux_review)
        ad_fit = self.compute_ad_fit_score(page_snapshot, ad_analysis, site_profile)
        risk = self.compute_risk_score(opportunity, page_snapshot, ad_analysis, site_profile)

        gate, reasons = self._determine_gate(relevant, value, ux, ad_fit, risk)

        return CompositeScore(
            relevant=relevant,
            value=value,
            ux=ux,
            ad_fit=ad_fit,
            risk=risk,
            deployment_gate=gate,
            gate_reasons=reasons,
        )

    # ── Individual score computations ─────────────────────────────────────────

    def compute_relevant_score(
        self,
        site_profile: dict[str, Any],
        opportunity: dict[str, Any],
    ) -> ScoreResult:
        """Relevant Score — how related is this opportunity to the core business?

        Architecture §6.2: relevance to main business.
        Threshold: < 70 → not allowed for auto-recommend.
        """
        factors: dict[str, float] = {}

        # Business type match
        biz_type = site_profile.get("business_type", "unknown")
        opp_type = opportunity.get("type", "")
        opp_topic = str(opportunity.get("topic", "")).lower()
        site_keywords = [
            str(k).lower()
            for k in site_profile.get("core_keywords", [])
        ]

        # Keyword overlap
        if site_keywords and opp_topic:
            overlap = sum(1 for k in site_keywords if k in opp_topic)
            factors["keyword_overlap"] = overlap / max(len(site_keywords), 1)
        else:
            factors["keyword_overlap"] = 0.3  # neutral when unknown

        # Category match
        opp_category = opportunity.get("category", "")
        if biz_type and opp_category:
            factors["category_match"] = 1.0 if biz_type == opp_category else 0.4
        else:
            factors["category_match"] = 0.5

        # Explicit relevance score from upstream (if provided)
        upstream = opportunity.get("relevance_score")
        if upstream is not None:
            factors["upstream_relevance"] = float(upstream) / 100.0
        else:
            factors["upstream_relevance"] = 0.5

        # Weighted composite
        score = (
            factors["keyword_overlap"] * 0.40
            + factors["category_match"] * 0.30
            + factors["upstream_relevance"] * 0.30
        ) * 100

        return ScoreResult(
            score=score,
            label="relevant_score",
            factors=factors,
            explanation=f"Business type '{biz_type}' vs opportunity '{opp_type}/{opp_topic[:50]}'",
            passed=score >= RELEVANCE_MIN_FOR_RECOMMEND,
            threshold=RELEVANCE_MIN_FOR_RECOMMEND,
        )

    def compute_value_score(
        self,
        opportunity: dict[str, Any],
        site_profile: dict[str, Any],
    ) -> ScoreResult:
        """Value Score — does this provide real user value (not just trend-chasing)?

        Architecture §6.2: user value, not pure trend exploitation.
        Threshold: < 50 → not recommended.
        """
        factors: dict[str, float] = {}

        # Search volume / interest signal
        search_volume = opportunity.get("search_volume", opportunity.get("trend_score", 50))
        factors["search_interest"] = min(1.0, float(search_volume) / 100.0)

        # Content depth potential
        word_count = opportunity.get("estimated_word_count", 500)
        factors["content_depth"] = min(1.0, float(word_count) / 1500.0)

        # Evergreen vs trending
        is_evergreen = opportunity.get("is_evergreen", False)
        factors["evergreen_bonus"] = 0.8 if is_evergreen else 0.5

        # User intent match
        intent = opportunity.get("user_intent", "")
        intent_scores = {
            "informational": 0.7,
            "navigational": 0.5,
            "transactional": 0.8,
            "commercial": 0.75,
        }
        factors["intent_value"] = intent_scores.get(intent, 0.5)

        score = (
            factors["search_interest"] * 0.30
            + factors["content_depth"] * 0.25
            + factors["evergreen_bonus"] * 0.20
            + factors["intent_value"] * 0.25
        ) * 100

        return ScoreResult(
            score=score,
            label="value_score",
            factors=factors,
            explanation=f"Intent={intent}, evergreen={is_evergreen}, volume={search_volume}",
            passed=score >= VALUE_MIN_FOR_RECOMMEND,
            threshold=VALUE_MIN_FOR_RECOMMEND,
        )

    def compute_ux_score(
        self,
        page_snapshot: dict[str, Any],
        ux_review: dict[str, Any],
    ) -> ScoreResult:
        """UX Score — visual consistency and conversion path safety.

        Architecture §6.2: module insertion maintains visual consistency.
        Threshold: < 65 → not safe for auto-deploy.
        """
        factors: dict[str, float] = {}

        # Mobile friendliness
        factors["mobile_friendly"] = 1.0 if page_snapshot.get("is_mobile_friendly") else 0.3

        # Core Web Vitals proxy
        lcp = page_snapshot.get("lcp_ms", 2500)
        factors["lcp_score"] = max(0.0, min(1.0, (4000 - lcp) / 2500))

        # Layout stability
        cls = page_snapshot.get("cls", 0.1)
        factors["cls_score"] = max(0.0, min(1.0, (0.25 - cls) / 0.25))

        # UX reviewer input
        if ux_review:
            reviewer_score = ux_review.get("current_ux_score", 60)
            factors["reviewer_score"] = float(reviewer_score) / 100.0
            # Exclusion zone violations
            zone_violations = ux_review.get("exclusion_zone_violations", 0)
            factors["zone_safety"] = max(0.0, 1.0 - zone_violations * 0.3)
        else:
            factors["reviewer_score"] = 0.6
            factors["zone_safety"] = 0.8

        score = (
            factors["mobile_friendly"] * 0.20
            + factors["lcp_score"] * 0.20
            + factors["cls_score"] * 0.15
            + factors["reviewer_score"] * 0.25
            + factors["zone_safety"] * 0.20
        ) * 100

        return ScoreResult(
            score=score,
            label="ux_score",
            factors=factors,
            explanation=f"LCP={lcp}ms, CLS={cls}, mobile={page_snapshot.get('is_mobile_friendly')}",
            passed=score >= UX_MIN_FOR_AUTO,
            threshold=UX_MIN_FOR_AUTO,
        )

    def compute_ad_fit_score(
        self,
        page_snapshot: dict[str, Any],
        ad_analysis: dict[str, Any],
        site_profile: dict[str, Any],
    ) -> ScoreResult:
        """Ad Fit Score — is this page suitable for advertising?

        Architecture §6.2: position safety, UX impact, viewability, policy risk.
        """
        factors: dict[str, float] = {}

        # From AdSlotAuditor if available
        viable_count = ad_analysis.get("viable_candidates", 0)
        factors["viable_slots"] = min(1.0, viable_count / 3.0)

        # Ad fit level from auditor
        fit_level = ad_analysis.get("ad_fit", {}).get("level", "D")
        level_scores = {"A": 0.9, "B": 0.7, "C": 0.4, "D": 0.1}
        factors["fit_level"] = level_scores.get(fit_level, 0.1)

        # Page type suitability
        page_type = page_snapshot.get("template_type", page_snapshot.get("page_type", "unknown"))
        page_ad_scores = {
            "content": 0.8, "blog": 0.8, "article": 0.8,
            "category": 0.6, "home": 0.5,
            "product": 0.35, "checkout": 0.1,
        }
        factors["page_type_suitability"] = page_ad_scores.get(page_type, 0.4)

        # Content density (too thin = bad for ads)
        content_length = len(str(page_snapshot.get("content", "")))
        factors["content_density"] = min(1.0, content_length / 3000.0)

        score = (
            factors["viable_slots"] * 0.30
            + factors["fit_level"] * 0.30
            + factors["page_type_suitability"] * 0.25
            + factors["content_density"] * 0.15
        ) * 100

        return ScoreResult(
            score=score,
            label="ad_fit_score",
            factors=factors,
            explanation=f"Fit level={fit_level}, page_type={page_type}, viable_slots={viable_count}",
            passed=score >= AD_FIT_MIN_FOR_PROCEED,
            threshold=AD_FIT_MIN_FOR_PROCEED,
        )

    def compute_risk_score(
        self,
        opportunity: dict[str, Any],
        page_snapshot: dict[str, Any],
        ad_analysis: dict[str, Any],
        site_profile: dict[str, Any],
    ) -> ScoreResult:
        """Risk Score — combined content/tech/performance/compliance risk.

        Architecture §6.2 + §7.2:
        - >= 80: block auto-deploy
        - 60-79: require manual merge
        - < 60: auto-deploy allowed
        """
        risk_components: dict[str, float] = {}

        # Content risk: thin content, low relevance
        relevance = opportunity.get("relevance_score", 50)
        risk_components["content_risk"] = max(0.0, (50 - float(relevance)) / 50.0) * 40

        # Technical risk: JS rendering, crawlability
        is_js_heavy = page_snapshot.get("is_js_rendered", False)
        risk_components["technical_risk"] = 25.0 if is_js_heavy else 5.0

        # Performance risk: LCP/CLS degradation potential
        lcp = page_snapshot.get("lcp_ms", 2500)
        if lcp > 4000:
            risk_components["performance_risk"] = 20.0
        elif lcp > 2500:
            risk_components["performance_risk"] = 10.0
        else:
            risk_components["performance_risk"] = 3.0

        # Compliance risk: policy violations
        policy_violations = ad_analysis.get("policy_violations", 0)
        risk_components["compliance_risk"] = min(30.0, policy_violations * 10.0)

        # Conversion risk: ecommerce pages are riskier
        biz_type = site_profile.get("business_type", "unknown")
        page_type = page_snapshot.get("template_type", "unknown")
        if biz_type == "ecommerce" and page_type in ("product", "checkout"):
            risk_components["conversion_risk"] = 15.0
        elif biz_type == "ecommerce":
            risk_components["conversion_risk"] = 8.0
        else:
            risk_components["conversion_risk"] = 3.0

        # Total risk (0-100 scale, capped)
        total = min(100.0, sum(risk_components.values()))

        return ScoreResult(
            score=total,
            label="risk_score",
            factors=risk_components,
            explanation=(
                f"content={risk_components['content_risk']:.0f}, "
                f"tech={risk_components['technical_risk']:.0f}, "
                f"perf={risk_components['performance_risk']:.0f}, "
                f"compliance={risk_components['compliance_risk']:.0f}, "
                f"conversion={risk_components['conversion_risk']:.0f}"
            ),
            passed=total < RISK_BLOCK_AUTO_DEPLOY,
            threshold=RISK_BLOCK_AUTO_DEPLOY,
        )

    # ── Deployment gate ───────────────────────────────────────────────────────

    def _determine_gate(
        self,
        relevant: ScoreResult,
        value: ScoreResult,
        ux: ScoreResult,
        ad_fit: ScoreResult,
        risk: ScoreResult,
    ) -> tuple[str, list[str]]:
        """Determine deployment gate: allow | require_approval | block.

        Architecture §7.2 thresholds.
        """
        reasons: list[str] = []

        # Hard block: risk >= 80
        if risk.score >= RISK_BLOCK_AUTO_DEPLOY:
            reasons.append(
                f"Risk score {risk.score:.0f} >= {RISK_BLOCK_AUTO_DEPLOY}: "
                "auto-deploy blocked, human review required"
            )
            return "block", reasons

        # Hard block: relevance too low for any recommendation
        if not relevant.passed:
            reasons.append(
                f"Relevance score {relevant.score:.0f} < {RELEVANCE_MIN_FOR_RECOMMEND}: "
                "not relevant enough to recommend"
            )
            return "block", reasons

        # Require approval: risk 60-79
        if risk.score >= RISK_REQUIRE_MANUAL_MERGE:
            reasons.append(
                f"Risk score {risk.score:.0f} in [{RISK_REQUIRE_MANUAL_MERGE}, {RISK_BLOCK_AUTO_DEPLOY}): "
                "preview and PR allowed, default no auto-merge"
            )

        # Require approval: UX below threshold
        if not ux.passed:
            reasons.append(
                f"UX score {ux.score:.0f} < {UX_MIN_FOR_AUTO}: "
                "manual review needed before deploy"
            )

        # Require approval: value too low
        if not value.passed:
            reasons.append(
                f"Value score {value.score:.0f} < {VALUE_MIN_FOR_RECOMMEND}: "
                "low user value, manual review recommended"
            )

        if reasons:
            return "require_approval", reasons

        return "allow", ["All scores within acceptable thresholds"]


# ── Convenience singleton ─────────────────────────────────────────────────────

_default_engine: ScoringEngine | None = None


def get_scoring_engine() -> ScoringEngine:
    global _default_engine
    if _default_engine is None:
        _default_engine = ScoringEngine()
    return _default_engine


def score_proposal(
    site_profile: dict[str, Any] | None = None,
    opportunity: dict[str, Any] | None = None,
    page_snapshot: dict[str, Any] | None = None,
    ad_analysis: dict[str, Any] | None = None,
    ux_review: dict[str, Any] | None = None,
) -> CompositeScore:
    """Convenience function: score a proposal with the default engine."""
    return get_scoring_engine().score_proposal(
        site_profile=site_profile,
        opportunity=opportunity,
        page_snapshot=page_snapshot,
        ad_analysis=ad_analysis,
        ux_review=ux_review,
    )
