"""Query Agent - Multi-platform opportunity search."""

from __future__ import annotations

from typing import Any, Optional

from .base import Agent, AgentOutput, AgentRole, SiteContext, DebateOpinion, DebateStance


class QueryAgent(Agent):
    """Query Agent - searches for content opportunities across multiple platforms.
    
    This agent is responsible for:
    - Searching for trending topics
    - Finding keyword opportunities
    - Identifying content gaps
    - Analyzing competitor content
    - Finding GEO opportunities for AI search
    """
    
    def __init__(self):
        super().__init__()
        self._role = AgentRole.QUERY
    
    def analyze(self, context: SiteContext) -> AgentOutput:
        """Search for opportunities across multiple platforms."""
        site_profile = context.site_profile or {}
        business_type = site_profile.get("business_type", "unknown")
        
        # Search for opportunities
        opportunities = []
        
        # Traditional SEO opportunities
        seo_opps = self._find_seo_opportunities(context)
        opportunities.extend(seo_opps)
        
        # GEO opportunities for AI search
        geo_opps = self._find_geo_opportunities(context)
        opportunities.extend(geo_opps)
        
        # Content opportunities
        content_opps = self._find_content_opportunities(context)
        opportunities.extend(content_opps)
        
        # Competitor gaps
        competitor_gaps = self._find_competitor_gaps(context)
        opportunities.extend(competitor_gaps)
        
        content = {
            "opportunities": opportunities,
            "total_found": len(opportunities),
            "high_priority": len([o for o in opportunities if o.get("priority") == "high"]),
            "platform_coverage": self._get_platform_coverage(),
        }
        
        return self._create_output(
            content=content,
            confidence=0.7,
            risk_score=0.2,
            reasoning=f"Found {len(opportunities)} opportunities across multiple platforms",
        )
    
    def challenge(self, other_output: AgentOutput, context: SiteContext) -> Optional[dict[str, Any]]:
        """Challenge if opportunities don't align with site analysis."""
        if other_output.agent_role == AgentRole.SNIFFER:
            site_profile = other_output.content
            business_type = site_profile.get("business_type", "unknown")
            
            # Check if opportunities match business type
            opportunities = self._find_seo_opportunities(context)
            mismatched = [
                o for o in opportunities
                if not self._matches_business_type(o, business_type)
            ]
            
            if mismatched:
                return {
                    "type": "opportunity_mismatch",
                    "reason": f"{len(mismatched)} opportunities don't match business type",
                    "suggestion": "Filter opportunities by business type relevance",
                    "mismatched_count": len(mismatched),
                }
        
        return None
    
    def offer_opinion(
        self,
        topic: str,
        proposal: dict[str, Any],
        context: SiteContext,
        previous_opinions: list[DebateOpinion] = None,
    ) -> DebateOpinion:
        """Opine from a keyword-opportunity / search-intent perspective."""
        seo_opps = self._find_seo_opportunities(context)
        geo_opps = self._find_geo_opportunities(context)
        total = len(seo_opps) + len(geo_opps)
        high_val = [o for o in seo_opps if o.get("priority") == "high"]
        coverage = self._get_platform_coverage()
        ai_covered = sum(1 for v in coverage.values() if v)

        if total >= 5 and len(high_val) >= 2:
            return DebateOpinion(
                agent_role=self._role,
                stance=DebateStance.AGREE,
                reasoning=(f"Strong landscape: {len(high_val)} high-priority gaps "
                           f"across {ai_covered} AI platforms."),
                evidence=[f"Opportunities: {total} ({len(seo_opps)} SEO, {len(geo_opps)} GEO)",
                          f"High-priority gaps: {len(high_val)}",
                          f"AI coverage: {ai_covered}/{len(coverage)}"],
                confidence=0.85,
            )
        if total >= 2:
            return DebateOpinion(
                agent_role=self._role,
                stance=DebateStance.PARTIALLY_AGREE,
                reasoning="Moderate opportunity set — viable but prioritise quick-wins first.",
                evidence=[f"Found {total} opportunities; {len(high_val)} high-value"],
                confidence=0.72,
                conditions=["Prioritise high-value keyword gaps before broader expansion"],
            )
        return DebateOpinion(
            agent_role=self._role,
            stance=DebateStance.DISAGREE,
            reasoning="Insufficient keyword-opportunity data to support the proposal.",
            evidence=["< 2 opportunities identified", "Search-intent signals too weak"],
            confidence=0.78,
            conditions=["Run deeper keyword research before committing to execution"],
        )

    def _find_seo_opportunities(self, context: SiteContext) -> list[dict[str, Any]]:
        """Find traditional SEO opportunities from keyword/search datasets."""
        opportunities = self._keyword_research_opportunities(context)
        if opportunities:
            return opportunities

        site_profile = context.site_profile or {}
        business_type = site_profile.get("business_type", "unknown")

        fallback: list[dict[str, Any]] = []
        if business_type == "ecommerce":
            fallback.append({
                "type": "product_schema",
                "title": "Add Product Schema",
                "description": "Implement structured data for product pages",
                "priority": "high",
                "engine": "google",
                "estimated_impact": "Rich snippets in search results",
                "source": "business_profile_fallback",
            })

        if business_type == "content":
            fallback.append({
                "type": "faq_schema",
                "title": "Add FAQ Schema",
                "description": "Create FAQ content with structured data",
                "priority": "medium",
                "engine": "google",
                "estimated_impact": "FAQ rich results",
                "source": "business_profile_fallback",
            })

        return fallback
    
    def _find_geo_opportunities(self, context: SiteContext) -> list[dict[str, Any]]:
        """Find GEO opportunities for AI search engines."""
        opportunities = []
        
        # GEO opportunities
        opportunities.append({
            "type": "citation_content",
            "title": "Create Citation-Friendly Content",
            "description": "Write content with clear sources and data",
            "priority": "high",
            "engine": "chatgpt/perplexity",
            "estimated_impact": "Better visibility in AI search results",
        })
        
        opportunities.append({
            "type": "entity_optimization",
            "title": "Optimize Entity Recognition",
            "description": "Implement structured data for entities",
            "priority": "medium",
            "engine": "chatgpt/perplexity",
            "estimated_impact": "Better entity understanding by AI",
        })
        
        opportunities.append({
            "type": "authority_signals",
            "title": "Build Authority Signals",
            "description": "Create authoritative content with citations",
            "priority": "high",
            "engine": "claude",
            "estimated_impact": "Higher trust score in AI responses",
        })
        
        return opportunities
    
    def _find_content_opportunities(self, context: SiteContext) -> list[dict[str, Any]]:
        """Find content opportunities from trend datasets."""
        opportunities = []
        for trend in self._get_list_dataset(context, "trending_topics"):
            topic = str(trend.get("topic") or trend.get("keyword") or trend.get("title") or "").strip()
            if not topic:
                continue
            growth = trend.get("growth", trend.get("growth_pct", trend.get("trend_score", 0)))
            priority = "high" if _as_float(growth) >= 50 else "medium"
            opportunities.append({
                "type": "trending_topic",
                "title": f"Cover: {topic}",
                "description": f"Create timely content around '{topic}' while trend momentum is high",
                "priority": priority,
                "engine": "all",
                "estimated_impact": "Fresh content signal + trend-driven traffic potential",
                "source": trend.get("source", "trend_data"),
                "topic": topic,
                "growth": growth,
            })

        return opportunities
    
    def _find_competitor_gaps(self, context: SiteContext) -> list[dict[str, Any]]:
        """Find gaps from competitor keyword-position datasets."""
        opportunities = []
        competitor_data = self._get_mapping_dataset(context, "competitor_data")
        known_keywords = set(self._get_mapping_dataset(context, "our_rank_history"))

        for domain, data in competitor_data.items():
            positions = (data or {}).get("keyword_positions", {}) if isinstance(data, dict) else {}
            for keyword, position in positions.items():
                if keyword in known_keywords:
                    continue
                priority = "high" if _as_float(position, 999) <= 10 else "medium"
                opportunities.append({
                    "type": "content_gap",
                    "title": f"Fill Content Gap: {keyword}",
                    "description": f"Competitor {domain} ranks #{position} for '{keyword}'",
                    "priority": priority,
                    "engine": "all",
                    "estimated_impact": "Capture missing organic traffic from competitor keyword gaps",
                    "source": "competitor_analysis",
                    "keyword": keyword,
                    "competitor": domain,
                    "position": position,
                })

        return sorted(opportunities, key=lambda o: _as_float(o.get("position"), 999))[:20]
    

    def _keyword_research_opportunities(self, context: SiteContext) -> list[dict[str, Any]]:
        data = self._get_mapping_dataset(context, "keyword_research")
        keywords = data.get("keywords", []) if isinstance(data, dict) else []
        opportunities = []
        for item in keywords:
            if not isinstance(item, dict):
                continue
            keyword = str(item.get("keyword") or "").strip()
            if not keyword:
                continue
            difficulty = _as_float(item.get("difficulty"), 50)
            volume = _as_float(item.get("search_volume"), 0)
            score = _as_float(item.get("score"), max(0, 100 - difficulty) + min(volume / 100, 25))
            priority = "high" if score >= 75 or (difficulty <= 30 and volume >= 1000) else "medium"
            opportunities.append({
                "type": "keyword_opportunity",
                "title": f"Target keyword: {keyword}",
                "description": f"Create or optimize content for '{keyword}'",
                "priority": priority,
                "engine": "google",
                "estimated_impact": f"Volume {int(volume)} with difficulty {difficulty:g}",
                "source": "keyword_research",
                "keyword": keyword,
                "search_volume": item.get("search_volume", 0),
                "difficulty": item.get("difficulty", 0),
                "intent": item.get("intent", "informational"),
                "score": score,
            })

        return sorted(opportunities, key=lambda o: _as_float(o.get("score")), reverse=True)[:20]

    def _get_mapping_dataset(self, context: SiteContext, key: str) -> dict[str, Any]:
        raw = context.raw_data or {}
        value = raw.get(key)
        if isinstance(value, dict):
            return value
        return {}

    def _get_list_dataset(self, context: SiteContext, key: str) -> list[dict[str, Any]]:
        raw = context.raw_data or {}
        value = raw.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = value.get("topics") or value.get("items") or value.get("data")
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
        return []

    def _matches_business_type(self, opportunity: dict[str, Any], business_type: str) -> bool:
        """Check if an opportunity matches the business type."""
        # Simple matching logic
        if business_type == "ecommerce":
            return opportunity.get("type") in ["product_schema", "buying_guide", "comparison"]
        elif business_type == "content":
            return opportunity.get("type") in ["faq_schema", "citation_content", "trending_topic"]
        return True
    
    def _get_platform_coverage(self) -> dict[str, bool]:
        """Get coverage status for each platform."""
        return {
            "google": True,
            "bing": True,
            "baidu": False,
            "yandex": False,
            "chatgpt": True,
            "perplexity": True,
            "claude": True,
        }


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
