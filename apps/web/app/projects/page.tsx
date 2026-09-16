import Link from "next/link";

import { ProjectsBulkActions } from "@/components/ProjectsBulkActions";
import { getProjects } from "@/lib/api";
import { fallbackDashboard } from "@/lib/fallback";

export default async function ProjectsPage() {
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
        <div className="eyebrow">Projects</div>
        <h1>项目管理</h1>
        <p className="hero-copy">管理后端工作区里的所有 SEO/GEO/广告自动化项目。</p>
        <div className="hero-actions">
          <Link className="button button-primary button-link" href="/projects/new">
            + 新建项目
          </Link>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">所有项目</div>
            <h2>项目列表 ({projects.length})</h2>
          </div>
          <p>
            {dataSource === "live"
              ? "当前展示后端工作区项目，可直接打开详情或批量同步。"
              : "后端不可用，当前展示本地 fallback 示例数据。"}
          </p>
        </div>

        {projects.length === 0 ? (
          <div className="empty-state">
            <p>还没有项目</p>
            <Link className="button button-primary button-link" href="/projects/new">
              创建第一个项目
            </Link>
          </div>
        ) : (
          <ProjectsBulkActions projects={projects} />
        )}
      </section>
    </div>
  );
}
