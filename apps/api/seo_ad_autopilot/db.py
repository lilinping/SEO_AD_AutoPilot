from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from sqlalchemy import Boolean, Float, JSON, DateTime, Integer, String, Text, create_engine, inspect, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


from .config import Settings, get_settings
from .models import ApprovalStatus, SiteClass, WorkflowStage, utcnow


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    site_class: Mapped[str] = mapped_column(String(32), nullable=False)
    workspace: Mapped[str] = mapped_column(String(128), nullable=False)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    site_class: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    approval_status: Mapped[str] = mapped_column(String(32), default=ApprovalStatus.pending.value)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    analysis_json: Mapped[dict] = mapped_column(JSON, default=dict)
    preview_json: Mapped[dict] = mapped_column(JSON, default=dict)
    approval_json: Mapped[dict] = mapped_column(JSON, default=dict)
    deployment_json: Mapped[dict] = mapped_column(JSON, default=dict)
    metric_json: Mapped[dict] = mapped_column(JSON, default=dict)
    rollback_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditRow(Base):
    __tablename__ = "audits"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    task_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProjectStateRow(Base):
    __tablename__ = "project_states"

    project_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    connection_health: Mapped[str] = mapped_column(String(32), default="unknown")
    auto_cruise_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_run_status: Mapped[str] = mapped_column(String(32), default="idle")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProjectConnectionRow(Base):
    __tablename__ = "project_connections"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default="unavailable")
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    provenance_json: Mapped[list] = mapped_column(JSON, default=list)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProjectRunRow(Base):
    __tablename__ = "project_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    task_id: Mapped[Optional[str]] = mapped_column(String(32), index=True, nullable=True)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    connector_status_json: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_json: Mapped[list] = mapped_column(JSON, default=list)
    notes_json: Mapped[list] = mapped_column(JSON, default=list)
    auto_deploy: Mapped[bool] = mapped_column(Boolean, default=False)
    rollback_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    runtime_route_request_path: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    runtime_route_request_method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    runtime_route_execution_mode: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    runtime_route_execution_action: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    runtime_route_execution_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    runtime_route_execution_entrypoint: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    gateway_route_provider_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    gateway_route_fallback_provider_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    gateway_route_priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AlertSnapshotRow(Base):
    __tablename__ = "alert_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    blocking_count: Mapped[int] = mapped_column(Integer, default=0)
    recoverable_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AcceptanceSnapshotRow(Base):
    __tablename__ = "acceptance_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_gate_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MetricSnapshotRow(Base):
    __tablename__ = "metric_snapshots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    task_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    source_status_json: Mapped[dict] = mapped_column(JSON, default=dict)
    external_metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class JobQueueRow(Base):
    __tablename__ = "job_queue"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    task_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    ready_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ContentVersionRow(Base):
    """DB-004 — persisted content version snapshots.

    Mirrors migration 0001_initial `content_versions` table so the ORM layer
    and Alembic schema stay in sync.
    """

    __tablename__ = "content_versions"

    version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    content_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    author: Mapped[str] = mapped_column(String(100), nullable=False, default="agent")
    change_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False, default=time.time)


class AdRecommendationRow(Base):
    """DB-006 — persisted ad platform recommendation history.

    Mirrors migration 0001_initial `ad_recommendations` table.
    """

    __tablename__ = "ad_recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    platforms: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    site_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False, default=time.time)


class RankingSnapshotRow(Base):
    """DB-003 — persisted daily keyword rank snapshots.

    Mirrors migration 0001_initial `ranking_snapshots` table.
    """

    __tablename__ = "ranking_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    keyword: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    search_engine: Mapped[str] = mapped_column(String(20), nullable=False, default="google")
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    device: Mapped[str] = mapped_column(String(10), nullable=False, default="desktop")
    serp_features: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    snapshot_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    created_at: Mapped[float] = mapped_column(Float, nullable=False, default=time.time)


class AnalysisTaskRow(Base):
    """DB-005 — persisted analysis task queue state.

    Mirrors migration 0001_initial `analysis_tasks` table.
    """

    __tablename__ = "analysis_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    agent_filter: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False, default=time.time)
    updated_at: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class DebateLogRow(Base):
    """DB-007 — persisted multi-agent debate logs for audit.

    Mirrors migration 0001_initial `debate_logs` table.
    """

    __tablename__ = "debate_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    proposer_role: Mapped[str] = mapped_column(String(50), nullable=False)
    participants: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    rounds: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    consensus_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, nullable=False, default=time.time)



class Database:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._engine = self._create_engine()
        self.session_factory = sessionmaker(bind=self._engine, expire_on_commit=False, future=True)


    def _create_engine(self):
        url = self.settings.database_url
        require_postgres = bool(self.settings.require_postgres)
        disable_sqlite_fallback = bool(self.settings.disable_sqlite_fallback)
        if require_postgres and not url.startswith("postgresql"):
            raise RuntimeError("SEO_AD_BOT_REQUIRE_POSTGRES=true requires DATABASE_URL to use a postgresql scheme")
        
        # If URL is PostgreSQL but psycopg not installed, fallback to SQLite
        if url.startswith("postgresql") and not require_postgres:
            try:
                import psycopg
            except ImportError:
                print("[DB] psycopg not installed, falling back to SQLite")
                url = "sqlite:///./var/seo-ad-autopilot.db"
        
        connect_args = {}
        if url.startswith("sqlite"):
            Path("var").mkdir(parents=True, exist_ok=True)
            connect_args = {"check_same_thread": False}
        try:
            engine = create_engine(url, future=True, connect_args=connect_args)
            with engine.connect() as connection:
                connection.execute(select(1))
            return engine
        except (OperationalError, ImportError):
            if require_postgres or disable_sqlite_fallback:
                raise
            fallback = "sqlite:///./var/seo-ad-autopilot.db"
            Path("var").mkdir(parents=True, exist_ok=True)
            return create_engine(fallback, future=True, connect_args={"check_same_thread": False})

    def create_all(self) -> None:
        Base.metadata.create_all(self._engine)
        self._ensure_project_runs_runtime_route_columns()

    def _ensure_project_runs_runtime_route_columns(self) -> None:
        inspector = inspect(self._engine)
        if "project_runs" not in inspector.get_table_names():
            return
        existing_columns = {column["name"] for column in inspector.get_columns("project_runs")}
        statements: list[str] = []
        if "runtime_route_request_path" not in existing_columns:
            statements.append("ALTER TABLE project_runs ADD COLUMN runtime_route_request_path VARCHAR(256)")
        if "runtime_route_request_method" not in existing_columns:
            statements.append("ALTER TABLE project_runs ADD COLUMN runtime_route_request_method VARCHAR(16)")
        if "runtime_route_execution_mode" not in existing_columns:
            statements.append("ALTER TABLE project_runs ADD COLUMN runtime_route_execution_mode VARCHAR(16)")
        if "runtime_route_execution_action" not in existing_columns:
            statements.append("ALTER TABLE project_runs ADD COLUMN runtime_route_execution_action VARCHAR(32)")
        if "runtime_route_execution_reason" not in existing_columns:
            statements.append("ALTER TABLE project_runs ADD COLUMN runtime_route_execution_reason VARCHAR(256)")
        if "runtime_route_execution_entrypoint" not in existing_columns:
            statements.append("ALTER TABLE project_runs ADD COLUMN runtime_route_execution_entrypoint VARCHAR(256)")
        if "gateway_route_provider_name" not in existing_columns:
            statements.append("ALTER TABLE project_runs ADD COLUMN gateway_route_provider_name VARCHAR(64)")
        if "gateway_route_fallback_provider_name" not in existing_columns:
            statements.append("ALTER TABLE project_runs ADD COLUMN gateway_route_fallback_provider_name VARCHAR(64)")
        if "gateway_route_priority" not in existing_columns:
            statements.append("ALTER TABLE project_runs ADD COLUMN gateway_route_priority INTEGER")
        if not statements:
            return
        with self._engine.begin() as connection:
            for statement in statements:
                connection.exec_driver_sql(statement)

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def count_projects(self) -> int:
        with self.session() as session:
            return session.query(ProjectRow).count()

    def count_runs(self) -> int:
        with self.session() as session:
            return session.query(ProjectRunRow).count()

    # ── DB-006: ad recommendation persistence ────────────────────────────────

    def save_ad_recommendation(
        self,
        url: str,
        platforms: list,
        site_data: Optional[dict] = None,
        tenant_id: Optional[str] = None,
    ) -> str:
        """Persist an ad platform recommendation result. Returns the row id."""
        row_id = uuid.uuid4().hex
        with self.session() as session:
            session.add(AdRecommendationRow(
                id=row_id,
                url=url,
                platforms=platforms or [],
                site_data=site_data or {},
                tenant_id=tenant_id,
                created_at=time.time(),
            ))
        return row_id

    def list_ad_recommendations(
        self,
        url: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Return recommendation history (newest first)."""
        with self.session() as session:
            query = session.query(AdRecommendationRow)
            if url:
                query = query.filter(AdRecommendationRow.url == url)
            if tenant_id:
                query = query.filter(AdRecommendationRow.tenant_id == tenant_id)
            rows = query.order_by(AdRecommendationRow.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": r.id,
                    "url": r.url,
                    "platforms": r.platforms,
                    "site_data": r.site_data,
                    "tenant_id": r.tenant_id,
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    # ── DB-003: ranking snapshot persistence ─────────────────────────────────

    def save_ranking_snapshots(
        self,
        url: str,
        keyword_rows: list[dict],
        search_engine: str = "google",
        locale: str = "en",
        device: str = "desktop",
        snapshot_date: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> list[str]:
        """Persist a batch of per-keyword rank snapshots. Returns the row ids."""
        date_str = snapshot_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        ids: list[str] = []
        with self.session() as session:
            for row in keyword_rows:
                keyword = row.get("keyword")
                if not keyword:
                    continue
                row_id = uuid.uuid4().hex
                position = row.get("position")
                # RankSnapshotSkill uses 999 as the "unranked" sentinel.
                if isinstance(position, (int, float)) and position >= 999:
                    position = None
                session.add(RankingSnapshotRow(
                    id=row_id,
                    url=url,
                    keyword=keyword,
                    position=int(position) if position is not None else None,
                    search_engine=search_engine,
                    locale=locale,
                    device=device,
                    serp_features=row.get("serp_features") or [],
                    tenant_id=tenant_id,
                    snapshot_date=row.get("date") or date_str,
                    created_at=time.time(),
                ))
                ids.append(row_id)
        return ids

    def list_ranking_snapshots(
        self,
        url: Optional[str] = None,
        keyword: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Return rank snapshot history (newest first)."""
        with self.session() as session:
            query = session.query(RankingSnapshotRow)
            if url:
                query = query.filter(RankingSnapshotRow.url == url)
            if keyword:
                query = query.filter(RankingSnapshotRow.keyword == keyword)
            if tenant_id:
                query = query.filter(RankingSnapshotRow.tenant_id == tenant_id)
            rows = query.order_by(RankingSnapshotRow.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": r.id,
                    "url": r.url,
                    "keyword": r.keyword,
                    "position": r.position,
                    "search_engine": r.search_engine,
                    "locale": r.locale,
                    "device": r.device,
                    "serp_features": r.serp_features,
                    "snapshot_date": r.snapshot_date,
                    "tenant_id": r.tenant_id,
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    # ── DB-007: debate log persistence ───────────────────────────────────────

    def save_debate_log(
        self,
        topic: str,
        proposer_role: str,
        task_id: Optional[str] = None,
        participants: Optional[list] = None,
        rounds: Optional[list] = None,
        consensus_score: Optional[float] = None,
        resolution: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> str:
        """Persist a debate log for audit. Returns the row id."""
        row_id = uuid.uuid4().hex
        with self.session() as session:
            session.add(DebateLogRow(
                id=row_id,
                task_id=task_id,
                topic=topic,
                proposer_role=proposer_role,
                participants=participants or [],
                rounds=rounds or [],
                consensus_score=consensus_score,
                resolution=resolution,
                tenant_id=tenant_id,
                created_at=time.time(),
            ))
        return row_id

    def list_debate_logs(
        self,
        task_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Return debate log history (newest first)."""
        with self.session() as session:
            query = session.query(DebateLogRow)
            if task_id:
                query = query.filter(DebateLogRow.task_id == task_id)
            if tenant_id:
                query = query.filter(DebateLogRow.tenant_id == tenant_id)
            rows = query.order_by(DebateLogRow.created_at.desc()).limit(limit).all()
            return [
                {
                    "id": r.id,
                    "task_id": r.task_id,
                    "topic": r.topic,
                    "proposer_role": r.proposer_role,
                    "participants": r.participants,
                    "rounds": r.rounds,
                    "consensus_score": r.consensus_score,
                    "resolution": r.resolution,
                    "tenant_id": r.tenant_id,
                    "created_at": r.created_at,
                }
                for r in rows
            ]

    # ── DB-005: analysis task persistence ────────────────────────────────────

    def save_analysis_task(
        self,
        task_id: str,
        url: str,
        status: str = "queued",
        percent: int = 0,
        agent_filter: Optional[list] = None,
        dry_run: bool = False,
        locale: str = "en",
        result: Optional[dict] = None,
        error: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> str:
        """Upsert an analysis task's queue state. Returns the task id."""
        with self.session() as session:
            existing = session.get(AnalysisTaskRow, task_id)
            if existing is None:
                session.add(AnalysisTaskRow(
                    id=task_id,
                    url=url,
                    status=status,
                    percent=percent,
                    agent_filter=agent_filter,
                    dry_run=dry_run,
                    locale=locale,
                    result=result,
                    error=error,
                    tenant_id=tenant_id,
                    created_at=time.time(),
                    updated_at=time.time(),
                ))
            else:
                existing.url = url
                existing.status = status
                existing.percent = percent
                if agent_filter is not None:
                    existing.agent_filter = agent_filter
                existing.dry_run = dry_run
                existing.locale = locale
                if result is not None:
                    existing.result = result
                if error is not None:
                    existing.error = error
                if tenant_id is not None:
                    existing.tenant_id = tenant_id
                existing.updated_at = time.time()
        return task_id

    def get_analysis_task(self, task_id: str) -> Optional[dict]:
        """Return a persisted analysis task by id, or None."""
        with self.session() as session:
            r = session.get(AnalysisTaskRow, task_id)
            if r is None:
                return None
            return {
                "id": r.id,
                "url": r.url,
                "status": r.status,
                "percent": r.percent,
                "agent_filter": r.agent_filter,
                "dry_run": r.dry_run,
                "locale": r.locale,
                "result": r.result,
                "error": r.error,
                "tenant_id": r.tenant_id,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }



def json_dump(payload: object) -> dict:
    if payload is None:
        return {}

    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json", by_alias=True)  # type: ignore[no-any-return]
    if isinstance(payload, dict):
        return payload
    return json.loads(json.dumps(payload, default=str))
