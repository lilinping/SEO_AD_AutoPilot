"""Ad Platform Registry with auto-discovery and best-match recommendations."""

from __future__ import annotations

from typing import Any, Optional

from .base import (
    AdPlatform,
    AdPlatformType,
    AdRecommendation,
    AdSlot,
)


class AdPlatformAutoDiscovery:
    """Auto-discover and recommend best ad platforms for a site."""
    
    def __init__(self):
        self._platforms: dict[str, AdPlatform] = {}
    
    def register(self, platform: AdPlatform) -> None:
        """Register an ad platform."""
        self._platforms[platform.name] = platform
    
    def discover_best_platforms(
        self,
        site_profile: dict[str, Any],
    ) -> list[AdRecommendation]:
        """Discover and rank best platforms for a site."""
        recommendations = []
        
        for platform in self._platforms.values():
            if platform.is_available():
                rec = platform.is_suitable_for_site(site_profile)
                if rec.confidence > 0.3:
                    recommendations.append(rec)
        
        # Sort by confidence
        return sorted(recommendations, key=lambda r: r.confidence, reverse=True)
    
    def get_platform_by_name(self, name: str) -> Optional[AdPlatform]:
        """Get a platform by name."""
        return self._platforms.get(name)
    
    def list_all_platforms(self) -> list[dict[str, Any]]:
        """List all registered platforms."""
        return [
            {
                "name": p.name,
                "type": p.platform_type.value,
                "formats": [f.value for f in p.supported_formats],
            }
            for p in self._platforms.values()
        ]


def analyze_site_for_ads(url: str, site_data: dict[str, Any]) -> dict[str, Any]:
    """Analyze a site and recommend best ad platforms.
    
    This is the main entry point for ad platform analysis.
    """
    from .adsense import AdSensePlatform
    from .mediavine import MediavinePlatform
    from .ezoic import EzoicPlatform
    from .adthrive import AdThrivePlatform
    from .monumetric import MonumetricPlatform
    from .pubmatic import PubMaticPlatform
    
    # Create auto-discovery instance
    discovery = AdPlatformAutoDiscovery()
    
    # Register all platforms
    discovery.register(AdSensePlatform())
    discovery.register(MediavinePlatform())
    discovery.register(EzoicPlatform())
    discovery.register(AdThrivePlatform())
    discovery.register(MonumetricPlatform())
    discovery.register(PubMaticPlatform())
    
    # Build site profile from data
    site_profile = {
        "url": url,
        "content_type": _detect_content_type(site_data),
        "monthly_visits": site_data.get("monthly_visits", 0),
        "traffic_sources": site_data.get("traffic_sources", []),
        "audience_location": site_data.get("audience_location", "global"),
        "page_views": site_data.get("page_views", 0),
        "bounce_rate": site_data.get("bounce_rate", 0),
        "avg_time_on_site": site_data.get("avg_time_on_site", 0),
    }
    
    # Discover best platforms
    recommendations = discovery.discover_best_platforms(site_profile)
    
    # Generate ad slot recommendations
    ad_slots = _recommend_ad_slots(site_data)
    
    # Calculate overall ad readiness
    ad_readiness = _calculate_ad_readiness(site_profile, recommendations)
    
    return {
        "url": url,
        "site_profile": site_profile,
        "recommendations": [
            {
                "platform": r.platform,
                "type": r.platform_type.value,
                "confidence": r.confidence,
                "reasons": r.reasons,
                "requirements": r.requirements,
                "estimated_rpm": r.estimated_rpm,
            }
            for r in recommendations
        ],
        "ad_slots": ad_slots,
        "ad_readiness": ad_readiness,
        "next_steps": _generate_next_steps(recommendations, ad_readiness),
    }


def _detect_content_type(site_data: dict[str, Any]) -> str:
    """Detect site content type from data."""
    # Simple detection based on available data
    if site_data.get("has_products"):
        return "ecommerce"
    elif site_data.get("has_blog"):
        return "content"
    elif site_data.get("is_saas"):
        return "saas"
    else:
        return "general"


def _recommend_ad_slots(site_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Recommend ad slot placements."""
    slots = []
    
    # Standard ad slot recommendations
    slots.append({
        "position": "in_article",
        "format": "in_article",
        "visibility_score": 85,
        "ux_impact": "low",
        "recommendation": "Place between paragraphs for high viewability",
    })
    
    slots.append({
        "position": "sidebar",
        "format": "display",
        "visibility_score": 60,
        "ux_impact": "low",
        "recommendation": "Good for desktop, not visible on mobile",
    })
    
    slots.append({
        "position": "below_content",
        "format": "native",
        "visibility_score": 70,
        "ux_impact": "low",
        "recommendation": "Non-intrusive, good for content sites",
    })
    
    slots.append({
        "position": "header",
        "format": "banner",
        "visibility_score": 90,
        "ux_impact": "medium",
        "recommendation": "High visibility but can be intrusive",
    })
    
    # Exclude certain zones
    exclusion_zones = [
        {
            "selector": ".cta, .buy-button, .checkout",
            "reason": "Conversion elements should not have ads",
        },
        {
            "selector": "header, nav",
            "reason": "Navigation should not be modified",
        },
        {
            "selector": "footer",
            "reason": "Footer ads have low viewability",
        },
    ]
    
    return {
        "recommended_slots": slots,
        "exclusion_zones": exclusion_zones,
    }


def _calculate_ad_readiness(
    site_profile: dict[str, Any],
    recommendations: list[AdRecommendation],
) -> dict[str, Any]:
    """Calculate overall ad readiness score."""
    score = 50.0
    factors = []
    
    # Traffic factor
    monthly_visits = site_profile.get("monthly_visits", 0)
    if monthly_visits >= 100000:
        score += 20
        factors.append("high_traffic")
    elif monthly_visits >= 10000:
        score += 10
        factors.append("medium_traffic")
    else:
        score -= 10
        factors.append("low_traffic")
    
    # Content type factor
    content_type = site_profile.get("content_type", "general")
    if content_type == "content":
        score += 15
        factors.append("content_site")
    elif content_type == "ecommerce":
        score += 5
        factors.append("ecommerce_site")
    
    # Platform availability factor
    if recommendations:
        top_confidence = max(r.confidence for r in recommendations)
        score += top_confidence * 10
        factors.append("platforms_available")
    
    # Calculate grade
    if score >= 80:
        grade = "A"
    elif score >= 60:
        grade = "B"
    elif score >= 40:
        grade = "C"
    else:
        grade = "D"
    
    return {
        "score": min(100.0, max(0.0, score)),
        "grade": grade,
        "factors": factors,
        "top_platform": recommendations[0].platform if recommendations else None,
    }


def _generate_next_steps(
    recommendations: list[AdRecommendation],
    ad_readiness: dict[str, Any],
) -> list[str]:
    """Generate next steps for ad implementation."""
    steps = []
    
    if not recommendations:
        steps.append("Improve content and traffic before considering ads")
        return steps
    
    top_platform = recommendations[0]
    
    steps.append(f"Sign up for {top_platform.platform}")
    steps.extend(top_platform.requirements[:3])
    
    if ad_readiness.get("grade") in ["A", "B"]:
        steps.append("Implement recommended ad slots")
        steps.append("A/B test ad placements")
    else:
        steps.append("Focus on increasing traffic first")
        steps.append("Improve content quality")
    
    return steps
