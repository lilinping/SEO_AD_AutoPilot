"""Agent Result Cache — AGT-004 实现

基于 URL + 参数哈希的 Agent 结果缓存，支持 TTL 可配置。
自动后端选择：REDIS_URL 存在且 redis.asyncio 可用 → Redis；否则 → 进程内存。

快速用法:
    from .agent_cache import get_agent_cache

    cache = get_agent_cache()

    # 方式 1: 手动 get / set
    result = await cache.get(url, agent="sniffer")
    if result is None:
        result = await sniffer.analyze(context)
        await cache.set(url, agent="sniffer", data=result)

    # 方式 2: 一步包装（推荐）
    result = await cache.cached_call(
        url=url, agent="sniffer",
        fn=lambda: sniffer.analyze(context),
    )
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── 默认 TTL 配置表（按 Agent 类型）──────────────────────────────────────────
_DEFAULT_TTL: dict[str, int] = {
    "sniffer":            3600,   # 1h  — 技术健康度
    "query":              7200,   # 2h  — 关键词机会
    "strategist":         7200,   # 2h  — 策略分析
    "ux_reviewer":        3600,   # 1h  — UX 审查
    "aio_optimizer":      3600,   # 1h  — AIO 优化
    "geo":                3600,   # 1h  — GEO 分析
    "rank_tracker":       1800,   # 30m — 排名追踪（数据变化快）
    "competitor_analyst": 14400,  # 4h  — 竞品分析
    "policy_guard":       86400,  # 24h — 合规检查（规则稳定）
    "coordinator":        1800,   # 30m — 协调器
    "_default":           3600,
}


def _make_key(url: str, agent: str, extra: Optional[dict] = None) -> str:
    """生成稳定缓存键 agt_cache:{agent}:{sha256[:16]}"""
    payload = json.dumps(
        {"url": url, "agent": agent, **(extra or {})},
        sort_keys=True, ensure_ascii=False,
    )
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"agt_cache:{agent}:{digest}"


# ── 内存后端 ─────────────────────────────────────────────────────────────────

@dataclass
class _Slot:
    data: Any
    expires_at: float


class _MemoryBackend:
    """单进程内存缓存，适合开发 / 测试环境。"""

    def __init__(self) -> None:
        self._store: dict[str, _Slot] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            slot = self._store.get(key)
            if slot is None:
                return None
            if time.time() > slot.expires_at:
                del self._store[key]
                return None
            return slot.data

    async def set(self, key: str, data: Any, ttl: int) -> None:
        async with self._lock:
            self._store[key] = _Slot(data=data, expires_at=time.time() + ttl)
            # 概率性清理过期条目（20% 触发）
            import random
            if random.random() < 0.20:
                now = time.time()
                stale = [k for k, v in self._store.items() if now > v.expires_at]
                for k in stale:
                    del self._store[k]

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)

    async def clear_all(self) -> int:
        async with self._lock:
            n = len(self._store)
            self._store.clear()
            return n

    @property
    def size(self) -> int:
        return len(self._store)


# ── Redis 后端 ────────────────────────────────────────────────────────────────

class _RedisBackend:
    """生产级 Redis 后端（依赖 redis[asyncio]）。"""

    def __init__(self, url: str) -> None:
        self._url = url
        self._client: Any = None

    async def _conn(self) -> Any:
        if self._client is None:
            try:
                import redis.asyncio as aio  # type: ignore
                self._client = await aio.from_url(
                    self._url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=3,
                )
            except ImportError as exc:
                raise RuntimeError("请安装: pip install 'redis[asyncio]'") from exc
        return self._client

    async def get(self, key: str) -> Optional[Any]:
        try:
            raw = await (await self._conn()).get(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("AgentCache Redis GET: %s", exc)
            return None

    async def set(self, key: str, data: Any, ttl: int) -> None:
        try:
            await (await self._conn()).setex(key, ttl, json.dumps(data, ensure_ascii=False))
        except Exception as exc:
            logger.warning("AgentCache Redis SET: %s", exc)

    async def delete(self, key: str) -> None:
        try:
            await (await self._conn()).delete(key)
        except Exception as exc:
            logger.warning("AgentCache Redis DEL: %s", exc)

    async def clear_all(self) -> int:
        try:
            client = await self._conn()
            keys = await client.keys("agt_cache:*")
            if keys:
                await client.delete(*keys)
            return len(keys)
        except Exception as exc:
            logger.warning("AgentCache Redis CLEAR: %s", exc)
            return 0


# ── 统计 ──────────────────────────────────────────────────────────────────────

@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits":       self.hits,
            "misses":     self.misses,
            "sets":       self.sets,
            "evictions":  self.evictions,
            "hit_rate":   self.hit_rate,
        }


# ── 门面类 ────────────────────────────────────────────────────────────────────

class AgentCache:
    """Agent 结果缓存门面。

    参数:
        redis_url   — Redis URL（如 redis://localhost:6379/0）；
                      None 或空字符串 → 内存后端（开发/测试）
        default_ttl — 全局 TTL 覆盖（秒）；None → 使用 _DEFAULT_TTL 表
        enabled     — False 时完全禁用缓存（测试 / dry_run）
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_ttl: Optional[int] = None,
        enabled: bool = True,
    ) -> None:
        self._enabled = enabled
        self._default_ttl = default_ttl
        self._stats = CacheStats()
        if redis_url:
            self._bk: _MemoryBackend | _RedisBackend = _RedisBackend(redis_url)
            logger.info("AgentCache: Redis 后端 (%s)", redis_url.split("@")[-1])
        else:
            self._bk = _MemoryBackend()
            logger.info("AgentCache: 内存后端（单进程开发环境）")

    # ── 核心 API ──────────────────────────────────────────────────────────────

    async def get(
        self,
        url: str,
        agent: str,
        extra: Optional[dict] = None,
    ) -> Optional[Any]:
        """查询缓存；未命中返回 None。"""
        if not self._enabled:
            return None
        key = _make_key(url, agent, extra)
        result = await self._bk.get(key)
        if result is None:
            self._stats.misses += 1
            logger.debug("MISS  %s | %s", agent, url[:60])
        else:
            self._stats.hits += 1
            logger.debug("HIT   %s | %s", agent, url[:60])
        return result

    async def set(
        self,
        url: str,
        agent: str,
        data: Any,
        ttl: Optional[int] = None,
        extra: Optional[dict] = None,
    ) -> None:
        """写入缓存；ttl=None 时使用 _DEFAULT_TTL 表。"""
        if not self._enabled:
            return
        resolved_ttl = (
            ttl
            or self._default_ttl
            or _DEFAULT_TTL.get(agent, _DEFAULT_TTL["_default"])
        )
        key = _make_key(url, agent, extra)
        try:
            serial = _serialize(data)
        except Exception as exc:
            logger.warning("AgentCache: 无法序列化 %s，跳过缓存: %s", agent, exc)
            return
        await self._bk.set(key, serial, resolved_ttl)
        self._stats.sets += 1
        logger.debug("SET   %s | %s (TTL=%ds)", agent, url[:60], resolved_ttl)

    async def delete(
        self,
        url: str,
        agent: str,
        extra: Optional[dict] = None,
    ) -> None:
        """手动删除单条缓存。"""
        await self._bk.delete(_make_key(url, agent, extra))
        self._stats.evictions += 1

    async def cached_call(
        self,
        url: str,
        agent: str,
        fn: Callable,
        ttl: Optional[int] = None,
        extra: Optional[dict] = None,
    ) -> Any:
        """缓存包装器：先查缓存，未命中则调用 fn() 并写入缓存后返回。

        示例:
            result = await cache.cached_call(
                url=url, agent="sniffer",
                fn=lambda: sniffer.analyze(context),
            )
        """
        cached = await self.get(url, agent, extra)
        if cached is not None:
            return cached
        result = await fn() if asyncio.iscoroutinefunction(fn) else fn()
        await self.set(url, agent, result, ttl, extra)
        return result

    # ── 统计 & 诊断 ───────────────────────────────────────────────────────────

    @property
    def stats(self) -> CacheStats:
        return self._stats

    def stats_dict(self) -> dict[str, Any]:
        d = self._stats.to_dict()
        if isinstance(self._bk, _MemoryBackend):
            d.update(backend="memory", memory_entries=self._bk.size)
        else:
            d["backend"] = "redis"
        return d


# ── 序列化工具 ────────────────────────────────────────────────────────────────

def _serialize(obj: Any) -> Any:
    """递归将 AgentOutput / dataclass / Enum 转为 JSON 可序列化结构。"""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dataclass_fields__"):
        import dataclasses
        return {k: _serialize(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(i) for i in obj]
    if hasattr(obj, "value"):   # Enum
        return obj.value
    return str(obj)


# ── 全局单例 ──────────────────────────────────────────────────────────────────

_instance: Optional[AgentCache] = None


def get_agent_cache(
    redis_url: Optional[str] = None,
    enabled: bool = True,
) -> AgentCache:
    """返回全局 AgentCache 单例（首次调用时初始化）。

    推荐在 FastAPI lifespan 中预热:
        from .agents.agent_cache import get_agent_cache
        cache = get_agent_cache(redis_url=settings.redis_url)
    """
    global _instance
    if _instance is None:
        if not redis_url:
            redis_url = (
                os.getenv("REDIS_URL")
                or os.getenv("SEO_AD_BOT_REDIS_URL")
                or ""
            )
        _instance = AgentCache(redis_url=redis_url or None, enabled=enabled)
    return _instance
