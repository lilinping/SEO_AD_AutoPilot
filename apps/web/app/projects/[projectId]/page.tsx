import { notFound } from "next/navigation";
import Link from "next/link";

import { getMarketEvidenceProviderStatusReport, getProjectConnectionEvidence, getProjectConnectionHistory, getProjectConnectorsHealth, getProjectCruiseHealth, getProjectDeploymentHistory, getProjectDetail, getProjectMarketEvidenceHealth, getProjectRollbackHistory, getProjectRuntimeRouteHistory, getProjectRuns, getRuntimeEdgeGatewayProviderStatusReport, getVisualFarmGatewayProviderStatusReport, getWorkspaceBillingGatewayProviderStatusReport, getWorkspaceBillingSettlementHistory, getWorkspaceModelGatewayProviderStatusReport } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { StatusPill, toneForStatus } from "@/components/StatusPill";
import { PreviewDiff } from "@/components/PreviewDiff";
import { StatCard } from "@/components/StatCard";
import { TaskActions } from "@/components/TaskActions";
import { WorkflowTimeline } from "@/components/WorkflowTimeline";
import { ProjectOperations } from "@/components/ProjectOperations";
import { ProjectConnectorRefreshAction } from "@/components/ProjectConnectorRefreshAction";
import { ProjectCruiseToggleAction } from "@/components/ProjectCruiseToggleAction";
import { formatNumber } from "@/lib/format";
import { getServerI18n } from "@/lib/i18n/server";

function stringifyAuditPayload(payload: unknown): string {
  if (payload == null) {
    return "null";
  }
  if (typeof payload === "string") {
    return payload;
  }
  if (payload instanceof Date) {
    return payload.toISOString();
  }
  try {
    return JSON.stringify(payload, null, 2);
  } catch {
    return String(payload);
  }
}

function formatAuditTime(value: unknown, locale: "zh" | "en"): string {
  if (value instanceof Date || typeof value === "string") {
    return formatDateTime(value, locale);
  }
  return "n/a";
}

function connectionTone(status: string) {
  if (status === "connected") return "good";
  if (status === "synthetic") return "warn";
  if (status === "missing_credentials" || status === "unavailable" || status === "error") return "danger";
  return "neutral";
}

function runTone(status: string) {
  if (status === "completed") return "good";
  if (status === "rolled_back") return "warn";
  if (status === "failed") return "danger";
  return "neutral";
}

function readDetailString(details: Record<string, unknown>, key: string, fallback: string): string {
  const value = details[key];
  return typeof value === "string" && value.trim() ? value : fallback;
}

function readDetailNumber(details: Record<string, unknown>, key: string): number | null {
  const value = details[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function readFirstQuery(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return value[0] ?? "";
  }
  return value ?? "";
}

export default async function ProjectPage({
  params,
  searchParams,
}: {
  params: { projectId: string };
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const { locale, t } = getServerI18n();
  const focusTaskIdRaw = searchParams?.taskId;
  const focusArtifactRefRaw = searchParams?.artifactRef;
  const focusTaskId = Array.isArray(focusTaskIdRaw) ? focusTaskIdRaw[0] ?? "" : focusTaskIdRaw ?? "";
  const focusArtifactRef = Array.isArray(focusArtifactRefRaw) ? focusArtifactRefRaw[0] ?? "" : focusArtifactRefRaw ?? "";
  const runTriggerRaw = readFirstQuery(searchParams?.runTrigger).trim();
  const runStatusRaw = readFirstQuery(searchParams?.runStatus).trim();
  const runLimitRaw = readFirstQuery(searchParams?.runLimit).trim();
  const runTrigger =
    runTriggerRaw === "manual" ||
    runTriggerRaw === "schedule" ||
    runTriggerRaw === "approval" ||
    runTriggerRaw === "deploy" ||
    runTriggerRaw === "monitor" ||
    runTriggerRaw === "rollback"
      ? runTriggerRaw
      : undefined;
  const runStatus =
    runStatusRaw === "queued" ||
    runStatusRaw === "running" ||
    runStatusRaw === "completed" ||
    runStatusRaw === "failed" ||
    runStatusRaw === "rolled_back"
      ? runStatusRaw
      : undefined;
  const runLimit = Math.max(1, Math.min(Number(runLimitRaw || "20"), 100));

  const [detail, projectConnectorsHealth, connectionHistory, connectionEvidence, deploymentHistory, rollbackHistory, runtimeRouteHistory, runs, billingSettlementHistory, runtimeEdgeGatewayProviders, visualFarmGatewayProviders, billingGatewayProviders, modelGatewayProviders, marketEvidenceProviders] = await Promise.all([
    getProjectDetail(params.projectId),
    getProjectConnectorsHealth(params.projectId),
    getProjectConnectionHistory(params.projectId, 10),
    getProjectConnectionEvidence(params.projectId),
    getProjectDeploymentHistory(params.projectId),
    getProjectRollbackHistory(params.projectId),
    getProjectRuntimeRouteHistory(params.projectId, 10),
    getProjectRuns(params.projectId, { trigger: runTrigger, status: runStatus, limit: runLimit }),
    getWorkspaceBillingSettlementHistory(10, params.projectId),
    getRuntimeEdgeGatewayProviderStatusReport(params.projectId),
    getVisualFarmGatewayProviderStatusReport(params.projectId),
    getWorkspaceBillingGatewayProviderStatusReport(),
    getWorkspaceModelGatewayProviderStatusReport(),
    getMarketEvidenceProviderStatusReport(),
  ]);
  const marketEvidenceHealth = await getProjectMarketEvidenceHealth(params.projectId);
  const cruiseHealth = await getProjectCruiseHealth(params.projectId);
  if (!detail) {
    notFound();
  }

  const { project, workflow, state } = detail;
  const marketEvidence = detail.marketEvidence;
  const adOpportunity = workflow.opportunitySet.ad[0];
  const contentStrategy = detail.contentStrategy;
  const adAudit = detail.adAudit;
  const technicalSeo = detail.technicalSeo;
  const technicalSeoPatch = detail.technicalSeoPatch;
  const seoConversionAudit = detail.seoConversionAudit;
  const experimentAssignment = workflow.experimentAssignment;
  const localizationAssignment = workflow.localizationAssignment;
  const runtimeRoute = workflow.runtimeRoute;
  const connectionEvidenceRealCount = connectionEvidence.entries.filter((entry) => entry.providerMode === "real").length;
  const connectionEvidenceFallbackCount = connectionEvidence.entries.filter((entry) => entry.providerMode === "fallback").length;
  const connectionEvidenceUnconfiguredCount = connectionEvidence.entries.filter((entry) => entry.providerMode === "unconfigured").length;
  const connectionEvidenceStrictEligibleCount = connectionEvidence.entries.filter((entry) => entry.strictEligible).length;
  const connectionEvidenceTop = connectionEvidence.entries[0] ?? null;
  const deploymentStrictCount = deploymentHistory.entries.filter((entry) => entry.deployment.strictMode).length;
  const deploymentVerifiedCount = deploymentHistory.entries.filter((entry) => entry.deployment.verifiedPatch).length;
  const deploymentRealWritebackCount = deploymentHistory.entries.filter((entry) => entry.deployment.providerArtifactId || entry.deployment.providerUrl).length;
  const deploymentLatest = deploymentHistory.entries[0] ?? null;
  const rollbackLatest = rollbackHistory.entries[0] ?? null;
  const latestRun = runs[0] ?? null;
  const deploymentModeCounts = deploymentHistory.entries.reduce<Record<string, number>>((acc, entry) => {
    const mode = entry.deployment.mode;
    acc[mode] = (acc[mode] ?? 0) + 1;
    return acc;
  }, {});
  const topDeploymentMode = Object.entries(deploymentModeCounts).sort((a, b) => b[1] - a[1])[0] ?? null;
  const opportunityGroups = [
    { label: "SEO", items: workflow.opportunitySet.seo },
    { label: "AD", items: workflow.opportunitySet.ad },
    { label: "Technical", items: workflow.opportunitySet.technical },
    { label: "UX", items: workflow.opportunitySet.ux },
  ] as const;
  const technicalSections = technicalSeo
    ? [
        { label: "crawlability", findings: technicalSeo.crawlability },
        { label: "on-page", findings: technicalSeo.onPage },
        { label: "content", findings: technicalSeo.content },
        { label: "performance", findings: technicalSeo.performance },
      ]
    : [];
  const monitorRuns = runs.filter((run) => run.trigger === "monitor");
  const rollbackRuns = runs.filter((run) => run.status === "rolled_back");
  const monitorFailedRuns = monitorRuns.filter((run) => run.status === "failed");
  const latestMonitorRun = monitorRuns[0];
  const latestRollbackRun = rollbackRuns[0];
  const completedRunCount = runs.filter((run) => run.status === "completed").length;
  const failedRunCount = runs.filter((run) => run.status === "failed").length;
  const rolledBackRunCount = runs.filter((run) => run.status === "rolled_back").length;
  const requeuedRunCount = runs.filter((run) => run.status === "queued" || run.status === "running").length;
  const billingSettlementLatest = billingSettlementHistory.entries[0] ?? null;
  const billingSettlementDryRunCount = billingSettlementHistory.entries.filter((entry) => entry.dryRun).length;
  const billingSettlementLiveCount = billingSettlementHistory.entries.filter((entry) => !entry.dryRun).length;
  const billingSettlementDueTotal = billingSettlementHistory.entries.reduce((sum, entry) => sum + (entry.dueCents ?? 0), 0);
  const auditActionCounts = detail.audits.reduce<Record<string, number>>((acc, audit) => {
    const action = String(audit.action ?? "unknown");
    acc[action] = (acc[action] ?? 0) + 1;
    return acc;
  }, {});
  const auditActionTop = Object.entries(auditActionCounts).sort((a, b) => b[1] - a[1])[0] ?? null;
  const latestAudit = detail.audits[0] ?? null;
  const verifiedRollbackReady = Boolean(workflow.deployment?.rollbackReady && workflow.rollbackBundle);
  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("project_detail.title")}</div>
        <div className="project-head">
          <div className="project-title">
            <div>
              <h1>{project.name}</h1>
              <p className="hero-copy">{project.url}</p>
            </div>
            <StatusPill tone={toneForStatus(project.latestStage)}>{project.latestStage}</StatusPill>
          </div>
          <div className="project-meta">
            <StatusPill tone="accent">{project.siteClass}</StatusPill>
            <StatusPill tone={project.riskScore >= 80 ? "danger" : project.riskScore >= 60 ? "warn" : "good"}>
              {t("project_detail.risk")} {project.riskScore}
            </StatusPill>
            <StatusPill tone="neutral">{project.deploymentMode ?? t("project_detail.preview_only")}</StatusPill>
            <StatusPill tone={connectionTone(state.connectionHealth)}>{state.connectionHealth}</StatusPill>
          </div>
        </div>
        <div className="stat-grid" style={{ marginTop: 16 }}>
          <StatCard
            label={t("project_detail.real_evidence")}
            value={`${connectionEvidenceRealCount}/${connectionEvidence.entries.length}`}
            caption={t("project_detail.real_evidence_caption")}
            accent
          />
          <StatCard
            label={t("project_detail.approval")}
            value={workflow.approvalRequest.status}
            caption={workflow.approvalRequest.decisionHint}
          />
          <StatCard
            label={t("project_detail.release")}
            value={workflow.deployment?.status ?? t("project_detail.not_scheduled")}
            caption={workflow.deployment?.mode ?? workflow.plan.deploymentMode}
          />
          <StatCard
            label={t("project_detail.rollback")}
            value={verifiedRollbackReady ? t("project_detail.ready") : t("project_detail.pending")}
            caption={workflow.rollbackBundle?.rollbackId ?? t("project_detail.no_rollback_bundle")}
          />
        </div>
        {connectionEvidenceTop || deploymentLatest ? (
          <div className="alert-box" style={{ marginTop: 12 }}>
            {connectionEvidenceTop ? (
              <>
                {t("project_detail.top_connector")}: {connectionEvidenceTop.provider} · {connectionEvidenceTop.providerMode} · {connectionEvidenceTop.recentEvidenceLabel ?? "n/a"}
              </>
            ) : null}
            {connectionEvidenceTop && deploymentLatest ? " · " : null}
            {deploymentLatest ? (
              <>
                {t("project_detail.latest_deploy")}: {deploymentLatest.deployment.deploymentId} · {deploymentLatest.deployment.mode} · {deploymentLatest.deployment.status}
              </>
            ) : null}
          </div>
        ) : null}
        {focusTaskId || focusArtifactRef ? (
          <div className="alert-box" style={{ marginTop: 12 }}>
            {t("project_detail.focus_context")}
            {focusTaskId ? ` · taskId=${focusTaskId}` : ""}
            {focusArtifactRef ? ` · artifactRef=${focusArtifactRef}` : ""}
          </div>
        ) : null}
        <div className="project-foot" style={{ marginTop: 12 }}>
          <span>{t("project_detail.advanced_operations")}</span>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <a href="#sources">{t("project_detail.source_health")}</a>
            <a href="#opportunities">{t("project_detail.opportunities")}</a>
            <a href="#billing">{t("project_detail.billing")}</a>
            <a href="#runs">{t("project_detail.runs")}</a>
            <a href="#audit">{t("project_detail.audit")}</a>
          </div>
        </div>
      </section>

      <section className="panel project-flow-panel" aria-labelledby="project-flow-title">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("project_detail.execution_workspace")}</div>
            <h2 id="project-flow-title">{t("project_detail.execution_title")}</h2>
          </div>
          <p>{t("project_detail.execution_description")}</p>
        </div>
        <nav className="project-flow-grid" aria-label="Project execution stages">
          <a className="project-flow-step" href="#preview">
            <span className="project-flow-index">01</span>
            <strong>{t("project_detail.preview")}</strong>
            <span>{workflow.preview.previewId}</span>
            <StatusPill tone="good">{t("project_detail.ready")}</StatusPill>
          </a>
          <a className="project-flow-step" href="#approval">
            <span className="project-flow-index">02</span>
            <strong>{t("project_detail.approval")}</strong>
            <span>{t("project_detail.risk")} {workflow.plan.riskScore}</span>
            <StatusPill tone={toneForStatus(workflow.approvalRequest.status)}>{workflow.approvalRequest.status}</StatusPill>
          </a>
          <a className="project-flow-step" href="#release">
            <span className="project-flow-index">03</span>
            <strong>{t("project_detail.release")}</strong>
            <span>{workflow.deployment?.mode ?? workflow.plan.deploymentMode}</span>
            <StatusPill tone={toneForStatus(workflow.deployment?.status ?? "not scheduled")}>
              {workflow.deployment?.status ?? t("project_detail.not_scheduled")}
            </StatusPill>
          </a>
          <a className="project-flow-step" href="#monitoring">
            <span className="project-flow-index">04</span>
            <strong>{t("project_detail.monitor_rollback")}</strong>
            <span>{monitorRuns.length} {t("project_detail.monitor_runs")}</span>
            <StatusPill tone={verifiedRollbackReady ? "good" : monitorFailedRuns.length ? "danger" : "neutral"}>
              {verifiedRollbackReady ? t("project_detail.rollback_ready") : latestMonitorRun?.status ?? t("project_detail.not_started")}
            </StatusPill>
          </a>
        </nav>
      </section>

      <div className="project-layout">
        <div className="detail-stack">
          <section className="panel" id="profile">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("project_detail.profile")}</div>
                <h2>{t("project_detail.site_profile")}</h2>
              </div>
              <p>{formatDateTime(project.updatedAt, locale)}</p>
            </div>
            <div className="stack">
              <div className="metric-row">
                <span>{t("project_detail.brand_voice")}</span>
                <strong>{workflow.siteProfile.brandVoice}</strong>
              </div>
              <div className="metric-row">
                <span>{t("project_detail.pages")}</span>
                <strong>{workflow.siteProfile.pageCountEstimate}</strong>
              </div>
              <div className="metric-row">
                <span>{t("project_detail.trust_signals")}</span>
                <strong>{workflow.siteProfile.trustSignals.join(" · ")}</strong>
              </div>
              <div className="metric-row">
                <span>{t("project_detail.auto_cruise")}</span>
                <strong>{state.autoCruiseEnabled ? `${t("project_detail.on")} · ${state.syncIntervalMinutes}m` : t("project_detail.off")}</strong>
              </div>
              <div className="metric-row">
                <span>{t("project_detail.cruise_state")}</span>
                <strong>
                  {cruiseHealth.dueNow ? t("project_detail.due_now") : t("project_detail.scheduled")}
                  {cruiseHealth.overdue ? ` · ${t("project_detail.overdue")}` : ""}
                </strong>
              </div>
              <div className="metric-row">
                <span>{t("project_detail.cruise_next_run")}</span>
                <strong>{cruiseHealth.nextSyncAt ? formatDateTime(cruiseHealth.nextSyncAt, locale) : t("project_detail.not_scheduled")}</strong>
              </div>
              <ProjectCruiseToggleAction
                projectId={project.projectId}
                autoCruiseEnabled={state.autoCruiseEnabled}
                syncIntervalMinutes={state.syncIntervalMinutes}
                connections={detail.connections}
              />
              <div className="metric-row">
                <span>{t("project_detail.last_sync")}</span>
                <strong>{state.lastSyncAt ? formatDateTime(state.lastSyncAt, locale) : t("project_detail.never")}</strong>
              </div>
              <div className="metric-row">
                <span>{t("project_detail.next_sync")}</span>
                <strong>{state.nextSyncAt ? formatDateTime(state.nextSyncAt, locale) : t("project_detail.not_scheduled")}</strong>
              </div>
            </div>
          </section>

          <section className="panel" id="sources">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("project_detail.connections")}</div>
                <h2>{t("project_detail.source_health")}</h2>
              </div>
              <p>{workflow.ingestionReport?.status ?? "synthetic"}</p>
            </div>
            <div className="stat-grid">
              <StatCard label={t("project_detail.real")} value={formatNumber(connectionEvidenceRealCount)} caption={t("project_detail.real_evidence_caption")} accent />
              <StatCard label={t("project_detail.fallback")} value={formatNumber(connectionEvidenceFallbackCount)} caption={t("project_detail.fallback")} />
              <StatCard label={t("project_detail.unconfigured")} value={formatNumber(connectionEvidenceUnconfiguredCount)} caption={t("project_detail.unconfigured")} />
              <StatCard label={t("project_detail.strict_ready")} value={formatNumber(connectionEvidenceStrictEligibleCount)} caption={t("project_detail.strict_ready")} />
            </div>
            {connectionEvidenceTop ? (
              <div className="audit-meta" style={{ marginTop: 12 }}>
                Top evidence: {connectionEvidenceTop.provider} · {connectionEvidenceTop.providerMode} ·{" "}
                {connectionEvidenceTop.recentEvidenceLabel ?? "n/a"} ·{" "}
                {connectionEvidenceTop.recentEvidenceAt ? formatDateTime(connectionEvidenceTop.recentEvidenceAt, locale) : "n/a"}
              </div>
            ) : null}
            <div className="suite-grid">
              <article className="suite-card">
                <div className="metric-row">
                  <span>{t("project_detail.project_health")}</span>
                  <strong>{projectConnectorsHealth.connectionHealth}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.connection_mix")}</span>
                  <strong>
                    {projectConnectorsHealth.realConnectionCount}/{projectConnectorsHealth.fallbackConnectionCount}/{projectConnectorsHealth.unconfiguredConnectionCount}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.last_real_read")}</span>
                  <strong>{projectConnectorsHealth.readRealLastEvidenceAt ? formatDateTime(projectConnectorsHealth.readRealLastEvidenceAt, locale) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.last_real_write")}</span>
                  <strong>{projectConnectorsHealth.writeRealLastEvidenceAt ? formatDateTime(projectConnectorsHealth.writeRealLastEvidenceAt, locale) : "n/a"}</strong>
                </div>
              </article>
              {connectionEvidence.entries.map((connection) => (
                <article className="suite-card" key={`${connection.provider}-${connection.recentEvidenceRef ?? "none"}`}>
                  {(() => {
                    const fallbackReason = connection.fallbackReason ?? "none";
                    const latencyMs = typeof connection.latencyMs === "number" ? connection.latencyMs : null;
                    return (
                      <>
                  <div className="suite-title">
                    <strong>{connection.label}</strong>
                    <StatusPill tone={connectionTone(connection.status)}>{connection.status}</StatusPill>
                  </div>
                  <ul>
                    <li>Provider: {connection.provider}</li>
                    <li>Mode: {connection.providerMode}</li>
                    <li>Strict-ready: {connection.strictEligible ? "yes" : "no"}</li>
                    <li>Auth source: {connection.authSource ?? "n/a"}</li>
                    <li>Last success: {connection.lastSuccessAt ? formatDateTime(connection.lastSuccessAt, locale) : "n/a"}</li>
                    <li>Last error: {connection.lastErrorAt ? formatDateTime(connection.lastErrorAt, locale) : "n/a"}</li>
                    <li>Recent evidence: {connection.recentEvidenceLabel ?? "n/a"}</li>
                    <li>Evidence ref: {connection.recentEvidenceRef ?? "n/a"}</li>
                    <li>Evidence time: {connection.recentEvidenceAt ? formatDateTime(connection.recentEvidenceAt, locale) : "n/a"}</li>
                    <li>Fallback: {fallbackReason}</li>
                    <li>Latency: {latencyMs != null ? `${latencyMs}ms` : "n/a"}</li>
                  </ul>
                  <ProjectConnectorRefreshAction projectId={project.projectId} provider={connection.provider as never} />
                      </>
                    );
                  })()}
                </article>
              ))}
            </div>
            {workflow.ingestionReport ? (
              <div className="stack" style={{ marginTop: 14 }}>
                <div className="metric-row">
                  <span>{t("project_detail.ingestion_report")}</span>
                  <strong>{workflow.ingestionReport.reportId}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.evidence")}</span>
                  <strong>{workflow.ingestionReport.evidence.length} sources</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.notes")}</span>
                  <strong>{workflow.ingestionReport.notes.join(" · ") || "None"}</strong>
                </div>
              </div>
            ) : null}
            <div style={{ marginTop: 16 }}>
              <ProjectOperations projectId={project.projectId} />
            </div>
          </section>

          <section className="panel" id="runs">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("project_detail.connector_history")}</div>
                <h2>{t("project_detail.recent_connector_events")}</h2>
              </div>
              <p>{connectionHistory.entries.length} recent events</p>
            </div>
            <div className="stack">
              {connectionHistory.entries.map((entry) => (
                <article className="audit-card" key={entry.auditId}>
                  <div className="audit-header">
                    <strong className="audit-title">{entry.provider}</strong>
                    <StatusPill tone={connectionTone(entry.status)}>{entry.status}</StatusPill>
                  </div>
                  <p>{entry.summary || entry.action}</p>
                  <div className="metric-row">
                    <span>{t("project_detail.action")}</span>
                    <strong>{entry.action}</strong>
                  </div>
                  <div className="metric-row">
                    <span>{t("project_detail.created")}</span>
                    <strong>{formatDateTime(entry.createdAt, locale)}</strong>
                  </div>
                  <div className="metric-row">
                    <span>{t("project_detail.auth_source")}</span>
                    <strong>{entry.authSource ?? "none"}</strong>
                  </div>
                  <div className="metric-row">
                    <span>{t("project_detail.failure")}</span>
                    <strong>{entry.failureCode ?? "none"}</strong>
                  </div>
                  <div className="metric-row">
                    <span>{t("project_detail.fallback_reason")}</span>
                    <strong>{entry.fallbackReason ?? "none"}</strong>
                  </div>
                  <div className="metric-row">
                    <span>{t("project_detail.latency")}</span>
                    <strong>{entry.latencyMs != null ? `${entry.latencyMs}ms` : "n/a"}</strong>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="panel" id="billing">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("project_detail.billing")}</div>
                <h2>{t("project_detail.settlement_history")}</h2>
              </div>
              <p>
                Project-level settlement history with direct links into the workspace billing filter.
              </p>
            </div>
            <div className="stat-grid">
              <StatCard label="Executions" value={formatNumber(billingSettlementHistory.total)} caption="project settlement records" accent />
              <StatCard label="Dry-run" value={formatNumber(billingSettlementDryRunCount)} caption="preview settlements" />
              <StatCard label="Live" value={formatNumber(billingSettlementLiveCount)} caption="live settlements" />
              <StatCard label="Due total" value={formatNumber(billingSettlementDueTotal)} caption="sum of due cents in history" />
            </div>
            <div className="project-foot" style={{ marginTop: 12 }}>
              <span>{t("project_detail.workspace_view")}</span>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <Link href={`/settings?billingProjectId=${encodeURIComponent(params.projectId)}#billing`}>{t("project_detail.open_billing_filter")}</Link>
                <Link href={`/monitor?billingProjectId=${encodeURIComponent(params.projectId)}#billing-history`}>{t("project_detail.monitor_replay")}</Link>
                <Link href={`/acceptance?billingProjectId=${encodeURIComponent(params.projectId)}#billing-history`}>{t("project_detail.acceptance_replay")}</Link>
              </div>
            </div>
            {billingSettlementLatest ? (
              <div className="alert-box" style={{ marginTop: 12 }}>
                Latest settlement: {billingSettlementLatest.createdAt} · {billingSettlementLatest.status} · {billingSettlementLatest.providerName} · gateway{" "}
                {billingSettlementLatest.gatewayProviderName ?? "n/a"} · route {billingSettlementLatest.gatewayRouteProviderName ?? "n/a"} ·{" "}
                {billingSettlementLatest.dryRun ? "dry-run" : "live"} · {billingSettlementLatest.requestMethod ?? "POST"}{" "}
                {billingSettlementLatest.requestPath ?? "/api/billing/settlement/execute"} · gateway {billingSettlementLatest.gatewayReady ? "ready" : "partial"} · route{" "}
                {billingSettlementLatest.gatewayRoutePriority ?? "n/a"} · reason {billingSettlementLatest.gatewayRouteReason ?? "n/a"} · {billingSettlementLatest.gatewayRouteReady ? "ready" : "fallback"} · failure {billingSettlementLatest.failureCode ?? "none"} · retryable {billingSettlementLatest.retryable ? "yes" : "no"} ·{" "}
                {billingSettlementLatest.projectName ?? params.projectId}
              </div>
            ) : null}
            <div className="stack" style={{ marginTop: 12 }}>
              {billingSettlementHistory.entries.length === 0 ? (
                <div className="project-copy">{t("project_detail.no_settlements")}</div>
              ) : (
                billingSettlementHistory.entries.map((entry) => (
                  <article className="audit-card" key={entry.auditId}>
                    <div className="audit-header">
                      <strong className="audit-title">{entry.providerName}</strong>
                      <StatusPill tone={entry.status === "completed" ? "good" : entry.status === "failed" || entry.status === "blocked" ? "danger" : "neutral"}>
                        {entry.status}
                      </StatusPill>
                    </div>
                    <p>{entry.message ?? entry.memo ?? "Settlement execution."}</p>
                    <div className="metric-row">
                      <span>{t("project_detail.created")}</span>
                      <strong>{formatDateTime(entry.createdAt, locale)}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.gateway_provider")}</span>
                      <strong>{entry.gatewayProviderName ?? "n/a"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.gateway_route")}</span>
                      <strong>{entry.gatewayRouteProviderName ?? "n/a"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.route_reason")}</span>
                      <strong>{entry.gatewayRouteReason ?? "n/a"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.request")}</span>
                      <strong>
                        {entry.requestMethod ?? "POST"} {entry.requestPath ?? "/api/billing/settlement/execute"}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.due")}</span>
                      <strong>{entry.dueCents} cents</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.ready")}</span>
                      <strong>{entry.settlementReady ? "yes" : "no"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.gateway")}</span>
                      <strong>{entry.gatewayReady ? "ready" : "partial"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.route")}</span>
                      <strong>
                        {entry.gatewayRouteProviderName ?? "n/a"} · priority {entry.gatewayRoutePriority ?? "n/a"} · {entry.gatewayRouteReady ? "ready" : "fallback"}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.reason")}</span>
                      <strong>{entry.gatewayRouteReason ?? "n/a"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.failure")}</span>
                      <strong>{entry.failureCode ?? "none"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.retryable")}</span>
                      <strong>{entry.retryable ? "yes" : "no"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.mode")}</span>
                      <strong>{entry.dryRun ? "dry-run" : "live"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.project")}</span>
                      <strong>{entry.projectName ?? entry.projectId ?? params.projectId}</strong>
                    </div>
                    <div className="project-foot">
                      <span>{t("project_detail.workspace_replay")}</span>
                      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                        <Link href={`/monitor?billingProjectId=${encodeURIComponent(params.projectId)}#billing-history`}>{t("project_detail.monitor")}</Link>
                        <Link href={`/acceptance?billingProjectId=${encodeURIComponent(params.projectId)}#billing-history`}>{t("project_detail.acceptance")}</Link>
                      </div>
                    </div>
                  </article>
                ))
              )}
            </div>
          </section>

          {marketEvidence ? (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <div className="eyebrow">{t("project_detail.market_evidence")}</div>
                  <h2>{t("project_detail.market_sources")}</h2>
                </div>
                <p>{marketEvidence.notes.join(" · ")}</p>
              </div>
              <div className="stat-grid" style={{ marginBottom: 14 }}>
                <StatCard label="Strict ready" value={marketEvidenceHealth.strictReady ? "yes" : "no"} caption="market evidence strict gate" accent />
                <StatCard label="Connected" value={formatNumber(marketEvidenceHealth.connectedCount)} caption="connected trend/news/qa samples" />
                <StatCard label="Fresh" value={formatNumber(marketEvidenceHealth.freshCount)} caption="samples inside freshness window" />
                <StatCard label="Synthetic" value={formatNumber(marketEvidenceHealth.syntheticCount)} caption="fallback market samples" />
              </div>
              <div className="audit-meta" style={{ marginBottom: 14 }}>
                Strict mode: {marketEvidenceHealth.strictProvidersEnabled ? "enabled" : "disabled"} · Latest fetched:{" "}
                {marketEvidenceHealth.latestFetchedAt ? formatDateTime(marketEvidenceHealth.latestFetchedAt, locale) : "n/a"} ·
                Stale: {marketEvidenceHealth.staleCount}
              </div>
              <div className="suite-grid" style={{ marginBottom: 14 }}>
                <article className="suite-card">
                  <div className="suite-title">
                    <strong>{t("project_detail.provider_readiness")}</strong>
                    <StatusPill tone={marketEvidenceProviders.strictReadyCount > 0 ? "good" : "warn"}>
                      {marketEvidenceProviders.strictReadyCount}
                    </StatusPill>
                  </div>
                  <div className="project-copy">
                    {marketEvidenceProviders.configuredCount}/{marketEvidenceProviders.providerCount} configured · {marketEvidenceProviders.authConfiguredCount} auth-configured
                  </div>
                  <div className="audit-meta" style={{ marginTop: 8 }}>
                    {marketEvidenceProviders.notes[0] ?? "No market evidence provider notes yet."}
                  </div>
                </article>
                <article className="suite-card">
                  <div className="suite-title">
                    <strong>{t("project_detail.strict_refresh_ready")}</strong>
                    <StatusPill tone={marketEvidenceProviders.strictReadyCount > 0 ? "good" : "danger"}>
                      {marketEvidenceProviders.strictReadyCount > 0 ? "ready" : "blocked"}
                    </StatusPill>
                  </div>
                  <div className="project-copy">
                    Connector refresh should favor strict-ready sources for trend/news/qa.
                  </div>
                  <div className="audit-meta" style={{ marginTop: 8 }}>
                    {marketEvidenceProviders.entries.map((entry) => `${entry.provider}: ${entry.strictReady ? "strict" : "fallback"}`).join(" · ")}
                  </div>
              </article>
            </div>
            <div className="suite-grid" style={{ marginBottom: 14 }}>
              {marketEvidenceProviders.entries.map((entry) => (
                  <article className="suite-card" key={entry.provider}>
                    <div className="suite-title">
                      <strong>{entry.providerLabel}</strong>
                      <StatusPill tone={entry.strictReady ? "good" : "warn"}>{entry.strictReady ? "strict" : "fallback"}</StatusPill>
                    </div>
                    <ul>
                      <li>Endpoint: {entry.endpoint ?? "n/a"}</li>
                      <li>Configured: {entry.configured ? "yes" : "no"}</li>
                      <li>Auth configured: {entry.authConfigured ? "yes" : "no"}</li>
                      <li>Auth source: {entry.authSource}</li>
                      <li>Fallback: {entry.fallbackReason ?? "none"}</li>
                    </ul>
                  </article>
                ))}
              </div>
              <div className="suite-grid">
                {[
                  ["Trend", marketEvidence.trend],
                  ["News", marketEvidence.news],
                  ["QA", marketEvidence.qa],
                ].map(([label, items]) => (
                  <article className="suite-card" key={label as string}>
                    <div className="suite-title">
                      <strong>{label as string}</strong>
                      <StatusPill tone={(items as typeof marketEvidence.trend).some((item) => item.status === "connected") ? "good" : "warn"}>
                        {(items as typeof marketEvidence.trend).length}
                      </StatusPill>
                    </div>
                    {marketEvidence.summaries
                      .filter((summary) => summary.sourceType.toLowerCase() === String(label).toLowerCase())
                      .map((summary) => (
                        <div className="stack" key={`${label}-summary`} style={{ marginBottom: 12 }}>
                          <div className="metric-row">
                            <span>{t("project_detail.connected_synthetic_failed")}</span>
                            <strong>{summary.connectedCount} / {summary.syntheticCount} / {summary.failedCount}</strong>
                          </div>
                          <div className="metric-row">
                            <span>{t("project_detail.latest_fetched")}</span>
                            <strong>{summary.latestFetchedAt ? formatDateTime(summary.latestFetchedAt, locale) : "n/a"}</strong>
                          </div>
                          <div className="metric-row">
                            <span>{t("project_detail.average_latency")}</span>
                            <strong>{typeof summary.averageLatencyMs === "number" ? `${summary.averageLatencyMs}ms` : "n/a"}</strong>
                          </div>
                          <div className="audit-meta">
                            Auth: {summary.authSources.join(" · ") || "none"} {summary.fallbackReasons.length > 0 ? `· Fallback: ${summary.fallbackReasons.join(" · ")}` : ""}
                          </div>
                          <div className="audit-meta">
                            Endpoints: {summary.connectedEndpoints.join(" · ") || "none"} {summary.connectedSourceRefs.length > 0 ? `· Sources: ${summary.connectedSourceRefs.join(" · ")}` : ""}
                          </div>
                        </div>
                      ))}
                    <ul>
                      {(items as typeof marketEvidence.trend).map((item) => (
                        <li key={`${label}-${item.sourceRef ?? item.summary}`}>
                          {item.summary} · {item.status} · {item.sourceRef ?? "n/a"} · {item.fetchedAt ? formatDateTime(item.fetchedAt, locale) : "n/a"}
                        </li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          <section className="panel" id="opportunities">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("project_detail.opportunities")}</div>
                <h2>{t("project_detail.opportunity_title")}</h2>
              </div>
              <p>{t("project_detail.opportunity_description")}</p>
            </div>
            <div className="suite-grid">
              {opportunityGroups.map((group) => (
                <div className="suite-card" key={group.label}>
                  <div className="suite-title">
                    <strong>{group.label}</strong>
                    <StatusPill tone="neutral">{group.items.length}</StatusPill>
                  </div>
                  <ul>
                    {group.items.map((item) => (
                      <li key={item.title}>
                        {item.title} ({item.impactScore}/{item.riskScore})
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>

          {contentStrategy ? (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <div className="eyebrow">{t("project_detail.content_plan")}</div>
                  <h2>{t("project_detail.topic_clusters")}</h2>
                </div>
                <p>{contentStrategy.pillarPage}</p>
              </div>
              <div className="stack">
                <div className="metric-row">
                  <span>{t("project_detail.pillar_keyword")}</span>
                  <strong>{contentStrategy.pillarKeyword}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.intent")}</span>
                  <strong>{contentStrategy.pillarIntent}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.clusters")}</span>
                  <strong>{formatNumber(contentStrategy.topicClusters.length)}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.market_signals")}</span>
                  <strong>{formatNumber(contentStrategy.marketSignals.length)}</strong>
                </div>
              </div>
              {contentStrategy.marketSignals.length > 0 ? (
                <div className="audit-meta" style={{ marginTop: 14 }}>
                  Live signals: {contentStrategy.marketSignals.join(" · ")}
                </div>
              ) : null}
              <div className="suite-grid" style={{ marginTop: 14 }}>
                {contentStrategy.topicClusters.map((cluster) => (
                  <article className="suite-card" key={cluster.title}>
                    <div className="suite-title">
                      <strong>{cluster.title}</strong>
                      <StatusPill tone="accent">{cluster.contentType}</StatusPill>
                    </div>
                    <ul>
                      <li>Primary keyword: {cluster.primaryKeyword}</li>
                      <li>Word count: {cluster.wordCount}</li>
                      <li>Priority: {cluster.priority}</li>
                    </ul>
                    <div className="audit-meta">Next step: {cluster.nextStep}</div>
                  </article>
                ))}
              </div>
              <div className="stack" style={{ marginTop: 14 }}>
                {contentStrategy.calendar.map((item) => (
                  <div className="metric-row" key={`${item.week}-${item.topic}`}>
                    <span>Week {item.week}: {item.topic}</span>
                    <strong>{item.targetKeyword}</strong>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {adAudit ? (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <div className="eyebrow">{t("project_detail.ad_audit")}</div>
                  <h2>{t("project_detail.placement_policy_fit")}</h2>
                </div>
                <p>{adAudit.reason}</p>
              </div>
              <div className="stack">
                <div className="metric-row">
                  <span>{t("project_detail.ad_allowed")}</span>
                  <strong>{adAudit.adAllowed ? "yes" : "no"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.connector_status")}</span>
                  <strong>{adAudit.adConnectorStatus ?? "unknown"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.provider_family")}</span>
                  <strong>{adAudit.adProviderFamily ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.provider_name")}</span>
                  <strong>{adAudit.adProviderName ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.provider_ref")}</span>
                  <strong>{adAudit.adProviderRef ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.inventory")}</span>
                  <strong>{adAudit.adInventoryStatus ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.impressions_day")}</span>
                  <strong>{typeof adAudit.adImpressionsDaily === "number" ? formatNumber(adAudit.adImpressionsDaily) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.clicks_day")}</span>
                  <strong>{typeof adAudit.adClicksDaily === "number" ? formatNumber(adAudit.adClicksDaily) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>CTR</span>
                  <strong>{typeof adAudit.adCtr === "number" ? `${(adAudit.adCtr * 100).toFixed(2)}%` : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Fill rate</span>
                  <strong>{typeof adAudit.adFillRate === "number" ? `${(adAudit.adFillRate * 100).toFixed(1)}%` : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>RPM</span>
                  <strong>{typeof adAudit.adRpm === "number" ? adAudit.adRpm.toFixed(2) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.revenue_day")}</span>
                  <strong>{typeof adAudit.adRevenueEstimateDaily === "number" ? adAudit.adRevenueEstimateDaily.toFixed(2) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.revenue_month")}</span>
                  <strong>{typeof adAudit.adRevenueEstimateMonthly === "number" ? adAudit.adRevenueEstimateMonthly.toFixed(2) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.settled_day")}</span>
                  <strong>{typeof adAudit.adRevenueSettledDaily === "number" ? adAudit.adRevenueSettledDaily.toFixed(2) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.settlement")}</span>
                  <strong>{adAudit.adRevenueSettlementWindow ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.currency")}</span>
                  <strong>{adAudit.adRevenueCurrency ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.policy_tier")}</span>
                  <strong>{adAudit.adPolicyTier ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.payout_threshold")}</span>
                  <strong>{typeof adAudit.adPayoutThreshold === "number" ? adAudit.adPayoutThreshold.toFixed(2) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.provider_program")}</span>
                  <strong>{adAudit.adProviderProgram ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.geo_coverage")}</span>
                  <strong>{adAudit.adGeoCoverage.join(" · ") || "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.strict_publish")}</span>
                  <strong>{adAudit.strictPublishEligible ? "eligible" : "blocked"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.providers")}</span>
                  <strong>{adAudit.providerExamples.join(" · ") || "none"}</strong>
                </div>
                {adAudit.failureCode ? (
                  <div className="metric-row">
                    <span>{t("project_detail.failure_code")}</span>
                    <strong>{adAudit.failureCode}</strong>
                  </div>
                ) : null}
              {adAudit.fallbackReason ? (
                <div className="metric-row">
                  <span>{t("project_detail.fallback_reason")}</span>
                  <strong>{adAudit.fallbackReason}</strong>
                </div>
              ) : null}
              <div className="project-foot" style={{ marginTop: 14 }}>
                <span>{t("project_detail.workspace_replay")}</span>
                <Link href={`/monitor?adAuditProjectId=${encodeURIComponent(project.projectId)}#ad-audit-history`}>{t("project_detail.open_ad_replay")}</Link>
              </div>
            </div>
              {adAudit.negativeConditions.length > 0 ? (
                <div className="audit-meta" style={{ marginTop: 14 }}>
                  No-ad conditions: {adAudit.negativeConditions.join(" · ")}
                </div>
              ) : null}
              <div className="suite-grid" style={{ marginTop: 14 }}>
                {adAudit.recommendations.map((item) => (
                  <article className="suite-card" key={item.slotName}>
                    <div className="suite-title">
                      <strong>{item.slotName}</strong>
                      <StatusPill tone={item.allowed ? "good" : "danger"}>{item.allowed ? "allowed" : "blocked"}</StatusPill>
                    </div>
                    <ul>
                      <li>Page: {item.pageUrl}</li>
                      <li>Placement: {item.placement}</li>
                      <li>Risk: {item.riskScore}</li>
                    </ul>
                    <div className="audit-meta">{item.reason}</div>
                    {item.negativeConditions && item.negativeConditions.length > 0 ? (
                      <div className="audit-meta" style={{ marginTop: 8 }}>
                        Block when: {item.negativeConditions.join(" · ")}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {technicalSeo ? (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <div className="eyebrow">{t("project_detail.technical_seo")}</div>
                  <h2>{t("project_detail.technical_seo_title")}</h2>
                </div>
                <p>{technicalSeo.overallHealth}</p>
              </div>
              <div className="stack">
                <div className="metric-row">
                  <span>{t("project_detail.health")}</span>
                  <strong>{technicalSeo.overallHealth}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.action_plan")}</span>
                  <strong>{technicalSeo.actionPlan.join(" · ")}</strong>
                </div>
              </div>
              <div className="suite-grid" style={{ marginTop: 14 }}>
                {technicalSections.map((section) => (
                  <article className="suite-card" key={section.label}>
                    <div className="suite-title">
                      <strong>{section.label}</strong>
                      <StatusPill tone={section.findings.length ? "warn" : "good"}>{section.findings.length}</StatusPill>
                    </div>
                    <ul>
                      {section.findings.map((item) => (
                        <li key={`${item.area}-${item.priority}`}>
                          {item.issue} - {item.fix}
                        </li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {technicalSeoPatch ? (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <div className="eyebrow">{t("project_detail.technical_patch")}</div>
                  <h2>{t("project_detail.verification_audit")}</h2>
                </div>
                <StatusPill tone={technicalSeoPatch.verifiedPatch ? "good" : "danger"}>
                  {technicalSeoPatch.verifiedPatch ? "verified" : "failed"}
                </StatusPill>
              </div>
              <div className="stack">
                <div className="metric-row">
                  <span>{t("project_detail.strict_mode")}</span>
                  <strong>{technicalSeoPatch.strictMode ? "on" : "off"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.checked_targets")}</span>
                  <strong>{String((technicalSeoPatch.patchAudit?.checkedTargets as number | undefined) ?? 0)}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.passed_failed")}</span>
                  <strong>
                    {String((technicalSeoPatch.patchAudit?.passedTargets as number | undefined) ?? 0)} /{" "}
                    {String((technicalSeoPatch.patchAudit?.failedTargets as number | undefined) ?? 0)}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.schema_before_after")}</span>
                  <strong>
                    {String((((technicalSeoPatch.patchAudit?.beforeAfter as { schemaTypes?: { before?: unknown[] } } | undefined)?.schemaTypes?.before?.length) ?? 0))} /{" "}
                    {String((((technicalSeoPatch.patchAudit?.beforeAfter as { schemaTypes?: { after?: unknown[] } } | undefined)?.schemaTypes?.after?.length) ?? 0))}
                  </strong>
                </div>
              </div>
              {technicalSeoPatch.notes.length ? (
                <ul className="bullets" style={{ marginTop: 12 }}>
                  {technicalSeoPatch.notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}

          {seoConversionAudit ? (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <div className="eyebrow">SEO audit lifecycle</div>
                  <h2>Evidence and conversion review</h2>
                </div>
                <StatusPill tone={seoConversionAudit.attribution.status === "ready" ? "good" : "warn"}>
                  {seoConversionAudit.attribution.status === "ready" ? "attribution ready" : "待核验"}
                </StatusPill>
              </div>
              <div className="stack">
                <div className="metric-row">
                  <span>Conversion goal</span>
                  <strong>{seoConversionAudit.attribution.conversionGoal}</strong>
                </div>
                <div className="metric-row">
                  <span>Evidence sources</span>
                  <strong>{seoConversionAudit.attribution.availableSources.join(" · ") || "none"}</strong>
                </div>
                <div className="metric-row">
                  <span>Baseline windows</span>
                  <strong>
                    {seoConversionAudit.baselineReadiness.map((item) => `${item.windowDays}d ${item.ready ? "ready" : "待核验"}`).join(" · ")}
                  </strong>
                </div>
              </div>
              <div className="suite-grid" style={{ marginTop: 14 }}>
                {seoConversionAudit.findings.slice(0, 6).map((item) => (
                  <article className="suite-card" key={item.findingId}>
                    <div className="suite-title">
                      <strong>{item.priority} · {item.area}</strong>
                      <StatusPill tone={item.evidenceStatus === "observed" ? "good" : "warn"}>{item.evidenceStatus}</StatusPill>
                    </div>
                    <p>{item.issue}</p>
                    <div className="audit-meta">{item.recommendedAction}</div>
                    {item.requiresApproval ? <div className="audit-meta">Approval and rollback required.</div> : null}
                  </article>
                ))}
              </div>
              <div className="audit-meta" style={{ marginTop: 14 }}>
                Reviews: {seoConversionAudit.reviewCheckpoints.map((item) => `day ${item.day}: ${item.ready ? "ready" : "待核验"}`).join(" · ")}
              </div>
            </section>
          ) : null}

          <div id="preview">
            <PreviewDiff preview={workflow.preview} />
          </div>
        </div>

        <div className="detail-stack">
          <section className="panel" id="approval">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("project_detail.approval")}</div>
                <h2>{t("project_detail.gate_status")}</h2>
              </div>
              <p>{workflow.approvalRequest.decisionHint}</p>
            </div>
            <div className="stack">
              <div className="metric-row">
                <span>{t("project_detail.approval_status")}</span>
                <strong>{workflow.approvalRequest.status}</strong>
              </div>
              <div className="metric-row">
                <span>{t("project_detail.risk_summary")}</span>
                <strong>{workflow.approvalRequest.riskSummary}</strong>
              </div>
              <div className="metric-row">
                <span>{t("project_detail.approvers")}</span>
                <strong>{workflow.approvalRequest.requiredApprovers.join(", ")}</strong>
              </div>
            </div>
            <div style={{ marginTop: 16 }}>
              <TaskActions
                taskId={workflow.task.taskId}
                approvalStatus={workflow.task.approvalStatus}
                taskStatus={workflow.task.status}
                deploymentMode={workflow.project.deploymentMode}
                riskScore={workflow.project.riskScore}
              />
            </div>
          </section>

          {experimentAssignment ? (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <div className="eyebrow">{t("project_detail.experiment_routing")}</div>
                  <h2>{t("project_detail.runtime_assignment")}</h2>
                </div>
                <StatusPill tone={experimentAssignment.assignedExperimentCount > 0 ? "good" : experimentAssignment.warnings.length > 0 ? "warn" : "neutral"}>
                  {experimentAssignment.assignedExperimentCount > 0 ? "assigned" : experimentAssignment.strictAssignment ? "strict" : "preview"}
                </StatusPill>
              </div>
              <div className="stat-grid">
                <StatCard
                  label="Experiments"
                  value={String(experimentAssignment.experimentCount)}
                  caption={`${experimentAssignment.matchedExperimentCount} matched the current request`}
                  accent
                />
                <StatCard
                  label="Assigned"
                  value={String(experimentAssignment.assignedExperimentCount)}
                  caption={`${experimentAssignment.strictAssignment ? "strict" : "hash"} assignment path`}
                />
                <StatCard
                  label="Target surface"
                  value={experimentAssignment.targetSurface}
                  caption={experimentAssignment.targetLocale ?? "locale agnostic"}
                />
                <StatCard
                  label="Subject"
                  value={experimentAssignment.subjectKey}
                  caption={experimentAssignment.projectId ?? project.projectId}
                />
              </div>
              <div className="stack" style={{ marginTop: 14 }}>
                {experimentAssignment.assignments.map((assignment) => (
                  <article className="audit-card" key={assignment.experimentKey}>
                    <div className="audit-head">
                      <strong className="audit-title">{assignment.experimentKey}</strong>
                      <StatusPill tone={assignment.eligible ? "good" : "warn"}>
                        {assignment.eligible ? "eligible" : "blocked"}
                      </StatusPill>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.variant")}</span>
                      <strong>{assignment.assignedVariantName ?? assignment.controlVariantName}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.bucket")}</span>
                      <strong>
                        {assignment.bucketRoll}/{assignment.bucketSize}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.scope")}</span>
                      <strong>
                        {assignment.targetSurface}
                        {assignment.targetLocale ? ` · ${assignment.targetLocale}` : ""}
                        {assignment.targetProjectMatch ? "" : " · out of scope"}
                      </strong>
                    </div>
                    {assignment.warnings.length ? (
                      <div className="audit-meta" style={{ marginTop: 8 }}>
                        {assignment.warnings.join(" · ")}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
              {experimentAssignment.warnings.length ? (
                <div className="alert-box" style={{ marginTop: 12 }}>
                  {experimentAssignment.warnings.join(" · ")}
                </div>
              ) : null}
              {experimentAssignment.recommendations.length ? (
                <ul className="bullets" style={{ marginTop: 12 }}>
                  {experimentAssignment.recommendations.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}

          {localizationAssignment ? (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <div className="eyebrow">{t("project_detail.localization_routing")}</div>
                  <h2>{t("project_detail.runtime_cluster_assignment")}</h2>
                </div>
                <StatusPill tone={localizationAssignment.assignedClusterCount > 0 ? "good" : localizationAssignment.warnings.length > 0 ? "warn" : "neutral"}>
                  {localizationAssignment.assignedClusterCount > 0 ? "assigned" : localizationAssignment.strictLocalization ? "strict" : "preview"}
                </StatusPill>
              </div>
              <div className="stat-grid">
                <StatCard
                  label="Clusters"
                  value={String(localizationAssignment.clusterCount)}
                  caption={`${localizationAssignment.matchedClusterCount} matched the current request`}
                  accent
                />
                <StatCard
                  label="Assigned"
                  value={String(localizationAssignment.assignedClusterCount)}
                  caption={`${localizationAssignment.strictLocalization ? "strict" : "loose"} localization`}
                />
                <StatCard
                  label="Locale"
                  value={localizationAssignment.targetLocale ?? "default"}
                  caption={localizationAssignment.host ?? "host agnostic"}
                />
                <StatCard
                  label="Subject"
                  value={localizationAssignment.subjectKey}
                  caption={localizationAssignment.projectId ?? project.projectId}
                />
              </div>
              <div className="stack" style={{ marginTop: 14 }}>
                {localizationAssignment.assignments.map((assignment) => (
                  <article className="audit-card" key={assignment.clusterKey}>
                    <div className="audit-head">
                      <strong className="audit-title">{assignment.clusterKey}</strong>
                      <StatusPill tone={assignment.clusterReady ? "good" : "warn"}>
                        {assignment.clusterReady ? "ready" : "blocked"}
                      </StatusPill>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.route_prefix")}</span>
                      <strong>{assignment.routePrefix}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.scope")}</span>
                      <strong>
                        {assignment.matchedByProject ? "project" : ""}
                        {assignment.matchedByLocale ? `${assignment.matchedByProject ? " · " : ""}locale` : ""}
                        {assignment.matchedByHost ? `${assignment.matchedByProject || assignment.matchedByLocale ? " · " : ""}host` : ""}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.canonical")}</span>
                      <strong>{assignment.canonicalProjectId ?? "n/a"}</strong>
                    </div>
                    {assignment.warnings.length ? (
                      <div className="audit-meta" style={{ marginTop: 8 }}>
                        {assignment.warnings.join(" · ")}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
              {localizationAssignment.warnings.length ? (
                <div className="alert-box" style={{ marginTop: 12 }}>
                  {localizationAssignment.warnings.join(" · ")}
                </div>
              ) : null}
              {localizationAssignment.recommendations.length ? (
                <ul className="bullets" style={{ marginTop: 12 }}>
                  {localizationAssignment.recommendations.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}

          {runtimeRoute ? (
            <section className="panel">
              <div className="section-heading">
                <div>
                  <div className="eyebrow">{t("project_detail.runtime_route")}</div>
                  <h2>{t("project_detail.request_chain")}</h2>
                </div>
                <StatusPill tone={runtimeRoute.runtimeReady ? "good" : "warn"}>
                  {runtimeRoute.runtimeReady ? "runtime-ready" : "preview"}
                </StatusPill>
              </div>
              <div className="stat-grid">
                <StatCard
                  label="Ready"
                  value={runtimeRoute.runtimeReady ? "yes" : "no"}
                  caption={`${Object.keys(runtimeRoute.resolvedProviders).length} provider routes resolved`}
                  accent
                />
                <StatCard
                  label="Surface"
                  value={runtimeRoute.targetSurface}
                  caption={runtimeRoute.targetLocale ?? "locale agnostic"}
                />
                <StatCard
                  label="Subject"
                  value={runtimeRoute.subjectKey}
                  caption={runtimeRoute.host ?? runtimeRoute.projectId}
                />
                <StatCard
                  label="Gateway"
                  value={runtimeRoute.gatewayReport?.gatewayReady ? "ready" : "partial"}
                  caption={`${runtimeRoute.gatewayReport?.routeReadyCount ?? 0}/${runtimeRoute.gatewayReport?.routeCount ?? 0} routes ready`}
                />
              </div>
              <div className="stack" style={{ marginTop: 14 }}>
                <div className="metric-row">
                  <span>{t("project_detail.experiment")}</span>
                  <strong>
                    {runtimeRoute.experimentAssignment?.assignments.find((assignment) => assignment.eligible && assignment.assignedVariantName)?.assignedVariantName ??
                      "preview"}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.locale_route")}</span>
                  <strong>
                    {runtimeRoute.localizationAssignment?.assignments.find(
                      (assignment) => assignment.clusterReady && (assignment.matchedByProject || assignment.matchedByLocale || assignment.matchedByHost),
                    )?.routePrefix ?? "preview"}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.request")}</span>
                  <strong>
                    {runtimeRoute.requestMethod ?? "POST"} {runtimeRoute.requestPath ?? `/api/projects/${runtimeRoute.projectId}/runtime-route`}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.providers")}</span>
                  <strong>{Object.entries(runtimeRoute.resolvedProviders).map(([suite, provider]) => `${suite}:${provider}`).join(" · ") || "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.analysis_entry")}</span>
                  <strong>
                    POST /api/projects/{runtimeRoute.projectId}/sync
                  </strong>
                </div>
              </div>
              {runtimeRoute.warnings.length ? (
                <div className="alert-box" style={{ marginTop: 12 }}>
                  {runtimeRoute.warnings.join(" · ")}
                </div>
              ) : null}
              {runtimeRoute.recommendations.length ? (
                <ul className="bullets" style={{ marginTop: 12 }}>
                  {runtimeRoute.recommendations.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}

          <section className="panel" id="advanced">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("project_detail.gateway_providers")}</div>
                <h2>{t("project_detail.runtime_visual_readiness")}</h2>
              </div>
              <p>{t("project_detail.runtime_visual_description")}</p>
            </div>
            <div className="suite-grid">
              <article className="suite-card">
                <div className="suite-title">
                  <strong>Runtime-edge</strong>
                  <StatusPill tone={runtimeEdgeGatewayProviders.gatewayReady ? "good" : "warn"}>
                    {runtimeEdgeGatewayProviders.gatewayReady ? "ready" : "partial"}
                  </StatusPill>
                </div>
                <div className="project-copy">
                  {runtimeEdgeGatewayProviders.routeReadyCount}/{runtimeEdgeGatewayProviders.routeCount} routes ready · {runtimeEdgeGatewayProviders.strictReadyCount} strict-ready
                </div>
                <div className="audit-meta" style={{ marginTop: 8 }}>
                  {runtimeEdgeGatewayProviders.recommendations[0] ?? "No runtime-edge recommendations yet."}
                </div>
                <div className="stack" style={{ marginTop: 12 }}>
                  {runtimeEdgeGatewayProviders.entries.slice(0, 2).map((entry) => (
                    <div className="metric-row" key={`project-runtime-edge-${entry.providerName}`}>
                      <span>{entry.providerLabel}</span>
                      <strong>
                        {entry.routeReady ? "route-ready" : "fallback"} · {entry.resolvedProviderName}
                      </strong>
                    </div>
                  ))}
                </div>
              </article>
              <article className="suite-card">
                <div className="suite-title">
                  <strong>Visual-farm</strong>
                  <StatusPill tone={visualFarmGatewayProviders.gatewayReady ? "good" : "warn"}>
                    {visualFarmGatewayProviders.gatewayReady ? "ready" : "partial"}
                  </StatusPill>
                </div>
                <div className="project-copy">
                  {visualFarmGatewayProviders.routeReadyCount}/{visualFarmGatewayProviders.routeCount} routes ready · {visualFarmGatewayProviders.strictReadyCount} strict-ready
                </div>
                <div className="audit-meta" style={{ marginTop: 8 }}>
                  {visualFarmGatewayProviders.recommendations[0] ?? "No visual-farm recommendations yet."}
                </div>
                <div className="stack" style={{ marginTop: 12 }}>
                  {visualFarmGatewayProviders.entries.slice(0, 2).map((entry) => (
                    <div className="metric-row" key={`project-visual-farm-${entry.providerName}`}>
                      <span>{entry.providerLabel}</span>
                      <strong>
                        {entry.routeReady ? "route-ready" : "fallback"} · {entry.resolvedProviderName}
                      </strong>
                    </div>
                  ))}
                </div>
              </article>
            </div>
          </section>

          <section className="panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("project_detail.runtime_route_history")}</div>
                <h2>{t("project_detail.route_replay")}</h2>
              </div>
              <p>
                Recent request-chain resolutions with request path, method, experiment, and locale routing.{" "}
                <Link href={`/monitor?runtimeRouteProjectId=${encodeURIComponent(params.projectId)}#runtime-route-history`}>
                  View workspace replay
                </Link>
              </p>
            </div>
            <div className="stat-grid" style={{ marginBottom: 14 }}>
              <StatCard label="History items" value={formatNumber(runtimeRouteHistory.total)} caption="recent runtime route records" accent />
              <StatCard
                label="Runtime-ready"
                value={formatNumber(runtimeRouteHistory.runtimeReadyCount)}
                caption={`${runtimeRouteHistory.previewOnlyCount} preview-only records`}
              />
              <StatCard
                label="Latest request"
                value={
                  runtimeRouteHistory.entries[0]
                    ? `${runtimeRouteHistory.entries[0].runtimeRouteRequestMethod ?? "POST"} ${runtimeRouteHistory.entries[0].runtimeRouteRequestPath ?? `/api/projects/${params.projectId}/sync`}`
                    : "n/a"
                }
                caption={runtimeRouteHistory.entries[0] ? formatDateTime(runtimeRouteHistory.entries[0].startedAt, locale) : "no route history yet"}
              />
              <StatCard
                label="Latest route"
                value={runtimeRouteHistory.entries[0]?.runtimeRouteSummary ?? "n/a"}
                caption="runtime route summary"
              />
            </div>
            <div className="stack">
              {runtimeRouteHistory.entries.length ? (
                runtimeRouteHistory.entries.map((run) => (
                  <article className="audit-card" key={`route-${run.runId}`}>
                    <div className="audit-head">
                      <strong className="audit-title">{run.trigger}</strong>
                      <StatusPill tone={runTone(run.runtimeRouteReady ? "completed" : run.status)}>
                        {run.runtimeRouteReady ? "runtime-ready" : "preview"}
                      </StatusPill>
                    </div>
                    <div className="audit-meta">
                      {run.runId} · {formatDateTime(run.startedAt, locale)}
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.request")}</span>
                      <strong>
                        {run.runtimeRouteRequestMethod ?? "POST"} {run.runtimeRouteRequestPath ?? `/api/projects/${params.projectId}/sync`}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.route")}</span>
                      <strong>
                        {run.runtimeRouteSummary ?? "n/a"} · route {run.gatewayRouteProviderName ?? "n/a"} · fallback {run.gatewayRouteFallbackProviderName ?? "n/a"} · priority{" "}
                        {run.gatewayRoutePriority ?? "n/a"}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.execution")}</span>
                      <strong>
                        {run.runtimeRouteExecutionMode ?? "preview"} · {run.runtimeRouteExecutionAction ?? "serve_preview"} · {run.runtimeRouteExecutionEntrypoint ?? `/api/projects/${params.projectId}/sync`}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.reason")}</span>
                      <strong>{run.runtimeRouteExecutionReason ?? "n/a"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.risk")}</span>
                      <strong>{run.riskScore}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.state")}</span>
                      <strong>{run.runtimeRouteReady ? "ready" : "preview-only"}</strong>
                    </div>
                  </article>
                ))
              ) : (
                <div className="alert-box">{t("project_detail.no_runtime_history")}</div>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("project_detail.gateway_providers")}</div>
                <h2>{t("project_detail.billing_model_readiness")}</h2>
              </div>
              <p>{t("project_detail.billing_model_description")}</p>
            </div>
            <div className="suite-grid">
              <article className="suite-card">
                <div className="suite-title">
                  <strong>{t("project_detail.billing_gateway")}</strong>
                  <StatusPill tone={billingGatewayProviders.gatewayReady ? "good" : "warn"}>
                    {billingGatewayProviders.gatewayReady ? "ready" : "partial"}
                  </StatusPill>
                </div>
                <div className="project-copy">
                  {billingGatewayProviders.routeReadyCount}/{billingGatewayProviders.providerCount} providers ready · {billingGatewayProviders.strictReadyCount} strict-ready
                </div>
                <div className="audit-meta" style={{ marginTop: 8 }}>
                  {billingGatewayProviders.configuredCount} configured · {billingGatewayProviders.authConfiguredCount} auth-configured
                </div>
                <div className="stack" style={{ marginTop: 12 }}>
                  {billingGatewayProviders.entries.slice(0, 2).map((entry) => (
                    <div className="metric-row" key={`project-billing-provider-${entry.providerName}`}>
                      <span>{entry.providerLabel}</span>
                      <strong>
                        {entry.routeReady ? "route-ready" : "fallback"} · {entry.resolvedProviderName}
                      </strong>
                    </div>
                  ))}
                </div>
              </article>
              <article className="suite-card">
                <div className="suite-title">
                  <strong>{t("project_detail.model_gateway")}</strong>
                  <StatusPill tone={modelGatewayProviders.gatewayReady ? "good" : "warn"}>
                    {modelGatewayProviders.gatewayReady ? "ready" : "partial"}
                  </StatusPill>
                </div>
                <div className="project-copy">
                  {modelGatewayProviders.routeReadyCount}/{modelGatewayProviders.routeCount} routes ready · {modelGatewayProviders.strictReadyCount} strict-ready
                </div>
                <div className="audit-meta" style={{ marginTop: 8 }}>
                  {modelGatewayProviders.recommendations[0] ?? "No model gateway recommendations yet."}
                </div>
                <div className="stack" style={{ marginTop: 12 }}>
                  {modelGatewayProviders.entries.slice(0, 2).map((entry) => (
                    <div className="metric-row" key={`project-model-provider-${entry.routeSuite}`}>
                      <span>{entry.routeSuite}</span>
                      <strong>
                        {entry.routeReady ? "route-ready" : "fallback"} · {entry.resolvedProviderName}
                      </strong>
                    </div>
                  ))}
                </div>
              </article>
            </div>
          </section>

          <WorkflowTimeline steps={workflow.plan.steps} />

          <section className="panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("project_detail.review")}</div>
                <h2>{t("project_detail.ux_policy_notes")}</h2>
              </div>
              <p>{t("project_detail.review_description")}</p>
            </div>
            <div className="stack">
              <div className="metric-row">
                <span>{t("project_detail.ux_score")}</span>
                <strong>{workflow.uxReview.score}</strong>
              </div>
              <div className="metric-row">
                <span>{t("project_detail.issues")}</span>
                <strong>{workflow.uxReview.issues.join(" · ") || "None"}</strong>
              </div>
              <div className="metric-row">
                <span>{t("project_detail.notes")}</span>
                <strong>{workflow.uxReview.notes.join(" · ")}</strong>
              </div>
            </div>
            {adOpportunity ? (
              <div className="alert-box" style={{ marginTop: 14 }}>
                AD opportunity: {adOpportunity.title}
              </div>
            ) : null}
          </section>

          <section className="panel" id="release">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("project_detail.deployment")}</div>
                <h2>{t("project_detail.release_rollback")}</h2>
              </div>
              <p>{t("project_detail.release_description")}</p>
            </div>
            <div className="stat-grid">
              <StatCard label="Deployments" value={formatNumber(deploymentHistory.total)} caption="project deployment records" accent />
              <StatCard label="Strict writes" value={formatNumber(deploymentStrictCount)} caption="deployments made in strict mode" />
              <StatCard label="Verified patches" value={formatNumber(deploymentVerifiedCount)} caption="deployments with verified pre/post checks" />
              <StatCard label="Real writeback" value={formatNumber(deploymentRealWritebackCount)} caption="deployments with provider artifacts or URLs" />
              <StatCard label="Rollback records" value={formatNumber(rollbackHistory.total)} caption="project rollback records" />
              <StatCard label="Top mode" value={topDeploymentMode?.[0] ?? "n/a"} caption={topDeploymentMode ? `${topDeploymentMode[1]} deploys` : "no deployments"} />
            </div>
            {deploymentLatest ? (
              <div className="audit-meta" style={{ marginTop: 12 }}>
                Latest deploy: {deploymentLatest.deployment.deploymentId} · {deploymentLatest.deployment.mode} ·{" "}
                {deploymentLatest.deployment.status} · updated {formatDateTime(deploymentLatest.updatedAt, locale)}
              </div>
            ) : null}
            {rollbackLatest ? (
              <div className="audit-meta">
                Latest rollback: {rollbackLatest.rollback.rollbackId} · {rollbackLatest.rollback.reason} ·{" "}
                {formatDateTime(rollbackLatest.updatedAt, locale)}
              </div>
            ) : null}
            <div className="deployment-grid">
              <div className="deployment-card">
                <div className="metric-row">
                  <span>{t("project_detail.status")}</span>
                  <strong>{workflow.deployment?.status ?? "not scheduled"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.mode")}</span>
                  <strong>{workflow.deployment?.mode ?? workflow.plan.deploymentMode}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.rollback_ready")}</span>
                  <strong>
                    {verifiedRollbackReady ? "yes" : workflow.deployment?.rollbackReady ? "declared, bundle missing" : "pending"}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.strict_mode")}</span>
                  <strong>{workflow.deployment?.strictMode ? "on" : "off"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.verified_patch")}</span>
                  <strong>{workflow.deployment?.verifiedPatch ? "yes" : "no"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.artifact")}</span>
                  <strong>{workflow.deployment?.artifactRef ?? workflow.preview.previewId}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.provider_id")}</span>
                  <strong>{workflow.deployment?.providerArtifactId ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.provider_url")}</span>
                  <strong>{workflow.deployment?.providerUrl ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.auth_source")}</span>
                  <strong>{workflow.deployment?.writebackAuthSource ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.writeback_provider")}</span>
                  <strong>{String(workflow.deployment?.writebackSummary?.provider ?? "n/a")}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.writeback_attempts")}</span>
                  <strong>{workflow.deployment?.writebackAttempts?.length ?? 0}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.writeback_summary")}</span>
                  <strong>
                    {`${String(workflow.deployment?.writebackSummary?.successCount ?? 0)}/${String(workflow.deployment?.writebackSummary?.failedCount ?? 0)}/${String(workflow.deployment?.writebackSummary?.skippedCount ?? 0)}`}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.last_endpoint")}</span>
                  <strong>{String(workflow.deployment?.writebackSummary?.lastEndpoint ?? "n/a")}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.average_latency")}</span>
                  <strong>
                    {typeof workflow.deployment?.writebackSummary?.averageLatencyMs === "number"
                      ? `${String(workflow.deployment.writebackSummary.averageLatencyMs)}ms`
                      : "n/a"}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.failure")}</span>
                  <strong>{String(workflow.deployment?.writebackSummary?.failureCode ?? "none")}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.successful_endpoints")}</span>
                  <strong>{Array.isArray(workflow.deployment?.writebackSummary?.successfulEndpoints) ? workflow.deployment.writebackSummary.successfulEndpoints.join(" · ") || "none" : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.failed_endpoints")}</span>
                  <strong>{Array.isArray(workflow.deployment?.writebackSummary?.failedEndpoints) ? workflow.deployment.writebackSummary.failedEndpoints.join(" · ") || "none" : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.patch_manifest")}</span>
                  <strong>{workflow.deployment?.patchManifestRef ?? "n/a"}</strong>
                </div>
                {workflow.deployment?.writebackAttempts?.length ? (
                  <ul className="bullets">
                    {workflow.deployment.writebackAttempts.slice(0, 3).map((item, idx) => (
                      <li key={`${idx}-${String(item.endpoint ?? "endpoint")}`}>
                        {String(item.endpoint ?? "endpoint")} · {String(item.status ?? "unknown")} · {String(item.failureCode ?? "ok")}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {workflow.deployment?.failureCode ? (
                  <div className="metric-row">
                    <span>{t("project_detail.failure_code")}</span>
                    <strong>{workflow.deployment.failureCode}</strong>
                  </div>
                ) : null}
                {workflow.deployment?.fallbackReason ? (
                  <div className="metric-row">
                    <span>{t("project_detail.fallback_reason")}</span>
                    <strong>{workflow.deployment.fallbackReason}</strong>
                  </div>
                ) : null}
                {workflow.deployment?.strictBlockers?.length ? (
                  <ul className="bullets">
                    {workflow.deployment.strictBlockers.slice(0, 5).map((item, idx) => (
                      <li key={`strict-blocker-${idx}`}>
                        {String(item.provider ?? "provider")} · {String(item.status ?? "unknown")} ·{" "}
                        {String(item.failureCode ?? "NO_CODE")} · {String(item.fallbackReason ?? "no reason")}
                      </li>
                    ))}
                  </ul>
                ) : null}
                {workflow.deployment?.releaseNotes?.length ? (
                  <ul className="bullets">
                    {workflow.deployment.releaseNotes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
              <div className="deployment-card">
                <div className="metric-row">
                  <span>{t("project_detail.rollback_id")}</span>
                  <strong>{workflow.rollbackBundle?.rollbackId ?? "pending"}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.safe_window")}</span>
                  <strong>{workflow.rollbackBundle ? `${workflow.rollbackBundle.safeWindowMinutes}m` : `${workflow.plan.riskScore >= 80 ? 5 : 10}m`}</strong>
                </div>
                <div className="metric-row">
                  <span>{t("project_detail.expected_effect")}</span>
                  <strong>{workflow.rollbackBundle?.expectedEffect ?? "Restore the previous stable release."}</strong>
                </div>
                {workflow.metricSnapshot ? (
                  <div className="stack" style={{ marginTop: 12 }}>
                    <div className="metric-row">
                      <span>{t("project_detail.seo_score")}</span>
                      <strong>{workflow.metricSnapshot.seoScore}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.ad_fit")}</span>
                      <strong>{workflow.metricSnapshot.adFitScore}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.traffic_delta")}</span>
                      <strong>{workflow.metricSnapshot.trafficDelta}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.metric_sources")}</span>
                      <strong>{Object.entries(workflow.metricSnapshot.sourceStatus).map(([key, value]) => `${key}:${value}`).join(" · ") || "synthetic"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.external_metrics")}</span>
                      <strong>{Object.keys(workflow.metricSnapshot.externalMetrics).join(" · ") || "none"}</strong>
                    </div>
                    {workflow.metricSnapshot.sourceMetricsSummary?.length ? (
                      <div className="stack" style={{ gap: 8 }}>
                        {workflow.metricSnapshot.sourceMetricsSummary.map((item) => (
                          <div className="audit-card" key={`${item.source}-${item.primaryMetric}`}>
                            <div className="audit-head">
                              <strong className="audit-title">{item.source}</strong>
                              <StatusPill tone={connectionTone(item.status)}>{item.status}</StatusPill>
                            </div>
                            <div className="audit-meta">
                              {item.primaryMetric} · {item.secondaryMetric}
                              {item.tertiaryMetric ? ` · ${item.tertiaryMetric}` : ""}
                            </div>
                            <div className="audit-meta">
                              {item.authSource ? `auth:${item.authSource}` : "auth:unknown"}
                              {item.fallbackReason ? ` · fallback:${item.fallbackReason}` : ""}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
              <div className="deployment-card">
                <div className="metric-row">
                  <span>{t("project_detail.deployment_history")}</span>
                  <strong>{deploymentHistory.entries?.length ?? 0}</strong>
                </div>
                {deploymentHistory.entries?.length ? (
                  <ul className="bullets">
                    {deploymentHistory.entries.slice(0, 6).map((item) => (
                      <li key={item.deployment.deploymentId}>
                        {((focusTaskId && item.deployment.taskId === focusTaskId) ||
                        (focusArtifactRef && item.deployment.artifactRef === focusArtifactRef)) ? "[FOCUS] " : ""}
                        {item.deployment.status} · {item.taskStatus} · {item.approvalStatus} · {item.deployment.mode} ·{" "}
                        {item.deployment.artifactRef} · strict:{item.deployment.strictMode ? "on" : "off"} ·
                        patch:{item.deployment.verifiedPatch ? "ok" : "failed"} ·
                        fail:{item.deployment.failureCode ?? "none"} · {item.rollbackId ?? "no-rollback"} ·{" "}
                        {new Date(item.updatedAt).toLocaleString("en-US")}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="panel-note">{t("project_detail.no_deployments")}</p>
                )}
              </div>
              <div className="deployment-card">
                <div className="metric-row">
                  <span>{t("project_detail.rollback_history")}</span>
                  <strong>{rollbackHistory.entries?.length ?? 0}</strong>
                </div>
                {rollbackHistory.entries?.length ? (
                  <ul className="bullets">
                    {rollbackHistory.entries.slice(0, 6).map((item) => (
                      <li key={item.rollback.rollbackId}>
                        {item.rollback.rollbackId} · {item.taskStatus} · {item.approvalStatus} ·{" "}
                        {item.rollback.safeWindowMinutes}m · {item.rollback.reason} ·{" "}
                        {new Date(item.updatedAt).toLocaleString("en-US")}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="panel-note">{t("project_detail.no_rollbacks")}</p>
                )}
              </div>
            </div>
          </section>

          <section className="panel" id="monitoring">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("project_detail.runs")}</div>
                <h2>{t("project_detail.run_history")}</h2>
              </div>
              <p>{t("project_detail.run_history_description")}</p>
            </div>
            <div className="stat-grid" style={{ marginBottom: 14 }}>
              <div className="suite-card">
                <div className="suite-title">
                  <strong>{t("project_detail.total_runs")}</strong>
                  <StatusPill tone="accent">{runs.length}</StatusPill>
                </div>
                <div className="project-copy">{t("project_detail.cross_stage_records")}</div>
              </div>
              <div className="suite-card">
                <div className="suite-title">
                  <strong>{t("project_detail.monitor_runs_label")}</strong>
                  <StatusPill tone={monitorFailedRuns.length > 0 ? "warn" : "good"}>{monitorRuns.length}</StatusPill>
                </div>
                <div className="project-copy">
                  {latestMonitorRun ? `Latest: ${formatDateTime(latestMonitorRun.startedAt, locale)}` : "No monitor run yet"}
                </div>
              </div>
              <div className="suite-card">
                <div className="suite-title">
                  <strong>{t("project_detail.rollback_runs_label")}</strong>
                  <StatusPill tone={rollbackRuns.length > 0 ? "warn" : "neutral"}>{rollbackRuns.length}</StatusPill>
                </div>
                <div className="project-copy">
                  {latestRollbackRun ? `Latest: ${formatDateTime(latestRollbackRun.startedAt, locale)}` : "No rollback run yet"}
                </div>
              </div>
              <div className="suite-card">
                <div className="suite-title">
                  <strong>{t("project_detail.completed_failed")}</strong>
                  <StatusPill tone={failedRunCount > 0 ? "warn" : "good"}>
                    {completedRunCount}/{failedRunCount}
                  </StatusPill>
                </div>
                <div className="project-copy">
                  {rolledBackRunCount} rolled back · {requeuedRunCount} pending/running
                </div>
              </div>
            </div>
            <div className="audit-meta" style={{ marginBottom: 14 }}>
              Latest run: {latestRun ? `${latestRun.runId} · ${latestRun.status} · ${latestRun.trigger}` : "n/a"} ·
              Latest monitor: {latestMonitorRun ? `${latestMonitorRun.status} at ${formatDateTime(latestMonitorRun.startedAt, locale)}` : "n/a"} ·
              Latest rollback: {latestRollbackRun ? `${latestRollbackRun.status} at ${formatDateTime(latestRollbackRun.startedAt, locale)}` : "n/a"}
            </div>
            <div className="project-foot" style={{ marginBottom: 14 }}>
              <span>{t("project_detail.filters")}</span>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <Link href={`/projects/${params.projectId}?runLimit=20`}>{t("project_detail.all")}</Link>
                <Link href={`/projects/${params.projectId}?runTrigger=monitor&runLimit=20`}>monitor</Link>
                <Link href={`/projects/${params.projectId}?runTrigger=rollback&runLimit=20`}>rollback</Link>
                <Link href={`/projects/${params.projectId}?runStatus=rolled_back&runLimit=20`}>rolled_back</Link>
                <Link href={`/projects/${params.projectId}?runTrigger=monitor&runStatus=failed&runLimit=20`}>monitor_failed</Link>
              </div>
            </div>
            <div className="stack">
              {runs.length ? (
                runs.map((run) => (
                  <article className="audit-card" key={run.runId}>
                    <div className="audit-head">
                      <strong className="audit-title">{run.trigger}</strong>
                      <StatusPill tone={runTone(run.status)}>{run.status}</StatusPill>
                    </div>
                    <div className="audit-meta">
                      {run.runId} · {formatDateTime(run.startedAt, locale)}
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.request")}</span>
                      <strong>
                        {run.runtimeRouteRequestMethod ?? "POST"} {run.runtimeRouteRequestPath ?? `/api/projects/${params.projectId}/sync`}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.risk")}</span>
                      <strong>{run.riskScore}</strong>
                    </div>
                    <div className="metric-row">
                      <span>{t("project_detail.connector_health")}</span>
                      <strong>{Object.values(run.connectorStatus).join(" · ") || state.connectionHealth}</strong>
                    </div>
                    <div className="audit-meta">{run.notes.join(" · ") || "No run notes."}</div>
                  </article>
                ))
              ) : (
                <div className="alert-box">{t("project_detail.no_run_history")}</div>
              )}
            </div>
          </section>

          <section className="panel" id="audit">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("project_detail.audit")}</div>
                <h2>{t("project_detail.event_trail")}</h2>
              </div>
              <p>{t("project_detail.audit_description")}</p>
            </div>
            <div className="stat-grid" style={{ marginBottom: 14 }}>
              <StatCard label="Audit entries" value={formatNumber(detail.audits.length)} caption="project audit records" accent />
              <StatCard label="Top action" value={auditActionTop?.[0] ?? "n/a"} caption={auditActionTop ? `${auditActionTop[1]} records` : "no audit actions"} />
              <StatCard label="Latest audit" value={latestAudit ? String(latestAudit.action ?? "n/a") : "n/a"} caption={latestAudit ? formatAuditTime(latestAudit.createdAt, locale) : "no audit trail"} />
              <StatCard label="Event spread" value={formatNumber(Object.keys(auditActionCounts).length)} caption="distinct audit actions" />
            </div>
            <div className="audit-grid">
              {detail.audits.map((audit) => (
                <article className="audit-card" key={`${String(audit.id)}-${String(audit.createdAt)}`}>
                  <div className="audit-head">
                    <strong className="audit-title">{String(audit.action)}</strong>
                    <span className="audit-meta">
                      {String(audit.actor)} · {formatAuditTime(audit.createdAt, locale)}
                    </span>
                  </div>
                  <div className="audit-meta">
                    {String(audit.id)} · {String(audit.taskId)}
                  </div>
                  <pre className="audit-payload">{stringifyAuditPayload(audit.payload)}</pre>
                </article>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
