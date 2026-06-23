import type { WorkspaceModelGatewayProviderStatusReport } from "@seo-ad-autopilot/contracts";

import { StatCard } from "@/components/StatCard";
import { StatusPill } from "@/components/StatusPill";
import { formatDateTime } from "@/lib/format";

type ModelGatewayProviderStatusPanelProps = {
  report: WorkspaceModelGatewayProviderStatusReport;
};

function toneForRoute(routeReady: boolean, strictReady: boolean) {
  if (strictReady) return "good";
  if (routeReady) return "warn";
  return "danger";
}

export function ModelGatewayProviderStatusPanel({ report }: ModelGatewayProviderStatusPanelProps) {
  return (
    <div className="stack" style={{ marginTop: 16 }}>
      <div className="suite-grid">
        <StatCard label="Routes" value={String(report.routeCount)} caption={report.gatewayEnabled ? "gateway enabled" : "gateway disabled"} accent />
        <StatCard label="Ready" value={String(report.routeReadyCount)} caption="routes ready for routing" />
        <StatCard label="Strict ready" value={String(report.strictReadyCount)} caption="routes without fallback" />
        <StatCard label="Providers" value={String(report.providerCount)} caption="unique provider targets" />
      </div>
      <div className="project-foot">
        <span>Provider snapshot</span>
        <span>{formatDateTime(report.generatedAt)}</span>
      </div>
      {report.warnings.length > 0 ? (
        <div className="alert-box">
          <strong>Warnings</strong>
          <div className="project-copy" style={{ marginTop: 8 }}>
            {report.warnings.join(" · ")}
          </div>
        </div>
      ) : null}
      <div className="stack">
        {report.entries.map((entry) => (
          <article className="audit-card" key={`${entry.priority}:${entry.routeSuite}`}>
            <div className="audit-head">
              <strong className="audit-title">{entry.routeSuite}</strong>
              <StatusPill tone={toneForRoute(entry.routeReady, entry.strictReady)}>
                {entry.strictReady ? "strict-ready" : entry.routeReady ? "route-ready" : "fallback"}
              </StatusPill>
            </div>
            <div className="audit-meta">
              {entry.providerName} · {entry.enabled ? "enabled" : "disabled"} · priority {entry.priority} · gateway{" "}
              {entry.resolvedProviderName}
            </div>
            <div className="metric-row">
              <span>Fallback</span>
              <strong>{entry.fallbackProviderName}</strong>
            </div>
            <div className="metric-row">
              <span>Strict</span>
              <strong>{entry.strictReady ? "yes" : "no"}</strong>
            </div>
            <div className="metric-row">
              <span>Reason</span>
              <strong>{entry.fallbackReason ?? "n/a"}</strong>
            </div>
            <div className="project-copy" style={{ marginTop: 8 }}>
              {entry.notes.length > 0 ? entry.notes.join(" · ") : "No additional notes."}
            </div>
          </article>
        ))}
      </div>
      {report.recommendations.length > 0 ? (
        <div className="project-copy" style={{ marginTop: 4 }}>
          {report.recommendations.join(" · ")}
        </div>
      ) : null}
    </div>
  );
}
