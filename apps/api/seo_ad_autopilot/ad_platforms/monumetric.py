"""Monumetric platform implementation."""

from __future__ import annotations

from typing import Any

from .base import (
    AdFormat,
    AdPlatform,
    AdPlatformType,
    AdRecommendation,
    AdSlot,
)


class MonumetricPlatform(AdPlatform):
    """Monumetric - premium ad management for mid-size publishers."""
    
    @property
    def name(self) -> str:
        return "Monumetric"
    
    @property
    def platform_type(self) -> AdPlatformType:
        return AdPlatformType.PROGRAMMATIC
    
    @property
    def supported_formats(self) -> list[AdFormat]:
        return [
            AdFormat.DISPLAY,
            AdFormat.NATIVE,
            AdFormat.IN_FEED,
            AdFormat.VIDEO,
        ]
    
    def is_suitable_for_site(self, site_profile: dict[str, Any]) -> AdRecommendation:
        content_type = site_profile.get("content_type", "unknown")
        monthly_visits = site_profile.get("monthly_visits", 0)
        
        confidence = 0.3
        reasons = []
        
        if monthly_visits >= 10000 and content_type == "content":
            confidence = 0.8
            reasons = [
                "Monumetric specializes in content sites",
                "Good RPMs for mid-size publishers",
                "Dedicated support team",
                "Easy integration",
            ]
        elif monthly_visits >= 10000:
            confidence = 0.5
            reasons.append("Meets minimum traffic requirement")
        else:
            reasons.append("Requires 10k+ monthly pageviews")
        
        return AdRecommendation(
            platform=self.name,
            platform_type=self.platform_type,
            confidence=confidence,
            reasons=reasons,
            requirements=[
                "10,000+ monthly pageviews",
                "Original content",
                "Compliance with Monumetric policies",
            ],
            estimated_rpm=10.0 if confidence > 0.5 else None,
        )
    
    def get_integration_code(self, slot: AdSlot) -> str:
        return f"""<div id="mon-{slot.selector}" class="mon-ad-slot"></div>
<script>
  var monScript = document.createElement('script');
  monScript.src = 'https://config.monumetric.com/script/YOUR_TAG_ID.js';
  monScript.async = true;
  document.body.appendChild(monScript);
</script>"""
    
    def get_requirements(self) -> list[str]:
        return [
            "10,000+ monthly pageviews",
            "Original content",
            "Compliance with Monumetric policies",
        ]
    
    def get_policy_constraints(self) -> list[str]:
        return [
            "No incentivized clicks",
            "No adult content",
            "Must have privacy policy",
        ]
