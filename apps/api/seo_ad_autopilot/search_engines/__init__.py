"""Search engines package — unified export for all adapters.

Phase 1 P1 (SE-001): all adapters exported from this package.

Standard interface each adapter exposes:
    adapter.search(query, num_results=10, locale="en", **kwargs)
    -> list[SearchResult]

SearchResult fields: title, url, snippet, position, [feature], [source]
"""

from .base import (
    SearchEngine,
    SearchResult,
    SearchFeature,
    SearchProvider,
)

from .google     import GoogleSearchEngine
from .bing       import BingSearchEngine
from .baidu      import BaiduSearchEngine
from .yandex     import YandexSearchEngine
from .chatgpt    import ChatGPTGEOEngine as ChatGPTSearchEngine
from .claude     import ClaudeGEOEngine as ClaudeSearchEngine
from .perplexity import PerplexityGEOEngine as PerplexitySearchEngine
from .chinese_ai import DeepSeekGEOEngine as ChineseAISearchEngine
from .qihoo360   import Qihoo360SearchEngine
from .sogou      import SogouSearchEngine
from .latest     import DuckDuckGoSearchEngine as LatestSearchEngine

__all__ = [
    # Base classes / models
    "SearchEngine",
    "SearchResult",
    "SearchFeature",
    "SearchProvider",
    # Traditional search engines
    "GoogleSearchEngine",
    "BingSearchEngine",
    "BaiduSearchEngine",
    "YandexSearchEngine",
    # AI-powered search engines
    "ChatGPTSearchEngine",
    "ClaudeSearchEngine",
    "PerplexitySearchEngine",
    "ChineseAISearchEngine",
    # Chinese traditional engines
    "Qihoo360SearchEngine",
    "SogouSearchEngine",
    # Latest / experimental
    "LatestSearchEngine",
]

# Convenience lookup: engine_name (lower) → class
ENGINE_REGISTRY: dict[str, type] = {
    "google":      GoogleSearchEngine,
    "bing":        BingSearchEngine,
    "baidu":       BaiduSearchEngine,
    "yandex":      YandexSearchEngine,
    "chatgpt":     ChatGPTSearchEngine,
    "claude":      ClaudeSearchEngine,
    "perplexity":  PerplexitySearchEngine,
    "chinese_ai":  ChineseAISearchEngine,
    "qihoo360":    Qihoo360SearchEngine,
    "sogou":       SogouSearchEngine,
    "latest":      LatestSearchEngine,
}


def get_engine(name: str) -> "SearchEngine":
    """Instantiate a search engine adapter by name (case-insensitive)."""
    cls = ENGINE_REGISTRY.get(name.lower())
    if cls is None:
        available = list(ENGINE_REGISTRY)
        raise ValueError(
            f"Unknown search engine {name!r}. "
            f"Available engines: {available}"
        )
    return cls()
