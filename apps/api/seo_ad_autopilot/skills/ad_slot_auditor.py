"""AdSlotAuditor Skill - Scan DOM for ad placement candidates with exclusion zones.

Implements PRD §5.2 requirements:
- Scan DOM for visual attention zones, content breakpoints, scroll-return zones
- Exclude conversion-critical areas (CTA, checkout, forms, price, payment)
- Score each candidate: visibility, UX impact, conversion risk, ad type fit
- Output selector-level candidate list with priority ranking
- Explicitly recommend "no ads" when all candidates score below threshold
"""

from __future__ import annotations

import time
from typing import Any

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


# ── Default exclusion zones (PRD §5.2) ──────────────────────────────────────

DEFAULT_EXCLUSION_ZONES: list[dict[str, Any]] = [
    {
        "selector": ".buy-button, .add-to-cart, .checkout-cta, [data-cta='buy']",
        "reason": "Primary purchase CTA",
        "priority": "critical",
    },
    {
        "selector": ".checkout, .payment-form, .billing-form",
        "reason": "Checkout / payment flow",
        "priority": "critical",
    },
    {
        "selector": ".price, .pricing, .discount-code",
        "reason": "Price display area",
        "priority": "high",
    },
    {
        "selector": "header nav, .main-nav, .site-header",
        "reason": "Primary navigation",
        "priority": "high",
    },
    {
        "selector": ".lead-form, .contact-form, .signup-form",
        "reason": "Lead generation form",
        "priority": "high",
    },
    {
        "selector": "footer .legal, footer .privacy",
        "reason": "Legal / privacy links",
        "priority": "medium",
    },
]

# ── Candidate position heuristics ────────────────────────────────────────────

_CANDIDATE_SELECTORS = [
    {
        "selector": "article .content-body, .post-content, .entry-content",
        "position_type": "in_article",
        "base_visibility": 0.75,
        "base_ux_impact": 0.30,
        "description": "Within article body (mid-content)",
    },
    {
        "selector": ".sidebar, aside, .widget-area",
        "position_type": "sidebar",
        "base_visibility": 0.55,
        "base_ux_impact": 0.20,
        "description": "Sidebar widget area",
    },
    {
        "selector": ".after-content, .post-footer, .content-end",
        "position_type": "after_content",
        "base_visibility": 0.65,
        "base_ux_impact": 0.25,
        "description": "After main content block",
    },
    {
        "selector": ".feed-item, .card-list, .product-grid",
        "position_type": "in_feed",
        "base_visibility": 0.70,
        "base_ux_impact": 0.35,
        "description": "Within content/product feed",
    },
    {
        "selector": ".between-sections, .section-divider, hr + *",
        "position_type": "content_break",
        "base_visibility": 0.60,
        "base_ux_impact": 0.25,
        "description": "Between content sections",
    },
    {
        "selector": ".related-posts, .recommended, .you-may-like",
        "position_type": "related",
        "base_visibility": 0.50,
        "base_ux_impact": 0.20,
        "description": "Related / recommended content area",
    },
]


class AdSlotAuditorSkill(Skill):
    """AdSlotAuditor — scan DOM and score ad placement candidates.

    Risk level: read_only (analysis only, no modification).
    """

    @property
    def name(self) -> str:
        return "AdSlotAuditor"

    @property
    def description(self) -> str:
        return (
            "Scan DOM structure to identify safe ad placement candidates. "
            "Excludes conversion-critical zones. Scores each candidate on "
            "visibility, UX impact, conversion risk, and ad-type fit. "
            "Outputs ranked selector-level candidates or explicit no-ad recommendation."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ANALYZE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    @property
    def requires_approval(self) -> bool:
        return False

    @property
    def rollback_supported(self) -> bool:
        return True  # Analysis-only, but supports "undo" via removing candidates

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start = time.time()

        url = skill_input.url or skill_input.params.get("url", "")
        dom_snapshot = skill_input.params.get("dom_snapshot") or skill_input.context.get("dom_snapshot", {})
        strategy = skill_input.params.get("strategy", "conservative")
        custom_exclusions = skill_input.params.get("exclude_selectors", [])
        page_type = skill_input.params.get("page_type", "unknown")
        site_business = skill_input.params.get("site_business", "unknown")

        if not url and not dom_snapshot:
            return self._create_output(
                success=False,
                error="Either url or dom_snapshot is required",
                execution_time_ms=int((time.time() - start) * 1000),
            )

        try:
            # Merge default + custom exclusion zones
            exclusion_zones = self._build_exclusion_zones(custom_exclusions)

            # Scan for candidates
            candidates = self._scan_candidates(dom_snapshot, exclusion_zones, strategy)

            # Score each candidate
            scored_candidates = []
            for c in candidates:
                scored = self._score_candidate(c, page_type, site_business, strategy)
                scored_candidates.append(scored)

            # Sort by composite score descending
            scored_candidates.sort(key=lambda x: x["composite_score"], reverse=True)

            # Apply strategy filter
            min_score = self._strategy_min_score(strategy)
            viable = [c for c in scored_candidates if c["composite_score"] >= min_score]

            # Determine ad fit level (A/B/C/D)
            ad_fit = self._compute_ad_fit_level(viable, page_type, site_business)

            # Build recommendation
            if not viable:
                recommendation = {
                    "action": "no_ads",
                    "reason": (
                        f"All {len(scored_candidates)} candidates scored below "
                        f"threshold ({min_score}). Site/page not suitable for ads."
                    ),
                    "ad_fit_level": ad_fit["level"],
                }
            else:
                recommendation = {
                    "action": "proceed",
                    "top_candidates": viable[:5],
                    "ad_fit_level": ad_fit["level"],
                    "ad_fit_reason": ad_fit["reason"],
                    "suggested_ad_types": ad_fit["suggested_ad_types"],
                }

            execution_ms = int((time.time() - start) * 1000)

            return self._create_output(
                success=True,
                result={
                    "url": url,
                    "strategy": strategy,
                    "page_type": page_type,
                    "exclusion_zones_count": len(exclusion_zones),
                    "total_candidates": len(scored_candidates),
                    "viable_candidates": len(viable),
                    "candidates": scored_candidates[:20],
                    "ad_fit": ad_fit,
                    "recommendation": recommendation,
                },
                execution_time_ms=execution_ms,
            )

        except Exception as e:
            return self._create_output(
                success=False,
                error=f"AdSlotAuditor failed: {str(e)}",
                execution_time_ms=int((time.time() - start) * 1000),
            )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Page URL"},
                "dom_snapshot": {"type": "object", "description": "DOM structure snapshot"},
                "strategy": {
                    "type": "string",
                    "enum": ["aggressive", "moderate", "conservative"],
                    "default": "conservative",
                },
                "exclude_selectors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional CSS selectors to exclude",
                },
                "page_type": {"type": "string", "description": "home|category|product|content|faq"},
                "site_business": {"type": "string", "description": "ecommerce|content|saas|tool|local"},
            },
            "required": [],
        }

    def get_output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "candidates": {"type": "array"},
                "ad_fit": {"type": "object"},
                "recommendation": {"type": "object"},
                "viable_candidates": {"type": "integer"},
            },
        }

    # ── Private helpers ──────────────────────────────────────────────────────

    def _build_exclusion_zones(self, custom: list[str]) -> list[dict[str, Any]]:
        zones = list(DEFAULT_EXCLUSION_ZONES)
        for sel in custom:
            zones.append({
                "selector": sel,
                "reason": "User-specified exclusion",
                "priority": "high",
            })
        return zones

    def _scan_candidates(
        self,
        dom_snapshot: dict[str, Any],
        exclusions: list[dict[str, Any]],
        strategy: str,
    ) -> list[dict[str, Any]]:
        """Scan DOM snapshot for candidate ad positions."""
        candidates = []

        # If we have a real DOM snapshot with elements, use it
        elements = dom_snapshot.get("elements", []) if isinstance(dom_snapshot, dict) else []

        if elements:
            for elem in elements:
                if not isinstance(elem, dict):
                    continue
                selector = elem.get("selector", "")
                tag = elem.get("tag", "")

                # Skip if in exclusion zone
                if self._is_excluded(selector, exclusions):
                    continue

                # Only consider block-level containers
                if tag in ("div", "section", "article", "aside", "main"):
                    candidates.append({
                        "selector": selector,
                        "tag": tag,
                        "position_type": self._infer_position_type(selector, elem),
                        "base_visibility": self._estimate_visibility(elem),
                        "base_ux_impact": self._estimate_ux_impact(elem),
                        "description": elem.get("class", selector),
                    })
        else:
            # Fallback: use heuristic candidate selectors
            for c in _CANDIDATE_SELECTORS:
                if self._is_excluded(c["selector"], exclusions):
                    candidates.append(dict(c))

        return candidates

    def _is_excluded(self, selector: str, exclusions: list[dict[str, Any]]) -> bool:
        sel_lower = selector.lower()
        for zone in exclusions:
            zone_sel = zone.get("selector", "").lower()
            # Simple substring match for exclusion
            for part in zone_sel.split(","):
                part = part.strip()
                if part and part in sel_lower:
                    return True
        return False

    def _infer_position_type(self, selector: str, elem: dict[str, Any]) -> str:
        sel = selector.lower()
        if "sidebar" in sel or "aside" in sel:
            return "sidebar"
        if "footer" in sel or "after" in sel:
            return "after_content"
        if "feed" in sel or "card" in sel or "grid" in sel:
            return "in_feed"
        if "related" in sel or "recommend" in sel:
            return "related"
        return "in_article"

    def _estimate_visibility(self, elem: dict[str, Any]) -> float:
        """Estimate visibility score 0-1 based on element properties."""
        base = 0.5
        # Larger elements are more visible
        area = elem.get("area", 0)
        if area > 50000:
            base += 0.2
        elif area > 20000:
            base += 0.1
        # Above-fold bonus
        if elem.get("above_fold", False):
            base += 0.15
        return min(1.0, base)

    def _estimate_ux_impact(self, elem: dict[str, Any]) -> float:
        """Estimate UX disruption score 0-1 (lower is better)."""
        base = 0.3
        # Dense content areas are more disruptive
        if elem.get("text_density", 0) > 0.7:
            base += 0.2
        # Interactive elements nearby increase disruption
        if elem.get("has_interactive", False):
            base += 0.15
        return min(1.0, base)

    def _score_candidate(
        self,
        candidate: dict[str, Any],
        page_type: str,
        site_business: str,
        strategy: str,
    ) -> dict[str, Any]:
        """Score a single ad placement candidate (PRD §5.2 four dimensions)."""
        visibility = candidate.get("base_visibility", 0.5)
        ux_impact = candidate.get("base_ux_impact", 0.3)

        # Conversion risk: higher on product/checkout pages
        conversion_risk = self._conversion_risk(candidate, page_type, site_business)

        # Ad type fit: which ad formats work here
        ad_type_fit = self._ad_type_fit(candidate, page_type)

        # Composite score: weighted average (higher = better candidate)
        # Visibility high, UX impact low, conversion risk low
        composite = (
            visibility * 0.35
            + (1.0 - ux_impact) * 0.30
            + (1.0 - conversion_risk) * 0.25
            + ad_type_fit["score"] * 0.10
        )

        return {
            **candidate,
            "visibility_score": round(visibility, 3),
            "ux_impact_score": round(ux_impact, 3),
            "conversion_risk_score": round(conversion_risk, 3),
            "ad_type_fit": ad_type_fit,
            "composite_score": round(composite, 3),
        }

    def _conversion_risk(
        self, candidate: dict[str, Any], page_type: str, site_business: str
    ) -> float:
        """Assess conversion path interference risk 0-1."""
        risk = 0.2  # base

        # Product pages have higher conversion risk
        if page_type in ("product", "checkout"):
            risk += 0.3
        elif page_type == "category":
            risk += 0.15

        # Ecommerce sites: conversion is sacred
        if site_business == "ecommerce":
            risk += 0.15

        # Sidebar/related positions are lower risk
        pos = candidate.get("position_type", "")
        if pos in ("sidebar", "related"):
            risk -= 0.1
        elif pos == "in_feed":
            risk += 0.1

        return max(0.0, min(1.0, risk))

    def _ad_type_fit(self, candidate: dict[str, Any], page_type: str) -> dict[str, Any]:
        """Determine which ad types fit this position."""
        pos = candidate.get("position_type", "")
        types = []
        score = 0.5

        if pos == "in_article":
            types = ["in_article", "native", "text"]
            score = 0.7
        elif pos == "sidebar":
            types = ["display", "native", "recommendation"]
            score = 0.6
        elif pos == "after_content":
            types = ["native", "recommendation", "display"]
            score = 0.75
        elif pos == "in_feed":
            types = ["in_feed", "native"]
            score = 0.65
        elif pos == "related":
            types = ["recommendation", "native"]
            score = 0.55
        else:
            types = ["native"]
            score = 0.4

        return {"types": types, "score": score}

    def _strategy_min_score(self, strategy: str) -> float:
        thresholds = {
            "aggressive": 0.35,
            "moderate": 0.50,
            "conservative": 0.60,
        }
        return thresholds.get(strategy, 0.60)

    def _compute_ad_fit_level(
        self,
        viable: list[dict[str, Any]],
        page_type: str,
        site_business: str,
    ) -> dict[str, Any]:
        """Compute A/B/C/D ad fit level per PRD §5.1."""
        if not viable:
            return {
                "level": "D",
                "reason": "No viable ad positions found. Content too thin or page too constrained.",
                "suggested_ad_types": [],
            }

        avg_composite = sum(c["composite_score"] for c in viable) / len(viable)
        avg_conversion_risk = sum(c["conversion_risk_score"] for c in viable) / len(viable)

        # Level A: content/news pages, high dwell, CTA separable
        if (
            page_type in ("content", "blog", "article")
            and avg_composite >= 0.65
            and avg_conversion_risk < 0.4
        ):
            return {
                "level": "A",
                "reason": "Content-type page with high dwell time and separable CTA. Ideal for native + in-feed ads.",
                "suggested_ad_types": ["native", "in_feed", "in_article"],
            }

        # Level B: ecommerce pages, light native only
        if (
            site_business == "ecommerce"
            and avg_composite >= 0.55
            and avg_conversion_risk < 0.55
        ):
            return {
                "level": "B",
                "reason": "Ecommerce page. Only non-interruptive native or brand-sponsored slots recommended.",
                "suggested_ad_types": ["native", "sponsored"],
            }

        # Level C: high-conversion pages, sponsored only
        if page_type in ("product", "checkout") or avg_conversion_risk >= 0.55:
            return {
                "level": "C",
                "reason": "High-conversion page with short conversion path. Only sponsored slots or no ads.",
                "suggested_ad_types": ["sponsored"],
            }

        # Level D: insufficient content or layout
        if avg_composite < 0.45:
            return {
                "level": "D",
                "reason": "Page content too thin or layout too constrained. Prioritize content expansion before ads.",
                "suggested_ad_types": [],
            }

        # Default: moderate B
        return {
            "level": "B",
            "reason": "Moderate ad suitability. Proceed with caution and A/B testing.",
            "suggested_ad_types": ["native", "display"],
        }
