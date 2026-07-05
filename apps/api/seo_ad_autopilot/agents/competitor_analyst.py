"""Competitor Analyst Agent — keyword gap, content comparison, SERP share.

P1 缺口补全:
- 竞品关键词差距分析 ("他们排名但我们没有的词")
- 同主题内容结构对比 (长度/结构/Schema/词数差异)
- SERP 份额变化追踪
- 广告策略监控
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from .base import Agent, AgentOutput, AgentRole, DebateOpinion, DebateStance, SiteContext

try:
    _ROLE = AgentRole.COMPETITOR_ANALYST    # type: ignore[attr-defined]
except AttributeError:
    _ROLE = "competitor_analyst"            # type: ignore[assignment]


class CompetitorAnalystAgent(Agent):
    """Competitor Analyst Agent — SERP gap analysis & content benchmarking."""

    # Gap thresholds
    SERP_SHARE_LOW      = 0.15   # <15% share → urgent action
    CONTENT_LENGTH_DIFF = 0.20   # competitor content >20% longer → notable
    KEYWORD_GAP_MIN     = 5      # ≥5 gap keywords before flagging

    def __init__(self) -> None:
        super().__init__()
        self._role = _ROLE  # type: ignore[assignment]

    # ── Debate ────────────────────────────────────────────────────────────

    def offer_opinion(
        self,
        topic: str,
        proposal: dict[str, Any],
        context: SiteContext,
        previous_opinions: list = None,
    ) -> DebateOpinion:
        kw = ["competitor", "gap", "serp share", "content gap", "benchmark"]
        if not any(k in topic.lower() for k in kw):
            return DebateOpinion(
                agent_role=self._role,
                stance=DebateStance.ABSTAIN,
                reasoning="Topic not related to competitor analysis",
            )
        share = proposal.get("competitor_analysis", {}).get("our_serp_share", 1.0)
        if share >= self.SERP_SHARE_LOW:
            return DebateOpinion(
                agent_role=self._role,
                stance=DebateStance.AGREE,
                reasoning=f"SERP share {share:.0%} meets minimum competitive threshold",
                evidence=[f"serp_share={share:.0%}"],
                confidence=0.78,
            )
        return DebateOpinion(
            agent_role=self._role,
            stance=DebateStance.DISAGREE,
            reasoning=f"SERP share only {share:.0%} — competitor dominance risk",
            evidence=[f"serp_share={share:.0%}"],
            confidence=0.82,
        )

    # ── Core Analysis ──────────────────────────────────────────────────────

    def analyze(self, context: SiteContext) -> AgentOutput:
        """全量竞品分析."""
        rd  = context.raw_data
        url = context.url

        our_domain   = urlparse(url).netloc
        competitors  = rd.get("competitors", [])
        comp_data    = rd.get("competitor_data", {})    # {domain: {...}}
        our_keywords = set(rd.get("target_keywords", []))
        our_ranks    = rd.get("rank_history", {})
        our_content  = rd.get("content_metrics", {})    # {word_count, schema_types, heading_count}

        keyword_gap   = self._keyword_gap(our_keywords, our_ranks, comp_data)
        content_bench = self._content_benchmark(our_content, comp_data)
        serp_share    = self._calc_serp_share(our_keywords, our_ranks, comp_data)
        ad_intel      = self._ad_intel(comp_data)
        quick_wins    = self._quick_wins(keyword_gap, content_bench, serp_share)

        priority = (
            "critical" if serp_share.get("our_share", 1) < self.SERP_SHARE_LOW else
            "high"     if keyword_gap.get("total_gap_keywords", 0) >= 20 else
            "medium"   if keyword_gap.get("total_gap_keywords", 0) >= self.KEYWORD_GAP_MIN else
            "low"
        )

        content = {
            "url":                url,
            "our_domain":         our_domain,
            "competitors_analyzed": len(competitors),
            "keyword_gap":        keyword_gap,
            "content_benchmark":  content_bench,
            "serp_share":         serp_share,
            "ad_intelligence":    ad_intel,
            "quick_wins":         quick_wins,
            "priority":           priority,
            "summary":            self._build_summary(keyword_gap, serp_share),
        }

        return self._create_output(
            content=content,
            confidence=0.82,
            risk_score=0.03,
            reasoning=(
                f"Competitor analysis: {len(competitors)} competitors, "
                f"{keyword_gap.get('total_gap_keywords', 0)} keyword gaps found"
            ),
        )

    # ── Keyword Gap ────────────────────────────────────────────────────────

    def _keyword_gap(
        self,
        our_kws:    set[str],
        our_ranks:  dict[str, list],
        comp_data:  dict[str, Any],
    ) -> dict[str, Any]:
        """找出竞品排名但我们没有的词."""
        gap_map: dict[str, list[dict]] = {}  # kw -> [{domain, position}]

        for domain, data in comp_data.items():
            for kw in data.get("keywords", []):
                if kw not in our_kws and kw not in our_ranks:
                    gap_map.setdefault(kw, []).append({
                        "domain":   domain,
                        "position": data.get("keyword_positions", {}).get(kw, 999),
                    })

        # Prioritize by: number of competitors ranking + their avg position
        gap_items: list[dict] = []
        for kw, sources in gap_map.items():
            avg_pos  = sum(s["position"] for s in sources) / len(sources)
            gap_items.append({
                "keyword":              kw,
                "competitor_count":     len(sources),
                "competitor_avg_rank":  round(avg_pos, 1),
                "sources":              sources,
                "priority_score":       len(sources) * (101 - avg_pos),
            })

        top_gaps = sorted(gap_items, key=lambda x: -x["priority_score"])

        # Keywords we rank but competitors rank MUCH better
        shared_gaps: list[dict] = []
        for kw, hist in our_ranks.items():
            if not hist:
                continue
            our_pos = hist[-1].get("position", 999)
            for domain, data in comp_data.items():
                comp_pos = data.get("keyword_positions", {}).get(kw, 999)
                if comp_pos < our_pos - 5:  # they're >5 positions ahead
                    shared_gaps.append({
                        "keyword":    kw,
                        "our_rank":   our_pos,
                        "their_rank": comp_pos,
                        "gap":        our_pos - comp_pos,
                        "domain":     domain,
                    })

        return {
            "total_gap_keywords":    len(top_gaps),
            "top_gap_keywords":      top_gaps[:30],
            "shared_keyword_gaps":   sorted(shared_gaps, key=lambda x: -x["gap"])[:20],
            "coverage_gap_pct":      round(
                len(top_gaps) / max(len(our_kws) + len(top_gaps), 1) * 100, 1
            ),
        }

    # ── Content Benchmark ──────────────────────────────────────────────────

    def _content_benchmark(
        self,
        our_metrics: dict[str, Any],
        comp_data:   dict[str, Any],
    ) -> dict[str, Any]:
        """对比内容深度、结构、Schema 覆盖."""
        our_words    = our_metrics.get("word_count", 0)
        our_headings = our_metrics.get("heading_count", 0)
        our_schemas  = set(our_metrics.get("schema_types", []))

        comp_benchmarks: list[dict] = []
        for domain, data in comp_data.items():
            c_words    = data.get("avg_word_count", 0)
            c_headings = data.get("avg_heading_count", 0)
            c_schemas  = set(data.get("schema_types", []))
            missing_schemas = list(c_schemas - our_schemas)

            comp_benchmarks.append({
                "domain":           domain,
                "avg_word_count":   c_words,
                "avg_heading_count": c_headings,
                "schema_types":     list(c_schemas),
                "missing_schemas_vs_us": missing_schemas,
                "word_count_diff":  c_words - our_words,
                "content_deeper":   c_words > our_words * (1 + self.CONTENT_LENGTH_DIFF),
            })

        # Overall benchmarks
        all_words  = [b["avg_word_count"] for b in comp_benchmarks if b["avg_word_count"]]
        avg_comp_words = round(sum(all_words) / len(all_words), 0) if all_words else 0

        return {
            "our_word_count":        our_words,
            "competitor_avg_words":  avg_comp_words,
            "word_count_gap":        avg_comp_words - our_words,
            "we_are_shorter":        avg_comp_words > our_words * (1 + self.CONTENT_LENGTH_DIFF),
            "our_schemas":           list(our_schemas),
            "competitor_benchmarks": comp_benchmarks,
            "schema_gaps":           list(
                set().union(*(set(b.get("missing_schemas_vs_us", [])) for b in comp_benchmarks))
            ),
            "recommendations": self._content_recs(our_words, avg_comp_words, our_schemas, comp_benchmarks),
        }

    def _content_recs(
        self,
        our_words:   int,
        avg_comp:    float,
        our_schemas: set,
        benchmarks:  list,
    ) -> list[str]:
        recs = []
        if avg_comp > our_words * 1.20:
            recs.append(
                f"Expand content by ~{int(avg_comp - our_words)} words "
                f"to match competitor average ({int(avg_comp)} words)"
            )
        all_missing = set()
        for b in benchmarks:
            all_missing.update(b.get("missing_schemas_vs_us", []))
        if all_missing:
            recs.append(
                f"Add missing Schema types used by competitors: {', '.join(sorted(all_missing))}"
            )
        return recs

    # ── SERP Share ─────────────────────────────────────────────────────────

    def _calc_serp_share(
        self,
        our_kws:    set[str],
        our_ranks:  dict[str, list],
        comp_data:  dict[str, Any],
    ) -> dict[str, Any]:
        """估算 SERP 份额 (基于可见曝光权重)."""
        # CTR 权重近似值 (position 1=30%, 2=15%, 3=10%, ...)
        CTR = {1:0.30,2:0.15,3:0.10,4:0.07,5:0.05,6:0.04,7:0.03,
               8:0.03,9:0.02,10:0.02}

        def pos_weight(pos: float) -> float:
            p = int(pos)
            if p in CTR: return CTR[p]
            if p <= 20:  return 0.01
            return 0.0

        our_weight  = 0.0
        comp_weight: dict[str, float] = {}

        for kw, hist in our_ranks.items():
            if hist:
                our_weight += pos_weight(hist[-1].get("position", 999))

        for domain, data in comp_data.items():
            w = 0.0
            for kw, pos in data.get("keyword_positions", {}).items():
                w += pos_weight(pos)
            comp_weight[domain] = w

        total = our_weight + sum(comp_weight.values())
        our_share = round(our_weight / total, 3) if total else 0

        comp_shares = {
            d: round(w / total, 3) if total else 0
            for d, w in comp_weight.items()
        }

        return {
            "our_share":         our_share,
            "our_share_pct":     f"{our_share:.1%}",
            "competitor_shares": comp_shares,
            "top_competitor":    max(comp_shares, key=comp_shares.get) if comp_shares else None,
            "share_trend":       "low" if our_share < self.SERP_SHARE_LOW else "acceptable",
        }

    # ── Ad Intelligence ────────────────────────────────────────────────────

    def _ad_intel(self, comp_data: dict[str, Any]) -> dict[str, Any]:
        """竞品广告策略情报."""
        intel: list[dict] = []
        for domain, data in comp_data.items():
            ad_info = data.get("ad_strategy", {})
            if ad_info:
                intel.append({
                    "domain":            domain,
                    "ad_networks":       ad_info.get("networks", []),
                    "ad_slots_count":    ad_info.get("slot_count", 0),
                    "uses_header_bidding": ad_info.get("header_bidding", False),
                    "estimated_rpm":     ad_info.get("estimated_rpm"),
                    "ad_density":        ad_info.get("ad_density", "unknown"),
                })
        return {
            "competitor_ad_intel": intel,
            "hb_adoption_rate":    round(
                sum(1 for i in intel if i["uses_header_bidding"]) / max(len(intel), 1), 2
            ),
        }

    # ── Quick Wins ──────────────────────────────────────────────────────────

    def _quick_wins(
        self,
        keyword_gap:   dict[str, Any],
        content_bench: dict[str, Any],
        serp_share:    dict[str, Any],
    ) -> list[dict[str, Any]]:
        wins: list[dict] = []

        # Easy keyword additions
        top_gaps = keyword_gap.get("top_gap_keywords", [])
        easy_gaps = [g for g in top_gaps if g.get("competitor_avg_rank", 999) <= 10][:5]
        if easy_gaps:
            wins.append({
                "type":   "keyword_gap",
                "action": f"Target {len(easy_gaps)} high-value gap keywords ranked top-10 by competitors",
                "keywords": [g["keyword"] for g in easy_gaps],
                "effort": "low",
                "impact": "high",
            })

        # Content depth
        if content_bench.get("we_are_shorter"):
            gap = content_bench.get("word_count_gap", 0)
            wins.append({
                "type":   "content_depth",
                "action": f"Expand content by ~{int(gap)} words to match competitor average",
                "effort": "medium",
                "impact": "medium",
            })

        # Schema gaps
        schema_gaps = content_bench.get("schema_gaps", [])
        if schema_gaps:
            wins.append({
                "type":   "schema_addition",
                "action": f"Add Schema types: {', '.join(schema_gaps[:3])}",
                "effort": "low",
                "impact": "medium",
            })

        return wins

    # ── Summary ────────────────────────────────────────────────────────────

    def _build_summary(self, keyword_gap: dict, serp_share: dict) -> str:
        return (
            f"Found {keyword_gap.get('total_gap_keywords', 0)} keyword gaps. "
            f"Our SERP share: {serp_share.get('our_share_pct', 'N/A')}. "
            f"Top competitor: {serp_share.get('top_competitor', 'N/A')}."
        )
