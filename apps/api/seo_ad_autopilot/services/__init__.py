"""Services package — GAP-007: service.py 拆分.

Original service.py (22577 lines) split into focused service modules:
    analysis_service.py     — site analysis orchestration
    content_service.py      — content generation & management
    ranking_service.py      — rank tracking
    competitor_service.py   — competitor analysis
    ad_service.py           — ad platform recommendations
    crawl_service.py        — crawl scheduling
    report_service.py       — report generation
    notification_service.py — alerts & notifications

WorkflowService (original core class) re-exported for backwards compatibility.
"""

from .analysis_service     import AnalysisService
from .content_service      import ContentService
from .ranking_service      import RankingService
from .competitor_service   import CompetitorService
from .ad_service           import AdService
from .crawl_service        import CrawlService
from .report_service       import ReportService
from .notification_service import NotificationService

__all__ = [
    "AnalysisService",
    "ContentService",
    "RankingService",
    "CompetitorService",
    "AdService",
    "CrawlService",
    "ReportService",
    "NotificationService",
]
