from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from sqlalchemy import Boolean, JSON, DateTime, Integer, String, Text, create_engine, inspect, select
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


def json_dump(payload: object) -> dict:
    if payload is None:
        return {}
    if hasattr(payload, "model_dump"):
        return payload.model_dump(mode="json", by_alias=True)  # type: ignore[no-any-return]
    if isinstance(payload, dict):
        return payload
    return json.loads(json.dumps(payload, default=str))
