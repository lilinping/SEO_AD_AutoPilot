import Link from "next/link";

import { ApprovalsBulkActions } from "@/components/ApprovalsBulkActions";
import { getOverview } from "@/lib/api";
import { fallbackDashboard } from "@/lib/fallback";
import { formatDateTime } from "@/lib/format";
import { getServerI18n } from "@/lib/i18n/server";

export default async function ApprovalsPage() {
  const { locale, t } = getServerI18n();
  let overview = fallbackDashboard;
  let dataSource: "live" | "fallback" = "fallback";

  try {
    overview = await getOverview();
    dataSource = "live";
  } catch (error) {
    console.error("Failed to fetch approval queue:", error);
  }

  const pending = overview.approvals.filter((approval) => approval.status === "pending");
  const approved = overview.approvals.filter((approval) => approval.status === "approved");
  const rejected = overview.approvals.filter((approval) => approval.status === "rejected");

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("approvals.title")}</div>
        <h1>{t("approvals.title")}</h1>
        <p className="hero-copy">{t("approvals.description")}</p>
        <div className="hero-meta">
          <span className={dataSource === "live" ? "status-badge good" : "status-badge warn"}>
            {dataSource === "live" ? t("approvals.live_api") : t("approvals.fallback_data")}
          </span>
          <span className="status-badge accent">{t("approvals.generated")} {formatDateTime(overview.generatedAt, locale)}</span>
          <span className={pending.length ? "status-badge warn" : "status-badge good"}>
            {pending.length ? `${pending.length} ${t("approvals.pending_suffix")}` : t("approvals.queue_clear")}
          </span>
        </div>
      </section>

      <section className="panel">
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">{t("approvals.pending")}</div>
            <div className="stat-value">{pending.length}</div>
            <div className="stat-caption">{t("approvals.awaiting_decision")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("approvals.approved")}</div>
            <div className="stat-value">{approved.length}</div>
            <div className="stat-caption">{t("approvals.release_ready")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("approvals.rejected")}</div>
            <div className="stat-value">{rejected.length}</div>
            <div className="stat-caption">{t("approvals.release_blocked")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("approvals.high_risk")}</div>
            <div className="stat-value">
              {overview.tasks.filter((task) => task.riskScore >= overview.policy.blockAutoDeployThreshold).length}
            </div>
            <div className="stat-caption">{t("approvals.risk_threshold")} {overview.policy.blockAutoDeployThreshold}</div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("approvals.decision_queue")}</div>
            <h2>{t("approvals.pending_tasks")}</h2>
          </div>
          <Link href="/projects" className="button button-secondary button-link">{t("approvals.view_projects")}</Link>
        </div>
        {pending.length ? (
          <ApprovalsBulkActions
            approvals={pending}
            projects={overview.projects}
            tasks={overview.tasks}
          />
        ) : (
          <div className="empty-state">{t("approvals.empty_queue")}</div>
        )}
      </section>

      {approved.length || rejected.length ? (
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">{t("approvals.decision_history")}</div>
              <h2>{t("approvals.current_decisions")}</h2>
            </div>
          </div>
          <div className="grid-three">
            {[...approved, ...rejected].map((approval) => {
              const task = overview.tasks.find((item) => item.taskId === approval.taskId);
              const project = overview.projects.find((item) => item.projectId === task?.projectId);
              return (
                <article className="audit-card" key={approval.approvalId}>
                  <div className="audit-head">
                    <strong>{project?.name ?? approval.taskId}</strong>
                    <span className={approval.status === "approved" ? "status-badge good" : "status-badge danger"}>
                      {approval.status}
                    </span>
                  </div>
                  <div className="project-copy">{approval.decisionHint}</div>
                  <div className="project-foot">
                    <span>{approval.riskSummary}</span>
                    {project ? <Link href={`/projects/${project.projectId}`}>{t("approvals.open_project")}</Link> : null}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      ) : null}
    </div>
  );
}
