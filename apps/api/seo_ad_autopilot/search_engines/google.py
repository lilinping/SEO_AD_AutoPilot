"""Google Search Engine implementation with real API integration."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .base import (
    SearchEngine,
    SearchEngineCategory,
    SearchEngineType,
    SearchQuery,
    SearchResult,
    SiteAnalysis,
)


class GoogleSearchEngine(SearchEngine):
    """Google search engine with real Custom Search API integration.
    
    Supports:
    - Google Custom Search API for organic results
    - Site performance analysis
    - SEO recommendations based on Google's guidelines
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        cx: Optional[str] = None,
    ):
        self._api_key = api_key or os.getenv("SEO_AD_BOT_GOOGLE_API_KEY", "")
        self._cx = cx or os.getenv("SEO_AD_BOT_GOOGLE_CX", "")
        self._base_url = "https://www.googleapis.com/customsearch/v1"
    
    @property
    def category(self) -> SearchEngineCategory:
        return SearchEngineCategory.GOOGLE
    
    @property
    def engine_type(self) -> SearchEngineType:
        return SearchEngineType.TRADITIONAL_SEO
    
    @property
    def name(self) -> str:
        return "Google"
    
    def is_available(self) -> bool:
        return bool(self._api_key and self._cx)
    
    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search Google using Custom Search API."""
        if not self.is_available():
            return []
        
        params = {
            "key": self._api_key,
            "cx": self._cx,
            "q": query.query,
            "num": 10,
        }
        
        if query.country:
            params["gl"] = query.country
        if query.language:
            params["hl"] = query.language
        
        try:
            url = f"{self._base_url}?{urlencode(params)}"
            request = Request(url, headers={"User-Agent": "SEO-AD-AutoPilot/1.0"})
            
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            results = []
            for i, item in enumerate(data.get("items", []), 1):
                result = SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    position=i,
                    engine=self.category,
                    features=self._extract_features(item),
                    metadata={
                        "displayLink": item.get("displayLink", ""),
                        "formattedUrl": item.get("formattedUrl", ""),
                    },
                )
                results.append(result)
            
            return results
        
        except (HTTPError, json.JSONDecodeError, Exception) as e:
            print(f"[Google] Search error: {e}")
            return []
    
    def _extract_features(self, item: dict[str, Any]) -> list[str]:
        """Extract search features from a result."""
        features = []
        
        if "richSnippet" in item:
            features.append("rich_snippet")
        if "pagemap" in item:
            if "metatags" in item["pagemap"]:
                features.append("meta_tags")
            if "cse_image" in item["pagemap"]:
                features.append("image")
        if "sitelinks" in item:
            features.append("sitelinks")
        
        return features
    
    def analyze_site(self, url: str) -> SiteAnalysis:
        """Analyze site performance on Google.
        
        This searches for the site URL and analyzes its presence.
        """
        query = SearchQuery(query=f"site:{url}")
        results = self.search(query)
        
        recommendations = self._generate_recommendations(url, results)
        
        return SiteAnalysis(
            url=url,
            rankings={self.category: results},
            geo_scores={self.category: self._calculate_score(results)},
            recommendations={self.category: recommendations},
        )
    
    def _calculate_score(self, results: list[SearchResult]) -> float:
        """Calculate a score based on search results."""
        if not results:
            return 0.0
        
        # Simple scoring: more results = better presence
        base_score = min(len(results) * 10, 50)
        
        # Bonus for sitelinks
        sitelink_count = sum(1 for r in results if "sitelinks" in r.features)
        base_score += sitelink_count * 5
        
        return min(base_score, 100.0)
    
    def _generate_recommendations(
        self, url: str, results: list[SearchResult]
    ) -> list[str]:
        """Generate SEO recommendations based on analysis."""
        recommendations = []
        
        if not results:
            recommendations.append("Site not indexed - submit to Google Search Console")
            recommendations.append("Create and submit XML sitemap")
            return recommendations
        
        # Check for common issues
        has_rich_snippets = any("rich_snippet" in r.features for r in results)
        if not has_rich_snippets:
            recommendations.append("Add structured data (Schema.org) for rich snippets")
        
        has_sitelinks = any("sitelinks" in r.features for r in results)
        if not has_sitelinks:
            recommendations.append("Improve site navigation for sitelinks")
            recommendations.append("Create clear internal linking structure")
        
        # Title tag analysis
        for result in results:
            if len(result.title) > 60:
                recommendations.append(f"Title too long ({len(result.title)} chars): {result.title[:50]}...")
                break
        
        # Meta description analysis
        for result in results:
            if len(result.snippet) > 160:
                recommendations.append("Meta description may be truncated")
                break
        
        # Standard Google SEO recommendations
        recommendations.extend([
            "Ensure mobile-friendly design (Mobile-First Indexing)",
            "Optimize Core Web Vitals (LCP, INP, CLS)",
            "Create high-quality, original content",
            "Build authoritative backlinks",
            "Use HTTPS across the site",
        ])
        
        return recommendations
    
    def get_seo_recommendations(self, url: str) -> list[str]:
        """Get comprehensive Google-specific SEO recommendations."""
        return [
            # Technical SEO
            "Submit XML sitemap to Google Search Console",
            "Ensure robots.txt allows crawling of important pages",
            "Implement canonical tags to avoid duplicate content",
            "Use hreflang tags for multi-language sites",
            "Fix any 404 errors or broken links",
            
            # On-page SEO
            "Write unique, descriptive title tags (50-60 chars)",
            "Create compelling meta descriptions (150-160 chars)",
            "Use proper heading hierarchy (H1-H6)",
            "Add alt text to all images",
            "Implement structured data (Schema.org)",
            
            # Content
            "Create high-quality, original content",
            "Focus on E-E-A-T (Experience, Expertise, Authority, Trust)",
            "Update content regularly for freshness",
            "Target relevant keywords naturally",
            
            # Technical
            "Ensure fast page loading (Core Web Vitals)",
            "Implement HTTPS across the site",
            "Make site mobile-friendly",
            "Use lazy loading for images",
            "Minimize render-blocking resources",
            
            # Links
            "Build high-quality backlinks",
            "Create internal linking structure",
            "Fix broken internal and external links",
            
            # Local SEO (if applicable)
            "Create Google Business Profile",
            "Ensure NAP consistency across the web",
            "Get local citations and reviews",
        ]
