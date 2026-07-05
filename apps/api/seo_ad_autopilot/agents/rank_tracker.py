"""Rank Tracker Agent — daily keyword rank snapshot + SERP feature tracking.

P0 缺口补全:
- 每日/每周关键词排名快照
- SERP 特性追踪 (Featured Snippet / PAA / Local Pack / AI Overview)
- 算法更新关联分析 (部署前后排名对比)
- 排名增量与 SEO 任务归因
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import Agent, AgentOutput, AgentRole, DebateOpinion, DebateStance, SiteContext

try:
    _ROLE = AgentRole.RANK_TRACKER          # type: ignore[attr-defined]
except AttributeError:
    _ROLE = "rank_tracker"                  # type: ignore[assignment]


class RankTrackerAgent(Agent):
    """Rank Tracker Agent — keyword rank monitoring + SERP feature tracking."""

    RANK_DROP_ALERT   = 5    # 单周期下降 ≥5 位 → alert
    RANK_GAIN_NOTABLE = 3    # 上升 ≥3 位 → notable
    TOP_10            = 10
    TOP_3             = 3

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
        kw = ["rank", "keyword", "serp", "position", "algorithm", "tracking"]
        if not any(k in topic.lower() for k in kw):
            return DebateOpinion(
                agent_role=self._role,
                stance=DebateStance.ABSTAIN,
                reasoning="Topic not related to rank tracking",
            )
        avg = proposal.get("rank_snapshot", {}).get("avg_position", 999)
        if avg <= self.TOP_10:
            return DebateOpinion(
                agent_role=self._role,
                stance=DebateStance.AGREE,
                reasoning=f"Avg rank {avg} is within top-10, good visibility",
                evidence=[f"avg_position={avg}"],
                confidence=0.80,
            )
        return DebateOpinion(
            agent_role=self._role,
            stance=DebateStance.DISAGREE,
            reasoning=f"Avg rank {avg} outside top-10 — content needs rank improvement",
            evidence=[f"avg_position={avg}"],
            confidence=0.75,
        )

    # ── Core Analysis ──────────────────────────────────────────────────────

    def analyze(self, context: SiteContext) -> AgentOutput:
        """分析关键词排名状况 + SERP 特性分布."""
        rd  = context.raw_data
        url = context.url

        keywords     = rd.get("target_keywords", [])
        rank_history = rd.get("rank_history", {})   # {kw: [{date,position,serp_features}]}
        gsc_data     = rd.get("gsc_data", {})

        snapshot      = self._build_snapshot(keywords, rank_history, gsc_data)
        movements     = self._detect_movements(rank_history)
        serp_features = self._analyze_serp_features(rank_history)
        algo_impact   = self._detect_algo_impact(rank_history, rd.get("algo_updates", []))
        opportunities = self._find_opportunities(snapshot, gsc_data)

        priority = self._calc_priority(snapshot, movements)

        content = {
            "url":            url,
            "snapshot_date":  datetime.utcnow().strftime("%Y-%m-%d"),
            "rank_snapshot":  snapshot,
            "rank_movements": movements,
            "serp_features":  serp_features,
            "algo_impact":    algo_impact,
            "opportunities":  opportunities,
            "priority":       priority,
            "summary":        self._build_summary(snapshot, movements),
        }

        return self._create_output(
            content=content,
            confidence=0.84,
            risk_score=0.02,
            reasoning=(
                f"Rank analysis: {snapshot.get('total_keywords', 0)} keywords tracked, "
                f"avg position {snapshot.get('avg_position', 'N/A')}"
            ),
        )

    # ── Snapshot ──────────────────────────────────────────────────────────

    def _build_snapshot(
        self,
        keywords:     list[str],
        rank_history: dict[str, list],
        gsc_data:     dict[str, Any],
    ) -> dict[str, Any]:
        rows:      list[dict] = []
        positions: list[float] = []

        for kw in keywords:
            hist    = rank_history.get(kw, [])
            current = hist[-1] if hist else None
            prev    = hist[-2] if len(hist) >= 2 else None
            pos     = current.get("position", 999) if current else 999
            prev_pos= prev.get("position", 999)    if prev    else 999
            delta   = prev_pos - pos
            positions.append(pos)
            gsc_kw  = gsc_data.get(kw, {})
            rows.append({
                "keyword":       kw,
                "position":      pos,
                "prev_position": prev_pos,
                "delta":         delta,
                "impressions":   gsc_kw.get("impressions", 0),
                "clicks":        gsc_kw.get("clicks", 0),
                "ctr":           gsc_kw.get("ctr", 0.0),
                "serp_features": current.get("serp_features", []) if current else [],
                "url_ranking":   current.get("url", "")           if current else "",
                "date":          current.get("date", "")          if current else "",
            })

        avg   = round(sum(positions) / len(positions), 1) if positions else 0
        return {
            "total_keywords": len(keywords),
            "avg_position":   avg,
            "top_3":          sum(1 for p in positions if p <= self.TOP_3),
            "top_10":         sum(1 for p in positions if p <= self.TOP_10),
            "page_2":         sum(1 for p in positions if 10 < p <= 20),
            "unranked":       sum(1 for p in positions if p > 100),
            "keyword_ranks":  sorted(rows, key=lambda x: x["position"]),
        }

    # ── Movement Detection ─────────────────────────────────────────────────

    def _detect_movements(self, rank_history: dict[str, list]) -> dict[str, Any]:
        drops:  list[dict] = []
        gains:  list[dict] = []
        stable: list[str]  = []

        for kw, hist in rank_history.items():
            if len(hist) < 2:
                stable.append(kw)
                continue
            curr = hist[-1].get("position", 999)
            prev = hist[-2].get("position", 999)
            d    = prev - curr
            if d <= -self.RANK_DROP_ALERT:
                drops.append({"keyword": kw, "from": prev, "to": curr, "delta": d})
            elif d >= self.RANK_GAIN_NOTABLE:
                gains.append({"keyword": kw, "from": prev, "to": curr, "delta": d})
            else:
                stable.append(kw)

        return {
            "significant_drops": sorted(drops, key=lambda x: x["delta"]),
            "notable_gains":     sorted(gains, key=lambda x: -x["delta"]),
            "stable_keywords":   stable,
            "drop_count":        len(drops),
            "gain_count":        len(gains),
            "alert_level": (
                "critical" if len(drops) >= 5 else
                "high"     if len(drops) >= 2 else
                "low"
            ),
        }

    # ── SERP Feature Analysis ──────────────────────────────────────────────

    def _analyze_serp_features(self, rank_history: dict[str, list]) -> dict[str, Any]:
        feature_counts: dict[str, int]   = {}
        owned_features: dict[str, list]  = {}

        for kw, hist in rank_history.items():
            if not hist:
                continue
            latest = hist[-1]
            for f in latest.get("serp_features", []):
                feature_counts[f] = feature_counts.get(f, 0) + 1
                if latest.get("we_own_feature", False):
                    owned_features.setdefault(f, []).append(kw)

        opps = []
        for feature, count in feature_counts.items():
            owned = len(owned_features.get(feature, []))
            if owned < count:
                opps.append({
                    "feature":     feature,
                    "appears_for": count,
                    "we_own":      owned,
                    "gap":         count - owned,
                })

        return {
            "feature_distribution":   feature_counts,
            "owned_features":         owned_features,
            "feature_opportunities":  sorted(opps, key=lambda x: -x["gap"]),
            "ai_overview_count":      feature_counts.get("ai_overview", 0),
            "featured_snippet_count": feature_counts.get("featured_snippet", 0),
            "paa_count":              feature_counts.get("people_also_ask", 0),
        }

    # ── Algorithm Impact ───────────────────────────────────────────────────

    def _detect_algo_impact(
        self,
        rank_history: dict[str, list],
        algo_updates: list[dict],
    ) -> dict[str, Any]:
        impacts: list[dict] = []

        for upd in algo_updates:
            ud = upd.get("date", "")
            if not ud:
                continue
            affected: list[dict] = []
            for kw, hist in rank_history.items():
                before = [h for h in hist if h.get("date", "") < ud]
                after  = [h for h in hist if h.get("date", "") >= ud]
                if not before or not after:
                    continue
                avg_b = sum(h["position"] for h in before[-3:]) / min(3, len(before))
                avg_a = sum(h["position"] for h in after[:3])   / min(3, len(after))
                delta = avg_b - avg_a
                if abs(delta) >= 3:
                    affected.append({
                        "keyword":   kw,
                        "delta":     round(delta, 1),
                        "direction": "improved" if delta > 0 else "declined",
                    })
            if affected:
                net = round(sum(a["delta"] for a in affected) / len(affected), 1)
                impacts.append({
                    "update_name":       upd.get("name", "Unknown Update"),
                    "update_date":       ud,
                    "affected_keywords": len(affected),
                    "net_impact":        net,
                    "details":           affected[:10],
                })

        return {"detected_impacts": impacts, "total_events": len(impacts)}

    # ── Opportunity Finder ─────────────────────────────────────────────────

    def _find_opportunities(
        self, snapshot: dict[str, Any], gsc_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        opps: list[dict] = []
        for row in snapshot.get("keyword_ranks", []):
            pos = row["position"]
            imp = row.get("impressions", 0)
            if 10 < pos <= 20:
                opps.append({
                    "keyword":        row["keyword"],
                    "position":       pos,
                    "impressions":    imp,
                    "opportunity":    "page_2_to_page_1",
                    "effort":         "medium",
                    "priority_score": imp / max(pos, 1),
                })
            elif 3 < pos <= 10 and imp > 100:
                opps.append({
                    "keyword":        row["keyword"],
                    "position":       pos,
                    "impressions":    imp,
                    "opportunity":    "top_10_to_top_3",
                    "effort":         "high",
                    "priority_score": imp / max(pos, 1) * 2,
                })
        return sorted(opps, key=lambda x: -x.get("priority_score", 0))[:20]

    # ── Helpers ────────────────────────────────────────────────────────────

    def _calc_priority(self, snapshot: dict, movements: dict) -> str:
        drops = movements.get("drop_count", 0)
        avg   = snapshot.get("avg_position", 999)
        if drops >= 5 or avg > 50: return "critical"
        if drops >= 2 or avg > 30: return "high"
        if drops >= 1 or avg > 20: return "medium"
        return "low"

    def _build_summary(self, snapshot: dict, movements: dict) -> str:
        return (
            f"Tracking {snapshot.get('total_keywords', 0)} keywords — "
            f"avg position {snapshot.get('avg_position', 0)}. "
            f"Top-10: {snapshot.get('top_10', 0)}. "
            f"Recent: {movements.get('gain_count', 0)} gains, "
            f"{movements.get('drop_count', 0)} drops."
        )
