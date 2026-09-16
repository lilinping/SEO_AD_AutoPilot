"""Unit tests for DB-004 (content_versions) and DB-006 (ad_recommendations)."""
import os

import pytest

from apps.api.seo_ad_autopilot.config import Settings
from apps.api.seo_ad_autopilot.db import Database
from apps.api.seo_ad_autopilot.content_versions import ContentVersionStore
from apps.api.seo_ad_autopilot.services import AdService


@pytest.fixture
def db(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path/'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    database = Database(Settings())
    database.create_all()
    return database



# ── DB-006 ─────────────────────────────────────────────────────────────────

def test_save_and_list_ad_recommendation(db):
    row_id = db.save_ad_recommendation(
        url="https://example.com",
        platforms=[{"platform": "AdSense", "confidence": 0.9}],
        site_data={"monthly_visits": 25000},
    )
    assert row_id

    history = db.list_ad_recommendations(url="https://example.com")
    assert len(history) == 1
    assert history[0]["url"] == "https://example.com"
    assert history[0]["platforms"][0]["platform"] == "AdSense"


@pytest.mark.asyncio
async def test_ad_service_persists_when_db_provided(db):
    service = AdService(db=db)
    result = await service.run(url="https://shop.example", site_data={"monthly_visits": 12000})
    assert result["success"] is True

    history = service.history(url="https://shop.example")
    assert len(history) == 1


@pytest.mark.asyncio
async def test_ad_service_no_db_is_noop():
    service = AdService()
    result = await service.run(url="https://nodb.example", site_data={"monthly_visits": 5000})
    assert result["success"] is True
    assert service.history(url="https://nodb.example") == []


# ── DB-004 ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_content_version_store_mirrors_to_db(db, tmp_path):
    from apps.api.seo_ad_autopilot.db import ContentVersionRow

    store = ContentVersionStore(storage_path=str(tmp_path / "cv"), db=db)
    v1 = await store.save(content_id="post-1", content={"markdown": "v1"}, author="agent")
    v2 = await store.save(content_id="post-1", content={"markdown": "v2"}, author="agent")

    assert v1.version == "1.0.0"
    assert v2.version == "1.0.1"

    with db.session() as session:
        rows = session.query(ContentVersionRow).filter(
            ContentVersionRow.content_id == "post-1"
        ).all()
        assert len(rows) == 2
        active = [r for r in rows if r.is_active]
        assert len(active) == 1
        assert active[0].version == "1.0.1"


@pytest.mark.asyncio
async def test_content_version_store_file_only_without_db(tmp_path):
    store = ContentVersionStore(storage_path=str(tmp_path / "cv2"))
    v1 = await store.save(content_id="post-2", content={"markdown": "x"})
    assert v1.version == "1.0.0"
    history = await store.history("post-2")
    assert len(history) == 1
