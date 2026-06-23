"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";

interface PipelineStage { stage_id: string; stage_name: string; status: string; agent: string; duration_ms?: number }
interface PlatformResult { name: string; type: string; score: number; status: string; findings: string[]; recommendations: string[]; details?: any }
interface AnalysisResult {
  url: string; title: string; meta_description: string; crawl_status: string;
  pipeline: PipelineStage[]; seo_platforms: PlatformResult[]; geo_platforms: PlatformResult[];
  agent_outputs: any[]; seo_score: number;
  geo_scores: { citation: number; entity: number; structure: number; authority: number; ai_presence: number; overall: number };
  ai_readiness: string; ad_recommendations: any[]; ad_readiness: any;
  technical: any; content: any; recommendations: any[];
}

export default function AnalyzePage() {
  const { t } = useI18n();
  const [url, setUrl] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"pipeline" | "seo" | "geo" | "ads" | "recs">("pipeline");
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null);

  const handleAnalyze = async () => {
    if (!url) return;
    setAnalyzing(true); setError(null); setResult(null); setSelectedPlatform(null);
    try {
      const API_BASE = process.env.NEXT_PUBLIC_AUTOPILOT_API_URL ?? "http://127.0.0.1:8000/api";
      const response = await fetch(`${API_BASE}/analyze`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url, include_seo: true, include_geo: true, include_ads: true }) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      setResult(await response.json());
    } catch (err) { setError(`分析失败: ${err instanceof Error ? err.message : "无法连接后端"}。请运行 make api-dev`); }
    finally { setAnalyzing(false); }
  };

  const getScoreColor = (s: number) => s >= 80 ? "good" : s >= 60 ? "accent" : s >= 40 ? "warn" : "danger";

  return (
    <div className="page">
      {/* Input */}
      <section className="panel">
        <div className="section-heading"><div><div className="eyebrow">{t("analyze.title")}</div><h2>{t("analyze.subtitle")}</h2></div></div>
        <div className="input-group">
          <input type="url" placeholder="https://example.com" value={url} onChange={e => setUrl(e.target.value)} className="input-field" disabled={analyzing} onKeyDown={e => e.key === "Enter" && handleAnalyze()} />
          <button onClick={handleAnalyze} disabled={analyzing || !url} className="button button-primary">{analyzing ? "分析中..." : t("common.analyze")}</button>
        </div>
        {error && (
          <section className="panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">错误</div>
                <h2>分析失败</h2>
              </div>
            </div>
            <div className="alert-box alert-error">
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: "1.2rem" }}>⚠️</span>
                <div>
                  <strong>{error}</strong>
                  <p style={{ margin: "8px 0 0", fontSize: "0.85rem", opacity: 0.8 }}>
                    请确保后端服务已启动 (make api-dev)
                  </p>
                </div>
              </div>
            </div>
          </section>
        )}
      </section>

      {/* Loading State */}
      {analyzing && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">分析中</div>
              <h2>正在分析网站...</h2>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "20px 0" }}>
            <div className="loading-spinner"></div>
            <span style={{ color: "var(--muted)" }}>请稍候，正在执行分析流水线</span>
          </div>
          <div className="analysis-progress">
            {["网页抓取", "类型检测", "SEO 分析", "GEO 分析", "广告分析", "报告生成"].map((step, idx) => (
              <div key={idx} className="progress-step running">
                <div className="progress-step-header">
                  <span className="step-icon">⏳</span>
                  <div className="step-info"><strong>{step}</strong></div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Skeleton Loading while processing */}
      {analyzing && !result && (
        <section className="panel">
          <div className="skeleton-card">
            <div className="skeleton skeleton-title"></div>
            <div className="skeleton skeleton-text" style={{ width: "80%" }}></div>
            <div className="skeleton skeleton-text" style={{ width: "60%" }}></div>
          </div>
        </section>
      )}

      {result && (
        <>
          {/* Tabs */}
          <section className="panel">
            <div className="tab-nav">
              {[
                { id: "pipeline", label: `分析链路 (${result.pipeline.length})` },
                { id: "seo", label: `SEO (${result.seo_platforms.length})` },
                { id: "geo", label: `GEO (${result.geo_platforms.length})` },
                { id: "ads", label: "广告" },
                { id: "recs", label: `建议 (${result.recommendations.length})` },
              ].map(tab => (
                <button key={tab.id} className={`tab-btn ${activeTab === tab.id ? "active" : ""}`} onClick={() => { setActiveTab(tab.id as any); setSelectedPlatform(null); }}>{tab.label}</button>
              ))}
            </div>
          </section>

          {/* ═══ Pipeline ═══ */}
          {activeTab === "pipeline" && (
            <section className="panel">
              <div className="section-heading"><div><div className="eyebrow">分析链路</div><h2>BettaFish 风格流水线</h2></div><span className="status-badge good">{result.pipeline.length} 阶段完成</span></div>
              
              {/* 流程图 */}
              <div className="pipeline-flow">
                {result.pipeline.map((stage, idx) => (
                  <div key={stage.stage_id} className="pipeline-stage">
                    <div className="pipeline-stage-number">{idx + 1}</div>
                    <div className="pipeline-stage-content">
                      <strong>{stage.stage_name}</strong>
                      <span className="step-agent">{stage.agent}</span>
                      {stage.duration_ms && <span className="step-duration">{stage.duration_ms}ms</span>}
                    </div>
                    {idx < result.pipeline.length - 1 && <div className="pipeline-arrow">→</div>}
                  </div>
                ))}
              </div>

              {/* 页面信息 */}
              <h3 style={{ fontSize: "0.9rem", marginTop: 20, marginBottom: 10 }}>页面信息</h3>
              <div className="stat-grid">
                <div className="stat-card"><div className="stat-label">标题</div><div className="stat-value" style={{ fontSize: "0.85rem", wordBreak: "break-all" }}>{result.title || "无"}</div></div>
                <div className="stat-card"><div className="stat-label">SEO 评分</div><div className={`stat-value ${getScoreColor(result.seo_score)}`}>{result.seo_score}/100</div></div>
                <div className="stat-card"><div className="stat-label">GEO 评分</div><div className={`stat-value ${getScoreColor(result.geo_scores.overall)}`}>{result.geo_scores.overall.toFixed(0)}/100</div></div>
                <div className="stat-card"><div className="stat-label">广告等级</div><div className={`stat-value ${getScoreColor(result.ad_readiness.score)}`}>{result.ad_readiness.grade}</div></div>
              </div>
            </section>
          )}

          {/* ═══ SEO Platforms ═══ */}
          {activeTab === "seo" && !selectedPlatform && (
            <section className="panel">
              <div className="section-heading"><div><div className="eyebrow">SEO 分析</div><h2>各搜索引擎独立分析</h2></div></div>
              <div className="stack">
                {result.seo_platforms.map((p, idx) => (
                  <article className="audit-card platform-card" key={idx} onClick={() => setSelectedPlatform(p.name)}>
                    <div className="audit-head">
                      <div><strong className="audit-title">{p.name}</strong><span className="platform-type-badge">{p.type}</span></div>
                      <span className={`status-badge ${getScoreColor(p.score)}`}>{p.score}/100</span>
                    </div>
                    <div className="project-copy">{p.findings.slice(0, 3).join(" · ")}</div>
                    <div className="metric-row"><span>发现</span><strong>{p.findings.length} 条</strong></div>
                    <div className="metric-row"><span>建议</span><strong>{p.recommendations.length} 条</strong></div>
                  </article>
                ))}
              </div>
            </section>
          )}
          {activeTab === "seo" && selectedPlatform && (
            <section className="panel">
              <div className="section-heading"><div><div className="eyebrow">SEO 平台</div><h2>{selectedPlatform} 详细分析</h2></div><button className="button button-secondary" onClick={() => setSelectedPlatform(null)}>← 返回</button></div>
              {result.seo_platforms.filter(p => p.name === selectedPlatform).map((p, idx) => (
                <div key={idx}>
                  <div className="stat-grid"><div className="stat-card"><div className="stat-label">评分</div><div className={`stat-value ${getScoreColor(p.score)}`}>{p.score}/100</div></div><div className="stat-card"><div className="stat-label">状态</div><div className="stat-value">已分析</div></div></div>
                  <h3 style={{ fontSize: "0.9rem", marginTop: 16, marginBottom: 10 }}>分析发现</h3>
                  <div className="stack">{p.findings.map((f, i) => <div className="audit-card" key={i}><div className="project-copy">{f}</div></div>)}</div>
                  <h3 style={{ fontSize: "0.9rem", marginTop: 16, marginBottom: 10 }}>优化建议</h3>
                  <div className="stack">{p.recommendations.map((r, i) => <div className="audit-card" key={i}><div className="project-copy">→ {r}</div></div>)}</div>
                  {p.details && Object.keys(p.details).length > 0 && (
                    <>
                      <h3 style={{ fontSize: "0.9rem", marginTop: 16, marginBottom: 10 }}>详细数据</h3>
                      <div className="audit-card"><pre style={{ fontSize: "0.78rem", color: "var(--muted)", whiteSpace: "pre-wrap" }}>{JSON.stringify(p.details, null, 2)}</pre></div>
                    </>
                  )}
                </div>
              ))}
            </section>
          )}

          {/* ═══ GEO Platforms ═══ */}
          {activeTab === "geo" && !selectedPlatform && (
            <section className="panel">
              <div className="section-heading"><div><div className="eyebrow">GEO 分析</div><h2>各 AI 搜索引擎独立分析</h2></div></div>
              <div className="stack">
                {result.geo_platforms.map((p, idx) => (
                  <article className="audit-card platform-card" key={idx} onClick={() => setSelectedPlatform(p.name)}>
                    <div className="audit-head">
                      <div><strong className="audit-title">{p.name}</strong><span className="platform-type-badge geo">GEO</span></div>
                      <span className={`status-badge ${getScoreColor(p.score)}`}>{p.score}/100</span>
                    </div>
                    <div className="project-copy">{p.findings.slice(0, 3).join(" · ")}</div>
                    <div className="metric-row"><span>发现</span><strong>{p.findings.length} 条</strong></div>
                    <div className="metric-row"><span>建议</span><strong>{p.recommendations.length} 条</strong></div>
                  </article>
                ))}
              </div>
            </section>
          )}
          {activeTab === "geo" && selectedPlatform && (
            <section className="panel">
              <div className="section-heading"><div><div className="eyebrow">GEO 平台</div><h2>{selectedPlatform} 详细分析</h2></div><button className="button button-secondary" onClick={() => setSelectedPlatform(null)}>← 返回</button></div>
              {result.geo_platforms.filter(p => p.name === selectedPlatform).map((p, idx) => (
                <div key={idx}>
                  <div className="stat-grid"><div className="stat-card"><div className="stat-label">评分</div><div className={`stat-value ${getScoreColor(p.score)}`}>{p.score}/100</div></div><div className="stat-card"><div className="stat-label">状态</div><div className="stat-value">已分析</div></div></div>
                  <h3 style={{ fontSize: "0.9rem", marginTop: 16, marginBottom: 10 }}>分析发现</h3>
                  <div className="stack">{p.findings.map((f, i) => <div className="audit-card" key={i}><div className="project-copy">{f}</div></div>)}</div>
                  <h3 style={{ fontSize: "0.9rem", marginTop: 16, marginBottom: 10 }}>优化建议</h3>
                  <div className="stack">{p.recommendations.map((r, i) => <div className="audit-card" key={i}><div className="project-copy">→ {r}</div></div>)}</div>
                  {p.details && Object.keys(p.details).length > 0 && (
                    <>
                      <h3 style={{ fontSize: "0.9rem", marginTop: 16, marginBottom: 10 }}>详细数据</h3>
                      <div className="audit-card"><pre style={{ fontSize: "0.78rem", color: "var(--muted)", whiteSpace: "pre-wrap" }}>{JSON.stringify(p.details, null, 2)}</pre></div>
                    </>
                  )}
                </div>
              ))}
            </section>
          )}

          {/* ═══ Ads ═══ */}
          {activeTab === "ads" && (
            <section className="panel">
              <div className="section-heading"><div><div className="eyebrow">广告分析</div><h2>广告平台推荐</h2></div></div>
              <div className="stat-grid"><div className="stat-card"><div className="stat-label">就绪度</div><div className="stat-value">{result.ad_readiness.score}/100</div></div><div className="stat-card"><div className="stat-label">等级</div><div className="stat-value">{result.ad_readiness.grade}</div></div></div>
              <div className="stack" style={{ marginTop: 12 }}>{result.ad_recommendations.map((rec, idx) => <article className="audit-card" key={idx}><div className="audit-head"><strong>{rec.platform}</strong><span className="status-badge">{(rec.confidence * 100).toFixed(0)}%</span></div><div className="project-copy">{rec.reasons.join(" · ")}</div></article>)}</div>
            </section>
          )}

          {/* ═══ Recommendations ═══ */}
          {activeTab === "recs" && (
            <section className="panel">
              <div className="section-heading"><div><div className="eyebrow">优化建议</div><h2>基于真实分析的建议</h2></div></div>
              <div className="stack">
                {result.recommendations.map((rec, idx) => (
                  <article className="audit-card" key={idx}>
                    <div className="audit-head"><strong>{rec.title}</strong><span className={`status-badge ${rec.priority === "high" ? "danger" : "warn"}`}>{rec.priority}</span><span className="status-badge accent">{rec.type}</span></div>
                    <div className="project-copy">{rec.description}</div>
                    {rec.actions && rec.actions.length > 0 && <div style={{ marginTop: 8 }}><strong style={{ fontSize: "0.78rem", color: "var(--muted)" }}>行动：</strong><ul style={{ margin: "4px 0 0", paddingLeft: 16, fontSize: "0.82rem", color: "var(--muted)" }}>{rec.actions.map((a: string, i: number) => <li key={i}>{a}</li>)}</ul></div>}
                    <div className="metric-row"><span>影响</span><strong>{rec.impact}</strong></div>
                  </article>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
