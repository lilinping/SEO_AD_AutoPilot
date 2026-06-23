import type { PreviewArtifact } from "@seo-ad-autopilot/contracts";

export function PreviewDiff({ preview }: { preview: PreviewArtifact }) {
  return (
    <section className="panel panel-preview">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Preview</div>
          <h2>Before / After</h2>
        </div>
        <p>{preview.diffSummary}</p>
      </div>
      <div className="preview-grid">
        <div className="preview-card">
          <div className="preview-label">Before</div>
          <pre>{preview.beforeHtml}</pre>
        </div>
        <div className="preview-card preview-card-after">
          <div className="preview-label">After</div>
          <pre>{preview.afterHtml}</pre>
        </div>
      </div>
      <div className="preview-meta">
        <div>
          <div className="preview-label">DOM insertions</div>
          <ul className="bullets">
            {preview.domInsertions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="preview-label">CSS diff</div>
          <pre className="code-block">{preview.cssDiff}</pre>
        </div>
        <div>
          <div className="preview-label">Performance budget</div>
          <div className="metric-row">
            <span>Baseline LCP</span>
            <strong>{preview.performanceBudget.baselineLcpMs}ms</strong>
          </div>
          <div className="metric-row">
            <span>Estimated LCP</span>
            <strong>{preview.performanceBudget.estimatedLcpMs}ms</strong>
          </div>
          <div className="metric-row">
            <span>Budget delta</span>
            <strong>{preview.performanceBudget.budgetDeltaMs}ms</strong>
          </div>
        </div>
      </div>
    </section>
  );
}
