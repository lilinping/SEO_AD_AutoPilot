"""ChatGPT GEO Engine implementation."""

from __future__ import annotations

from typing import Optional

from .base import (
    GEOOptimization,
    SearchEngine,
    SearchEngineCategory,
    SearchEngineType,
    SearchQuery,
    SearchResult,
    SiteAnalysis,
)


class ChatGPTGEOEngine(SearchEngine):
    """ChatGPT as a generative search engine.
    
    Optimizing for ChatGPT means:
    - Creating content that AI can easily cite
    - Structured data that helps AI understand entities
    - Clear, factual content with strong authority signals
    """
    
    @property
    def category(self) -> SearchEngineCategory:
        return SearchEngineCategory.CHATGPT
    
    @property
    def engine_type(self) -> SearchEngineType:
        return SearchEngineType.GEO
    
    @property
    def name(self) -> str:
        return "ChatGPT"
    
    def search(self, query: SearchQuery) -> list[SearchResult]:
        """ChatGPT doesn't have a traditional search API for rankings.
        
        Instead, we analyze how content appears in ChatGPT responses.
        """
        return []
    
    def analyze_site(self, url: str) -> SiteAnalysis:
        """Analyze how site content appears in ChatGPT responses."""
        return SiteAnalysis(
            url=url,
            rankings={self.category: []},
            geo_scores={self.category: 0.0},
            recommendations={self.category: self.get_geo_recommendations(url)},
        )
    
    def get_geo_optimizations(self, url: str) -> GEOOptimization:
        """Get ChatGPT-specific GEO optimizations."""
        return GEOOptimization(
            engine=self.category,
            recommendations=self.get_geo_recommendations(url),
            entity_optimization=[
                "Implement Organization and Person schema",
                "Use clear entity naming (avoid abbreviations)",
                "Create comprehensive 'About' pages",
                "Link to authoritative sources (Wikipedia, official docs)",
            ],
            structured_data_needed=[
                "FAQ Schema for Q&A content",
                "HowTo Schema for tutorials",
                "Article Schema with author and datePublished",
                "Organization Schema with sameAs links",
            ],
            citation_signals=[
                "Include statistics and data with sources",
                "Quote experts with credentials",
                "Link to primary sources",
                "Use numbered lists and clear structure",
                "Include dates and update timestamps",
            ],
            content_format_tips=[
                "Write clear, factual introductions",
                "Use H2/H3 headings that answer questions directly",
                "Include 'Key Takeaways' or 'TL;DR' sections",
                "Use tables for comparisons",
                "Include author bios with credentials",
            ],
            confidence=0.8,
        )
    
    def get_geo_recommendations(self, url: str) -> list[str]:
        """Get ChatGPT-specific GEO recommendations."""
        return [
            "Create citation-friendly content with clear data sources",
            "Implement structured data for entity recognition",
            "Write fact-checkable claims with references",
            "Use clear, authoritative language",
            "Include 'About the Author' sections",
            "Create comprehensive FAQ sections",
            "Link to official documentation and primary sources",
            "Use numbered lists and step-by-step guides",
            "Include publication and update dates",
            "Build topical authority through depth, not breadth",
        ]
