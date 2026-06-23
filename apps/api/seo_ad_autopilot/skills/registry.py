"""Skill Registry - manages skill registration and discovery.

Inspired by OpenClaw's skill system.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import Skill, SkillCategory, SkillRiskLevel


class SkillRegistry:
    """Registry for managing skills."""
    
    def __init__(self):
        self._skills: dict[str, Skill] = {}
    
    def register(self, skill: Skill) -> None:
        """Register a skill."""
        self._skills[skill.skill_id] = skill
    
    def unregister(self, skill_id: str) -> None:
        """Unregister a skill."""
        if skill_id in self._skills:
            del self._skills[skill_id]
    
    def get(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID."""
        return self._skills.get(skill_id)
    
    def get_by_name(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        for skill in self._skills.values():
            if skill.name == name:
                return skill
        return None
    
    def get_all(self) -> list[Skill]:
        """Get all registered skills."""
        return list(self._skills.values())
    
    def get_by_category(self, category: SkillCategory) -> list[Skill]:
        """Get skills by category."""
        return [
            s for s in self._skills.values()
            if s.category == category
        ]
    
    def get_by_risk_level(self, risk_level: SkillRiskLevel) -> list[Skill]:
        """Get skills by risk level."""
        return [
            s for s in self._skills.values()
            if s.risk_level == risk_level
        ]
    
    def get_safe_skills(self) -> list[Skill]:
        """Get skills that don't require approval."""
        return [
            s for s in self._skills.values()
            if not s.requires_approval
        ]
    
    def search(self, query: str) -> list[Skill]:
        """Search skills by name or description."""
        query_lower = query.lower()
        return [
            s for s in self._skills.values()
            if query_lower in s.name.lower() or query_lower in s.description.lower()
        ]
    
    def get_skill_info(self, skill_id: str) -> dict[str, Any]:
        """Get detailed skill information."""
        skill = self.get(skill_id)
        if not skill:
            return {}
        
        return {
            "skill_id": skill.skill_id,
            "name": skill.name,
            "description": skill.description,
            "category": skill.category.value,
            "risk_level": skill.risk_level.value,
            "requires_approval": skill.requires_approval,
            "rollback_supported": skill.rollback_supported,
            "input_schema": skill.get_input_schema(),
            "output_schema": skill.get_output_schema(),
        }
    
    def list_skills_summary(self) -> list[dict[str, Any]]:
        """List all skills with summary info."""
        return [
            {
                "skill_id": s.skill_id,
                "name": s.name,
                "category": s.category.value,
                "risk_level": s.risk_level.value,
            }
            for s in self._skills.values()
        ]


def create_default_registry() -> SkillRegistry:
    """Create a registry with all default skills."""
    from .crawl import SiteCrawlerSkill
    from .analyze import StyleExtractorSkill, SiteAnalyzerSkill
    from .generate import ContentGeneratorSkill, SchemaBuilderSkill
    from .deploy import GitHubPRCreatorSkill, CMSPublisherSkill
    from .monitor import MetricsCollectorSkill, AlertManagerSkill
    from .amazon_ads_report import AmazonAdsReportSkill
    from .ecommerce_analysis import EcommerceAnalysisSkill
    from .keyword_research import KeywordResearchSkill
    from .real_data import (
        DataForKeywordResearchSkill,
        AhrefsSiteExplorerSkill,
        AhrefsKeywordExplorerSkill,
        AmazonAdsReporterSkill,
        AmazonAdsNodeReporterSkill,
    )
    from .web_scraper import WebScraperSkill, YouTubeTranscriptSkill, RSSFeedSkill
    
    registry = SkillRegistry()
    
    registry.register(SiteCrawlerSkill())
    registry.register(StyleExtractorSkill())
    registry.register(SiteAnalyzerSkill())
    registry.register(ContentGeneratorSkill())
    registry.register(SchemaBuilderSkill())
    registry.register(GitHubPRCreatorSkill())
    registry.register(CMSPublisherSkill())
    registry.register(MetricsCollectorSkill())
    registry.register(AlertManagerSkill())
    registry.register(AmazonAdsReportSkill())
    registry.register(EcommerceAnalysisSkill())
    registry.register(KeywordResearchSkill())
    registry.register(DataForKeywordResearchSkill())
    registry.register(AhrefsSiteExplorerSkill())
    registry.register(AhrefsKeywordExplorerSkill())
    registry.register(AmazonAdsReporterSkill())
    registry.register(AmazonAdsNodeReporterSkill())
    registry.register(WebScraperSkill())
    registry.register(YouTubeTranscriptSkill())
    registry.register(RSSFeedSkill())
    
    return registry
