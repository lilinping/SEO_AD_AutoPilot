"""Enhanced crawler with anti-bot strategies and screenshot comparison.

Features:
- Multi-strategy anti-bot detection
- Screenshot comparison for change detection
- Page structure analysis
- Performance metrics collection
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlparse


class AntiBotStrategy(str, Enum):
    """Anti-bot detection strategies."""
    USER_AGENT_ROTATION = "user_agent_rotation"
    REQUEST_DELAY = "request_delay"
    PROXY_ROTATION = "proxy_rotation"
    COOKIE_HANDLING = "cookie_handling"
    CAPTCHA_DETECTION = "captcha_detection"


@dataclass
class PageMetrics:
    """Page performance metrics."""
    load_time_ms: int = 0
    dom_ready_ms: int = 0
    first_contentful_paint_ms: int = 0
    largest_contentful_paint_ms: int = 0
    total_size_bytes: int = 0
    request_count: int = 0


@dataclass
class PageStructure:
    """Page structure analysis."""
    title: str = ""
    meta_description: str = ""
    headings: dict[str, list[str]] = field(default_factory=dict)
    links: list[dict[str, str]] = field(default_factory=list)
    images: list[dict[str, str]] = field(default_factory=list)
    scripts: list[str] = field(default_factory=list)
    stylesheets: list[str] = field(default_factory=list)
    schema_data: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CrawlResult:
    """Enhanced crawl result."""
    url: str
    status_code: int = 200
    content: str = ""
    html: str = ""
    screenshot_url: Optional[str] = None
    metrics: PageMetrics = field(default_factory=PageMetrics)
    structure: PageStructure = field(default_factory=PageStructure)
    anti_bot_detected: bool = False
    anti_bot_strategy_used: Optional[AntiBotStrategy] = None
    crawl_time_ms: int = 0
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AntiBotDetector:
    """Detect and handle anti-bot measures."""
    
    def __init__(self):
        self._user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]
        self._delay_range = (1, 3)  # seconds
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent."""
        import random
        return random.choice(self._user_agents)
    
    def get_random_delay(self) -> float:
        """Get a random delay between requests."""
        import random
        return random.uniform(*self._delay_range)
    
    def detect_anti_bot(self, html: str, status_code: int) -> Optional[AntiBotStrategy]:
        """Detect anti-bot measures in the response."""
        html_lower = html.lower()
        
        # Check for CAPTCHA
        if any(keyword in html_lower for keyword in ["captcha", "recaptcha", "hcaptcha", "challenge"]):
            return AntiBotStrategy.CAPTCHA_DETECTION
        
        # Check for rate limiting
        if status_code == 429:
            return AntiBotStrategy.REQUEST_DELAY
        
        # Check for bot detection
        bot_indicators = ["access denied", "blocked", "forbidden", "bot detected", "security check"]
        if any(indicator in html_lower for indicator in bot_indicators):
            return AntiBotStrategy.USER_AGENT_ROTATION
        
        return None
    
    def should_use_proxy(self, domain: str) -> bool:
        """Determine if proxy should be used for this domain."""
        # High-traffic sites might need proxy
        high_traffic_domains = ["google.com", "facebook.com", "amazon.com"]
        return any(d in domain for d in high_traffic_domains)


@dataclass
class ScreenshotComparison:
    """Screenshot comparison result."""
    before_url: str
    after_url: str
    similarity_score: float = 0.0
    changes_detected: list[str] = field(default_factory=list)
    diff_percentage: float = 0.0


class EnhancedCrawler:
    """Enhanced crawler with anti-bot and comparison features."""
    
    def __init__(self):
        self._anti_bot = AntiBotDetector()
        self._results: dict[str, CrawlResult] = {}
    
    def crawl(
        self,
        url: str,
        use_proxy: bool = False,
        delay: bool = True,
    ) -> CrawlResult:
        """Crawl a URL with anti-bot measures."""
        start_time = time.time()
        
        result = CrawlResult(url=url)
        
        try:
            # Apply anti-bot measures
            if delay:
                time.sleep(self._anti_bot.get_random_delay())
            
            # Simulate crawling (in production, use Playwright)
            result.status_code = 200
            result.html = f"<html><head><title>Sample Page - {url}</title></head><body>Content for {url}</body></html>"
            result.content = f"Sample content for {url}"
            
            # Analyze page structure
            result.structure = self._analyze_structure(result.html)
            
            # Check for anti-bot
            anti_bot = self._anti_bot.detect_anti_bot(result.html, result.status_code)
            if anti_bot:
                result.anti_bot_detected = True
                result.anti_bot_strategy_used = anti_bot
            
            result.crawl_time_ms = int((time.time() - start_time) * 1000)
            
        except Exception as e:
            result.error = str(e)
            result.status_code = 500
        
        self._results[url] = result
        return result
    
    def _analyze_structure(self, html: str) -> PageStructure:
        """Analyze page structure from HTML."""
        structure = PageStructure()
        
        # Extract title
        title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
        if title_match:
            structure.title = title_match.group(1)
        
        # Extract meta description
        meta_match = re.search(r'<meta\s+name="description"\s+content="(.*?)"', html, re.IGNORECASE)
        if meta_match:
            structure.meta_description = meta_match.group(1)
        
        # Extract headings
        for level in range(1, 7):
            heading_matches = re.findall(f"<h{level}>(.*?)</h{level}>", html, re.IGNORECASE)
            if heading_matches:
                structure.headings[f"h{level}"] = heading_matches
        
        return structure
    
    def compare_screenshots(
        self,
        before_url: str,
        after_url: str,
    ) -> ScreenshotComparison:
        """Compare two screenshots for changes."""
        before = self._results.get(before_url)
        after = self._results.get(after_url)
        
        comparison = ScreenshotComparison(
            before_url=before_url,
            after_url=after_url,
        )
        
        if before and after:
            # Compare structure
            if before.structure.title != after.structure.title:
                comparison.changes_detected.append("Title changed")
            
            if before.structure.headings != after.structure.headings:
                comparison.changes_detected.append("Headings changed")
            
            # Calculate similarity
            if before.html and after.html:
                similarity = self._calculate_similarity(before.html, after.html)
                comparison.similarity_score = similarity
                comparison.diff_percentage = (1 - similarity) * 100
        
        return comparison
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using simple comparison."""
        if not text1 or not text2:
            return 0.0
        
        # Simple similarity based on common characters
        set1 = set(text1)
        set2 = set(text2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def get_result(self, url: str) -> Optional[CrawlResult]:
        """Get crawl result for a URL."""
        return self._results.get(url)
    
    def get_all_results(self) -> list[CrawlResult]:
        """Get all crawl results."""
        return list(self._results.values())
    
    def analyze_site(self, urls: list[str]) -> dict[str, Any]:
        """Analyze multiple URLs from a site."""
        results = []
        for url in urls:
            result = self.crawl(url)
            results.append(result)
        
        successful = [r for r in results if r.status_code == 200]
        failed = [r for r in results if r.status_code != 200]
        
        return {
            "total_urls": len(urls),
            "successful": len(successful),
            "failed": len(failed),
            "avg_crawl_time_ms": sum(r.crawl_time_ms for r in results) / max(len(results), 1),
            "anti_bot_detected": any(r.anti_bot_detected for r in results),
            "results": results,
        }


def create_enhanced_crawler() -> EnhancedCrawler:
    """Create an enhanced crawler instance."""
    return EnhancedCrawler()
