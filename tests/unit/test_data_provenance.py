"""Tests for the unified DataProvenance model and search-source evaluator.

Locks in the P0 backend slice of the data-trust product design: a partial
credential set (Google API key without CX) must be reported as ``partial``,
never as ``real``, and every non-real tier must carry an actionable
remediation.
"""

from apps.api.seo_ad_autopilot.data_provenance import (
    DataProvenance,
    build_data_trust_report,
    evaluate_ecommerce_source_provenance,
    evaluate_search_source_provenance,
)
from apps.api.seo_ad_autopilot.skills.keyword_research import KeywordResearchSkill
from apps.api.seo_ad_autopilot.skills.base import SkillInput



def _clear_search_env(monkeypatch):
    for key in (
        "SEO_AD_BOT_GOOGLE_API_KEY", "GOOGLE_API_KEY",
        "SEO_AD_BOT_GOOGLE_CX", "GOOGLE_CX",
        "SEO_AD_BOT_BING_API_KEY", "BING_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


def test_provenance_defaults_are_unknown():
    p = DataProvenance()
    assert p.source_tier == "unknown"
    assert p.is_real is False


def test_no_credentials_is_synthetic(monkeypatch):
    _clear_search_env(monkeypatch)
    p = evaluate_search_source_provenance()
    assert p.source_tier == "synthetic"
    assert p.gap_type == "missing_credential"
    assert p.remediation


def test_google_key_without_cx_is_partial(monkeypatch):
    _clear_search_env(monkeypatch)
    monkeypatch.setenv("SEO_AD_BOT_GOOGLE_API_KEY", "test-key")
    p = evaluate_search_source_provenance()
    assert p.source_tier == "partial"
    assert p.gap_type == "partial_credential"
    assert "CX" in p.remediation or "CX" in p.gap_summary
    assert p.is_real is False


def test_google_key_with_cx_is_real(monkeypatch):
    _clear_search_env(monkeypatch)
    monkeypatch.setenv("SEO_AD_BOT_GOOGLE_API_KEY", "test-key")
    monkeypatch.setenv("SEO_AD_BOT_GOOGLE_CX", "test-cx")
    p = evaluate_search_source_provenance()
    assert p.source_tier == "real"
    assert p.provider == "google_custom_search"
    assert p.is_real is True


def test_bing_only_is_real(monkeypatch):
    _clear_search_env(monkeypatch)
    monkeypatch.setenv("SEO_AD_BOT_BING_API_KEY", "test-key")
    p = evaluate_search_source_provenance()
    assert p.source_tier == "real"
    assert p.provider == "bing_web_search"


def test_provenance_alias_serialization():
    p = DataProvenance(source_tier="partial", gap_type="partial_credential")
    dumped = p.model_dump(by_alias=True)
    assert dumped["sourceTier"] == "partial"
    assert dumped["gapType"] == "partial_credential"


def test_keyword_skill_attaches_provenance(monkeypatch):
    _clear_search_env(monkeypatch)
    monkeypatch.setenv("SEO_AD_BOT_GOOGLE_API_KEY", "test-key")  # key, no CX

    skill = KeywordResearchSkill()
    out = skill.execute(SkillInput(params={"keyword": "seo tools"}))
    assert out.success is True

    provenance = out.result["provenance"]
    # Real source not truly available -> must not be labeled real.
    assert provenance["sourceTier"] == "partial"
    assert provenance["gapType"] == "partial_credential"


def test_ecommerce_without_jina_is_not_real(monkeypatch):
    for key in ("SEO_AD_BOT_JINA_KEY", "JINA_KEY"):
        monkeypatch.delenv(key, raising=False)
    p = evaluate_ecommerce_source_provenance()
    assert p.is_real is False
    assert p.remediation


def test_ecommerce_with_jina_is_real(monkeypatch):
    monkeypatch.setenv("SEO_AD_BOT_JINA_KEY", "test-jina")
    p = evaluate_ecommerce_source_provenance()
    assert p.source_tier == "real"
    assert p.provider == "jina_reader_api"


def test_data_trust_report_shape_no_credentials(monkeypatch):
    _clear_search_env(monkeypatch)
    for key in ("SEO_AD_BOT_JINA_KEY", "JINA_KEY"):
        monkeypatch.delenv(key, raising=False)

    report = build_data_trust_report()
    assert 0 <= report["dataTrustScore"] <= 100
    assert report["totalSourceCount"] == len(report["sources"])
    # With no real sources configured, every source is a gap.
    assert report["realSourceCount"] == 0
    assert len(report["gaps"]) == report["totalSourceCount"]
    # Every gap must carry an actionable remediation.
    assert all(gap["remediation"] for gap in report["gaps"])


def test_data_trust_score_rises_with_real_source(monkeypatch):
    _clear_search_env(monkeypatch)
    for key in ("SEO_AD_BOT_JINA_KEY", "JINA_KEY"):
        monkeypatch.delenv(key, raising=False)
    baseline = build_data_trust_report()["dataTrustScore"]

    monkeypatch.setenv("SEO_AD_BOT_BING_API_KEY", "test-key")
    improved = build_data_trust_report()["dataTrustScore"]
    assert improved > baseline

