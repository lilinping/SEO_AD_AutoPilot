from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

from .config import get_settings
from .models import SkillDefinition, WorkspacePolicy


class SkillRegistry:
    def __init__(self, skills: list[SkillDefinition]):
        self._skills = skills
        self._by_id = {skill.skill_id: skill for skill in skills}

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "SkillRegistry":
        registry_path = path or get_settings().skill_registry_path
        if registry_path.exists():
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
            skills = [SkillDefinition.model_validate(entry) for entry in payload.get("skills", [])]
            if skills:
                return cls(skills)
        return cls(cls._builtin_skills())

    @staticmethod
    def _builtin_skills() -> list[SkillDefinition]:
        entries = [
            {
                "skill_id": "read/site-sniffer",
                "suite": "read",
                "name": "Site Sniffer",
                "description": "Classify a site and extract surface signals.",
            },
            {
                "skill_id": "read/page-snapshotter",
                "suite": "read",
                "name": "Page Snapshotter",
                "description": "Capture page metadata and DOM-level evidence.",
            },
            {
                "skill_id": "seo/style-extractor",
                "suite": "seo",
                "name": "Style Extractor",
                "description": "Derive a content style profile.",
            },
            {
                "skill_id": "seo/content-opportunity-finder",
                "suite": "seo",
                "name": "Content Opportunity Finder",
                "description": "Identify high-value SEO opportunities.",
            },
            {
                "skill_id": "seo/adaptive-component-generator",
                "suite": "seo",
                "name": "Adaptive Component Generator",
                "description": "Generate page modules that improve intent match.",
            },
            {
                "skill_id": "seo/technical-seo-patcher",
                "suite": "seo",
                "name": "Technical SEO Patcher",
                "description": "Patch metadata, canonical tags, and structured data.",
            },
            {
                "skill_id": "seo/schema-builder",
                "suite": "seo",
                "name": "Schema Builder",
                "description": "Author safe schema markup.",
            },
            {
                "skill_id": "seo/internal-link-builder",
                "suite": "seo",
                "name": "Internal Link Builder",
                "description": "Strengthen authority flow and discovery.",
            },
            {
                "skill_id": "ad/ad-slot-auditor",
                "suite": "ad",
                "name": "Ad Slot Auditor",
                "description": "Evaluate page locations for safe ad inventory.",
            },
            {
                "skill_id": "ad/provider-integrator",
                "suite": "ad",
                "name": "Provider Integrator",
                "description": "Match safe ad providers and sponsorship templates.",
            },
            {
                "skill_id": "ad/ad-wrapper-renderer",
                "suite": "ad",
                "name": "Ad Wrapper Renderer",
                "description": "Render compliant ad containers.",
            },
            {
                "skill_id": "ad/ad-telemetry-binder",
                "suite": "ad",
                "name": "Ad Telemetry Binder",
                "description": "Attach telemetry hooks for ad viewability.",
            },
            {
                "skill_id": "deploy/github-pr-creator",
                "suite": "deploy",
                "name": "GitHub PR Creator",
                "description": "Package a plan into a pull request.",
            },
            {
                "skill_id": "deploy/cms-plugin-applier",
                "suite": "deploy",
                "name": "CMS Plugin Applier",
                "description": "Apply approved content changes to a CMS draft.",
            },
            {
                "skill_id": "deploy/universal-script-injector",
                "suite": "deploy",
                "name": "Universal Script Injector",
                "description": "Package an approved script for insertion.",
            },
            {
                "skill_id": "deploy/rollback-executor",
                "suite": "deploy",
                "name": "Rollback Executor",
                "description": "Generate and execute a safe reversal path.",
            },
            {
                "skill_id": "observe/monitoring-binder",
                "suite": "observe",
                "name": "Monitoring Binder",
                "description": "Attach post-deploy metrics and health checks.",
            },
            {
                "skill_id": "observe/alert-router",
                "suite": "observe",
                "name": "Alert Router",
                "description": "Route alerts when metrics deteriorate or rollback is required.",
            },
            {
                "skill_id": "seo/dataforseo-keyword-research",
                "suite": "seo",
                "name": "DataForSEO Keyword Research",
                "description": "Real keyword data via DataForSEO API: search volume, CPC, competition, suggestions, SERP, trends.",
            },
            {
                "skill_id": "seo/ahrefs-site-explorer",
                "suite": "seo",
                "name": "Ahrefs Site Explorer",
                "description": "Real SEO data via Ahrefs API: domain rating, traffic, backlinks, top pages, keywords.",
            },
            {
                "skill_id": "seo/ahrefs-keyword-explorer",
                "suite": "seo",
                "name": "Ahrefs Keyword Explorer",
                "description": "Real keyword data via Ahrefs API: volume, difficulty, CPC, SERP, related keywords.",
            },
            {
                "skill_id": "ecommerce/amazon-ads-reporter-v2",
                "suite": "ecommerce",
                "name": "Amazon Ads Reporter (Python)",
                "description": "Real Amazon Ads SP/SB/SD reports via linkfox-amazon-ads-report scripts.",
            },
            {
                "skill_id": "ecommerce/amazon-ads-node-reporter",
                "suite": "ecommerce",
                "name": "Amazon Ads Node Reporter",
                "description": "Lightweight Amazon Ads campaign/keyword reports via Node.js scripts.",
            },
        ]
        skill_map = {
            "read/site-sniffer": dict(is_destructive=False, required_approval=False, rollback_supported=False),
            "read/page-snapshotter": dict(is_destructive=False, required_approval=False, rollback_supported=False),
            "seo/style-extractor": dict(is_destructive=False, required_approval=True, rollback_supported=False),
            "seo/content-opportunity-finder": dict(is_destructive=False, required_approval=True, rollback_supported=False),
            "seo/adaptive-component-generator": dict(is_destructive=False, required_approval=True, rollback_supported=True),
            "seo/technical-seo-patcher": dict(is_destructive=True, required_approval=True, rollback_supported=True),
            "seo/schema-builder": dict(is_destructive=False, required_approval=True, rollback_supported=True),
            "seo/internal-link-builder": dict(is_destructive=False, required_approval=True, rollback_supported=True),
            "ad/ad-slot-auditor": dict(is_destructive=False, required_approval=True, rollback_supported=False),
            "ad/provider-integrator": dict(is_destructive=False, required_approval=True, rollback_supported=True),
            "ad/ad-wrapper-renderer": dict(is_destructive=True, required_approval=True, rollback_supported=True),
            "ad/ad-telemetry-binder": dict(is_destructive=False, required_approval=True, rollback_supported=True),
            "deploy/github-pr-creator": dict(is_destructive=True, required_approval=True, rollback_supported=True),
            "deploy/cms-plugin-applier": dict(is_destructive=True, required_approval=True, rollback_supported=True),
            "deploy/universal-script-injector": dict(is_destructive=True, required_approval=True, rollback_supported=True),
            "deploy/rollback-executor": dict(is_destructive=True, required_approval=True, rollback_supported=True),
            "observe/monitoring-binder": dict(is_destructive=False, required_approval=False, rollback_supported=False),
            "observe/alert-router": dict(is_destructive=False, required_approval=False, rollback_supported=False),
            "seo/dataforseo-keyword-research": dict(is_destructive=False, required_approval=False, rollback_supported=False),
            "seo/ahrefs-site-explorer": dict(is_destructive=False, required_approval=False, rollback_supported=False),
            "seo/ahrefs-keyword-explorer": dict(is_destructive=False, required_approval=False, rollback_supported=False),
            "ecommerce/amazon-ads-reporter-v2": dict(is_destructive=False, required_approval=False, rollback_supported=False),
            "ecommerce/amazon-ads-node-reporter": dict(is_destructive=False, required_approval=False, rollback_supported=False),
        }
        skills: list[SkillDefinition] = []
        for entry in entries:
            meta = skill_map[entry["skill_id"]]
            skills.append(
                SkillDefinition(
                    skill_id=entry["skill_id"],
                    suite=entry["suite"],
                    name=entry["name"],
                    description=entry["description"],
                    parameters={
                        "type": "object",
                        "required": ["site_profile"],
                        "properties": {"site_profile": {"type": "object"}},
                    },
                    is_destructive=meta["is_destructive"],
                    required_approval=meta["required_approval"],
                    rollback_supported=meta["rollback_supported"],
                    observability={"events": ["start", "finish", "error"], "fields": ["latency_ms"]},
                    failure_contract="Return a safe no-op and explain the missing signal.",
                )
            )
        return skills

    @property
    def skills(self) -> list[SkillDefinition]:
        return list(self._skills)

    def get(self, skill_id: str) -> Optional[SkillDefinition]:
        return self._by_id.get(skill_id)

    def by_suite(self, suite: str) -> list[SkillDefinition]:
        return [skill for skill in self._skills if skill.suite == suite]

    def as_policy(self) -> WorkspacePolicy:
        return WorkspacePolicy()

    def required_skill_ids(self) -> list[str]:
        return [skill.skill_id for skill in self._skills]


@lru_cache(maxsize=1)
def get_skill_registry() -> SkillRegistry:
    return SkillRegistry.load()
