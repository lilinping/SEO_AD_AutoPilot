"""Regression tests for the ported legacy skills (ecommerce_analysis / keyword_research).

These two skills previously targeted a non-existent BaseSkill/SkillResult API,
which broke the entire `skills` package import (and the services + API layers
downstream). These tests lock in that they now conform to the current
Skill/SkillInput/SkillOutput contract.
"""
from apps.api.seo_ad_autopilot.skills import (
    EcommerceAnalysisSkill,
    KeywordResearchSkill,
)
from apps.api.seo_ad_autopilot.skills.base import Skill, SkillInput, SkillOutput


def test_skills_are_exported_and_not_none():
    assert EcommerceAnalysisSkill is not None
    assert KeywordResearchSkill is not None
    assert issubclass(EcommerceAnalysisSkill, Skill)
    assert issubclass(KeywordResearchSkill, Skill)


def test_ecommerce_skill_conforms_to_contract():
    skill = EcommerceAnalysisSkill()
    # Required abstract properties are implemented.
    assert skill.name == "EcommerceAnalysis"
    assert skill.category is not None
    assert skill.risk_level is not None

    out = skill.execute(SkillInput(params={"url": "https://example.com/products/cool-widget"}))
    assert isinstance(out, SkillOutput)
    assert out.success is True
    assert "seo_score" in out.result
    assert out.result["url"] == "https://example.com/products/cool-widget"


def test_ecommerce_skill_missing_url_fails_gracefully():
    skill = EcommerceAnalysisSkill()
    out = skill.execute(SkillInput(params={}))
    assert isinstance(out, SkillOutput)
    assert out.success is False
    assert out.error


def test_keyword_skill_conforms_to_contract():
    skill = KeywordResearchSkill()
    assert skill.name == "KeywordResearch"

    out = skill.execute(SkillInput(params={"keyword": "seo tools"}))
    assert isinstance(out, SkillOutput)
    assert out.success is True
    assert out.result["query"] == "seo tools"
    assert len(out.result["keywords"]) > 0


def test_keyword_skill_missing_keyword_fails_gracefully():
    skill = KeywordResearchSkill()
    out = skill.execute(SkillInput(params={}))
    assert isinstance(out, SkillOutput)
    assert out.success is False
    assert out.error


def test_default_registry_builds_with_ported_skills():
    """create_default_registry() previously crashed instantiating the two
    legacy skills. Ensure it now builds fully and both are discoverable."""
    from apps.api.seo_ad_autopilot.skills.registry import create_default_registry

    registry = create_default_registry()
    assert registry.get_by_name("EcommerceAnalysis") is not None
    assert registry.get_by_name("KeywordResearch") is not None

