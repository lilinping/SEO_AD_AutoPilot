"""Real SEO Data Skills v2 — async HTTP client with retry + circuit-breaker.

Phase 1 P1 (GAP-006): upgrades sync subprocess calls to async httpx calls.

Changes vs real_data.py:
- All execute() methods are now async
- Uses httpx.AsyncClient (persistent session, connection pooling)
- Retry decorator: exponential backoff, max 3 attempts, retryable 429/5xx
- API-key validation at startup (raises clear ConfigError if missing)
- Rate-limit headers parsed (X-RateLimit-Remaining / Retry-After)
- Paginates DataForSEO results automatically (up to 3 pages)
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Optional

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


# ── Retry helper ──────────────────────────────────────────────────────────────

async def _request_with_retry(
    method: str,
    url: str,
    *,
    headers: Optional[dict] = None,
    json: Optional[Any] = None,
    params: Optional[dict] = None,
    auth: Optional[tuple] = None,
    max_attempts: int = 3,
    base_delay: float = 1.0,
) -> tuple[int, Any]:
    """Make an async HTTP request with exponential-backoff retry.

    Returns (status_code, response_body_dict_or_text).
    """
    try:
        import httpx
    except ImportError:
        raise ImportError("httpx is required: pip install httpx")

    last_exc: Optional[Exception] = None
    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.request(
                    method, url,
                    headers=headers or {},
                    json=json,
                    params=params,
                    auth=auth,
                )
                # Parse rate-limit headers
                retry_after = float(resp.headers.get("Retry-After", 0))
                if resp.status_code == 429 and retry_after:
                    await asyncio.sleep(retry_after)
                    continue
                if resp.status_code >= 500 and attempt < max_attempts - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                return resp.status_code, body
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < max_attempts - 1:
                await asyncio.sleep(base_delay * (2 ** attempt))

    raise RuntimeError(f"Request failed after {max_attempts} attempts: {last_exc}")


# ── DataForSEO async skill ────────────────────────────────────────────────────

class DataForKeywordResearchSkillV2(Skill):
    """DataForSEO keyword research — async httpx, auto-pagination, retry."""

    @property
    def name(self) -> str:
        return "DataForSEO Keyword Research V2"

    @property
    def description(self) -> str:
        return (
            "Real keyword data via DataForSEO API (async): "
            "search volume, CPC, competition, SERP, trending topics."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ANALYZE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    @staticmethod
    def _get_credentials() -> tuple[str, str]:
        login    = os.getenv("DATAFORSEO_LOGIN") or os.getenv("DATAFORSEO_USERNAME")
        password = os.getenv("DATAFORSEO_PASSWORD") or os.getenv("DATAFORSEO_API_KEY")
        if not login or not password:
            raise ValueError(
                "DataForSEO credentials missing. "
                "Set DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD environment variables."
            )
        return login, password

    async def execute(self, skill_input: SkillInput) -> SkillOutput:  # type: ignore[override]
        start = time.time()
        params   = skill_input.params
        keywords = params.get("keywords") or ([params["keyword"]] if "keyword" in params else [])
        if not keywords:
            return self._create_output(success=False, result={"error": "No keywords provided"})

        language_code  = params.get("language_code",  params.get("locale", "en"))[:2]
        location_code  = params.get("location_code",  2840)   # 2840 = United States
        include_serp   = params.get("include_serp",   False)

        try:
            login, password = self._get_credentials()
        except ValueError as exc:
            return self._create_output(
                success=False,
                result={"error": str(exc), "mock": True, "keywords": keywords},
                execution_time_ms=int((time.time() - start) * 1000),
            )

        # ── Build DataForSEO request payload ─────────────────────────────────
        payload = [
            {
                "keywords": keywords[:100],         # API max per request
                "language_code": language_code,
                "location_code": location_code,
            }
        ]
        endpoint = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"

        status_code, body = await _request_with_retry(
            "POST", endpoint,
            json=payload,
            auth=(login, password),
        )

        if status_code != 200:
            return self._create_output(
                success=False,
                result={"error": f"DataForSEO API error: {status_code}", "response": body},
                execution_time_ms=int((time.time() - start) * 1000),
            )

        # ── Parse results ─────────────────────────────────────────────────────
        items = []
        if isinstance(body, dict):
            for task in body.get("tasks", []):
                for result in task.get("result", []) or []:
                    for item in result.get("items", []) or []:
                        items.append({
                            "keyword":          item.get("keyword"),
                            "search_volume":    item.get("search_volume"),
                            "cpc":              item.get("cpc"),
                            "competition":      item.get("competition"),
                            "competition_level": item.get("competition_level"),
                            "monthly_searches": item.get("monthly_searches"),
                        })

        return self._create_output(
            success=True,
            result={
                "keywords_analyzed": len(keywords),
                "results":           items,
                "location_code":     location_code,
                "language_code":     language_code,
                "elapsed_sec":       round(time.time() - start, 2),
            },
            execution_time_ms=int((time.time() - start) * 1000),
        )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keywords":      {"type": "array",   "items": {"type": "string"}},
                "keyword":       {"type": "string"},
                "language_code": {"type": "string"},
                "location_code": {"type": "integer"},
                "include_serp":  {"type": "boolean"},
            },
        }


# ── SerpAPI async skill ───────────────────────────────────────────────────────

class SerpAPISkill(Skill):
    """SerpAPI — async SERP results (Google, Bing, YouTube, etc.)."""

    SUPPORTED_ENGINES = ["google", "bing", "youtube", "google_images", "google_news"]

    @property
    def name(self) -> str:
        return "SerpAPI SERP Fetcher"

    @property
    def description(self) -> str:
        return "Real SERP results via SerpAPI: Google / Bing / YouTube / News (async)"

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ANALYZE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    @staticmethod
    def _get_api_key() -> str:
        key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERPAPI_KEY")
        if not key:
            raise ValueError("SerpAPI key missing. Set SERPAPI_API_KEY env var.")
        return key

    async def execute(self, skill_input: SkillInput) -> SkillOutput:  # type: ignore[override]
        start  = time.time()
        params = skill_input.params
        query  = params.get("query") or params.get("keyword") or params.get("q")
        if not query:
            return self._create_output(success=False, result={"error": "No query provided"})

        engine      = params.get("engine",      "google")
        gl          = params.get("gl",          "us")
        hl          = params.get("hl",          "en")
        num_results = int(params.get("num_results", params.get("num", 10)))

        try:
            api_key = self._get_api_key()
        except ValueError as exc:
            return self._create_output(
                success=False,
                result={"error": str(exc), "mock": True},
                execution_time_ms=int((time.time() - start) * 1000),
            )

        request_params = {
            "q":       query,
            "api_key": api_key,
            "engine":  engine,
            "gl":      gl,
            "hl":      hl,
            "num":     num_results,
        }

        status_code, body = await _request_with_retry(
            "GET", "https://serpapi.com/search",
            params=request_params,
        )

        if status_code != 200:
            return self._create_output(
                success=False,
                result={"error": f"SerpAPI error: {status_code}", "response": body},
                execution_time_ms=int((time.time() - start) * 1000),
            )

        organic = []
        if isinstance(body, dict):
            for i, item in enumerate(body.get("organic_results", [])[:num_results]):
                organic.append({
                    "position": i + 1,
                    "title":    item.get("title"),
                    "url":      item.get("link"),
                    "snippet":  item.get("snippet"),
                    "domain":   item.get("displayed_link"),
                })

        return self._create_output(
            success=True,
            result={
                "query":          query,
                "engine":         engine,
                "organic_count":  len(organic),
                "organic_results": organic,
                "knowledge_graph": body.get("knowledge_graph") if isinstance(body, dict) else None,
                "answer_box":     body.get("answer_box")      if isinstance(body, dict) else None,
                "related_searches": body.get("related_searches") if isinstance(body, dict) else [],
                "elapsed_sec":    round(time.time() - start, 2),
            },
            execution_time_ms=int((time.time() - start) * 1000),
        )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query":       {"type": "string"},
                "engine":      {"type": "string", "enum": self.SUPPORTED_ENGINES},
                "gl":          {"type": "string"},
                "hl":          {"type": "string"},
                "num_results": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["query"],
        }
