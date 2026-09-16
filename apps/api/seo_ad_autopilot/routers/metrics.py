"""Prometheus / JSON 指标端点 — OPS-007 实现

端点:
  GET /metrics         — Prometheus text format（需安装 prometheus-client>=0.19.0）
  GET /metrics/summary — JSON 格式指标摘要（始终可用，无额外依赖）

安装:
  pip install "prometheus-client>=0.19.0"
"""

from __future__ import annotations

import os
import re as _re
from typing import Any

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse, PlainTextResponse

router = APIRouter(tags=["observability"])

# ── Prometheus SDK（可选）──────────────────────────────────────────────────────
try:
    from prometheus_client import (  # type: ignore
        CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, REGISTRY, generate_latest,
    )
    _PROM_OK = True
except ImportError:
    _PROM_OK = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


# ── 指标定义 ──────────────────────────────────────────────────────────────────
if _PROM_OK:
    HTTP_REQUESTS_TOTAL = Counter(
        "seo_ad_http_requests_total", "Total HTTP requests",
        ["method", "endpoint", "status"])
    HTTP_DURATION = Histogram(
        "seo_ad_http_request_duration_seconds", "HTTP request latency",
        ["method", "endpoint"],
        buckets=[.05, .1, .25, .5, 1, 2.5, 5, 10, 30])
    AGENT_EXEC_TOTAL = Counter(
        "seo_ad_agent_executions_total", "Agent execution count",
        ["agent", "status"])
    AGENT_DURATION = Histogram(
        "seo_ad_agent_duration_seconds", "Agent execution latency",
        ["agent"], buckets=[.1, .5, 1, 3, 10, 30, 60, 120])
    CACHE_HITS   = Counter("seo_ad_agent_cache_hits_total",   "Cache hits",   ["agent"])
    CACHE_MISSES = Counter("seo_ad_agent_cache_misses_total", "Cache misses", ["agent"])
    LLM_TOKENS   = Counter("seo_ad_llm_tokens_total", "LLM tokens", ["model", "token_type"])
    LLM_REQUESTS = Counter("seo_ad_llm_requests_total", "LLM requests", ["model", "status"])
    ACTIVE_TASKS = Gauge("seo_ad_active_analysis_tasks", "Running tasks")
    QUEUED_TASKS = Gauge("seo_ad_queued_analysis_tasks",  "Queued tasks")
    DEBATE_ROUNDS = Counter("seo_ad_debate_rounds_total", "Debate rounds", ["outcome"])
    AD_RECO_TOTAL = Counter(
        "seo_ad_ad_recommendation_requests_total", "Ad reco requests", ["platform"])
else:
    class _Noop:
        def labels(self, **_): return self
        def inc(self, n=1): pass
        def observe(self, v): pass
        def set(self, v): pass

    HTTP_REQUESTS_TOTAL = HTTP_DURATION = AGENT_EXEC_TOTAL = AGENT_DURATION = _Noop()
    CACHE_HITS = CACHE_MISSES = LLM_TOKENS = LLM_REQUESTS = _Noop()
    ACTIVE_TASKS = QUEUED_TASKS = DEBATE_ROUNDS = AD_RECO_TOTAL = _Noop()


# ── 路由端点 ──────────────────────────────────────────────────────────────────

@router.get(
    "/metrics",
    summary="Prometheus 格式指标",
    description=(
        "输出 Prometheus text format 指标。\n\n"
        "需安装: `pip install \'prometheus-client>=0.19.0\'`\n\n"
        "未安装时降级返回 JSON 提示信息。"
    ),
    response_class=PlainTextResponse,
)
async def prometheus_metrics() -> Response:
    if _PROM_OK:
        return Response(content=generate_latest(REGISTRY),
                        media_type=CONTENT_TYPE_LATEST)
    from datetime import datetime, timezone
    return JSONResponse({
        "warning": "prometheus_client 未安装，请执行: pip install prometheus-client",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hint": "pip install \'prometheus-client>=0.19.0\'",
        "metrics": {"prometheus_available": False},
    })


@router.get(
    "/metrics/summary",
    summary="JSON 指标摘要",
    description="以 JSON 格式返回关键运行指标，无额外依赖，始终可用。适合仪表盘和健康检查。",
)
async def metrics_summary() -> dict[str, Any]:
    from datetime import datetime, timezone
    import sys

    result: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prometheus_available": _PROM_OK,
        "runtime": {
            "python_version": sys.version.split()[0],
            "pid": os.getpid(),
            "environment": os.getenv("SEO_AD_BOT_ENVIRONMENT", "development"),
        },
    }
    try:
        from ..agents.agent_cache import get_agent_cache
        result["agent_cache"] = get_agent_cache().stats_dict()
    except Exception:
        result["agent_cache"] = {"status": "unavailable"}
    return result


# ── 便捷函数（供中间件和业务代码调用）────────────────────────────────────────

def _norm(path: str) -> str:
    """规范化路径，避免高基数标签：UUID/长数字 → {id}"""
    path = _re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "{id}", path, flags=_re.I)
    path = _re.sub(r"/\d{4,}", "/{id}", path)
    return path


def record_http(method: str, endpoint: str, status: int, dur: float) -> None:
    """记录一次 HTTP 请求（在中间件中调用）。"""
    HTTP_REQUESTS_TOTAL.labels(
        method=method.upper(), endpoint=_norm(endpoint), status=str(status)).inc()
    HTTP_DURATION.labels(
        method=method.upper(), endpoint=_norm(endpoint)).observe(dur)


def record_agent(agent: str, status: str, dur: float) -> None:
    """记录一次 Agent 执行。status: success | timeout | error"""
    AGENT_EXEC_TOTAL.labels(agent=agent, status=status).inc()
    AGENT_DURATION.labels(agent=agent).observe(dur)


def record_cache_hit(agent: str)  -> None:
    """记录缓存命中（在 AgentCache.get 中调用）。"""
    CACHE_HITS.labels(agent=agent).inc()


def record_cache_miss(agent: str) -> None:
    """记录缓存未命中（在 AgentCache.get 中调用）。"""
    CACHE_MISSES.labels(agent=agent).inc()


def record_llm(model: str, prompt: int, completion: int,
               status: str = "success") -> None:
    """记录 LLM Token 用量和请求状态。"""
    LLM_TOKENS.labels(model=model, token_type="prompt").inc(prompt)
    LLM_TOKENS.labels(model=model, token_type="completion").inc(completion)
    LLM_REQUESTS.labels(model=model, status=status).inc()


def set_task_gauges(active: int, queued: int = 0) -> None:
    """更新活跃/排队任务数量 Gauge。"""
    ACTIVE_TASKS.set(active)
    QUEUED_TASKS.set(queued)


def record_debate(outcome: str) -> None:
    """记录辩论轮次。outcome: consensus | split | timeout"""
    DEBATE_ROUNDS.labels(outcome=outcome).inc()


def record_ad_recommendation(platform: str) -> None:
    """记录广告平台推荐请求。"""
    AD_RECO_TOTAL.labels(platform=platform).inc()
