"""Deployment skills - delegates to real connector gateway."""

from __future__ import annotations

import time
from typing import Any

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


class GitHubPRCreatorSkill(Skill):
    """GitHub PR Creator - creates pull requests via real GitHub API."""
    
    @property
    def name(self) -> str:
        return "GitHubPRCreator"
    
    @property
    def description(self) -> str:
        return "Create GitHub pull requests with SEO/GEO improvements"
    
    @property
    def category(self) -> SkillCategory:
        return SkillCategory.DEPLOY
    
    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.HIGH
    
    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        
        repo = skill_input.params.get("repo", "")
        changes = skill_input.params.get("changes", [])
        
        if not repo:
            return self._create_output(
                success=False,
                error="Repository is required",
            )
        
        try:
            from ..connectors import ConnectorGateway
            
            gateway = ConnectorGateway()
            result_data = gateway.create_github_pr(
                repo=repo,
                changes=changes,
                title=skill_input.params.get("title", "SEO/AD AutoPilot improvements"),
                body=skill_input.params.get("body", "Automated SEO improvements from AutoPilot"),
                branch=skill_input.params.get("branch", "autopilot/seo-improvements"),
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return self._create_output(
                success=result_data.get("success", False),
                result=result_data,
                error=result_data.get("error"),
                execution_time_ms=execution_time,
            )
            
        except Exception as e:
            return self._create_output(
                success=False,
                error=f"GitHub PR creation failed: {str(e)}. Ensure GitHub credentials are configured.",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
    
    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "GitHub repository (owner/repo)"},
                "branch": {"type": "string", "description": "Branch name", "default": "main"},
                "changes": {"type": "array", "description": "List of file changes"},
                "title": {"type": "string", "description": "PR title"},
                "body": {"type": "string", "description": "PR description"},
            },
            "required": ["repo", "changes"],
        }


class CMSPublisherSkill(Skill):
    """CMS Publisher - publishes content via real CMS connector."""
    
    @property
    def name(self) -> str:
        return "CMSPublisher"
    
    @property
    def description(self) -> str:
        return "Publish content to WordPress, Shopify, or other CMS platforms"
    
    @property
    def category(self) -> SkillCategory:
        return SkillCategory.DEPLOY
    
    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.HIGH
    
    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        
        cms_type = skill_input.params.get("cms_type", "wordpress")
        content = skill_input.params.get("content", {})
        
        try:
            from ..connectors import ConnectorGateway
            
            gateway = ConnectorGateway()
            result_data = gateway.publish_to_cms(
                cms_type=cms_type,
                content=content,
                publish_as=skill_input.params.get("publish_as", "draft"),
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return self._create_output(
                success=result_data.get("success", False),
                result=result_data,
                error=result_data.get("error"),
                execution_time_ms=execution_time,
            )
            
        except Exception as e:
            return self._create_output(
                success=False,
                error=f"CMS publishing failed: {str(e)}. Ensure CMS credentials are configured.",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
    
    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "cms_type": {"type": "string", "enum": ["wordpress", "shopify", "webflow"], "description": "CMS type"},
                "content": {"type": "object", "description": "Content to publish"},
                "publish_as": {"type": "string", "enum": ["draft", "published"], "default": "draft"},
            },
            "required": ["cms_type", "content"],
        }
