from unittest.mock import patch

from apps.api.seo_ad_autopilot.search_engines.base import SearchEngineCategory, SearchQuery
from apps.api.seo_ad_autopilot.search_engines import yandex as yandex_module

YandexSearchEngine = yandex_module.YandexSearchEngine


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b"""
        <yandexsearch version="1.0">
          <response>
            <results>
              <grouping>
                <group>
                  <doc>
                    <url>https://example.com/a</url>
                    <title>First &amp; Result</title>
                    <headline>Snippet <hlword>match</hlword> text</headline>
                    <passages>
                      <passage>Passage fallback</passage>
                    </passages>
                    <domain>example.com</domain>
                  </doc>
                </group>
                <group>
                  <doc>
                    <url>https://example.com/b</url>
                    <title>Second Result</title>
                    <passages>
                      <passage>Second snippet</passage>
                    </passages>
                  </doc>
                </group>
              </grouping>
            </results>
          </response>
        </yandexsearch>
        """


def test_yandex_search_parses_xml_results_and_metadata():
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse()

    engine = YandexSearchEngine(api_key="key", user="user")

    with patch.object(yandex_module, "urlopen", fake_urlopen):
        results = engine.search(SearchQuery(query="seo audit", language="ru", country="ru"))

    assert len(results) == 2
    assert results[0].title == "First & Result"
    assert results[0].url == "https://example.com/a"
    assert results[0].snippet == "Snippet match text"
    assert results[0].position == 1
    assert results[0].engine == SearchEngineCategory.YANDEX
    assert results[0].metadata["domain"] == "example.com"
    assert "user=user" in captured["url"]
    assert "key=key" in captured["url"]
    assert "query=seo+audit" in captured["url"]
    assert captured["timeout"] == 10


def test_yandex_search_uses_env_credentials(monkeypatch):
    monkeypatch.setenv("SEO_AD_BOT_YANDEX_USER", "env-user")
    monkeypatch.setenv("SEO_AD_BOT_YANDEX_API_KEY", "env-key")

    engine = YandexSearchEngine()

    assert engine.is_available() is True
