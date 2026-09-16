"""Header Bidding Ad Platform — Prebid.js multi-SSP integration.

继承 AdPlatform 基类, 实现:
- PrebidHeaderBiddingPlatform  多 SSP 竞价平台聚合适配器
"""

from __future__ import annotations

from typing import Any

from .base import AdFormat, AdPlatform, AdPlatformType, AdRecommendation, AdSlot


class PrebidHeaderBiddingPlatform(AdPlatform):
    """Prebid.js Header Bidding 平台 — 聚合多个 SSP 进行实时竞价.

    核心优势:
    - 多 SSP 同时竞价 → RPM 通常提升 30–80%
    - 透明竞价 (open-source Prebid.js)
    - 支持 Floor Price 优化
    - 可与现有 AdSense / GAM 无缝叠加

    最低流量要求: 无 (但 <10K pv/月 效益有限)
    推荐适用: 月 PV >50K 的内容站
    """

    # RPM 基准 (2026 Prebid publisher survey, Tier-1 traffic)
    RPM_RANGES = {
        "tier1":  {"min": 8.0,  "max": 25.0,  "avg": 15.0},   # US/UK/AU/CA
        "tier2":  {"min": 3.0,  "max": 10.0,  "avg": 6.0},    # EU/JP/KR
        "tier3":  {"min": 0.5,  "max": 3.0,   "avg": 1.5},    # rest of world
    }

    SUPPORTED_SSPS = [
        "AppNexus (Xandr)", "PubMatic", "OpenX", "Magnite (Rubicon)",
        "Index Exchange", "Sovrn", "TripleLift", "Criteo", "33Across",
        "SmartAdServer",
    ]

    # Minimum viable traffic for meaningful header bidding
    MIN_MONTHLY_PV = 10_000

    @property
    def name(self) -> str:
        return "Prebid Header Bidding"

    @property
    def platform_type(self) -> AdPlatformType:
        return AdPlatformType.PROGRAMMATIC

    @property
    def supported_formats(self) -> list[AdFormat]:
        return [
            AdFormat.DISPLAY,
            AdFormat.BANNER,
            AdFormat.IN_ARTICLE,
            AdFormat.IN_FEED,
            AdFormat.NATIVE,
            AdFormat.VIDEO,
        ]

    def is_available(self) -> bool:
        """Prebid.js 是开源的, 任何站点均可使用."""
        return True

    def get_requirements(self) -> list[str]:
        return [
            "Monthly pageviews > 10,000 for meaningful bidding density",
            "SSL certificate (HTTPS) required for all SSPs",
            "JavaScript-enabled pages (standard)",
            "Prebid.js v8+ loaded from CDN or self-hosted",
            "At least 2–3 SSP accounts registered and approved",
            "Google Ad Manager (GAM) account recommended as primary ad server",
        ]

    def get_policy_constraints(self) -> list[str]:
        return [
            "Ad refresh minimum interval: 30 seconds (all major SSPs)",
            "Viewability requirement: >50% in-view for ≥1 second per refresh",
            "GDPR/CCPA consent management required for EU/CA traffic",
            "Avoid sticky/fixed-position ads that float on scroll (policy violation)",
            "Max 3 ads above the fold (IAB Best Practices 2025)",
            "No auto-playing video ads with sound",
        ]

    def is_suitable_for_site(self, site_profile: dict[str, Any]) -> AdRecommendation:
        """Evaluate site suitability for Prebid header bidding."""
        monthly_pv   = site_profile.get("monthly_pageviews", 0)
        traffic_tier = site_profile.get("traffic_tier", "tier3")   # tier1/2/3
        existing_ads = site_profile.get("current_ad_platform", "")
        https        = site_profile.get("https", True)
        content_type = site_profile.get("content_type", "blog")

        # Base confidence
        confidence = 0.50
        reasons: list[str] = []

        # Traffic volume scoring
        if monthly_pv >= 100_000:
            confidence += 0.25
            reasons.append(f"High traffic ({monthly_pv:,} pv/mo) — strong bid density")
        elif monthly_pv >= self.MIN_MONTHLY_PV:
            confidence += 0.12
            reasons.append(f"Adequate traffic ({monthly_pv:,} pv/mo) for header bidding")
        else:
            confidence -= 0.15
            reasons.append(
                f"Low traffic ({monthly_pv:,} pv/mo) — "
                f"header bidding less effective below {self.MIN_MONTHLY_PV:,} pv/mo"
            )

        # Traffic tier (geography)
        if traffic_tier == "tier1":
            confidence += 0.20
            reasons.append("Tier-1 traffic (US/UK/AU) — high CPM bids expected")
        elif traffic_tier == "tier2":
            confidence += 0.10
            reasons.append("Tier-2 traffic — moderate CPM, good for HB")
        else:
            confidence += 0.02
            reasons.append("Tier-3 traffic — lower CPM, consider lower-overhead solutions first")

        # HTTPS requirement
        if not https:
            confidence -= 0.30
            reasons.append("HTTPS required — most SSPs won't serve on HTTP")
        else:
            reasons.append("HTTPS enabled — SSP compatibility confirmed")

        # Already on AdSense/GAM — HB adds significant lift
        if "adsense" in existing_ads.lower():
            confidence += 0.08
            reasons.append("Currently on AdSense — HB adds competition and typically lifts RPM 30–80%")

        # Content type suitability
        content_good = ["blog", "news", "reviews", "guides", "tutorials"]
        if content_type.lower() in content_good:
            confidence += 0.05
            reasons.append(f"Content type '{content_type}' is well-monetized through display HB")

        # RPM estimate
        rpm_data = self.RPM_RANGES.get(traffic_tier, self.RPM_RANGES["tier3"])

        return AdRecommendation(
            platform=self.name,
            platform_type=self.platform_type,
            confidence=round(min(0.99, max(0.01, confidence)), 2),
            reasons=reasons,
            requirements=self.get_requirements(),
            estimated_rpm=rpm_data["avg"],
            metadata={
                "rpm_range":      f"${rpm_data['min']:.1f}–${rpm_data['max']:.1f}",
                "supported_ssps": self.SUPPORTED_SSPS,
                "lift_vs_single": "+30–80% RPM vs single ad network",
                "setup_effort":   "medium (2–4 hours with SEO-AD AutoPilot config generator)",
                "open_source":    True,
                "prebid_docs":    "https://docs.prebid.org",
            },
        )

    def get_integration_code(self, slot: AdSlot) -> str:
        """Generate Prebid.js ad unit snippet for a specific slot."""
        sizes_map = {
            "above_fold": [[728, 90], [970, 90]],
            "in_content": [[300, 250], [300, 600]],
            "sidebar":    [[300, 250], [160, 600]],
            "mobile":     [[320, 50], [320, 100]],
            "footer":     [[728, 90], [300, 250]],
        }
        sizes = sizes_map.get(slot.position, [[300, 250]])

        return f"""// Prebid.js Ad Unit — {slot.selector} ({slot.position})
var adUnit_{slot.selector.replace('#','').replace('.','').replace('-','_')} = {{
  code: '{slot.selector}',
  mediaTypes: {{
    banner: {{
      sizes: {sizes},
    }},
  }},
  bids: [
    {{
      bidder: 'appnexus',
      params: {{ placementId: 'REPLACE_WITH_APPNEXUS_ID' }},
    }},
    {{
      bidder: 'pubmatic',
      params: {{ publisherId: 'REPLACE_WITH_PUBMATIC_ID', adSlot: 'REPLACE_WITH_SLOT' }},
    }},
    {{
      bidder: 'ix',
      params: {{ siteId: 'REPLACE_WITH_IX_SITE_ID', size: {sizes[0]} }},
    }},
    {{
      bidder: 'sovrn',
      params: {{ tagid: 'REPLACE_WITH_SOVRN_TAGID' }},
    }},
  ],
}};

// Add to Prebid
pbjs.que.push(function() {{
  pbjs.addAdUnits(adUnit_{slot.selector.replace('#','').replace('.','').replace('-','_')});
}});

// GAM slot definition
googletag.cmd.push(function() {{
  googletag.defineSlot(
    '/REPLACE_WITH_GAM_NETWORK_ID/REPLACE_WITH_AD_UNIT_PATH',
    {sizes},
    '{slot.selector}'
  ).addService(googletag.pubads());
  googletag.pubads().enableSingleRequest();
  googletag.enableServices();
}});"""

    def estimate_revenue_impact(
        self,
        current_rpm: float,
        monthly_pv:  int,
    ) -> dict[str, Any]:
        """估算切换到 Header Bidding 后的收益提升."""
        min_lift = 0.30
        max_lift = 0.80
        mid_lift = 0.50

        new_rpm_low  = round(current_rpm * (1 + min_lift), 2)
        new_rpm_high = round(current_rpm * (1 + max_lift), 2)
        new_rpm_mid  = round(current_rpm * (1 + mid_lift), 2)

        rev_current  = round(current_rpm * monthly_pv / 1000, 2)
        rev_new_low  = round(new_rpm_low  * monthly_pv / 1000, 2)
        rev_new_high = round(new_rpm_high * monthly_pv / 1000, 2)

        return {
            "current_rpm":       current_rpm,
            "current_monthly_rev": f"${rev_current:,.2f}",
            "projected_rpm":     f"${new_rpm_low:.2f}–${new_rpm_high:.2f}",
            "projected_monthly": f"${rev_new_low:,.2f}–${rev_new_high:,.2f}",
            "monthly_uplift":    f"+${rev_new_low - rev_current:,.2f}–${rev_new_high - rev_current:,.2f}",
            "source":            "Prebid.org 2025 Publisher Impact Study",
        }
