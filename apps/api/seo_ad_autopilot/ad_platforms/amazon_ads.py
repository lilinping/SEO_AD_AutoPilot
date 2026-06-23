"""Amazon Ads platform - integration for Amazon Advertising API.

Supports Sponsored Products, Sponsored Brands, and Sponsored Display.
Provides report fetching, campaign analysis, and optimization recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .base import (
    AdFormat,
    AdPlatform,
    AdPlatformType,
    AdRecommendation,
    AdSlot,
)


class AmazonAdProduct(str, Enum):
    """Amazon Ads product types."""
    SPONSORED_PRODUCTS = "SPONSORED_PRODUCTS"
    SPONSORED_BRANDS = "SPONSORED_BRANDS"
    SPONSORED_DISPLAY = "SPONSORED_DISPLAY"


class ReportType(str, Enum):
    """Common Amazon Ads report types."""
    # Sponsored Products
    SP_CAMPAIGNS = "spCampaigns"
    SP_AD_GROUPS = "spAdGroup"
    SP_KEYWORDS = "spKeyword"
    SP_SEARCH_TERMS = "spSearchTerm"
    SP_ADVERTISED_PRODUCT = "spAdvertisedProduct"
    SP_PURCHASED_PRODUCT = "spPurchasedProduct"
    SP_PLACEMENT = "spPlacement"
    SP_CAMPAIGN_HOURLY = "spCampaignsHourly"
    # Sponsored Brands
    SB_CAMPAIGNS = "sbCampaigns"
    SB_AD_GROUPS = "sbAdGroup"
    SB_KEYWORDS = "sbKeyword"
    SB_PURCHASED_PRODUCT = "sbPurchasedProduct"
    SB_BRAND_HOURLY = "sbBrandsHourly"
    # Sponsored Display
    SD_CAMPAIGNS = "sdCampaigns"
    SD_AUDIENCES = "sdAudiences"
    SD_PLACEMENT = "sdPlacement"
    SD_PURCHASED_PRODUCT = "sdPurchasedProduct"


@dataclass
class AmazonCampaign:
    """Amazon Ads campaign data."""
    campaign_id: str
    campaign_name: str
    ad_product: AmazonAdProduct
    status: str
    daily_budget: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    targeting_type: Optional[str] = None
    impressions: int = 0
    clicks: int = 0
    cost: float = 0.0
    sales: float = 0.0
    purchases: int = 0
    acos: float = 0.0
    roas: float = 0.0
    ctr: float = 0.0
    cvr: float = 0.0
    cpc: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AmazonAdsMetrics:
    """Aggregated Amazon Ads metrics."""
    total_impressions: int = 0
    total_clicks: int = 0
    total_cost: float = 0.0
    total_sales: float = 0.0
    total_purchases: int = 0
    avg_acos: float = 0.0
    avg_roas: float = 0.0
    avg_ctr: float = 0.0
    avg_cvr: float = 0.0
    avg_cpc: float = 0.0
    campaign_count: int = 0
    keyword_count: int = 0
    search_term_count: int = 0


class AmazonAdsPlatform(AdPlatform):
    """Amazon Advertising platform integration.
    
    Provides:
    - Report fetching (SP/SB/SD)
    - Campaign performance analysis
    - Keyword and search term optimization
    - ACoS/ROAS tracking
    """
    
    def __init__(self, profile_id: Optional[int] = None, region: str = "NA"):
        self._profile_id = profile_id
        self._region = region
        self._report_skill = None
    
    @property
    def name(self) -> str:
        return "Amazon Ads"
    
    @property
    def platform_type(self) -> AdPlatformType:
        return AdPlatformType.DIRECT
    
    @property
    def supported_formats(self) -> list[AdFormat]:
        return [
            AdFormat.DISPLAY,
            AdFormat.NATIVE,
            AdFormat.VIDEO,
            AdFormat.SPONSORED,
        ]
    
    def is_suitable_for_site(self, site_profile: dict[str, Any]) -> AdRecommendation:
        """Determine if Amazon Ads is suitable for a site."""
        content_type = site_profile.get("content_type", "unknown")
        has_ecommerce = site_profile.get("has_ecommerce", False)
        monthly_visits = site_profile.get("monthly_visits", 0)
        
        confidence = 0.4
        reasons = []
        
        if has_ecommerce or content_type == "ecommerce":
            confidence = 0.9
            reasons.append("E-commerce site is ideal for Amazon Ads")
        
        if content_type == "content":
            confidence = 0.3
            reasons.append("Content sites may have limited Amazon Ads ROI")
        
        if monthly_visits > 10000:
            confidence = min(confidence + 0.1, 1.0)
            reasons.append("High traffic volume supports ad spend")
        
        return AdRecommendation(
            platform=self.name,
            platform_type=self.platform_type,
            confidence=confidence,
            reasons=reasons,
            requirements=[
                "Amazon Advertising account",
                "Amazon Seller or Vendor account",
                "Product listings on Amazon",
                "Campaign budget allocation",
            ],
            estimated_rpm=5.0 if has_ecommerce else 2.0,
        )
    
    def get_integration_code(self, slot: AdSlot) -> str:
        """Generate Amazon Ads integration guidance."""
        return f"""<!-- Amazon Ads Integration -->
<!-- Slot: {slot.selector} | Format: {slot.format.value} -->
<div id="amazon-ads-{slot.selector}" class="amazon-ad-container">
    <!-- Amazon Ads pixel and tracking -->
    <script>
    // Amazon Attribution tracking
    (function(a,m,o,c,l,er){{
        a['lynxAnalyticsObject']=o;a[o]=a[o]||function(){{
        (a[o].q=a[o].q||[]).push(arguments)}};
        a[o].l=1*new Date();er=m.createElement(o);
        var s=m.getElementsByTagName(o)[0];
        er.async=1;er.src='//c.amazon-adsystem.com/aax2/assoc_ad.js';
        s.parentNode.insertBefore(er,s);
    }})(window,document,'lynxAnalytics');
    </script>
</div>"""
    
    def get_requirements(self) -> list[str]:
        return [
            "Amazon Advertising account (Seller Central or Vendor Central)",
            "Active product listings on Amazon",
            "Campaign budget (minimum $1/day recommended)",
            "Product detail page optimization",
            "Brand Registry (for Sponsored Brands)",
        ]
    
    def get_policy_constraints(self) -> list[str]:
        return [
            "No incentivized reviews or clicks",
            "Must comply with Amazon advertising policies",
            "Product claims must be accurate",
            "No misleading product information",
            "Must disclose sponsored content",
            "Landing pages must match product listings",
        ]
    
    def set_profile(self, profile_id: int, region: str = "NA") -> None:
        """Set the Amazon Ads profile for API calls."""
        self._profile_id = profile_id
        self._region = region
    
    def get_report_skill(self):
        """Lazy-load the report skill."""
        if self._report_skill is None:
            from ..skills.amazon_ads_report import AmazonAdsReportSkill
            self._report_skill = AmazonAdsReportSkill()
        return self._report_skill
    
    def fetch_campaign_report(
        self,
        start_date: str,
        end_date: str,
        time_unit: str = "SUMMARY",
    ) -> dict[str, Any]:
        """Fetch campaign performance report."""
        if not self._profile_id:
            return {"error": "Profile ID not set. Call set_profile() first."}
        
        skill = self.get_report_skill()
        from ..skills.amazon_ads_report import SkillInput
        
        result = skill.execute(SkillInput(params={
            "profile_id": self._profile_id,
            "region": self._region,
            "report_type_id": "spCampaigns",
            "ad_product": "SPONSORED_PRODUCTS",
            "group_by": ["campaign"],
            "columns": [
                "campaignId", "campaignName", "impressions", "clicks",
                "cost", "sales7d", "purchases7d", "acosClicks7d", "roasClicks7d",
                "startDate", "endDate",
            ],
            "start_date": start_date,
            "end_date": end_date,
            "time_unit": time_unit,
        }))
        
        return result.result if result.success else {"error": result.error}
    
    def fetch_search_term_report(
        self,
        start_date: str,
        end_date: str,
        time_unit: str = "SUMMARY",
    ) -> dict[str, Any]:
        """Fetch search term performance report."""
        if not self._profile_id:
            return {"error": "Profile ID not set. Call set_profile() first."}
        
        skill = self.get_report_skill()
        from ..skills.amazon_ads_report import SkillInput
        
        result = skill.execute(SkillInput(params={
            "profile_id": self._profile_id,
            "region": self._region,
            "report_type_id": "spSearchTerm",
            "ad_product": "SPONSORED_PRODUCTS",
            "group_by": ["searchTerm"],
            "columns": [
                "searchTerm", "keyword", "matchType", "impressions", "clicks",
                "cost", "sales7d", "purchases7d", "acosClicks7d", "roasClicks7d",
                "startDate", "endDate",
            ],
            "start_date": start_date,
            "end_date": end_date,
            "time_unit": time_unit,
        }))
        
        return result.result if result.success else {"error": result.error}
    
    def fetch_advertised_product_report(
        self,
        start_date: str,
        end_date: str,
        time_unit: str = "SUMMARY",
    ) -> dict[str, Any]:
        """Fetch advertised product performance report."""
        if not self._profile_id:
            return {"error": "Profile ID not set. Call set_profile() first."}
        
        skill = self.get_report_skill()
        from ..skills.amazon_ads_report import SkillInput
        
        result = skill.execute(SkillInput(params={
            "profile_id": self._profile_id,
            "region": self._region,
            "report_type_id": "spAdvertisedProduct",
            "ad_product": "SPONSORED_PRODUCTS",
            "group_by": ["advertisedProduct"],
            "columns": [
                "advertisedAsin", "advertisedSku", "impressions", "clicks",
                "cost", "sales7d", "purchases7d", "acosClicks7d", "roasClicks7d",
                "startDate", "endDate",
            ],
            "start_date": start_date,
            "end_date": end_date,
            "time_unit": time_unit,
        }))
        
        return result.result if result.success else {"error": result.error}
    
    def calculate_metrics(self, campaigns: list[AmazonCampaign]) -> AmazonAdsMetrics:
        """Calculate aggregated metrics from campaign data."""
        if not campaigns:
            return AmazonAdsMetrics()
        
        total_impressions = sum(c.impressions for c in campaigns)
        total_clicks = sum(c.clicks for c in campaigns)
        total_cost = sum(c.cost for c in campaigns)
        total_sales = sum(c.sales for c in campaigns)
        total_purchases = sum(c.purchases for c in campaigns)
        
        avg_acos = (total_cost / total_sales * 100) if total_sales > 0 else 0
        avg_roas = (total_sales / total_cost) if total_cost > 0 else 0
        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        avg_cvr = (total_purchases / total_clicks * 100) if total_clicks > 0 else 0
        avg_cpc = (total_cost / total_clicks) if total_clicks > 0 else 0
        
        return AmazonAdsMetrics(
            total_impressions=total_impressions,
            total_clicks=total_clicks,
            total_cost=total_cost,
            total_sales=total_sales,
            total_purchases=total_purchases,
            avg_acos=avg_acos,
            avg_roas=avg_roas,
            avg_ctr=avg_ctr,
            avg_cvr=avg_cvr,
            avg_cpc=avg_cpc,
            campaign_count=len(campaigns),
        )
    
    def generate_optimization_recommendations(
        self,
        campaigns: list[AmazonCampaign],
        target_acos: float = 30.0,
    ) -> list[dict[str, Any]]:
        """Generate optimization recommendations based on campaign performance."""
        recommendations = []
        
        for campaign in campaigns:
            if campaign.acos > target_acos * 1.5:
                recommendations.append({
                    "campaign_id": campaign.campaign_id,
                    "campaign_name": campaign.campaign_name,
                    "type": "high_acos",
                    "severity": "high",
                    "message": f"ACoS ({campaign.acos:.1f}%) is significantly above target ({target_acos}%)",
                    "suggestion": "Consider pausing or reducing bids on underperforming keywords",
                })
            
            if campaign.ctr < 0.3:
                recommendations.append({
                    "campaign_id": campaign.campaign_id,
                    "campaign_name": campaign.campaign_name,
                    "type": "low_ctr",
                    "severity": "medium",
                    "message": f"CTR ({campaign.ctr:.2f}%) is below industry average",
                    "suggestion": "Review ad creative, title, and main image",
                })
            
            if campaign.impressions > 1000 and campaign.clicks == 0:
                recommendations.append({
                    "campaign_id": campaign.campaign_id,
                    "campaign_name": campaign.campaign_name,
                    "type": "no_clicks",
                    "severity": "high",
                    "message": "Campaign has impressions but zero clicks",
                    "suggestion": "Check targeting relevance and bid competitiveness",
                })
        
        return sorted(recommendations, key=lambda r: {"high": 0, "medium": 1, "low": 2}.get(r["severity"], 3))
