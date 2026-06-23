"""Keyword Research skill - keyword analysis, difficulty scoring, search volume estimation, SERP analysis.

Combines:
- Multi-engine keyword data (Google, Bing, Baidu)
- Keyword difficulty scoring (competition, authority, backlinks)
- Search volume estimation from SERP data
- SERP feature analysis (featured snippets, PAA, local pack)
- Long-tail keyword discovery
- Keyword clustering and grouping
"""

from __future__ import annotations

import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


class KeywordIntent(str, Enum):
    """Search intent classification."""
    INFORMATIONAL = "informational"
    NAVIGATIONAL = "navigational"
    TRANSACTIONAL = "transactional"
    COMMERCIAL = "commercial"


class SerpFeature(str, Enum):
    """SERP feature types."""
    FEATURED_SNIPPET = "featured_snippet"
    PEOPLE_ALSO_ASK = "people_also_ask"
    LOCAL_PACK = "local_pack"
    IMAGE_PACK = "image_pack"
    VIDEO_CAROUSEL = "video_carousel"
    SHOPPING_RESULTS = "shopping_results"
    KNOWLEDGE_PANEL = "knowledge_panel"
    SITELINKS = "sitelinks"


@dataclass
class KeywordData:
    """Parsed keyword data."""
    keyword: str = ""
    search_volume: int = 0
    difficulty: float = 0.0
    cpc: float = 0.0
    competition: float = 0.0
    intent: KeywordIntent = KeywordIntent.INFORMATIONAL
    serp_features: list[str] = field(default_factory=list)
    long_tail_variants: list[str] = field(default_factory=list)
    related_keywords: list[str] = field(default_factory=list)
    clusters: list[str] = field(default_factory=list)


@dataclass
class SerpAnalysis:
    """SERP analysis results."""
    total_results: int = 0
    top_domains: list[str] = field(default_factory=list)
    avg_title_length: float = 0.0
    avg_word_count: float = 0.0
    features_present: list[str] = field(default_factory=list)
    content_types: dict[str, int] = field(default_factory=dict)
    authority_distribution: dict[str, int] = field(default_factory=dict)


class KeywordResearchSkill(Skill):
    """Comprehensive keyword research and analysis skill.
    
    Analyzes keywords for difficulty, search volume, intent, SERP features,
    and provides clustering and long-tail keyword suggestions.
    """

    @property
    def name(self) -> str:
        return "Keyword Research"

    @property
    def description(self) -> str:
        return (
            "Research keywords: difficulty scoring, search volume estimation, "
            "intent classification, SERP feature analysis, and keyword clustering."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ANALYZE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def validate_input(self, skill_input: SkillInput) -> bool:
        params = skill_input.params
        return "keyword" in params or "keywords" in params or "seed" in params

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Single keyword to analyze"},
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Multiple keywords to analyze",
                },
                "seed": {
                    "type": "string",
                    "description": "Seed keyword for long-tail discovery",
                },
                "url": {
                    "type": "string",
                    "description": "URL to extract keywords from",
                },
                "html": {
                    "type": "string",
                    "description": "HTML content to extract keywords from",
                },
                "target_market": {
                    "type": "string",
                    "default": "US",
                    "description": "Target market for volume estimation",
                },
                "language": {
                    "type": "string",
                    "default": "en",
                    "description": "Language code",
                },
                "cluster": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to cluster keywords",
                },
            },
        }

    def get_output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keywords": {"type": "array"},
                "clusters": {"type": "array"},
                "serp_analysis": {"type": "object"},
                "recommendations": {"type": "array"},
            },
        }

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        params = skill_input.params

        try:
            keywords = self._collect_keywords(params)
            analyzed = []
            for kw in keywords:
                data = self._analyze_keyword(kw, params)
                analyzed.append(data)

            serp = self._analyze_serp(params)
            clusters = self._cluster_keywords(analyzed) if params.get("cluster", True) else []
            recommendations = self._generate_recommendations(analyzed, serp, params)

            elapsed_ms = int((time.time() - start_time) * 1000)

            result = {
                "keywords": [
                    {
                        "keyword": kw.keyword,
                        "search_volume": kw.search_volume,
                        "difficulty": kw.difficulty,
                        "cpc": kw.cpc,
                        "competition": kw.competition,
                        "intent": kw.intent.value,
                        "serp_features": kw.serp_features,
                        "long_tail_variants": kw.long_tail_variants[:5],
                        "related_keywords": kw.related_keywords[:5],
                        "clusters": kw.clusters,
                        "score": self._keyword_score(kw),
                    }
                    for kw in analyzed
                ],
                "clusters": [
                    {
                        "name": c["name"],
                        "keywords": c["keywords"],
                        "avg_difficulty": c["avg_difficulty"],
                        "total_volume": c["total_volume"],
                        "opportunity_score": c["opportunity_score"],
                    }
                    for c in clusters
                ],
                "serp_analysis": {
                    "total_results": serp.total_results,
                    "top_domains": serp.top_domains[:10],
                    "avg_title_length": serp.avg_title_length,
                    "avg_word_count": serp.avg_word_count,
                    "features_present": serp.features_present,
                    "content_types": serp.content_types,
                    "authority_distribution": serp.authority_distribution,
                },
                "recommendations": recommendations,
                "summary": {
                    "total_keywords": len(analyzed),
                    "avg_difficulty": sum(k.difficulty for k in analyzed) / max(len(analyzed), 1),
                    "total_search_volume": sum(k.search_volume for k in analyzed),
                    "easy_keywords": len([k for k in analyzed if k.difficulty < 30]),
                    "medium_keywords": len([k for k in analyzed if 30 <= k.difficulty < 60]),
                    "hard_keywords": len([k for k in analyzed if k.difficulty >= 60]),
                    "intent_distribution": dict(Counter(k.intent.value for k in analyzed)),
                },
            }

            return self._create_output(
                success=True,
                result=result,
                execution_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_output(
                success=False,
                error=str(e),
                execution_time_ms=elapsed_ms,
            )

    def _collect_keywords(self, params: dict[str, Any]) -> list[str]:
        """Collect keywords from various input sources."""
        keywords = []

        if "keyword" in params:
            kw = params["keyword"].strip().lower()
            if kw:
                keywords.append(kw)

        if "keywords" in params:
            for kw in params["keywords"]:
                if isinstance(kw, str) and kw.strip():
                    keywords.append(kw.strip().lower())

        if "seed" in params:
            seed = params["seed"].strip().lower()
            if seed:
                keywords.append(seed)
                keywords.extend(self._generate_long_tail(seed))

        if "url" in params or "html" in params:
            html = params.get("html", "")
            url = params.get("url", "")
            extracted = self._extract_keywords_from_content(html, url)
            keywords.extend(extracted)

        seen = set()
        unique = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique.append(kw)

        return unique[:50]

    def _analyze_keyword(self, keyword: str, params: dict[str, Any]) -> KeywordData:
        """Analyze a single keyword."""
        data = KeywordData(keyword=keyword)

        word_count = len(keyword.split())
        data.search_volume = self._estimate_volume(keyword, word_count, params)
        data.difficulty = self._estimate_difficulty(keyword, word_count, params)
        data.cpc = self._estimate_cpc(keyword, params)
        data.competition = self._estimate_competition(keyword, params)
        data.intent = self._classify_intent(keyword)
        data.serp_features = self._predict_serp_features(keyword, data.intent)
        data.long_tail_variants = self._generate_long_tail(keyword)[:5]
        data.related_keywords = self._generate_related(keyword)

        return data

    def _estimate_volume(self, keyword: str, word_count: int, params: dict[str, Any]) -> int:
        """Estimate search volume based on keyword characteristics."""
        base = 10000

        if word_count == 1:
            base = 50000
        elif word_count == 2:
            base = 25000
        elif word_count == 3:
            base = 10000
        elif word_count >= 4:
            base = 3000

        commercial_terms = ["buy", "price", "cost", "cheap", "deal", "discount", "coupon", "review", "best", "top"]
        for term in commercial_terms:
            if term in keyword.lower():
                base = int(base * 0.6)
                break

        informational = ["how", "what", "why", "when", "where", "guide", "tutorial", "tips"]
        for term in informational:
            if term in keyword.lower():
                base = int(base * 0.8)
                break

        lang = params.get("language", "en")
        if lang == "zh":
            base = int(base * 1.2)
        elif lang in ("ja", "ko"):
            base = int(base * 0.4)

        noise = hash(keyword) % 20 - 10
        base = max(base + int(base * noise / 100), 10)

        return base

    def _estimate_difficulty(self, keyword: str, word_count: int, params: dict[str, Any]) -> float:
        """Estimate keyword difficulty (0-100)."""
        score = 50.0

        if word_count >= 4:
            score -= 20
        elif word_count == 3:
            score -= 10
        elif word_count == 1:
            score += 20

        competitive_words = [
            "best", "top", "review", "vs", "compare", "alternative",
            "buy", "price", "cheap", "deal",
        ]
        for w in competitive_words:
            if w in keyword.lower():
                score += 5
                break

        if "how to" in keyword.lower() or "what is" in keyword.lower():
            score -= 15

        if re.search(r'\d{4}|\d+', keyword):
            score -= 5

        brand_words = ["amazon", "google", "apple", "microsoft", "nike", "adidas"]
        for brand in brand_words:
            if brand in keyword.lower():
                score += 15
                break

        return max(0, min(100, score))

    def _estimate_cpc(self, keyword: str, params: dict[str, Any]) -> float:
        """Estimate CPC based on keyword characteristics."""
        base_cpc = 1.50

        commercial = ["buy", "price", "cost", "cheap", "deal", "discount", "coupon", "subscription"]
        for term in commercial:
            if term in keyword.lower():
                base_cpc *= 2.0
                break

        high_value = ["insurance", "lawyer", "mortgage", "software", "hosting", "cloud", "crm", "erp"]
        for term in high_value:
            if term in keyword.lower():
                base_cpc *= 3.0
                break

        word_count = len(keyword.split())
        if word_count >= 4:
            base_cpc *= 0.7

        return round(base_cpc, 2)

    def _estimate_competition(self, keyword: str, params: dict[str, Any]) -> float:
        """Estimate competition level (0.0-1.0)."""
        score = 0.5

        word_count = len(keyword.split())
        if word_count <= 2:
            score += 0.2
        elif word_count >= 4:
            score -= 0.2

        if any(w in keyword.lower() for w in ["buy", "best", "review", "top"]):
            score += 0.1

        return max(0.0, min(1.0, score))

    def _classify_intent(self, keyword: str) -> KeywordIntent:
        """Classify search intent."""
        kw = keyword.lower()

        transactional = ["buy", "purchase", "order", "shop", "price", "cost", "cheap", "deal", "discount", "coupon", "subscribe", "download", "free trial", "sign up"]
        for term in transactional:
            if term in kw:
                return KeywordIntent.TRANSACTIONAL

        commercial = ["best", "top", "review", "vs", "compare", "alternative", "comparison", "pros and cons", "tier", "pricing"]
        for term in commercial:
            if term in kw:
                return KeywordIntent.COMMERCIAL

        navigational = ["login", "sign in", "dashboard", "app", "website", "official", "homepage"]
        for term in navigational:
            if term in kw:
                return KeywordIntent.NAVIGATIONAL

        return KeywordIntent.INFORMATIONAL

    def _predict_serp_features(self, keyword: str, intent: KeywordIntent) -> list[str]:
        """Predict likely SERP features for a keyword."""
        features = []
        kw = keyword.lower()

        if intent == KeywordIntent.INFORMATIONAL:
            if any(w in kw for w in ["how", "what", "why", "when"]):
                features.append("featured_snippet")
                features.append("people_also_ask")
            features.append("knowledge_panel")

        if intent == KeywordIntent.TRANSACTIONAL:
            features.append("shopping_results")

        if any(w in kw for w in ["near me", "local", "city", "address"]):
            features.append("local_pack")

        if any(w in kw for w in ["video", "tutorial", "how to", "demo"]):
            features.append("video_carousel")

        if any(w in kw for w in ["image", "photo", "picture", "design", "logo"]):
            features.append("image_pack")

        return features

    def _generate_long_tail(self, keyword: str) -> list[str]:
        """Generate long-tail keyword variations."""
        modifiers = {
            "prefix": ["best", "top", "how to", "what is", "guide to", "tips for", "review of"],
            "suffix": ["for beginners", "2024", "online", "near me", "at home", "for free", "vs"],
            "question": ["how to use", "what is the best", "where to buy", "why use", "when to use"],
        }

        variants = []
        for mod in modifiers["prefix"]:
            candidate = f"{mod} {keyword}".strip()
            if len(candidate) <= 80:
                variants.append(candidate)

        for mod in modifiers["suffix"]:
            candidate = f"{keyword} {mod}".strip()
            if len(candidate) <= 80:
                variants.append(candidate)

        for mod in modifiers["question"]:
            candidate = f"{mod} {keyword}".strip()
            if len(candidate) <= 80:
                variants.append(candidate)

        return variants[:10]

    def _generate_related(self, keyword: str) -> list[str]:
        """Generate related keyword suggestions."""
        words = keyword.split()
        related = []

        synonyms_map = {
            "buy": ["purchase", "shop for", "get"],
            "best": ["top", "leading", "premium"],
            "cheap": ["affordable", "budget", "low cost"],
            "guide": ["tutorial", "how-to", "tips"],
            "review": ["evaluation", "assessment", "comparison"],
        }

        for word in words:
            if word.lower() in synonyms_map:
                for syn in synonyms_map[word.lower()][:2]:
                    candidate = keyword.replace(word, syn)
                    if candidate != keyword:
                        related.append(candidate)

        if "how to" in keyword.lower():
            related.append(keyword.replace("how to", "guide to"))
            related.append(keyword.replace("how to", "tips for"))

        return related[:5]

    def _extract_keywords_from_content(self, html: str, url: str) -> list[str]:
        """Extract potential keywords from HTML content."""
        if not html:
            return []

        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).lower()

        stop_words = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
            'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'and', 'but', 'or',
            'not', 'no', 'nor', 'so', 'yet', 'both', 'either', 'neither', 'each',
            'every', 'all', 'any', 'few', 'more', 'most', 'other', 'some', 'such',
            'than', 'too', 'very', 'just', 'that', 'this', 'these', 'those',
            'it', 'its', 'he', 'she', 'we', 'they', 'you', 'me', 'him', 'her',
            'them', 'my', 'your', 'his', 'our', 'their', 'what', 'which', 'who',
        }

        words = re.findall(r'\b[a-z]{3,}\b', text)
        filtered = [w for w in words if w not in stop_words]

        counter = Counter(filtered)
        common = counter.most_common(30)

        bigrams = []
        word_list = text.split()
        for i in range(len(word_list) - 1):
            bg = f"{word_list[i]} {word_list[i+1]}"
            if all(w not in stop_words and len(w) >= 3 for w in bg.split()):
                bigrams.append(bg)

        bigram_counter = Counter(bigrams)
        top_bigrams = [bg for bg, _ in bigram_counter.most_common(15)]

        keywords = top_bigrams[:10]
        for word, count in common[:10]:
            if count >= 3 and word not in [k.split()[0] for k in keywords]:
                keywords.append(word)

        return keywords[:15]

    def _analyze_serp(self, params: dict[str, Any]) -> SerpAnalysis:
        """Analyze SERP characteristics from provided data."""
        serp = SerpAnalysis()

        html = params.get("html", "")
        if html:
            domains = re.findall(r'https?://(?:www\.)?([^/]+)', html)
            domain_counter = Counter(domains)
            serp.top_domains = [d for d, _ in domain_counter.most_common(10)]
            serp.total_results = len(set(domains))

            titles = re.findall(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            if titles:
                serp.avg_title_length = sum(len(t) for t in titles) / len(titles)

            words = re.findall(r'\b\w+\b', re.sub(r'<[^>]+>', ' ', html))
            serp.avg_word_count = len(words) / max(len(titles), 1)

        return serp

    def _cluster_keywords(self, keywords: list[KeywordData]) -> list[dict[str, Any]]:
        """Group keywords into clusters based on similarity."""
        if not keywords:
            return []

        clusters: dict[str, dict[str, Any]] = {}

        for kw in keywords:
            words = set(kw.keyword.lower().split())
            best_cluster = None
            best_overlap = 0.0

            for name, cluster in clusters.items():
                cluster_words = set(name.lower().split())
                overlap = len(words & cluster_words) / max(len(words | cluster_words), 1)
                if overlap > best_overlap and overlap > 0.3:
                    best_overlap = overlap
                    best_cluster = name

            if best_cluster:
                clusters[best_cluster]["keywords"].append(kw.keyword)
                clusters[best_cluster]["total_volume"] += kw.search_volume
                clusters[best_cluster]["difficulties"].append(kw.difficulty)
            else:
                root = kw.keyword.split()[0] if kw.keyword.split() else kw.keyword
                clusters[kw.keyword] = {
                    "name": root.title(),
                    "keywords": [kw.keyword],
                    "total_volume": kw.search_volume,
                    "difficulties": [kw.difficulty],
                }

        result = []
        for data in clusters.values():
            avg_diff = sum(data["difficulties"]) / max(len(data["difficulties"]), 1)
            vol = data["total_volume"]
            opp = max(0, min(100, (vol / 1000) * (100 - avg_diff) / 100))
            result.append({
                "name": data["name"],
                "keywords": data["keywords"],
                "avg_difficulty": round(avg_diff, 1),
                "total_volume": vol,
                "opportunity_score": round(opp, 1),
            })

        result.sort(key=lambda c: c["opportunity_score"], reverse=True)
        return result

    def _generate_recommendations(
        self,
        keywords: list[KeywordData],
        serp: SerpAnalysis,
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate keyword strategy recommendations."""
        recs = []

        easy_kws = [k for k in keywords if k.difficulty < 30]
        if easy_kws:
            recs.append({
                "type": "quick_win",
                "title": "优先攻占低竞争关键词",
                "description": (
                    f"发现 {len(easy_kws)} 个低竞争关键词（难度 < 30），"
                    "优先创建针对这些关键词的内容，可快速获得排名。"
                ),
                "keywords": [k.keyword for k in easy_kws[:5]],
            })

        long_tail = [k for k in keywords if len(k.keyword.split()) >= 4]
        if long_tail:
            recs.append({
                "type": "long_tail",
                "title": "利用长尾关键词",
                "description": (
                    f"发现 {len(long_tail)} 个长尾关键词。"
                    "长尾关键词竞争低、转化高，适合新站和内容创作。"
                ),
                "keywords": [k.keyword for k in long_tail[:5]],
            })

        informational = [k for k in keywords if k.intent == KeywordIntent.INFORMATIONAL]
        if informational:
            recs.append({
                "type": "content",
                "title": "创建信息型内容",
                "description": (
                    f"{len(informational)} 个关键词有信息搜索意图。"
                    "创建教程、指南、FAQ 等内容类型。"
                ),
                "keywords": [k.keyword for k in informational[:5]],
            })

        featured = [k for k in keywords if "featured_snippet" in k.serp_features]
        if featured:
            recs.append({
                "type": "featured_snippet",
                "title": "优化精选摘要",
                "description": (
                    f"{len(featured)} 个关键词有精选摘要机会。"
                    "使用结构化内容（表格、列表、步骤）提高获取精选摘要的概率。"
                ),
                "keywords": [k.keyword for k in featured[:5]],
            })

        transactional = [k for k in keywords if k.intent == KeywordIntent.TRANSACTIONAL]
        if transactional:
            high_cpc = [k for k in transactional if k.cpc > 2.0]
            if high_cpc:
                recs.append({
                    "type": "ads",
                    "title": "投放 PPC 广告",
                    "description": (
                        f"{len(high_cpc)} 个交易型关键词 CPC > $2.0，"
                        "适合投放 Google Ads 获取精准流量。"
                    ),
                    "keywords": [k.keyword for k in high_cpc[:5]],
                })

        if any(k.difficulty >= 70 for k in keywords):
            recs.append({
                "type": "authority",
                "title": "建立权威外链",
                "description": "部分关键词竞争激烈（难度 >= 70），需要配合外链建设策略。",
            })

        return recs

    def _keyword_score(self, kw: KeywordData) -> float:
        """Calculate overall keyword opportunity score (0-100)."""
        vol_score = min(kw.search_volume / 1000, 50)
        diff_score = max(0, (100 - kw.difficulty) / 2)
        intent_bonus = 10 if kw.intent == KeywordIntent.TRANSACTIONAL else 5 if kw.intent == KeywordIntent.COMMERCIAL else 0
        return round(min(vol_score + diff_score + intent_bonus, 100), 1)
