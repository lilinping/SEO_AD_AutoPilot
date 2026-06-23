"""Search Engine abstraction layer.

Supports both traditional SEO (Google, Bing, Baidu, Yandex) and
GEO (Generative Engine Optimization) for AI search (ChatGPT, Perplexity, Claude).

Design principles:
- Each search engine is a pluggable module
- Unified interface for all search engines
- GEO-specific optimizations for AI search engines
- Auto-discovery of best-performing engines per site
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SearchEngineType(str, Enum):
    """Search engine type."""
    TRADITIONAL_SEO = "traditional_seo"
    GEO = "generative_engine_optimization"


class SearchEngineCategory(str, Enum):
    """Search engine category."""
    GOOGLE = "google"
    BING = "bing"
    BAIDU = "baidu"
    YANDEX = "yandex"
    DUCKDUCKGO = "duckduckgo"
    NAVER = "naver"
    CHATGPT = "chatgpt"
    PERPLEXITY = "perplexity"
    CLAUDE = "claude"
    GOOGLE_AI_OVERVIEWS = "google_ai_overviews"
    OTHER = "other"


@dataclass
class SearchQuery:
    """Search query with context."""
    query: str
    language: str = "en"
    country: str = "us"
    device: str = "desktop"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """Search result from any engine."""
    title: str
    url: str
    snippet: str
    position: int
    engine: SearchEngineCategory
    features: list[str] = field(default_factory=list)
    ai_overview: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GEOOptimization:
    """GEO-specific optimization recommendations."""
    engine: SearchEngineCategory
    recommendations: list[str]
    entity_optimization: list[str]
    structured_data_needed: list[str]
    citation_signals: list[str]
    content_format_tips: list[str]
    confidence: float = 0.0


@dataclass
class SiteAnalysis:
    """Analysis of how a site performs across search engines."""
    url: str
    rankings: dict[SearchEngineCategory, list[SearchResult]]
    geo_scores: dict[SearchEngineCategory, float]
    recommendations: dict[SearchEngineCategory, list[str]]
    overall_score: float = 0.0


class SearchEngine(ABC):
    """Base class for all search engines."""
    
    @property
    @abstractmethod
    def category(self) -> SearchEngineCategory:
        """Return the engine category."""
        pass
    
    @property
    @abstractmethod
    def engine_type(self) -> SearchEngineType:
        """Return the engine type (SEO or GEO)."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return human-readable engine name."""
        pass
    
    @abstractmethod
    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Execute a search and return results."""
        pass
    
    @abstractmethod
    def analyze_site(self, url: str) -> SiteAnalysis:
        """Analyze how a site performs on this engine."""
        pass
    
    def get_geo_optimizations(self, url: str) -> Optional[GEOOptimization]:
        """Get GEO-specific optimizations (only for GEO engines)."""
        if self.engine_type != SearchEngineType.GEO:
            return None
        return None
    
    def is_available(self) -> bool:
        """Check if this engine is available (API key configured, etc.)."""
        return True


class SearchEngineRegistry:
    """Registry for all available search engines."""
    
    def __init__(self):
        self._engines: dict[SearchEngineCategory, SearchEngine] = {}
    
    def register(self, engine: SearchEngine) -> None:
        """Register a search engine."""
        self._engines[engine.category] = engine
    
    def get(self, category: SearchEngineCategory) -> Optional[SearchEngine]:
        """Get a search engine by category."""
        return self._engines.get(category)
    
    def get_all(self) -> list[SearchEngine]:
        """Get all registered engines."""
        return list(self._engines.values())
    
    def get_seo_engines(self) -> list[SearchEngine]:
        """Get all traditional SEO engines."""
        return [
            e for e in self._engines.values()
            if e.engine_type == SearchEngineType.TRADITIONAL_SEO
        ]
    
    def get_geo_engines(self) -> list[SearchEngine]:
        """Get all GEO engines."""
        return [
            e for e in self._engines.values()
            if e.engine_type == SearchEngineType.GEO
        ]
    
    def get_available_engines(self) -> list[SearchEngine]:
        """Get all available engines."""
        return [e for e in self._engines.values() if e.is_available()]


def create_default_registry() -> SearchEngineRegistry:
    """Create a registry with all default search engines."""
    from .google import GoogleSearchEngine
    from .bing import BingSearchEngine
    from .baidu import BaiduSearchEngine
    from .yandex import YandexSearchEngine
    from .chatgpt import ChatGPTGEOEngine
    from .perplexity import PerplexityGEOEngine
    from .claude import ClaudeGEOEngine
    
    registry = SearchEngineRegistry()
    
    # Traditional SEO engines
    registry.register(GoogleSearchEngine())
    registry.register(BingSearchEngine())
    registry.register(BaiduSearchEngine())
    registry.register(YandexSearchEngine())
    
    # GEO engines
    registry.register(ChatGPTGEOEngine())
    registry.register(PerplexityGEOEngine())
    registry.register(ClaudeGEOEngine())
    
    return registry
