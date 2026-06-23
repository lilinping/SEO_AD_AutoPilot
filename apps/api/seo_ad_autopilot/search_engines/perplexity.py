"""Perplexity GEO Engine implementation."""

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


class PerplexityGEOEngine(SearchEngine):
    """Perplexity AI as a generative search engine.
    
    Optimizing for Perplexity means:
    - Creating content that Perplexity can cite and reference
    - Strong factual signals with clear sources
    - Structured content that AI can parse and synthesize
    """
    
    @property
    def category(self) -> SearchEngineCategory:
        return SearchEngineCategory.PERPLEXITY
    
    @property
    def engine_type(self) -> SearchEngineType:
        return SearchEngineType.GEO
    
    @property
    def name(self) -> str:
        return "Perplexity"
    
    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Perplexity doesn't have a traditional search API for rankings.
        
        Instead, we analyze how content appears in Perplexity responses.
        """
        return []
    
    def analyze_site(self, url: str) -> SiteAnalysis:
        """Analyze how site content appears in Perplexity responses."""
        return SiteAnalysis(
            url=url,
            rankings={self.category: []},
            geo_scores={self.category: 0.0},
            recommendations={self.category: self.get_geo_recommendations(url)},
        )
    
    def get_geo_optimizations(self, url: str) -> GEOOptimization:
        """Get Perplexity-specific GEO optimizations."""
        return GEOOptimization(
            engine=self.category,
            recommendations=self.get_geo_recommendations(url),
            entity_optimization=[
                "Create clear entity definitions",
                "Use consistent naming across pages",
                "Implement Knowledge Graph schema",
                "Link to authoritative entity sources",
            ],
            structured_data_needed=[
                "FAQ Schema for common questions",
                "HowTo Schema for procedures",
                "Article Schema with datePublished and dateModified",
                "Claim Schema for factual assertions",
            ],
            citation_signals=[
                "Cite primary sources in-line",
                "Include data tables with sources",
                "Reference official documentation",
                "Use footnotes or references sections",
                "Include methodology for data claims",
            ],
            content_format_tips=[
                "Start with clear, direct answers",
                "Use comparison tables",
                "Include pros/cons lists",
                "Provide step-by-step instructions",
                "Add context and background",
            ],
            confidence=0.8,
        )
    
    def get_geo_recommendations(self, url: str) -> list[str]:
        """Get Perplexity-specific GEO recommendations."""
        return [
            "Create content that answers specific questions directly",
            "Include inline citations to authoritative sources",
            "Use structured data for factual claims",
            "Write comprehensive, well-researched content",
            "Include data, statistics, and research findings",
            "Create comparison content with clear sources",
            "Use clear, factual language without marketing fluff",
            "Include author credentials and expertise",
            "Provide primary source links",
            "Update content regularly with new information",
        ]
