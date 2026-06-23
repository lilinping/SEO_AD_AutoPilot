"""Mediavine platform implementation."""

from __future__ import annotations

from typing import Any

from .base import (
    AdFormat,
    AdPlatform,
    AdPlatformType,
    AdRecommendation,
    AdSlot,
)


class MediavinePlatform(AdPlatform):
    """Mediavine - premium ad management for content creators."""
    
    @property
    def name(self) -> str:
        return "Mediavine"
    
    @property
    def platform_type(self) -> AdPlatformType:
        return AdPlatformType.PROGRAMMATIC
    
    @property
    def supported_formats(self) -> list[AdFormat]:
        return [
            AdFormat.DISPLAY,
            AdFormat.IN_FEED,
            AdFormat.IN_ARTICLE,
            AdFormat.VIDEO,
        ]
    
    def is_suitable_for_site(self, site_profile: dict[str, Any]) -> AdRecommendation:
        content_type = site_profile.get("content_type", "unknown")
        monthly_visits = site_profile.get("monthly_visits", 0)
        
        confidence = 0.3
        reasons = []
        
        if content_type == "content" and monthly_visits >= 50000:
            confidence = 0.9
            reasons = [
                "Mediavine is ideal for high-traffic content sites",
                "Excellent RPM for lifestyle, food, travel blogs",
                "Managed service with dedicated support",
                "Advanced ad optimization",
            ]
        elif monthly_visits >= 10000:
            confidence = 0.6
            reasons.append("Meets minimum traffic requirement")
        else:
            reasons.append("Requires 50k+ monthly sessions")
        
        return AdRecommendation(
            platform=self.name,
            platform_type=self.platform_type,
            confidence=confidence,
            reasons=reasons,
            requirements=[
                "50,000+ monthly sessions",
                "Original, high-quality content",
                "US-based traffic preferred",
                "Compliance with Mediavine policies",
            ],
            estimated_rpm=15.0 if confidence > 0.5 else None,
        )
    
    def get_integration_code(self, slot: AdSlot) -> str:
        return f"""<div id="mp-{slot.selector}" class="mp-ad-slot"></div>
<script>
  (function() {{
    var script = document.createElement('script');
    script.src = 'https://scripts.mediavine.com/tags/YOUR_TAG_ID.js';
    script.async = true;
    document.head.appendChild(script);
  }})();
</script>"""
    
    def get_requirements(self) -> list[str]:
        return [
            "50,000+ monthly sessions",
            "Original, high-quality content",
            "US-based traffic",
            "Good standing with ad networks",
        ]
    
    def get_policy_constraints(self) -> list[str]:
        return [
            "No incentivized traffic",
            "No adult content",
            "No misleading content",
            "Must have privacy policy",
        ]
