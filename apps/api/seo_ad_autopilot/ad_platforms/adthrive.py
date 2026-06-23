"""AdThrive/Raptive platform implementation."""

from __future__ import annotations

from typing import Any

from .base import (
    AdFormat,
    AdPlatform,
    AdPlatformType,
    AdRecommendation,
    AdSlot,
)


class AdThrivePlatform(AdPlatform):
    """AdThrive (now Raptive) - premium ad management."""
    
    @property
    def name(self) -> str:
        return "AdThrive"
    
    @property
    def platform_type(self) -> AdPlatformType:
        return AdPlatformType.PROGRAMMATIC
    
    @property
    def supported_formats(self) -> list[AdFormat]:
        return [
            AdFormat.DISPLAY,
            AdFormat.NATIVE,
            AdFormat.IN_FEED,
            AdFormat.IN_ARTICLE,
            AdFormat.VIDEO,
        ]
    
    def is_suitable_for_site(self, site_profile: dict[str, Any]) -> AdRecommendation:
        content_type = site_profile.get("content_type", "unknown")
        monthly_visits = site_profile.get("monthly_visits", 0)
        
        confidence = 0.2
        reasons = []
        
        if monthly_visits >= 100000:
            confidence = 0.9
            reasons = [
                "AdThrive offers premium RPMs",
                "Dedicated account management",
                "Advanced ad optimization",
                "Excellent for lifestyle content",
            ]
        elif monthly_visits >= 50000:
            confidence = 0.5
            reasons.append("Meets minimum traffic requirement")
        else:
            reasons.append("Requires 100k+ monthly pageviews")
        
        return AdRecommendation(
            platform=self.name,
            platform_type=self.platform_type,
            confidence=confidence,
            reasons=reasons,
            requirements=[
                "100,000+ monthly pageviews",
                "Original, high-quality content",
                "US-based traffic preferred",
            ],
            estimated_rpm=20.0 if confidence > 0.5 else None,
        )
    
    def get_integration_code(self, slot: AdSlot) -> str:
        return f"""<div id="at-{slot.selector}" class="at-ad-slot"></div>
<script>
  var atScript = document.createElement('script');
  atScript.src = 'https://static.cdn-yourdomain.com/at.js';
  atScript.async = true;
  document.body.appendChild(atScript);
</script>"""
    
    def get_requirements(self) -> list[str]:
        return [
            "100,000+ monthly pageviews",
            "Original, high-quality content",
            "US-based traffic",
        ]
    
    def get_policy_constraints(self) -> list[str]:
        return [
            "No incentivized traffic",
            "No adult content",
            "Must have privacy policy",
        ]
