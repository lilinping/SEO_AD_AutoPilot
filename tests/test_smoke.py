"""Smoke tests — import checks + minimal unit tests.

Phase 1 P1 (GAP-010): covers P0 gaps (exports, routers, auto_discovery).
Run: pytest tests/ -v --tb=short
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project is importable
PROJECT_ROOT = Path(__file__).parent.parent
API_ROOT     = PROJECT_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))


# ── GAP-001: agents/__init__.py exports ──────────────────────────────────────

class TestAgentsExports:
    REQUIRED = [
        "Agent", "AgentRole", "AgentOutput", "DebateRound",
        "CoordinatorAgent", "PolicyGuardAgent",
        "SnifferAgent", "QueryAgent", "StrategistAgent", "UXReviewerAgent",
        "AIOOptimizerAgent", "GEOAgent", "RankTrackerAgent", "CompetitorAnalystAgent",
    ]

    def test_agents_init_syntax(self):
        path = API_ROOT / "seo_ad_autopilot" / "agents" / "__init__.py"
        src  = path.read_text()
        ast.parse(src)   # raises SyntaxError if broken

    def test_agents_init_has_all_exports(self):
        path = API_ROOT / "seo_ad_autopilot" / "agents" / "__init__.py"
        src  = path.read_text()
        for name in self.REQUIRED:
            assert name in src, f"{name} not in agents/__init__.py"

    def test_agents_all_list_complete(self):
        path = API_ROOT / "seo_ad_autopilot" / "agents" / "__init__.py"
        src  = path.read_text()
        # __all__ must contain every required symbol
        in_all = [n for n in self.REQUIRED if f'"{n}"' in src or f"'{n}'" in src]
        assert set(in_all) == set(self.REQUIRED), (
            f"Missing from __all__: {set(self.REQUIRED) - set(in_all)}"
        )


# ── GAP-002: skills/__init__.py exports ──────────────────────────────────────

class TestSkillsExports:
    NEW_SKILLS = [
        "LLMTxtGeneratorSkill", "EEATEnhancerSkill", "AIOCitationTrackerSkill",
        "RankSnapshotSkill", "SERPFeatureTrackerSkill",
        "CompetitorKeywordGapSkill", "ContentGapAnalysisSkill",
        "ContentDecayDetectorSkill",
        "CrUXCollectorSkill", "RUMSnippetInjectorSkill",
        "HeaderBiddingConfigGeneratorSkill", "FloorPriceOptimizerSkill", "AdRefreshStrategySkill",
    ]

    def test_skills_init_syntax(self):
        path = API_ROOT / "seo_ad_autopilot" / "skills" / "__init__.py"
        ast.parse(path.read_text())

    @pytest.mark.parametrize("skill_name", NEW_SKILLS)
    def test_new_skill_in_init(self, skill_name):
        src = (API_ROOT / "seo_ad_autopilot" / "skills" / "__init__.py").read_text()
        assert skill_name in src, f"{skill_name} not found in skills/__init__.py"


# ── GAP-003: routers/ all present ────────────────────────────────────────────

class TestRouters:
    REQUIRED_ROUTERS = [
        "__init__", "health", "agents", "analysis",
        "content", "ad_platforms", "rank_tracking",
        "competitor", "search_engines", "keywords", "ecommerce",
    ]

    @pytest.mark.parametrize("router_name", REQUIRED_ROUTERS)
    def test_router_file_exists(self, router_name):
        path = API_ROOT / "seo_ad_autopilot" / "routers" / f"{router_name}.py"
        assert path.exists(), f"routers/{router_name}.py is missing"

    @pytest.mark.parametrize("router_name", REQUIRED_ROUTERS)
    def test_router_file_syntax(self, router_name):
        path = API_ROOT / "seo_ad_autopilot" / "routers" / f"{router_name}.py"
        ast.parse(path.read_text())

    def test_routers_init_exports_all_routers(self):
        src = (API_ROOT / "seo_ad_autopilot" / "routers" / "__init__.py").read_text()
        assert "all_routers" in src

    def test_routers_init_imports_new_routers(self):
        src = (API_ROOT / "seo_ad_autopilot" / "routers" / "__init__.py").read_text()
        for name in ["health", "agents", "analysis", "content", "ad_platforms", "rank_tracking"]:
            assert name in src, f"router '{name}' not imported in routers/__init__.py"

    def test_create_app_registers_domain_routers(self):
        from apps.api.seo_ad_autopilot.app import create_app

        route_paths = {getattr(route, "path", "") for route in create_app().routes}
        for path in [
            "/api/agents/list",
            "/api/analysis/site",
            "/api/content/generate",
            "/api/ads/platforms",
            "/api/rank/snapshot",
            "/api/competitor/analyze",
            "/api/search/engines",
        ]:
            assert path in route_paths

    def test_agent_router_analyze_uses_async_entrypoint(self):
        src = (API_ROOT / "seo_ad_autopilot" / "routers" / "agents.py").read_text()
        assert "await coordinator.async_analyze" in src


# ── GAP-007: extracted service modules are usable ────────────────────────────

class TestExtractedServices:
    @pytest.mark.asyncio
    async def test_service_run_methods_return_actionable_results(self):
        from apps.api.seo_ad_autopilot.services import (
            AdService,
            CompetitorService,
            ContentService,
            CrawlService,
            NotificationService,
            RankingService,
            ReportService,
        )

        cases = [
            (CrawlService(), {"url": "https://example.com"}, "crawl"),
            (ContentService(), {"topic": "SEO checklist", "content_type": "faq"}, "content"),
            (AdService(), {"url": "https://example.com", "site_data": {"monthly_visits": 12000}}, "ad"),
            (CompetitorService(), {"url": "https://example.com", "competitors": ["https://competitor.example"]}, "competitor"),
            (RankingService(), {"url": "https://example.com", "keywords": ["seo tool"]}, "ranking"),
            (ReportService(), {"url": "https://example.com", "analysis_data": {"recommendations": []}}, "report"),
            (NotificationService(), {"title": "Smoke", "message": "Service check"}, "notification"),
        ]

        for service, kwargs, expected_type in cases:
            result = await service.run(**kwargs)
            assert result["status"] == "complete"
            assert result["service"] == expected_type
            assert "task_id" in result



# ── GAP-004: auto_discovery platform registration ────────────────────────────

class TestAutoDiscovery:
    def test_autodiscovery_mentions_amazon_ads(self):
        path = API_ROOT / "seo_ad_autopilot" / "ad_platforms" / "auto_discovery.py"
        assert "AmazonAdsPlatform" in path.read_text()

    def test_autodiscovery_mentions_prebid(self):
        path = API_ROOT / "seo_ad_autopilot" / "ad_platforms" / "auto_discovery.py"
        assert "PrebidHeaderBiddingPlatform" in path.read_text()

    def test_autodiscovery_syntax(self):
        path = API_ROOT / "seo_ad_autopilot" / "ad_platforms" / "auto_discovery.py"
        ast.parse(path.read_text())


# ── GAP-009: coordinator.py async features ───────────────────────────────────

class TestCoordinator:
    def test_coordinator_syntax(self):
        path = API_ROOT / "seo_ad_autopilot" / "agents" / "coordinator.py"
        ast.parse(path.read_text())

    def test_coordinator_has_async_analyze(self):
        src = (API_ROOT / "seo_ad_autopilot" / "agents" / "coordinator.py").read_text()
        assert "async def async_analyze" in src or "async def _async_analyze" in src

    def test_coordinator_has_asyncio_gather(self):
        src = (API_ROOT / "seo_ad_autopilot" / "agents" / "coordinator.py").read_text()
        assert "asyncio.gather" in src

    def test_coordinator_has_agent_filter(self):
        src = (API_ROOT / "seo_ad_autopilot" / "agents" / "coordinator.py").read_text()
        assert "agent_filter" in src

    def test_coordinator_has_dry_run(self):
        src = (API_ROOT / "seo_ad_autopilot" / "agents" / "coordinator.py").read_text()
        assert "dry_run" in src

    def test_coordinator_has_analysis_report(self):
        src = (API_ROOT / "seo_ad_autopilot" / "agents" / "coordinator.py").read_text()
        assert "class AnalysisReport" in src


# ── GAP-005: skills/generate.py async + LLM ──────────────────────────────────

class TestGenerateSkill:
    def test_generate_syntax(self):
        path = API_ROOT / "seo_ad_autopilot" / "skills" / "generate.py"
        ast.parse(path.read_text())

    def test_generate_has_async_execute(self):
        src = (API_ROOT / "seo_ad_autopilot" / "skills" / "generate.py").read_text()
        assert "async def execute" in src

    def test_generate_has_llm_router(self):
        src = (API_ROOT / "seo_ad_autopilot" / "skills" / "generate.py").read_text()
        assert "LLMCostRouter" in src

    def test_generate_has_multi_provider_dispatch(self):
        src = (API_ROOT / "seo_ad_autopilot" / "skills" / "generate.py").read_text()
        for provider in ["AsyncOpenAI", "AsyncAnthropic", "generativeai", "deepseek"]:
            assert provider in src.lower() or provider in src, (
                f"Provider {provider!r} not found in generate.py"
            )

    def test_generate_has_template_fallback(self):
        src = (API_ROOT / "seo_ad_autopilot" / "skills" / "generate.py").read_text()
        assert "_template_faq" in src and "_template_article" in src and "_template_howto" in src

    @pytest.mark.asyncio
    async def test_content_generator_faq_template_fallback(self, sample_skill_input):
        """ContentGeneratorSkill falls back to template when LLM unavailable."""
        src_path = API_ROOT / "seo_ad_autopilot" / "skills" / "generate.py"
        if not src_path.exists():
            pytest.skip("generate.py not found")
        try:
            from seo_ad_autopilot.skills.generate import ContentGeneratorSkill
            from seo_ad_autopilot.skills.base import SkillInput
        except ImportError:
            pytest.skip("Cannot import skill classes (dependencies not installed)")

        skill = ContentGeneratorSkill()
        inp   = SkillInput(
            url="",
            params={"content_type": "faq", "topic": "SEO best practices", "word_count": 300},
        )
        output = await skill.execute(inp)
        assert output is not None
        assert output.success is True
        data = output.data if hasattr(output, "data") else output.result
        assert "markdown" in data or "content" in data or data


# ── GAP-012: middleware presence ─────────────────────────────────────────────

class TestMiddleware:
    def test_request_logger_exists(self):
        path = API_ROOT / "seo_ad_autopilot" / "middleware" / "request_logger.py"
        assert path.exists(), "middleware/request_logger.py is missing"

    def test_request_logger_syntax(self):
        path = API_ROOT / "seo_ad_autopilot" / "middleware" / "request_logger.py"
        ast.parse(path.read_text())

    def test_request_logger_has_middleware_class(self):
        src = (API_ROOT / "seo_ad_autopilot" / "middleware" / "request_logger.py").read_text()
        assert "RequestLoggerMiddleware" in src

    def test_request_logger_has_request_id_contextvar(self):
        src = (API_ROOT / "seo_ad_autopilot" / "middleware" / "request_logger.py").read_text()
        assert "ContextVar" in src and "request_id" in src

    def test_structured_logging_function(self):
        src = (API_ROOT / "seo_ad_autopilot" / "middleware" / "request_logger.py").read_text()
        assert "configure_structured_logging" in src


# ── GAP-014: WebSocket progress ──────────────────────────────────────────────

class TestWebSocketProgress:
    def test_websocket_progress_exists(self):
        path = API_ROOT / "seo_ad_autopilot" / "websocket_progress.py"
        assert path.exists(), "websocket_progress.py is missing"

    def test_websocket_progress_syntax(self):
        path = API_ROOT / "seo_ad_autopilot" / "websocket_progress.py"
        ast.parse(path.read_text())

    def test_has_ws_endpoint(self):
        src = (API_ROOT / "seo_ad_autopilot" / "websocket_progress.py").read_text()
        assert "@router.websocket" in src

    def test_has_task_registry(self):
        src = (API_ROOT / "seo_ad_autopilot" / "websocket_progress.py").read_text()
        assert "_TaskRegistry" in src or "registry" in src

    def test_has_progress_event(self):
        src = (API_ROOT / "seo_ad_autopilot" / "websocket_progress.py").read_text()
        assert "ProgressEvent" in src


# ── SE-001: search_engines/__init__.py ───────────────────────────────────────

class TestSearchEnginesInit:
    REQUIRED = [
        "GoogleSearchEngine", "BingSearchEngine", "BaiduSearchEngine",
        "ChatGPTSearchEngine", "ClaudeSearchEngine", "PerplexitySearchEngine",
        "ChineseAISearchEngine", "ENGINE_REGISTRY", "get_engine",
    ]

    def test_search_engines_init_syntax(self):
        path = API_ROOT / "seo_ad_autopilot" / "search_engines" / "__init__.py"
        ast.parse(path.read_text())

    @pytest.mark.parametrize("symbol", REQUIRED)
    def test_search_engines_init_has_symbol(self, symbol):
        src = (API_ROOT / "seo_ad_autopilot" / "search_engines" / "__init__.py").read_text()
        assert symbol in src, f"{symbol} not found in search_engines/__init__.py"


# ── GAP-006: real_data_v2.py ─────────────────────────────────────────────────

class TestRealDataV2:
    def test_real_data_v2_syntax(self):
        path = API_ROOT / "seo_ad_autopilot" / "skills" / "real_data_v2.py"
        if not path.exists():
            pytest.skip("real_data_v2.py not yet created")
        ast.parse(path.read_text())

    def test_has_async_execute(self):
        src = (API_ROOT / "seo_ad_autopilot" / "skills" / "real_data_v2.py").read_text()
        assert "async def execute" in src

    def test_has_retry_logic(self):
        src = (API_ROOT / "seo_ad_autopilot" / "skills" / "real_data_v2.py").read_text()
        assert "_request_with_retry" in src or "retry" in src.lower()

    def test_has_dataforseo_and_serpapi(self):
        src = (API_ROOT / "seo_ad_autopilot" / "skills" / "real_data_v2.py").read_text()
        assert "DataForSEO" in src
        assert "SerpAPI" in src
