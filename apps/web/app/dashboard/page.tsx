"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";

interface DashboardStats {
  totalProjects: number;
  activeProjects: number;
  completedProjects: number;
  avgGeoScore: number;
  avgSeoScore: number;
  totalAlerts: number;
}

export default function DashboardPage() {
  const { t } = useI18n();
  const [stats, setStats] = useState<DashboardStats>({
    totalProjects: 12,
    activeProjects: 5,
    completedProjects: 7,
    avgGeoScore: 68.5,
    avgSeoScore: 72.3,
    totalAlerts: 3,
  });

  const [recentActivity, setRecentActivity] = useState([
    { id: 1, type: "analysis", project: "电商网站", time: "2 分钟前", status: "completed" },
    { id: 2, type: "deploy", project: "博客站点", time: "15 分钟前", status: "success" },
    { id: 3, type: "alert", project: "SaaS 平台", time: "1 小时前", status: "warning" },
  ]);

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("nav.overview")}</div>
        <h1>{t("home.mission_control")}</h1>
        <p className="hero-copy">{t("home.hero_description")}</p>
        <div className="hero-actions">
          <Link className="button button-primary button-link" href="/analyze">
            {t("home.launch_project")}
          </Link>
          <Link className="button button-secondary button-link" href="/projects">
            {t("nav.projects")}
          </Link>
        </div>
      </section>

      {/* Stats */}
      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("home.signals")}</div>
            <h2>{t("home.current_state")}</h2>
          </div>
        </div>
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">{t("home.projects")}</div>
            <div className="stat-value">{stats.totalProjects}</div>
            <div className="stat-caption">{t("common.projects_in_workspace")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">GEO Score</div>
            <div className="stat-value">{stats.avgGeoScore}</div>
            <div className="stat-caption">平均 GEO 评分</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">SEO Score</div>
            <div className="stat-value">{stats.avgSeoScore}</div>
            <div className="stat-caption">平均 SEO 评分</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Alerts</div>
            <div className="stat-value">{stats.totalAlerts}</div>
            <div className="stat-caption">{t("monitor.active_alerts")}</div>
          </div>
        </div>
      </section>

      {/* Recent Activity */}
      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">最近活动</div>
            <h2>Recent Activity</h2>
          </div>
        </div>
        <div className="stack">
          {recentActivity.map((activity) => (
            <article className="audit-card" key={activity.id}>
              <div className="audit-head">
                <strong>{activity.project}</strong>
                <span className={`status-badge ${activity.status === "completed" ? "good" : activity.status === "success" ? "good" : "warn"}`}>
                  {activity.type}
                </span>
              </div>
              <div className="metric-row">
                <span>{activity.time}</span>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Quick Actions */}
      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">快速操作</div>
            <h2>Quick Actions</h2>
          </div>
        </div>
        <div className="grid-three">
          <Link href="/analyze" className="audit-card" style={{ textDecoration: "none" }}>
            <div className="audit-head"><strong>{t("nav.analyze")}</strong></div>
            <div className="project-copy">输入 URL 开始分析</div>
          </Link>
          <Link href="/projects" className="audit-card" style={{ textDecoration: "none" }}>
            <div className="audit-head"><strong>{t("nav.projects")}</strong></div>
            <div className="project-copy">管理所有项目</div>
          </Link>
          <Link href="/settings" className="audit-card" style={{ textDecoration: "none" }}>
            <div className="audit-head"><strong>{t("nav.settings")}</strong></div>
            <div className="project-copy">配置系统设置</div>
          </Link>
        </div>
      </section>
    </div>
  );
}
