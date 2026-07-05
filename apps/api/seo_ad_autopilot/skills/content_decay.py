"""Content Decay Detection Skill — 内容流量下滑预警 + 自动刷新建议.

P1 缺口补全:
- 定期扫描已上线内容的流量/排名变化
- 识别正在流失排名的内容 (衰减预警)
- 自动生成"内容更新建议包"
- 关键词蚕食分析 (多页面争抢同一词)
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


class ContentDecayDetectorSkill(Skill):
    """检测内容衰减信号并生成优先级刷新行动计划.

    衰减判定标准 (任意一条触发):
    - 过去 90 天点击量下降 >25%
    - 过去 90 天平均排名下降 >5 位
    - 过去 90 天曝光量下降 >30%
    - 内容上次更新距今 >180 天 且排名在 page 2+
    """

    # Decay thresholds
    CLICK_DROP_PCT    = 0.25   # 25% click drop
    RANK_DROP_POS     = 5      # 5-position rank drop
    IMPRESSION_DROP   = 0.30   # 30% impression drop
    STALENESS_DAYS    = 180    # content older than 180d + page2+ = at-risk
    PAGE2_THRESHOLD   = 11     # position > 11 = page 2

    # Severity levels
    SEVERE_CLICK_DROP = 0.50
    MODERATE_CLICK    = 0.25

    @property
    def name(self) -> str:
        return "ContentDecayDetector"

    @property
    def description(self) -> str:
        return (
            "Detect traffic and ranking decay for published content pages. "
            "Compares 90-day click/impression/rank windows, flags stale content, "
            "detects keyword cannibalization, and generates prioritized refresh plans."
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

        # Inputs
        pages        = params.get("pages", [])
        # Each page: {url, title, published_date, modified_date, keywords:[]}
        gsc_history  = ctx.get("gsc_history", {})
        # {url: {current_90d:{clicks,impressions,avg_position}, prev_90d:{...}}}
        rank_history = ctx.get("rank_history", {})
        # {url: {kw: [{date, position}]}}
        today        = datetime.now(timezone.utc)

        if not pages:
            return self._create_output(
                success=False, error="pages list is required", execution_time_ms=0
            )

        # ── Per-page decay analysis ───────────────────────────────────────
        decayed:  list[dict] = []
        at_risk:  list[dict] = []
        healthy:  list[dict] = []

        for page in pages:
            url      = page.get("url", "")
            title    = page.get("title", "")
            mod_date = page.get("modified_date") or page.get("published_date")

            # GSC comparison windows
            gsc = gsc_history.get(url, {})
            cur = gsc.get("current_90d", {})
            prv = gsc.get("prev_90d", {})

            cur_clicks  = cur.get("clicks", 0)
            prv_clicks  = prv.get("clicks", 0)
            cur_impr    = cur.get("impressions", 0)
            prv_impr    = prv.get("impressions", 0)
            cur_pos     = cur.get("avg_position", 999)
            prv_pos     = prv.get("avg_position", 999)

            click_delta = (
                (cur_clicks - prv_clicks) / prv_clicks
                if prv_clicks > 0 else 0.0
            )
            impr_delta = (
                (cur_impr - prv_impr) / prv_impr
                if prv_impr > 0 else 0.0
            )
            pos_delta = prv_pos - cur_pos  # positive = improved

            # Staleness
            stale = False
            stale_days = 0
            if mod_date:
                try:
                    mod_dt = datetime.fromisoformat(mod_date.replace("Z", "+00:00"))
                    if mod_dt.tzinfo is None:
                        mod_dt = mod_dt.replace(tzinfo=timezone.utc)
                    stale_days = (today - mod_dt).days
                    stale = stale_days >= self.STALENESS_DAYS and cur_pos > self.PAGE2_THRESHOLD
                except (ValueError, TypeError):
                    pass

            # Decay signals
            signals: list[str] = []
            if prv_clicks > 5 and click_delta <= -self.CLICK_DROP_PCT:
                signals.append(
                    f"Click drop {click_delta:.0%} vs prev 90d "
                    f"({prv_clicks}→{cur_clicks})"
                )
            if prv_impr > 10 and impr_delta <= -self.IMPRESSION_DROP:
                signals.append(
                    f"Impression drop {impr_delta:.0%} vs prev 90d"
                )
            if prv_pos < 999 and pos_delta <= -self.RANK_DROP_POS:
                signals.append(
                    f"Rank dropped {abs(pos_delta):.1f} positions "
                    f"({prv_pos:.1f}→{cur_pos:.1f})"
                )
            if stale:
                signals.append(
                    f"Content not updated for {stale_days}d, ranking on page 2+ "
                    f"(pos {cur_pos:.1f})"
                )

            severity = self._calc_severity(click_delta, pos_delta, stale, signals)

            record = {
                "url":           url,
                "title":         title,
                "current_pos":   round(cur_pos, 1),
                "prev_pos":      round(prv_pos, 1),
                "click_delta":   round(click_delta, 3),
                "impr_delta":    round(impr_delta, 3),
                "pos_delta":     round(pos_delta, 1),
                "cur_clicks":    cur_clicks,
                "prv_clicks":    prv_clicks,
                "stale_days":    stale_days,
                "decay_signals": signals,
                "severity":      severity,
                "refresh_plan":  self._refresh_plan(page, signals, cur_pos, stale_days),
            }

            if signals:
                if severity in ("critical", "high"):
                    decayed.append(record)
                else:
                    at_risk.append(record)
            else:
                healthy.append(record)

        # ── Keyword cannibalization ────────────────────────────────────────
        cannibalization = self._detect_cannibalization(pages, rank_history)

        # ── Summary + priority order ──────────────────────────────────────
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        all_issues = sorted(
            decayed + at_risk,
            key=lambda x: (severity_order.get(x["severity"], 9), x.get("click_delta", 0))
        )

        ms = int((time.time() - t0) * 1000)
        return self._create_output(
            success=True,
            result={
                "total_pages":           len(pages),
                "decayed_count":         len(decayed),
                "at_risk_count":         len(at_risk),
                "healthy_count":         len(healthy),
                "priority_refresh_list": all_issues[:20],
                "decayed_pages":         decayed,
                "at_risk_pages":         at_risk,
                "cannibalization":       cannibalization,
                "refresh_roi_estimate":  self._roi_estimate(decayed),
                "summary": (
                    f"{len(pages)} pages scanned — "
                    f"{len(decayed)} decayed (action needed), "
                    f"{len(at_risk)} at-risk, "
                    f"{len(healthy)} healthy."
                ),
            },
            execution_time_ms=ms,
        )

    # ── Helpers ────────────────────────────────────────────────────────────

    def _calc_severity(
        self,
        click_delta: float,
        pos_delta:   float,
        stale:       bool,
        signals:     list[str],
    ) -> str:
        if not signals:
            return "none"
        if click_delta <= -self.SEVERE_CLICK_DROP or pos_delta <= -15:
            return "critical"
        if click_delta <= -self.MODERATE_CLICK or pos_delta <= -self.RANK_DROP_POS or stale:
            return "high"
        return "medium"

    def _refresh_plan(
        self,
        page:       dict,
        signals:    list[str],
        cur_pos:    float,
        stale_days: int,
    ) -> dict[str, Any]:
        actions: list[str] = []
        effort  = "low"

        if stale_days >= self.STALENESS_DAYS:
            actions.append(
                f"Update all statistics and data references (content is {stale_days}d old)"
            )
            effort = "medium"

        if cur_pos > self.PAGE2_THRESHOLD:
            actions.append(
                "Improve content depth: add FAQ section, expand thin sections, "
                "add supporting data and expert quotes"
            )
            effort = "medium"

        for sig in signals:
            if "Click drop" in sig:
                actions.append(
                    "Refresh title/meta description to improve CTR; "
                    "A/B test new headline variants"
                )
            if "Impression" in sig:
                actions.append(
                    "Expand keyword coverage: add related long-tail queries, "
                    "update semantic clusters"
                )
            if "Rank dropped" in sig and effort == "low":
                effort = "medium"
                actions.append(
                    "Strengthen internal linking to this page; "
                    "add new supporting content sections"
                )

        # Remove duplicates preserving order
        seen: set = set()
        unique: list[str] = []
        for a in actions:
            if a not in seen:
                seen.add(a)
                unique.append(a)

        return {
            "actions":         unique,
            "effort":          effort,
            "estimated_weeks": 1 if effort == "low" else 2 if effort == "medium" else 4,
            "expected_gain":   "+10–30% click recovery within 60 days after refresh",
        }

    def _detect_cannibalization(
        self,
        pages:        list[dict],
        rank_history: dict[str, Any],
    ) -> dict[str, Any]:
        """识别多个页面争抢同一关键词的情况."""
        kw_map: dict[str, list[dict]] = {}   # kw -> [{url, avg_pos}]

        for page in pages:
            url = page.get("url", "")
            url_hist = rank_history.get(url, {})
            for kw, kw_hist in url_hist.items():
                if not kw_hist:
                    continue
                recent = kw_hist[-3:]
                avg_pos = sum(h.get("position", 999) for h in recent) / len(recent)
                kw_map.setdefault(kw, []).append({"url": url, "avg_pos": round(avg_pos, 1)})

        cannibalizations: list[dict] = []
        for kw, urls in kw_map.items():
            if len(urls) >= 2:
                sorted_urls = sorted(urls, key=lambda x: x["avg_pos"])
                cannibalizations.append({
                    "keyword":      kw,
                    "pages":        sorted_urls,
                    "winner":       sorted_urls[0]["url"],
                    "looser":       [u["url"] for u in sorted_urls[1:]],
                    "recommendation": (
                        "Merge or canonicalize weaker pages into the winner, "
                        "or differentiate content intent clearly."
                    ),
                })

        return {
            "total_cannibalization_cases": len(cannibalizations),
            "cases": cannibalizations[:20],
        }

    def _roi_estimate(self, decayed: list[dict]) -> dict[str, Any]:
        """估算内容刷新的 ROI."""
        total_lost_clicks = sum(
            max(0, p.get("prv_clicks", 0) - p.get("cur_clicks", 0))
            for p in decayed
        )
        return {
            "recoverable_clicks_per_90d": total_lost_clicks,
            "note": (
                "Estimated based on current vs previous 90-day click delta. "
                "Actual recovery depends on refresh quality and indexation speed."
            ),
        }
