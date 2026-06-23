"""GEO Agent - Generative Engine Optimization analysis with REAL data.

This agent analyzes websites using actual crawled content to provide
accurate GEO scores and recommendations.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import urlparse

from .base import Agent, AgentOutput, AgentRole, DebateOpinion, DebateStance, SiteContext


class GEOAgent(Agent):
    """GEO Agent - analyzes websites using REAL crawled data.
    
    This agent performs real GEO analysis by:
    - Analyzing actual page content for citation signals
    - Checking real schema markup
    - Evaluating actual content structure
    - Assessing real authority signals
    """
    
    def __init__(self):
        super().__init__()
        self._role = AgentRole.GEO
    
    def offer_opinion(
        self,
        topic: str,
        proposal: dict[str, Any],
        context: SiteContext,
        previous_opinions: list = None,
    ) -> DebateOpinion:
        """Offer opinion on GEO-related proposals."""
        proposal_text = str(proposal).lower()
        
        if any(word in proposal_text for word in ["content", "seo", "citation", "entity", "authority"]):
            if proposal.get("geo_scores", {}).get("overall", 0) >= 60:
                return DebateOpinion(
                    agent_role=self._role,
                    stance=DebateStance.AGREE,
                    reasoning="GEO scores are above threshold",
                    evidence=["GEO score meets minimum requirements"],
                    confidence=0.8,
                )
            else:
                return DebateOpinion(
                    agent_role=self._role,
                    stance=DebateStance.DISAGREE,
                    reasoning="GEO scores are too low, need improvement",
                    evidence=["GEO score below threshold"],
                    confidence=0.7,
                )
        
        return DebateOpinion(
            agent_role=self._role,
            stance=DebateStance.ABSTAIN,
            reasoning="Not directly related to GEO",
        )
    
    def analyze(self, context: SiteContext) -> AgentOutput:
        """Analyze GEO-readiness using REAL crawled data."""
        url = context.url
        raw_data = context.raw_data
        
        # Analyze using real data
        citation_score = self._analyze_citation_signals(raw_data)
        entity_score = self._analyze_entity_recognition(raw_data)
        structure_score = self._analyze_content_structure(raw_data)
        authority_score = self._analyze_authority_signals(raw_data)
        ai_presence = self._check_ai_search_presence(url, raw_data)
        
        recommendations = self._generate_recommendations(
            citation_score, entity_score, structure_score, authority_score, ai_presence
        )
        
        content = {
            "url": url,
            "geo_scores": {
                "citation": citation_score,
                "entity": entity_score,
                "structure": structure_score,
                "authority": authority_score,
                "ai_presence": ai_presence.get("score", 0),
                "overall": self._calculate_overall_score(
                    citation_score, entity_score, structure_score, authority_score, ai_presence.get("score", 0)
                ),
            },
            "ai_presence": ai_presence,
            "recommendations": recommendations,
            "ai_search_readiness": self._assess_ai_readiness(
                citation_score, entity_score, structure_score, authority_score
            ),
        }
        
        return self._create_output(
            content=content,
            confidence=0.85,
            risk_score=0.1,
            reasoning="Analyzed GEO-readiness using real page data",
        )
    
    def _analyze_citation_signals(self, raw_data: dict[str, Any]) -> float:
        """Analyze citation signals from REAL content."""
        score = 30.0  # Base score
        
        # Get real content
        content = raw_data.get("content", "")
        headings = raw_data.get("headings", [])
        links = raw_data.get("links", [])
        
        # 1. Check for source citations in content
        citation_patterns = [
            r"according to", r"source:", r"reference:", r"study shows",
            r"research indicates", r"data from", r"according to research",
            r"statistics show", r"experts say", r"official data",
        ]
        
        for pattern in citation_patterns:
            if re.search(pattern, content.lower()):
                score += 3
        
        # 2. Check for external links to authoritative sources
        authoritative_domains = [
            "wikipedia.org", "github.com", "stackoverflow.com",
            "nih.gov", "gov", "edu", "scholar.google.com",
            "pubmed.ncbi.nlm.nih.gov", "arxiv.org",
        ]
        
        for link in links:
            if any(domain in link.lower() for domain in authoritative_domains):
                score += 5
        
        # 3. Check for numbers and statistics
        number_patterns = [
            r"\d+(\.\d+)?%",  # Percentages
            r"\$[\d,]+",  # Money amounts
            r"\d{4}",  # Years
            r"\d+(\.\d+)?x",  # Multipliers
        ]
        
        for pattern in number_patterns:
            if re.search(pattern, content):
                score += 2
        
        # 4. Check for headings that suggest citations
        for heading in headings:
            heading_lower = heading.lower()
            if any(word in heading_lower for word in ["research", "study", "data", "statistics", "source"]):
                score += 3
        
        return min(100.0, score)
    
    def _analyze_entity_recognition(self, raw_data: dict[str, Any]) -> float:
        """Analyze entity recognition from REAL data."""
        score = 25.0  # Base score
        
        # 1. Check for structured data (Schema.org)
        schema_data = raw_data.get("schema_data", [])
        if schema_data:
            score += 25
            # Bonus for specific entity types
            for schema in schema_data:
                schema_type = schema.get("@type", "")
                if schema_type in ["Organization", "Person", "Product", "Article"]:
                    score += 5
        
        # 2. Check for meta tags
        title = raw_data.get("title", "")
        meta_desc = raw_data.get("meta_description", "")
        
        if title and len(title) > 10:
            score += 10
        if meta_desc and len(meta_desc) > 50:
            score += 5
        
        # 3. Check for Open Graph tags
        if raw_data.get("og_title") or raw_data.get("og_description"):
            score += 10
        
        # 4. Check for canonical URL
        if raw_data.get("canonical"):
            score += 5
        
        # 5. Check for author information
        if raw_data.get("author"):
            score += 10
        
        return min(100.0, score)
    
    def _analyze_content_structure(self, raw_data: dict[str, Any]) -> float:
        """Analyze content structure from REAL page data."""
        score = 35.0  # Base score
        
        headings = raw_data.get("headings", [])
        content = raw_data.get("content", "")
        
        # 1. Check heading hierarchy
        h1_count = len(headings.get("h1", []))
        h2_count = len(headings.get("h2", []))
        h3_count = len(headings.get("h3", []))
        
        if h1_count == 1:
            score += 10
        elif h1_count > 1:
            score += 5
        
        if h2_count >= 2:
            score += 5
        if h3_count >= 2:
            score += 5
        
        # 2. Check for lists
        if re.search(r"^\s*[\-\*]\s", content, re.MULTILINE):
            score += 5
        if re.search(r"^\s*\d+\.\s", content, re.MULTILINE):
            score += 5
        
        # 3. Check for tables
        if "<table" in content or re.search(r"\|.*\|", content):
            score += 5
        
        # 4. Check paragraph structure
        paragraphs = content.split("\n\n")
        if len(paragraphs) > 3:
            score += 5
        
        # 5. Check for FAQ-style content
        if re.search(r"what is|how to|why|when|where", content.lower()):
            score += 5
        
        return min(100.0, score)
    
    def _analyze_authority_signals(self, raw_data: dict[str, Any]) -> float:
        """Analyze authority signals from REAL data."""
        score = 30.0  # Base score
        
        # 1. HTTPS
        if raw_data.get("url", "").startswith("https://"):
            score += 10
        
        # 2. Domain age (simplified - check domain length)
        url = raw_data.get("url", "")
        domain = urlparse(url).netloc
        if len(domain) < 20:  # Shorter domains often older
            score += 5
        
        # 3. Check for About page
        links = raw_data.get("links", [])
        has_about = any("/about" in link.lower() for link in links)
        if has_about:
            score += 10
        
        # 4. Check for Contact page
        has_contact = any("/contact" in link.lower() for link in links)
        if has_contact:
            score += 5
        
        # 5. Check for Privacy Policy
        has_privacy = any("/privacy" in link.lower() or "/policy" in link.lower() for link in links)
        if has_privacy:
            score += 5
        
        # 6. Check for social links
        social_domains = ["facebook.com", "twitter.com", "linkedin.com", "instagram.com"]
        has_social = any(any(sd in link.lower() for sd in social_domains) for link in links)
        if has_social:
            score += 5
        
        return min(100.0, score)
    
    def _check_ai_search_presence(self, url: str, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Check AI search presence using REAL data."""
        score = 30.0
        signals = []
        
        domain = urlparse(url).netloc
        
        # 1. Domain analysis
        if len(domain) < 20:
            score += 10
            signals.append("short_domain")
        
        # 2. Check for authoritative TLD
        if domain.endswith((".edu", ".gov", ".org")):
            score += 15
            signals.append("authoritative_tld")
        
        # 3. Check content quality indicators
        content = raw_data.get("content", "")
        if len(content) > 500:
            score += 10
            signals.append("substantial_content")
        
        # 4. Check for structured data
        if raw_data.get("schema_data"):
            score += 10
            signals.append("structured_data")
        
        return {
            "score": min(100.0, score),
            "signals": signals,
        }
    
    def _calculate_overall_score(
        self, citation: float, entity: float, structure: float, authority: float, ai_presence: float
    ) -> float:
        """Calculate weighted overall GEO score."""
        weights = {
            "citation": 0.25,
            "entity": 0.20,
            "structure": 0.20,
            "authority": 0.20,
            "ai_presence": 0.15,
        }
        
        return (
            citation * weights["citation"]
            + entity * weights["entity"]
            + structure * weights["structure"]
            + authority * weights["authority"]
            + ai_presence * weights["ai_presence"]
        )
    
    def _assess_ai_readiness(self, citation: float, entity: float, structure: float, authority: float) -> str:
        """Assess AI search readiness level."""
        overall = (citation + entity + structure + authority) / 4
        
        if overall >= 75:
            return "excellent"
        elif overall >= 60:
            return "good"
        elif overall >= 45:
            return "needs_work"
        else:
            return "poor"
    
    def _generate_recommendations(
        self, citation: float, entity: float, structure: float, authority: float, ai_presence: dict
    ) -> list[dict[str, Any]]:
        """Generate actionable GEO recommendations based on real analysis."""
        recommendations = []
        
        # Citation recommendations
        if citation < 50:
            recommendations.append({
                "type": "citation",
                "priority": "high",
                "title": "添加引用来源",
                "description": "在内容中添加权威来源引用，如研究报告、官方数据、专家观点",
                "impact": "提高 AI 搜索引擎引用率",
                "actions": [
                    "引用相关研究数据",
                    "链接到权威网站 (edu/gov/org)",
                    "使用 'According to...' 等引用句式",
                ],
            })
        
        # Entity recommendations
        if entity < 50:
            recommendations.append({
                "type": "entity",
                "priority": "high",
                "title": "优化实体识别",
                "description": "添加结构化数据和清晰的实体命名",
                "impact": "帮助 AI 更好理解页面内容",
                "actions": [
                    "添加 Schema.org 结构化数据",
                    "创建清晰的组织/产品/文章实体",
                    "使用 Open Graph 标签",
                ],
            })
        
        # Structure recommendations
        if structure < 50:
            recommendations.append({
                "type": "structure",
                "priority": "medium",
                "title": "改进内容结构",
                "description": "使用清晰的标题层级和列表格式",
                "impact": "便于 AI 解析和提取信息",
                "actions": [
                    "使用 H1-H3 标题层级",
                    "添加有序/无序列表",
                    "使用表格展示对比数据",
                    "创建 FAQ 部分",
                ],
            })
        
        # Authority recommendations
        if authority < 50:
            recommendations.append({
                "type": "authority",
                "priority": "medium",
                "title": "增强权威信号",
                "description": "添加作者信息、关于我们页面、隐私政策",
                "impact": "提高 AI 信任度和引用率",
                "actions": [
                    "添加作者简介和资质",
                    "创建详细的关于我们页面",
                    "添加隐私政策和联系方式",
                    "链接到社交媒体账号",
                ],
            })
        
        # AI-specific recommendations
        recommendations.append({
            "type": "ai_optimization",
            "priority": "high",
            "title": "优化 AI 搜索可见度",
            "description": "创建易于 AI 引用和理解的内容",
            "impact": "提高在 ChatGPT/Perplexity 等 AI 搜索中的曝光",
            "actions": [
                "在文章开头提供直接答案",
                "使用 'Key Takeaways' 或 '总结' 部分",
                "创建比较表格和列表",
                "提供步骤指南和教程",
            ],
        })
        
        return recommendations
