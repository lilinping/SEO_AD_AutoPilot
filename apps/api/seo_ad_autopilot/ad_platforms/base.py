"""Ad Platform abstraction layer.

Supports multiple ad platforms with auto-discovery and best-match recommendations.

Design principles:
- Each ad platform is a pluggable module
- Unified interface for all ad platforms
- Auto-detect best platforms based on site characteristics
- Support multiple ad ecosystems (Google, programmatic, direct)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AdPlatformType(str, Enum):
    """Ad platform type."""
    ADSENSE = "adsense"
    PROGRAMMATIC = "programmatic"
    NATIVE = "native"
    AFFILIATE = "affiliate"
    DIRECT = "direct"
    OTHER = "other"


class AdFormat(str, Enum):
    """Ad format."""
    DISPLAY = "display"
    NATIVE = "native"
    IN_FEED = "in_feed"
    IN_ARTICLE = "in_article"
    BANNER = "banner"
    VIDEO = "video"
    SPONSORED = "sponsored"
    AFFILIATE_LINK = "affiliate_link"


@dataclass
class AdSlot:
    """Ad slot candidate."""
    selector: str
    format: AdFormat
    position: str
    visibility_score: float
    ux_impact: float
    conversion_risk: float
    recommended_platforms: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdRecommendation:
    """Ad platform recommendation."""
    platform: str
    platform_type: AdPlatformType
    confidence: float
    reasons: list[str]
    requirements: list[str]
    estimated_rpm: Optional[float] = None
    estimated_ctr: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SiteAdProfile:
    """Site's ad-readiness profile."""
    url: str
    ad_grade: str  # A, B, C, D, F
    suitable_platforms: list[AdRecommendation]
    recommended_slots: list[AdSlot]
    exclusion_zones: list[str]
    overall_score: float = 0.0


class AdPlatform(ABC):
    """Base class for all ad platforms."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return human-readable platform name."""
        pass
    
    @property
    @abstractmethod
    def platform_type(self) -> AdPlatformType:
        """Return the platform type."""
        pass
    
    @property
    @abstractmethod
    def supported_formats(self) -> list[AdFormat]:
        """Return supported ad formats."""
        pass
    
    @abstractmethod
    def is_suitable_for_site(self, site_profile: dict[str, Any]) -> AdRecommendation:
        """Determine if this platform is suitable for a site."""
        pass
    
    @abstractmethod
    def get_integration_code(self, slot: AdSlot) -> str:
        """Generate integration code for a slot."""
        pass
    
    def is_available(self) -> bool:
        """Check if this platform is available (API key configured, etc.)."""
        return True
    
    def get_requirements(self) -> list[str]:
        """Get platform requirements."""
        return []
    
    def get_policy_constraints(self) -> list[str]:
        """Get platform policy constraints."""
        return []


class AdPlatformRegistry:
    """Registry for all available ad platforms."""
    
    def __init__(self):
        self._platforms: dict[str, AdPlatform] = {}
    
    def register(self, platform: AdPlatform) -> None:
        """Register an ad platform."""
        self._platforms[platform.name] = platform
    
    def get(self, name: str) -> Optional[AdPlatform]:
        """Get an ad platform by name."""
        return self._platforms.get(name)
    
    def get_all(self) -> list[AdPlatform]:
        """Get all registered platforms."""
        return list(self._platforms.values())
    
    def get_by_type(self, platform_type: AdPlatformType) -> list[AdPlatform]:
        """Get platforms by type."""
        return [
            p for p in self._platforms.values()
            if p.platform_type == platform_type
        ]
    
    def get_available(self) -> list[AdPlatform]:
        """Get all available platforms."""
        return [p for p in self._platforms.values() if p.is_available()]
    
    def recommend_for_site(self, site_profile: dict[str, Any]) -> list[AdRecommendation]:
        """Recommend platforms for a site based on its profile."""
        recommendations = []
        for platform in self._platforms.values():
            if platform.is_available():
                rec = platform.is_suitable_for_site(site_profile)
                if rec.confidence > 0.3:
                    recommendations.append(rec)
        return sorted(recommendations, key=lambda r: r.confidence, reverse=True)


def create_default_registry() -> AdPlatformRegistry:
    """Create a registry with all default ad platforms."""
    from .adsense import AdSensePlatform
    from .mediavine import MediavinePlatform
    from .ezoic import EzoicPlatform
    from .adthrive import AdThrivePlatform
    from .monumetric import MonumetricPlatform
    from .pubmatic import PubMaticPlatform
    
    registry = AdPlatformRegistry()
    
    registry.register(AdSensePlatform())
    registry.register(MediavinePlatform())
    registry.register(EzoicPlatform())
    registry.register(AdThrivePlatform())
    registry.register(MonumetricPlatform())
    registry.register(PubMaticPlatform())
    
    return registry
