import type { PreviewArtifact } from "@seo-ad-autopilot/contracts";
import { getServerI18n } from "@/lib/i18n/server";

export function PreviewDiff({ preview }: { preview: PreviewArtifact }) {
  const { t } = getServerI18n();
  return (
    <section className="panel panel-preview">
      <div className="section-heading">
        <div>
          <div className="eyebrow">{t("project_detail.preview")}</div>
          <h2>{t("project_detail.before_after")}</h2>
        </div>
        <p>{preview.diffSummary}</p>
      </div>
      <div className="preview-grid">
        <div className="preview-card">
          <div className="preview-label">{t("project_detail.before")}</div>
          <pre>{preview.beforeHtml}</pre>
        </div>
        <div className="preview-card preview-card-after">
          <div className="preview-label">{t("project_detail.after")}</div>
          <pre>{preview.afterHtml}</pre>
        </div>
      </div>
      <div className="preview-meta">
        <div>
          <div className="preview-label">{t("project_detail.dom_insertions")}</div>
          <ul className="bullets">
            {preview.domInsertions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="preview-label">{t("project_detail.css_diff")}</div>
          <pre className="code-block">{preview.cssDiff}</pre>
        </div>
        <div>
          <div className="preview-label">{t("project_detail.performance_budget")}</div>
          <div className="metric-row">
            <span>{t("project_detail.baseline_lcp")}</span>
            <strong>{preview.performanceBudget.baselineLcpMs}ms</strong>
          </div>
          <div className="metric-row">
            <span>{t("project_detail.estimated_lcp")}</span>
            <strong>{preview.performanceBudget.estimatedLcpMs}ms</strong>
          </div>
          <div className="metric-row">
            <span>{t("project_detail.budget_delta")}</span>
            <strong>{preview.performanceBudget.budgetDeltaMs}ms</strong>
          </div>
        </div>
      </div>
    </section>
  );
}
