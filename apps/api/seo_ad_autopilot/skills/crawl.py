"""Crawling skills - delegates to real Playwright crawler."""

from __future__ import annotations

import time
from typing import Any

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


class SiteCrawlerSkill(Skill):
    """Site Crawler - crawls websites using the project's crawler module."""
    
    @property
    def name(self) -> str:
        return "SiteCrawler"
    
    @property
    def description(self) -> str:
        return "Crawl a website and extract page data, screenshots, and DOM snapshots"
    
    @property
    def category(self) -> SkillCategory:
        return SkillCategory.CRAWL
    
    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY
    
    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        
        url = skill_input.params.get("url", "")
        if not url:
            return self._create_output(
                success=False,
                error="URL is required",
            )
        
        try:
            from ..crawler import crawl_page_with_diagnostics
            
            diagnostics = crawl_page_with_diagnostics(url)
            
            result = {
                "url": url,
                "pages_crawled": 1 if diagnostics.get("snapshot") else 0,
                "title": diagnostics.get("snapshot", {}).get("title", ""),
                "description": diagnostics.get("snapshot", {}).get("description", ""),
                "headings": diagnostics.get("snapshot", {}).get("headings", []),
                "links": diagnostics.get("snapshot", {}).get("links", []),
                "images": diagnostics.get("snapshot", {}).get("images", []),
                "dom_snapshot": diagnostics.get("snapshot", {}).get("html", "")[:5000],
                "anti_bot": diagnostics.get("anti_bot", {}),
                "status": diagnostics.get("status", "unknown"),
            }
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return self._create_output(
                success=bool(diagnostics.get("snapshot")),
                result=result,
                execution_time_ms=execution_time,
            )
            
        except ImportError:
            return self._create_output(
                success=False,
                error="Crawler module not available. Ensure crawler.py is properly configured.",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            return self._create_output(
                success=False,
                error=f"Crawl failed: {str(e)}",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
    
    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to crawl"},
                "depth": {"type": "integer", "description": "Crawl depth", "default": 1},
                "take_screenshot": {"type": "boolean", "description": "Take screenshots", "default": True},
            },
            "required": ["url"],
        }
