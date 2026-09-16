import Link from "next/link";

import { ProjectsBulkActions } from "@/components/ProjectsBulkActions";
import { getProjects } from "@/lib/api";
import { fallbackDashboard } from "@/lib/fallback";
import { getServerI18n } from "@/lib/i18n/server";

export default async function ProjectsPage() {
  const { t } = getServerI18n();
  let projects = fallbackDashboard.projects;
  let dataSource: "live" | "fallback" = "fallback";

  try {
    projects = await getProjects();
    dataSource = "live";
  } catch (error) {
    console.error("Failed to fetch projects:", error);
  }

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("projects.eyebrow")}</div>
        <h1>{t("projects.title")}</h1>
        <p className="hero-copy">{t("projects.hero_description")}</p>
        <div className="hero-actions">
          <Link className="button button-primary button-link" href="/projects/new">
            {t("projects.new_project")}
          </Link>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("projects.all_projects")}</div>
            <h2>{t("projects.project_list")} ({projects.length})</h2>
          </div>
          <p>
            {dataSource === "live"
              ? t("projects.live_description")
              : t("projects.fallback_description")}
          </p>
        </div>

        {projects.length === 0 ? (
          <div className="empty-state">
            <p>{t("projects.no_projects_title")}</p>
            <Link className="button button-primary button-link" href="/projects/new">
              {t("projects.create_first")}
            </Link>
          </div>
        ) : (
          <ProjectsBulkActions projects={projects} />
        )}
      </section>
    </div>
  );
}
