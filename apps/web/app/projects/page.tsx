"use client";

import { useState } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";

interface Project {
  id: string;
  name: string;
  url: string;
  status: "active" | "pending" | "completed";
  geoScore: number;
  adGrade: string;
  createdAt: string;
}

export default function ProjectsPage() {
  const { t } = useI18n();
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProjectUrl, setNewProjectUrl] = useState("");
  const [newProjectName, setNewProjectName] = useState("");
  const [projects, setProjects] = useState<Project[]>([
    {
      id: "demo-1",
      name: "示例电商站",
      url: "https://example-shop.com",
      status: "completed",
      geoScore: 65,
      adGrade: "B",
      createdAt: "2024-01-15",
    },
    {
      id: "demo-2",
      name: "示例博客站",
      url: "https://example-blog.com",
      status: "active",
      geoScore: 72,
      adGrade: "A",
      createdAt: "2024-01-16",
    },
  ]);

  const handleCreateProject = () => {
    if (!newProjectUrl) return;

    const newProject: Project = {
      id: `project-${Date.now()}`,
      name: newProjectName || new URL(newProjectUrl).hostname,
      url: newProjectUrl,
      status: "pending",
      geoScore: 0,
      adGrade: "-",
      createdAt: new Date().toISOString().split("T")[0],
    };

    setProjects([newProject, ...projects]);
    setNewProjectUrl("");
    setNewProjectName("");
    setShowNewProject(false);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active": return "good";
      case "completed": return "accent";
      case "pending": return "warn";
      default: return "neutral";
    }
  };

  const getGradeColor = (grade: string) => {
    if (grade === "A") return "good";
    if (grade === "B") return "accent";
    if (grade === "C") return "warn";
    return "neutral";
  };

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("nav.projects")}</div>
        <h1>{t("projects.title")}</h1>
        <p className="hero-copy">{t("projects.hero_description")}</p>
        <div className="hero-actions">
          <button
            className="button button-primary"
            onClick={() => setShowNewProject(true)}
          >
            + 新建项目
          </button>
        </div>
      </section>

      {/* 新建项目表单 */}
      {showNewProject && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">新建项目</div>
              <h2>创建新项目</h2>
            </div>
            <button
              className="button button-secondary"
              onClick={() => setShowNewProject(false)}
            >
              取消
            </button>
          </div>
          <div className="new-project-form">
            <div className="form-group">
              <label>项目名称</label>
              <input
                type="text"
                placeholder="我的网站"
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                className="input-field"
              />
            </div>
            <div className="form-group">
              <label>网站 URL *</label>
              <input
                type="url"
                placeholder="https://example.com"
                value={newProjectUrl}
                onChange={(e) => setNewProjectUrl(e.target.value)}
                className="input-field"
              />
            </div>
            <div className="form-actions">
              <button
                className="button button-primary"
                onClick={handleCreateProject}
                disabled={!newProjectUrl}
              >
                创建项目
              </button>
              <button
                className="button button-secondary"
                onClick={() => setShowNewProject(false)}
              >
                取消
              </button>
            </div>
          </div>
        </section>
      )}

      {/* 项目列表 */}
      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">所有项目</div>
            <h2>项目列表 ({projects.length})</h2>
          </div>
        </div>

        {projects.length === 0 ? (
          <div className="empty-state">
            <p>还没有项目</p>
            <button
              className="button button-primary"
              onClick={() => setShowNewProject(true)}
            >
              创建第一个项目
            </button>
          </div>
        ) : (
          <div className="project-list">
            {projects.map((project) => (
              <article className="project-card" key={project.id}>
                <div className="project-title">
                  <div>
                    <div className="eyebrow">{project.url}</div>
                    <h3>{project.name}</h3>
                  </div>
                  <span className={`status-badge ${getStatusColor(project.status)}`}>
                    {project.status}
                  </span>
                </div>
                <div className="project-stats">
                  <div className="stat-item">
                    <span className="stat-label">GEO Score</span>
                    <span className="stat-value">{project.geoScore}</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">Ad Grade</span>
                    <span className={`status-badge ${getGradeColor(project.adGrade)}`}>
                      {project.adGrade}
                    </span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-label">创建时间</span>
                    <span className="stat-value">{project.createdAt}</span>
                  </div>
                </div>
                <div className="project-actions">
                  <Link href={`/analyze?url=${encodeURIComponent(project.url)}`}>
                    <button className="button button-primary button-sm">分析</button>
                  </Link>
                  <button className="button button-secondary button-sm">编辑</button>
                  <button className="button button-danger button-sm">删除</button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
