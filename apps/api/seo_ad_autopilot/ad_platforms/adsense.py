"""Google AdSense platform implementation."""

from __future__ import annotations

from typing import Any, Optional

from .base import (
    AdFormat,
    AdPlatform,
    AdPlatformType,
    AdRecommendation,
    AdSlot,
)


class AdSensePlatform(AdPlatform):
    """Google AdSense - the most common ad platform for small-medium sites."""
    
    @property
    def name(self) -> str:
        return "Google AdSense"
    
    @property
    def platform_type(self) -> AdPlatformType:
        return AdPlatformType.ADSENSE
    
    @property
    def supported_formats(self) -> list[AdFormat]:
        return [
            AdFormat.DISPLAY,
            AdFormat.IN_FEED,
            AdFormat.IN_ARTICLE,
            AdFormat.BANNER,
            AdFormat.VIDEO,
        ]
    
    def is_suitable_for_site(self, site_profile: dict[str, Any]) -> AdRecommendation:
        """Determine if AdSense is suitable for a site."""
        content_type = site_profile.get("content_type", "unknown")
        monthly_visits = site_profile.get("monthly_visits", 0)
        
        # AdSense is suitable for most content sites
        confidence = 0.7
        
        reasons = [
            "AdSense is easy to set up",
            "Low traffic threshold (1000+ monthly visits)",
            "Auto-optimizes ad placements",
            "Supports multiple ad formats",
        ]
        
        if content_type == "content":
            confidence = 0.9
            reasons.append("Content sites are ideal for AdSense")
        elif content_type == "ecommerce":
            confidence = 0.5
            reasons.append("E-commerce sites may benefit more from direct partnerships")
        
        if monthly_visits < 1000:
            confidence = 0.3
            reasons.append("Low traffic may limit earnings")
        
        return AdRecommendation(
            platform=self.name,
            platform_type=self.platform_type,
            confidence=confidence,
            reasons=reasons,
            requirements=[
                "Google AdSense account",
                "Website with original content",
                "Compliance with AdSense policies",
                "Privacy policy and cookie consent",
            ],
            estimated_rpm=2.0 if content_type == "content" else 1.0,
        )
    
    def get_integration_code(self, slot: AdSlot) -> str:
        """Generate AdSense integration code."""
        return f"""<ins class="adsbygoogle"
     style="display:block"
     data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
     data-ad-slot="{slot.selector}"
     data-ad-format="auto"
     data-full-width-responsive="true"></ins>
<script>
     (adsbygoogle = window.adsbygoogle || []).push({{}});
</script>"""
    
    def get_requirements(self) -> list[str]:
        return [
            "Google AdSense account approval",
            "Original, high-quality content",
            "Compliance with Google content policies",
            "Privacy policy page",
            "Cookie consent mechanism",
        ]
    
    def get_policy_constraints(self) -> list[str]:
        return [
            "No click incentivization",
            "No ads on pages with prohibited content",
            "No misleading ad placement",
            "Must disclose ad content",
            "No ads on 404 pages",
        ]
