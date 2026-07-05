"""Search engines router.

Endpoints:
  POST /api/search/query            – query multiple search engines simultaneously
  POST /api/search/ai-visibility    – check AI engine visibility
  GET  /api/search/engines          – list available search engines
  POST /api/search/serp             – fetch live SERP results
"""

from __future__ import annotations

import asyncio
import importlib
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/search", tags=["search-engines"])

_ENGINE_MODULES = {
    "google": "google",
    "bing": "bing",
    "baidu": "baidu",
    "yandex": "yandex",
    "chatgpt": "chatgpt",
    "claude": "claude",
    "perplexity": "perplexity",
    "chinese_ai": "chinese_ai",
    "qihoo360": "qihoo360",
    "sogou": "sogou",
}


class SearchQueryRequest(BaseModel):
    query: str
    engines: list[str] = ["google", "bing"]
    num_results: int = 10
    locale: str = "en"
    safe_search: bool = True


class AIVisibilityRequest(BaseModel):
    url: str
    brand_name: Optional[str] = None
    target_queries: list[str] = []
    engines: list[str] = ["chatgpt", "perplexity", "claude"]


class SERPRequest(BaseModel):
    keyword: str
    engine: str = "google"
    locale: str = "en"
    device: str = "desktop"
    num_results: int = 10


def _load_engine(name: str):
    """Dynamically load a search-engine adapter class by name."""
    if name not in _ENGINE_MODULES:
        raise ValueError(f"Unknown search engine: {name!r}. "
                         f"Available: {list(_ENGINE_MODULES)}")
    mod_name = _ENGINE_MODULES[name]
    # Relative import from search_engines sub-package
    base_pkg = __name__.rsplit(".", 1)[0]          # seo_ad_autopilot.routers -> seo_ad_autopilot
    mod = importlib.import_module(f"{base_pkg}.search_engines.{mod_name}")
    # Find the engine class: any public class containing "Engine" or "Search"
    for attr in dir(mod):
        if not attr.startswith("_") and ("Engine" in attr or "Search" in attr):
            obj = getattr(mod, attr)
            if isinstance(obj, type):
                return obj
    raise ImportError(f"No engine class found in search_engines.{mod_name}")


@router.post("/query")
async def multi_engine_query(request: SearchQueryRequest) -> dict[str, Any]:
    """Query multiple search engines in parallel and aggregate results."""
    start = time.time()

    async def _query_one(engine_name: str) -> tuple[str, Any]:
        try:
            EngineClass = _load_engine(engine_name)
            engine = EngineClass()
            search_fn = getattr(engine, "search", None)
            kwargs = dict(query=request.query, num_results=request.num_results, locale=request.locale)
            if search_fn and asyncio.iscoroutinefunction(search_fn):
                r = await search_fn(**kwargs)
            elif search_fn:
                r = search_fn(**kwargs)
            else:
                r = {"error": "search() not found on engine"}
            return engine_name, {"status": "ok", "results": r}
        except Exception as exc:
            return engine_name, {"status": "error", "error": str(exc)}

    pairs = await asyncio.gather(*[_query_one(e) for e in request.engines])
    results = dict(pairs)

    return {
        "status": "success",
        "query": request.query,
        "engines_queried": request.engines,
        "elapsed_sec": round(time.time() - start, 2),
        "results": results,
    }


@router.post("/ai-visibility")
async def check_ai_visibility(request: AIVisibilityRequest) -> dict[str, Any]:
    """Check how visible a URL/brand is across AI-powered search engines."""
    from ..agents import AIOOptimizerAgent, GEOAgent

    start = time.time()
    try:
        aio_agent = AIOOptimizerAgent()
        geo_agent = GEOAgent()

        aio_result, geo_result = await asyncio.gather(
            aio_agent.analyze(url=request.url, target_keywords=request.target_queries),
            geo_agent.analyze(url=request.url, target_engines=request.engines),
        )

        return {
            "status": "success",
            "url": request.url,
            "brand": request.brand_name,
            "elapsed_sec": round(time.time() - start, 2),
            "aio_analysis": aio_result,
            "geo_analysis": geo_result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/engines")
async def list_search_engines() -> dict[str, Any]:
    """List all available search engine adapters."""
    return {
        "engines": {
            "traditional": ["google", "bing", "baidu", "yandex"],
            "ai_powered": ["chatgpt", "claude", "perplexity", "chinese_ai"],
            "chinese": ["baidu", "qihoo360", "sogou", "chinese_ai"],
        },
        "total": len(_ENGINE_MODULES),
    }


@router.post("/serp")
async def fetch_serp(request: SERPRequest) -> dict[str, Any]:
    """Fetch live SERP results for a keyword on a specific engine."""
    start = time.time()
    try:
        EngineClass = _load_engine(request.engine)
        engine = EngineClass()
        search_fn = getattr(engine, "search", None)
        kwargs = dict(query=request.keyword, num_results=request.num_results, locale=request.locale)
        if search_fn and asyncio.iscoroutinefunction(search_fn):
            results = await search_fn(**kwargs)
        elif search_fn:
            results = search_fn(**kwargs)
        else:
            results = []

        return {
            "status": "success",
            "keyword": request.keyword,
            "engine": request.engine,
            "elapsed_sec": round(time.time() - start, 2),
            "results": results,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
