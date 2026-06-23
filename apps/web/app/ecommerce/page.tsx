"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";

interface ListingScore {
  title: number;
  bullets: number;
  description: number;
  images: number;
  a_plus: number;
  reviews: number;
  overall: number;
}

interface ConversionScore {
  cta: number;
  trust: number;
  urgency: number;
  social_proof: number;
  checkout: number;
  overall: number;
}

interface ConversionSignals {
  cta_count: number;
  cta_texts: string[];
  has_add_to_cart: boolean;
  has_buy_now: boolean;
  has_trust_badges: boolean;
  has_return_policy: boolean;
  has_free_shipping: boolean;
  has_urgency_signals: boolean;
  urgency_texts: string[];
  social_proof_count: number;
  stock_indicator: string | null;
}

interface Recommendation {
  priority: number;
  category: string;
  title: string;
  description: string;
  impact: string;
  effort: string;
}

interface EcommerceResult {
  platform: string;
  scope: string;
  product: {
    title: string;
    price: string | null;
    original_price: string | null;
    brand: string;
    category: string;
    bullet_count: number;
    image_count: number;
    rating: number | null;
    review_count: number;
    has_a_plus: boolean;
    has_video: boolean;
    has_variants: boolean;
  };
  listing_score: ListingScore;
  conversion_score: ConversionScore;
  conversion_signals: ConversionSignals;
  competitors: any[];
  recommendations: Recommendation[];
  quick_wins: Recommendation[];
  critical_issues: Recommendation[];
  summary: {
    total_recommendations: number;
    quick_wins_count: number;
    critical_issues_count: number;
    listing_grade: string;
    conversion_grade: string;
  };
}

export default function EcommercePage() {
  const { t } = useI18n();
  const [url, setUrl] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<EcommerceResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [platform, setPlatform] = useState("auto");
  const [scope, setScope] = useState("full");
  const [competitors, setCompetitors] = useState("");
  const [activeTab, setActiveTab] = useState<"overview" | "listing" | "conversion" | "recommendations">("overview");

  const handleAnalyze = async () => {
    if (!url) return;
    setAnalyzing(true); setError(null); setResult(null);
    try {
      const API_BASE = process.env.NEXT_PUBLIC_AUTOPILOT_API_URL ?? "http://127.0.0.1:8000/api";
      const compList = competitors.split("\n").map(s => s.trim()).filter(Boolean);
      const response = await fetch(`${API_BASE}/ecommerce/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, platform, scope, competitors: compList.length ? compList : undefined }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!data.success) throw new Error(data.error || "分析失败");
      setResult(data.data);
    } catch (err) {
      setError(`分析失败: ${err instanceof Error ? err.message : "无法连接后端"}`);
    } finally { setAnalyzing(false); }
  };

  const getGradeColor = (g: string) => {
    if (g.startsWith("A")) return "#22c55e";
    if (g.startsWith("B")) return "#3b82f6";
    if (g.startsWith("C")) return "#f59e0b";
    return "#ef4444";
  };

  const getScoreColor = (s: number) => s >= 80 ? "#22c55e" : s >= 60 ? "#3b82f6" : s >= 40 ? "#f59e0b" : "#ef4444";

  const getImpactColor = (impact: string) => {
    if (impact === "critical") return "#ef4444";
    if (impact === "high") return "#f59e0b";
    if (impact === "medium") return "#3b82f6";
    return "#6b7280";
  };

  const getEffortColor = (effort: string) => {
    if (effort === "low") return "#22c55e";
    if (effort === "medium") return "#f59e0b";
    return "#ef4444";
  };

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("nav.ecommerce") || "电商分析"}</div>
        <h1>{t("ecommerce.title") || "E-commerce Analysis"}</h1>
        <p className="hero-copy">{t("ecommerce.subtitle") || "Analyze product listings, conversion funnels, and get optimization recommendations"}</p>
      </section>

      <section className="panel">
        <div className="input-group">
          <input type="url" placeholder="https://www.amazon.com/dp/B08N5WRWNW" value={url} onChange={e => setUrl(e.target.value)} className="input-field" disabled={analyzing} onKeyDown={e => e.key === "Enter" && handleAnalyze()} />
          <select value={platform} onChange={e => setPlatform(e.target.value)} className="input-field" style={{ width: "auto" }}>
            <option value="auto">Auto-detect</option>
            <option value="amazon">Amazon</option>
            <option value="shopify">Shopify</option>
            <option value="woocommerce">WooCommerce</option>
            <option value="magento">Magento</option>
            <option value="custom">Custom</option>
          </select>
          <select value={scope} onChange={e => setScope(e.target.value)} className="input-field" style={{ width: "auto" }}>
            <option value="full">Full Analysis</option>
            <option value="listing">Listing Only</option>
            <option value="pricing">Pricing</option>
            <option value="conversion">Conversion</option>
            <option value="competitors">Competitors</option>
          </select>
          <button onClick={handleAnalyze} disabled={analyzing || !url} className="button button-primary">
            {analyzing ? "分析中..." : t("common.analyze") || "Analyze"}
          </button>
        </div>
        <div style={{ marginTop: 8 }}>
          <textarea placeholder="Competitor URLs (one per line, optional)" value={competitors} onChange={e => setCompetitors(e.target.value)} className="input-field" rows={2} style={{ width: "100%", resize: "vertical" }} />
        </div>
      </section>

      {error && (
        <section className="alert-box alert-error">{error}</section>
      )}

      {analyzing && (
        <section className="panel" style={{ textAlign: "center", padding: 40 }}>
          <div className="spinner" style={{ margin: "0 auto 12px" }} />
          <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>{t("ecommerce.analyzing") || "Analyzing product page..."}</p>
        </section>
      )}

      {result && (
        <>
          <section className="stat-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
            <div className="stat-card">
              <div className="stat-card-label">Platform</div>
              <div className="stat-card-value" style={{ textTransform: "capitalize" }}>{result.platform}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Listing Grade</div>
              <div className="stat-card-value" style={{ color: getGradeColor(result.summary.listing_grade) }}>{result.summary.listing_grade}</div>
              <div className="stat-card-caption">{Math.round(result.listing_score.overall)}%</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Conversion Grade</div>
              <div className="stat-card-value" style={{ color: getGradeColor(result.summary.conversion_grade) }}>{result.summary.conversion_grade}</div>
              <div className="stat-card-caption">{Math.round(result.conversion_score.overall)}%</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Recommendations</div>
              <div className="stat-card-value">{result.summary.total_recommendations}</div>
              <div className="stat-card-caption">{result.summary.critical_issues_count} critical · {result.summary.quick_wins_count} quick wins</div>
            </div>
          </section>

          {result.product && (
            <section className="panel">
              <div className="section-heading"><h3>Product Info</h3></div>
              <div className="metric-row"><span>Brand</span><span>{result.product.brand || "—"}</span></div>
              <div className="metric-row"><span>Title</span><span style={{ fontSize: "0.82rem" }}>{result.product.title || "—"}</span></div>
              <div className="metric-row"><span>Price</span><span>{result.product.price ? `$${result.product.price}` : "—"}</span></div>
              <div className="metric-row"><span>Bullets</span><span>{result.product.bullet_count}</span></div>
              <div className="metric-row"><span>Images</span><span>{result.product.image_count}</span></div>
              <div className="metric-row"><span>Rating</span><span>{result.product.rating ? `${result.product.rating}/5` : "—"}</span></div>
              <div className="metric-row"><span>Reviews</span><span>{result.product.review_count.toLocaleString()}</span></div>
              <div className="metric-row"><span>A+ Content</span><span>{result.product.has_a_plus ? "✓" : "✗"}</span></div>
              <div className="metric-row"><span>Video</span><span>{result.product.has_video ? "✓" : "✗"}</span></div>
            </section>
          )}

          <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap" }}>
            {(["overview", "listing", "conversion", "recommendations"] as const).map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)} className={`button ${activeTab === tab ? "button-primary" : "button-secondary"}`} style={{ textTransform: "capitalize" }}>
                {tab}
              </button>
            ))}
          </div>

          {activeTab === "overview" && (
            <>
              <section className="panel">
                <div className="section-heading"><h3>Listing Score Breakdown</h3></div>
                {Object.entries(result.listing_score).filter(([k]) => k !== "overall").map(([key, val]) => (
                  <div key={key} className="metric-row">
                    <span style={{ textTransform: "capitalize" }}>{key.replace("_", " ")}</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
                      <div style={{ flex: 1, height: 6, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{ width: `${val}%`, height: "100%", background: getScoreColor(val as number), borderRadius: 3, transition: "width 0.3s" }} />
                      </div>
                      <span style={{ fontSize: "0.75rem", color: "var(--muted)", minWidth: 32, textAlign: "right" }}>{Math.round(val as number)}</span>
                    </div>
                  </div>
                ))}
              </section>
              <section className="panel">
                <div className="section-heading"><h3>Conversion Score Breakdown</h3></div>
                {Object.entries(result.conversion_score).filter(([k]) => k !== "overall").map(([key, val]) => (
                  <div key={key} className="metric-row">
                    <span style={{ textTransform: "capitalize" }}>{key.replace("_", " ")}</span>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
                      <div style={{ flex: 1, height: 6, background: "var(--border)", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{ width: `${val}%`, height: "100%", background: getScoreColor(val as number), borderRadius: 3, transition: "width 0.3s" }} />
                      </div>
                      <span style={{ fontSize: "0.75rem", color: "var(--muted)", minWidth: 32, textAlign: "right" }}>{Math.round(val as number)}</span>
                    </div>
                  </div>
                ))}
              </section>
            </>
          )}

          {activeTab === "listing" && (
            <section className="panel">
              <div className="section-heading"><h3>Listing Details</h3></div>
              <div className="metric-row"><span>Title Length</span><span>{result.product.title?.length || 0} chars</span></div>
              <div className="metric-row"><span>Bullet Points</span><span>{result.product.bullet_count} / 5</span></div>
              <div className="metric-row"><span>Images</span><span>{result.product.image_count} / 7+</span></div>
              <div className="metric-row"><span>A+ Content</span><span style={{ color: result.product.has_a_plus ? "#22c55e" : "#ef4444" }}>{result.product.has_a_plus ? "Available" : "Missing"}</span></div>
              <div className="metric-row"><span>Product Video</span><span style={{ color: result.product.has_video ? "#22c55e" : "#ef4444" }}>{result.product.has_video ? "Available" : "Missing"}</span></div>
              <div className="metric-row"><span>Variants</span><span>{result.product.has_variants ? "Yes" : "No"}</span></div>
              <div className="metric-row"><span>Reviews</span><span>{result.product.review_count.toLocaleString()}</span></div>
              <div className="metric-row"><span>Rating</span><span>{result.product.rating ?? "—"}</span></div>
            </section>
          )}

          {activeTab === "conversion" && result.conversion_signals && (
            <>
              <section className="panel">
                <div className="section-heading"><h3>Conversion Signals</h3></div>
                <div className="metric-row"><span>CTA Buttons</span><span>{result.conversion_signals.cta_count}</span></div>
                <div className="metric-row"><span>CTA Texts</span><span style={{ fontSize: "0.78rem" }}>{result.conversion_signals.cta_texts.join(", ") || "—"}</span></div>
                <div className="metric-row"><span>Add to Cart</span><span style={{ color: result.conversion_signals.has_add_to_cart ? "#22c55e" : "#ef4444" }}>{result.conversion_signals.has_add_to_cart ? "✓" : "✗"}</span></div>
                <div className="metric-row"><span>Buy Now</span><span style={{ color: result.conversion_signals.has_buy_now ? "#22c55e" : "#ef4444" }}>{result.conversion_signals.has_buy_now ? "✓" : "✗"}</span></div>
                <div className="metric-row"><span>Trust Badges</span><span style={{ color: result.conversion_signals.has_trust_badges ? "#22c55e" : "#ef4444" }}>{result.conversion_signals.has_trust_badges ? "✓" : "✗"}</span></div>
                <div className="metric-row"><span>Return Policy</span><span style={{ color: result.conversion_signals.has_return_policy ? "#22c55e" : "#ef4444" }}>{result.conversion_signals.has_return_policy ? "✓" : "✗"}</span></div>
                <div className="metric-row"><span>Free Shipping</span><span style={{ color: result.conversion_signals.has_free_shipping ? "#22c55e" : "#ef4444" }}>{result.conversion_signals.has_free_shipping ? "✓" : "✗"}</span></div>
                <div className="metric-row"><span>Urgency Signals</span><span style={{ color: result.conversion_signals.has_urgency_signals ? "#22c55e" : "#ef4444" }}>{result.conversion_signals.has_urgency_signals ? "✓" : "✗"}</span></div>
                <div className="metric-row"><span>Social Proof</span><span>{result.conversion_signals.social_proof_count.toLocaleString()}</span></div>
                <div className="metric-row"><span>Stock Status</span><span>{result.conversion_signals.stock_indicator || "—"}</span></div>
              </section>
            </>
          )}

          {activeTab === "recommendations" && (
            <>
              {result.critical_issues.length > 0 && (
                <section className="panel" style={{ borderLeft: "3px solid #ef4444" }}>
                  <div className="section-heading"><h3 style={{ color: "#ef4444" }}>Critical Issues ({result.critical_issues.length})</h3></div>
                  {result.critical_issues.map((rec, i) => (
                    <div key={i} style={{ padding: "8px 0", borderBottom: i < result.critical_issues.length - 1 ? "1px solid var(--border)" : "none" }}>
                      <div style={{ fontWeight: 600, fontSize: "0.85rem", marginBottom: 4 }}>{rec.title}</div>
                      <div style={{ fontSize: "0.82rem", color: "var(--muted)", lineHeight: 1.5 }}>{rec.description}</div>
                    </div>
                  ))}
                </section>
              )}

              {result.quick_wins.length > 0 && (
                <section className="panel" style={{ borderLeft: "3px solid #22c55e" }}>
                  <div className="section-heading"><h3 style={{ color: "#22c55e" }}>Quick Wins ({result.quick_wins.length})</h3></div>
                  {result.quick_wins.map((rec, i) => (
                    <div key={i} style={{ padding: "8px 0", borderBottom: i < result.quick_wins.length - 1 ? "1px solid var(--border)" : "none" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                        <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>{rec.title}</span>
                        <span style={{ fontSize: "0.68rem", padding: "2px 6px", borderRadius: 4, background: getEffortColor(rec.effort) + "20", color: getEffortColor(rec.effort) }}>{rec.effort}</span>
                      </div>
                      <div style={{ fontSize: "0.82rem", color: "var(--muted)", lineHeight: 1.5 }}>{rec.description}</div>
                    </div>
                  ))}
                </section>
              )}

              <section className="panel">
                <div className="section-heading"><h3>All Recommendations ({result.recommendations.length})</h3></div>
                {result.recommendations.map((rec, i) => (
                  <div key={i} style={{ padding: "8px 0", borderBottom: i < result.recommendations.length - 1 ? "1px solid var(--border)" : "none" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <span style={{ fontSize: "0.68rem", padding: "2px 6px", borderRadius: 4, background: "var(--border)", fontWeight: 600 }}>#{rec.priority}</span>
                      <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>{rec.title}</span>
                      <span style={{ fontSize: "0.68rem", padding: "2px 6px", borderRadius: 4, background: getImpactColor(rec.impact) + "20", color: getImpactColor(rec.impact) }}>{rec.impact}</span>
                      <span style={{ fontSize: "0.68rem", padding: "2px 6px", borderRadius: 4, background: getEffortColor(rec.effort) + "20", color: getEffortColor(rec.effort) }}>{rec.effort}</span>
                      <span style={{ fontSize: "0.68rem", padding: "2px 6px", borderRadius: 4, background: "var(--border)", textTransform: "capitalize" }}>{rec.category}</span>
                    </div>
                    <div style={{ fontSize: "0.82rem", color: "var(--muted)", lineHeight: 1.5 }}>{rec.description}</div>
                  </div>
                ))}
              </section>
            </>
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
        .input-group {
          display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
        }
      `}</style>
    </div>
  );
}
