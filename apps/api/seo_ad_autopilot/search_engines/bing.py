"""Bing Search Engine implementation with real API integration."""

from __future__ import annotations

import json
import os
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


class BingSearchEngine(SearchEngine):
    """Bing search engine with real Web Search API integration.
    
    Supports:
    - Bing Web Search API for organic results
    - Site performance analysis
    - Bing-specific SEO recommendations
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("SEO_AD_BOT_BING_API_KEY", "")
        self._base_url = "https://api.bing.microsoft.com/v7.0/search"
    
    @property
    def category(self) -> SearchEngineCategory:
        return SearchEngineCategory.BING
    
    @property
    def engine_type(self) -> SearchEngineType:
        return SearchEngineType.TRADITIONAL_SEO
    
    @property
    def name(self) -> str:
        return "Bing"
    
    def is_available(self) -> bool:
        return bool(self._api_key)
    
    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search Bing using Web Search API."""
        if not self.is_available():
            return []
        
        params = {
            "q": query.query,
            "count": 10,
            "offset": 0,
            "mkt": f"{query.language}-{query.country}".upper() if query.country else "en-US",
        }
        
        try:
            url = f"{self._base_url}?{urlencode(params)}"
            request = Request(
                url,
                headers={
                    "Ocp-Apim-Subscription-Key": self._api_key,
                    "User-Agent": "SEO-AD-AutoPilot/1.0",
                },
            )
            
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
            
            results = []
            web_pages = data.get("webPages", {}).get("value", [])
            
            for i, item in enumerate(web_pages, 1):
                result = SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    position=i,
                    engine=self.category,
                    features=self._extract_features(item),
                    metadata={
                        "dateLastCrawled": item.get("dateLastCrawled", ""),
                        "language": item.get("language", ""),
                    },
                )
                results.append(result)
            
            return results
        
        except (HTTPError, json.JSONDecodeError, Exception) as e:
            print(f"[Bing] Search error: {e}")
            return []
    
    def _extract_features(self, item: dict[str, Any]) -> list[str]:
        """Extract search features from a result."""
        features = []
        
        if "deepLinks" in item:
            features.append("sitelinks")
        if "dateLastCrawled" in item:
            features.append("recently_crawled")
        
        return features
    
    def analyze_site(self, url: str) -> SiteAnalysis:
        """Analyze site performance on Bing."""
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
        
        base_score = min(len(results) * 10, 50)
        
        sitelink_count = sum(1 for r in results if "sitelinks" in r.features)
        base_score += sitelink_count * 5
        
        return min(base_score, 100.0)
    
    def _generate_recommendations(
        self, url: str, results: list[SearchResult]
    ) -> list[str]:
        """Generate Bing-specific SEO recommendations."""
        recommendations = []
        
        if not results:
            recommendations.append("Site not indexed - submit to Bing Webmaster Tools")
            recommendations.append("Create and submit XML sitemap")
            return recommendations
        
        # Bing-specific recommendations
        has_sitelinks = any("sitelinks" in r.features for r in results)
        if not has_sitelinks:
            recommendations.append("Improve site structure for Bing deep links")
        
        recommendations.extend([
            "Register with Bing Webmaster Tools",
            "Submit XML sitemap to Bing",
            "Optimize for social signals (Bing values social media)",
            "Use Bing Places for local SEO",
            "Implement Bing-specific meta tags",
        ])
        
        return recommendations
    
    def get_seo_recommendations(self, url: str) -> list[str]:
        """Get comprehensive Bing-specific SEO recommendations."""
        return [
            # Bing Webmaster Tools
            "Register site with Bing Webmaster Tools",
            "Submit XML sitemap to Bing",
            "Use Bing URL Submission API for faster indexing",
            
            # Bing-specific ranking factors
            "Bing values exact-match domains more than Google",
            "Social signals (Facebook, Twitter) matter more for Bing",
            "Bing favors multimedia content (images, videos)",
            "Clear site structure with breadcrumbs helps Bing",
            "Authoritative backlinks are important for Bing",
            "Local SEO is important for Bing (Bing Places)",
            "Bing favors older, established domains",
            
            # Technical SEO
            "Ensure mobile-friendly design",
            "Optimize page load speed",
            "Use HTTPS across the site",
            "Implement structured data (Schema.org)",
            
            # Content
            "Create high-quality, original content",
            "Use clear, descriptive title tags",
            "Write compelling meta descriptions",
            "Include alt text for images",
            
            # Bing-specific features
            "Implement Bing-specific meta tags (msvalidate.01)",
            "Use Bing Places for local business",
            "Submit to Bing Shopping (if applicable)",
        ]
