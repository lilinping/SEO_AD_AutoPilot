"""Regression tests for KeywordResearchSkill real-vs-synthetic source labeling.

These lock in the fix for a data-integrity bug: the skill used to label its
output `api_source = "google_custom_search"` whenever a Google API key was
present, even though GoogleSearchEngine only works when BOTH the key and the
CX (custom search engine id) are configured. A key-without-CX setup therefore
returned synthetic estimates mislabeled as real Google data.

The correct behavior is to derive the source from each engine's actual
`is_available()` readiness and to warn (not silently fake) when the Google
config is only partially set.
"""

from apps.api.seo_ad_autopilot.skills.keyword_research import KeywordResearchSkill
from apps.api.seo_ad_autopilot.skills.base import SkillInput


def _run(skill: KeywordResearchSkill) -> dict:
    out = skill.execute(SkillInput(params={"keyword": "seo tools"}))
    assert out.success is True
    return out.result


def test_no_credentials_is_synthetic_fallback(monkeypatch):
    for key in (
        "SEO_AD_BOT_GOOGLE_API_KEY", "GOOGLE_API_KEY",
        "SEO_AD_BOT_GOOGLE_CX", "GOOGLE_CX",
        "SEO_AD_BOT_BING_API_KEY", "BING_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    result = _run(KeywordResearchSkill())
    assert result["api_source"] == "synthetic_fallback"
    assert result["warnings"]


def test_google_key_without_cx_is_not_labeled_real(monkeypatch):
    """A Google API key with no CX must NOT be reported as real Google data."""
    monkeypatch.setenv("SEO_AD_BOT_GOOGLE_API_KEY", "test-google-key")
    for key in ("SEO_AD_BOT_GOOGLE_CX", "GOOGLE_CX", "SEO_AD_BOT_BING_API_KEY", "BING_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    result = _run(KeywordResearchSkill())
    assert result["api_source"] == "synthetic_fallback"
    # The user should be told the config is only partially set.
    assert any("CX" in w for w in result["warnings"])


def test_google_key_with_cx_is_labeled_real(monkeypatch):
    monkeypatch.setenv("SEO_AD_BOT_GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setenv("SEO_AD_BOT_GOOGLE_CX", "test-cx")
    for key in ("SEO_AD_BOT_BING_API_KEY", "BING_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    result = _run(KeywordResearchSkill())
    assert result["api_source"] == "google_custom_search"


def test_bing_key_only_is_labeled_bing(monkeypatch):
    for key in ("SEO_AD_BOT_GOOGLE_API_KEY", "GOOGLE_API_KEY", "SEO_AD_BOT_GOOGLE_CX", "GOOGLE_CX"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SEO_AD_BOT_BING_API_KEY", "test-bing-key")

    result = _run(KeywordResearchSkill())
    assert result["api_source"] == "bing_web_search"
