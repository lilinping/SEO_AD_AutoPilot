"""Regression tests for DB-003 / DB-005 / DB-007 persistence.

These three requirements had Alembic migration tables (ranking_snapshots,
analysis_tasks, debate_logs) but no ORM models or write paths — i.e. they were
marked "done" while nothing actually persisted. These tests lock in that the
ORM models exist and the service/router write paths work end-to-end.
"""
import asyncio

from apps.api.seo_ad_autopilot.db import Database
from apps.api.seo_ad_autopilot.services import RankingService, AnalysisService


def _fresh_db() -> Database:
    # Uses the configured DB (SQLite fallback under ./var by default).
    db = Database()
    db.create_all()
    return db


# ── DB-003: ranking snapshots ────────────────────────────────────────────────

def test_db003_ranking_snapshots_persisted():
    db = _fresh_db()
    svc = RankingService(db=db)
    out = asyncio.run(svc.run(
        url="https://db003.example.com",
        keywords=["alpha kw", "beta kw"],
        context={"serp_data": {
            "alpha kw": {"position": 3, "url": "https://db003.example.com/a"},
            "beta kw": {"position": 15},
        }},
    ))
    assert out["success"] is True
    hist = svc.history(url="https://db003.example.com")
    keywords = {h["keyword"] for h in hist}
    assert {"alpha kw", "beta kw"}.issubset(keywords)


def test_db003_unranked_sentinel_stored_as_null():
    db = _fresh_db()
    svc = RankingService(db=db)
    asyncio.run(svc.run(
        url="https://db003b.example.com",
        keywords=["missing kw"],
        context={"serp_data": {}},  # no position -> 999 sentinel
    ))
    hist = svc.history(url="https://db003b.example.com", keyword="missing kw")
    assert hist and hist[0]["position"] is None


# ── DB-005: analysis task persistence + fallback ─────────────────────────────

def test_db005_task_survives_outside_memory():
    db = _fresh_db()
    svc = AnalysisService(db=db)  # empty in-memory dict
    db.save_analysis_task(task_id="db005-task", url="https://db005.example.com",
                          status="complete", percent=100, result={"ok": True})
    got = svc.get_task("db005-task")  # must fall back to DB
    assert got is not None
    assert got["status"] == "complete"
    assert got["percent"] == 100


def test_db005_upsert_updates_status():
    db = _fresh_db()
    db.save_analysis_task(task_id="db005-upsert", url="https://u.example.com", status="running", percent=10)
    db.save_analysis_task(task_id="db005-upsert", url="https://u.example.com", status="complete", percent=100)
    got = db.get_analysis_task("db005-upsert")
    assert got["status"] == "complete"
    assert got["percent"] == 100


# ── DB-007: debate log persistence ───────────────────────────────────────────

def test_db007_debate_log_persisted():
    db = _fresh_db()
    db.save_debate_log(
        topic="Should we add FAQ schema?",
        proposer_role="strategist",
        task_id="db007-task",
        participants=["strategist", "policy_guard"],
        rounds=[{"agent_role": "policy_guard", "stance": "agree", "confidence": 0.9}],
        consensus_score=0.75,
        resolution="approved",
    )
    logs = db.list_debate_logs(task_id="db007-task")
    assert logs and logs[0]["topic"] == "Should we add FAQ schema?"
    assert logs[0]["consensus_score"] == 0.75
