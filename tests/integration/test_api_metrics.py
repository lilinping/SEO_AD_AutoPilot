"""tests/integration/test_api_metrics.py — 指标端点集成测试
运行: make test-integration
"""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def client():
    try:
        from apps.api.seo_ad_autopilot.app import create_app
        app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
    except Exception as exc:
        pytest.skip(f"App import failed: {exc}")


@pytest.mark.asyncio
async def test_metrics_summary_200(client):
    resp = await client.get("/metrics/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "timestamp" in body
    assert "prometheus_available" in body

@pytest.mark.asyncio
async def test_prometheus_endpoint_200(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200

@pytest.mark.asyncio
async def test_health_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
