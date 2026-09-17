"""Skills execution layer for SEO_AD_BOT.

All skill classes are exported here. See Architecture §5.2-5.4 for skill taxonomy.
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
from .ad_slot_auditor import AdSlotAuditorSkill
from .rollback_executor import RollbackExecutorSkill
from .extra import (
    InternalLinkBuilderSkill,
    AdWrapperRendererSkill,
    AdTelemetryBinderSkill,
    SitemapUpdaterSkill,
    ContentModulePublisherSkill,
    PerfProbeBinderSkill,
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
    # Ad slot auditor (PRD §5.2)
    "AdSlotAuditorSkill",
    # Rollback executor (Architecture §5.4)
    "RollbackExecutorSkill",
    # SEO/AD extra skills (PRD §4.5, §5.2, Architecture §5.2-5.3)
    "InternalLinkBuilderSkill",
    "AdWrapperRendererSkill",
    "AdTelemetryBinderSkill",
    "SitemapUpdaterSkill",
    "ContentModulePublisherSkill",
    "PerfProbeBinderSkill",
]
