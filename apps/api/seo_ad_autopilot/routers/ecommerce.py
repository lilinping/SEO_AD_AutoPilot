"""E-commerce analysis API endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional


router = APIRouter(prefix="/api/ecommerce", tags=["ecommerce"])


class EcommerceAnalysisRequest(BaseModel):
    url: Optional[str] = None
    html: Optional[str] = None
    product_data: Optional[dict[str, Any]] = None
    scope: str = "full"
    platform: str = "auto"
    competitors: Optional[list[str]] = None
    target_market: str = "US"


class EcommerceAnalysisResponse(BaseModel):
    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: int = 0


@router.post("/analyze", response_model=EcommerceAnalysisResponse)
async def analyze_ecommerce(request: EcommerceAnalysisRequest) -> EcommerceAnalysisResponse:
    """Run e-commerce analysis on a product page."""
    from ..skills.ecommerce_analysis import EcommerceAnalysisSkill
    from ..skills.base import SkillInput
    import time

    start_time = time.time()

    try:
        skill = EcommerceAnalysisSkill()
        params: dict[str, Any] = {}
        if request.url:
            params["url"] = request.url
        if request.html:
            params["html"] = request.html
        if request.product_data:
            params["product_data"] = request.product_data
        params["scope"] = request.scope
        params["platform"] = request.platform
        if request.competitors:
            params["competitors"] = request.competitors
        params["target_market"] = request.target_market

        skill_input = SkillInput(params=params)
        output = skill.execute(skill_input)

        elapsed_ms = int((time.time() - start_time) * 1000)

        if output.success:
            return EcommerceAnalysisResponse(
                success=True,
                data=output.result,
                execution_time_ms=elapsed_ms,
            )
        else:
            return EcommerceAnalysisResponse(
                success=False,
                error=output.error,
                execution_time_ms=elapsed_ms,
            )

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return EcommerceAnalysisResponse(
            success=False,
            error=str(e),
            execution_time_ms=elapsed_ms,
        )


@router.get("/platforms")
async def list_platforms() -> dict[str, Any]:
    """List supported e-commerce platforms."""
    return {
        "platforms": [
            {"id": "amazon", "name": "Amazon", "features": ["SP/SB/SD Ads", "A+ Content", "Brand Registry"]},
            {"id": "shopify", "name": "Shopify", "features": ["App Store", "Themes", "Payments"]},
            {"id": "woocommerce", "name": "WooCommerce", "features": ["Plugins", "Customizable", "Self-hosted"]},
            {"id": "magento", "name": "Magento", "features": ["Enterprise", "B2B", "Multi-store"]},
            {"id": "custom", "name": "Custom Platform", "features": ["Universal analysis"]},
        ]
    }


@router.get("/scopes")
async def list_scopes() -> dict[str, Any]:
    """List analysis scopes."""
    return {
        "scopes": [
            {"id": "full", "name": "Full Analysis", "description": "Complete listing + conversion + competitor analysis"},
            {"id": "listing", "name": "Listing Analysis", "description": "Product title, bullets, images, A+ content"},
            {"id": "pricing", "name": "Pricing Analysis", "description": "Price positioning and competitive pricing"},
            {"id": "conversion", "name": "Conversion Analysis", "description": "CTA, trust, urgency, social proof"},
            {"id": "competitors", "name": "Competitor Analysis", "description": "Competitive positioning and gaps"},
        ]
    }
