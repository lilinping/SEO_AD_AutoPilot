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

function formatAuditTime(value: unknown): string {
  if (value instanceof Date || typeof value === "string") {
    return formatDateTime(value);
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
  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">Project detail</div>
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
              risk {project.riskScore}
            </StatusPill>
            <StatusPill tone="neutral">{project.deploymentMode ?? "preview only"}</StatusPill>
            <StatusPill tone={connectionTone(state.connectionHealth)}>{state.connectionHealth}</StatusPill>
          </div>
        </div>
        <div className="stat-grid" style={{ marginTop: 16 }}>
          <StatCard label="Real connectors" value={formatNumber(connectionEvidenceRealCount)} caption="project connectors in real mode" accent />
          <StatCard label="Fallback connectors" value={formatNumber(connectionEvidenceFallbackCount)} caption="project connectors still on fallback" />
          <StatCard label="Strict-ready" value={formatNumber(connectionEvidenceStrictEligibleCount)} caption="connectors eligible for strict mode" />
          <StatCard label="Real writeback" value={formatNumber(deploymentRealWritebackCount)} caption="deployments with provider artifact evidence" />
          <StatCard label="Verified patches" value={formatNumber(deploymentVerifiedCount)} caption="deployments with pre/post verification" />
          <StatCard label="Market sources" value={`${marketEvidenceProviders.strictReadyCount}/${marketEvidenceProviders.providerCount}`} caption="trend/news/qa strict-ready providers" />
          <StatCard label="Latest run" value={latestRun?.runId ?? "n/a"} caption={latestRun ? `${latestRun.status} · ${latestRun.trigger}` : "no run history"} />
        </div>
        {connectionEvidenceTop || deploymentLatest ? (
          <div className="alert-box" style={{ marginTop: 12 }}>
            {connectionEvidenceTop ? (
              <>
                Top connector: {connectionEvidenceTop.provider} · {connectionEvidenceTop.providerMode} · {connectionEvidenceTop.recentEvidenceLabel ?? "n/a"}
              </>
            ) : null}
            {connectionEvidenceTop && deploymentLatest ? " · " : null}
            {deploymentLatest ? (
              <>
                Latest deploy: {deploymentLatest.deployment.deploymentId} · {deploymentLatest.deployment.mode} · {deploymentLatest.deployment.status}
              </>
            ) : null}
          </div>
        ) : null}
        {focusTaskId || focusArtifactRef ? (
          <div className="alert-box" style={{ marginTop: 12 }}>
            Focus context
            {focusTaskId ? ` · taskId=${focusTaskId}` : ""}
            {focusArtifactRef ? ` · artifactRef=${focusArtifactRef}` : ""}
          </div>
        ) : null}
        <div className="project-foot" style={{ marginTop: 12 }}>
          <span>Jump to</span>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <a href="#connections">connections</a>
            <a href="#deployment">deployment</a>
            <a href="#billing">billing</a>
            <a href="#runs">runs</a>
            <a href="#audit">audit</a>
          </div>
        </div>
      </section>

      <div className="project-layout">
        <div className="detail-stack">
          <section className="panel" id="connections">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Profile</div>
                <h2>Site profile</h2>
              </div>
              <p>{formatDateTime(project.updatedAt)}</p>
            </div>
            <div className="stack">
              <div className="metric-row">
                <span>Brand voice</span>
                <strong>{workflow.siteProfile.brandVoice}</strong>
              </div>
              <div className="metric-row">
                <span>Pages</span>
                <strong>{workflow.siteProfile.pageCountEstimate}</strong>
              </div>
              <div className="metric-row">
                <span>Trust signals</span>
                <strong>{workflow.siteProfile.trustSignals.join(" · ")}</strong>
              </div>
              <div className="metric-row">
                <span>Auto cruise</span>
                <strong>{state.autoCruiseEnabled ? `on · ${state.syncIntervalMinutes}m` : "off"}</strong>
              </div>
              <div className="metric-row">
                <span>Cruise state</span>
                <strong>
                  {cruiseHealth.dueNow ? "due now" : "scheduled"}
                  {cruiseHealth.overdue ? " · overdue" : ""}
                </strong>
              </div>
              <div className="metric-row">
                <span>Cruise next run</span>
                <strong>{cruiseHealth.nextSyncAt ? formatDateTime(cruiseHealth.nextSyncAt) : "not scheduled"}</strong>
              </div>
              <ProjectCruiseToggleAction
                projectId={project.projectId}
                autoCruiseEnabled={state.autoCruiseEnabled}
                syncIntervalMinutes={state.syncIntervalMinutes}
                connections={detail.connections}
              />
              <div className="metric-row">
                <span>Last sync</span>
                <strong>{state.lastSyncAt ? formatDateTime(state.lastSyncAt) : "never"}</strong>
              </div>
              <div className="metric-row">
                <span>Next sync</span>
                <strong>{state.nextSyncAt ? formatDateTime(state.nextSyncAt) : "not scheduled"}</strong>
              </div>
            </div>
          </section>

          <section className="panel" id="deployment">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Connections</div>
                <h2>Source health</h2>
              </div>
              <p>{workflow.ingestionReport?.status ?? "synthetic"}</p>
            </div>
            <div className="stat-grid">
              <StatCard label="Real" value={formatNumber(connectionEvidenceRealCount)} caption="project connectors in real mode" accent />
              <StatCard label="Fallback" value={formatNumber(connectionEvidenceFallbackCount)} caption="project connectors in fallback mode" />
              <StatCard label="Unconfigured" value={formatNumber(connectionEvidenceUnconfiguredCount)} caption="project connectors without config" />
              <StatCard label="Strict-ready" value={formatNumber(connectionEvidenceStrictEligibleCount)} caption="connectors eligible for strict mode" />
            </div>
            {connectionEvidenceTop ? (
              <div className="audit-meta" style={{ marginTop: 12 }}>
                Top evidence: {connectionEvidenceTop.provider} · {connectionEvidenceTop.providerMode} ·{" "}
                {connectionEvidenceTop.recentEvidenceLabel ?? "n/a"} ·{" "}
                {connectionEvidenceTop.recentEvidenceAt ? formatDateTime(connectionEvidenceTop.recentEvidenceAt) : "n/a"}
              </div>
            ) : null}
            <div className="suite-grid">
              <article className="suite-card">
                <div className="metric-row">
                  <span>Project health</span>
                  <strong>{projectConnectorsHealth.connectionHealth}</strong>
                </div>
                <div className="metric-row">
                  <span>Real/Fallback/Unconfigured</span>
                  <strong>
                    {projectConnectorsHealth.realConnectionCount}/{projectConnectorsHealth.fallbackConnectionCount}/{projectConnectorsHealth.unconfiguredConnectionCount}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>Last real read evidence</span>
                  <strong>{projectConnectorsHealth.readRealLastEvidenceAt ? formatDateTime(projectConnectorsHealth.readRealLastEvidenceAt) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Last real write evidence</span>
                  <strong>{projectConnectorsHealth.writeRealLastEvidenceAt ? formatDateTime(projectConnectorsHealth.writeRealLastEvidenceAt) : "n/a"}</strong>
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
                    <li>Last success: {connection.lastSuccessAt ? formatDateTime(connection.lastSuccessAt) : "n/a"}</li>
                    <li>Last error: {connection.lastErrorAt ? formatDateTime(connection.lastErrorAt) : "n/a"}</li>
                    <li>Recent evidence: {connection.recentEvidenceLabel ?? "n/a"}</li>
                    <li>Evidence ref: {connection.recentEvidenceRef ?? "n/a"}</li>
                    <li>Evidence time: {connection.recentEvidenceAt ? formatDateTime(connection.recentEvidenceAt) : "n/a"}</li>
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
                  <span>Ingestion report</span>
                  <strong>{workflow.ingestionReport.reportId}</strong>
                </div>
                <div className="metric-row">
                  <span>Evidence</span>
                  <strong>{workflow.ingestionReport.evidence.length} sources</strong>
                </div>
                <div className="metric-row">
                  <span>Notes</span>
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
                <div className="eyebrow">Connector history</div>
                <h2>Recent probe and refresh events</h2>
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
                    <span>Action</span>
                    <strong>{entry.action}</strong>
                  </div>
                  <div className="metric-row">
                    <span>Created</span>
                    <strong>{formatDateTime(entry.createdAt)}</strong>
                  </div>
                  <div className="metric-row">
                    <span>Auth source</span>
                    <strong>{entry.authSource ?? "none"}</strong>
                  </div>
                  <div className="metric-row">
                    <span>Failure</span>
                    <strong>{entry.failureCode ?? "none"}</strong>
                  </div>
                  <div className="metric-row">
                    <span>Fallback</span>
                    <strong>{entry.fallbackReason ?? "none"}</strong>
                  </div>
                  <div className="metric-row">
                    <span>Latency</span>
                    <strong>{entry.latencyMs != null ? `${entry.latencyMs}ms` : "n/a"}</strong>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="panel" id="billing">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Billing</div>
                <h2>Settlement history</h2>
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
              <span>Workspace view</span>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <Link href={`/settings?billingProjectId=${encodeURIComponent(params.projectId)}#billing`}>Open billing filter</Link>
                <Link href={`/monitor?billingProjectId=${encodeURIComponent(params.projectId)}#billing-history`}>Monitor replay</Link>
                <Link href={`/acceptance?billingProjectId=${encodeURIComponent(params.projectId)}#billing-history`}>Acceptance replay</Link>
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
                <div className="project-copy">No settlement executions recorded for this project.</div>
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
                      <span>Created</span>
                      <strong>{formatDateTime(entry.createdAt)}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Gateway provider</span>
                      <strong>{entry.gatewayProviderName ?? "n/a"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Gateway route</span>
                      <strong>{entry.gatewayRouteProviderName ?? "n/a"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Route reason</span>
                      <strong>{entry.gatewayRouteReason ?? "n/a"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Request</span>
                      <strong>
                        {entry.requestMethod ?? "POST"} {entry.requestPath ?? "/api/billing/settlement/execute"}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>Due</span>
                      <strong>{entry.dueCents} cents</strong>
                    </div>
                    <div className="metric-row">
                      <span>Ready</span>
                      <strong>{entry.settlementReady ? "yes" : "no"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Gateway</span>
                      <strong>{entry.gatewayReady ? "ready" : "partial"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Route</span>
                      <strong>
                        {entry.gatewayRouteProviderName ?? "n/a"} · priority {entry.gatewayRoutePriority ?? "n/a"} · {entry.gatewayRouteReady ? "ready" : "fallback"}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>Reason</span>
                      <strong>{entry.gatewayRouteReason ?? "n/a"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Failure</span>
                      <strong>{entry.failureCode ?? "none"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Retryable</span>
                      <strong>{entry.retryable ? "yes" : "no"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Mode</span>
                      <strong>{entry.dryRun ? "dry-run" : "live"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Project</span>
                      <strong>{entry.projectName ?? entry.projectId ?? params.projectId}</strong>
                    </div>
                    <div className="project-foot">
                      <span>Workspace replay</span>
                      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                        <Link href={`/monitor?billingProjectId=${encodeURIComponent(params.projectId)}#billing-history`}>Monitor</Link>
                        <Link href={`/acceptance?billingProjectId=${encodeURIComponent(params.projectId)}#billing-history`}>Acceptance</Link>
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
                  <div className="eyebrow">Market evidence</div>
                  <h2>Trend, news, and QA sources</h2>
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
                {marketEvidenceHealth.latestFetchedAt ? formatDateTime(marketEvidenceHealth.latestFetchedAt) : "n/a"} ·
                Stale: {marketEvidenceHealth.staleCount}
              </div>
              <div className="suite-grid" style={{ marginBottom: 14 }}>
                <article className="suite-card">
                  <div className="suite-title">
                    <strong>Provider readiness</strong>
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
                    <strong>Strict refresh ready</strong>
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
                            <span>Connected / Synthetic / Failed</span>
                            <strong>{summary.connectedCount} / {summary.syntheticCount} / {summary.failedCount}</strong>
                          </div>
                          <div className="metric-row">
                            <span>Latest fetched</span>
                            <strong>{summary.latestFetchedAt ? formatDateTime(summary.latestFetchedAt) : "n/a"}</strong>
                          </div>
                          <div className="metric-row">
                            <span>Average latency</span>
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
                          {item.summary} · {item.status} · {item.sourceRef ?? "n/a"} · {item.fetchedAt ? formatDateTime(item.fetchedAt) : "n/a"}
                        </li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          <section className="panel" id="audit">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Opportunities</div>
                <h2>SEO / AD / technical / UX</h2>
              </div>
              <p>Each opportunity is scored and linked to a skill-backed step in the release plan.</p>
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
                  <div className="eyebrow">Content plan</div>
                  <h2>Topic clusters and publishing order</h2>
                </div>
                <p>{contentStrategy.pillarPage}</p>
              </div>
              <div className="stack">
                <div className="metric-row">
                  <span>Pillar keyword</span>
                  <strong>{contentStrategy.pillarKeyword}</strong>
                </div>
                <div className="metric-row">
                  <span>Intent</span>
                  <strong>{contentStrategy.pillarIntent}</strong>
                </div>
                <div className="metric-row">
                  <span>Clusters</span>
                  <strong>{formatNumber(contentStrategy.topicClusters.length)}</strong>
                </div>
                <div className="metric-row">
                  <span>Market signals</span>
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
                  <div className="eyebrow">Ad audit</div>
                  <h2>Placement and policy fit</h2>
                </div>
                <p>{adAudit.reason}</p>
              </div>
              <div className="stack">
                <div className="metric-row">
                  <span>Ad allowed</span>
                  <strong>{adAudit.adAllowed ? "yes" : "no"}</strong>
                </div>
                <div className="metric-row">
                  <span>Connector status</span>
                  <strong>{adAudit.adConnectorStatus ?? "unknown"}</strong>
                </div>
                <div className="metric-row">
                  <span>Provider family</span>
                  <strong>{adAudit.adProviderFamily ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Provider name</span>
                  <strong>{adAudit.adProviderName ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Provider ref</span>
                  <strong>{adAudit.adProviderRef ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Inventory</span>
                  <strong>{adAudit.adInventoryStatus ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Impressions/day</span>
                  <strong>{typeof adAudit.adImpressionsDaily === "number" ? formatNumber(adAudit.adImpressionsDaily) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Clicks/day</span>
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
                  <span>Revenue/day</span>
                  <strong>{typeof adAudit.adRevenueEstimateDaily === "number" ? adAudit.adRevenueEstimateDaily.toFixed(2) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Revenue/month</span>
                  <strong>{typeof adAudit.adRevenueEstimateMonthly === "number" ? adAudit.adRevenueEstimateMonthly.toFixed(2) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Settled/day</span>
                  <strong>{typeof adAudit.adRevenueSettledDaily === "number" ? adAudit.adRevenueSettledDaily.toFixed(2) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Settlement</span>
                  <strong>{adAudit.adRevenueSettlementWindow ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Currency</span>
                  <strong>{adAudit.adRevenueCurrency ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Policy tier</span>
                  <strong>{adAudit.adPolicyTier ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Payout threshold</span>
                  <strong>{typeof adAudit.adPayoutThreshold === "number" ? adAudit.adPayoutThreshold.toFixed(2) : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Provider program</span>
                  <strong>{adAudit.adProviderProgram ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Geo coverage</span>
                  <strong>{adAudit.adGeoCoverage.join(" · ") || "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Strict publish</span>
                  <strong>{adAudit.strictPublishEligible ? "eligible" : "blocked"}</strong>
                </div>
                <div className="metric-row">
                  <span>Providers</span>
                  <strong>{adAudit.providerExamples.join(" · ") || "none"}</strong>
                </div>
                {adAudit.failureCode ? (
                  <div className="metric-row">
                    <span>Failure code</span>
                    <strong>{adAudit.failureCode}</strong>
                  </div>
                ) : null}
              {adAudit.fallbackReason ? (
                <div className="metric-row">
                  <span>Fallback reason</span>
                  <strong>{adAudit.fallbackReason}</strong>
                </div>
              ) : null}
              <div className="project-foot" style={{ marginTop: 14 }}>
                <span>Workspace replay</span>
                <Link href={`/monitor?adAuditProjectId=${encodeURIComponent(project.projectId)}#ad-audit-history`}>Open ad audit replay</Link>
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
                  <div className="eyebrow">Technical SEO</div>
                  <h2>Crawlability, on-page, content, and performance</h2>
                </div>
                <p>{technicalSeo.overallHealth}</p>
              </div>
              <div className="stack">
                <div className="metric-row">
                  <span>Health</span>
                  <strong>{technicalSeo.overallHealth}</strong>
                </div>
                <div className="metric-row">
                  <span>Action plan</span>
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
                  <div className="eyebrow">Technical SEO patch</div>
                  <h2>Pre/post verification audit</h2>
                </div>
                <StatusPill tone={technicalSeoPatch.verifiedPatch ? "good" : "danger"}>
                  {technicalSeoPatch.verifiedPatch ? "verified" : "failed"}
                </StatusPill>
              </div>
              <div className="stack">
                <div className="metric-row">
                  <span>Strict mode</span>
                  <strong>{technicalSeoPatch.strictMode ? "on" : "off"}</strong>
                </div>
                <div className="metric-row">
                  <span>Checked targets</span>
                  <strong>{String((technicalSeoPatch.patchAudit?.checkedTargets as number | undefined) ?? 0)}</strong>
                </div>
                <div className="metric-row">
                  <span>Passed / failed</span>
                  <strong>
                    {String((technicalSeoPatch.patchAudit?.passedTargets as number | undefined) ?? 0)} /{" "}
                    {String((technicalSeoPatch.patchAudit?.failedTargets as number | undefined) ?? 0)}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>Schema types (before/after)</span>
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

          <PreviewDiff preview={workflow.preview} />
        </div>

        <div className="detail-stack">
          <section className="panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Approval</div>
                <h2>Gate status</h2>
              </div>
              <p>{workflow.approvalRequest.decisionHint}</p>
            </div>
            <div className="stack">
              <div className="metric-row">
                <span>Approval status</span>
                <strong>{workflow.approvalRequest.status}</strong>
              </div>
              <div className="metric-row">
                <span>Risk summary</span>
                <strong>{workflow.approvalRequest.riskSummary}</strong>
              </div>
              <div className="metric-row">
                <span>Approvers</span>
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
                  <div className="eyebrow">Experiment routing</div>
                  <h2>Runtime assignment</h2>
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
                      <span>Variant</span>
                      <strong>{assignment.assignedVariantName ?? assignment.controlVariantName}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Bucket</span>
                      <strong>
                        {assignment.bucketRoll}/{assignment.bucketSize}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>Scope</span>
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
                  <div className="eyebrow">Localization routing</div>
                  <h2>Runtime cluster assignment</h2>
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
                      <span>Route prefix</span>
                      <strong>{assignment.routePrefix}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Scope</span>
                      <strong>
                        {assignment.matchedByProject ? "project" : ""}
                        {assignment.matchedByLocale ? `${assignment.matchedByProject ? " · " : ""}locale` : ""}
                        {assignment.matchedByHost ? `${assignment.matchedByProject || assignment.matchedByLocale ? " · " : ""}host` : ""}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>Canonical</span>
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
                  <div className="eyebrow">Runtime route</div>
                  <h2>Request-chain resolution</h2>
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
                  <span>Experiment</span>
                  <strong>
                    {runtimeRoute.experimentAssignment?.assignments.find((assignment) => assignment.eligible && assignment.assignedVariantName)?.assignedVariantName ??
                      "preview"}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>Locale route</span>
                  <strong>
                    {runtimeRoute.localizationAssignment?.assignments.find(
                      (assignment) => assignment.clusterReady && (assignment.matchedByProject || assignment.matchedByLocale || assignment.matchedByHost),
                    )?.routePrefix ?? "preview"}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>Request</span>
                  <strong>
                    {runtimeRoute.requestMethod ?? "POST"} {runtimeRoute.requestPath ?? `/api/projects/${runtimeRoute.projectId}/runtime-route`}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>Providers</span>
                  <strong>{Object.entries(runtimeRoute.resolvedProviders).map(([suite, provider]) => `${suite}:${provider}`).join(" · ") || "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Analysis entry</span>
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

          <section className="panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Gateway providers</div>
                <h2>Runtime-edge and visual-farm readiness</h2>
              </div>
              <p>Project-scoped provider status for the two publish chains that feed runtime routing and visual regression.</p>
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
                <div className="eyebrow">Runtime route history</div>
                <h2>Route replay</h2>
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
                caption={runtimeRouteHistory.entries[0] ? formatDateTime(runtimeRouteHistory.entries[0].startedAt) : "no route history yet"}
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
                      {run.runId} · {formatDateTime(run.startedAt)}
                    </div>
                    <div className="metric-row">
                      <span>Request</span>
                      <strong>
                        {run.runtimeRouteRequestMethod ?? "POST"} {run.runtimeRouteRequestPath ?? `/api/projects/${params.projectId}/sync`}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>Route</span>
                      <strong>
                        {run.runtimeRouteSummary ?? "n/a"} · route {run.gatewayRouteProviderName ?? "n/a"} · fallback {run.gatewayRouteFallbackProviderName ?? "n/a"} · priority{" "}
                        {run.gatewayRoutePriority ?? "n/a"}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>Execution</span>
                      <strong>
                        {run.runtimeRouteExecutionMode ?? "preview"} · {run.runtimeRouteExecutionAction ?? "serve_preview"} · {run.runtimeRouteExecutionEntrypoint ?? `/api/projects/${params.projectId}/sync`}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>Reason</span>
                      <strong>{run.runtimeRouteExecutionReason ?? "n/a"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Risk</span>
                      <strong>{run.riskScore}</strong>
                    </div>
                    <div className="metric-row">
                      <span>State</span>
                      <strong>{run.runtimeRouteReady ? "ready" : "preview-only"}</strong>
                    </div>
                  </article>
                ))
              ) : (
                <div className="alert-box">No runtime route history yet for this project.</div>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Gateway providers</div>
                <h2>Billing and model readiness</h2>
              </div>
              <p>Project view for the remaining routed control planes: settlement and model execution.</p>
            </div>
            <div className="suite-grid">
              <article className="suite-card">
                <div className="suite-title">
                  <strong>Billing gateway</strong>
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
                  <strong>Model gateway</strong>
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
                <div className="eyebrow">Review</div>
                <h2>UX / policy notes</h2>
              </div>
              <p>Issues that would affect trust or CTA clarity are surfaced before deployment.</p>
            </div>
            <div className="stack">
              <div className="metric-row">
                <span>UX score</span>
                <strong>{workflow.uxReview.score}</strong>
              </div>
              <div className="metric-row">
                <span>Issues</span>
                <strong>{workflow.uxReview.issues.join(" · ") || "None"}</strong>
              </div>
              <div className="metric-row">
                <span>Notes</span>
                <strong>{workflow.uxReview.notes.join(" · ")}</strong>
              </div>
            </div>
            {adOpportunity ? (
              <div className="alert-box" style={{ marginTop: 14 }}>
                AD opportunity: {adOpportunity.title}
              </div>
            ) : null}
          </section>

          <section className="panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Deployment</div>
                <h2>Release and rollback</h2>
              </div>
              <p>Promotion status, metrics, and reversal safety are surfaced together instead of being hidden in logs.</p>
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
                {deploymentLatest.deployment.status} · updated {formatDateTime(deploymentLatest.updatedAt)}
              </div>
            ) : null}
            {rollbackLatest ? (
              <div className="audit-meta">
                Latest rollback: {rollbackLatest.rollback.rollbackId} · {rollbackLatest.rollback.reason} ·{" "}
                {formatDateTime(rollbackLatest.updatedAt)}
              </div>
            ) : null}
            <div className="deployment-grid">
              <div className="deployment-card">
                <div className="metric-row">
                  <span>Status</span>
                  <strong>{workflow.deployment?.status ?? "not scheduled"}</strong>
                </div>
                <div className="metric-row">
                  <span>Mode</span>
                  <strong>{workflow.deployment?.mode ?? workflow.plan.deploymentMode}</strong>
                </div>
                <div className="metric-row">
                  <span>Rollback ready</span>
                  <strong>{workflow.deployment?.rollbackReady ? "yes" : "pending"}</strong>
                </div>
                <div className="metric-row">
                  <span>Strict mode</span>
                  <strong>{workflow.deployment?.strictMode ? "on" : "off"}</strong>
                </div>
                <div className="metric-row">
                  <span>Verified patch</span>
                  <strong>{workflow.deployment?.verifiedPatch ? "yes" : "no"}</strong>
                </div>
                <div className="metric-row">
                  <span>Artifact</span>
                  <strong>{workflow.deployment?.artifactRef ?? workflow.preview.previewId}</strong>
                </div>
                <div className="metric-row">
                  <span>Provider id</span>
                  <strong>{workflow.deployment?.providerArtifactId ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Provider url</span>
                  <strong>{workflow.deployment?.providerUrl ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Auth source</span>
                  <strong>{workflow.deployment?.writebackAuthSource ?? "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Writeback provider</span>
                  <strong>{String(workflow.deployment?.writebackSummary?.provider ?? "n/a")}</strong>
                </div>
                <div className="metric-row">
                  <span>Writeback attempts</span>
                  <strong>{workflow.deployment?.writebackAttempts?.length ?? 0}</strong>
                </div>
                <div className="metric-row">
                  <span>Writeback summary</span>
                  <strong>
                    {`${String(workflow.deployment?.writebackSummary?.successCount ?? 0)}/${String(workflow.deployment?.writebackSummary?.failedCount ?? 0)}/${String(workflow.deployment?.writebackSummary?.skippedCount ?? 0)}`}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>Last endpoint</span>
                  <strong>{String(workflow.deployment?.writebackSummary?.lastEndpoint ?? "n/a")}</strong>
                </div>
                <div className="metric-row">
                  <span>Average latency</span>
                  <strong>
                    {typeof workflow.deployment?.writebackSummary?.averageLatencyMs === "number"
                      ? `${String(workflow.deployment.writebackSummary.averageLatencyMs)}ms`
                      : "n/a"}
                  </strong>
                </div>
                <div className="metric-row">
                  <span>Writeback failure</span>
                  <strong>{String(workflow.deployment?.writebackSummary?.failureCode ?? "none")}</strong>
                </div>
                <div className="metric-row">
                  <span>Successful endpoints</span>
                  <strong>{Array.isArray(workflow.deployment?.writebackSummary?.successfulEndpoints) ? workflow.deployment.writebackSummary.successfulEndpoints.join(" · ") || "none" : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Failed endpoints</span>
                  <strong>{Array.isArray(workflow.deployment?.writebackSummary?.failedEndpoints) ? workflow.deployment.writebackSummary.failedEndpoints.join(" · ") || "none" : "n/a"}</strong>
                </div>
                <div className="metric-row">
                  <span>Patch manifest</span>
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
                    <span>Failure code</span>
                    <strong>{workflow.deployment.failureCode}</strong>
                  </div>
                ) : null}
                {workflow.deployment?.fallbackReason ? (
                  <div className="metric-row">
                    <span>Fallback reason</span>
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
                  <span>Rollback ID</span>
                  <strong>{workflow.rollbackBundle?.rollbackId ?? "pending"}</strong>
                </div>
                <div className="metric-row">
                  <span>Safe window</span>
                  <strong>{workflow.rollbackBundle ? `${workflow.rollbackBundle.safeWindowMinutes}m` : `${workflow.plan.riskScore >= 80 ? 5 : 10}m`}</strong>
                </div>
                <div className="metric-row">
                  <span>Expected effect</span>
                  <strong>{workflow.rollbackBundle?.expectedEffect ?? "Restore the previous stable release."}</strong>
                </div>
                {workflow.metricSnapshot ? (
                  <div className="stack" style={{ marginTop: 12 }}>
                    <div className="metric-row">
                      <span>SEO score</span>
                      <strong>{workflow.metricSnapshot.seoScore}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Ad fit</span>
                      <strong>{workflow.metricSnapshot.adFitScore}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Traffic delta</span>
                      <strong>{workflow.metricSnapshot.trafficDelta}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Metric sources</span>
                      <strong>{Object.entries(workflow.metricSnapshot.sourceStatus).map(([key, value]) => `${key}:${value}`).join(" · ") || "synthetic"}</strong>
                    </div>
                    <div className="metric-row">
                      <span>External metrics</span>
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
                  <span>Deployment history</span>
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
                  <p className="panel-note">No deployment records have been captured for this project yet.</p>
                )}
              </div>
              <div className="deployment-card">
                <div className="metric-row">
                  <span>Rollback history</span>
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
                  <p className="panel-note">No rollback records have been captured for this project yet.</p>
                )}
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Runs</div>
                <h2>Run history</h2>
              </div>
              <p>Sync, monitor, deploy, and rollback now share one auditable run timeline.</p>
            </div>
            <div className="stat-grid" style={{ marginBottom: 14 }}>
              <div className="suite-card">
                <div className="suite-title">
                  <strong>Total runs</strong>
                  <StatusPill tone="accent">{runs.length}</StatusPill>
                </div>
                <div className="project-copy">Cross-stage execution records</div>
              </div>
              <div className="suite-card">
                <div className="suite-title">
                  <strong>Monitor runs</strong>
                  <StatusPill tone={monitorFailedRuns.length > 0 ? "warn" : "good"}>{monitorRuns.length}</StatusPill>
                </div>
                <div className="project-copy">
                  {latestMonitorRun ? `Latest: ${formatDateTime(latestMonitorRun.startedAt)}` : "No monitor run yet"}
                </div>
              </div>
              <div className="suite-card">
                <div className="suite-title">
                  <strong>Rollback runs</strong>
                  <StatusPill tone={rollbackRuns.length > 0 ? "warn" : "neutral"}>{rollbackRuns.length}</StatusPill>
                </div>
                <div className="project-copy">
                  {latestRollbackRun ? `Latest: ${formatDateTime(latestRollbackRun.startedAt)}` : "No rollback run yet"}
                </div>
              </div>
              <div className="suite-card">
                <div className="suite-title">
                  <strong>Completed / Failed</strong>
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
              Latest monitor: {latestMonitorRun ? `${latestMonitorRun.status} at ${formatDateTime(latestMonitorRun.startedAt)}` : "n/a"} ·
              Latest rollback: {latestRollbackRun ? `${latestRollbackRun.status} at ${formatDateTime(latestRollbackRun.startedAt)}` : "n/a"}
            </div>
            <div className="project-foot" style={{ marginBottom: 14 }}>
              <span>Filters</span>
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <Link href={`/projects/${params.projectId}?runLimit=20`}>all</Link>
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
                      {run.runId} · {formatDateTime(run.startedAt)}
                    </div>
                    <div className="metric-row">
                      <span>Request</span>
                      <strong>
                        {run.runtimeRouteRequestMethod ?? "POST"} {run.runtimeRouteRequestPath ?? `/api/projects/${params.projectId}/sync`}
                      </strong>
                    </div>
                    <div className="metric-row">
                      <span>Risk</span>
                      <strong>{run.riskScore}</strong>
                    </div>
                    <div className="metric-row">
                      <span>Connector health</span>
                      <strong>{Object.values(run.connectorStatus).join(" · ") || state.connectionHealth}</strong>
                    </div>
                    <div className="audit-meta">{run.notes.join(" · ") || "No run notes."}</div>
                  </article>
                ))
              ) : (
                <div className="alert-box">No run history yet for this project.</div>
              )}
            </div>
          </section>

          <section className="panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">Audit</div>
                <h2>Event trail</h2>
              </div>
              <p>Each action is recorded so approvals, deploys, and rollbacks can be traced from the console.</p>
            </div>
            <div className="stat-grid" style={{ marginBottom: 14 }}>
              <StatCard label="Audit entries" value={formatNumber(detail.audits.length)} caption="project audit records" accent />
              <StatCard label="Top action" value={auditActionTop?.[0] ?? "n/a"} caption={auditActionTop ? `${auditActionTop[1]} records` : "no audit actions"} />
              <StatCard label="Latest audit" value={latestAudit ? String(latestAudit.action ?? "n/a") : "n/a"} caption={latestAudit ? formatAuditTime(latestAudit.createdAt) : "no audit trail"} />
              <StatCard label="Event spread" value={formatNumber(Object.keys(auditActionCounts).length)} caption="distinct audit actions" />
            </div>
            <div className="audit-grid">
              {detail.audits.map((audit) => (
                <article className="audit-card" key={`${String(audit.id)}-${String(audit.createdAt)}`}>
                  <div className="audit-head">
                    <strong className="audit-title">{String(audit.action)}</strong>
                    <span className="audit-meta">
                      {String(audit.actor)} · {formatAuditTime(audit.createdAt)}
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
