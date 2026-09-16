"""tests/unit/test_agent_cache.py — AGT-004 单元测试
特点: 纯内存后端，无网络 / 无 DB / 无 LLM，< 2 秒完成
运行: make test-unit
"""
import asyncio, sys, os, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from apps.api.seo_ad_autopilot.agents.agent_cache import (
    AgentCache, CacheStats, _make_key, _serialize,
)


# ── fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture
def cache():
    return AgentCache(redis_url=None, enabled=True)

@pytest.fixture
def off_cache():
    return AgentCache(redis_url=None, enabled=False)


# ── _make_key ─────────────────────────────────────────────────────────────────
def test_key_stable():
    assert _make_key("https://a.com", "sniffer") == _make_key("https://a.com", "sniffer")

def test_key_url_diff():
    assert _make_key("https://a.com", "s") != _make_key("https://b.com", "s")

def test_key_agent_diff():
    assert _make_key("https://a.com", "s") != _make_key("https://a.com", "q")

def test_key_extra_diff():
    assert _make_key("https://a.com", "s", {"x": 1}) != _make_key("https://a.com", "s", {"x": 2})

def test_key_format():
    k = _make_key("https://a.com", "sniffer")
    parts = k.split(":")
    assert parts[0] == "agt_cache" and parts[1] == "sniffer" and len(parts[2]) == 16


# ── _serialize ────────────────────────────────────────────────────────────────
def test_serialize_primitives():
    for v in [None, True, 42, 3.14, "hi"]:
        assert _serialize(v) == v

def test_serialize_dict():
    assert _serialize({"a": 1, "b": [2, 3]}) == {"a": 1, "b": [2, 3]}

def test_serialize_dataclass():
    from dataclasses import dataclass
    @dataclass
    class Foo:
        x: int; y: str
    assert _serialize(Foo(1, "bar")) == {"x": 1, "y": "bar"}

def test_serialize_enum():
    from enum import Enum
    class C(Enum):
        A = "red"
    assert _serialize(C.A) == "red"

def test_serialize_unknown():
    class Weird:
        pass
    assert isinstance(_serialize(Weird()), str)


# ── get / set ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_miss_returns_none(cache):
    assert await cache.get("https://x.com", "sniffer") is None
    assert cache.stats.misses == 1 and cache.stats.hits == 0

@pytest.mark.asyncio
async def test_set_then_hit(cache):
    data = {"score": 0.9}
    await cache.set("https://x.com", "sniffer", data, ttl=3600)
    assert await cache.get("https://x.com", "sniffer") == data
    assert cache.stats.hits == 1 and cache.stats.sets == 1

@pytest.mark.asyncio
async def test_agents_isolated(cache):
    await cache.set("https://x.com", "sniffer", {"a": 1})
    await cache.set("https://x.com", "query",   {"a": 2})
    assert (await cache.get("https://x.com", "sniffer"))["a"] == 1
    assert (await cache.get("https://x.com", "query"))["a"]   == 2

@pytest.mark.asyncio
async def test_ttl_expiry(cache):
    await cache.set("https://x.com", "sniffer", {"v": 1}, ttl=1)
    assert await cache.get("https://x.com", "sniffer") is not None
    await asyncio.sleep(1.1)
    assert await cache.get("https://x.com", "sniffer") is None


# ── delete ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_delete(cache):
    await cache.set("https://x.com", "sniffer", {"v": 1})
    await cache.delete("https://x.com", "sniffer")
    assert await cache.get("https://x.com", "sniffer") is None
    assert cache.stats.evictions == 1


# ── cached_call ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_cached_call_calls_fn_once(cache):
    n = {"count": 0}
    async def fn():
        n["count"] += 1
        return {"ok": True}
    r1 = await cache.cached_call("https://x.com", "query", fn)
    r2 = await cache.cached_call("https://x.com", "query", fn)
    assert r1 == r2 == {"ok": True}
    assert n["count"] == 1          # fn 只被调用一次

@pytest.mark.asyncio
async def test_cached_call_sync_fn(cache):
    result = await cache.cached_call("https://x.com", "sniffer", lambda: {"sync": True})
    assert result == {"sync": True}


# ── disabled cache ────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_disabled_always_miss(off_cache):
    await off_cache.set("https://x.com", "sniffer", {"v": 1})
    assert await off_cache.get("https://x.com", "sniffer") is None

@pytest.mark.asyncio
async def test_disabled_stats_unchanged(off_cache):
    await off_cache.get("https://x.com", "sniffer")
    assert off_cache.stats.hits == 0 and off_cache.stats.misses == 0


# ── hit_rate ──────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_hit_rate(cache):
    await cache.set("https://x.com", "sniffer", {"v": 1})
    await cache.get("https://x.com", "sniffer")   # hit
    await cache.get("https://y.com", "sniffer")   # miss
    assert cache.stats.hit_rate == 0.5

@pytest.mark.asyncio
async def test_stats_dict_memory(cache):
    d = cache.stats_dict()
    assert d["backend"] == "memory"
    assert "memory_entries" in d and "hit_rate" in d
