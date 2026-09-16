"""Yandex Search Engine implementation with XML Search API integration."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .base import (
    SearchEngine,
    SearchEngineCategory,
    SearchEngineType,
    SearchQuery,
    SearchResult,
    SiteAnalysis,
)


class YandexSearchEngine(SearchEngine):
    """Yandex XML search engine for Russian market SEO."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        user: Optional[str] = None,
        base_url: str = "https://yandex.com/search/xml",
    ):
        self._api_key = api_key or os.getenv("SEO_AD_BOT_YANDEX_API_KEY", "")
        self._user = user or os.getenv("SEO_AD_BOT_YANDEX_USER", "")
        self._base_url = base_url

    @property
    def category(self) -> SearchEngineCategory:
        return SearchEngineCategory.YANDEX

    @property
    def engine_type(self) -> SearchEngineType:
        return SearchEngineType.TRADITIONAL_SEO

    @property
    def name(self) -> str:
        return "Yandex"

    def is_available(self) -> bool:
        return bool(self._api_key and self._user)

    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search Yandex using XML Search API."""
        if not self.is_available():
            return []

        params = {
            "user": self._user,
            "key": self._api_key,
            "query": query.query,
            "l10n": query.language or "en",
            "sortby": "rlv",
            "filter": "strict",
            "groupby": "attr=d.mode=deep.groups-on-page=10.docs-in-group=1",
        }
        if query.country:
            params["lr"] = query.country

        try:
            url = f"{self._base_url}?{urlencode(params)}"
            request = Request(url, headers={"User-Agent": "SEO-AD-AutoPilot/1.0"})
            with urlopen(request, timeout=10) as response:
                xml_text = response.read().decode("utf-8", errors="ignore")
            return self._parse_results(xml_text)
        except (HTTPError, URLError, ET.ParseError, Exception) as exc:
            print(f"[Yandex] Search error: {exc}")
            return []

    def _parse_results(self, xml_text: str) -> list[SearchResult]:
        root = ET.fromstring(xml_text)
        results = []
        for position, doc in enumerate(root.findall(".//doc"), 1):
            url = _text(doc, "url")
            title = _plain_text(doc.find("title"))
            snippet = _plain_text(doc.find("headline")) or _plain_text(doc.find("passages/passage"))
            if not url and not title:
                continue
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    position=position,
                    engine=self.category,
                    features=_extract_features(doc),
                    metadata={
                        "domain": _text(doc, "domain"),
                        "charset": _text(doc, "charset"),
                    },
                )
            )
        return results

    def analyze_site(self, url: str) -> SiteAnalysis:
        """Analyze site performance on Yandex."""
        results = self.search(SearchQuery(query=f"site:{url}", language="ru", country="ru"))
        return SiteAnalysis(
            url=url,
            rankings={self.category: results},
            geo_scores={self.category: self._calculate_score(results)},
            recommendations={self.category: self._generate_recommendations(results)},
        )

    def _calculate_score(self, results: list[SearchResult]) -> float:
        if not results:
            return 0.0
        return min(100.0, len(results) * 10.0)

    def _generate_recommendations(self, results: list[SearchResult]) -> list[str]:
        if not results:
            return [
                "Site not indexed - register with Yandex.Webmaster",
                "Submit XML sitemap to Yandex",
            ]
        return self.get_seo_recommendations("")

    def get_seo_recommendations(self, url: str) -> list[str]:
        """Get Yandex-specific SEO recommendations."""
        return [
            "Register site with Yandex.Webmaster",
            "Submit XML sitemap to Yandex",
            "Yandex values Russian language content",
            "Yandex favors Yandex.Maps integration",
            "Yandex values Yandex.Metrica usage",
            "Social signals from VK and Odnoklassniki matter",
            "Yandex values unique, high-quality content",
            "Yandex favors fast loading times",
            "Yandex values mobile-friendly sites",
            "Yandex values HTTPS sites",
        ]


def _text(parent: ET.Element, path: str) -> str:
    child = parent.find(path)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _plain_text(element: Optional[ET.Element]) -> str:
    if element is None:
        return ""
    text = "".join(element.itertext())
    return re.sub(r"\s+", " ", text).strip()


def _extract_features(doc: ET.Element) -> list[str]:
    features = []
    if doc.find("headline") is not None:
        features.append("headline")
    if doc.find("passages/passage") is not None:
        features.append("passage")
    if _text(doc, "domain"):
        features.append("domain")
    return features
