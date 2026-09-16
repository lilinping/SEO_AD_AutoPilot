import pytest

from apps.api.seo_ad_autopilot.services import (
    AdService,
    CompetitorService,
    ContentService,
    CrawlService,
    NotificationService,
    RankingService,
    ReportService,
)


@pytest.mark.asyncio
async def test_crawl_service_reports_missing_url_without_notimplemented():
    result = await CrawlService().run()

    assert result["status"] == "error"
    assert result["success"] is False
    assert "URL is required" in result["error"]


@pytest.mark.asyncio
async def test_content_service_generates_template_content():
    result = await ContentService().run(
        action="generate",
        topic="technical seo",
        content_type="faq",
        keywords=["crawl budget"],
    )

    assert result["status"] == "complete"
    assert result["success"] is True
    assert "markdown" in result["result"]


@pytest.mark.asyncio
async def test_ad_service_returns_ad_readiness_report():
    result = await AdService().run(url="https://example.com", site_data={"monthly_visits": 25000, "has_blog": True})

    assert result["status"] == "complete"
    assert result["success"] is True
    assert result["result"]["ad_readiness"]["grade"] in {"A", "B", "C", "D"}


@pytest.mark.asyncio
async def test_ranking_service_creates_rank_snapshot():
    result = await RankingService().run(
        action="snapshot",
        keywords=["seo tool"],
        context={"serp_data": {"seo tool": {"position": 8}}},
    )

    assert result["status"] == "complete"
    assert result["success"] is True
    assert result["result"]["summary"]["tracked_keywords"] == 1


@pytest.mark.asyncio
async def test_competitor_service_creates_keyword_gap():
    result = await CompetitorService().run(
        action="keyword_gap",
        context={"competitor_data": {"competitor.example": {"keyword_positions": {"seo audit": 4}}}},
    )

    assert result["status"] == "complete"
    assert result["success"] is True
    assert result["result"]["gap_count"] == 1


@pytest.mark.asyncio
async def test_report_service_builds_summary_report():
    result = await ReportService().run(title="Audit", sections={"summary": {"score": 80}})

    assert result["status"] == "complete"
    assert result["success"] is True
    assert result["result"]["title"] == "Audit"
    assert result["result"]["sections"]["summary"]["score"] == 80


@pytest.mark.asyncio
async def test_notification_service_handles_unconfigured_channels():
    result = await NotificationService().run(alert_type="info", message="Smoke test")

    assert result["status"] == "complete"
    assert result["success"] is True
    assert "configured_channels" in result["result"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("service", "kwargs", "expected_type"),
    [
        (CrawlService(), {"url": "https://example.com"}, "crawl"),
        (ContentService(), {"topic": "SEO checklist", "content_type": "faq"}, "content"),
        (AdService(), {"url": "https://example.com", "site_data": {"monthly_visits": 12000}}, "ad"),
        (CompetitorService(), {"url": "https://example.com", "competitors": ["https://competitor.example"]}, "competitor"),
        (RankingService(), {"url": "https://example.com", "keywords": ["seo tool"]}, "ranking"),
        (ReportService(), {"url": "https://example.com", "analysis_data": {"recommendations": []}}, "report"),
        (NotificationService(), {"title": "Smoke", "message": "Service check"}, "notification"),
    ],
)
async def test_services_keep_smoke_contract(service, kwargs, expected_type):
    result = await service.run(**kwargs)

    assert result["status"] == "complete"
    assert result["service"] == expected_type
    assert "task_id" in result
