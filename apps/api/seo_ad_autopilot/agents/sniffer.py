"""Sniffer Agent - Site analysis and classification."""

from __future__ import annotations

from typing import Any, Optional

from .base import Agent, AgentOutput, AgentRole, DebateRound, SiteContext


class SnifferAgent(Agent):
    """Sniffer Agent - analyzes sites to understand their business, audience, and structure.
    
    This agent is responsible for:
    - Identifying the site's core business
    - Understanding the target audience
    - Classifying page templates
    - Extracting UI style tokens
    - Assessing site maturity
    """
    
    def __init__(self):
        super().__init__()
        self._role = AgentRole.SNIFFER
    
    def analyze(self, context: SiteContext) -> AgentOutput:
        """Analyze the site and produce a SiteProfile."""
        url = context.url
        raw_data = context.raw_data
        
        # Extract signals from raw data
        signals = self._extract_signals(raw_data)
        
        # Classify business type
        business_type = self._classify_business(signals)
        
        # Identify audience
        audience = self._identify_audience(signals)
        
        # Classify page templates
        page_templates = self._classify_templates(raw_data.get("pages", []))
        
        # Extract UI style tokens
        ui_tokens = self._extract_ui_tokens(raw_data)
        
        # Calculate maturity score
        maturity_score = self._calculate_maturity(signals, raw_data)
        
        content = {
            "url": url,
            "business_type": business_type,
            "audience": audience,
            "page_templates": page_templates,
            "ui_tokens": ui_tokens,
            "maturity_score": maturity_score,
            "core_conversions": self._identify_conversions(signals),
            "content_gaps": self._identify_content_gaps(raw_data),
            "technical_health": self._assess_technical_health(raw_data),
        }
        
        confidence = 0.8 if signals else 0.3
        needs_human_review = confidence < 0.6
        
        return self._create_output(
            content=content,
            confidence=confidence,
            risk_score=0.1,
            needs_human_review=needs_human_review,
            reasoning=f"Analyzed {url} with {len(signals)} signals",
        )
    
    def challenge(self, other_output: AgentOutput, context: SiteContext) -> Optional[dict[str, Any]]:
        """Challenge another agent's output if it conflicts with site analysis."""
        if other_output.agent_role == AgentRole.QUERY:
            # Challenge if query results don't match site classification
            site_profile = other_output.content.get("site_profile", {})
            if site_profile.get("business_type") != context.site_profile.get("business_type"):
                return {
                    "type": "classification_conflict",
                    "reason": "Query results suggest different business type than site analysis",
                    "suggestion": "Re-evaluate business classification based on query results",
                }
        return None
    
    def _extract_signals(self, raw_data: dict[str, Any]) -> list[str]:
        """Extract business signals from raw data."""
        signals = []
        
        # Check meta tags
        meta = raw_data.get("meta", {})
        if meta.get("title"):
            signals.append(f"title:{meta['title']}")
        if meta.get("description"):
            signals.append(f"description:{meta['description']}")
        
        # Check content
        content = raw_data.get("content", "")
        commerce_words = ["shop", "store", "buy", "price", "cart", "checkout"]
        content_words = ["blog", "news", "article", "guide", "tutorial"]
        
        for word in commerce_words:
            if word in content.lower():
                signals.append(f"commerce:{word}")
        
        for word in content_words:
            if word in content.lower():
                signals.append(f"content:{word}")
        
        return signals
    
    def _classify_business(self, signals: list[str]) -> str:
        """Classify business type based on signals."""
        commerce_score = sum(1 for s in signals if s.startswith("commerce:"))
        content_score = sum(1 for s in signals if s.startswith("content:"))
        
        if commerce_score > content_score:
            return "ecommerce"
        elif content_score > commerce_score:
            return "content"
        else:
            return "mixed"
    
    def _identify_audience(self, signals: list[str]) -> dict[str, Any]:
        """Identify target audience."""
        return {
            "primary": "general",
            "interests": [],
            "demographics": {},
        }
    
    def _classify_templates(self, pages: list[dict[str, Any]]) -> list[str]:
        """Classify page templates."""
        templates = set()
        for page in pages:
            path = page.get("path", "/")
            if path == "/":
                templates.add("home")
            elif "/product" in path or "/item" in path:
                templates.add("product")
            elif "/blog" in path or "/news" in path:
                templates.add("content")
            elif "/category" in path or "/tag" in path:
                templates.add("category")
            else:
                templates.add("other")
        return list(templates)
    
    def _extract_ui_tokens(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Extract UI style tokens."""
        return {
            "colors": [],
            "fonts": [],
            "spacing": {},
            "layout": "unknown",
        }
    
    def _calculate_maturity(self, signals: list[str], raw_data: dict[str, Any]) -> float:
        """Calculate site maturity score (0-100)."""
        score = 50.0
        
        # Content depth
        content_length = len(raw_data.get("content", ""))
        if content_length > 10000:
            score += 10
        elif content_length > 5000:
            score += 5
        
        # Technical signals
        if raw_data.get("has_schema"):
            score += 10
        if raw_data.get("has_sitemap"):
            score += 5
        if raw_data.get("is_mobile_friendly"):
            score += 10
        
        return min(100.0, max(0.0, score))
    
    def _identify_conversions(self, signals: list[str]) -> list[str]:
        """Identify core conversion goals."""
        conversions = []
        for signal in signals:
            if "commerce" in signal:
                conversions.append("purchase")
            if "content" in signal:
                conversions.append("engagement")
        return conversions or ["unknown"]
    
    def _identify_content_gaps(self, raw_data: dict[str, Any]) -> list[str]:
        """Identify content gaps."""
        gaps = []
        
        # Check for missing content types
        pages = raw_data.get("pages", [])
        has_faq = any("/faq" in p.get("path", "") for p in pages)
        has_about = any("/about" in p.get("path", "") for p in pages)
        has_blog = any("/blog" in p.get("path", "") for p in pages)
        
        if not has_faq:
            gaps.append("FAQ page")
        if not has_about:
            gaps.append("About page")
        if not has_blog:
            gaps.append("Blog/News section")
        
        return gaps
    
    def _assess_technical_health(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Assess technical health."""
        return {
            "score": 70,
            "issues": [],
            "warnings": [],
        }
