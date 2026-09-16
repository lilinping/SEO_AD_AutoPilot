"""Unified data-provenance (数据出处 / 数据可信度) model and evaluators.

This implements the P0 backend slice of
``docs/数据可信度与真实数据源就绪度-产品设计.md``.

The core problem it solves: across the product, many capabilities silently
fall back to synthetic / fallback data when real credentials are missing or
only partially configured. Consumers previously had no consistent way to
answer "how much of this report is real, and what do I need to make it real?".

``DataProvenance`` is the single, reusable label every skill / connector /
report can attach to its output. A partial credential set (e.g. a Google API
key without a Custom Search CX) is treated as *not real*, never as real.
"""

from __future__ import annotations

import os
from typing import Literal, Optional

from pydantic import BaseModel, Field


SourceTier = Literal["real", "partial", "synthetic", "unknown"]

GapType = Literal[
    "none",
    "missing_credential",
    "partial_credential",
    "stale",
    "provider_error",
    "unknown",
]


class DataProvenance(BaseModel):
    """A reusable data-trust label attached to any produced dataset.

    Fields intentionally mirror the design doc so the frontend contract stays
    stable regardless of which skill/connector emitted the data.
    """

    source_tier: SourceTier = Field(default="unknown", alias="sourceTier")
    provider: str = ""
    evidence_at: Optional[str] = Field(default=None, alias="evidenceAt")
    is_fresh: bool = Field(default=False, alias="isFresh")
    gap_type: GapType = Field(default="unknown", alias="gapType")
    gap_summary: str = Field(default="", alias="gapSummary")
    remediation: str = ""

    model_config = {"populate_by_name": True}

    @property
    def is_real(self) -> bool:
        return self.source_tier == "real"


def _env(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""


def evaluate_search_source_provenance() -> DataProvenance:
    """Evaluate the real-data readiness of the keyword/search data source.

    Precedence: a fully-configured Google Custom Search wins, then Bing, then
    synthetic fallback. Partial Google config (key present, CX missing) is
    surfaced as ``partial`` with an actionable remediation, never as real.
    """

    google_key = _env("SEO_AD_BOT_GOOGLE_API_KEY", "GOOGLE_API_KEY")
    google_cx = _env("SEO_AD_BOT_GOOGLE_CX", "GOOGLE_CX")
    bing_key = _env("SEO_AD_BOT_BING_API_KEY", "BING_API_KEY")

    if google_key and google_cx:
        return DataProvenance(
            source_tier="real",
            provider="google_custom_search",
            is_fresh=True,
            gap_type="none",
            gap_summary="Google Custom Search 已完整配置 (API Key + CX)。",
            remediation="",
        )

    if bing_key:
        return DataProvenance(
            source_tier="real",
            provider="bing_web_search",
            is_fresh=True,
            gap_type="none",
            gap_summary="Bing Web Search 已配置。",
            remediation="",
        )

    if google_key and not google_cx:
        return DataProvenance(
            source_tier="partial",
            provider="google_custom_search",
            is_fresh=False,
            gap_type="partial_credential",
            gap_summary="已配置 Google API Key，但缺少 SEO_AD_BOT_GOOGLE_CX（Custom Search 引擎 ID），真实 Google 搜索链路未激活。",
            remediation="在设置页补全 Google Custom Search 引擎 ID (CX)，或改用 Bing/DataForSEO 等其它真实源。",
        )

    return DataProvenance(
        source_tier="synthetic",
        provider="synthetic",
        is_fresh=False,
        gap_type="missing_credential",
        gap_summary="未配置任何真实搜索凭证，当前由高拟真合成引擎生成估算数据。",
        remediation="在设置页填入 Google (API Key + CX) 或 Bing API Key 以激活真实搜索引擎链路。",
    )


def evaluate_ecommerce_source_provenance() -> DataProvenance:
    """Evaluate the real-data readiness of the ecommerce crawl/extraction source.

    Uses Jina Reader API if configured, falls back to direct HTTP scraping.
    """
    jina_key = _env("SEO_AD_BOT_JINA_KEY", "JINA_KEY")

    if jina_key:
        return DataProvenance(
            source_tier="real",
            provider="jina_reader_api",
            is_fresh=True,
            gap_type="none",
            gap_summary="Jina Reader API 已配置，可规避反爬并获取真实页面内容。",
            remediation="",
        )

    return DataProvenance(
        source_tier="partial",
        provider="http_direct_scraper",
        is_fresh=False,
        gap_type="missing_credential",
        gap_summary="未配置 Jina Reader API Key，当前依赖直接 HTTP 抓取（易遭反爬阻断）+ 合成估算兜底。",
        remediation="在设置页填入 Jina API Key 以提升电商页面抓取成功率，或接入 Playwright 真实浏览器方案。",
    )


# Weight each tier when computing an aggregate 0–100 data-trust score.
_TIER_WEIGHT: dict[SourceTier, float] = {
    "real": 1.0,
    "partial": 0.5,
    "synthetic": 0.0,
    "unknown": 0.0,
}


def build_data_trust_report() -> dict:
    """Aggregate provenance across all evaluable data sources.

    Returns a workspace-level report with a 0–100 ``dataTrustScore``, the tier
    distribution, and the per-source gaps (sorted so blocking / non-real
    sources surface first).
    """
    sources: dict[str, DataProvenance] = {
        "search": evaluate_search_source_provenance(),
        "ecommerce": evaluate_ecommerce_source_provenance(),
    }

    tier_counts: dict[str, int] = {"real": 0, "partial": 0, "synthetic": 0, "unknown": 0}
    weighted_sum = 0.0
    for provenance in sources.values():
        tier_counts[provenance.source_tier] += 1
        weighted_sum += _TIER_WEIGHT.get(provenance.source_tier, 0.0)

    total = max(len(sources), 1)
    data_trust_score = round((weighted_sum / total) * 100)

    # Non-real sources first (they carry actionable gaps), then by source key.
    def _sort_key(item: tuple[str, DataProvenance]) -> tuple[int, str]:
        return (0 if not item[1].is_real else 1, item[0])

    source_items = sorted(sources.items(), key=_sort_key)

    return {
        "dataTrustScore": data_trust_score,
        "realSourceCount": tier_counts["real"],
        "totalSourceCount": total,
        "tierDistribution": tier_counts,
        "sources": [
            {"sourceId": key, **provenance.model_dump(by_alias=True)}
            for key, provenance in source_items
        ],
        "gaps": [
            {"sourceId": key, **provenance.model_dump(by_alias=True)}
            for key, provenance in source_items
            if not provenance.is_real
        ],
    }


# Map api_source labels used elsewhere in the codebase to the provenance tier,
# so legacy consumers can be migrated without changing their string contract.
API_SOURCE_TO_TIER: dict[str, SourceTier] = {

    "google_custom_search": "real",
    "bing_web_search": "real",
    "jina_reader_api": "real",
    "http_direct_scraper": "partial",
    "synthetic_fallback": "synthetic",
    "synthetic": "synthetic",
}

