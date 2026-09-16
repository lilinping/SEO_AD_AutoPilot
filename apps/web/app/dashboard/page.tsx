import Link from "next/link";

import { getOverview } from "@/lib/api";
import { fallbackDashboard } from "@/lib/fallback";
import { formatDateTime } from "@/lib/format";
import { getServerI18n } from "@/lib/i18n/server";

export default async function DashboardPage() {
  const { locale, t } = getServerI18n();
  let overview = fallbackDashboard;
  let dataSource: "live" | "fallback" = "fallback";

  try {
    overview = await getOverview();
    dataSource = "live";
  } catch (error) {
    console.error("Failed to fetch dashboard overview:", error);
  }

  const totalProjects = overview.projects.length;
  const activeProjects = overview.projects.filter((project) =>
    ["sensing", "profiled", "planned", "previewed", "awaiting_approval", "monitoring"].includes(project.latestStage),
  ).length;
  const deployedProjects = overview.projects.filter((project) => project.latestStage === "deployed").length;
  const awaitingApproval = overview.tasks.filter((task) => task.status === "awaiting_approval").length;
  const highRisk = overview.tasks.filter((task) => task.riskScore >= overview.policy.blockAutoDeployThreshold).length;
  const avgRisk = totalProjects
    ? Math.round(overview.projects.reduce((sum, project) => sum + project.riskScore, 0) / totalProjects)
    : 0;
  const recentProjects = [...overview.projects]
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    .slice(0, 5);

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("dashboard.eyebrow")}</div>
        <h1>{t("dashboard.title")}</h1>
        <p className="hero-copy">{t("dashboard.description")}</p>
        <div className="hero-actions">
          <Link className="button button-primary button-link" href="/projects/new">
            {t("dashboard.new_project")}
          </Link>
          <Link className="button button-secondary button-link" href="/projects">
            {t("dashboard.open_projects")}
          </Link>
        </div>
        <div className="hero-meta">
          <span className={`status-badge ${dataSource === "live" ? "good" : "warn"}`}>
            {dataSource === "live" ? t("dashboard.live_api") : t("dashboard.fallback_data")}
          </span>
          <span className="status-badge accent">{t("dashboard.generated")} {formatDateTime(overview.generatedAt, locale)}</span>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("dashboard.current_state")}</div>
            <h2>{t("dashboard.workspace_health")}</h2>
          </div>
        </div>
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">{t("dashboard.projects")}</div>
            <div className="stat-value">{totalProjects}</div>
            <div className="stat-caption">{t("dashboard.projects_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("dashboard.active")}</div>
            <div className="stat-value">{activeProjects}</div>
            <div className="stat-caption">{t("dashboard.active_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("dashboard.deployed")}</div>
            <div className="stat-value">{deployedProjects}</div>
            <div className="stat-caption">{t("dashboard.deployed_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("dashboard.awaiting")}</div>
            <div className="stat-value">{awaitingApproval}</div>
            <div className="stat-caption">{t("dashboard.awaiting_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("dashboard.high_risk")}</div>
            <div className="stat-value">{highRisk}</div>
            <div className="stat-caption">{t("dashboard.high_risk_caption")} {overview.policy.blockAutoDeployThreshold}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("dashboard.average_risk")}</div>
            <div className="stat-value">{avgRisk}</div>
            <div className="stat-caption">{t("dashboard.average_risk_caption")}</div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("dashboard.recent_activity")}</div>
            <h2>{t("dashboard.recent_updates")}</h2>
          </div>
        </div>
        <div className="stack">
          {recentProjects.map((project) => (
            <article className="audit-card" key={project.projectId}>
              <div className="audit-head">
                <strong>{project.name}</strong>
                <span className="status-badge">{t(`workflow_stages.${project.latestStage}`)}</span>
              </div>
              <div className="project-copy">
                {t(`workflow_recommendations.${project.latestStage}`) === `workflow_recommendations.${project.latestStage}`
                  ? project.recommendation
                  : t(`workflow_recommendations.${project.latestStage}`)}
              </div>
              <div className="metric-row">
                <span>{project.url}</span>
                <strong>{formatDateTime(project.updatedAt, locale)}</strong>
              </div>
              <div className="project-foot">
                <span>{t("dashboard.risk")} {project.riskScore}</span>
                <Link href={`/projects/${project.projectId}`}>{t("dashboard.open")}</Link>
              </div>
            </article>
          ))}
          {recentProjects.length === 0 ? <div className="empty-state">{t("dashboard.no_updates")}</div> : null}
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("dashboard.quick_actions")}</div>
            <h2>{t("dashboard.quick_actions")}</h2>
          </div>
        </div>
        <div className="grid-three">
          <Link href="/analyze" className="audit-card" style={{ textDecoration: "none" }}>
            <div className="audit-head"><strong>{t("dashboard.site_analysis")}</strong></div>
            <div className="project-copy">{t("dashboard.site_analysis_description")}</div>
          </Link>
          <Link href="/approvals" className="audit-card" style={{ textDecoration: "none" }}>
            <div className="audit-head"><strong>{t("dashboard.approval_queue")}</strong></div>
            <div className="project-copy">{t("dashboard.approval_queue_description")} · {overview.approvals.length}</div>
          </Link>
          <Link href="/monitor" className="audit-card" style={{ textDecoration: "none" }}>
            <div className="audit-head"><strong>{t("dashboard.monitor")}</strong></div>
            <div className="project-copy">{t("dashboard.monitor_description")} · {overview.alerts.length}</div>
          </Link>
        </div>
      </section>
    </div>
  );
}
