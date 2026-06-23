"""Ezoic platform implementation."""

from __future__ import annotations

from typing import Any

from .base import (
    AdFormat,
    AdPlatform,
    AdPlatformType,
    AdRecommendation,
    AdSlot,
)


class EzoicPlatform(AdPlatform):
    """Ezoic - AI-driven ad optimization platform."""
    
    @property
    def name(self) -> str:
        return "Ezoic"
    
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
        
        confidence = 0.5
        reasons = []
        
        if monthly_visits >= 10000:
            confidence = 0.8
            reasons = [
                "Ezoic's AI optimizes ad placements",
                "No minimum traffic requirement for basic features",
                "Free plan available",
                "Advanced analytics and insights",
            ]
        elif monthly_visits >= 1000:
            confidence = 0.6
            reasons.append("Basic plan available")
        else:
            reasons.append("Higher traffic yields better optimization")
        
        return AdRecommendation(
            platform=self.name,
            platform_type=self.platform_type,
            confidence=confidence,
            reasons=reasons,
            requirements=[
                "Ezoic account",
                "Original content",
                "Compliance with Ezoic policies",
            ],
            estimated_rpm=8.0 if confidence > 0.5 else None,
        )
    
    def get_integration_code(self, slot: AdSlot) -> str:
        return f"""<div id="ezoic-{slot.selector}" class="ezoic-ad-slot"></div>
<script>
  var ezoad = document.createElement('script');
  ezoad.src = '//go.ezojs.com/ezoic.js';
  ezoad.async = true;
  document.body.appendChild(ezoad);
</script>"""
    
    def get_requirements(self) -> list[str]:
        return [
            "Ezoic account",
            "Original content",
            "Compliance with Ezoic policies",
        ]
    
    def get_policy_constraints(self) -> list[str]:
        return [
            "No incentivized clicks",
            "No adult content",
            "Must disclose ad content",
        ]
