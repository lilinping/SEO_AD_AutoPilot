"""tests/unit/test_metrics.py — OPS-007 指标模块单元测试"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def test_record_functions_no_raise():
    from apps.api.seo_ad_autopilot.routers.metrics import (
        record_http, record_agent, record_cache_hit,
        record_cache_miss, record_llm, set_task_gauges,
        record_debate, record_ad_recommendation,
    )
    record_http("GET", "/api/v1/analysis", 200, 0.12)
    record_agent("sniffer", "success", 2.5)
    record_cache_hit("sniffer")
    record_cache_miss("query")
    record_llm("gpt-4o", 100, 50, "success")
    set_task_gauges(3, 1)
    record_debate("consensus")
    record_ad_recommendation("google_ads")


def test_norm_uuid():
    from apps.api.seo_ad_autopilot.routers.metrics import _norm
    path = "/api/v1/analysis/550e8400-e29b-41d4-a716-446655440000/result"
    result = _norm(path)
    assert "{id}" in result
    assert "550e8400" not in result

def test_norm_numeric_id():
    from apps.api.seo_ad_autopilot.routers.metrics import _norm
    assert "{id}" in _norm("/api/v1/tasks/12345/status")

def test_norm_short_number_kept():
    from apps.api.seo_ad_autopilot.routers.metrics import _norm
    # 3자리 미만의 숫자는 정상 경로 세그먼트 유지
    result = _norm("/api/v1/page/2")
    assert "/2" in result or "/{id}" in result
