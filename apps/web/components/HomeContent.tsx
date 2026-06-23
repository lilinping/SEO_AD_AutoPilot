"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import type { DashboardSnapshot, ProjectSummary } from "@seo-ad-autopilot/contracts";

function ProjectHero({ project }: { project: ProjectSummary }) {
  const { t } = useI18n();
  return (
    <article className="project-card">
      <div className="project-title">
        <div>
          <div className="eyebrow">{project.siteClass}</div>
          <h3>{project.name}</h3>
        </div>
        <span className="status-badge">{project.latestStage}</span>
      </div>
      <div className="project-copy">{project.recommendation}</div>
      <div className="project-foot">
        <span>{project.url}</span>
        <Link href={`/projects/${project.projectId}`}>{t("common.open")}</Link>
      </div>
    </article>
  );
}

export function HomeContent({ overview }: { overview: DashboardSnapshot }) {
  const { t } = useI18n();
  const deployed = overview.tasks.filter((task) => task.status === "deployed").length;
  const awaiting = overview.tasks.filter((task) => task.status === "awaiting_approval").length;
  const blocked = overview.tasks.filter((task) => task.riskScore >= 80).length;

  return (
    <div className="page">
      {/* Hero Section */}
      <section className="hero">
        <div className="eyebrow">{t("home.mission_control")}</div>
        <div className="hero-grid">
          <div>
            <h1>{t("home.hero_title")}</h1>
            <p className="hero-copy">{t("home.hero_description")}</p>
            <div className="hero-actions">
              <Link className="button button-primary button-link" href="/analyze">
                {t("home.launch_project")}
              </Link>
              <Link className="button button-secondary button-link" href="/acceptance">
                {t("home.open_acceptance")}
              </Link>
              <Link className="button button-secondary button-link" href="/approvals">
                {t("home.review_gates")}
              </Link>
            </div>
            <div className="hero-meta">
              <span className="status-badge accent">{t("home.preview_first")}</span>
              <span className="status-badge good">{t("home.rollback_ready")}</span>
              <span className="status-badge warn">{t("home.approval_gated")}</span>
            </div>
          </div>
          <div className="hero-side">
            <div className="stat-card">
              <div className="stat-label">{t("home.projects")}</div>
              <div className="stat-value">{overview.projects.length}</div>
              <div className="stat-caption">{t("common.projects_in_workspace")}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">{t("home.awaiting_approval")}</div>
              <div className="stat-value">{awaiting}</div>
              <div className="stat-caption">{t("common.manual_review")}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">{t("home.deployed")}</div>
              <div className="stat-value">{deployed}</div>
              <div className="stat-caption">{t("common.live_or_promoted")}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">{t("home.high_risk")}</div>
              <div className="stat-value">{blocked}</div>
              <div className="stat-caption">{t("common.blocked_from_deploy")}</div>
            </div>
          </div>
        </div>
      </section>

      {/* Signals Section */}
      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("home.signals")}</div>
            <h2>{t("home.current_state")}</h2>
          </div>
        </div>
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">Skills</div>
            <div className="stat-value">{overview.skills.length}</div>
            <div className="stat-caption">read, seo, ad, deploy, observe</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Alerts</div>
            <div className="stat-value">{overview.alerts.length}</div>
            <div className="stat-caption">monitoring and policy notices</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Window</div>
            <div className="stat-value">{overview.policy.monitorWindowMinutes}m</div>
            <div className="stat-caption">rollback within {overview.policy.rollbackWindowMinutes}m</div>
          </div>
        </div>
      </section>

      {/* Projects Section */}
      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("home.projects")}</div>
            <h2>{t("home.workspace_portfolio")}</h2>
          </div>
          <p>{t("home.each_card_points")}</p>
        </div>
        <div className="grid-two">
          {overview.projects.slice(0, 4).map((project) => (
            <ProjectHero key={project.projectId} project={project} />
          ))}
        </div>
      </section>

      {/* Alerts Section */}
      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Alerts</div>
            <h2>{t("home.guardrails")}</h2>
          </div>
          <p>{t("home.risk_thresholds")}</p>
        </div>
        <div className="stack">
          {overview.alerts.map((alert, idx) => (
            <div className="alert-box" key={idx}>
              {alert}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
