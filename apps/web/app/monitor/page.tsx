import Link from "next/link";

import {
  getAcceptanceReport,
  getAlertLatestReport,
  getWorkerServiceHealth,
  getWorkspaceConnectorsHealth,
} from "@/lib/api";
import {
  fallbackAcceptanceReport,
  fallbackAlertReport,
  fallbackWorkerServiceHealthReport,
  fallbackWorkspaceConnectorsHealthReport,
} from "@/lib/fallback";
import { formatDateTime } from "@/lib/format";
import { getServerI18n } from "@/lib/i18n/server";

export default async function MonitorPage() {
  const { locale, t } = getServerI18n();
  let alerts = fallbackAlertReport();
  let connectors = fallbackWorkspaceConnectorsHealthReport();
  let worker = fallbackWorkerServiceHealthReport();
  let acceptance = fallbackAcceptanceReport();
  let dataSource: "live" | "fallback" = "fallback";

  try {
    [alerts, connectors, worker, acceptance] = await Promise.all([
      getAlertLatestReport(),
      getWorkspaceConnectorsHealth(),
      getWorkerServiceHealth(),
      getAcceptanceReport(),
    ]);
    dataSource = "live";
  } catch (error) {
    console.error("Failed to fetch monitor data:", error);
  }

  const activeAlerts = alerts.blocking.length + alerts.recoverable.length;
  const healthyProjects = Math.max(0, connectors.projectCount - connectors.degradedProjectCount - connectors.unavailableProjectCount);
  const healthLabel = alerts.blocking.length
    ? "blocked"
    : connectors.unavailableProjectCount || worker.status === "degraded"
      ? "degraded"
      : "healthy";
  const healthTone = healthLabel === "healthy" ? "good" : healthLabel === "blocked" ? "danger" : "warn";

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("monitor.eyebrow")}</div>
        <h1>{t("monitor.center_title")}</h1>
        <p className="hero-copy">{t("monitor.description")}</p>
        <div className="hero-meta">
          <span className={dataSource === "live" ? "status-badge good" : "status-badge warn"}>
            {dataSource === "live" ? t("monitor.live_api") : t("monitor.fallback_data")}
          </span>
          <span className={`status-badge ${healthTone}`}>{healthLabel}</span>
          <span className="status-badge accent">{t("monitor.generated")} {formatDateTime(alerts.generatedAt, locale)}</span>
        </div>
      </section>

      <section className="panel">
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">{t("monitor.healthy_projects")}</div>
            <div className="stat-value">{healthyProjects}/{connectors.projectCount}</div>
            <div className="stat-caption">{t("monitor.health_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("monitor.blocking_alerts")}</div>
            <div className="stat-value">{alerts.blocking.length}</div>
            <div className="stat-caption">{t("monitor.blocking_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("monitor.recoverable_alerts")}</div>
            <div className="stat-value">{alerts.recoverable.length}</div>
            <div className="stat-caption">{t("monitor.recoverable_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("monitor.rollback_ready")}</div>
            <div className="stat-value">{acceptance.rollbackReadyCount}</div>
            <div className="stat-caption">{t("monitor.rollback_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("monitor.real_read_coverage")}</div>
            <div className="stat-value">{Math.round(connectors.readRealCoveragePercent)}%</div>
            <div className="stat-caption">{t("monitor.real_read_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Worker</div>
            <div className="stat-value">{worker.status}</div>
            <div className="stat-caption">{t("monitor.latest_tick")} {worker.lastTickAt ? formatDateTime(worker.lastTickAt, locale) : t("monitor.none")}</div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("monitor.blocking_queue")}</div>
            <h2>{t("monitor.blocking_alerts")}</h2>
          </div>
          <span className={alerts.blocking.length ? "status-badge danger" : "status-badge good"}>
            {alerts.blocking.length ? `${alerts.blocking.length} ${t("monitor.open")}` : t("monitor.clear")}
          </span>
        </div>
        <div className="stack">
          {alerts.blocking.map((alert) => (
            <article className="audit-card" key={alert.alertId}>
              <div className="audit-head">
                <strong>{alert.summary}</strong>
                <span className="status-badge danger">{alert.failureCode}</span>
              </div>
              <div className="metric-row"><span>{t("monitor.provider")}</span><strong>{alert.provider}</strong></div>
              <div className="metric-row"><span>{t("monitor.affected_projects")}</span><strong>{alert.projectCount}</strong></div>
              <div className="project-foot">
                <span>{alert.category} · {alert.severity}</span>
                <Link href={alert.remediationPath ?? "/settings"}>{t("monitor.resolve_alert")}</Link>
              </div>
            </article>
          ))}
          {alerts.blocking.length === 0 ? <div className="empty-state">{t("monitor.no_blocking")}</div> : null}
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("monitor.recoverable_queue")}</div>
            <h2>{t("monitor.recoverable_alerts")}</h2>
          </div>
          <span className="status-badge warn">{alerts.recoverable.length} {t("monitor.open")}</span>
        </div>
        <div className="grid-three">
          {alerts.recoverable.map((alert) => (
            <article className="audit-card" key={alert.alertId}>
              <div className="audit-head">
                <strong>{alert.provider}</strong>
                <span className="status-badge warn">{alert.failureCode}</span>
              </div>
              <div className="project-copy">{alert.summary}</div>
              <div className="project-foot">
                <span>{alert.projectCount} projects</span>
                <Link href={alert.remediationPath ?? "/settings"}>{t("monitor.view_remediation")}</Link>
              </div>
            </article>
          ))}
          {alerts.recoverable.length === 0 ? <div className="empty-state">{t("monitor.no_recoverable")}</div> : null}
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("monitor.runtime_status")}</div>
            <h2>{t("monitor.runtime_chain")}</h2>
          </div>
          <Link href="/acceptance" className="button button-secondary button-link">{t("monitor.open_acceptance")}</Link>
        </div>
        <div className="grid-three">
          <article className="audit-card">
            <div className="audit-head"><strong>{t("monitor.provider_connections")}</strong><span className="status-badge">{connectors.totalConnectionCount}</span></div>
            <div className="metric-row"><span>{t("monitor.real")}</span><strong>{connectors.realConnectionCount}</strong></div>
            <div className="metric-row"><span>{t("monitor.fallback")}</span><strong>{connectors.fallbackConnectionCount}</strong></div>
            <div className="metric-row"><span>{t("monitor.unconfigured")}</span><strong>{connectors.unconfiguredConnectionCount}</strong></div>
            <div className="project-foot"><span>{connectors.strictGapCount} {t("monitor.strict_gaps")}</span><Link href="/settings">{t("monitor.configure_connections")}</Link></div>
          </article>
          <article className="audit-card">
            <div className="audit-head"><strong>{t("monitor.worker_service")}</strong><span className={`status-badge ${worker.status === "running" ? "good" : "warn"}`}>{worker.status}</span></div>
            <div className="metric-row"><span>{t("monitor.processed")}</span><strong>{worker.processed}</strong></div>
            <div className="metric-row"><span>{t("monitor.failures")}</span><strong>{worker.failures}</strong></div>
            <div className="metric-row"><span>{t("monitor.due_projects")}</span><strong>{worker.dueProjects}</strong></div>
            <div className="project-foot"><span>{worker.lastError ?? worker.notes[0] ?? t("monitor.none")}</span><Link href="/settings">{t("monitor.worker_settings")}</Link></div>
          </article>
          <article className="audit-card">
            <div className="audit-head"><strong>{t("monitor.release_readiness")}</strong><span className={acceptance.passed ? "status-badge good" : "status-badge danger"}>{acceptance.passed ? t("monitor.ready") : t("monitor.blocked")}</span></div>
            <div className="metric-row"><span>{t("monitor.active_alerts_label")}</span><strong>{activeAlerts}</strong></div>
            <div className="metric-row"><span>{t("monitor.failed_gates")}</span><strong>{acceptance.gates.filter((gate) => !gate.passed).length}</strong></div>
            <div className="metric-row"><span>{t("monitor.rollback_ready")}</span><strong>{acceptance.rollbackReadyCount}</strong></div>
            <div className="project-foot"><span>{t("monitor.preview_gate")}</span><Link href="/acceptance">{t("monitor.view_evidence")}</Link></div>
          </article>
        </div>
      </section>
    </div>
  );
}
