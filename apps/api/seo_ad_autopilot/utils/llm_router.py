"""LLM Cost Router — 按任务复杂度智能路由到低/高成本模型, 含 Prompt 缓存.

P2 缺口补全:
- 按任务类型路由 (简单任务用低成本模型, 复杂任务用高质量模型)
- Prompt 缓存 (同类站型分析结果缓存, 避免重复调用)
- 成本追踪面板 (每个项目/任务的 LLM 消耗成本可视化)
- 支持 OpenAI / Anthropic / Google / DeepSeek / Ollama
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ── Task Complexity Levels ────────────────────────────────────────────────────

class TaskComplexity(str, Enum):
    SIMPLE   = "simple"    # 单一提取/分类/格式化  → 低成本模型
    MEDIUM   = "medium"    # 分析/推理/建议        → 中端模型
    COMPLEX  = "complex"   # 多步骤推理/长文生成   → 高质量模型
    CRITICAL = "critical"  # 最终审批/策略决策     → 最优模型


# ── Model Catalog (2026 pricing, per 1M tokens input/output) ─────────────────

@dataclass
class ModelSpec:
    name:         str
    provider:     str
    input_cost:   float    # USD per 1M input tokens
    output_cost:  float    # USD per 1M output tokens
    context_window: int    # tokens
    supports_vision: bool = False
    supports_cache:  bool = False   # prompt caching supported
    max_complexity: TaskComplexity = TaskComplexity.CRITICAL
    quality_score:  float = 0.8    # 0–1 relative quality estimate


MODEL_CATALOG: dict[str, ModelSpec] = {
    # ── Ultra-low cost (simple tasks) ──────────────────────────────────
    "deepseek-chat": ModelSpec(
        name="deepseek-chat", provider="deepseek",
        input_cost=0.27, output_cost=1.10,
        context_window=64_000,
        max_complexity=TaskComplexity.MEDIUM,
        quality_score=0.80,
    ),
    "gpt-4o-mini": ModelSpec(
        name="gpt-4o-mini", provider="openai",
        input_cost=0.15, output_cost=0.60,
        context_window=128_000,
        supports_cache=True,
        max_complexity=TaskComplexity.MEDIUM,
        quality_score=0.78,
    ),
    "gemini-2.0-flash": ModelSpec(
        name="gemini-2.0-flash", provider="google",
        input_cost=0.10, output_cost=0.40,
        context_window=1_000_000,
        supports_vision=True,
        supports_cache=True,
        max_complexity=TaskComplexity.MEDIUM,
        quality_score=0.82,
    ),
    # ── Mid-tier (analysis tasks) ───────────────────────────────────────
    "gpt-4o": ModelSpec(
        name="gpt-4o", provider="openai",
        input_cost=2.50, output_cost=10.00,
        context_window=128_000,
        supports_vision=True,
        supports_cache=True,
        max_complexity=TaskComplexity.COMPLEX,
        quality_score=0.92,
    ),
    "claude-3-5-haiku": ModelSpec(
        name="claude-3-5-haiku-20241022", provider="anthropic",
        input_cost=0.80, output_cost=4.00,
        context_window=200_000,
        supports_cache=True,
        max_complexity=TaskComplexity.MEDIUM,
        quality_score=0.83,
    ),
    "gemini-2.0-pro": ModelSpec(
        name="gemini-2.0-pro", provider="google",
        input_cost=1.25, output_cost=5.00,
        context_window=2_000_000,
        supports_vision=True,
        supports_cache=True,
        max_complexity=TaskComplexity.COMPLEX,
        quality_score=0.90,
    ),
    # ── High-quality (complex/critical tasks) ───────────────────────────
    "claude-3-7-sonnet": ModelSpec(
        name="claude-3-7-sonnet-20250219", provider="anthropic",
        input_cost=3.00, output_cost=15.00,
        context_window=200_000,
        supports_vision=True,
        supports_cache=True,
        max_complexity=TaskComplexity.CRITICAL,
        quality_score=0.97,
    ),
    "gpt-4.1": ModelSpec(
        name="gpt-4.1", provider="openai",
        input_cost=2.00, output_cost=8.00,
        context_window=1_000_000,
        supports_vision=True,
        supports_cache=True,
        max_complexity=TaskComplexity.CRITICAL,
        quality_score=0.95,
    ),
    "deepseek-r1": ModelSpec(
        name="deepseek-r1", provider="deepseek",
        input_cost=0.55, output_cost=2.19,
        context_window=128_000,
        max_complexity=TaskComplexity.CRITICAL,
        quality_score=0.91,
    ),
}

# ── Task type → complexity mapping ──────────────────────────────────────────

TASK_COMPLEXITY_MAP: dict[str, TaskComplexity] = {
    # Simple (extraction / classification)
    "extract_metadata":       TaskComplexity.SIMPLE,
    "classify_content":       TaskComplexity.SIMPLE,
    "format_schema":          TaskComplexity.SIMPLE,
    "check_robots":           TaskComplexity.SIMPLE,
    "parse_sitemap":          TaskComplexity.SIMPLE,
    "rank_snapshot":          TaskComplexity.SIMPLE,
    "crux_parse":             TaskComplexity.SIMPLE,
    "ad_slot_detection":      TaskComplexity.SIMPLE,

    # Medium (analysis / recommendations)
    "seo_analysis":           TaskComplexity.MEDIUM,
    "geo_analysis":           TaskComplexity.MEDIUM,
    "aio_analysis":           TaskComplexity.MEDIUM,
    "keyword_research":       TaskComplexity.MEDIUM,
    "competitor_analysis":    TaskComplexity.MEDIUM,
    "content_decay_scan":     TaskComplexity.MEDIUM,
    "ad_platform_audit":      TaskComplexity.MEDIUM,
    "floor_price_calc":       TaskComplexity.MEDIUM,
    "eeat_scoring":           TaskComplexity.MEDIUM,

    # Complex (generation / multi-step reasoning)
    "content_generation":     TaskComplexity.COMPLEX,
    "strategy_synthesis":     TaskComplexity.COMPLEX,
    "full_site_report":       TaskComplexity.COMPLEX,
    "llm_txt_generation":     TaskComplexity.COMPLEX,
    "competitor_gap_report":  TaskComplexity.COMPLEX,
    "header_bidding_config":  TaskComplexity.COMPLEX,
    "schema_generation":      TaskComplexity.COMPLEX,
    "debate_synthesis":       TaskComplexity.COMPLEX,

    # Critical (final decisions / approvals)
    "deployment_decision":    TaskComplexity.CRITICAL,
    "policy_check":           TaskComplexity.CRITICAL,
    "risk_assessment":        TaskComplexity.CRITICAL,
    "final_approval":         TaskComplexity.CRITICAL,
}

# ── Recommended model per complexity tier ───────────────────────────────────

COMPLEXITY_TO_MODEL: dict[TaskComplexity, list[str]] = {
    TaskComplexity.SIMPLE:   ["gpt-4o-mini", "deepseek-chat", "gemini-2.0-flash"],
    TaskComplexity.MEDIUM:   ["claude-3-5-haiku", "gemini-2.0-flash", "deepseek-chat"],
    TaskComplexity.COMPLEX:  ["gpt-4o", "gemini-2.0-pro", "claude-3-5-haiku"],
    TaskComplexity.CRITICAL: ["claude-3-7-sonnet", "gpt-4.1", "deepseek-r1"],
}


# ── Cache Entry ───────────────────────────────────────────────────────────────

@dataclass
class CacheEntry:
    key:         str
    result:      Any
    model:       str
    task_type:   str
    input_tokens:  int
    output_tokens: int
    cost_usd:    float
    created_at:  float = field(default_factory=time.time)
    ttl_seconds: int   = 3600 * 24   # 24h default

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds


# ── Cost Ledger Entry ─────────────────────────────────────────────────────────

@dataclass
class CostLedgerEntry:
    task_id:      str
    task_type:    str
    model:        str
    provider:     str
    input_tokens: int
    output_tokens: int
    cost_usd:     float
    cache_hit:    bool
    timestamp:    float = field(default_factory=time.time)
    project_id:   str   = "default"


# ── LLM Cost Router ───────────────────────────────────────────────────────────

class LLMCostRouter:
    """智能 LLM 成本路由器.

    功能:
    1. 按任务类型路由到合适成本/质量的模型
    2. Prompt 缓存 (基于 prompt hash)
    3. 成本账本追踪
    4. 成本面板报告生成

    使用示例:
        router = LLMCostRouter(preferred_providers=["openai", "anthropic"])
        model  = router.route("seo_analysis")
        # → "claude-3-5-haiku"

        # With cache:
        result = router.get_cached("my_prompt_hash")
        if result is None:
            result = llm_call(model, prompt)
            router.cache("my_prompt_hash", result, model, "seo_analysis", 800, 400)
    """

    def __init__(
        self,
        preferred_providers: list[str] | None = None,
        force_model:         str | None       = None,
        cache_ttl_seconds:   int              = 86_400,   # 24h
        project_id:          str              = "default",
    ) -> None:
        self.preferred_providers = preferred_providers or list(
            {m.provider for m in MODEL_CATALOG.values()}
        )
        self.force_model    = force_model
        self.cache_ttl      = cache_ttl_seconds
        self.project_id     = project_id

        self._cache:  dict[str, CacheEntry]       = {}
        self._ledger: list[CostLedgerEntry]       = []

    # ── Routing ──────────────────────────────────────────────────────────────

    def route(
        self,
        task_type:           str,
        override_complexity: TaskComplexity | None = None,
        require_vision:      bool = False,
        max_cost_per_1k:     float | None = None,   # USD per 1K tokens budget
    ) -> str:
        """Return the best model name for a task type."""

        if self.force_model and self.force_model in MODEL_CATALOG:
            return self.force_model

        complexity = override_complexity or TASK_COMPLEXITY_MAP.get(
            task_type, TaskComplexity.MEDIUM
        )

        candidates = COMPLEXITY_TO_MODEL.get(complexity, [])

        for model_name in candidates:
            spec = MODEL_CATALOG.get(model_name)
            if spec is None:
                continue
            if spec.provider not in self.preferred_providers:
                continue
            if require_vision and not spec.supports_vision:
                continue
            if max_cost_per_1k is not None:
                avg_cost_per_1k = (spec.input_cost + spec.output_cost) / 2 / 1000
                if avg_cost_per_1k > max_cost_per_1k:
                    continue
            return model_name

        # Fallback: first matching candidate regardless of provider filter
        for model_name in candidates:
            if model_name in MODEL_CATALOG:
                return model_name

        return "gpt-4o-mini"    # ultimate fallback

    def route_with_spec(
        self,
        task_type: str,
        **kwargs: Any,
    ) -> tuple[str, ModelSpec]:
        """Return (model_name, ModelSpec) for a task."""
        name = self.route(task_type, **kwargs)
        return name, MODEL_CATALOG[name]

    # ── Cache ────────────────────────────────────────────────────────────────

    @staticmethod
    def make_cache_key(prompt: str, task_type: str, extra: str = "") -> str:
        """Generate a deterministic cache key."""
        raw = f"{task_type}::{extra}::{prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get_cached(self, cache_key: str) -> Optional[Any]:
        """Return cached result if fresh, else None."""
        entry = self._cache.get(cache_key)
        if entry and not entry.is_expired:
            # Record as cache hit in ledger
            self._ledger.append(CostLedgerEntry(
                task_id=cache_key[:12],
                task_type=entry.task_type,
                model=entry.model,
                provider=MODEL_CATALOG.get(entry.model, ModelSpec("?","?",0,0,0)).provider,
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                cache_hit=True,
                project_id=self.project_id,
            ))
            return entry.result
        if entry and entry.is_expired:
            del self._cache[cache_key]
        return None

    def cache(
        self,
        cache_key:    str,
        result:       Any,
        model:        str,
        task_type:    str,
        input_tokens: int,
        output_tokens:int,
        ttl_seconds:  int | None = None,
    ) -> float:
        """Cache a result and record cost. Returns cost in USD."""
        spec = MODEL_CATALOG.get(model)
        cost = 0.0
        if spec:
            cost = (
                input_tokens  / 1_000_000 * spec.input_cost +
                output_tokens / 1_000_000 * spec.output_cost
            )

        entry = CacheEntry(
            key=cache_key,
            result=result,
            model=model,
            task_type=task_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 6),
            ttl_seconds=ttl_seconds or self.cache_ttl,
        )
        self._cache[cache_key] = entry

        self._ledger.append(CostLedgerEntry(
            task_id=cache_key[:12],
            task_type=task_type,
            model=model,
            provider=spec.provider if spec else "unknown",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 6),
            cache_hit=False,
            project_id=self.project_id,
        ))

        return round(cost, 6)

    def record_cost(
        self,
        task_id:      str,
        task_type:    str,
        model:        str,
        input_tokens: int,
        output_tokens:int,
    ) -> float:
        """Record a cost event without caching. Returns cost in USD."""
        spec = MODEL_CATALOG.get(model)
        cost = 0.0
        if spec:
            cost = (
                input_tokens  / 1_000_000 * spec.input_cost +
                output_tokens / 1_000_000 * spec.output_cost
            )

        self._ledger.append(CostLedgerEntry(
            task_id=task_id,
            task_type=task_type,
            model=model,
            provider=spec.provider if spec else "unknown",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=round(cost, 6),
            cache_hit=False,
            project_id=self.project_id,
        ))
        return round(cost, 6)

    # ── Cost Dashboard ───────────────────────────────────────────────────────

    def get_dashboard(self, since_hours: float = 24.0) -> dict[str, Any]:
        """Generate cost dashboard report for the last N hours."""
        cutoff   = time.time() - since_hours * 3600
        entries  = [e for e in self._ledger if e.timestamp >= cutoff]
        real     = [e for e in entries if not e.cache_hit]

        if not entries:
            return {
                "period_hours":    since_hours,
                "total_calls":     0,
                "cache_hits":      0,
                "total_cost_usd":  0.0,
                "message":         "No LLM calls recorded in this period.",
            }

        total_cost   = sum(e.cost_usd for e in real)
        total_input  = sum(e.input_tokens  for e in real)
        total_output = sum(e.output_tokens for e in real)
        cache_hits   = len(entries) - len(real)
        cache_rate   = round(cache_hits / len(entries), 3) if entries else 0

        # Cost saved by caching (estimate)
        avg_cost_per_call = total_cost / max(len(real), 1)
        cache_savings = round(cache_hits * avg_cost_per_call, 6)

        # Per-model breakdown
        by_model: dict[str, dict] = {}
        for e in real:
            bm = by_model.setdefault(e.model, {
                "calls": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0,
            })
            bm["calls"]         += 1
            bm["cost"]          += e.cost_usd
            bm["input_tokens"]  += e.input_tokens
            bm["output_tokens"] += e.output_tokens

        for bm in by_model.values():
            bm["cost"]         = round(bm["cost"], 6)
            bm["avg_cost"]     = round(bm["cost"] / max(bm["calls"], 1), 6)

        # Per-task-type breakdown
        by_task: dict[str, dict] = {}
        for e in real:
            bt = by_task.setdefault(e.task_type, {"calls": 0, "cost": 0.0})
            bt["calls"] += 1
            bt["cost"]  += e.cost_usd
        for bt in by_task.values():
            bt["cost"] = round(bt["cost"], 6)

        # Recommendations
        recs: list[str] = []
        if cache_rate < 0.20 and len(real) > 10:
            recs.append(
                "Cache hit rate is low (<20%). "
                "Consider increasing cache TTL or normalising prompt templates."
            )
        most_costly = max(by_model, key=lambda m: by_model[m]["cost"]) if by_model else None
        if most_costly:
            spec = MODEL_CATALOG.get(most_costly)
            if spec and spec.max_complexity == TaskComplexity.CRITICAL:
                recs.append(
                    f"'{most_costly}' is your highest cost model. "
                    "Check if any SIMPLE/MEDIUM tasks are being routed there."
                )

        return {
            "period_hours":     since_hours,
            "total_calls":      len(real),
            "cache_hits":       cache_hits,
            "cache_hit_rate":   f"{cache_rate:.1%}",
            "total_cost_usd":   round(total_cost, 6),
            "total_cost_fmt":   f"${total_cost:.4f}",
            "cache_savings_usd":f"${cache_savings:.4f}",
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "avg_cost_per_call": round(avg_cost_per_call, 6),
            "by_model":          by_model,
            "by_task_type":      by_task,
            "recommendations":   recs,
            "project_id":        self.project_id,
        }

    def get_cost_estimate(
        self,
        task_type:    str,
        est_input_tokens:  int = 1000,
        est_output_tokens: int = 500,
    ) -> dict[str, Any]:
        """Estimate cost for a task before executing it."""
        model_name, spec = self.route_with_spec(task_type)
        cost = (
            est_input_tokens  / 1_000_000 * spec.input_cost +
            est_output_tokens / 1_000_000 * spec.output_cost
        )
        # Compare with most expensive option
        alt = MODEL_CATALOG.get("claude-3-7-sonnet")
        max_cost = (
            est_input_tokens  / 1_000_000 * alt.input_cost +
            est_output_tokens / 1_000_000 * alt.output_cost
        ) if alt else cost

        return {
            "task_type":       task_type,
            "routed_model":    model_name,
            "provider":        spec.provider,
            "estimated_cost":  f"${cost:.6f}",
            "savings_vs_top":  f"${max_cost - cost:.6f}",
            "savings_pct":     f"{(1 - cost/max_cost)*100:.1f}%" if max_cost > 0 else "0%",
            "quality_score":   spec.quality_score,
        }

    def clear_cache(self, task_type: str | None = None) -> int:
        """Clear cache entries. Optionally filter by task_type. Returns cleared count."""
        if task_type is None:
            count = len(self._cache)
            self._cache.clear()
            return count
        to_del = [k for k, v in self._cache.items() if v.task_type == task_type]
        for k in to_del:
            del self._cache[k]
        return len(to_del)

    def export_ledger(self) -> list[dict[str, Any]]:
        """Export full cost ledger as list of dicts."""
        return [
            {
                "task_id":      e.task_id,
                "task_type":    e.task_type,
                "model":        e.model,
                "provider":     e.provider,
                "input_tokens": e.input_tokens,
                "output_tokens":e.output_tokens,
                "cost_usd":     e.cost_usd,
                "cache_hit":    e.cache_hit,
                "timestamp":    e.timestamp,
                "project_id":   e.project_id,
            }
            for e in self._ledger
        ]


# ── Singleton factory ─────────────────────────────────────────────────────────

_router_instances: dict[str, LLMCostRouter] = {}

def get_router(project_id: str = "default", **kwargs: Any) -> LLMCostRouter:
    """Get or create a project-scoped router instance."""
    if project_id not in _router_instances:
        _router_instances[project_id] = LLMCostRouter(project_id=project_id, **kwargs)
    return _router_instances[project_id]
