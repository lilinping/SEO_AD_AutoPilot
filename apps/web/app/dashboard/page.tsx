import Link from "next/link";

import { getOverview } from "@/lib/api";
import { fallbackDashboard } from "@/lib/fallback";
import { formatDateTime } from "@/lib/format";

export default async function DashboardPage() {
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
        <div className="eyebrow">Dashboard</div>
        <h1>实时工作台</h1>
        <p className="hero-copy">
          汇总后端项目、任务、审批和风险阈值，替代原来的静态演示数据。
        </p>
        <div className="hero-actions">
          <Link className="button button-primary button-link" href="/projects/new">
            新建项目
          </Link>
          <Link className="button button-secondary button-link" href="/projects">
            打开项目列表
          </Link>
        </div>
        <div className="hero-meta">
          <span className={`status-badge ${dataSource === "live" ? "good" : "warn"}`}>
            {dataSource === "live" ? "Live API" : "Fallback data"}
          </span>
          <span className="status-badge accent">Generated {formatDateTime(overview.generatedAt)}</span>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Current state</div>
            <h2>工作区健康度</h2>
          </div>
        </div>
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">Projects</div>
            <div className="stat-value">{totalProjects}</div>
            <div className="stat-caption">后端工作区项目总数</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Active</div>
            <div className="stat-value">{activeProjects}</div>
            <div className="stat-caption">分析、预览或监控中的项目</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Deployed</div>
            <div className="stat-value">{deployedProjects}</div>
            <div className="stat-caption">已发布项目</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Awaiting approval</div>
            <div className="stat-value">{awaitingApproval}</div>
            <div className="stat-caption">等待人工审批的任务</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">High risk</div>
            <div className="stat-value">{highRisk}</div>
            <div className="stat-caption">达到阻断阈值 {overview.policy.blockAutoDeployThreshold}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Avg risk</div>
            <div className="stat-value">{avgRisk}</div>
            <div className="stat-caption">按项目 riskScore 计算</div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Recent activity</div>
            <h2>最近项目更新</h2>
          </div>
        </div>
        <div className="stack">
          {recentProjects.map((project) => (
            <article className="audit-card" key={project.projectId}>
              <div className="audit-head">
                <strong>{project.name}</strong>
                <span className="status-badge">{project.latestStage}</span>
              </div>
              <div className="project-copy">{project.recommendation}</div>
              <div className="metric-row">
                <span>{project.url}</span>
                <strong>{formatDateTime(project.updatedAt)}</strong>
              </div>
              <div className="project-foot">
                <span>risk {project.riskScore}</span>
                <Link href={`/projects/${project.projectId}`}>Open</Link>
              </div>
            </article>
          ))}
          {recentProjects.length === 0 ? <div className="empty-state">暂无项目更新</div> : null}
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Quick actions</div>
            <h2>快速操作</h2>
          </div>
        </div>
        <div className="grid-three">
          <Link href="/analyze" className="audit-card" style={{ textDecoration: "none" }}>
            <div className="audit-head"><strong>单站分析</strong></div>
            <div className="project-copy">输入 URL 开始 SEO/GEO/广告分析</div>
          </Link>
          <Link href="/approvals" className="audit-card" style={{ textDecoration: "none" }}>
            <div className="audit-head"><strong>审批队列</strong></div>
            <div className="project-copy">处理 {overview.approvals.length} 个审批请求</div>
          </Link>
          <Link href="/monitor" className="audit-card" style={{ textDecoration: "none" }}>
            <div className="audit-head"><strong>监控</strong></div>
            <div className="project-copy">查看 {overview.alerts.length} 条告警和策略提示</div>
          </Link>
        </div>
      </section>
    </div>
  );
}
