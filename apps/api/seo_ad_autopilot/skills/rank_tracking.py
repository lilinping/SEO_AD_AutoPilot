"""Rank Tracking Skills — daily keyword rank snapshot + SERP feature monitoring.

包含两个 Skill:
- RankSnapshotSkill       每日关键词排名快照，支持 GSC/SerpAPI 数据源
- SERPFeatureTrackerSkill SERP 特性追踪 (Featured Snippet/PAA/AI Overview/Local Pack)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


# ═══════════════════════════════════════════════════════════════════
# 1. RankSnapshotSkill
# ═══════════════════════════════════════════════════════════════════

class RankSnapshotSkill(Skill):
    """每日关键词排名快照 — 记录位置变化、趋势、机会窗口."""

    ALERT_DROP  = 5    # 单周期下降 ≥5 位 → alert
    GAIN_NOTABLE = 3   # 上升 ≥3 位 → notable

    @property
    def name(self) -> str:
        return "RankSnapshot"

    @property
    def description(self) -> str:
        return (
            "Record daily keyword position snapshots from GSC / SerpAPI / DataForSEO "
            "data. Detects rank movements, calculates position trends, and surfaces "
            "quick-win opportunities for page-2 and top-10 keywords."
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
        ctx    = skill_input.context

        keywords      = params.get("keywords", [])
        serp_data     = ctx.get("serp_data", {})        # {kw: {position, url, serp_features}}
        gsc_data      = ctx.get("gsc_data", {})          # {kw: {impressions, clicks, ctr, avg_position}}
        prev_snapshot = params.get("prev_snapshot", {})  # {kw: position} or {kw: {position}}
        date_str      = params.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        alert_drop    = params.get("alert_drop", self.ALERT_DROP)

        if not keywords:
            return self._create_output(
                success=False, error="keywords list is required", execution_time_ms=0
            )

        rows:      list[dict] = []
        positions: list[float] = []
        drops:     list[dict] = []
        gains:     list[dict] = []

        for kw in keywords:
            sd  = serp_data.get(kw, {})
            gsc = gsc_data.get(kw, {})

            # Position resolution: SERP > GSC avg_position > 999
            cur = sd.get("position") or gsc.get("avg_position") or 999

            # Prev position normalisation (supports both int and dict formats)
            pv_raw = prev_snapshot.get(kw, 999)
            prev   = pv_raw.get("position", 999) if isinstance(pv_raw, dict) else pv_raw

            delta     = prev - cur   # positive = improved
            positions.append(cur)

            row = {
                "keyword":       kw,
                "position":      cur,
                "prev_position": prev,
                "delta":         round(delta, 1),
                "url":           sd.get("url", ""),
                "impressions":   gsc.get("impressions", 0),
                "clicks":        gsc.get("clicks", 0),
                "ctr":           round(gsc.get("ctr", 0.0), 4),
                "serp_features": sd.get("serp_features", []),
                "we_featured":   sd.get("we_own_feature", False),
                "date":          date_str,
            }
            rows.append(row)

            if delta <= -alert_drop:
                drops.append({"keyword": kw, "delta": delta, "position": cur})
            elif delta >= self.GAIN_NOTABLE:
                gains.append({"keyword": kw, "delta": delta, "position": cur})

        # ── Aggregate ─────────────────────────────────────────────────────
        real = [p for p in positions if p < 999]
        avg  = round(sum(real) / len(real), 1) if real else 0

        snapshot = {
            "date":           date_str,
            "total_keywords": len(keywords),
            "avg_position":   avg,
            "top_3":          sum(1 for p in positions if p <= 3),
            "top_10":         sum(1 for p in positions if p <= 10),
            "top_30":         sum(1 for p in positions if p <= 30),
            "unranked":       sum(1 for p in positions if p >= 100),
            "keyword_rows":   sorted(rows, key=lambda x: x["position"]),
        }

        movements = {
            "drops":       sorted(drops, key=lambda x: x["delta"]),
            "gains":       sorted(gains, key=lambda x: -x["delta"]),
            "drop_count":  len(drops),
            "gain_count":  len(gains),
            "alert_level": (
                "critical" if len(drops) >= 5 else
                "high"     if len(drops) >= 2 else
                "low"
            ),
        }

        # ── Opportunity detector ──────────────────────────────────────────
        opps: list[dict] = []
        for row in rows:
            pos = row["position"]
            imp = row.get("impressions", 0)
            if 10 < pos <= 20:
                opps.append({
                    "keyword":      row["keyword"],
                    "current_rank": pos,
                    "type":         "page_2_to_page_1",
                    "priority":     "high",
                    "impressions":  imp,
                })
            elif 3 < pos <= 10 and imp > 50:
                opps.append({
                    "keyword":      row["keyword"],
                    "current_rank": pos,
                    "type":         "top_10_to_top_3",
                    "priority":     "medium",
                    "impressions":  imp,
                })

        alerts = [
            {
                "level":   "warning",
                "message": (
                    f"Rank drop: '{d['keyword']}' dropped "
                    f"{abs(d['delta']):.0f} positions to #{d['position']}"
                ),
            }
            for d in drops
        ]

        ms = int((time.time() - t0) * 1000)
        return self._create_output(
            success=True,
            result={
                "snapshot":      snapshot,
                "movements":     movements,
                "opportunities": sorted(opps, key=lambda x: -x.get("impressions", 0))[:20],
                "alerts":        alerts,
                "summary": (
                    f"{len(keywords)} keywords tracked — avg rank {avg}. "
                    f"{len(gains)} gains, {len(drops)} drops "
                    f"(alert: {movements['alert_level']})"
                ),
            },
            execution_time_ms=ms,
        )


# ═══════════════════════════════════════════════════════════════════
# 2. SERPFeatureTrackerSkill
# ═══════════════════════════════════════════════════════════════════

class SERPFeatureTrackerSkill(Skill):
    """SERP 特性追踪 — 识别 AI Overview / Featured Snippet / PAA 等特性机会."""

    TRACKABLE = [
        "featured_snippet", "people_also_ask", "ai_overview",
        "local_pack", "knowledge_panel", "image_pack",
        "video_carousel", "top_stories", "sitelinks", "shopping",
    ]

    HINTS: dict[str, str] = {
        "featured_snippet": "Add concise direct-answer paragraph; use structured list/table",
        "people_also_ask":  "Add FAQ section with question-style H2s matching PAA questions",
        "ai_overview":      "Add FAQPage schema, E-E-A-T signals, authority citations",
        "local_pack":       "Optimize Google Business Profile; add LocalBusiness schema",
        "knowledge_panel":  "Add Organization/Person schema with sameAs Wikipedia/Wikidata",
        "image_pack":       "Add descriptive alt text, image schema, optimize filenames",
        "video_carousel":   "Add VideoObject schema; optimize YouTube titles/descriptions",
        "shopping":         "Add Product schema with price/availability",
        "sitelinks":        "Improve internal linking; add SiteNavigationElement schema",
        "top_stories":      "Publish news sitemap; use Article schema; publish timely content",
    }

    @property
    def name(self) -> str:
        return "SERPFeatureTracker"

    @property
    def description(self) -> str:
        return (
            "Track SERP feature presence (Featured Snippet, PAA, AI Overviews, Local Pack) "
            "across target keywords. Identifies owned vs unowned features and generates "
            "targeted optimization actions for each feature type."
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
        ctx    = skill_input.context

        keywords      = params.get("keywords", [])
        serp_data     = ctx.get("serp_data", {})
        prev_features = params.get("prev_features", {})   # {kw: [features]}

        if not keywords:
            return self._create_output(
                success=False, error="keywords is required", execution_time_ms=0
            )

        # ── Feature inventory ─────────────────────────────────────────────
        inventory: dict[str, dict] = {
            f: {"total": 0, "owned": 0, "opp_keywords": []}
            for f in self.TRACKABLE
        }
        kw_detail: list[dict] = []
        changes:   list[dict] = []

        for kw in keywords:
            sd            = serp_data.get(kw, {})
            cur_features  = sd.get("serp_features", [])
            owned_features= sd.get("owned_features", [])
            prev          = prev_features.get(kw, [])

            new_f  = [f for f in cur_features if f not in prev]
            lost_f = [f for f in prev if f not in cur_features]
            if new_f or lost_f:
                changes.append({"keyword": kw, "gained": new_f, "lost": lost_f})

            for feat in cur_features:
                if feat in inventory:
                    inventory[feat]["total"] += 1
                    if feat in owned_features:
                        inventory[feat]["owned"] += 1
                    else:
                        inventory[feat]["opp_keywords"].append(kw)

            kw_detail.append({
                "keyword":          kw,
                "features_present": cur_features,
                "features_owned":   owned_features,
                "features_gap":     [f for f in cur_features if f not in owned_features],
                "position":         sd.get("position", 999),
            })

        # ── Opportunity scoring ────────────────────────────────────────────
        opps: list[dict] = []
        for feat, data in inventory.items():
            gap = data["total"] - data["owned"]
            if gap > 0:
                win_rate = round(data["owned"] / data["total"], 2) if data["total"] else 0
                opps.append({
                    "feature":      feat,
                    "total":        data["total"],
                    "owned":        data["owned"],
                    "gap":          gap,
                    "win_rate":     win_rate,
                    "top_keywords": data["opp_keywords"][:5],
                    "action":       self.HINTS.get(feat, "Follow Schema.org guidelines"),
                })

        opps_sorted = sorted(opps, key=lambda x: x["gap"] * (1 - x["win_rate"]), reverse=True)

        # ── AI Overview summary ───────────────────────────────────────────
        aio = inventory.get("ai_overview", {})
        aio_summary = {
            "keywords_with_aio": aio.get("total", 0),
            "we_own":            aio.get("owned", 0),
            "opportunity_kws":   aio.get("opp_keywords", []),
            "win_rate":          round(aio["owned"] / aio["total"], 2) if aio.get("total") else 0,
        }

        ms = int((time.time() - t0) * 1000)
        return self._create_output(
            success=True,
            result={
                "feature_inventory":      inventory,
                "feature_opportunities":  opps_sorted,
                "top_priority_actions": [
                    {"feature": o["feature"], "action": o["action"],
                     "impact": f"Win {o['gap']} feature appearances"}
                    for o in opps_sorted[:5]
                ],
                "ai_overview_summary":    aio_summary,
                "keyword_detail":         kw_detail,
                "recent_changes":         changes,
                "total_opp_count":        sum(o["gap"] for o in opps),
            },
            execution_time_ms=ms,
        )
