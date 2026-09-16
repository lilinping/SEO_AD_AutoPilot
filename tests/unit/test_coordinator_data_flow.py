import pytest

from apps.api.seo_ad_autopilot.agents.coordinator import CoordinatorAgent


@pytest.mark.asyncio
async def test_coordinator_injects_research_datasets_before_query_agent(monkeypatch):
    async def fake_collect(self, context):
        return {
            "keyword_research": {
                "keywords": [
                    {
                        "keyword": "programmatic seo checklist",
                        "search_volume": 1800,
                        "difficulty": 18,
                        "score": 92,
                    }
                ]
            },
            "trending_topics": [
                {"topic": "ai search optimization", "growth": 70, "source": "test"}
            ],
            "competitor_data": {
                "competitor.example": {
                    "keyword_positions": {"seo audit template": 4}
                }
            },
        }

    monkeypatch.setattr(CoordinatorAgent, "_collect_research_datasets", fake_collect)

    report = await CoordinatorAgent().async_analyze(
        "https://example.com",
        agent_filter=["sniffer", "query"],
        timeout_sec=5,
    )

    query_output = report.agent_outputs["query"].content
    opportunities = query_output["opportunities"]

    assert any(
        opportunity.get("keyword") == "programmatic seo checklist"
        and opportunity.get("source") == "keyword_research"
        for opportunity in opportunities
    )
    assert any(
        opportunity.get("topic") == "ai search optimization"
        and opportunity.get("source") == "test"
        for opportunity in opportunities
    )
    assert any(
        opportunity.get("keyword") == "seo audit template"
        and opportunity.get("source") == "competitor_analysis"
        for opportunity in opportunities
    )


def test_coordinator_normalizes_dataforseo_payload_shapes():
    coordinator = CoordinatorAgent()

    keyword_payload = {
        "keywords": [
            {"keyword": "seo checklist", "search_volume": 1200, "difficulty": 20}
        ],
        "competitors": [
            {"domain": "competitor.example", "keyword_positions": {"seo audit": 5}}
        ],
    }
    trend_payload = {
        "topics": [{"topic": "ai seo", "growth": 60}]
    }

    assert coordinator._normalize_keyword_research(keyword_payload) == {
        "keywords": [{"keyword": "seo checklist", "search_volume": 1200, "difficulty": 20}],
        "source": "dataforseo",
    }
    assert coordinator._normalize_trending_topics(trend_payload) == [
        {"topic": "ai seo", "growth": 60, "source": "dataforseo"}
    ]
    assert coordinator._normalize_competitor_data(keyword_payload) == {
        "competitor.example": {
            "domain": "competitor.example",
            "keyword_positions": {"seo audit": 5},
        }
    }


@pytest.mark.asyncio
async def test_coordinator_runs_strategist_after_query_opportunities_are_available(monkeypatch):
    async def fake_collect(self, context):
        return {
            "keyword_research": {
                "keywords": [
                    {
                        "keyword": "programmatic seo checklist",
                        "search_volume": 1800,
                        "difficulty": 18,
                        "score": 92,
                    }
                ]
            }
        }

    monkeypatch.setattr(CoordinatorAgent, "_collect_research_datasets", fake_collect)

    report = await CoordinatorAgent().async_analyze(
        "https://example.com",
        agent_filter=["query", "strategist"],
        timeout_sec=5,
    )

    query_opportunities = report.agent_outputs["query"].content["opportunities"]
    strategist_strategies = report.agent_outputs["strategist"].content["strategies"]

    assert query_opportunities
    assert any(
        strategy.get("keyword") == "programmatic seo checklist"
        and strategy.get("source") == "keyword_research"
        for strategy in strategist_strategies
    )
