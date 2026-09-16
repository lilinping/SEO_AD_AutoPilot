from typing import Any, Optional, Dict, List
import logging
from pydantic import BaseModel, Field
import os
import math
from urllib.parse import urlparse

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel
from ..search_engines.base import SearchQuery, SearchResult
from ..search_engines.google import GoogleSearchEngine
from ..search_engines.bing import BingSearchEngine
from ..data_provenance import DataProvenance, evaluate_search_source_provenance

logger = logging.getLogger(__name__)

class KeywordData(BaseModel):
    keyword: str
    search_volume: int = 0
    difficulty: float = 0.0
    cpc: float = 0.0
    competition: float = 0.0
    intent: str = "informational"
    serp_features: list[str] = Field(default_factory=list)
    long_tail_variants: list[str] = Field(default_factory=list)
    related_keywords: list[str] = Field(default_factory=list)

class KeywordAnalysisResult(BaseModel):
    query: str
    target_market: str = "US"
    language: str = "en"
    keywords: list[KeywordData] = Field(default_factory=list)
    categories: dict[str, list[str]] = Field(default_factory=dict)
    top_domains: list[str] = Field(default_factory=list)
    overall_competition: float = 0.0
    serp_features_distribution: dict[str, int] = Field(default_factory=dict)
    api_source: str = "synthetic"
    provenance: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class KeywordResearchSkill(Skill):
    """Skill for conducting keyword research and search market analysis using real APIs."""

    def __init__(self) -> None:
        super().__init__()
        # Initialize real search engines. Read credentials from either the
        # SEO_AD_BOT_* prefixed names or the bare names so the skill and the
        # underlying engines agree on what is actually configured.
        google_key = os.getenv("SEO_AD_BOT_GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        google_cx = os.getenv("SEO_AD_BOT_GOOGLE_CX") or os.getenv("GOOGLE_CX") or ""
        bing_key = os.getenv("SEO_AD_BOT_BING_API_KEY") or os.getenv("BING_API_KEY") or ""
        self.google_engine = GoogleSearchEngine(api_key=google_key, cx=google_cx)
        self.bing_engine = BingSearchEngine(api_key=bing_key)


    @property
    def name(self) -> str:
        return "KeywordResearch"

    @property
    def description(self) -> str:
        return "Conduct keyword research, analyze search volumes, difficulty, intent, and cluster keyword topical taxonomy."

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ANALYZE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        params = skill_input.params
        logger.info(f"Executing KeywordResearch with params: {params}")

        query_keyword = (params.get("query") or params.get("keyword") or params.get("seed") or "").strip()
        target_market = str(params.get("target_market", "US")).strip().upper()
        language = str(params.get("language", "en")).strip().lower()

        if not query_keyword:
            return self._create_output(
                success=False,
                error="Query keyword is required",
            )

        warnings = []
        api_source = "synthetic"

        # Determine the real data source from each engine's *actual* readiness,
        # not merely from the presence of an API key. Google Custom Search only
        # works when BOTH the API key and the CX (search engine id) are set, so
        # relying on the key alone silently mislabels synthetic estimates as
        # real Google data. Detect partial configuration and surface it instead.
        has_google_key = bool(os.getenv("SEO_AD_BOT_GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        google_ready = self.google_engine.is_available()
        bing_ready = self.bing_engine.is_available()

        if google_ready:
            api_source = "google_custom_search"
        elif bing_ready:
            api_source = "bing_web_search"
        else:
            api_source = "synthetic_fallback"
            if has_google_key and not google_ready:
                warnings.append(
                    "已配置 Google API Key 但缺少 SEO_AD_BOT_GOOGLE_CX（Custom Search 引擎 ID），"
                    "Google 真实搜索链路未激活，当前结果由高拟真合成引擎生成。请补全 CX 以启用真实 Google 搜索。"
                )
            else:
                warnings.append(
                    "未配置 Google/Bing 真实搜索凭证 (SEO_AD_BOT_GOOGLE_API_KEY + SEO_AD_BOT_GOOGLE_CX / SEO_AD_BOT_BING_API_KEY)，"
                    "当前结果由高拟真合成引擎生成。请在系统设置中填入 API 凭证以激活真实搜索引擎链路。"
                )


        # Generate related and long tail candidates
        seed_keywords = [query_keyword]
        seed_keywords.extend(self._generate_long_tail(query_keyword)[:5])
        seed_keywords.extend(self._generate_related(query_keyword)[:5])

        # Unique list
        seen = set()
        keywords_list = []
        for kw in seed_keywords:
            kw_clean = kw.lower().strip()
            if kw_clean and kw_clean not in seen:
                seen.add(kw_clean)
                keywords_list.append(kw_clean)

        # Analyze each keyword
        keywords_data = []
        all_serp_results = []

        for kw in keywords_list[:10]: # Process up to 10 for performance
            real_results = self._fetch_real_serp(kw, api_source)
            if real_results:
                all_serp_results.extend(real_results)

            data = self._analyze_single_keyword(kw, real_results, params)
            keywords_data.append(data)

        # Categorization & taxonomy clustering
        categories = self._cluster_keywords(keywords_data)

        # Retrieve top domains & features
        top_domains = self._extract_top_domains(all_serp_results)
        if not top_domains:
            # Fallback mock domains matching query
            top_domains = [f"www.best{query_keyword.replace(' ', '')}.com", f"www.{query_keyword.replace(' ', '')}guide.org", "www.amazon.com", "www.wikipedia.org"]

        serp_features_dist = {}
        for kw_d in keywords_data:
            for feat in kw_d.serp_features:
                serp_features_dist[feat] = serp_features_dist.get(feat, 0) + 1

        overall_comp = sum(k.competition for k in keywords_data) / max(len(keywords_data), 1)

        # Attach a unified data-provenance label so downstream consumers can
        # tell real data from synthetic estimates without re-deriving it.
        provenance = evaluate_search_source_provenance()
        if provenance.is_real and not all_serp_results:
            # Real source is configured but returned nothing this run: the data
            # actually served fell back to estimates, so do not claim "real".
            provenance = DataProvenance(
                source_tier="partial",
                provider=provenance.provider,
                is_fresh=False,
                gap_type="provider_error",
                gap_summary="真实搜索源已配置但本次未返回结果，当前数据包含合成估算。",
                remediation="检查搜索凭证配额/网络连通性后重试。",
            )

        result = KeywordAnalysisResult(
            query=query_keyword,
            target_market=target_market,
            language=language,
            keywords=keywords_data,
            categories=categories,
            top_domains=top_domains,
            overall_competition=overall_comp,
            serp_features_distribution=serp_features_dist,
            api_source=api_source,
            provenance=provenance.model_dump(by_alias=True),
            warnings=warnings
        )


        return self._create_output(
            success=True,
            result=result.model_dump(),
        )

    def _fetch_real_serp(self, keyword: str, source: str) -> list[SearchResult]:
        try:
            query = SearchQuery(query=keyword)
            if source == "google_custom_search":
                return self.google_engine.search(query)
            elif source == "bing_web_search":
                return self.bing_engine.search(query)
        except Exception as e:
            logger.error(f"Failed to fetch real search results for '{keyword}' via {source}: {e}")
        return []

    def _analyze_single_keyword(self, keyword: str, real_results: list[SearchResult], params: dict[str, Any]) -> KeywordData:
        data = KeywordData(keyword=keyword)
        word_count = len(keyword.split())

        # Estimate / Retrieve Volume
        base_vol = 12000
        if word_count == 1:
            base_vol = 48000
        elif word_count == 2:
            base_vol = 24000
        elif word_count == 3:
            base_vol = 8000
        else:
            base_vol = 1500

        # Adjust base_vol slightly based on real SERP index size if available
        if real_results:
            base_vol = int(base_vol * (1.0 + (len(real_results) * 0.05)))

        data.search_volume = base_vol

        # Estimate / Retrieve Difficulty & Competition
        if real_results:
            # Calculate metrics based on top domain strengths
            high_authority_domains = ["wikipedia.org", "amazon.com", "reddit.com", "github.com", "youtube.com"]
            match_count = 0
            for res in real_results:
                for ha in high_authority_domains:
                    if ha in res.url.lower():
                        match_count += 1
            data.difficulty = min(35.0 + (match_count * 12.0) + (word_count * -3.0), 100.0)
            data.competition = min(0.1 + (match_count * 0.15) + (len(real_results) * 0.05), 1.0)
        else:
            data.difficulty = max(10.0, min(95.0, 65.0 - (word_count * 8.0) + (hash(keyword) % 15)))
            data.competition = max(0.05, min(1.0, 0.75 - (word_count * 0.1) + ((hash(keyword) % 20) / 100.0)))

        # Estimates for CPC
        data.cpc = max(0.15, round(2.5 - (word_count * 0.25) + ((hash(keyword) % 10) / 5.0), 2))

        # Intent classification
        keyword_lower = keyword.lower()
        if any(w in keyword_lower for w in ["buy", "price", "cost", "shop", "cheap", "store", "sale"]):
            data.intent = "transactional"
        elif any(w in keyword_lower for w in ["best", "review", "vs", "compare", "top"]):
            data.intent = "commercial"
        elif any(w in keyword_lower for w in ["how", "why", "what", "guide", "tutorial", "learn"]):
            data.intent = "informational"
        else:
            data.intent = "navigational" if word_count == 1 else "informational"

        # Features
        features = ["organic"]
        if real_results:
            for r in real_results:
                if getattr(r, "features", []):
                    features.extend(r.features)
        else:
            # Predict features synthetically
            if data.intent == "transactional":
                features.extend(["shopping_ads", "reviews"])
            elif data.intent == "commercial":
                features.extend(["sitelinks", "images"])
            elif data.intent == "informational":
                features.extend(["people_also_ask", "rich_snippet"])

        data.serp_features = list(set(features))
        data.long_tail_variants = self._generate_long_tail(keyword)[:3]
        data.related_keywords = self._generate_related(keyword)[:3]
        return data

    def _cluster_keywords(self, keywords_data: list[KeywordData]) -> dict[str, list[str]]:
        categories = {}
        for kw_d in keywords_data:
            intent_key = f"Intent: {kw_d.intent.capitalize()}"
            if intent_key not in categories:
                categories[intent_key] = []
            categories[intent_key].append(kw_d.keyword)

            # Additional clustering based on length
            len_key = "Long-tail Keywords" if len(kw_d.keyword.split()) >= 3 else "Short-tail Keywords"
            if len_key not in categories:
                categories[len_key] = []
            categories[len_key].append(kw_d.keyword)
        return categories

    def _extract_top_domains(self, results: list[SearchResult]) -> list[str]:
        domains = []
        for r in results:
            try:
                domain = urlparse(r.url).netloc
                if domain.startswith("www."):
                    domain = domain[4:]
                if domain and domain not in domains:
                    domains.append(domain)
            except Exception:
                pass
        return domains[:6]

    def _generate_long_tail(self, keyword: str) -> list[str]:
        return [
            f"best {keyword} for beginners",
            f"how to use {keyword} effectively",
            f"cheap {keyword} alternative online",
            f"top 10 {keyword} platform review"
        ]

    def _generate_related(self, keyword: str) -> list[str]:
        return [
            f"{keyword} tutorial",
            f"{keyword} cost",
            f"{keyword} software",
            f"free {keyword} tool"
        ]
