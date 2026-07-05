"""Competitor Analysis Skills — keyword gap + content structural benchmarking.

包含两个 Skill:
- CompetitorKeywordGapSkill  发现竞品排名但我们没有的词，附优先级评分
- ContentGapAnalysisSkill    内容深度/结构/Schema/字数差距全面对比
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


# ═══════════════════════════════════════════════════════════════════
# 1. CompetitorKeywordGapSkill
# ═══════════════════════════════════════════════════════════════════

class CompetitorKeywordGapSkill(Skill):
    """发现竞品排名但我们没有排名的词，并附带优先级评分."""

    @property
    def name(self) -> str:
        return "CompetitorKeywordGap"

    @property
    def description(self) -> str:
        return (
            "Identify keywords that competitors rank for but we do not. "
            "Scores gaps by competitor count × difficulty and surfaces quick-win, "
            "mid-term, and long-term keyword opportunities with recommended page targets."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ANALYZE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        t0     = time.time()
        params = skill_input.params
        ctx    = skill_input.context

        our_keywords = set(params.get("our_keywords", []))
        our_ranks    = ctx.get("our_rank_history", {})     # {kw: [{position}]}
        comp_data    = ctx.get("competitor_data", {})       # {domain: {keywords:[], keyword_positions:{kw:pos}}}
        max_results  = params.get("max_results", 50)

        if not comp_data:
            return self._create_output(
                success=False,
                error="competitor_data is required in context",
                execution_time_ms=0,
            )

        # ── Pure gap keywords (we have no ranking) ────────────────────────
        gap_map: dict[str, list[dict]] = {}
        for domain, data in comp_data.items():
            kw_positions = data.get("keyword_positions", {})
            for kw, pos in kw_positions.items():
                if kw not in our_keywords and kw not in our_ranks:
                    gap_map.setdefault(kw, []).append({"domain": domain, "position": pos})

        gap_items: list[dict] = []
        for kw, sources in gap_map.items():
            avg_pos = sum(s["position"] for s in sources) / len(sources)
            # Priority = number of competitors × (100 - avg position) proxy
            priority_score = len(sources) * max(0, 101 - avg_pos)
            difficulty = (
                "low"    if avg_pos <= 10 else
                "medium" if avg_pos <= 30 else
                "high"
            )
            gap_items.append({
                "keyword":             kw,
                "competitor_count":    len(sources),
                "competitor_avg_rank": round(avg_pos, 1),
                "difficulty":          difficulty,
                "priority_score":      round(priority_score, 1),
                "sources":             sources,
                "recommendation": (
                    "quick_win"   if avg_pos <= 10 and len(sources) >= 2 else
                    "mid_term"    if avg_pos <= 30 else
                    "long_term"
                ),
            })

        top_gaps = sorted(gap_items, key=lambda x: -x["priority_score"])[:max_results]

        # ── Shared keywords where competitors rank better ─────────────────
        shared_gaps: list[dict] = []
        for kw, hist in our_ranks.items():
            if not hist:
                continue
            our_pos = hist[-1].get("position", 999)
            for domain, data in comp_data.items():
                comp_pos = data.get("keyword_positions", {}).get(kw, 999)
                if comp_pos < our_pos - 5:
                    shared_gaps.append({
                        "keyword":      kw,
                        "our_rank":     our_pos,
                        "their_rank":   comp_pos,
                        "gap":          our_pos - comp_pos,
                        "competitor":   domain,
                    })

        shared_sorted = sorted(shared_gaps, key=lambda x: -x["gap"])[:30]

        # ── Categorise by opportunity type ───────────────────────────────
        quick_wins = [g for g in top_gaps if g["recommendation"] == "quick_win"][:10]
        mid_terms  = [g for g in top_gaps if g["recommendation"] == "mid_term"][:15]
        long_terms = [g for g in top_gaps if g["recommendation"] == "long_term"][:10]

        ms = int((time.time() - t0) * 1000)
        return self._create_output(
            success=True,
            result={
                "total_gap_keywords":  len(gap_items),
                "analyzed_competitors": len(comp_data),
                "top_gap_keywords":    top_gaps,
                "shared_keyword_gaps": shared_sorted,
                "by_recommendation": {
                    "quick_wins": quick_wins,
                    "mid_term":   mid_terms,
                    "long_term":  long_terms,
                },
                "coverage_gap_pct": round(
                    len(gap_items) / max(len(our_keywords) + len(gap_items), 1) * 100, 1
                ),
                "summary": (
                    f"Found {len(gap_items)} keyword gaps vs {len(comp_data)} competitors. "
                    f"Quick wins: {len(quick_wins)}, Mid-term: {len(mid_terms)}, "
                    f"Long-term: {len(long_terms)}."
                ),
            },
            execution_time_ms=ms,
        )


# ═══════════════════════════════════════════════════════════════════
# 2. ContentGapAnalysisSkill
# ═══════════════════════════════════════════════════════════════════

class ContentGapAnalysisSkill(Skill):
    """内容深度/结构/Schema/字数 差距全面对比."""

    DEPTH_THRESHOLD = 0.20   # 竞品内容比我们长 >20% → notable

    @property
    def name(self) -> str:
        return "ContentGapAnalysis"

    @property
    def description(self) -> str:
        return (
            "Benchmark our page content against competitors for word count, heading count, "
            "schema coverage, internal links, and topic coverage. "
            "Generates specific content expansion and schema addition recommendations."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ANALYZE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        t0     = time.time()
        params = skill_input.params
        ctx    = skill_input.context

        # Our page metrics
        our = params.get("our_metrics", {})
        our_words    = our.get("word_count", 0)
        our_headings = our.get("heading_count", 0)
        our_schemas  = set(our.get("schema_types", []))
        our_images   = our.get("image_count", 0)
        our_links    = our.get("internal_link_count", 0)
        our_topics   = set(our.get("topic_coverage", []))

        comp_data    = ctx.get("competitor_data", {})  # {domain: {content_metrics: {...}}}

        if not comp_data:
            return self._create_output(
                success=False,
                error="competitor_data is required in context",
                execution_time_ms=0,
            )

        # ── Per-competitor benchmarks ─────────────────────────────────────
        benchmarks: list[dict] = []
        all_words:   list[float] = []
        all_schemas: set = set()
        all_topics:  set = set()

        for domain, data in comp_data.items():
            cm = data.get("content_metrics", {})
            c_words    = cm.get("word_count", 0)
            c_headings = cm.get("heading_count", 0)
            c_schemas  = set(cm.get("schema_types", []))
            c_images   = cm.get("image_count", 0)
            c_links    = cm.get("internal_link_count", 0)
            c_topics   = set(cm.get("topic_coverage", []))

            if c_words:  all_words.append(c_words)
            all_schemas |= c_schemas
            all_topics  |= c_topics

            missing_schemas = list(c_schemas - our_schemas)
            missing_topics  = list(c_topics  - our_topics)

            benchmarks.append({
                "domain":            domain,
                "word_count":        c_words,
                "heading_count":     c_headings,
                "schema_types":      list(c_schemas),
                "image_count":       c_images,
                "internal_links":    c_links,
                "topic_coverage":    list(c_topics),
                "missing_schemas":   missing_schemas,
                "missing_topics":    missing_topics,
                "word_count_diff":   c_words - our_words,
                "content_deeper":    c_words > our_words * (1 + self.DEPTH_THRESHOLD),
            })

        # ── Aggregated gaps ───────────────────────────────────────────────
        avg_comp_words = round(sum(all_words) / len(all_words), 0) if all_words else 0
        schema_gap     = list(all_schemas - our_schemas)
        topic_gap      = list(all_topics  - our_topics)
        deeper_count   = sum(1 for b in benchmarks if b["content_deeper"])

        # ── Recommendations ───────────────────────────────────────────────
        recs: list[dict] = []

        if avg_comp_words > our_words * (1 + self.DEPTH_THRESHOLD):
            recs.append({
                "type":       "word_count",
                "priority":   "high",
                "action":     f"Expand content from {our_words} to ~{int(avg_comp_words)} words",
                "detail":     (
                    f"Competitors average {int(avg_comp_words)} words. "
                    f"Add depth sections, examples, and data to bridge the gap."
                ),
                "impact":     "+content_depth_score, +AI_citation_eligibility",
            })

        if schema_gap:
            recs.append({
                "type":       "schema",
                "priority":   "high",
                "action":     f"Add missing Schema types: {', '.join(schema_gap[:5])}",
                "schemas":    schema_gap,
                "impact":     "+structured_data_coverage, +SERP_features",
            })

        if topic_gap:
            recs.append({
                "type":       "topic_coverage",
                "priority":   "medium",
                "action":     f"Cover missing subtopics: {', '.join(list(topic_gap)[:5])}",
                "topics":     list(topic_gap),
                "impact":     "+topical_authority, +long_tail_coverage",
            })

        if our_images < 3:
            recs.append({
                "type":     "media",
                "priority": "medium",
                "action":   "Add more images/infographics (competitors avg "
                            f"{round(sum(b['image_count'] for b in benchmarks)/max(len(benchmarks),1),1)} images)",
                "impact":   "+Image Pack SERP feature, +engagement",
            })

        ms = int((time.time() - t0) * 1000)
        return self._create_output(
            success=True,
            result={
                "our_metrics": {
                    "word_count":    our_words,
                    "heading_count": our_headings,
                    "schema_types":  list(our_schemas),
                    "image_count":   our_images,
                    "internal_links":our_links,
                    "topic_count":   len(our_topics),
                },
                "competitor_avg": {
                    "word_count": avg_comp_words,
                    "schema_coverage": len(all_schemas),
                    "topic_coverage":  len(all_topics),
                },
                "gaps": {
                    "word_count_gap":     avg_comp_words - our_words,
                    "schema_gap":         schema_gap,
                    "topic_gap":          list(topic_gap),
                    "competitors_deeper": deeper_count,
                },
                "benchmarks":        benchmarks,
                "recommendations":   recs,
                "priority_actions":  [r for r in recs if r["priority"] == "high"],
                "summary": (
                    f"Content gap vs {len(comp_data)} competitors: "
                    f"word gap {int(avg_comp_words - our_words)}, "
                    f"{len(schema_gap)} missing schemas, "
                    f"{len(topic_gap)} missing topics."
                ),
            },
            execution_time_ms=ms,
        )
