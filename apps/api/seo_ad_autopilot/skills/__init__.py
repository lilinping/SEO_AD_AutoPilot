"""Skills execution layer for SEO_AD_BOT.

All 19 skill classes are exported here.
"""

from .base import Skill, SkillCategory, SkillInput, SkillOutput
from .registry import SkillRegistry
from .crawl import SiteCrawlerSkill
from .analyze import StyleExtractorSkill, SiteAnalyzerSkill
from .generate import ContentGeneratorSkill, SchemaBuilderSkill
from .deploy import GitHubPRCreatorSkill, CMSPublisherSkill
from .monitor import MetricsCollectorSkill, AlertManagerSkill
from .amazon_ads_report import AmazonAdsReportSkill
from .ecommerce_analysis import EcommerceAnalysisSkill
from .keyword_research import KeywordResearchSkill
from .real_data import (
    DataForKeywordResearchSkill,
    AhrefsSiteExplorerSkill,
    AhrefsKeywordExplorerSkill,
    AmazonAdsReporterSkill,
    AmazonAdsNodeReporterSkill,
)
from .web_scraper import WebScraperSkill, YouTubeTranscriptSkill, RSSFeedSkill
from .aio_optimizer import LLMTxtGeneratorSkill, EEATEnhancerSkill, AIOCitationTrackerSkill
from .rank_tracking import RankSnapshotSkill, SERPFeatureTrackerSkill
from .competitor_analysis import CompetitorKeywordGapSkill, ContentGapAnalysisSkill
from .content_decay import ContentDecayDetectorSkill
from .crux_rum import CrUXCollectorSkill, RUMSnippetInjectorSkill
from .header_bidding import (
    HeaderBiddingConfigGeneratorSkill,
    FloorPriceOptimizerSkill,
    AdRefreshStrategySkill,
)

__all__ = [
    # Base
    "Skill",
    "SkillCategory",
    "SkillInput",
    "SkillOutput",
    "SkillRegistry",
    # Crawl
    "SiteCrawlerSkill",
    # Analyze
    "StyleExtractorSkill",
    "SiteAnalyzerSkill",
    # Generate
    "ContentGeneratorSkill",
    "SchemaBuilderSkill",
    # Deploy
    "GitHubPRCreatorSkill",
    "CMSPublisherSkill",
    # Monitor
    "MetricsCollectorSkill",
    "AlertManagerSkill",
    # Ads
    "AmazonAdsReportSkill",
    "EcommerceAnalysisSkill",
    # Keywords
    "KeywordResearchSkill",
    # Real data
    "DataForKeywordResearchSkill",
    "AhrefsSiteExplorerSkill",
    "AhrefsKeywordExplorerSkill",
    "AmazonAdsReporterSkill",
    "AmazonAdsNodeReporterSkill",
    # Web scraper
    "WebScraperSkill",
    "YouTubeTranscriptSkill",
    "RSSFeedSkill",
    # AIO optimizer
    "LLMTxtGeneratorSkill",
    "EEATEnhancerSkill",
    "AIOCitationTrackerSkill",
    # Rank tracking
    "RankSnapshotSkill",
    "SERPFeatureTrackerSkill",
    # Competitor analysis
    "CompetitorKeywordGapSkill",
    "ContentGapAnalysisSkill",
    # Content decay
    "ContentDecayDetectorSkill",
    # CrUX / RUM
    "CrUXCollectorSkill",
    "RUMSnippetInjectorSkill",
    # Header bidding
    "HeaderBiddingConfigGeneratorSkill",
    "FloorPriceOptimizerSkill",
    "AdRefreshStrategySkill",
]
