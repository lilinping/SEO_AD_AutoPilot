import type { WorkspaceBillingSettlementGatewayProviderStatusReport } from "@seo-ad-autopilot/contracts";

import { StatCard } from "@/components/StatCard";
import { StatusPill } from "@/components/StatusPill";
import { formatDateTime } from "@/lib/format";

type BillingGatewayProviderStatusPanelProps = {
  report: WorkspaceBillingSettlementGatewayProviderStatusReport;
};

function toneForProviderStatus(routeReady: boolean, strictReady: boolean, configured: boolean, authConfigured: boolean) {
  if (strictReady) return "good";
  if (routeReady && configured && !authConfigured) return "warn";
  if (routeReady) return "warn";
  return "danger";
}

export function BillingGatewayProviderStatusPanel({ report }: BillingGatewayProviderStatusPanelProps) {
  return (
    <div className="stack" style={{ marginTop: 16 }}>
      <div className="suite-grid">
        <StatCard label="Providers" value={String(report.providerCount)} caption={report.gatewayEnabled ? "gateway enabled" : "gateway disabled"} accent />
        <StatCard label="Configured" value={String(report.configuredCount)} caption="routes with endpoints" />
        <StatCard label="Auth ready" value={String(report.authConfiguredCount)} caption="routes with credentials" />
        <StatCard
          label="Strict ready"
          value={String(report.strictReadyCount)}
          caption={report.gatewayReady ? "ready for routed execution" : "needs endpoint + auth"}
        />
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
          <article className="audit-card" key={`${entry.priority}:${entry.providerName}`}>
            <div className="audit-head">
              <strong className="audit-title">{entry.providerLabel}</strong>
              <StatusPill tone={toneForProviderStatus(entry.routeReady, entry.strictReady, entry.configured, entry.authConfigured)}>
                {entry.strictReady ? "strict-ready" : entry.routeReady ? "route-ready" : "fallback"}
              </StatusPill>
            </div>
            <div className="audit-meta">
              {entry.providerName} · {entry.routeEnabled ? "enabled" : "disabled"} · priority {entry.priority} · route{" "}
              {entry.routeReady ? "ready" : "fallback"} · auth {entry.authConfigured ? "ready" : "missing"} · gateway{" "}
              {entry.resolvedProviderName}
            </div>
            <div className="metric-row">
              <span>Endpoint</span>
              <strong>{entry.endpoint ?? "n/a"}</strong>
            </div>
            <div className="metric-row">
              <span>Auth</span>
              <strong>
                {entry.authHeader} · {entry.authSource}
              </strong>
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
