"""PubMatic platform implementation."""

from __future__ import annotations

from typing import Any

from .base import (
    AdFormat,
    AdPlatform,
    AdPlatformType,
    AdRecommendation,
    AdSlot,
)


class PubMaticPlatform(AdPlatform):
    """PubMatic - programmatic advertising platform."""
    
    @property
    def name(self) -> str:
        return "PubMatic"
    
    @property
    def platform_type(self) -> AdPlatformType:
        return AdPlatformType.PROGRAMMATIC
    
    @property
    def supported_formats(self) -> list[AdFormat]:
        return [
            AdFormat.DISPLAY,
            AdFormat.NATIVE,
            AdFormat.VIDEO,
        ]
    
    def is_suitable_for_site(self, site_profile: dict[str, Any]) -> AdRecommendation:
        content_type = site_profile.get("content_type", "unknown")
        monthly_visits = site_profile.get("monthly_visits", 0)
        
        confidence = 0.4
        reasons = []
        
        if monthly_visits >= 50000:
            confidence = 0.7
            reasons = [
                "PubMatic offers programmatic demand",
                "Header bidding integration",
                "Global demand partners",
                "Advanced yield optimization",
            ]
        elif monthly_visits >= 10000:
            confidence = 0.5
            reasons.append("Can start with basic integration")
        else:
            reasons.append("Higher traffic recommended for better yields")
        
        return AdRecommendation(
            platform=self.name,
            platform_type=self.platform_type,
            confidence=confidence,
            reasons=reasons,
            requirements=[
                "PubMatic account",
                "Integration with header bidding",
                "Original content",
            ],
            estimated_rpm=12.0 if confidence > 0.5 else None,
        )
    
    def get_integration_code(self, slot: AdSlot) -> str:
        return f"""<div id="pub-{slot.selector}" class="pub-ad-slot"></div>
<script>
  var pubScript = document.createElement('script');
  pubScript.src = 'https://ads.pubmatic.com/AdServer/js/pugreen/YOUR_TAG_ID.js';
  pubScript.async = true;
  document.body.appendChild(pubScript);
</script>"""
    
    def get_requirements(self) -> list[str]:
        return [
            "PubMatic account",
            "Header bidding setup",
            "Original content",
        ]
    
    def get_policy_constraints(self) -> list[str]:
        return [
            "No incentivized traffic",
            "No adult content",
            "Must have privacy policy",
        ]
