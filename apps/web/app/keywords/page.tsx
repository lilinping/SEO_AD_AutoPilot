"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";

interface KeywordResult {
  keyword: string;
  search_volume: number;
  difficulty: number;
  cpc: number;
  competition: number;
  intent: string;
  serp_features: string[];
  long_tail_variants: string[];
  related_keywords: string[];
  clusters: string[];
  score: number;
}

interface ClusterResult {
  name: string;
  keywords: string[];
  avg_difficulty: number;
  total_volume: number;
  opportunity_score: number;
}

interface ResearchResult {
  keywords: KeywordResult[];
  clusters: ClusterResult[];
  serp_analysis: {
    total_results: number;
    top_domains: string[];
    features_present: string[];
    content_types: Record<string, number>;
  };
  recommendations: {
    type: string;
    title: string;
    description: string;
    keywords?: string[];
  }[];
  summary: {
    total_keywords: number;
    avg_difficulty: number;
    total_search_volume: number;
    easy_keywords: number;
    medium_keywords: number;
    hard_keywords: number;
    intent_distribution: Record<string, number>;
  };
}

export default function KeywordsPage() {
  const { t } = useI18n();
  const [input, setInput] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [market, setMarket] = useState("US");
  const [activeTab, setActiveTab] = useState<"keywords" | "clusters" | "recommendations">("keywords");
  const [sortField, setSortField] = useState<"score" | "search_volume" | "difficulty">("score");
  const [sortAsc, setSortAsc] = useState(false);

  const handleResearch = async () => {
    if (!input.trim()) return;
    setAnalyzing(true); setError(null); setResult(null);
    try {
      const API_BASE = process.env.NEXT_PUBLIC_AUTOPILOT_API_URL ?? "http://127.0.0.1:8000/api";
      const kws = input.split("\n").map(s => s.trim()).filter(Boolean);
      const isMulti = kws.length > 1;
      const response = await fetch(`${API_BASE}/keywords/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(isMulti ? { keywords: kws, target_market: market } : { keyword: kws[0], seed: kws[0], target_market: market }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!data.success) throw new Error(data.error || "Research failed");
      setResult(data.data);
    } catch (err) {
      setError(`Research failed: ${err instanceof Error ? err.message : "Cannot connect to backend"}`);
    } finally { setAnalyzing(false); }
  };

  const getDiffColor = (d: number) => d < 30 ? "#22c55e" : d < 60 ? "#f59e0b" : "#ef4444";
  const getIntentColor = (i: string) => {
    if (i === "transactional") return "#22c55e";
    if (i === "commercial") return "#3b82f6";
    if (i === "informational") return "#8b5cf6";
    return "#6b7280";
  };

  const sorted = result ? [...result.keywords].sort((a, b) => {
    const av = a[sortField] as number, bv = b[sortField] as number;
    return sortAsc ? av - bv : bv - av;
  }) : [];

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("nav.keywords") || "Keywords"}</div>
        <h1>{t("keywords.title") || "Keyword Research"}</h1>
        <p className="hero-copy">{t("keywords.subtitle") || "Analyze keywords: difficulty, volume, intent, SERP features, and clustering"}</p>
      </section>

      <section className="panel">
        <div className="input-group">
          <textarea
            placeholder="Enter keywords (one per line)&#10;e.g.: wireless headphones&#10;best bluetooth earbuds&#10;noise cancelling headphones"
            value={input}
            onChange={e => setInput(e.target.value)}
            className="input-field"
            rows={4}
            style={{ flex: 1, resize: "vertical" }}
            disabled={analyzing}
          />
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <select value={market} onChange={e => setMarket(e.target.value)} className="input-field" style={{ width: 120 }}>
              <option value="US">US</option>
              <option value="UK">UK</option>
              <option value="DE">DE</option>
              <option value="CN">CN</option>
              <option value="JP">JP</option>
            </select>
            <button onClick={handleResearch} disabled={analyzing || !input.trim()} className="button button-primary">
              {analyzing ? "研究中..." : t("common.analyze") || "Research"}
            </button>
          </div>
        </div>
      </section>

      {error && <section className="alert-box alert-error">{error}</section>}

      {analyzing && (
        <section className="panel" style={{ textAlign: "center", padding: 40 }}>
          <div className="spinner" style={{ margin: "0 auto 12px" }} />
          <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>Researching keywords...</p>
        </section>
      )}

      {result && (
        <>
          <section className="stat-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}>
            <div className="stat-card">
              <div className="stat-card-label">Keywords</div>
              <div className="stat-card-value">{result.summary.total_keywords}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Total Volume</div>
              <div className="stat-card-value">{result.summary.total_search_volume.toLocaleString()}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Avg Difficulty</div>
              <div className="stat-card-value" style={{ color: getDiffColor(result.summary.avg_difficulty) }}>{result.summary.avg_difficulty.toFixed(0)}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Easy / Med / Hard</div>
              <div className="stat-card-value" style={{ fontSize: "1rem" }}>
                <span style={{ color: "#22c55e" }}>{result.summary.easy_keywords}</span>
                {" / "}
                <span style={{ color: "#f59e0b" }}>{result.summary.medium_keywords}</span>
                {" / "}
                <span style={{ color: "#ef4444" }}>{result.summary.hard_keywords}</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Clusters</div>
              <div className="stat-card-value">{result.clusters.length}</div>
            </div>
          </section>

          <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
            {(["keywords", "clusters", "recommendations"] as const).map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)} className={`button ${activeTab === tab ? "button-primary" : "button-secondary"}`} style={{ textTransform: "capitalize" }}>
                {tab}
              </button>
            ))}
          </div>

          {activeTab === "keywords" && (
            <section className="panel">
              <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
                {(["score", "search_volume", "difficulty"] as const).map(field => (
                  <button key={field} onClick={() => { setSortField(field); setSortAsc(sortField === field ? !sortAsc : field === "difficulty"); }} className={`button ${sortField === field ? "button-primary" : "button-secondary"}`} style={{ textTransform: "capitalize", fontSize: "0.75rem", padding: "4px 10px" }}>
                    {field === "search_volume" ? "volume" : field} {sortField === field ? (sortAsc ? "↑" : "↓") : ""}
                  </button>
                ))}
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "2px solid var(--border)", textAlign: "left" }}>
                      <th style={{ padding: "6px 8px" }}>Keyword</th>
                      <th style={{ padding: "6px 8px", textAlign: "right" }}>Volume</th>
                      <th style={{ padding: "6px 8px", textAlign: "right" }}>Difficulty</th>
                      <th style={{ padding: "6px 8px", textAlign: "right" }}>CPC</th>
                      <th style={{ padding: "6px 8px" }}>Intent</th>
                      <th style={{ padding: "6px 8px", textAlign: "right" }}>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((kw, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td style={{ padding: "6px 8px", fontWeight: 500 }}>{kw.keyword}</td>
                        <td style={{ padding: "6px 8px", textAlign: "right" }}>{kw.search_volume.toLocaleString()}</td>
                        <td style={{ padding: "6px 8px", textAlign: "right" }}>
                          <span style={{ color: getDiffColor(kw.difficulty), fontWeight: 600 }}>{kw.difficulty.toFixed(0)}</span>
                        </td>
                        <td style={{ padding: "6px 8px", textAlign: "right" }}>${kw.cpc.toFixed(2)}</td>
                        <td style={{ padding: "6px 8px" }}>
                          <span style={{ fontSize: "0.7rem", padding: "2px 6px", borderRadius: 4, background: getIntentColor(kw.intent) + "20", color: getIntentColor(kw.intent), textTransform: "capitalize" }}>{kw.intent}</span>
                        </td>
                        <td style={{ padding: "6px 8px", textAlign: "right", fontWeight: 600 }}>{kw.score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {activeTab === "clusters" && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
              {result.clusters.map((cl, i) => (
                <section key={i} className="panel">
                  <div className="section-heading"><h3>{cl.name}</h3></div>
                  <div className="metric-row"><span>Keywords</span><span>{cl.keywords.length}</span></div>
                  <div className="metric-row"><span>Volume</span><span>{cl.total_volume.toLocaleString()}</span></div>
                  <div className="metric-row"><span>Avg Difficulty</span><span style={{ color: getDiffColor(cl.avg_difficulty) }}>{cl.avg_difficulty}</span></div>
                  <div className="metric-row"><span>Opportunity</span><span style={{ fontWeight: 700, color: cl.opportunity_score > 50 ? "#22c55e" : cl.opportunity_score > 20 ? "#f59e0b" : "#ef4444" }}>{cl.opportunity_score}</span></div>
                  <div style={{ marginTop: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
                    {cl.keywords.slice(0, 5).map((kw, j) => (
                      <span key={j} style={{ fontSize: "0.7rem", padding: "2px 6px", borderRadius: 4, background: "var(--border)" }}>{kw}</span>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}

          {activeTab === "recommendations" && (
            <div style={{ display: "grid", gap: 10 }}>
              {result.recommendations.map((rec, i) => (
                <section key={i} className="panel">
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <span style={{ fontSize: "0.7rem", padding: "2px 6px", borderRadius: 4, background: "var(--border)", textTransform: "capitalize" }}>{rec.type}</span>
                    <h3 style={{ fontSize: "0.9rem", margin: 0 }}>{rec.title}</h3>
                  </div>
                  <p style={{ fontSize: "0.82rem", color: "var(--muted)", margin: "0 0 8px 0", lineHeight: 1.5 }}>{rec.description}</p>
                  {rec.keywords && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {rec.keywords.map((kw, j) => (
                        <span key={j} style={{ fontSize: "0.7rem", padding: "2px 8px", borderRadius: 4, background: "var(--primary, #3b82f6)20", color: "var(--primary, #3b82f6)" }}>{kw}</span>
                      ))}
                    </div>
                  )}
                </section>
              ))}
            </div>
          )}
        </>
      )}

      <style jsx>{`
        .spinner {
          width: 24px; height: 24px;
          border: 3px solid var(--border);
          border-top-color: var(--primary, #3b82f6);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .input-group { display: flex; gap: 8px; align-items: stretch; }
      `}</style>
    </div>
  );
}
