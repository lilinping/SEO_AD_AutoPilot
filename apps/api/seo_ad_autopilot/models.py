from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class APIModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, protected_namespaces=())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class SiteClass(str, Enum):
    ecommerce = "ecommerce"
    content = "content"
    saas = "saas"
    tool = "tool"
    local = "local"
    brand = "brand"
    ymyl = "ymyl"


class DeploymentMode(str, Enum):
    github_pr = "github_pr"
    cms_draft = "cms_draft"
    universal_script = "universal_script"
    static_export = "static_export"


class WorkflowStage(str, Enum):
    queued = "queued"
    sensing = "sensing"
    profiled = "profiled"
    planned = "planned"
    previewed = "previewed"
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    deployed = "deployed"
    monitoring = "monitoring"
    rolled_back = "rolled_back"
    closed = "closed"
    rejected = "rejected"


class ApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ConnectorKind(str, Enum):
    search_console = "search_console"
    ga4 = "ga4"
    github = "github"
    cms = "cms"
    script_api = "script_api"
    ad_network = "ad_network"
    sitemap = "sitemap"
    playwright = "playwright"
    trend = "trend"
    news = "news"
    qa = "qa"


class ConnectorStatus(str, Enum):
    connected = "connected"
    missing_credentials = "missing_credentials"
    unavailable = "unavailable"
    synthetic = "synthetic"
    error = "error"


class ConnectionHealth(str, Enum):
    healthy = "healthy"
    degraded = "degraded"
    unavailable = "unavailable"
    unknown = "unknown"


class RunTrigger(str, Enum):
    manual = "manual"
    schedule = "schedule"
    approval = "approval"
    deploy = "deploy"
    monitor = "monitor"
    rollback = "rollback"


class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    rolled_back = "rolled_back"


class WorkerJobStatus(str, Enum):
    queued = "queued"
    claimed = "claimed"
    completed = "completed"
    failed = "failed"


class WorkerRunOnceRequest(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    include_approved_tasks: bool = True
    claim_limit: int = 200


class WorkerRunOnceResult(APIModel):
    processed: int
    enqueued: int
    skipped_duplicates: int
    claimed: int
    due_projects: int
    target_project_ids: list[str] = Field(default_factory=list)


class WorkerQueueStageStats(APIModel):
    stage: str
    total: int = 0
    queued: int = 0
    claimed: int = 0
    completed: int = 0
    failed: int = 0


class WorkerQueueHealthReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    backend: str
    backend_connected: bool = True
    backend_probe_latency_ms: Optional[int] = None
    backend_probe_failure_code: Optional[str] = None
    backend_probe_error: Optional[str] = None
    queue_depth: Optional[int] = None
    total: int = 0
    queued: int = 0
    claimed: int = 0
    completed: int = 0
    failed: int = 0
    oldest_ready_at: Optional[datetime] = None
    stage_stats: list[WorkerQueueStageStats] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkerExecutionHistoryEntry(APIModel):
    audit_id: str
    project_id: str
    task_id: Optional[str] = None
    action: str
    status: str
    stage: str
    job_id: Optional[str] = None
    attempt: int = 0
    retry_delay_seconds: Optional[int] = None
    failure_code: Optional[str] = None
    error: Optional[str] = None
    actor: str
    created_at: datetime
    span_id: Optional[str] = None
    trace_id: Optional[str] = None


class WorkerExecutionHistoryReport(APIModel):
    project_id: Optional[str] = None
    total: int = 0
    entries: list[WorkerExecutionHistoryEntry] = Field(default_factory=list)


class WorkerServiceHealthReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    state_file_configured: bool = False
    state_file_path: Optional[str] = None
    state_file_found: bool = False
    status: Literal["running", "starting", "degraded", "stopped", "unknown"] = "unknown"
    started_at: Optional[datetime] = None
    last_tick_at: Optional[datetime] = None
    failures: int = 0
    processed: int = 0
    enqueued: int = 0
    claimed: int = 0
    skipped_duplicates: int = 0
    due_projects: int = 0
    targets: list[str] = Field(default_factory=list)
    last_error: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class ObservabilityStatusReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    enable_otlp: bool = False
    otlp_endpoint_configured: bool = False
    sentry_dsn_configured: bool = False
    observability_strict: bool = False
    tracing_backend: str = "disabled"
    otlp_exporter_available: bool = False
    notes: list[str] = Field(default_factory=list)


class SiteIntake(APIModel):
    url: str
    site_name: Optional[str] = None
    repo_url: Optional[str] = None
    cms_name: Optional[str] = None
    sitemap_urls: list[str] = Field(default_factory=list)
    search_console: dict[str, Any] = Field(default_factory=dict)
    ga4: dict[str, Any] = Field(default_factory=dict)
    keywords: list[str] = Field(default_factory=list)
    brand_whitelist: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    approval_rules: dict[str, Any] = Field(default_factory=dict)
    locale: str = "en-US"
    language: str = "en"
    notes: str = ""


class PagePerformanceBudget(APIModel):
    lcp_ms: int
    cls: float
    inp_ms: int


class PageSnapshot(APIModel):
    url: str
    title: str
    description: str
    headings: list[str] = Field(default_factory=list)
    word_count: int
    internal_links: int
    external_links: int
    images: int
    missing_alt_count: int
    structured_data: list[str] = Field(default_factory=list)
    cta_count: int
    performance_budget: PagePerformanceBudget


class CrawlDiagnosticsReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    url: str
    fallback_title: str
    fallback_description: str
    snapshot: Optional[PageSnapshot] = None
    html_artifact_ref: Optional[str] = None
    html_artifact_path: Optional[str] = None
    screenshot_artifact_ref: Optional[str] = None
    screenshot_artifact_path: Optional[str] = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class SiteProfile(APIModel):
    site_id: str
    name: str
    url: str
    vertical: SiteClass
    language: str
    locale: str
    brand_voice: str
    page_count_estimate: int
    trust_signals: list[str] = Field(default_factory=list)
    pages: list[PageSnapshot] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    risk_score: int


class BusinessClassifierRule(APIModel):
    rule_id: str
    name: str
    description: str
    vertical: SiteClass
    triggers: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    enabled: bool = True


class BusinessClassifierReport(APIModel):
    report_id: str
    site_id: str
    inferred_vertical: SiteClass
    brand_voice: str
    matched_rules: list[BusinessClassifierRule] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class StyleToken(APIModel):
    token: str
    value: str
    source: str
    confidence: float = 0.0


class StyleExtractionReport(APIModel):
    report_id: str
    project_id: str
    site_id: str
    brand_voice: str
    tone: str
    density: Literal["compact", "balanced", "expansive"]
    trust_level: Literal["low", "medium", "high"]
    tokens: list[StyleToken] = Field(default_factory=list)
    module_guidance: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SourceEvidence(APIModel):
    provider: ConnectorKind
    status: ConnectorStatus
    summary: str
    provenance: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    source_type: Literal["connector", "trend", "news", "qa"] = "connector"
    source_ref: Optional[str] = None
    fetched_at: datetime = Field(default_factory=utcnow)
    fallback_reason: Optional[str] = None
    failure_code: Optional[str] = None
    retryable: bool = False
    latency_ms: Optional[int] = None
    auth_source: Optional[str] = None
    checked_at: datetime = Field(default_factory=utcnow)


class IngestionReport(APIModel):
    report_id: str
    project_id: str
    task_id: Optional[str] = None
    status: ConnectorStatus
    generated_at: datetime = Field(default_factory=utcnow)
    evidence: list[SourceEvidence] = Field(default_factory=list)
    connector_status: dict[str, ConnectorStatus] = Field(default_factory=dict)
    provenance: dict[str, list[str]] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class MarketEvidenceReport(APIModel):
    report_id: str
    project_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    trend: list[SourceEvidence] = Field(default_factory=list)
    news: list[SourceEvidence] = Field(default_factory=list)
    qa: list[SourceEvidence] = Field(default_factory=list)
    summaries: list["MarketEvidenceSummary"] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MarketEvidenceHealthReport(APIModel):
    report_id: str
    project_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    strict_providers_enabled: bool = False
    connected_count: int = 0
    synthetic_count: int = 0
    failed_count: int = 0
    fresh_count: int = 0
    stale_count: int = 0
    latest_fetched_at: Optional[datetime] = None
    strict_ready: bool = False
    notes: list[str] = Field(default_factory=list)


class WorkspaceMarketEvidenceHealthReport(APIModel):
    report_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    strict_providers_enabled: bool = False
    project_count: int = 0
    connected_count: int = 0
    synthetic_count: int = 0
    failed_count: int = 0
    fresh_count: int = 0
    stale_count: int = 0
    strict_ready_project_count: int = 0
    strict_ready_project_rate_percent: float = 0.0
    latest_fetched_at: Optional[datetime] = None
    strict_ready_project_ids: list[str] = Field(default_factory=list)
    stale_project_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MarketEvidenceProviderStatus(APIModel):
    provider: ConnectorKind
    provider_label: str
    endpoint: Optional[str] = None
    configured: bool = False
    auth_configured: bool = False
    auth_header: str = "Authorization"
    auth_source: str = "none"
    strict_ready: bool = False
    fallback_reason: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class MarketEvidenceProviderStatusReport(APIModel):
    report_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    provider_count: int = 0
    configured_count: int = 0
    auth_configured_count: int = 0
    strict_ready_count: int = 0
    entries: list[MarketEvidenceProviderStatus] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceCruiseProjectHealthItem(APIModel):
    project_id: str
    name: str
    url: str
    auto_cruise_enabled: bool = False
    connection_health: ConnectionHealth = ConnectionHealth.unknown
    sync_interval_minutes: int = 60
    last_sync_at: Optional[datetime] = None
    next_sync_at: Optional[datetime] = None
    due_now: bool = False
    overdue: bool = False
    last_run_status: Optional[str] = None


class WorkspaceCruiseHealthReport(APIModel):
    report_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    auto_cruise_enabled: bool = False
    project_count: int = 0
    enabled_project_count: int = 0
    due_project_count: int = 0
    overdue_project_count: int = 0
    next_due_at: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    enabled_project_ids: list[str] = Field(default_factory=list)
    due_project_ids: list[str] = Field(default_factory=list)
    overdue_project_ids: list[str] = Field(default_factory=list)
    project_samples: list[WorkspaceCruiseProjectHealthItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ProjectCruiseHealthReport(APIModel):
    report_id: str
    project_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    auto_cruise_enabled: bool = False
    connection_health: ConnectionHealth = ConnectionHealth.unknown
    sync_interval_minutes: int = 60
    last_sync_at: Optional[datetime] = None
    next_sync_at: Optional[datetime] = None
    due_now: bool = False
    overdue: bool = False
    last_run_status: Optional[str] = None
    project_sample: Optional[WorkspaceCruiseProjectHealthItem] = None
    notes: list[str] = Field(default_factory=list)


class MarketEvidenceSummary(APIModel):
    source_type: Literal["trend", "news", "qa"]
    total_count: int = 0
    connected_count: int = 0
    synthetic_count: int = 0
    failed_count: int = 0
    latest_fetched_at: Optional[datetime] = None
    auth_sources: list[str] = Field(default_factory=list)
    fallback_reasons: list[str] = Field(default_factory=list)
    connected_endpoints: list[str] = Field(default_factory=list)
    connected_source_refs: list[str] = Field(default_factory=list)
    average_latency_ms: Optional[int] = None


class ProjectConnection(APIModel):
    connection_id: str
    provider: ConnectorKind
    label: str
    enabled: bool = True
    status: ConnectorStatus = ConnectorStatus.unavailable
    provider_mode: Literal["real", "fallback", "unconfigured"] = "unconfigured"
    strict_eligible: bool = False
    blocking_reason: Optional[str] = None
    config: dict[str, Any] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)
    provenance: list[str] = Field(default_factory=list)
    last_checked_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    recent_evidence_label: Optional[str] = None
    recent_evidence_ref: Optional[str] = None
    recent_evidence_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    next_sync_at: Optional[datetime] = None


class ProjectState(APIModel):
    project_id: str
    connection_health: ConnectionHealth = ConnectionHealth.unknown
    auto_cruise_enabled: bool = False
    sync_interval_minutes: int = 60
    last_sync_at: Optional[datetime] = None
    next_sync_at: Optional[datetime] = None
    last_run_id: Optional[str] = None
    last_run_status: Optional[str] = "idle"


class ProjectConnections(APIModel):
    project_id: str
    state: ProjectState
    connections: list[ProjectConnection] = Field(default_factory=list)


class ProjectConnectionEvidenceEntry(APIModel):
    provider: ConnectorKind
    label: str
    status: ConnectorStatus
    provider_mode: Literal["real", "fallback", "unconfigured"] = "unconfigured"
    strict_eligible: bool = False
    auth_source: Optional[str] = None
    fallback_reason: Optional[str] = None
    latency_ms: Optional[int] = None
    recent_evidence_label: Optional[str] = None
    recent_evidence_ref: Optional[str] = None
    recent_evidence_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None


class ProjectConnectionEvidenceReport(APIModel):
    project_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    total: int = 0
    real_count: int = 0
    fallback_count: int = 0
    unconfigured_count: int = 0
    entries: list[ProjectConnectionEvidenceEntry] = Field(default_factory=list)


class CrawlDiagnosticsHistoryEntry(APIModel):
    audit_id: str
    project_id: str
    url: str
    snapshot_available: bool = False
    failure_code: Optional[str] = None
    manual_intervention_required: bool = False
    html_artifact_ref: Optional[str] = None
    screenshot_artifact_ref: Optional[str] = None
    created_at: datetime
    actor: Optional[str] = None


class CrawlDiagnosticsHistoryReport(APIModel):
    project_id: Optional[str] = None
    generated_at: datetime = Field(default_factory=utcnow)
    total: int = 0
    entries: list[CrawlDiagnosticsHistoryEntry] = Field(default_factory=list)


class WorkspaceConnectionEvidenceEntry(ProjectConnectionEvidenceEntry):
    project_id: str
    project_name: str
    project_url: str


class WorkspaceConnectionEvidenceProviderSummary(APIModel):
    provider: ConnectorKind
    total: int = 0
    real_count: int = 0
    fallback_count: int = 0
    unconfigured_count: int = 0
    project_count: int = 0
    recent_evidence_label: Optional[str] = None
    recent_evidence_ref: Optional[str] = None
    recent_evidence_at: Optional[datetime] = None


class WorkspaceConnectionEvidenceReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    real_count: int = 0
    fallback_count: int = 0
    unconfigured_count: int = 0
    entries: list[WorkspaceConnectionEvidenceEntry] = Field(default_factory=list)
    provider_summaries: list[WorkspaceConnectionEvidenceProviderSummary] = Field(default_factory=list)


class Opportunity(APIModel):
    id: str
    category: Literal["seo", "ad", "technical", "ux"]
    title: str
    description: str
    impact_score: int
    effort_score: int
    risk_score: int
    skill_ids: list[str] = Field(default_factory=list)
    preview_target: str
    evidence: list[str] = Field(default_factory=list)


class OpportunitySet(APIModel):
    seo: list[Opportunity] = Field(default_factory=list)
    ad: list[Opportunity] = Field(default_factory=list)
    technical: list[Opportunity] = Field(default_factory=list)
    ux: list[Opportunity] = Field(default_factory=list)


class PlanStep(APIModel):
    id: str
    skill_id: str
    action: str
    target: str
    expected_output: str
    approval_required: bool
    destructive: bool
    rollback_supported: bool


class Plan(APIModel):
    plan_id: str
    site_id: str
    deployment_mode: DeploymentMode
    risk_score: int
    release_strategy: str
    steps: list[PlanStep] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
    requires_manual_approval: bool
    auto_deploy_allowed: bool


class UXReview(APIModel):
    score: int
    issues: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ApprovalRequest(APIModel):
    approval_id: str
    task_id: str
    status: ApprovalStatus
    required_approvers: list[str] = Field(default_factory=list)
    policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    risk_summary: str
    decision_hint: str


class BulkApprovalRequest(APIModel):
    task_ids: list[str] = Field(default_factory=list)
    actor: Optional[str] = None
    note: Optional[str] = None


class BulkApprovalResult(APIModel):
    task_ids: list[str] = Field(default_factory=list)
    approved_count: int = 0
    skipped_task_ids: list[str] = Field(default_factory=list)
    bundles: list["WorkflowBundle"] = Field(default_factory=list)


class ProjectRun(APIModel):
    run_id: str
    project_id: str
    task_id: Optional[str] = None
    trigger: RunTrigger
    status: RunStatus
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: Optional[datetime] = None
    risk_score: int
    connector_status: dict[str, ConnectorStatus] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    auto_deploy: bool = False
    rollback_ready: bool = False
    runtime_route_ready: bool = False
    runtime_route_summary: Optional[str] = None
    runtime_route_request_path: Optional[str] = None
    runtime_route_request_method: Optional[str] = None
    runtime_route_execution_mode: Optional[Literal["runtime", "preview", "blocked"]] = None
    runtime_route_execution_action: Optional[Literal["serve_runtime", "serve_preview", "block"]] = None
    runtime_route_execution_reason: Optional[str] = None
    runtime_route_execution_entrypoint: Optional[str] = None
    gateway_route_provider_name: Optional[str] = None
    gateway_route_fallback_provider_name: Optional[str] = None
    gateway_route_priority: Optional[int] = None


class PreviewArtifact(APIModel):
    preview_id: str
    before_html: str
    after_html: str
    dom_insertions: list[str] = Field(default_factory=list)
    css_diff: str
    performance_budget: dict[str, int]
    diff_summary: str


class DeploymentRecord(APIModel):
    deployment_id: str
    task_id: str
    mode: DeploymentMode
    status: Literal["blocked", "scheduled", "deployed", "failed"]
    artifact_ref: str
    release_notes: list[str] = Field(default_factory=list)
    rollback_ready: bool
    strict_mode: bool = False
    verified_patch: bool = False
    patch_audit: dict[str, Any] = Field(default_factory=dict)
    patch_manifest_ref: Optional[str] = None
    writeback_target: Optional[str] = None
    writeback_auth_source: Optional[str] = None
    writeback_attempts: list[dict[str, Any]] = Field(default_factory=list)
    provider_artifact_id: Optional[str] = None
    provider_url: Optional[str] = None
    writeback_summary: dict[str, Any] = Field(default_factory=dict)
    strict_blockers: list[dict[str, Any]] = Field(default_factory=list)
    fallback_reason: Optional[str] = None
    failure_code: Optional[str] = None


class DeploymentHistoryEntry(APIModel):
    project_id: Optional[str] = None
    deployment: DeploymentRecord
    task_status: WorkflowStage
    approval_status: ApprovalStatus
    updated_at: datetime
    rollback_id: Optional[str] = None


class MetricSnapshot(APIModel):
    snapshot_id: str
    project_id: str
    task_id: str
    seo_score: int
    ad_fit_score: int
    core_web_vitals: dict[str, int]
    traffic_delta: int
    conversion_delta: int
    source_status: dict[str, ConnectorStatus] = Field(default_factory=dict)
    source_metrics_summary: list["SourceMetricSummary"] = Field(default_factory=list)
    external_metrics: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)


class SourceMetricSummary(APIModel):
    source: Literal["search_console", "ga4", "ad_network"]
    status: ConnectorStatus
    primary_metric: str
    secondary_metric: str
    tertiary_metric: Optional[str] = None
    auth_source: Optional[str] = None
    fallback_reason: Optional[str] = None


class MetricHistoryReport(APIModel):
    project_id: str
    total: int = 0
    limit: int = 20
    offset: int = 0
    snapshots: list[MetricSnapshot] = Field(default_factory=list)


class RollbackBundle(APIModel):
    rollback_id: str
    deployment_id: str
    commands: list[str] = Field(default_factory=list)
    safe_window_minutes: int
    reason: str
    expected_effect: str


class RollbackHistoryEntry(APIModel):
    project_id: Optional[str] = None
    rollback: RollbackBundle
    task_id: str
    task_status: WorkflowStage
    approval_status: ApprovalStatus
    updated_at: datetime


class DeploymentHistoryReport(APIModel):
    project_id: str
    total: int = 0
    entries: list[DeploymentHistoryEntry] = Field(default_factory=list)


class RollbackHistoryReport(APIModel):
    project_id: str
    total: int = 0
    entries: list[RollbackHistoryEntry] = Field(default_factory=list)


class SkillDefinition(APIModel):
    skill_id: str
    suite: Literal["read", "seo", "ad", "deploy", "observe", "ecommerce"]
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    is_destructive: bool
    required_approval: bool
    rollback_supported: bool
    observability: dict[str, Any] = Field(default_factory=dict)
    failure_contract: str


class WorkspacePolicy(APIModel):
    auto_deploy_enabled: bool = True
    approval_required_threshold: int = 60
    block_auto_deploy_threshold: int = 80
    monitor_window_minutes: int = 90
    rollback_window_minutes: int = 5
    auto_cruise_enabled: bool = False
    allowed_deployment_modes: list[DeploymentMode] = Field(
        default_factory=lambda: [
            DeploymentMode.github_pr,
            DeploymentMode.cms_draft,
            DeploymentMode.universal_script,
            DeploymentMode.static_export,
        ]
    )


class WorkspacePolicyUpdateRequest(APIModel):
    auto_deploy_enabled: Optional[bool] = None
    approval_required_threshold: Optional[int] = None
    block_auto_deploy_threshold: Optional[int] = None
    monitor_window_minutes: Optional[int] = None
    rollback_window_minutes: Optional[int] = None
    auto_cruise_enabled: Optional[bool] = None
    allowed_deployment_modes: Optional[list[DeploymentMode]] = None


class WorkspaceBillingPolicy(APIModel):
    plan_tier: Literal["starter", "growth", "scale", "enterprise"] = "growth"
    commercial_mode_enabled: bool = False
    settlement_enabled: bool = False
    settlement_provider_name: str = "manual"
    settlement_account_ref: Optional[str] = None
    settlement_currency: str = "USD"
    settlement_window_days: int = 30
    settlement_holdback_percent: int = 0
    settlement_payout_threshold_cents: int = 10000
    monthly_project_limit: int = 10
    monthly_task_limit: int = 100
    monthly_deploy_limit: int = 30
    monthly_budget_cents: int = 50000
    overage_blocking: bool = True
    notes: list[str] = Field(default_factory=list)


class WorkspaceBillingPolicyUpdateRequest(APIModel):
    plan_tier: Optional[Literal["starter", "growth", "scale", "enterprise"]] = None
    commercial_mode_enabled: Optional[bool] = None
    settlement_enabled: Optional[bool] = None
    settlement_provider_name: Optional[str] = None
    settlement_account_ref: Optional[str] = None
    settlement_currency: Optional[str] = None
    settlement_window_days: Optional[int] = None
    settlement_holdback_percent: Optional[int] = None
    settlement_payout_threshold_cents: Optional[int] = None
    monthly_project_limit: Optional[int] = None
    monthly_task_limit: Optional[int] = None
    monthly_deploy_limit: Optional[int] = None
    monthly_budget_cents: Optional[int] = None
    overage_blocking: Optional[bool] = None
    notes: Optional[list[str]] = None


class WorkspaceBillingUsage(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    active_project_count: int = 0
    task_count: int = 0
    run_count_30d: int = 0
    deploy_count_30d: int = 0
    rollback_count_30d: int = 0
    auto_deploy_count_30d: int = 0
    strict_ready_project_count: int = 0
    estimated_usage_cents: int = 0
    project_limit_used_percent: float = 0.0
    task_limit_used_percent: float = 0.0
    deploy_limit_used_percent: float = 0.0
    budget_limit_used_percent: float = 0.0
    over_project_limit: bool = False
    over_task_limit: bool = False
    over_deploy_limit: bool = False
    over_budget_limit: bool = False
    notes: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlement(APIModel):
    settlement_enabled: bool = False
    settlement_provider_name: str = "manual"
    settlement_account_ref: Optional[str] = None
    settlement_currency: str = "USD"
    settlement_window_days: int = 30
    settlement_holdback_percent: int = 0
    payout_threshold_cents: int = 10000
    gross_estimated_cents: int = 0
    holdback_cents: int = 0
    net_settlement_cents: int = 0
    settlement_due_cents: int = 0
    settlement_ready: bool = False
    settlement_blocked: bool = False
    notes: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlementExecutionRequest(APIModel):
    dry_run: bool = True
    provider_name: Optional[str] = None
    account_ref: Optional[str] = None
    currency: Optional[str] = None
    amount_cents: Optional[int] = None
    memo: Optional[str] = None
    project_id: Optional[str] = None
    destination_type: Optional[str] = None
    destination_ref: Optional[str] = None
    beneficiary_name: Optional[str] = None
    beneficiary_email: Optional[str] = None
    rail: Optional[str] = None
    country_code: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    provider_payload: dict[str, Any] = Field(default_factory=dict)


class WorkspaceBillingSettlementExecutionBatchRequest(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    dry_run: bool = True
    provider_name: Optional[str] = None
    account_ref: Optional[str] = None
    currency: Optional[str] = None
    amount_cents: Optional[int] = None
    memo: Optional[str] = None
    destination_type: Optional[str] = None
    destination_ref: Optional[str] = None
    beneficiary_name: Optional[str] = None
    beneficiary_email: Optional[str] = None
    rail: Optional[str] = None
    country_code: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    provider_payload: dict[str, Any] = Field(default_factory=dict)
    actor: str = "ui"


class WorkspaceBillingSettlementExecution(APIModel):
    audit_id: str
    created_at: datetime
    actor: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    dry_run: bool
    provider_name: str
    gateway_provider_name: Optional[str] = None
    gateway_route_provider_name: Optional[str] = None
    gateway_route_fallback_provider_name: Optional[str] = None
    gateway_route_priority: Optional[int] = None
    gateway_route_reason: Optional[str] = None
    account_ref: Optional[str] = None
    destination_type: Optional[str] = None
    destination_ref: Optional[str] = None
    beneficiary_name: Optional[str] = None
    beneficiary_email: Optional[str] = None
    rail: Optional[str] = None
    country_code: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    provider_payload: dict[str, Any] = Field(default_factory=dict)
    currency: str
    gross_cents: int = 0
    holdback_cents: int = 0
    net_cents: int = 0
    due_cents: int = 0
    status: Literal["previewed", "completed", "failed", "blocked"] = "previewed"
    failure_code: Optional[str] = None
    retryable: bool = False
    transaction_ref: Optional[str] = None
    provider_endpoint: Optional[str] = None
    provider_url: Optional[str] = None
    provider_artifact_id: Optional[str] = None
    provider_mode: Optional[str] = None
    auth_source: Optional[str] = None
    message: Optional[str] = None
    memo: Optional[str] = None
    settlement_ready: bool = False
    gateway_ready: bool = False
    gateway_route_ready: bool = False
    notes: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlementExecutionReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    billing: "WorkspaceBillingReport"
    execution: WorkspaceBillingSettlementExecution
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlementExecutionBatchReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    dry_run: bool = True
    actor: str = "ui"
    note: Optional[str] = None
    total_count: int = 0
    completed_count: int = 0
    previewed_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    items: list[WorkspaceBillingSettlementExecutionReport] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlementExecutionHistoryReport(APIModel):
    project_id: Optional[str] = None
    total: int = 0
    entries: list[WorkspaceBillingSettlementExecution] = Field(default_factory=list)


class WorkspaceBillingSettlementGatewayRoute(APIModel):
    provider_name: str
    enabled: bool = True
    fallback_provider_name: str = "manual"
    priority: int = 100
    notes: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlementGatewayPolicy(APIModel):
    gateway_enabled: bool = False
    default_provider_name: str = "manual"
    fallback_provider_name: str = "manual"
    strict_routing: bool = False
    routes: list[WorkspaceBillingSettlementGatewayRoute] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlementGatewayPolicyUpdateRequest(APIModel):
    gateway_enabled: Optional[bool] = None
    default_provider_name: Optional[str] = None
    fallback_provider_name: Optional[str] = None
    strict_routing: Optional[bool] = None
    routes: Optional[list[WorkspaceBillingSettlementGatewayRoute]] = None
    notes: Optional[list[str]] = None


class WorkspaceBillingSettlementGatewayRouteStatus(APIModel):
    provider_name: str
    enabled: bool = True
    fallback_provider_name: str
    resolved_provider_name: str
    priority: int = 100
    route_ready: bool = False
    notes: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlementGatewayPublishReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    provider_name: str
    strict_routing: bool = False
    status: Literal["blocked", "completed", "failed"]
    gateway_endpoint: Optional[str] = None
    gateway_url: Optional[str] = None
    gateway_artifact_id: Optional[str] = None
    gateway_mode: Literal["external", "local"] = "external"
    auth_source: str = "config"
    message: str
    failure_code: Optional[str] = None
    retryable: bool = False
    notes: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlementGatewayReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    policy: WorkspaceBillingSettlementGatewayPolicy = Field(default_factory=WorkspaceBillingSettlementGatewayPolicy)
    route_count: int = 0
    enabled_route_count: int = 0
    provider_count: int = 0
    route_ready_count: int = 0
    gateway_ready: bool = False
    routes: list[WorkspaceBillingSettlementGatewayRouteStatus] = Field(default_factory=list)
    gateway_publish: Optional[WorkspaceBillingSettlementGatewayPublishReport] = None
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlementGatewayExportReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    gateway_enabled: bool = False
    strict_routing: bool = False
    gateway_ready: bool = False
    route_count: int = 0
    provider_count: int = 0
    endpoint_count: int = 0
    endpoint: Optional[str] = None
    auth_header: str = "Authorization"
    auth_source: str = "none"
    nginx_snippet: str
    caddyfile_fragment: str
    haproxy_conf: str = ""
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlementGatewayHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    project_count: int = 0
    gateway_ready_count: int = 0
    gateway_route_ready_count: int = 0
    dry_run_count: int = 0
    live_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    latest_project_id: Optional[str] = None
    latest_project_name: Optional[str] = None
    latest_gateway_provider_name: Optional[str] = None
    latest_gateway_route_provider_name: Optional[str] = None
    latest_gateway_route_reason: Optional[str] = None
    latest_gateway_route_priority: Optional[int] = None
    latest_failure_code: Optional[str] = None
    latest_retryable: Optional[bool] = None
    entries: list[WorkspaceBillingSettlementExecution] = Field(default_factory=list)


class WorkspaceBillingSettlementGatewayProviderStatus(APIModel):
    provider_name: str
    provider_label: str
    endpoint: Optional[str] = None
    configured: bool = False
    auth_configured: bool = False
    auth_header: str = "Authorization"
    auth_source: str = "none"
    route_enabled: bool = True
    fallback_provider_name: str = "manual"
    resolved_provider_name: str = "manual"
    priority: int = 100
    route_ready: bool = False
    strict_ready: bool = False
    fallback_reason: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlementGatewayProviderStatusReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    gateway_enabled: bool = False
    provider_count: int = 0
    configured_count: int = 0
    auth_configured_count: int = 0
    route_ready_count: int = 0
    strict_ready_count: int = 0
    gateway_ready: bool = False
    entries: list[WorkspaceBillingSettlementGatewayProviderStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlementProviderRequirement(APIModel):
    class ConditionalRequirement(APIModel):
        when_field: str
        when_value: str
        required_fields: list[str] = Field(default_factory=list)
        metadata_fields: list[str] = Field(default_factory=list)
        notes: list[str] = Field(default_factory=list)

    provider_name: str
    provider_label: str
    destination_types: list[str] = Field(default_factory=list)
    rails: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    metadata_fields: list[str] = Field(default_factory=list)
    conditional_requirements: list[ConditionalRequirement] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceBillingSettlementProviderRequirementsReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    provider_count: int = 0
    entries: list[WorkspaceBillingSettlementProviderRequirement] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class WorkspaceBillingReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    policy: WorkspaceBillingPolicy = Field(default_factory=WorkspaceBillingPolicy)
    usage: WorkspaceBillingUsage = Field(default_factory=WorkspaceBillingUsage)
    settlement: WorkspaceBillingSettlement = Field(default_factory=WorkspaceBillingSettlement)
    settlement_gateway: Optional[WorkspaceBillingSettlementGatewayReport] = None
    settlement_gateway_history: Optional[WorkspaceBillingSettlementGatewayHistoryReport] = None
    commercial_ready: bool = False
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class WorkspaceModelGatewayRoute(APIModel):
    route_suite: Literal["read", "seo", "ad", "deploy", "observe"]
    provider_name: str
    enabled: bool = True
    fallback_provider_name: str = "local"
    priority: int = 100
    notes: list[str] = Field(default_factory=list)


class WorkspaceModelGatewayPolicy(APIModel):
    gateway_enabled: bool = False
    default_provider_name: str = "local"
    fallback_provider_name: str = "local"
    strict_routing: bool = False
    routes: list[WorkspaceModelGatewayRoute] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceModelGatewayPolicyUpdateRequest(APIModel):
    gateway_enabled: Optional[bool] = None
    default_provider_name: Optional[str] = None
    fallback_provider_name: Optional[str] = None
    strict_routing: Optional[bool] = None
    routes: Optional[list[WorkspaceModelGatewayRoute]] = None
    notes: Optional[list[str]] = None


class WorkspaceModelGatewayRouteStatus(APIModel):
    route_suite: Literal["read", "seo", "ad", "deploy", "observe"]
    provider_name: str
    enabled: bool = True
    fallback_provider_name: str
    resolved_provider_name: str
    priority: int = 100
    route_ready: bool = False
    notes: list[str] = Field(default_factory=list)


class WorkspaceModelGatewayProviderStatus(APIModel):
    route_suite: Literal["read", "seo", "ad", "deploy", "observe"]
    provider_name: str
    provider_label: str
    enabled: bool = True
    fallback_provider_name: str
    resolved_provider_name: str
    priority: int = 100
    route_ready: bool = False
    strict_ready: bool = False
    fallback_reason: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class WorkspaceModelGatewayProviderStatusReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    gateway_enabled: bool = False
    provider_count: int = 0
    route_count: int = 0
    route_ready_count: int = 0
    strict_ready_count: int = 0
    gateway_ready: bool = False
    entries: list[WorkspaceModelGatewayProviderStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class WorkspaceModelGatewayReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    policy: WorkspaceModelGatewayPolicy = Field(default_factory=WorkspaceModelGatewayPolicy)
    route_count: int = 0
    enabled_route_count: int = 0
    provider_count: int = 0
    suite_count: int = 0
    route_ready_count: int = 0
    gateway_ready: bool = False
    routes: list[WorkspaceModelGatewayRouteStatus] = Field(default_factory=list)
    gateway_publish: Optional["WorkspaceModelGatewayPublishReport"] = None
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class WorkspaceModelGatewayPublishReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    strict_routing: bool = False
    status: Literal["completed", "blocked", "failed"] = "completed"
    failure_code: Optional[str] = None
    retryable: bool = False
    gateway_endpoint: Optional[str] = None
    gateway_url: Optional[str] = None
    gateway_artifact_id: Optional[str] = None
    gateway_mode: Optional[str] = None
    auth_source: Optional[str] = None
    message: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class WorkspaceModelGatewayHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    project_count: int = 0
    runtime_ready_count: int = 0
    preview_only_count: int = 0
    gateway_ready_count: int = 0
    route_ready_count: int = 0
    latest_project_id: Optional[str] = None
    latest_project_name: Optional[str] = None
    latest_request_path: Optional[str] = None
    latest_request_method: Optional[str] = None
    latest_execution_mode: Optional[Literal["runtime", "preview", "blocked"]] = None
    latest_execution_action: Optional[Literal["serve_runtime", "serve_preview", "block"]] = None
    latest_execution_reason: Optional[str] = None
    latest_execution_entrypoint: Optional[str] = None
    latest_gateway_provider_name: Optional[str] = None
    latest_gateway_route_provider_name: Optional[str] = None
    latest_gateway_route_fallback_provider_name: Optional[str] = None
    latest_gateway_route_reason: Optional[str] = None
    latest_gateway_route_priority: Optional[int] = None
    entries: list["WorkspaceRuntimeRouteHistoryItem"] = Field(default_factory=list)


class WorkspaceExperimentVariant(APIModel):
    variant_name: str
    allocation_percent: int = 0
    enabled: bool = True
    notes: list[str] = Field(default_factory=list)


class WorkspaceExperiment(APIModel):
    experiment_key: str
    enabled: bool = True
    target_surface: Literal["site", "seo", "content", "ad", "ui"] = "site"
    target_locale: Optional[str] = None
    target_project_ids: list[str] = Field(default_factory=list)
    control_variant_name: str = "control"
    assignment_strategy: Literal["hash", "sticky", "round_robin"] = "hash"
    primary_metric: str = "conversion_rate"
    variants: list[WorkspaceExperimentVariant] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceExperimentPolicy(APIModel):
    experiments_enabled: bool = False
    strict_assignment: bool = False
    default_assignment_strategy: Literal["hash", "sticky", "round_robin"] = "hash"
    experiments: list[WorkspaceExperiment] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceExperimentPolicyUpdateRequest(APIModel):
    experiments_enabled: Optional[bool] = None
    strict_assignment: Optional[bool] = None
    default_assignment_strategy: Optional[Literal["hash", "sticky", "round_robin"]] = None
    experiments: Optional[list[WorkspaceExperiment]] = None
    notes: Optional[list[str]] = None


class WorkspaceExperimentStatus(APIModel):
    experiment_key: str
    enabled: bool = True
    target_surface: Literal["site", "seo", "content", "ad", "ui"] = "site"
    target_locale: Optional[str] = None
    target_project_count: int = 0
    variant_count: int = 0
    total_allocation_percent: int = 0
    balanced_allocation: bool = False
    control_variant_present: bool = False
    experiment_ready: bool = False
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceExperimentReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    policy: WorkspaceExperimentPolicy = Field(default_factory=WorkspaceExperimentPolicy)
    experiment_count: int = 0
    enabled_experiment_count: int = 0
    ready_experiment_count: int = 0
    variant_count: int = 0
    balanced_experiment_count: int = 0
    project_scope_count: int = 0
    workspace_ready: bool = False
    experiments: list[WorkspaceExperimentStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class WorkspaceExperimentAssignmentRequest(APIModel):
    project_id: Optional[str] = None
    subject_key: Optional[str] = None
    session_key: Optional[str] = None
    target_surface: Literal["site", "seo", "content", "ad", "ui"] = "site"
    target_locale: Optional[str] = None
    experiment_key: Optional[str] = None


class WorkspaceExperimentAssignment(APIModel):
    experiment_key: str
    enabled: bool = True
    target_surface: Literal["site", "seo", "content", "ad", "ui"] = "site"
    target_locale: Optional[str] = None
    target_project_match: bool = False
    assignment_strategy: Literal["hash", "sticky", "round_robin"] = "hash"
    subject_key: str
    bucket_key: str
    bucket_roll: int = 0
    bucket_size: int = 0
    eligible: bool = False
    control_variant_name: str = "control"
    assigned_variant_name: Optional[str] = None
    assigned_variant_index: Optional[int] = None
    variant_count: int = 0
    total_allocation_percent: int = 0
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceExperimentAssignmentReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    policy: WorkspaceExperimentPolicy = Field(default_factory=WorkspaceExperimentPolicy)
    project_id: Optional[str] = None
    subject_key: str
    session_key: Optional[str] = None
    target_surface: Literal["site", "seo", "content", "ad", "ui"] = "site"
    target_locale: Optional[str] = None
    experiment_count: int = 0
    matched_experiment_count: int = 0
    assigned_experiment_count: int = 0
    strict_assignment: bool = False
    assignments: list[WorkspaceExperimentAssignment] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class WorkspaceSiteCluster(APIModel):
    cluster_key: str
    enabled: bool = True
    canonical_project_id: Optional[str] = None
    project_ids: list[str] = Field(default_factory=list)
    supported_locales: list[str] = Field(default_factory=list)
    primary_locale: Optional[str] = None
    locale_strategy: Literal["path", "subdomain", "cctld"] = "path"
    notes: list[str] = Field(default_factory=list)


class WorkspaceLocalizationPolicy(APIModel):
    localization_enabled: bool = False
    strict_localization: bool = False
    default_locale: str = "en-US"
    default_language: str = "en"
    clusters: list[WorkspaceSiteCluster] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceLocalizationPolicyUpdateRequest(APIModel):
    localization_enabled: Optional[bool] = None
    strict_localization: Optional[bool] = None
    default_locale: Optional[str] = None
    default_language: Optional[str] = None
    clusters: Optional[list[WorkspaceSiteCluster]] = None
    notes: Optional[list[str]] = None


class WorkspaceLocalizationClusterStatus(APIModel):
    cluster_key: str
    enabled: bool = True
    canonical_project_id: Optional[str] = None
    project_count: int = 0
    locale_count: int = 0
    supported_locale_count: int = 0
    has_canonical_project: bool = False
    locale_coverage_ready: bool = False
    cluster_ready: bool = False
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceLocalizationReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    policy: WorkspaceLocalizationPolicy = Field(default_factory=WorkspaceLocalizationPolicy)
    cluster_count: int = 0
    enabled_cluster_count: int = 0
    ready_cluster_count: int = 0
    project_count: int = 0
    locale_count: int = 0
    workspace_ready: bool = False
    clusters: list[WorkspaceLocalizationClusterStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class WorkspaceLocalizationAssignmentRequest(APIModel):
    project_id: Optional[str] = None
    target_locale: Optional[str] = None
    host: Optional[str] = None
    subject_key: Optional[str] = None


class WorkspaceLocalizationAssignment(APIModel):
    cluster_key: str
    enabled: bool = True
    locale_strategy: Literal["path", "subdomain", "cctld"] = "path"
    subject_key: str
    project_id: Optional[str] = None
    target_locale: Optional[str] = None
    matched_by_project: bool = False
    matched_by_locale: bool = False
    matched_by_host: bool = False
    canonical_project_id: Optional[str] = None
    project_count: int = 0
    locale_count: int = 0
    cluster_ready: bool = False
    route_prefix: str = ""
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceLocalizationAssignmentReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    policy: WorkspaceLocalizationPolicy = Field(default_factory=WorkspaceLocalizationPolicy)
    project_id: Optional[str] = None
    target_locale: Optional[str] = None
    host: Optional[str] = None
    subject_key: str
    cluster_count: int = 0
    matched_cluster_count: int = 0
    assigned_cluster_count: int = 0
    strict_localization: bool = False
    assignments: list[WorkspaceLocalizationAssignment] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class RuntimeRouteReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: str
    task_id: str
    subject_key: str
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    target_surface: Literal["site", "seo", "content", "ad", "ui"] = "site"
    target_locale: Optional[str] = None
    host: Optional[str] = None
    experiment_assignment: Optional[WorkspaceExperimentAssignmentReport] = None
    localization_assignment: Optional[WorkspaceLocalizationAssignmentReport] = None
    gateway_report: Optional["WorkspaceModelGatewayReport"] = None
    resolved_providers: dict[str, str] = Field(default_factory=dict)
    gateway_route_provider_name: Optional[str] = None
    gateway_route_fallback_provider_name: Optional[str] = None
    gateway_route_priority: Optional[int] = None
    runtime_ready: bool = False
    execution_mode: Literal["runtime", "preview", "blocked"] = "preview"
    execution_action: Literal["serve_runtime", "serve_preview", "block"] = "serve_preview"
    execution_reason: Optional[str] = None
    execution_entrypoint: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class RuntimeRouteRequest(APIModel):
    task_id: Optional[str] = None
    subject_key: Optional[str] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    target_surface: Literal["site", "seo", "content", "ad", "ui"] = "site"
    target_locale: Optional[str] = None
    host: Optional[str] = None


class RuntimeExecutionResponse(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: str
    task_id: str
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    served_mode: Literal["runtime", "preview", "blocked"] = "blocked"
    served_target: Literal["deployment", "preview_artifact", "none"] = "none"
    status_code: int = 409
    runtime_route: RuntimeRouteReport
    project: ProjectSummary
    workflow_status: WorkflowStage
    preview: Optional[PreviewArtifact] = None
    deployment: Optional[DeploymentRecord] = None
    served_artifact_ref: Optional[str] = None
    served_url: Optional[str] = None
    served_content_type: Optional[str] = None
    served_response_mode: Optional[Literal["json", "redirect", "html", "blocked"]] = None
    notes: list[str] = Field(default_factory=list)


class ProjectRuntimeEdgeConfig(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: str
    project_name: str
    project_url: Optional[str] = None
    site_host: Optional[str] = None
    strict_providers_enabled: bool = False
    runtime_ready: bool = False
    execution_mode: Literal["runtime", "preview", "blocked"] = "blocked"
    execution_action: Literal["serve_runtime", "serve_preview", "block"] = "block"
    execution_reason: Optional[str] = None
    edge_mode: Literal["proxy"] = "proxy"
    edge_proxy_url: str
    edge_proxy_strict_url: str
    edge_health_url: str
    enforce_runtime_ready_default: bool = False
    preview_url: Optional[str] = None
    deployment_url: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    public_path: str = "/"
    proxy_path: str = ""
    strict_proxy_path: str = ""
    rewrite_rule: str = ""
    upstream_host: Optional[str] = None
    nginx_snippet: str
    caddy_snippet: str


class WorkspaceRuntimeEdgeConfigReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    strict_providers_enabled: bool = False
    project_id: Optional[str] = None
    project_count: int = 0
    runtime_ready_count: int = 0
    preview_only_count: int = 0
    blocked_count: int = 0
    edge_mode: Literal["proxy"] = "proxy"
    items: list[ProjectRuntimeEdgeConfig] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeRouteOverride(APIModel):
    project_id: str
    enabled: bool = True
    site_host: Optional[str] = None
    public_path: str = "/"
    proxy_path: Optional[str] = None
    strict_proxy_path: Optional[str] = None
    rewrite_rule: Optional[str] = None
    upstream_host: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeRouteOverridesUpdateRequest(APIModel):
    overrides: list[RuntimeEdgeRouteOverride] = Field(default_factory=list)
    replace: bool = True
    actor: str = "ui"
    note: Optional[str] = None


class RuntimeEdgeRouteOverridesReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    total: int = 0
    enabled_count: int = 0
    project_id: Optional[str] = None
    overrides: list[RuntimeEdgeRouteOverride] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeRouteMapItem(APIModel):
    project_id: str
    project_name: str
    site_host: str
    public_path: str = "/"
    proxy_path: str = ""
    strict_proxy_path: str = ""
    rewrite_rule: str = ""
    upstream_host: Optional[str] = None
    runtime_ready: bool = False
    execution_action: Literal["serve_runtime", "serve_preview", "block"] = "block"
    route_mode: Literal["strict", "default"] = "default"
    proxy_url: str
    health_url: str
    notes: list[str] = Field(default_factory=list)


class WorkspaceRuntimeEdgeRouteMapReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    strict_providers_enabled: bool = False
    strict_routes_only: bool = False
    project_id: Optional[str] = None
    project_count: int = 0
    host_count: int = 0
    duplicate_host_count: int = 0
    duplicate_hosts: list[str] = Field(default_factory=list)
    items: list[RuntimeEdgeRouteMapItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class RuntimeEdgeGatewayExportReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    strict_routes_only: bool = False
    project_id: Optional[str] = None
    project_count: int = 0
    host_count: int = 0
    duplicate_host_count: int = 0
    blocking_host_count: int = 0
    nginx_map_conf: str
    caddyfile_fragment: str
    haproxy_conf: str = ""
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class RuntimeEdgeValidationBlocker(APIModel):
    host: str
    project_id: str
    blocker_code: Literal["DUPLICATE_HOST", "STRICT_RUNTIME_NOT_READY", "CANARY_REQUIRED", "RUNTIME_EDGE_GATEWAY_PUBLISH_FAILED"] = "DUPLICATE_HOST"
    severity: Literal["blocking", "warning"] = "blocking"
    message: str


class RuntimeEdgeValidationReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    strict_routes_only: bool = False
    project_id: Optional[str] = None
    passed: bool = False
    project_count: int = 0
    host_count: int = 0
    duplicate_host_count: int = 0
    non_runtime_ready_host_count: int = 0
    blockers: list[RuntimeEdgeValidationBlocker] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class RuntimeEdgeRolloutStage(APIModel):
    stage_id: Literal["validate", "canary", "full"] = "validate"
    title: str
    passed: bool = False
    host_count: int = 0
    project_count: int = 0
    description: str
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeRolloutPlanReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    strict_routes_only: bool = False
    project_id: Optional[str] = None
    total_host_count: int = 0
    runtime_ready_host_count: int = 0
    blocked_host_count: int = 0
    duplicate_host_count: int = 0
    canary_host_count: int = 0
    canary_percent: int = 0
    stages: list[RuntimeEdgeRolloutStage] = Field(default_factory=list)
    blockers: list[RuntimeEdgeValidationBlocker] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class RuntimeEdgeRolloutExecuteRequest(APIModel):
    stage_id: Literal["validate", "canary", "full"] = "validate"
    strict_routes_only: bool = False
    project_id: Optional[str] = None
    canary_percent: int = 20
    dry_run: bool = True
    actor: str = "ui"
    note: Optional[str] = None


class RuntimeEdgeRolloutExecutionReport(APIModel):
    execution_id: str
    executed_at: datetime = Field(default_factory=utcnow)
    stage_id: Literal["validate", "canary", "full"] = "validate"
    strict_routes_only: bool = False
    dry_run: bool = True
    project_id: Optional[str] = None
    actor: str = "ui"
    note: Optional[str] = None
    status: Literal["planned", "blocked", "executed"] = "planned"
    plan: RuntimeEdgeRolloutPlanReport
    blocker_count: int = 0
    blockers: list[RuntimeEdgeValidationBlocker] = Field(default_factory=list)
    rollout_host_count: int = 0
    rollout_nginx_artifact_path: Optional[str] = None
    rollout_caddy_artifact_path: Optional[str] = None
    rollout_manifest_path: Optional[str] = None
    gateway_publish_status: Literal["planned", "blocked", "executed"] = "planned"
    provider_endpoint: Optional[str] = None
    provider_url: Optional[str] = None
    provider_artifact_id: Optional[str] = None
    failure_code: Optional[str] = None
    retryable: bool = False
    gateway_publish_notes: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class RuntimeEdgeDeploymentRequest(APIModel):
    strict_routes_only: bool = False
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    canary_percent: int = 20
    dry_run: bool = False
    actor: str = "ui"
    note: Optional[str] = None


class RuntimeEdgeDeploymentReport(APIModel):
    deployment_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    strict_routes_only: bool = False
    dry_run: bool = False
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    actor: str = "ui"
    note: Optional[str] = None
    status: Literal["planned", "blocked", "executed"] = "planned"
    export: RuntimeEdgeGatewayExportReport
    provider_endpoint: Optional[str] = None
    provider_url: Optional[str] = None
    provider_artifact_id: Optional[str] = None
    failure_code: Optional[str] = None
    retryable: bool = False
    message: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeDeploymentBatchRequest(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    strict_routes_only: bool = False
    canary_percent: int = 20
    dry_run: bool = False
    actor: str = "ui"
    note: Optional[str] = None


class RuntimeEdgeDeploymentBatchReport(APIModel):
    batch_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    strict_routes_only: bool = False
    dry_run: bool = False
    actor: str = "ui"
    note: Optional[str] = None
    total_count: int = 0
    executed_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    items: list[RuntimeEdgeDeploymentReport] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeDeploymentBatchEnqueueResult(APIModel):
    enqueued: bool
    skipped_duplicate: bool = False
    job_id: str
    stage: str = "runtime_edge_deployment_batch"
    strict_routes_only: bool = False
    canary_percent: int = 20
    dry_run: bool = True
    project_ids: list[str] = Field(default_factory=list)
    message: str = ""


class RuntimeEdgeHistorySummary(APIModel):
    total_count: int = 0
    strict_routes_only_count: int = 0
    executed_count: int = 0
    blocked_count: int = 0
    planned_count: int = 0
    failed_count: int = 0
    connected_count: int = 0
    skipped_count: int = 0
    gateway_ready_count: int = 0
    route_ready_count: int = 0


class RuntimeEdgeDeploymentHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    summary: "RuntimeEdgeHistorySummary" = Field(default_factory=lambda: RuntimeEdgeHistorySummary())
    executed_count: int = 0
    blocked_count: int = 0
    planned_count: int = 0
    items: list[RuntimeEdgeDeploymentReport] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeDeploymentBatchHistoryEntry(APIModel):
    audit_id: str
    created_at: datetime
    actor: str
    batch_id: str
    strict_routes_only: bool = False
    dry_run: bool = False
    total_count: int = 0
    executed_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    project_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeDeploymentBatchHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    summary: "RuntimeEdgeHistorySummary" = Field(default_factory=lambda: RuntimeEdgeHistorySummary())
    executed_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    entries: list[RuntimeEdgeDeploymentBatchHistoryEntry] = Field(default_factory=list)


class RuntimeIngressBundleReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    strict_routes_only: bool = False
    runtime_edge_export: RuntimeEdgeGatewayExportReport
    runtime_edge_gateway: RuntimeEdgeGatewayReport
    route_manifest: "RuntimeIngressRouteManifestReport"
    runtime_edge_deployment_history: RuntimeEdgeDeploymentHistoryReport
    visual_farm_gateway: VisualFarmGatewayReport
    visual_farm_deployment_history: VisualFarmDeploymentHistoryReport
    visual_farm_status: VisualFarmStatusReport
    bundle_ready: bool = False
    gateway_publish: Optional["RuntimeIngressGatewayPublishReport"] = None
    notes: list[str] = Field(default_factory=list)


class RuntimeIngressBundleBatchRequest(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    strict_routes_only: bool = False
    actor: str = "ui"
    note: Optional[str] = None


class RuntimeIngressBundleBatchReport(APIModel):
    batch_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    strict_routes_only: bool = False
    actor: str = "ui"
    note: Optional[str] = None
    total_count: int = 0
    completed_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    items: list[RuntimeIngressBundleReport] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeIngressBundleBatchEnqueueResult(APIModel):
    enqueued: bool
    skipped_duplicate: bool = False
    job_id: str
    stage: str = "runtime_ingress_bundle_batch"
    strict_routes_only: bool = False
    project_ids: list[str] = Field(default_factory=list)
    message: str = ""


class RuntimeIngressBundleBatchHistoryEntry(APIModel):
    audit_id: str
    created_at: datetime
    actor: str
    batch_id: str
    strict_routes_only: bool = False
    total_count: int = 0
    completed_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    project_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeIngressBundleBatchHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    completed_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    entries: list[RuntimeIngressBundleBatchHistoryEntry] = Field(default_factory=list)


class RuntimeIngressBundleBatchHealthReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    freshness_minutes: int = 0
    run_count: int = 0
    last_batch_id: Optional[str] = None
    last_batch_at: Optional[datetime] = None
    last_total_count: int = 0
    last_completed_count: int = 0
    last_blocked_count: int = 0
    last_failed_count: int = 0
    healthy: bool = False
    stale: bool = True
    notes: list[str] = Field(default_factory=list)


class RuntimeIngressRouteManifestItem(APIModel):
    project_id: str
    project_name: str
    site_host: str
    public_path: str = "/"
    proxy_path: str = ""
    strict_proxy_path: str = ""
    rewrite_rule: str = ""
    upstream_host: Optional[str] = None
    runtime_ready: bool = False
    execution_action: Literal["serve_runtime", "serve_preview", "block"] = "block"
    route_mode: Literal["strict", "default"] = "default"
    proxy_url: str
    health_url: str
    notes: list[str] = Field(default_factory=list)


class RuntimeIngressRouteManifestReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    strict_routes_only: bool = False
    project_count: int = 0
    host_count: int = 0
    runtime_ready_host_count: int = 0
    preview_only_host_count: int = 0
    blocked_host_count: int = 0
    items: list[RuntimeIngressRouteManifestItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class RuntimeIngressConfigArtifactReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    strict_routes_only: bool = False
    format: Literal["nginx", "caddy"] = "nginx"
    artifact_path: str
    manifest_path: Optional[str] = None
    content: str
    bundle_ready: bool = False
    gateway_publish: Optional["RuntimeIngressGatewayPublishReport"] = None
    notes: list[str] = Field(default_factory=list)


class RuntimeIngressConfigArtifactHistoryEntry(APIModel):
    audit_id: str
    created_at: datetime
    actor: str
    project_id: Optional[str] = None
    strict_routes_only: bool = False
    format: Literal["nginx", "caddy"] = "nginx"
    artifact_path: str
    bundle_ready: bool = False
    notes: list[str] = Field(default_factory=list)


class RuntimeIngressConfigArtifactHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    format: Optional[Literal["nginx", "caddy"]] = None
    total: int = 0
    bundle_ready_count: int = 0
    entries: list[RuntimeIngressConfigArtifactHistoryEntry] = Field(default_factory=list)


class RuntimeIngressGatewayPublishReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    strict_routes_only: bool = False
    status: Literal["completed", "blocked", "failed"] = "completed"
    failure_code: Optional[str] = None
    retryable: bool = False
    gateway_endpoint: Optional[str] = None
    gateway_url: Optional[str] = None
    gateway_artifact_id: Optional[str] = None
    gateway_mode: Optional[str] = None
    auth_source: Optional[str] = None
    message: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeGatewayRoute(APIModel):
    provider_name: str = "runtime_edge"
    enabled: bool = True
    fallback_provider_name: str = "runtime_edge"
    priority: int = 10
    endpoint: str = ""
    access_token: str = ""
    auth_header: str = "Authorization"
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeGatewayPolicy(APIModel):
    gateway_enabled: bool = False
    default_provider_name: str = "runtime_edge"
    fallback_provider_name: str = "runtime_edge"
    strict_routing: bool = False
    routes: list[RuntimeEdgeGatewayRoute] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeGatewayPolicyUpdateRequest(APIModel):
    gateway_enabled: Optional[bool] = None
    default_provider_name: Optional[str] = None
    fallback_provider_name: Optional[str] = None
    strict_routing: Optional[bool] = None
    routes: Optional[list[RuntimeEdgeGatewayRoute]] = None
    notes: Optional[list[str]] = None


class RuntimeEdgeGatewayRouteStatus(APIModel):
    provider_name: str
    enabled: bool = True
    fallback_provider_name: str = "runtime_edge"
    resolved_provider_name: str = "runtime_edge"
    priority: int = 10
    route_ready: bool = False
    endpoint: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeGatewayProviderStatus(APIModel):
    provider_name: str
    provider_label: str
    enabled: bool = True
    fallback_provider_name: str = "runtime_edge"
    resolved_provider_name: str = "runtime_edge"
    priority: int = 10
    route_ready: bool = False
    strict_ready: bool = False
    endpoint: Optional[str] = None
    auth_header: str = "Authorization"
    auth_configured: bool = False
    fallback_reason: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeGatewayProviderStatusReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    gateway_enabled: bool = False
    provider_count: int = 0
    route_count: int = 0
    route_ready_count: int = 0
    strict_ready_count: int = 0
    gateway_ready: bool = False
    entries: list[RuntimeEdgeGatewayProviderStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class RuntimeEdgeGatewayReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    policy: RuntimeEdgeGatewayPolicy
    route_count: int = 0
    enabled_route_count: int = 0
    provider_count: int = 0
    route_ready_count: int = 0
    gateway_ready: bool = False
    routes: list[RuntimeEdgeGatewayRouteStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    gateway_publish: Optional["RuntimeEdgeGatewayPublishReport"] = None


class RuntimeEdgeGatewayHistoryEntry(APIModel):
    audit_id: str
    created_at: datetime
    actor: str
    project_id: Optional[str] = None
    gateway_enabled: bool = False
    strict_routing: bool = False
    route_count: int = 0
    route_ready_count: int = 0
    provider_count: int = 0
    latest_provider_name: Optional[str] = None
    latest_endpoint: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeGatewayHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    summary: "RuntimeEdgeHistorySummary" = Field(default_factory=lambda: RuntimeEdgeHistorySummary())
    gateway_ready_count: int = 0
    route_ready_count: int = 0
    latest_provider_name: Optional[str] = None
    latest_endpoint: Optional[str] = None
    latest_route_count: Optional[int] = None
    latest_route_ready_count: Optional[int] = None
    entries: list[RuntimeEdgeGatewayHistoryEntry] = Field(default_factory=list)


class RuntimeEdgeGatewayPublishReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    strict_routing: bool = False
    status: Literal["completed", "blocked", "failed"] = "completed"
    failure_code: Optional[str] = None
    retryable: bool = False
    gateway_endpoint: Optional[str] = None
    gateway_url: Optional[str] = None
    gateway_artifact_id: Optional[str] = None
    gateway_mode: Optional[str] = None
    auth_source: Optional[str] = None
    message: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeRolloutHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    summary: "RuntimeEdgeHistorySummary" = Field(default_factory=lambda: RuntimeEdgeHistorySummary())
    items: list[RuntimeEdgeRolloutExecutionReport] = Field(default_factory=list)


class RuntimeEdgeRolloutRemediationItem(APIModel):
    blocker_code: Literal["DUPLICATE_HOST", "STRICT_RUNTIME_NOT_READY", "CANARY_REQUIRED", "RUNTIME_EDGE_GATEWAY_PUBLISH_FAILED"] = "DUPLICATE_HOST"
    severity: Literal["blocking", "warning"] = "blocking"
    count: int = 0
    hosts: list[str] = Field(default_factory=list)
    project_ids: list[str] = Field(default_factory=list)
    recommendation: str


class RuntimeEdgeRolloutRemediationReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    strict_routes_only: bool = False
    project_id: Optional[str] = None
    blocker_count: int = 0
    blocking_count: int = 0
    warning_count: int = 0
    items: list[RuntimeEdgeRolloutRemediationItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeProbeRequest(APIModel):
    strict_routes_only: bool = False
    project_id: Optional[str] = None
    timeout_seconds: float = 3.0
    actor: str = "ui"
    note: Optional[str] = None


class RuntimeEdgeProbeItem(APIModel):
    project_id: str
    host: str
    strict_routes_only: bool = False
    health_url: str
    status: Literal["connected", "failed", "skipped"] = "skipped"
    http_status: Optional[int] = None
    latency_ms: int = 0
    failure_code: Optional[str] = None
    fallback_reason: Optional[str] = None
    retryable: bool = False
    auth_source: Optional[str] = None
    provenance: list[str] = Field(default_factory=list)
    message: Optional[str] = None


class RuntimeEdgeProbeReport(APIModel):
    probe_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    strict_routes_only: bool = False
    project_id: Optional[str] = None
    actor: str = "ui"
    note: Optional[str] = None
    total: int = 0
    connected: int = 0
    failed: int = 0
    skipped: int = 0
    items: list[RuntimeEdgeProbeItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RuntimeEdgeProbeHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    summary: "RuntimeEdgeHistorySummary" = Field(default_factory=lambda: RuntimeEdgeHistorySummary())
    items: list[RuntimeEdgeProbeReport] = Field(default_factory=list)


class ProjectRuntimeRouteHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: str
    total: int = 0
    runtime_ready_count: int = 0
    preview_only_count: int = 0
    entries: list[ProjectRun] = Field(default_factory=list)


class WorkspaceRuntimeRouteHistoryItem(APIModel):
    project_id: str
    project_name: str
    run_id: str
    task_id: Optional[str] = None
    trigger: str
    status: str
    started_at: datetime
    runtime_ready: bool = False
    runtime_summary: Optional[str] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    experiment_variant: str = "unassigned"
    localization_cluster: str = "unassigned"
    gateway_provider_name: str = "local"
    gateway_route_provider_name: Optional[str] = None
    gateway_route_fallback_provider_name: Optional[str] = None
    gateway_route_priority: Optional[int] = None
    gateway_ready: bool = False
    execution_mode: Optional[Literal["runtime", "preview", "blocked"]] = None
    execution_action: Optional[Literal["serve_runtime", "serve_preview", "block"]] = None
    execution_reason: Optional[str] = None
    execution_entrypoint: Optional[str] = None


class WorkspaceRuntimeRouteHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    runtime_ready_count: int = 0
    preview_only_count: int = 0
    items: list[WorkspaceRuntimeRouteHistoryItem] = Field(default_factory=list)


class WorkspaceRuntimeRouteHealthItem(APIModel):
    project_id: str
    project_name: str
    runtime_ready: bool = False
    runtime_summary: Optional[str] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    experiment_variant: str = "unassigned"
    localization_cluster: str = "unassigned"
    gateway_provider_name: str = "local"
    gateway_route_provider_name: Optional[str] = None
    gateway_route_fallback_provider_name: Optional[str] = None
    gateway_route_priority: Optional[int] = None
    gateway_ready: bool = False
    execution_mode: Optional[Literal["runtime", "preview", "blocked"]] = None
    execution_action: Optional[Literal["serve_runtime", "serve_preview", "block"]] = None
    execution_reason: Optional[str] = None
    execution_entrypoint: Optional[str] = None


class WorkspaceRuntimeRouteHealthReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    project_count: int = 0
    runtime_ready_count: int = 0
    preview_only_count: int = 0
    gateway_ready_count: int = 0
    strict_ready_count: int = 0
    runtime_ready_rate_percent: float = 0.0
    gateway_ready_rate_percent: float = 0.0
    ready_project_ids: list[str] = Field(default_factory=list)
    preview_only_project_ids: list[str] = Field(default_factory=list)
    items: list[WorkspaceRuntimeRouteHealthItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceTemplateMarketTemplate(APIModel):
    template_key: str
    enabled: bool = True
    template_surface: Literal["site", "content", "ad", "technical_seo", "ui"] = "content"
    target_locale: Optional[str] = None
    target_project_ids: list[str] = Field(default_factory=list)
    coverage_requirements: list[str] = Field(default_factory=list)
    template_source: str = "workspace"
    notes: list[str] = Field(default_factory=list)


class WorkspaceTemplateMarketPolicy(APIModel):
    market_enabled: bool = False
    strict_market: bool = False
    default_template_surface: Literal["site", "content", "ad", "technical_seo", "ui"] = "content"
    templates: list[WorkspaceTemplateMarketTemplate] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceTemplateMarketPolicyUpdateRequest(APIModel):
    market_enabled: Optional[bool] = None
    strict_market: Optional[bool] = None
    default_template_surface: Optional[Literal["site", "content", "ad", "technical_seo", "ui"]] = None
    templates: Optional[list[WorkspaceTemplateMarketTemplate]] = None
    notes: Optional[list[str]] = None


class WorkspaceTemplateMarketStatus(APIModel):
    template_key: str
    enabled: bool = True
    template_surface: Literal["site", "content", "ad", "technical_seo", "ui"] = "content"
    target_locale: Optional[str] = None
    target_project_count: int = 0
    coverage_requirement_count: int = 0
    coverage_ready: bool = False
    template_ready: bool = False
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceTemplateMarketReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    policy: WorkspaceTemplateMarketPolicy = Field(default_factory=WorkspaceTemplateMarketPolicy)
    template_count: int = 0
    enabled_template_count: int = 0
    ready_template_count: int = 0
    project_scope_count: int = 0
    workspace_ready: bool = False
    templates: list[WorkspaceTemplateMarketStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class ProjectSummary(APIModel):
    project_id: str
    name: str
    url: str
    site_class: SiteClass
    latest_stage: WorkflowStage
    risk_score: int
    deployment_mode: Optional[DeploymentMode] = None
    recommendation: str
    updated_at: datetime
    connection_health: ConnectionHealth = ConnectionHealth.unknown
    last_sync_at: Optional[datetime] = None
    next_sync_at: Optional[datetime] = None
    run_count: int = 0


class TaskSummary(APIModel):
    task_id: str
    project_id: str
    status: WorkflowStage
    risk_score: int
    approval_status: ApprovalStatus
    site_class: SiteClass
    updated_at: datetime


class WorkflowBundle(APIModel):
    project: ProjectSummary
    task: TaskSummary
    site_profile: SiteProfile
    ingestion_report: Optional[IngestionReport] = None
    experiment_assignment: Optional[WorkspaceExperimentAssignmentReport] = None
    localization_assignment: Optional[WorkspaceLocalizationAssignmentReport] = None
    runtime_route: Optional[RuntimeRouteReport] = None
    opportunity_set: OpportunitySet
    plan: Plan
    ux_review: UXReview
    approval_request: ApprovalRequest
    preview: PreviewArtifact
    deployment: Optional[DeploymentRecord] = None
    metric_snapshot: Optional[MetricSnapshot] = None
    rollback_bundle: Optional[RollbackBundle] = None


class DashboardSnapshot(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    projects: list[ProjectSummary] = Field(default_factory=list)
    tasks: list[TaskSummary] = Field(default_factory=list)
    approvals: list[ApprovalRequest] = Field(default_factory=list)
    skills: list[SkillDefinition] = Field(default_factory=list)
    policy: WorkspacePolicy = Field(default_factory=WorkspacePolicy)
    market_evidence_providers: Optional[MarketEvidenceProviderStatusReport] = None
    billing_gateway_providers: Optional[WorkspaceBillingSettlementGatewayProviderStatusReport] = None
    model_gateway_providers: Optional[WorkspaceModelGatewayProviderStatusReport] = None
    runtime_edge_gateway_providers: Optional[RuntimeEdgeGatewayProviderStatusReport] = None
    visual_farm_gateway_providers: Optional[VisualFarmGatewayProviderStatusReport] = None
    connectors_health: Optional[WorkspaceConnectorsHealthReport] = None
    market_evidence_health: Optional[WorkspaceMarketEvidenceHealthReport] = None
    cruise_health: Optional[WorkspaceCruiseHealthReport] = None
    runtime_route_health: Optional[WorkspaceRuntimeRouteHealthReport] = None
    runtime_route_history: Optional[WorkspaceRuntimeRouteHistoryReport] = None
    runtime_edge_deployment_history: Optional[RuntimeEdgeDeploymentHistoryReport] = None
    runtime_edge_deployment_batch_history: Optional[RuntimeEdgeDeploymentBatchHistoryReport] = None
    runtime_ingress_batch_history: Optional[RuntimeIngressBundleBatchHistoryReport] = None
    runtime_ingress_batch_health: Optional[RuntimeIngressBundleBatchHealthReport] = None
    visual_farm_deployment_batch_history: Optional["VisualFarmDeploymentBatchHistoryReport"] = None
    crawl_diagnostics_history: Optional[CrawlDiagnosticsHistoryReport] = None
    ad_audit_history: Optional[WorkspaceAdAuditHistoryReport] = None
    skill_regression: Optional[SkillRegressionReport] = None
    billing_settlement_history: Optional[WorkspaceBillingSettlementExecutionHistoryReport] = None
    billing_gateway_history: Optional[WorkspaceBillingSettlementGatewayHistoryReport] = None
    model_gateway_history: Optional[WorkspaceModelGatewayHistoryReport] = None
    alerts: list[str] = Field(default_factory=list)


class ConnectorFailureEntry(APIModel):
    failure_code: str
    category: Literal["auth", "permission", "rate_limit", "network", "validation", "config", "unavailable", "other"]
    count: int
    providers: list[str] = Field(default_factory=list)
    affected_projects: int = 0
    project_ids: list[str] = Field(default_factory=list)
    last_seen_at: datetime = Field(default_factory=utcnow)


class ConnectorFailureReport(APIModel):
    report_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total_failures: int = 0
    active_project_count: int = 0
    entries: list[ConnectorFailureEntry] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ProjectDetail(APIModel):
    project: ProjectSummary
    workflow: WorkflowBundle
    state: ProjectState
    connections: list[ProjectConnection] = Field(default_factory=list)
    connectors_health: Optional[ConnectorsHealthResult] = None
    market_evidence_health: Optional[MarketEvidenceHealthReport] = None
    cruise_health: Optional[ProjectCruiseHealthReport] = None
    billing: Optional[WorkspaceBillingReport] = None
    billing_gateway_history: Optional[WorkspaceBillingSettlementGatewayHistoryReport] = None
    model_gateway: Optional[WorkspaceModelGatewayReport] = None
    model_gateway_history: Optional[WorkspaceModelGatewayHistoryReport] = None
    runtime_edge_config: Optional[ProjectRuntimeEdgeConfig] = None
    alerts: list[str] = Field(default_factory=list)
    alert_history: Optional[AlertHistoryReport] = None
    alert_deliveries: Optional[AlertDeliveryReport] = None
    alert_emit_status: Optional[AlertEmitStatusReport] = None
    connector_history: Optional[ProjectConnectionHistoryReport] = None
    connector_failures: Optional[ConnectorFailureReport] = None
    experiment_assignment: Optional[WorkspaceExperimentAssignmentReport] = None
    localization_assignment: Optional[WorkspaceLocalizationAssignmentReport] = None
    runtime_route: Optional[RuntimeRouteReport] = None
    runtime_route_history: Optional[ProjectRuntimeRouteHistoryReport] = None
    runtime_edge_deployment_history: Optional[RuntimeEdgeDeploymentHistoryReport] = None
    runtime_edge_deployment_batch_history: Optional[RuntimeEdgeDeploymentBatchHistoryReport] = None
    runtime_ingress_batch_history: Optional[RuntimeIngressBundleBatchHistoryReport] = None
    runtime_ingress_batch_health: Optional[RuntimeIngressBundleBatchHealthReport] = None
    visual_regression_runs: Optional[VisualRegressionRunsReport] = None
    visual_regression_health: Optional[VisualRegressionHealthReport] = None
    visual_regression_remediation: Optional[VisualRegressionRemediationReport] = None
    visual_farm_status: Optional[VisualFarmStatusReport] = None
    visual_farm_probe_history: Optional[VisualFarmProbeHistoryReport] = None
    visual_farm_deployment_batch_history: Optional["VisualFarmDeploymentBatchHistoryReport"] = None
    crawl_diagnostics_history: Optional[CrawlDiagnosticsHistoryReport] = None
    deployment_history: list[DeploymentHistoryEntry] = Field(default_factory=list)
    rollback_history: list[RollbackHistoryEntry] = Field(default_factory=list)
    runs: list[ProjectRun] = Field(default_factory=list)
    audits: list[dict[str, Any]] = Field(default_factory=list)
    market_evidence: Optional["MarketEvidenceReport"] = None
    business_classifier: Optional["BusinessClassifierReport"] = None
    style_extraction: Optional["StyleExtractionReport"] = None
    content_strategy: Optional["ContentStrategyReport"] = None
    ad_audit: Optional["AdAuditReport"] = None
    adaptive_components: Optional["AdaptiveComponentReport"] = None
    technical_seo: Optional["TechnicalSeoReport"] = None
    technical_seo_patch: Optional["TechnicalSeoPatchReport"] = None


class RegressionCaseResult(APIModel):
    sample_id: str
    name: str
    site_class: SiteClass
    risk_score: int
    deployment_mode: DeploymentMode
    connection_health: ConnectionHealth
    seo_preview_ready: bool
    ad_recommendation: str
    ad_allowed: bool
    passed: bool
    notes: list[str] = Field(default_factory=list)


class RegressionReport(APIModel):
    report_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    sample_count: int
    seo_preview_count: int
    ad_recommendation_count: int
    no_ad_count: int
    pass_count: int
    fail_count: int
    cases: list[RegressionCaseResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AcceptanceGateResult(APIModel):
    gate_id: str
    name: str
    passed: bool
    expected: str
    actual: str
    quick_action_path: Optional[str] = None
    quick_action_label: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class AcceptanceProviderEvidence(APIModel):
    provider: str
    project_id: str
    project_name: str
    provider_mode: Literal["real", "fallback", "unconfigured"]
    evidence_ref: Optional[str] = None
    evidence_label: Optional[str] = None
    evidence_at: Optional[datetime] = None


class AcceptanceReport(APIModel):
    report_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    regression: RegressionReport
    strict_providers_enabled: bool = False
    billing_gateway_ready: bool = False
    billing_gateway_route_ready_count: int = 0
    billing_gateway_route_count: int = 0
    prompt_registry_count: int
    active_prompt_count: int
    rollback_ready_count: int
    total_project_count: int
    read_real_evidence_count: int = 0
    write_real_evidence_count: int = 0
    read_real_provider_count: int = 0
    write_real_provider_count: int = 0
    read_real_providers: list[str] = Field(default_factory=list)
    write_real_providers: list[str] = Field(default_factory=list)
    read_real_evidence: list[AcceptanceProviderEvidence] = Field(default_factory=list)
    write_real_evidence: list[AcceptanceProviderEvidence] = Field(default_factory=list)
    market_evidence_connected_count: int = 0
    market_evidence_synthetic_count: int = 0
    market_evidence_failed_count: int = 0
    market_evidence_fresh_count: int = 0
    market_evidence_last_fetched_at: Optional[datetime] = None
    gates: list[AcceptanceGateResult] = Field(default_factory=list)
    passed: bool
    notes: list[str] = Field(default_factory=list)


class AcceptanceHistoryEntry(APIModel):
    report_id: str
    generated_at: datetime
    passed: bool
    failed_gate_ids: list[str] = Field(default_factory=list)
    failed_gate_count: int = 0
    report: AcceptanceReport


class AcceptanceHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    total: int = 0
    limit: int = 20
    entries: list[AcceptanceHistoryEntry] = Field(default_factory=list)


class ProductBenchmarkReference(APIModel):
    name: str
    category: Literal["seo_monitoring", "visual_monitoring", "edge_runtime", "ads_reporting", "settlement", "experimentation"]
    source_url: str
    observed_capabilities: list[str] = Field(default_factory=list)


class ProductCapabilityBenchmark(APIModel):
    capability_id: str
    title: str
    current_status: Literal["production_ready", "operational", "partial", "missing"]
    maturity_score: int = 0
    comparable_products: list[str] = Field(default_factory=list)
    implemented_evidence: list[str] = Field(default_factory=list)
    remaining_gaps: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    priority: Literal["p0", "p1", "p2", "p3"] = "p2"


class ProductBenchmarkReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    reference_count: int = 0
    capability_count: int = 0
    production_ready_count: int = 0
    partial_count: int = 0
    missing_count: int = 0
    average_maturity_score: float = 0.0
    references: list[ProductBenchmarkReference] = Field(default_factory=list)
    capabilities: list[ProductCapabilityBenchmark] = Field(default_factory=list)
    recommended_next_capability_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RemainingTaskItem(APIModel):
    task_id: str
    title: str
    priority: Literal["p0", "p1", "p2", "p3"] = "p2"
    source_capability_id: str
    status: Literal["blocked", "planned"] = "planned"
    blocking: bool = False
    acceptance_gate_ids: list[str] = Field(default_factory=list)
    remaining_gaps: list[str] = Field(default_factory=list)
    next_action: Optional[str] = None
    quick_action_path: Optional[str] = None
    quick_action_label: Optional[str] = None


class RemainingTaskReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    blocking_count: int = 0
    p0_count: int = 0
    p1_count: int = 0
    p2_count: int = 0
    p3_count: int = 0
    items: list[RemainingTaskItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RemainingTaskBoardGroup(APIModel):
    group_id: Literal["provider", "visual", "runtime", "ads", "billing", "experiment", "other"]
    title: str
    total: int = 0
    blocking_count: int = 0
    p0_count: int = 0
    p1_count: int = 0
    p2_count: int = 0
    p3_count: int = 0
    task_ids: list[str] = Field(default_factory=list)


class RemainingTaskBoardReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    blocking_count: int = 0
    groups: list[RemainingTaskBoardGroup] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RegressionSample(APIModel):
    sample_id: str
    name: str
    intake: SiteIntake
    expected_seo_preview: bool
    expected_ad_allowed: bool
    expected_risk_band: Literal["low", "medium", "high"]
    notes: list[str] = Field(default_factory=list)


class RegressionSampleSet(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    sample_count: int
    samples: list[RegressionSample] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PromptVersion(APIModel):
    prompt_id: str
    role: Literal["sniffer", "query", "strategist", "ux", "policy", "coordinator"]
    name: str
    version: str
    status: Literal["active", "draft", "archived"]
    owner: str
    summary: str
    checksum: str
    last_reviewed_at: datetime
    used_by: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PromptRegistry(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    versions: list[PromptVersion] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PromptRegistryUpdateRequest(APIModel):
    versions: list[PromptVersion] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PromptVersionUpsertRequest(APIModel):
    version: PromptVersion


class PromptVersionActivateRequest(APIModel):
    version: str


class VisualRegressionCase(APIModel):
    sample_id: str
    name: str
    page_url: str
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    workflow_task_id: Optional[str] = None
    deployment_artifact_ref: Optional[str] = None
    deployment_record_id: Optional[str] = None
    baseline_label: str
    preview_label: str
    expected_max_diff_percent: float
    actual_diff_percent: float
    artifact_ref: str
    task_id: str
    execution_mode: Literal["playwright", "manifest"] = "manifest"
    baseline_artifact_ref: Optional[str] = None
    preview_artifact_ref: Optional[str] = None
    diff_artifact_ref: Optional[str] = None
    diff_method: Optional[Literal["pixel-rgba", "byte-fallback"]] = None
    mismatch_pixels: Optional[int] = None
    compared_pixels: Optional[int] = None
    mismatch_ratio: Optional[float] = None
    mean_channel_delta: Optional[float] = None
    max_channel_delta: Optional[int] = None
    threshold_delta: Optional[int] = None
    threshold_exceeded_pixels: Optional[int] = None
    threshold_exceeded_ratio: Optional[float] = None
    provider_status: Optional[Literal["connected", "failed", "not_configured", "fallback"]] = None
    provider_failure_code: Optional[str] = None
    visual_farm_provider: Optional[str] = None
    visual_farm_run_id: Optional[str] = None
    visual_farm_endpoint: Optional[str] = None
    visual_farm_latency_ms: Optional[int] = None
    visual_farm_auth_source: Optional[str] = None
    visual_farm_strict_blocked: bool = False
    screenshot_count: Optional[int] = None
    provider_attempts: list[dict[str, Any]] = Field(default_factory=list)
    cta_preserved: bool
    layout_shift_risk: Literal["low", "medium", "high"]
    passed: bool
    notes: list[str] = Field(default_factory=list)


class VisualRegressionReport(APIModel):
    report_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    sample_count: int
    pass_count: int
    fail_count: int
    average_diff_percent: float
    cases: list[VisualRegressionCase] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VisualRegressionRun(APIModel):
    run_id: str
    executed_at: datetime = Field(default_factory=utcnow)
    sample_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    average_diff_percent: float = 0.0
    strict_mode: bool = False
    farm_provider: Optional[str] = None
    connected_case_count: int = 0
    strict_blocked_case_count: int = 0
    failed_case_count: int = 0
    fallback_case_count: int = 0
    not_configured_case_count: int = 0
    configured_endpoint_count: int = 0
    configured_endpoints: list[str] = Field(default_factory=list)
    attempted_endpoint_count: int = 0
    attempted_endpoints: list[str] = Field(default_factory=list)
    failed_endpoints: list[str] = Field(default_factory=list)
    provider_attempt_count: int = 0
    average_farm_latency_ms: Optional[int] = None
    project_ids: list[str] = Field(default_factory=list)
    workflow_task_ids: list[str] = Field(default_factory=list)
    deployment_artifact_refs: list[str] = Field(default_factory=list)
    deployment_record_ids: list[str] = Field(default_factory=list)
    cases: list[VisualRegressionCase] = Field(default_factory=list)


class VisualRegressionRunsReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    runs: list[VisualRegressionRun] = Field(default_factory=list)


class VisualRegressionRunExecuteRequest(APIModel):
    strict_mode: Optional[bool] = None
    project_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    max_cases: int = 0


class VisualRegressionRunEnqueueResult(APIModel):
    enqueued: bool
    skipped_duplicate: bool = False
    job_id: str
    stage: str = "visual_regression"
    strict_mode: Optional[bool] = None
    project_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    max_cases: int = 0
    message: str = ""


class VisualRegressionHealthReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    strict_mode: bool = False
    configured_endpoint_count: int = 0
    configured_endpoints: list[str] = Field(default_factory=list)
    run_count: int = 0
    last_run_id: Optional[str] = None
    last_run_executed_at: Optional[datetime] = None
    last_run_connected_case_count: int = 0
    last_run_failed_case_count: int = 0
    last_run_fallback_case_count: int = 0
    last_run_not_configured_case_count: int = 0
    last_run_strict_blocked_case_count: int = 0
    last_run_attempted_endpoint_count: int = 0
    last_run_failed_endpoints: list[str] = Field(default_factory=list)
    failure_buckets: list["VisualRegressionFailureBucket"] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VisualFarmStatusReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    strict_mode: bool = False
    configured_endpoint_count: int = 0
    configured_endpoints: list[str] = Field(default_factory=list)
    access_token_configured: bool = False
    auth_source: str = "none"
    timeout_ms: int = 0
    run_count: int = 0
    last_run_id: Optional[str] = None
    last_run_executed_at: Optional[datetime] = None
    last_run_connected_case_count: int = 0
    last_run_failed_case_count: int = 0
    last_run_fallback_case_count: int = 0
    last_run_not_configured_case_count: int = 0
    last_run_strict_blocked_case_count: int = 0
    probe_freshness_minutes: int = 0
    last_probe_executed_at: Optional[datetime] = None
    last_probe_connected_count: int = 0
    last_probe_failed_count: int = 0
    last_probe_blocking_count: int = 0
    last_probe_recoverable_count: int = 0
    probe_fresh: bool = False
    probe_stale: bool = True
    strict_publish_ready: bool = False
    failure_buckets: list["VisualRegressionFailureBucket"] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VisualFarmEndpointProbe(APIModel):
    endpoint: str
    status: Literal["connected", "failed", "not_configured"]
    latency_ms: Optional[int] = None
    http_status: Optional[int] = None
    failure_code: Optional[str] = None
    retryable: bool = False
    blocking: bool = False
    alert_severity: Literal["critical", "warning", "info"] = "info"
    message: Optional[str] = None


class VisualFarmProbeReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    strict_mode: bool = False
    project_id: Optional[str] = None
    configured_endpoint_count: int = 0
    probed_endpoint_count: int = 0
    connected_count: int = 0
    failed_count: int = 0
    not_configured_count: int = 0
    blocking_count: int = 0
    recoverable_count: int = 0
    access_token_configured: bool = False
    auth_source: str = "none"
    timeout_ms: int = 0
    probes: list[VisualFarmEndpointProbe] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VisualFarmProbeEnqueueResult(APIModel):
    enqueued: bool
    skipped_duplicate: bool = False
    job_id: str
    stage: str = "visual_farm_probe"
    message: str = ""


class VisualFarmDeploymentRequest(APIModel):
    strict_mode: Optional[bool] = None
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    actor: str = "ui"
    dry_run: bool = True
    note: Optional[str] = None


class VisualFarmDeploymentReport(APIModel):
    deployment_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    strict_mode: bool = False
    dry_run: bool = True
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    actor: str = "ui"
    note: Optional[str] = None
    status: Literal["planned", "blocked", "executed"] = "planned"
    provider_endpoint: Optional[str] = None
    provider_url: Optional[str] = None
    provider_artifact_id: Optional[str] = None
    failure_code: Optional[str] = None
    retryable: bool = False
    message: Optional[str] = None
    manifest_path: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class VisualFarmDeploymentBatchRequest(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    strict_mode: Optional[bool] = None
    dry_run: bool = True
    actor: str = "ui"
    note: Optional[str] = None


class VisualFarmDeploymentBatchReport(APIModel):
    batch_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    strict_mode: bool = False
    dry_run: bool = True
    actor: str = "ui"
    note: Optional[str] = None
    total_count: int = 0
    executed_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    items: list[VisualFarmDeploymentReport] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VisualFarmDeploymentBatchEnqueueResult(APIModel):
    enqueued: bool
    skipped_duplicate: bool = False
    job_id: str
    stage: str = "visual_farm_deployment_batch"
    strict_mode: bool = False
    dry_run: bool = True
    project_ids: list[str] = Field(default_factory=list)
    message: str = ""


class VisualFarmDeploymentBatchHistoryEntry(APIModel):
    audit_id: str
    created_at: datetime
    actor: str
    batch_id: str
    strict_mode: bool = False
    dry_run: bool = True
    total_count: int = 0
    executed_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    project_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VisualFarmHistorySummary(APIModel):
    total_count: int = 0
    strict_mode_count: int = 0
    connected_count: int = 0
    failed_count: int = 0
    blocking_count: int = 0
    recoverable_count: int = 0
    executed_count: int = 0
    blocked_count: int = 0
    planned_count: int = 0
    dry_run_count: int = 0


class VisualFarmDeploymentBatchHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    summary: VisualFarmHistorySummary = Field(default_factory=VisualFarmHistorySummary)
    executed_count: int = 0
    blocked_count: int = 0
    failed_count: int = 0
    entries: list[VisualFarmDeploymentBatchHistoryEntry] = Field(default_factory=list)


class VisualFarmDeploymentHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    summary: VisualFarmHistorySummary = Field(default_factory=VisualFarmHistorySummary)
    executed_count: int = 0
    blocked_count: int = 0
    planned_count: int = 0
    items: list[VisualFarmDeploymentReport] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VisualFarmGatewayPublishReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    strict_routing: bool = False
    status: Literal["completed", "blocked", "failed"] = "completed"
    failure_code: Optional[str] = None
    retryable: bool = False
    gateway_endpoint: Optional[str] = None
    gateway_url: Optional[str] = None
    gateway_artifact_id: Optional[str] = None
    gateway_mode: Optional[str] = None
    auth_source: Optional[str] = None
    message: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class VisualFarmGatewayRoute(APIModel):
    provider_name: str = "visual_farm"
    enabled: bool = True
    fallback_provider_name: str = "visual_farm"
    priority: int = 10
    endpoint: str = ""
    access_token: str = ""
    auth_header: str = "Authorization"
    notes: list[str] = Field(default_factory=list)


class VisualFarmGatewayPolicy(APIModel):
    gateway_enabled: bool = False
    default_provider_name: str = "visual_farm"
    fallback_provider_name: str = "visual_farm"
    strict_routing: bool = False
    routes: list[VisualFarmGatewayRoute] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VisualFarmGatewayPolicyUpdateRequest(APIModel):
    gateway_enabled: Optional[bool] = None
    default_provider_name: Optional[str] = None
    fallback_provider_name: Optional[str] = None
    strict_routing: Optional[bool] = None
    routes: Optional[list[VisualFarmGatewayRoute]] = None
    notes: Optional[list[str]] = None


class VisualFarmGatewayRouteStatus(APIModel):
    provider_name: str
    enabled: bool = True
    fallback_provider_name: str = "visual_farm"
    resolved_provider_name: str = "visual_farm"
    priority: int = 10
    route_ready: bool = False
    endpoint: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class VisualFarmGatewayProviderStatus(APIModel):
    provider_name: str
    provider_label: str
    enabled: bool = True
    fallback_provider_name: str = "visual_farm"
    resolved_provider_name: str = "visual_farm"
    priority: int = 10
    route_ready: bool = False
    strict_ready: bool = False
    endpoint: Optional[str] = None
    auth_header: str = "Authorization"
    auth_configured: bool = False
    fallback_reason: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class VisualFarmGatewayProviderStatusReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    gateway_enabled: bool = False
    provider_count: int = 0
    route_count: int = 0
    route_ready_count: int = 0
    strict_ready_count: int = 0
    gateway_ready: bool = False
    entries: list[VisualFarmGatewayProviderStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class VisualFarmGatewayReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    policy: VisualFarmGatewayPolicy
    route_count: int = 0
    enabled_route_count: int = 0
    provider_count: int = 0
    route_ready_count: int = 0
    gateway_ready: bool = False
    routes: list[VisualFarmGatewayRouteStatus] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    gateway_publish: Optional["VisualFarmGatewayPublishReport"] = None


class VisualFarmGatewayExportReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    gateway_enabled: bool = False
    strict_routing: bool = False
    gateway_ready: bool = False
    route_count: int = 0
    provider_count: int = 0
    endpoint_count: int = 0
    endpoint: Optional[str] = None
    auth_header: str = "Authorization"
    auth_source: str = "none"
    nginx_snippet: str
    caddyfile_fragment: str
    haproxy_conf: str = ""
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class VisualFarmGatewayHistoryEntry(APIModel):
    audit_id: str
    created_at: datetime
    actor: str
    project_id: Optional[str] = None
    gateway_enabled: bool = False
    strict_routing: bool = False
    route_count: int = 0
    route_ready_count: int = 0
    provider_count: int = 0
    latest_provider_name: Optional[str] = None
    latest_endpoint: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class VisualFarmGatewayHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    gateway_ready_count: int = 0
    route_ready_count: int = 0
    latest_provider_name: Optional[str] = None
    latest_endpoint: Optional[str] = None
    latest_route_count: Optional[int] = None
    latest_route_ready_count: Optional[int] = None
    entries: list[VisualFarmGatewayHistoryEntry] = Field(default_factory=list)


class VisualFarmProbeHistoryEntry(APIModel):
    audit_id: str
    actor: str
    created_at: datetime
    strict_mode: bool = False
    project_id: Optional[str] = None
    configured_endpoint_count: int = 0
    probed_endpoint_count: int = 0
    connected_count: int = 0
    failed_count: int = 0
    not_configured_count: int = 0
    blocking_count: int = 0
    recoverable_count: int = 0
    access_token_configured: bool = False
    auth_source: str = "none"
    timeout_ms: int = 0
    probes: list[VisualFarmEndpointProbe] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    span_id: Optional[str] = None
    trace_id: Optional[str] = None


class VisualFarmProbeHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    strict_mode: Optional[bool] = None
    summary: VisualFarmHistorySummary = Field(default_factory=VisualFarmHistorySummary)
    entries: list[VisualFarmProbeHistoryEntry] = Field(default_factory=list)


class VisualRegressionFailureBucket(APIModel):
    category: str
    count: int = 0
    retryable: bool = False
    failure_codes: list[str] = Field(default_factory=list)
    sample_ids: list[str] = Field(default_factory=list)
    suggested_action: str = ""
    quick_action_path: Optional[str] = None


class SkillRegressionCase(APIModel):
    skill_id: str
    suite: str
    name: str
    destructive: bool
    required_approval: bool
    rollback_supported: bool
    observability_ready: bool
    failure_contract_present: bool
    passed: bool
    notes: list[str] = Field(default_factory=list)


class SkillRegressionReport(APIModel):
    report_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    sample_count: int
    pass_count: int
    fail_count: int
    destructive_count: int
    rollback_supported_count: int
    cases: list[SkillRegressionCase] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ContentCluster(APIModel):
    title: str
    intent: Literal["informational", "commercial", "transactional"]
    primary_keyword: str
    secondary_keywords: list[str] = Field(default_factory=list)
    content_type: str
    target_url: str
    word_count: int
    priority: int
    internal_links: list[str] = Field(default_factory=list)
    next_step: str


class ContentCalendarEntry(APIModel):
    week: int
    topic: str
    target_keyword: str
    content_type: str
    word_count: int
    internal_link_targets: list[str] = Field(default_factory=list)
    priority: int


class ContentStrategyReport(APIModel):
    report_id: str
    project_id: str
    pillar_page: str
    pillar_keyword: str
    pillar_intent: Literal["informational", "commercial", "transactional"]
    topic_clusters: list[ContentCluster] = Field(default_factory=list)
    calendar: list[ContentCalendarEntry] = Field(default_factory=list)
    internal_link_blueprint: list[str] = Field(default_factory=list)
    market_signals: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AdSlotRecommendation(APIModel):
    page_url: str
    slot_name: str
    placement: str
    reason: str
    risk_score: int
    allowed: bool
    evidence: list[str] = Field(default_factory=list)
    negative_conditions: list[str] = Field(default_factory=list)


class AdSlotAuditPageFinding(APIModel):
    page_url: str
    template: str
    slot_name: str
    placement: str
    allowed: bool
    risk_score: int
    reason: str
    cta_distance: int
    layout_risk: Literal["low", "medium", "high"]
    rollback_supported: bool
    evidence: list[str] = Field(default_factory=list)


class AdAuditReport(APIModel):
    report_id: str
    project_id: str
    ad_allowed: bool
    reason: str
    ad_connector_status: Optional[ConnectorStatus] = None
    ad_provider_family: Optional[str] = None
    ad_provider_name: Optional[str] = None
    ad_provider_ref: Optional[str] = None
    ad_inventory_status: Optional[str] = None
    ad_impressions_daily: Optional[int] = None
    ad_clicks_daily: Optional[int] = None
    ad_ctr: Optional[float] = None
    ad_fill_rate: Optional[float] = None
    ad_rpm: Optional[float] = None
    ad_revenue_estimate_daily: Optional[float] = None
    ad_revenue_estimate_monthly: Optional[float] = None
    ad_revenue_settled_daily: Optional[float] = None
    ad_revenue_settlement_window: Optional[str] = None
    ad_revenue_currency: Optional[str] = None
    ad_policy_tier: Optional[str] = None
    ad_payout_threshold: Optional[float] = None
    ad_geo_coverage: list[str] = Field(default_factory=list)
    ad_provider_program: Optional[str] = None
    ad_revenue_provenance: list[str] = Field(default_factory=list)
    strict_publish_eligible: bool = False
    fallback_reason: Optional[str] = None
    failure_code: Optional[str] = None
    provider_examples: list[str] = Field(default_factory=list)
    negative_conditions: list[str] = Field(default_factory=list)
    recommendations: list[AdSlotRecommendation] = Field(default_factory=list)
    page_findings: list[AdSlotAuditPageFinding] = Field(default_factory=list)
    template_coverage: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WorkspaceAdAuditHistoryItem(APIModel):
    report_id: str
    generated_at: datetime
    project_id: str
    project_name: str
    ad_allowed: bool
    reason: str
    ad_connector_status: Optional[ConnectorStatus] = None
    ad_provider_family: Optional[str] = None
    ad_provider_name: Optional[str] = None
    ad_provider_ref: Optional[str] = None
    ad_inventory_status: Optional[str] = None
    ad_revenue_estimate_daily: Optional[float] = None
    ad_revenue_estimate_monthly: Optional[float] = None
    ad_revenue_settled_daily: Optional[float] = None
    ad_revenue_currency: Optional[str] = None
    ad_policy_tier: Optional[str] = None
    strict_publish_eligible: bool = False
    fallback_reason: Optional[str] = None
    failure_code: Optional[str] = None
    provider_examples: list[str] = Field(default_factory=list)
    negative_conditions: list[str] = Field(default_factory=list)
    recommendation_count: int = 0


class WorkspaceAdAuditHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    project_count: int = 0
    allowed_count: int = 0
    blocked_count: int = 0
    strict_publish_eligible_count: int = 0
    connector_connected_count: int = 0
    latest_report_id: Optional[str] = None
    latest_project_id: Optional[str] = None
    latest_project_name: Optional[str] = None
    latest_ad_provider_family: Optional[str] = None
    latest_ad_provider_name: Optional[str] = None
    latest_ad_inventory_status: Optional[str] = None
    latest_ad_allowed: Optional[bool] = None
    latest_strict_publish_eligible: Optional[bool] = None
    latest_reason: Optional[str] = None
    latest_failure_code: Optional[str] = None
    latest_fallback_reason: Optional[str] = None
    latest_ad_revenue_estimate_daily: Optional[float] = None
    latest_ad_revenue_estimate_monthly: Optional[float] = None
    latest_ad_revenue_currency: Optional[str] = None
    latest_negative_condition_count: Optional[int] = None
    latest_recommendation_count: Optional[int] = None
    entries: list[WorkspaceAdAuditHistoryItem] = Field(default_factory=list)


class AdaptiveComponentSuggestion(APIModel):
    component_name: str
    preview_target: str
    placement: str
    behavior: str
    rollback_supported: bool
    skill_ids: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class AdaptiveComponentReport(APIModel):
    report_id: str
    project_id: str
    site_id: str
    suggestions: list[AdaptiveComponentSuggestion] = Field(default_factory=list)
    module_stack: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TechnicalSeoFinding(APIModel):
    area: str
    issue: str
    impact: Literal["high", "medium", "low"]
    evidence: list[str] = Field(default_factory=list)
    fix: str
    priority: int


class TechnicalSeoReport(APIModel):
    report_id: str
    project_id: str
    overall_health: Literal["healthy", "degraded", "critical"]
    crawlability: list[TechnicalSeoFinding] = Field(default_factory=list)
    on_page: list[TechnicalSeoFinding] = Field(default_factory=list)
    content: list[TechnicalSeoFinding] = Field(default_factory=list)
    performance: list[TechnicalSeoFinding] = Field(default_factory=list)
    action_plan: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TechnicalSeoPatchStep(APIModel):
    area: str
    field: str
    before: str
    after: str
    skill_id: str
    verified: bool = False
    rollback_supported: bool = True
    evidence: list[str] = Field(default_factory=list)


class TechnicalSeoPatchReport(APIModel):
    report_id: str
    project_id: str
    task_id: str
    verified_patch: bool
    strict_mode: bool
    patch_audit: dict[str, Any] = Field(default_factory=dict)
    steps: list[TechnicalSeoPatchStep] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ProjectCreateRequest(APIModel):
    name: str
    intake: SiteIntake


class ApprovalDecisionRequest(APIModel):
    decision: ApprovalStatus
    actor: str = "ui"
    note: str = ""


class DeploymentActionRequest(APIModel):
    actor: str = "ui"
    note: str = ""


class RollbackActionRequest(APIModel):
    actor: str = "ui"
    reason: str = "manual rollback"


class ProjectSyncRequest(APIModel):
    trigger: RunTrigger = RunTrigger.manual
    force: bool = False


class BulkProjectSyncRequest(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    trigger: RunTrigger = RunTrigger.manual
    force: bool = False


class BulkProjectSyncResult(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    processed_count: int = 0
    skipped_project_ids: list[str] = Field(default_factory=list)
    bundles: list["WorkflowBundle"] = Field(default_factory=list)


class ProjectConnectionsUpdateRequest(APIModel):
    auto_cruise_enabled: bool = False
    sync_interval_minutes: int = 60
    connections: list[ProjectConnection] = Field(default_factory=list)


class ProjectConnectionsRefreshRequest(APIModel):
    providers: list[ConnectorKind] = Field(default_factory=list)
    max_providers: int = 20


class ProjectConnectionsRefreshResult(APIModel):
    project_id: str
    refreshed_count: int = 0
    skipped_providers: list[ConnectorKind] = Field(default_factory=list)
    results: list["ConnectorRefreshResult"] = Field(default_factory=list)
    connection_health: ConnectionHealth = ConnectionHealth.unknown
    strict_mode: bool = False
    strict_blocked: bool = False
    strict_gap_count: int = 0
    strict_blockers: list[str] = Field(default_factory=list)


class ProjectConnectionsTestResult(APIModel):
    project_id: str
    tested_at: datetime = Field(default_factory=utcnow)
    connection_health: ConnectionHealth = ConnectionHealth.unknown
    connections: list[ProjectConnection] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    strict_mode: bool = False
    strict_blocked: bool = False
    strict_gap_count: int = 0
    strict_blockers: list[str] = Field(default_factory=list)


class ConnectorsHealthResult(APIModel):
    project_id: str
    checked_at: datetime = Field(default_factory=utcnow)
    connection_health: ConnectionHealth = ConnectionHealth.unknown
    total_connection_count: int = 0
    real_connection_count: int = 0
    fallback_connection_count: int = 0
    unconfigured_connection_count: int = 0
    strict_eligible_count: int = 0
    anti_bot_blocked_count: int = 0
    manual_intervention_required_count: int = 0
    read_real_last_evidence_at: Optional[datetime] = None
    write_real_last_evidence_at: Optional[datetime] = None
    connections: list[ProjectConnection] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class ConnectorProviderCoverageItem(APIModel):
    provider: ConnectorKind
    total_connection_count: int = 0
    affected_project_count: int = 0
    strict_ready_project_count: int = 0
    strict_ready_project_rate_percent: float = 0.0
    blocking_project_count: int = 0
    blocking_project_rate_percent: float = 0.0
    strict_gap_count: int = 0
    real_coverage_percent: float = 0.0
    strict_coverage_percent: float = 0.0
    blocking_rate_percent: float = 0.0
    affected_project_ids: list[str] = Field(default_factory=list)
    strict_ready_project_ids: list[str] = Field(default_factory=list)
    blocking_project_ids: list[str] = Field(default_factory=list)
    affected_projects: list[dict[str, str]] = Field(default_factory=list)
    strict_ready_projects: list[dict[str, str]] = Field(default_factory=list)
    blocking_projects: list[dict[str, str]] = Field(default_factory=list)
    primary_failure_category: Optional[Literal["auth", "permission", "rate_limit", "network", "validation", "config", "unavailable", "other"]] = None
    primary_failure_code: Optional[str] = None
    primary_blocking_reason: Optional[str] = None
    suggested_action_path: Optional[str] = None
    suggested_action_label: Optional[str] = None
    real_connection_count: int = 0
    fallback_connection_count: int = 0
    unconfigured_connection_count: int = 0
    strict_eligible_count: int = 0
    anti_bot_blocked_count: int = 0
    manual_intervention_required_count: int = 0


class ConnectorProjectHealthItem(APIModel):
    project_id: str
    name: str
    url: str
    checked_at: datetime = Field(default_factory=utcnow)
    connection_health: ConnectionHealth = ConnectionHealth.unknown
    total_connection_count: int = 0
    real_connection_count: int = 0
    fallback_connection_count: int = 0
    unconfigured_connection_count: int = 0
    strict_eligible_count: int = 0
    issue_count: int = 0
    issues: list[str] = Field(default_factory=list)


class WorkspaceConnectorsHealthReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    project_count: int = 0
    degraded_project_count: int = 0
    unavailable_project_count: int = 0
    total_connection_count: int = 0
    real_connection_count: int = 0
    fallback_connection_count: int = 0
    unconfigured_connection_count: int = 0
    strict_eligible_count: int = 0
    strict_gap_count: int = 0
    anti_bot_blocked_connection_count: int = 0
    anti_bot_manual_intervention_count: int = 0
    read_connection_count: int = 0
    read_real_connection_count: int = 0
    read_strict_eligible_count: int = 0
    read_real_coverage_percent: float = 0.0
    read_strict_coverage_percent: float = 0.0
    read_real_last_evidence_at: Optional[datetime] = None
    write_connection_count: int = 0
    write_real_connection_count: int = 0
    write_strict_eligible_count: int = 0
    write_real_coverage_percent: float = 0.0
    write_strict_coverage_percent: float = 0.0
    write_real_last_evidence_at: Optional[datetime] = None
    real_provider_count: int = 0
    real_provider_rate_percent: float = 0.0
    zero_real_provider_count: int = 0
    zero_real_provider_rate_percent: float = 0.0
    zero_real_providers: list[ConnectorKind] = Field(default_factory=list)
    zero_strict_provider_count: int = 0
    zero_strict_provider_rate_percent: float = 0.0
    zero_strict_providers: list[ConnectorKind] = Field(default_factory=list)
    strict_ready_provider_count: int = 0
    strict_ready_provider_rate_percent: float = 0.0
    strict_ready_providers: list[ConnectorKind] = Field(default_factory=list)
    partial_strict_provider_count: int = 0
    partial_strict_provider_rate_percent: float = 0.0
    partial_strict_providers: list[ConnectorKind] = Field(default_factory=list)
    fully_strict_provider_count: int = 0
    fully_strict_provider_rate_percent: float = 0.0
    fully_strict_providers: list[ConnectorKind] = Field(default_factory=list)
    provider_coverage: list[ConnectorProviderCoverageItem] = Field(default_factory=list)
    top_blocking_providers: list[ConnectorProviderCoverageItem] = Field(default_factory=list)
    top_strict_gap_providers: list[ConnectorProviderCoverageItem] = Field(default_factory=list)
    top_strict_ready_providers: list[ConnectorProviderCoverageItem] = Field(default_factory=list)
    projects: list[ConnectorProjectHealthItem] = Field(default_factory=list)


class ConnectorRefreshResult(APIModel):
    project_id: str
    provider: ConnectorKind
    status: ConnectorStatus
    checked_at: datetime = Field(default_factory=utcnow)
    connection_health: ConnectionHealth = ConnectionHealth.unknown
    issue: Optional[str] = None
    connection: ProjectConnection
    evidence: SourceEvidence


class ConnectorRetryRequest(APIModel):
    categories: list[Literal["auth", "permission", "rate_limit", "network", "validation", "config", "unavailable", "other"]] = Field(
        default_factory=lambda: ["network"]
    )
    project_ids: list[str] = Field(default_factory=list)
    providers: list[ConnectorKind] = Field(default_factory=list)
    retryable_only: bool = True
    max_retries: int = 50


class ConnectorRetryResult(APIModel):
    attempted: int = 0
    refreshed: int = 0
    skipped: int = 0
    failed: int = 0
    categories: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VisualRegressionRetryRequest(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    categories: list[Literal["auth", "permission", "rate_limit", "network", "validation", "config", "unavailable", "other"]] = Field(
        default_factory=lambda: ["network", "rate_limit", "unavailable"]
    )
    retryable_only: bool = True
    max_cases: int = 20


class VisualRegressionRetryResult(APIModel):
    attempted: int = 0
    rerun_passed: int = 0
    rerun_failed: int = 0
    skipped: int = 0
    categories: list[str] = Field(default_factory=list)
    run_id: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class VisualRegressionRetryHistoryEntry(APIModel):
    audit_id: str
    actor: str
    created_at: datetime
    attempted: int = 0
    rerun_passed: int = 0
    rerun_failed: int = 0
    skipped: int = 0
    categories: list[str] = Field(default_factory=list)
    project_id: Optional[str] = None
    project_ids: list[str] = Field(default_factory=list)
    run_id: Optional[str] = None
    notes: list[str] = Field(default_factory=list)
    span_id: Optional[str] = None


class VisualRegressionRetryHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    entries: list[VisualRegressionRetryHistoryEntry] = Field(default_factory=list)


class VisualRegressionRunHistoryEntry(APIModel):
    audit_id: str
    actor: str
    created_at: datetime
    strict_mode: bool = False
    project_id: Optional[str] = None
    project_ids: list[str] = Field(default_factory=list)
    max_cases: int = 0
    run_count: int = 0
    case_count: int = 0
    run_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class VisualRegressionRunHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    strict_mode: Optional[bool] = None
    entries: list[VisualRegressionRunHistoryEntry] = Field(default_factory=list)


class VisualRegressionRemediationItem(APIModel):
    remediation_id: str
    category: Literal["auth", "permission", "rate_limit", "network", "validation", "config", "unavailable", "other"]
    failure_code: str
    priority: Literal["p0", "p1", "p2", "p3"]
    action: str
    rationale: str
    blocking: bool = False
    affected_cases: int = 0
    affected_projects: int = 0
    project_ids: list[str] = Field(default_factory=list)
    quick_action_path: str
    quick_action_label: str
    retry_request_template: VisualRegressionRetryRequest


class VisualRegressionRemediationReport(APIModel):
    report_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    item_count: int = 0
    items: list[VisualRegressionRemediationItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ConnectorRetryHistoryEntry(APIModel):
    audit_id: str
    actor: str
    created_at: datetime
    attempted: int = 0
    refreshed: int = 0
    failed: int = 0
    skipped: int = 0
    categories: list[str] = Field(default_factory=list)
    project_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    span_id: Optional[str] = None
    alert_ids: list[str] = Field(default_factory=list)
    strict_mode: bool = False


class ConnectorRetryHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    strict_mode: bool = False
    entries: list[ConnectorRetryHistoryEntry] = Field(default_factory=list)


class BulkConnectorActionHistoryEntry(APIModel):
    audit_id: str
    action: str
    created_at: datetime
    actor: str = "system"
    provider_count: int = 0
    providers: list[str] = Field(default_factory=list)
    refreshed_count: int = 0
    skipped_project_count: int = 0
    project_scope_count: int = 0
    project_ids: list[str] = Field(default_factory=list)
    max_providers: int = 0
    span_id: Optional[str] = None
    trace_id: Optional[str] = None


class BulkConnectorActionHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    entries: list[BulkConnectorActionHistoryEntry] = Field(default_factory=list)


class ProjectConnectionHistoryEntry(APIModel):
    audit_id: str
    provider: str
    action: str
    status: str
    summary: str
    auth_source: Optional[str] = None
    failure_code: Optional[str] = None
    fallback_reason: Optional[str] = None
    latency_ms: Optional[int] = None
    retryable: bool = False
    provenance: list[str] = Field(default_factory=list)
    actor: str = "system"
    created_at: datetime


class ConnectionHistoryCount(APIModel):
    label: str
    count: int = 0


class ConnectionHistorySummary(APIModel):
    total_count: int = 0
    provider_counts: list[ConnectionHistoryCount] = Field(default_factory=list)
    status_counts: list[ConnectionHistoryCount] = Field(default_factory=list)
    action_counts: list[ConnectionHistoryCount] = Field(default_factory=list)
    failure_code_counts: list[ConnectionHistoryCount] = Field(default_factory=list)
    retryable_count: int = 0
    blocking_count: int = 0


class ProjectConnectionHistoryReport(APIModel):
    project_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    summary: ConnectionHistorySummary = Field(default_factory=ConnectionHistorySummary)
    entries: list[ProjectConnectionHistoryEntry] = Field(default_factory=list)


class WorkspaceConnectionHistoryEntry(ProjectConnectionHistoryEntry):
    project_id: str
    task_id: Optional[str] = None


class WorkspaceConnectionHistoryReport(APIModel):
    project_id: Optional[str] = None
    generated_at: datetime = Field(default_factory=utcnow)
    summary: ConnectionHistorySummary = Field(default_factory=ConnectionHistorySummary)
    entries: list[WorkspaceConnectionHistoryEntry] = Field(default_factory=list)


class ConnectorRemediationItem(APIModel):
    remediation_id: str
    failure_code: str
    category: Literal["auth", "permission", "rate_limit", "network", "validation", "config", "unavailable", "other"]
    priority: Literal["p0", "p1", "p2", "p3"]
    action: str
    rationale: str
    target: Literal["settings", "monitor", "project", "provider"]
    quick_action_path: str
    quick_action_label: str
    retry_after_minutes: Optional[int] = None
    affected_projects: int = 0
    project_ids: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    blocking: bool = False
    alert_severity: Literal["critical", "warning", "info"] = "info"


class ConnectorRemediationReport(APIModel):
    report_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    strict_mode: bool = False
    item_count: int = 0
    items: list[ConnectorRemediationItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AlertItem(APIModel):
    alert_id: str
    created_at: datetime = Field(default_factory=utcnow)
    category: Literal["auth", "config", "permission", "network", "rate_limit", "validation", "unavailable", "other"]
    severity: Literal["critical", "warning", "info"]
    blocking: bool
    failure_code: str
    provider: str
    project_count: int = 0
    project_ids: list[str] = Field(default_factory=list)
    summary: str
    remediation_path: Optional[str] = None
    rule_id: Optional[str] = None


class AlertReport(APIModel):
    report_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    blocking: list[AlertItem] = Field(default_factory=list)
    recoverable: list[AlertItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AlertHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    limit: int = 10
    offset: int = 0
    order: Literal["desc", "asc"] = "desc"
    cursor: Optional[str] = None
    next_cursor: Optional[str] = None
    has_more: bool = False
    snapshots: list[AlertReport] = Field(default_factory=list)


class AlertDeliveryEntry(APIModel):
    audit_id: str
    created_at: datetime = Field(default_factory=utcnow)
    status: Literal["sent", "failed"]
    route: str
    target: str
    channel: str
    report_id: Optional[str] = None
    project_ids: list[str] = Field(default_factory=list)
    blocking_count: int = 0
    recoverable_count: int = 0
    status_code: Optional[int] = None
    error: Optional[str] = None
    span_id: Optional[str] = None
    trace_id: Optional[str] = None


class AlertDeliveryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    sent: int = 0
    failed: int = 0
    entries: list[AlertDeliveryEntry] = Field(default_factory=list)


class AlertEmitStatusReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    cooldown_seconds: int = 0
    executed_count_24h: int = Field(default=0, alias="executedCount24h")
    suppressed_count_24h: int = Field(default=0, alias="suppressedCount24h")
    last_executed_at: Optional[datetime] = None
    last_suppressed_at: Optional[datetime] = None
    last_signature: Optional[str] = None
    notes: list[str] = Field(default_factory=list)


class AlertEmitHistoryEntry(APIModel):
    audit_id: str
    created_at: datetime = Field(default_factory=utcnow)
    status: Literal["executed", "suppressed"]
    signature: Optional[str] = None
    cooldown_seconds: int = 0
    blocking_count: int = 0
    recoverable_count: int = 0
    project_ids: list[str] = Field(default_factory=list)
    span_id: Optional[str] = None
    trace_id: Optional[str] = None


class AlertEmitHistoryReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    total: int = 0
    executed: int = 0
    suppressed: int = 0
    entries: list[AlertEmitHistoryEntry] = Field(default_factory=list)


class AlertPreset(APIModel):
    preset_id: str
    name: str
    description: str = ""
    project_ids: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    severities: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    blocking: Optional[bool] = None
    updated_at: datetime = Field(default_factory=utcnow)


class AlertPresetCollection(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    presets: list[AlertPreset] = Field(default_factory=list)


class AlertPresetUpdateRequest(APIModel):
    presets: list[AlertPreset] = Field(default_factory=list)


class AlertRule(APIModel):
    rule_id: str
    enabled: bool = True
    description: str = ""
    categories: list[str] = Field(default_factory=list)
    failure_codes: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    set_blocking: Optional[bool] = None
    set_severity: Optional[Literal["critical", "warning", "info"]] = None
    priority: int = 100
    updated_at: datetime = Field(default_factory=utcnow)


class AlertRuleCollection(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    rules: list[AlertRule] = Field(default_factory=list)


class AlertRuleUpdateRequest(APIModel):
    rules: list[AlertRule] = Field(default_factory=list)


class OnCallRoute(APIModel):
    route_id: str
    enabled: bool = True
    description: str = ""
    categories: list[str] = Field(default_factory=list)
    severities: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=list)
    blocking: Optional[bool] = None
    primary_channels: list[str] = Field(default_factory=list)
    escalation_channels: list[str] = Field(default_factory=list)
    escalation_after_minutes: int = 15
    rotation_members: list[str] = Field(default_factory=list)
    rotation_timezone: str = "UTC"
    rotation_handoff_hour: int = 9
    updated_at: datetime = Field(default_factory=utcnow)


class OnCallPolicyCollection(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    routes: list[OnCallRoute] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class OnCallPolicyUpdateRequest(APIModel):
    routes: list[OnCallRoute] = Field(default_factory=list)


class OnCallCoverageItem(APIModel):
    route_id: str
    enabled: bool = True
    rotation_enabled: bool = False
    rotation_timezone: str = "UTC"
    rotation_handoff_hour: int = 9
    member_count: int = 0
    current_member: Optional[str] = None
    next_member: Optional[str] = None
    next_handoff_at: Optional[datetime] = None


class OnCallCoverageReport(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    project_id: Optional[str] = None
    route_count: int = 0
    rotating_route_count: int = 0
    items: list[OnCallCoverageItem] = Field(default_factory=list)


class BulkConnectionsTestRequest(APIModel):
    project_ids: list[str] = Field(default_factory=list)


class BulkConnectionsTestResult(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    tested_count: int = 0
    skipped_project_ids: list[str] = Field(default_factory=list)
    results: list[ProjectConnectionsTestResult] = Field(default_factory=list)


class BulkProjectConnectionsRefreshRequest(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    providers: list[ConnectorKind] = Field(default_factory=list)
    max_providers: int = 20


class BulkProjectConnectionsRefreshResult(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    refreshed_count: int = 0
    skipped_project_ids: list[str] = Field(default_factory=list)
    results: list[ProjectConnectionsRefreshResult] = Field(default_factory=list)


class BulkConnectorRefreshRequest(APIModel):
    project_ids: list[str] = Field(default_factory=list)


class BulkConnectorRefreshResult(APIModel):
    provider: ConnectorKind
    project_ids: list[str] = Field(default_factory=list)
    refreshed_count: int = 0
    skipped_project_ids: list[str] = Field(default_factory=list)
    results: list[ConnectorRefreshResult] = Field(default_factory=list)


class BulkMarketEvidenceRefreshRequest(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    providers: list[ConnectorKind] = Field(default_factory=list)
    max_providers: int = 3


class BulkMarketEvidenceRefreshResult(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    provider_count: int = 0
    refreshed_count: int = 0
    skipped_project_count: int = 0
    provider_results: list[BulkConnectorRefreshResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class BulkStrictGapRefreshRequest(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    providers: list[ConnectorKind] = Field(default_factory=list)
    max_providers: int = 5


class BulkStrictGapRefreshResult(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    provider_count: int = 0
    refreshed_count: int = 0
    skipped_project_count: int = 0
    provider_results: list[BulkConnectorRefreshResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class BulkBlockingRefreshRequest(APIModel):
    project_ids: list[str] = Field(default_factory=list)
    providers: list[ConnectorKind] = Field(default_factory=list)
    max_providers: int = 5


class BulkBlockingRefreshResult(APIModel):
    generated_at: datetime = Field(default_factory=utcnow)
    provider_count: int = 0
    refreshed_count: int = 0
    skipped_project_count: int = 0
    provider_results: list[BulkConnectorRefreshResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SeedSite(APIModel):
    name: str
    intake: SiteIntake
    auto_run: bool = True


WorkspaceBillingSettlementExecutionReport.model_rebuild()
WorkspaceBillingSettlementGatewayProviderStatusReport.model_rebuild()
WorkspaceModelGatewayReport.model_rebuild()
WorkspaceModelGatewayProviderStatusReport.model_rebuild()
ProjectConnectionsRefreshResult.model_rebuild()
BulkProjectConnectionsRefreshResult.model_rebuild()
BulkMarketEvidenceRefreshResult.model_rebuild()
MarketEvidenceProviderStatusReport.model_rebuild()
RuntimeEdgeDeploymentBatchReport.model_rebuild()
RuntimeEdgeDeploymentHistoryReport.model_rebuild()
RuntimeEdgeGatewayReport.model_rebuild()
RuntimeEdgeGatewayHistoryReport.model_rebuild()
RuntimeEdgeGatewayProviderStatusReport.model_rebuild()
RuntimeIngressBundleReport.model_rebuild()
RuntimeIngressBundleBatchReport.model_rebuild()
RuntimeIngressConfigArtifactReport.model_rebuild()
RuntimeIngressConfigArtifactHistoryEntry.model_rebuild()
RuntimeIngressConfigArtifactHistoryReport.model_rebuild()
VisualFarmDeploymentBatchReport.model_rebuild()
VisualFarmDeploymentHistoryReport.model_rebuild()
VisualFarmGatewayReport.model_rebuild()
VisualFarmGatewayHistoryReport.model_rebuild()
VisualFarmGatewayProviderStatusReport.model_rebuild()
WorkspaceBillingSettlementExecutionBatchReport.model_rebuild()
