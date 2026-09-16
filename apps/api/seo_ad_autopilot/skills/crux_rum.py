"""CrUX / RUM Skills — 真实用户 Core Web Vitals 采集 + RUM 注入.

P1 缺口补全:
- CrUXCollectorSkill     从 Google CrUX API 采集真实用户 LCP/INP/CLS 数据
- RUMSnippetInjectorSkill 生成轻量 RUM 监控代码片段, 可注入任意页面
"""

from __future__ import annotations

import json
import time
from typing import Any

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


# ── CWV 评分阈值 (Google 官方 2024+ 标准) ──────────────────────────────────
CWV_THRESHOLDS = {
    "lcp": {"good": 2500,  "needs_improvement": 4000},   # ms
    "inp": {"good": 200,   "needs_improvement": 500},    # ms
    "cls": {"good": 0.1,   "needs_improvement": 0.25},   # score
    "fcp": {"good": 1800,  "needs_improvement": 3000},   # ms
    "ttfb":{"good": 800,   "needs_improvement": 1800},   # ms
}


def _cwv_label(metric: str, value: float) -> str:
    t = CWV_THRESHOLDS.get(metric)
    if not t:
        return "unknown"
    if value <= t["good"]:
        return "good"
    if value <= t["needs_improvement"]:
        return "needs_improvement"
    return "poor"


# ═══════════════════════════════════════════════════════════════════
# 1. CrUXCollectorSkill
# ═══════════════════════════════════════════════════════════════════

class CrUXCollectorSkill(Skill):
    """从 Google CrUX API 采集真实用户 Core Web Vitals 数据.

    输出 LCP / INP / CLS / FCP / TTFB 的:
    - p75 值及 Good/NI/Poor 分布
    - 与上次快照的 delta
    - 超预算阈值时触发 deploy_blocker 信号
    """

    # 部署阻断阈值 (比 Google "needs improvement" 稍宽松)
    DEPLOY_BLOCK_THRESHOLDS = {
        "lcp":  4500,   # ms  → 超过此值阻断部署
        "inp":  600,    # ms
        "cls":  0.30,   # score
    }

    @property
    def name(self) -> str:
        return "CrUXCollector"

    @property
    def description(self) -> str:
        return (
            "Collect real-user Core Web Vitals (LCP, INP, CLS, FCP, TTFB) from the "
            "Google CrUX API. Compares p75 values against Good/NI/Poor thresholds, "
            "diffs against previous snapshots, and raises a deploy_blocker signal "
            "when any metric exceeds the configured hard limit."
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

        url           = params.get("url", "")
        form_factor   = params.get("form_factor", "PHONE")   # PHONE | DESKTOP | ALL_FORM_FACTORS
        prev_snapshot = params.get("prev_snapshot", {})       # {metric: p75_value}
        block_on_poor = params.get("block_deploy_on_poor", True)

        if not url:
            return self._create_output(
                success=False, error="url is required", execution_time_ms=0
            )

        # Context may provide CrUX data already fetched by the crawler
        crux_raw = ctx.get("crux_data", {})

        if not crux_raw:
            # No live API call here — return a "data unavailable" result
            # with the API call spec so the Coordinator can schedule it
            return self._create_output(
                success=True,
                result={
                    "url":         url,
                    "form_factor": form_factor,
                    "status":      "data_unavailable",
                    "message":     "CrUX data not in context. Trigger CrUX API fetch first.",
                    "api_spec": {
                        "endpoint": "https://chromeuxreport.googleapis.com/v1/records:queryRecord",
                        "method":   "POST",
                        "body": {
                            "url":        url,
                            "formFactor": form_factor,
                            "metrics": ["largest_contentful_paint",
                                        "interaction_to_next_paint",
                                        "cumulative_layout_shift",
                                        "first_contentful_paint",
                                        "experimental_time_to_first_byte"],
                        },
                        "auth": "API_KEY query param",
                    },
                },
                execution_time_ms=int((time.time() - t0) * 1000),
            )

        # ── Parse CrUX API response ──────────────────────────────────────
        metric_map = {
            "largest_contentful_paint":    "lcp",
            "interaction_to_next_paint":   "inp",
            "cumulative_layout_shift":     "cls",
            "first_contentful_paint":      "fcp",
            "experimental_time_to_first_byte": "ttfb",
        }

        metrics: dict[str, Any] = {}
        blockers: list[str] = []
        warnings: list[str] = []

        record = crux_raw.get("record", crux_raw)
        raw_metrics = record.get("metrics", {})

        for api_name, short in metric_map.items():
            m = raw_metrics.get(api_name, {})
            if not m:
                continue

            p75 = m.get("percentiles", {}).get("p75")
            hist = m.get("histogram", [])
            good_pct = ni_pct = poor_pct = 0.0
            if len(hist) >= 3:
                good_pct = hist[0].get("density", 0) * 100
                ni_pct   = hist[1].get("density", 0) * 100
                poor_pct = hist[2].get("density", 0) * 100

            label   = _cwv_label(short, p75) if p75 is not None else "unknown"
            prev_p75 = prev_snapshot.get(short)
            delta    = round(p75 - prev_p75, 3) if (p75 is not None and prev_p75 is not None) else None
            trend    = (
                "improving" if delta is not None and (
                    delta < 0 if short != "cls" else delta < 0
                ) else
                "degrading" if delta is not None else
                "unknown"
            )

            metrics[short] = {
                "p75":       p75,
                "label":     label,
                "good_pct":  round(good_pct, 1),
                "ni_pct":    round(ni_pct, 1),
                "poor_pct":  round(poor_pct, 1),
                "prev_p75":  prev_p75,
                "delta":     delta,
                "trend":     trend,
                "threshold": CWV_THRESHOLDS.get(short),
            }

            # Deploy blocker check
            block_thresh = self.DEPLOY_BLOCK_THRESHOLDS.get(short)
            if block_thresh and p75 is not None and block_on_poor:
                if p75 > block_thresh:
                    blockers.append(
                        f"{short.upper()} p75={p75} exceeds deploy limit {block_thresh}"
                    )

            if label == "poor":
                warnings.append(
                    f"{short.upper()} is POOR (p75={p75}) — "
                    f"affects {round(poor_pct, 1)}% of real users"
                )

        # ── Overall CWV pass/fail ─────────────────────────────────────────
        core = ["lcp", "inp", "cls"]
        core_labels = [metrics[m]["label"] for m in core if m in metrics]
        overall = (
            "good"             if all(l == "good"             for l in core_labels) else
            "needs_improvement"if all(l != "poor"             for l in core_labels) else
            "poor"
        )

        # ── Improvement recommendations ──────────────────────────────────
        recs: list[dict] = []
        if "lcp" in metrics and metrics["lcp"]["label"] != "good":
            recs.append({
                "metric": "LCP",
                "actions": [
                    "Preload the LCP image resource with <link rel=preload>",
                    "Use a CDN for images; convert to WebP/AVIF format",
                    "Eliminate render-blocking resources (unused CSS/JS)",
                    "Check server response time (TTFB); use edge caching",
                ],
            })
        if "inp" in metrics and metrics["inp"]["label"] != "good":
            recs.append({
                "metric": "INP",
                "actions": [
                    "Minimize long JavaScript tasks (>50ms) — use code splitting",
                    "Yield to main thread with scheduler.yield() or setTimeout(0)",
                    "Remove or defer third-party scripts (ads, analytics, chat widgets)",
                    "Use web workers for CPU-intensive computations",
                ],
            })
        if "cls" in metrics and metrics["cls"]["label"] != "good":
            recs.append({
                "metric": "CLS",
                "actions": [
                    "Add explicit width/height to all images and video elements",
                    "Reserve space for ads with min-height CSS before they load",
                    "Avoid dynamically injecting content above existing content",
                    "Use font-display: optional or swap with font preloading",
                ],
            })

        ms = int((time.time() - t0) * 1000)
        return self._create_output(
            success=True,
            result={
                "url":           url,
                "form_factor":   form_factor,
                "overall_cwv":   overall,
                "metrics":       metrics,
                "deploy_blockers": blockers,
                "warnings":      warnings,
                "recommendations": recs,
                "snapshot_date": time.strftime("%Y-%m-%d", time.gmtime()),
                "deploy_allowed": len(blockers) == 0,
                "summary": (
                    f"CrUX ({form_factor}): Overall={overall}. "
                    f"Blockers={len(blockers)}, Warnings={len(warnings)}."
                ),
            },
            execution_time_ms=ms,
        )


# ═══════════════════════════════════════════════════════════════════
# 2. RUMSnippetInjectorSkill
# ═══════════════════════════════════════════════════════════════════

class RUMSnippetInjectorSkill(Skill):
    """生成轻量 RUM (Real User Monitoring) 代码片段, 通过 web-vitals.js 采集真实 CWV.

    生成的代码片段:
    - 基于 Google web-vitals 库 (官方, 3KB gzip)
    - 支持自定义上报端点 (或 Google Analytics 4)
    - 支持采样率控制 (默认 100%)
    - 部署方式: Script 注入 / CMS 插件 / GTM 自定义 HTML
    """

    WEB_VITALS_CDN = "https://unpkg.com/web-vitals@4/dist/web-vitals.attribution.iife.min.js"

    @property
    def name(self) -> str:
        return "RUMSnippetInjector"

    @property
    def description(self) -> str:
        return (
            "Generate a lightweight RUM snippet based on Google web-vitals.js that "
            "collects LCP, INP, CLS, FCP, and TTFB from real users. "
            "Supports custom analytics endpoints, GA4 events, or console logging. "
            "Generates GTM-ready, async, and CMS-paste versions."
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

        endpoint    = params.get("endpoint", "")        # custom POST endpoint
        ga4_id      = params.get("ga4_measurement_id", "")
        sample_rate = params.get("sample_rate", 1.0)    # 0–1
        debug_mode  = params.get("debug_mode", False)
        site_id     = params.get("site_id", "site")

        # ── Choose reporter function ─────────────────────────────────────
        if ga4_id:
            reporter = self._ga4_reporter(ga4_id)
        elif endpoint:
            reporter = self._endpoint_reporter(endpoint)
        else:
            reporter = self._console_reporter()

        # ── Core snippet ─────────────────────────────────────────────────
        sample_guard = (
            f"if (Math.random() > {sample_rate}) return;"
            if sample_rate < 1.0 else ""
        )
        debug_line = (
            "console.log('[RUM]', metric.name, metric.value, metric);"
            if debug_mode else ""
        )

        snippet = f"""<!-- SEO-AD AutoPilot: Real User Monitoring (web-vitals v4) -->
<script>
(function() {{
  'use strict';
  var SITE_ID = '{site_id}';

  function sendMetric(metric) {{
    {sample_guard}
    {debug_line}
    {reporter}
  }}

  // Load web-vitals library async and register all core metrics
  var script = document.createElement('script');
  script.src = '{self.WEB_VITALS_CDN}';
  script.async = true;
  script.onload = function() {{
    if (typeof webVitals === 'undefined') return;
    webVitals.onLCP(sendMetric,  {{reportAllChanges: false}});
    webVitals.onINP(sendMetric,  {{reportAllChanges: false}});
    webVitals.onCLS(sendMetric,  {{reportAllChanges: true}});
    webVitals.onFCP(sendMetric,  {{reportAllChanges: false}});
    webVitals.onTTFB(sendMetric, {{reportAllChanges: false}});
  }};
  document.head.appendChild(script);
}})();
</script>"""

        # ── GTM version (Custom HTML tag) ─────────────────────────────────
        gtm_snippet = snippet.replace("<!-- SEO-AD AutoPilot: Real User Monitoring (web-vitals v4) -->\n", "")

        # ── WordPress / PHP include version ──────────────────────────────
        wp_snippet = (
            "<?php\n"
            "// Add to functions.php — SEO-AD AutoPilot RUM\n"
            "add_action('wp_head', function() {\n"
            f"    echo '{snippet.strip()}';\n"
            "}, 999);\n"
            "?>"
        )

        ms = int((time.time() - t0) * 1000)
        return self._create_output(
            success=True,
            result={
                "snippet":              snippet,
                "gtm_snippet":          gtm_snippet,
                "wordpress_snippet":    wp_snippet,
                "web_vitals_cdn":       self.WEB_VITALS_CDN,
                "metrics_tracked":      ["LCP", "INP", "CLS", "FCP", "TTFB"],
                "sample_rate":          sample_rate,
                "reporter_type":        "ga4" if ga4_id else "endpoint" if endpoint else "console",
                "deployment_options": [
                    "Script injection via Universal Script (SEO-AD AutoPilot)",
                    "GTM Custom HTML tag (paste gtm_snippet)",
                    "WordPress functions.php (paste wordpress_snippet)",
                    "Direct <head> paste",
                ],
                "size_estimate_bytes":  len(snippet.encode()),
                "performance_impact":   "Negligible — async load, < 3KB gzip",
            },
            execution_time_ms=ms,
        )

    # ── Reporter templates ─────────────────────────────────────────────────

    def _ga4_reporter(self, ga4_id: str) -> str:
        return f"""
    if (typeof gtag === 'function') {{
      gtag('event', metric.name, {{
        event_category: 'Web Vitals',
        value: Math.round(metric.name === 'CLS' ? metric.value * 1000 : metric.value),
        event_label: metric.id,
        non_interaction: true,
        send_to: '{ga4_id}',
        metric_id: metric.id,
        metric_value: metric.value,
        metric_delta: metric.delta,
        site_id: SITE_ID,
      }});
    }}"""

    def _endpoint_reporter(self, endpoint: str) -> str:
        return f"""
    var body = JSON.stringify({{
      name: metric.name,
      value: metric.value,
      id: metric.id,
      delta: metric.delta,
      rating: metric.rating,
      navigationType: metric.navigationType,
      url: location.href,
      site_id: SITE_ID,
      ts: Date.now(),
    }});
    if (navigator.sendBeacon) {{
      navigator.sendBeacon('{endpoint}', new Blob([body], {{type: 'application/json'}}));
    }} else {{
      fetch('{endpoint}', {{method:'POST', body:body, keepalive:true, headers:{{'Content-Type':'application/json'}}}});
    }}"""

    def _console_reporter(self) -> str:
        return """
    console.table({
      metric: metric.name,
      value: metric.value,
      rating: metric.rating,
      id: metric.id,
    });"""
