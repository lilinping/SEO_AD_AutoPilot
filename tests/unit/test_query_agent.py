from apps.api.seo_ad_autopilot.agents.base import SiteContext
from apps.api.seo_ad_autopilot.agents.query import QueryAgent


def test_query_agent_builds_seo_opportunities_from_keyword_research_data():
    context = SiteContext(
        url="https://example.com",
        raw_data={
            "keyword_research": {
                "keywords": [
                    {
                        "keyword": "technical seo checklist",
                        "search_volume": 2400,
                        "difficulty": 22,
                        "intent": "informational",
                        "score": 91,
                    }
                ]
            }
        },
        site_profile={"business_type": "content"},
    )

    opportunities = QueryAgent()._find_seo_opportunities(context)

    assert opportunities[0]["type"] == "keyword_opportunity"
    assert opportunities[0]["keyword"] == "technical seo checklist"
    assert opportunities[0]["priority"] == "high"
    assert opportunities[0]["source"] == "keyword_research"
    assert all(opp["title"] != "Add FAQ Schema" for opp in opportunities)


def test_query_agent_builds_content_opportunities_from_trend_data():
    context = SiteContext(
        url="https://example.com",
        raw_data={
            "trending_topics": [
                {"topic": "ai search optimization", "growth": 68, "source": "dataforseo"}
            ]
        },
    )

    opportunities = QueryAgent()._find_content_opportunities(context)

    assert opportunities == [
        {
            "type": "trending_topic",
            "title": "Cover: ai search optimization",
            "description": "Create timely content around 'ai search optimization' while trend momentum is high",
            "priority": "high",
            "engine": "all",
            "estimated_impact": "Fresh content signal + trend-driven traffic potential",
            "source": "dataforseo",
            "topic": "ai search optimization",
            "growth": 68,
        }
    ]


def test_query_agent_builds_competitor_gaps_from_competitor_data():
    context = SiteContext(
        url="https://example.com",
        raw_data={
            "competitor_data": {
                "competitor.example": {"keyword_positions": {"seo audit template": 3}}
            }
        },
    )

    opportunities = QueryAgent()._find_competitor_gaps(context)

    assert opportunities[0]["type"] == "content_gap"
    assert opportunities[0]["keyword"] == "seo audit template"
    assert opportunities[0]["source"] == "competitor_analysis"
    assert opportunities[0]["priority"] == "high"
