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
    } catch (err) {
      setError(`${t("analyze.analysis_failed")}: ${err instanceof Error ? err.message : t("analyze.cannot_connect")}. ${t("analyze.ensure_backend")}`);
    }
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
          <button onClick={handleAnalyze} disabled={analyzing || !url} className="button button-primary">{analyzing ? t("analyze.analyzing") : t("common.analyze")}</button>
        </div>
        {error && (
          <section className="panel">
            <div className="section-heading">
              <div>
                <div className="eyebrow">{t("common.error")}</div>
                <h2>{t("analyze.analysis_failed")}</h2>
              </div>
            </div>
            <div className="alert-box alert-error">
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: "1.2rem" }}>⚠️</span>
                <div>
                  <strong>{error}</strong>
                  <p style={{ margin: "8px 0 0", fontSize: "0.85rem", opacity: 0.8 }}>
                    {t("analyze.ensure_backend")}
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
              <div className="eyebrow">{t("analyze.analyzing")}</div>
              <h2>{t("analyze.analyzing_site")}</h2>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "20px 0" }}>
            <div className="loading-spinner"></div>
            <span style={{ color: "var(--muted)" }}>{t("analyze.pipeline_wait")}</span>
          </div>
          <div className="analysis-progress">
            {["crawl", "type_detection", "seo_analysis", "geo_analysis", "ad_analysis", "report_generation"].map((step, idx) => (
              <div key={idx} className="progress-step running">
                <div className="progress-step-header">
                  <span className="step-icon">⏳</span>
                  <div className="step-info"><strong>{t(`analyze.${step}`)}</strong></div>
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
                { id: "pipeline", label: `${t("analyze.pipeline")} (${result.pipeline.length})` },
                { id: "seo", label: `SEO (${result.seo_platforms.length})` },
                { id: "geo", label: `GEO (${result.geo_platforms.length})` },
                { id: "ads", label: t("analyze.ads") },
                { id: "recs", label: `${t("analyze.recommendations")} (${result.recommendations.length})` },
              ].map(tab => (
                <button key={tab.id} className={`tab-btn ${activeTab === tab.id ? "active" : ""}`} onClick={() => { setActiveTab(tab.id as any); setSelectedPlatform(null); }}>{tab.label}</button>
              ))}
            </div>
          </section>

          {/* ═══ Pipeline ═══ */}
          {activeTab === "pipeline" && (
            <section className="panel">
              <div className="section-heading"><div><div className="eyebrow">{t("analyze.pipeline")}</div><h2>{t("analyze.pipeline_title")}</h2></div><span className="status-badge good">{result.pipeline.length} {t("analyze.stages_completed")}</span></div>
              
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
              <h3 style={{ fontSize: "0.9rem", marginTop: 20, marginBottom: 10 }}>{t("analyze.page_info")}</h3>
              <div className="stat-grid">
                <div className="stat-card"><div className="stat-label">{t("analyze.page_title")}</div><div className="stat-value" style={{ fontSize: "0.85rem", wordBreak: "break-all" }}>{result.title || t("analyze.none")}</div></div>
                <div className="stat-card"><div className="stat-label">{t("analyze.seo_score")}</div><div className={`stat-value ${getScoreColor(result.seo_score)}`}>{result.seo_score}/100</div></div>
                <div className="stat-card"><div className="stat-label">{t("analyze.geo_score")}</div><div className={`stat-value ${getScoreColor(result.geo_scores.overall)}`}>{result.geo_scores.overall.toFixed(0)}/100</div></div>
                <div className="stat-card"><div className="stat-label">{t("analyze.ad_grade")}</div><div className={`stat-value ${getScoreColor(result.ad_readiness.score)}`}>{result.ad_readiness.grade}</div></div>
              </div>
            </section>
          )}

          {/* ═══ SEO Platforms ═══ */}
          {activeTab === "seo" && !selectedPlatform && (
            <section className="panel">
              <div className="section-heading"><div><div className="eyebrow">{t("analyze.seo_analysis")}</div><h2>{t("analyze.seo_platforms")}</h2></div></div>
              <div className="stack">
                {result.seo_platforms.map((p, idx) => (
                  <article className="audit-card platform-card" key={idx} onClick={() => setSelectedPlatform(p.name)}>
                    <div className="audit-head">
                      <div><strong className="audit-title">{p.name}</strong><span className="platform-type-badge">{p.type}</span></div>
                      <span className={`status-badge ${getScoreColor(p.score)}`}>{p.score}/100</span>
                    </div>
                    <div className="project-copy">{p.findings.slice(0, 3).join(" · ")}</div>
                    <div className="metric-row"><span>{t("analyze.findings")}</span><strong>{p.findings.length} {t("analyze.items")}</strong></div>
                    <div className="metric-row"><span>{t("analyze.recommendations")}</span><strong>{p.recommendations.length} {t("analyze.items")}</strong></div>
                  </article>
                ))}
              </div>
            </section>
          )}
          {activeTab === "seo" && selectedPlatform && (
            <section className="panel">
              <div className="section-heading"><div><div className="eyebrow">SEO</div><h2>{selectedPlatform} {t("analyze.platform_detail")}</h2></div><button className="button button-secondary" onClick={() => setSelectedPlatform(null)}>← {t("analyze.back")}</button></div>
              {result.seo_platforms.filter(p => p.name === selectedPlatform).map((p, idx) => (
                <div key={idx}>
                  <div className="stat-grid"><div className="stat-card"><div className="stat-label">{t("analyze.score")}</div><div className={`stat-value ${getScoreColor(p.score)}`}>{p.score}/100</div></div><div className="stat-card"><div className="stat-label">{t("analyze.status")}</div><div className="stat-value">{t("analyze.analyzed")}</div></div></div>
                  <h3 style={{ fontSize: "0.9rem", marginTop: 16, marginBottom: 10 }}>{t("analyze.analysis_findings")}</h3>
                  <div className="stack">{p.findings.map((f, i) => <div className="audit-card" key={i}><div className="project-copy">{f}</div></div>)}</div>
                  <h3 style={{ fontSize: "0.9rem", marginTop: 16, marginBottom: 10 }}>{t("analyze.optimization_recommendations")}</h3>
                  <div className="stack">{p.recommendations.map((r, i) => <div className="audit-card" key={i}><div className="project-copy">→ {r}</div></div>)}</div>
                  {p.details && Object.keys(p.details).length > 0 && (
                    <>
                      <h3 style={{ fontSize: "0.9rem", marginTop: 16, marginBottom: 10 }}>{t("analyze.details")}</h3>
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
              <div className="section-heading"><div><div className="eyebrow">{t("analyze.geo_analysis")}</div><h2>{t("analyze.geo_platforms")}</h2></div></div>
              <div className="stack">
                {result.geo_platforms.map((p, idx) => (
                  <article className="audit-card platform-card" key={idx} onClick={() => setSelectedPlatform(p.name)}>
                    <div className="audit-head">
                      <div><strong className="audit-title">{p.name}</strong><span className="platform-type-badge geo">GEO</span></div>
                      <span className={`status-badge ${getScoreColor(p.score)}`}>{p.score}/100</span>
                    </div>
                    <div className="project-copy">{p.findings.slice(0, 3).join(" · ")}</div>
                    <div className="metric-row"><span>{t("analyze.findings")}</span><strong>{p.findings.length} {t("analyze.items")}</strong></div>
                    <div className="metric-row"><span>{t("analyze.recommendations")}</span><strong>{p.recommendations.length} {t("analyze.items")}</strong></div>
                  </article>
                ))}
              </div>
            </section>
          )}
          {activeTab === "geo" && selectedPlatform && (
            <section className="panel">
              <div className="section-heading"><div><div className="eyebrow">GEO</div><h2>{selectedPlatform} {t("analyze.platform_detail")}</h2></div><button className="button button-secondary" onClick={() => setSelectedPlatform(null)}>← {t("analyze.back")}</button></div>
              {result.geo_platforms.filter(p => p.name === selectedPlatform).map((p, idx) => (
                <div key={idx}>
                  <div className="stat-grid"><div className="stat-card"><div className="stat-label">{t("analyze.score")}</div><div className={`stat-value ${getScoreColor(p.score)}`}>{p.score}/100</div></div><div className="stat-card"><div className="stat-label">{t("analyze.status")}</div><div className="stat-value">{t("analyze.analyzed")}</div></div></div>
                  <h3 style={{ fontSize: "0.9rem", marginTop: 16, marginBottom: 10 }}>{t("analyze.analysis_findings")}</h3>
                  <div className="stack">{p.findings.map((f, i) => <div className="audit-card" key={i}><div className="project-copy">{f}</div></div>)}</div>
                  <h3 style={{ fontSize: "0.9rem", marginTop: 16, marginBottom: 10 }}>{t("analyze.optimization_recommendations")}</h3>
                  <div className="stack">{p.recommendations.map((r, i) => <div className="audit-card" key={i}><div className="project-copy">→ {r}</div></div>)}</div>
                  {p.details && Object.keys(p.details).length > 0 && (
                    <>
                      <h3 style={{ fontSize: "0.9rem", marginTop: 16, marginBottom: 10 }}>{t("analyze.details")}</h3>
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
              <div className="section-heading"><div><div className="eyebrow">{t("analyze.ad_analysis")}</div><h2>{t("analyze.ad_platform_recommendations")}</h2></div></div>
              <div className="stat-grid"><div className="stat-card"><div className="stat-label">{t("analyze.readiness")}</div><div className="stat-value">{result.ad_readiness.score}/100</div></div><div className="stat-card"><div className="stat-label">{t("analyze.grade")}</div><div className="stat-value">{result.ad_readiness.grade}</div></div></div>
              <div className="stack" style={{ marginTop: 12 }}>{result.ad_recommendations.map((rec, idx) => <article className="audit-card" key={idx}><div className="audit-head"><strong>{rec.platform}</strong><span className="status-badge">{(rec.confidence * 100).toFixed(0)}%</span></div><div className="project-copy">{rec.reasons.join(" · ")}</div></article>)}</div>
            </section>
          )}

          {/* ═══ Recommendations ═══ */}
          {activeTab === "recs" && (
            <section className="panel">
              <div className="section-heading"><div><div className="eyebrow">{t("analyze.optimization_recommendations")}</div><h2>{t("analyze.evidence_based_recommendations")}</h2></div></div>
              <div className="stack">
                {result.recommendations.map((rec, idx) => (
                  <article className="audit-card" key={idx}>
                    <div className="audit-head"><strong>{rec.title}</strong><span className={`status-badge ${rec.priority === "high" ? "danger" : "warn"}`}>{rec.priority}</span><span className="status-badge accent">{rec.type}</span></div>
                    <div className="project-copy">{rec.description}</div>
                    {rec.actions && rec.actions.length > 0 && <div style={{ marginTop: 8 }}><strong style={{ fontSize: "0.78rem", color: "var(--muted)" }}>{t("analyze.actions")}:</strong><ul style={{ margin: "4px 0 0", paddingLeft: 16, fontSize: "0.82rem", color: "var(--muted)" }}>{rec.actions.map((a: string, i: number) => <li key={i}>{a}</li>)}</ul></div>}
                    <div className="metric-row"><span>{t("analyze.impact")}</span><strong>{rec.impact}</strong></div>
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
