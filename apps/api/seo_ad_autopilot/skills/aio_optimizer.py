"""AIO Optimizer Skills — LLM.txt 生成 / E-E-A-T 强化 / AI 引用追踪.

包含三个 Skill:
- LLMTxtGeneratorSkill    生成 /llm.txt 文件内容
- EEATEnhancerSkill       生成 E-E-A-T 强化补丁 (Schema + 作者信息)
- AIOCitationTrackerSkill 追踪品牌/页面在 AI 引擎中的引用率
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


# ═══════════════════════════════════════════════════════════════════
# 1. LLMTxtGeneratorSkill
# ═══════════════════════════════════════════════════════════════════

class LLMTxtGeneratorSkill(Skill):
    """生成符合 llm.txt 标准的文件内容，引导 AI 爬虫了解站点范围和限制."""

    @property
    def name(self) -> str:
        return "LLMTxtGenerator"

    @property
    def description(self) -> str:
        return (
            "Generate /llm.txt content that guides AI crawlers (GPTBot, ClaudeBot, "
            "PerplexityBot, Google-Extended) on site scope, allowed content, "
            "and usage restrictions. Based on 2025/2026 llm.txt standard."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.GENERATE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.LOW

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        t0     = time.time()
        params = skill_input.params

        url         = params.get("url", "")
        brand       = params.get("brand", "")
        description = params.get("description", "")
        allow_training   = params.get("allow_training", True)
        allow_rag        = params.get("allow_rag", True)
        disallow_paths   = params.get("disallow_paths", ["/admin", "/private", "/wp-admin"])
        contact_email    = params.get("contact_email", "")
        license_url      = params.get("license_url", "")
        sections         = params.get("sections", {})   # optional content map

        if not url:
            return self._create_output(
                success=False, error="url is required", execution_time_ms=0
            )

        # ── Build llm.txt content ──────────────────────────────────────────
        lines: list[str] = []

        # Header block
        lines.append(f"# {brand or url}")
        if description:
            lines.append(f"> {description}")
        lines.append("")

        # Site information
        lines.append("## Site Information")
        lines.append(f"- URL: {url}")
        if brand:
            lines.append(f"- Brand: {brand}")
        lines.append("")

        # AI Usage Policy
        lines.append("## AI Usage Policy")
        lines.append(
            f"- Training: {'Allowed' if allow_training else 'Not Allowed'}"
        )
        lines.append(
            f"- RAG / Retrieval: {'Allowed' if allow_rag else 'Not Allowed'}"
        )
        lines.append("- Citation: Allowed (attribution required)")
        lines.append("- Summarization: Allowed")
        if license_url:
            lines.append(f"- License: {license_url}")
        lines.append("")

        # Disallowed paths
        if disallow_paths:
            lines.append("## Disallowed Paths")
            for path in disallow_paths:
                lines.append(f"- {path}")
            lines.append("")

        # Content sections / site map summary
        if sections:
            lines.append("## Content Sections")
            for section, desc in sections.items():
                lines.append(f"- [{section}]({url}/{section}): {desc}")
            lines.append("")

        # Contact
        if contact_email:
            lines.append("## Contact")
            lines.append(f"- AI/Licensing inquiries: {contact_email}")
            lines.append("")

        # Standard footer note
        lines.append("## Notes")
        lines.append(
            "This file follows the llm.txt standard (https://llmstxt.org). "
            "Please respect these guidelines when using this content."
        )

        content_str = "\n".join(lines)

        # ── Build ai.txt (Spawning.ai standard) ───────────────────────────
        ai_txt_lines = [
            "# ai.txt — Training Data Consent",
            f"# Site: {url}",
            "",
            f"User-agent: *",
            f"Allow: {'/' if allow_training else ''}",
        ]
        if not allow_training:
            ai_txt_lines.append("Disallow: /")
        for path in disallow_paths:
            ai_txt_lines.append(f"Disallow: {path}")
        ai_txt_str = "\n".join(ai_txt_lines)

        ms = int((time.time() - t0) * 1000)
        return self._create_output(
            success=True,
            result={
                "llm_txt_content": content_str,
                "ai_txt_content":  ai_txt_str,
                "deploy_paths": {
                    "llm_txt": "/llm.txt",
                    "ai_txt":  "/ai.txt",
                },
                "estimated_aio_score_lift": "+15–20 AIO crawlability points",
                "word_count": len(content_str.split()),
            },
            execution_time_ms=ms,
        )


# ═══════════════════════════════════════════════════════════════════
# 2. EEATEnhancerSkill
# ═══════════════════════════════════════════════════════════════════

class EEATEnhancerSkill(Skill):
    """生成 E-E-A-T 强化补丁: Author Schema / Organization Schema / FAQ Schema."""

    @property
    def name(self) -> str:
        return "EEATEnhancer"

    @property
    def description(self) -> str:
        return (
            "Generate E-E-A-T enhancement patches: structured Author schema with "
            "credentials and social profiles, Organization schema with Wikipedia "
            "sameAs links, and FAQPage schema for answer-format optimization."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.GENERATE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.LOW

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        t0     = time.time()
        params = skill_input.params

        url            = params.get("url", "")
        author_name    = params.get("author_name", "")
        author_title   = params.get("author_title", "")
        author_url     = params.get("author_url", "")
        author_twitter = params.get("author_twitter", "")
        author_linkedin= params.get("author_linkedin", "")
        org_name       = params.get("org_name", "")
        org_url        = params.get("org_url", url)
        org_logo       = params.get("org_logo", "")
        org_wiki       = params.get("org_wikipedia", "")
        org_wikidata   = params.get("org_wikidata", "")
        faq_items      = params.get("faq_items", [])   # [{q, a}]
        published      = params.get("published_date", "")
        modified       = params.get("modified_date", "")

        patches: dict[str, Any] = {}

        # ── Author Schema ─────────────────────────────────────────────────
        if author_name:
            author_schema: dict[str, Any] = {
                "@context": "https://schema.org",
                "@type":    "Person",
                "name":     author_name,
            }
            if author_title:   author_schema["jobTitle"]  = author_title
            if author_url:     author_schema["url"]        = author_url
            same_as = []
            if author_twitter:  same_as.append(f"https://twitter.com/{author_twitter.lstrip('@')}")
            if author_linkedin: same_as.append(author_linkedin)
            if same_as:         author_schema["sameAs"]   = same_as
            patches["author_schema"] = author_schema

        # ── Organization Schema ───────────────────────────────────────────
        if org_name:
            org_schema: dict[str, Any] = {
                "@context": "https://schema.org",
                "@type":    "Organization",
                "name":     org_name,
                "url":      org_url,
            }
            if org_logo:
                org_schema["logo"] = {"@type": "ImageObject", "url": org_logo}
            same_as_org = []
            if org_wiki:     same_as_org.append(org_wiki)
            if org_wikidata: same_as_org.append(org_wikidata)
            if same_as_org:  org_schema["sameAs"] = same_as_org
            patches["org_schema"] = org_schema

        # ── Article Schema (freshness) ────────────────────────────────────
        if published or modified:
            art_schema: dict[str, Any] = {
                "@context": "https://schema.org",
                "@type":    "Article",
                "url":      url,
            }
            if published: art_schema["datePublished"] = published
            if modified:  art_schema["dateModified"]  = modified
            if author_name:
                art_schema["author"] = {"@type": "Person", "name": author_name}
            patches["article_schema"] = art_schema

        # ── FAQPage Schema ────────────────────────────────────────────────
        if faq_items:
            faq_schema = {
                "@context":   "https://schema.org",
                "@type":      "FAQPage",
                "mainEntity": [
                    {
                        "@type":          "Question",
                        "name":           item.get("q", ""),
                        "acceptedAnswer": {
                            "@type": "Answer",
                            "text":  item.get("a", ""),
                        },
                    }
                    for item in faq_items
                ],
            }
            patches["faq_schema"] = faq_schema

        # ── Generate HTML snippets ────────────────────────────────────────
        html_snippets: dict[str, str] = {}
        for key, schema in patches.items():
            html_snippets[key] = (
                f'<script type="application/ld+json">\n'
                f'{json.dumps(schema, indent=2, ensure_ascii=False)}\n'
                f'</script>'
            )

        # ── Score improvement estimate ────────────────────────────────────
        est_gain = 0
        if "author_schema"   in patches: est_gain += 15
        if "org_schema"      in patches: est_gain += 12
        if "faq_schema"      in patches: est_gain += 18
        if "article_schema"  in patches: est_gain += 8

        ms = int((time.time() - t0) * 1000)
        return self._create_output(
            success=True,
            result={
                "patches":                  patches,
                "html_snippets":            html_snippets,
                "patches_count":            len(patches),
                "estimated_eeat_gain":      f"+{est_gain} E-E-A-T score points",
                "estimated_answer_gain":    "+15–20 answer format score points" if "faq_schema" in patches else "0",
                "deployment_instructions": (
                    "Add each HTML snippet to the <head> section of the target page. "
                    "For FAQPage, ensure FAQ content matches the schema exactly."
                ),
            },
            execution_time_ms=ms,
        )


# ═══════════════════════════════════════════════════════════════════
# 3. AIOCitationTrackerSkill
# ═══════════════════════════════════════════════════════════════════

class AIOCitationTrackerSkill(Skill):
    """追踪品牌/页面在 ChatGPT / Perplexity / Google AI Overviews 中的引用率."""

    # AI engines to check
    AI_ENGINES = ["chatgpt", "perplexity", "google_aio", "claude", "bing_copilot"]

    @property
    def name(self) -> str:
        return "AIOCitationTracker"

    @property
    def description(self) -> str:
        return (
            "Track brand and URL citation rates across AI-powered search engines "
            "(ChatGPT, Perplexity, Google AI Overviews, Claude). "
            "Establishes baseline and detects citation changes over time."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.MONITOR

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        t0     = time.time()
        params = skill_input.params

        url            = params.get("url", "")
        brand          = params.get("brand", url)
        target_queries = params.get("target_queries", [])
        prev_snapshot  = params.get("previous_snapshot", {})

        if not url:
            return self._create_output(
                success=False, error="url is required", execution_time_ms=0
            )

        citation_data = skill_input.context.get("ai_citation_data", {})

        results: dict[str, Any] = {}
        for engine in self.AI_ENGINES:
            engine_data = citation_data.get(engine, {})
            cited_queries = [
                q for q in target_queries
                if engine_data.get(q, {}).get("cited", False)
            ]
            citation_rate = (
                len(cited_queries) / len(target_queries)
                if target_queries else 0.0
            )
            prev_rate = prev_snapshot.get(engine, {}).get("citation_rate", 0.0)
            results[engine] = {
                "citation_rate":     round(citation_rate, 3),
                "citation_rate_pct": f"{citation_rate:.1%}",
                "cited_queries":     cited_queries,
                "total_queries":     len(target_queries),
                "delta_vs_prev":     round(citation_rate - prev_rate, 3),
                "trend":             (
                    "improving" if citation_rate > prev_rate else
                    "declining" if citation_rate < prev_rate else
                    "stable"
                ),
            }

        # Overall citation score
        all_rates = [r["citation_rate"] for r in results.values()]
        overall   = round(sum(all_rates) / len(all_rates), 3) if all_rates else 0.0

        # Identify best and worst engines
        best  = max(results, key=lambda e: results[e]["citation_rate"])
        worst = min(results, key=lambda e: results[e]["citation_rate"])

        recommendations: list[str] = []
        if overall < 0.2:
            recommendations.append(
                "Critical: <20% citation rate. Prioritize E-E-A-T signals, "
                "FAQ schema, and authority links to improve AI discoverability."
            )
        if results.get("google_aio", {}).get("citation_rate", 0) < 0.15:
            recommendations.append(
                "Google AIO visibility low — add structured FAQ + HowTo schema, "
                "ensure content directly answers target queries."
            )
        if results.get("chatgpt", {}).get("citation_rate", 0) < 0.10:
            recommendations.append(
                "ChatGPT citation low — add authoritative external links, "
                "factual statistics, and clear author credentials."
            )

        ms = int((time.time() - t0) * 1000)
        return self._create_output(
            success=True,
            result={
                "url":                url,
                "brand":              brand,
                "overall_citation_rate": overall,
                "overall_citation_pct":  f"{overall:.1%}",
                "engine_results":     results,
                "best_engine":        best,
                "worst_engine":       worst,
                "recommendations":    recommendations,
                "tracked_queries":    len(target_queries),
                "next_check_hours":   24,
            },
            execution_time_ms=ms,
        )
