"""Ad Platforms router.

Endpoints:
  POST /api/ads/analyze             – analyze site & recommend ad platforms
  GET  /api/ads/platforms           – list all registered platforms
  GET  /api/ads/platforms/{name}    – get platform details
  POST /api/ads/header-bidding      – generate header-bidding config
  POST /api/ads/floor-price         – optimize floor prices
"""

from __future__ import annotations

import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/ads", tags=["ad-platforms"])


# ── Request models ────────────────────────────────────────────────────────────

class AdAnalysisRequest(BaseModel):
    url: str
    monthly_visits: int = 0
    page_views: int = 0
    bounce_rate: float = 0.0
    avg_time_on_site: float = 0.0
    audience_location: str = "global"
    has_products: bool = False
    has_blog: bool = True
    is_saas: bool = False
    traffic_sources: list[str] = []


class HeaderBiddingRequest(BaseModel):
    url: str
    ad_units: list[dict[str, Any]] = []
    target_bidders: list[str] = []   # ["appnexus", "rubicon", "pubmatic", ...]
    currency: str = "USD"
    timeout_ms: int = 1000


class FloorPriceRequest(BaseModel):
    url: str
    current_ecpm: float = 0.0
    ad_units: list[dict[str, Any]] = []
    target_fill_rate: float = 0.8


# ── Singleton discovery instance (module-level) ───────────────────────────────

def _get_discovery():
    """Return a fully registered AdPlatformAutoDiscovery instance."""
    from ..ad_platforms import (
        AdPlatformAutoDiscovery,
        AdSensePlatform,
        MediavinePlatform,
        EzoicPlatform,
        AdThrivePlatform,
        MonumetricPlatform,
        PubMaticPlatform,
        AmazonAdsPlatform,
        PrebidHeaderBiddingPlatform,
    )

    discovery = AdPlatformAutoDiscovery()
    discovery.register(AdSensePlatform())
    discovery.register(MediavinePlatform())
    discovery.register(EzoicPlatform())
    discovery.register(AdThrivePlatform())
    discovery.register(MonumetricPlatform())
    discovery.register(PubMaticPlatform())
    discovery.register(AmazonAdsPlatform())
    discovery.register(PrebidHeaderBiddingPlatform())
    return discovery


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_ad_platforms(request: AdAnalysisRequest) -> dict[str, Any]:
    """Analyze a site and recommend the best ad monetization platforms."""
    from ..ad_platforms.auto_discovery import analyze_site_for_ads

    start = time.time()
    try:
        site_data = request.model_dump(exclude={"url"})
        result = analyze_site_for_ads(url=request.url, site_data=site_data)
        return {
            "status": "success",
            "url": request.url,
            "elapsed_sec": round(time.time() - start, 2),
            **result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/platforms")
async def list_platforms() -> dict[str, Any]:
    """List all registered ad platforms."""
    try:
        discovery = _get_discovery()
        return {
            "status": "success",
            "platforms": discovery.list_all_platforms(),
            "count": len(discovery.list_all_platforms()),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/platforms/{name}")
async def get_platform(name: str) -> dict[str, Any]:
    """Get details for a specific ad platform by name."""
    try:
        discovery = _get_discovery()
        platform = discovery.get_platform_by_name(name)
        if not platform:
            raise HTTPException(status_code=404, detail=f"Platform '{name}' not found")
        return {
            "status": "success",
            "name": platform.name,
            "type": platform.platform_type.value,
            "formats": [f.value for f in platform.supported_formats],
            "available": platform.is_available(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/header-bidding")
async def generate_header_bidding_config(request: HeaderBiddingRequest) -> dict[str, Any]:
    """Generate Prebid.js header-bidding configuration."""
    from ..skills import HeaderBiddingConfigGeneratorSkill
    from ..skills.base import SkillInput

    start = time.time()
    try:
        skill = HeaderBiddingConfigGeneratorSkill()
        inp = SkillInput(
            url=request.url,
            params={
                "ad_units": request.ad_units,
                "target_bidders": request.target_bidders,
                "currency": request.currency,
                "timeout_ms": request.timeout_ms,
            },
        )
        result = await skill.execute(inp)
        return {
            "status": "success",
            "url": request.url,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result.data if hasattr(result, "data") else result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/floor-price")
async def optimize_floor_price(request: FloorPriceRequest) -> dict[str, Any]:
    """Optimize header-bidding floor prices to maximize eCPM."""
    from ..skills import FloorPriceOptimizerSkill
    from ..skills.base import SkillInput

    start = time.time()
    try:
        skill = FloorPriceOptimizerSkill()
        inp = SkillInput(
            url=request.url,
            params={
                "current_ecpm": request.current_ecpm,
                "ad_units": request.ad_units,
                "target_fill_rate": request.target_fill_rate,
            },
        )
        result = await skill.execute(inp)
        return {
            "status": "success",
            "url": request.url,
            "elapsed_sec": round(time.time() - start, 2),
            "result": result.data if hasattr(result, "data") else result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
