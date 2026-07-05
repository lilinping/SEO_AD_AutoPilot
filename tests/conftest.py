"""pytest fixtures and configuration for SEO_AD_BOT test suite.

Phase 1 P1 (GAP-010):
- Shared fixtures for agents, skills, and API client
- Async event loop configuration (asyncio mode)
- Mock factories for external dependencies
"""

from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Event-loop configuration ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Provide a shared asyncio event loop for the entire test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# ── Env-var fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _no_real_api_calls(monkeypatch) -> None:
    """Prevent accidental real API calls by removing credentials from env."""
    for key in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY",
        "DEEPSEEK_API_KEY", "DATAFORSEO_LOGIN", "DATAFORSEO_PASSWORD",
        "SERPAPI_API_KEY", "AHREFS_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def mock_openai_key(monkeypatch) -> str:
    key = "sk-test-openai-key-1234567890"
    monkeypatch.setenv("OPENAI_API_KEY", key)
    return key


@pytest.fixture
def mock_anthropic_key(monkeypatch) -> str:
    key = "sk-ant-test-anthropic-key-0987654321"
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    return key


@pytest.fixture
def mock_dataforseo_creds(monkeypatch) -> dict:
    monkeypatch.setenv("DATAFORSEO_LOGIN",    "test@example.com")
    monkeypatch.setenv("DATAFORSEO_PASSWORD", "test-password")
    return {"login": "test@example.com", "password": "test-password"}


@pytest.fixture
def mock_serpapi_key(monkeypatch) -> str:
    key = "test-serpapi-key-abcdef"
    monkeypatch.setenv("SERPAPI_API_KEY", key)
    return key


# ── Sample data fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def sample_url() -> str:
    return "https://example.com"


@pytest.fixture
def sample_keywords() -> list[str]:
    return ["seo optimization", "keyword research", "content marketing", "backlink building"]


@pytest.fixture
def sample_site_context(sample_url):
    """Return a minimal SiteContext for agent tests."""
    try:
        import sys
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "apps" / "api"))
        from seo_ad_autopilot.agents.base import SiteContext
        return SiteContext(
            url=sample_url,
            raw_data={"title": "Example Domain", "meta_description": "Test site", "locale": "en"},
        )
    except Exception:
        return MagicMock(url=sample_url, raw_data={})


@pytest.fixture
def sample_skill_input(sample_url):
    """Return a minimal SkillInput for skill tests."""
    try:
        import sys
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "apps" / "api"))
        from seo_ad_autopilot.skills.base import SkillInput
        return SkillInput(url=sample_url, params={})
    except Exception:
        return MagicMock(url=sample_url, params={})


# ── Mock LLM response factory ─────────────────────────────────────────────────

def _make_llm_response(content: str = "Mock LLM response") -> MagicMock:
    mock = MagicMock()
    mock.choices = [MagicMock(message=MagicMock(content=content))]
    return mock


@pytest.fixture
def mock_llm(monkeypatch) -> AsyncMock:
    """Patch the async OpenAI client to return a fixed response."""
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _make_llm_response(
        "# Test Article\n\nThis is mock LLM content for testing purposes."
    )
    with patch("openai.AsyncOpenAI", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_httpx(monkeypatch) -> AsyncMock:
    """Patch httpx.AsyncClient to return controlled responses."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"tasks": [], "status_code": 20000}
    mock_resp.headers = {}

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.request.return_value = mock_resp

    with patch("httpx.AsyncClient", return_value=mock_client):
        yield mock_client


# ── FastAPI test client ───────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    """Return a FastAPI TestClient for smoke tests."""
    try:
        from fastapi.testclient import TestClient
        import sys
        sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent / "apps" / "api"))
        from seo_ad_autopilot.app import create_app
        app = create_app()
        return TestClient(app, raise_server_exceptions=False)
    except Exception:
        return None
