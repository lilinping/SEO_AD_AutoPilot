from pathlib import Path

import pytest

from apps.api.seo_ad_autopilot.config import Settings
from apps.api.seo_ad_autopilot.skill_registry import SkillRegistry
from apps.api.seo_ad_autopilot.service import WorkflowService


@pytest.fixture()
def isolated_service(tmp_path, monkeypatch) -> WorkflowService:
    db_path = tmp_path / "seo-ad-autopilot.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv(
        "SEO_AD_BOT_SKILL_REGISTRY_PATH",
        str(Path("packages/skill-registry/registry.json").resolve()),
    )
    monkeypatch.setenv("SEO_AD_BOT_WEB_ORIGIN", "http://testserver")
    settings = Settings()
    registry = SkillRegistry.load(settings.skill_registry_path)
    service = WorkflowService(settings=settings, registry=registry)
    service.database.create_all()
    return service
