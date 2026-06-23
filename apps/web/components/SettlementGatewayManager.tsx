"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import type {
  WorkspaceBillingSettlementGatewayHistoryReport,
  WorkspaceBillingSettlementGatewayPolicyUpdateRequest,
  WorkspaceBillingSettlementGatewayReport,
  WorkspaceBillingSettlementGatewayRoute,
} from "@seo-ad-autopilot/contracts";
import { updateWorkspaceBillingGatewayPolicy } from "@/lib/api";
import { StatusPill } from "@/components/StatusPill";

type EditableRoute = {
  providerName: string;
  enabled: "true" | "false";
  fallbackProviderName: string;
  priority: string;
  notes: string;
};

function toEditable(route: WorkspaceBillingSettlementGatewayRoute): EditableRoute {
  return {
    providerName: route.providerName,
    enabled: route.enabled ? "true" : "false",
    fallbackProviderName: route.fallbackProviderName,
    priority: String(route.priority),
    notes: route.notes.join("\n"),
  };
}

function asPriority(raw: string): number {
  const value = Number(raw);
  if (Number.isNaN(value)) return 100;
  return Math.max(0, Math.trunc(value));
}

export function SettlementGatewayManager({
  report,
  history,
}: {
  report: WorkspaceBillingSettlementGatewayReport;
  history?: WorkspaceBillingSettlementGatewayHistoryReport | null;
}) {
  const router = useRouter();
  const [gatewayEnabled, setGatewayEnabled] = useState(report.policy.gatewayEnabled ? "true" : "false");
  const [strictRouting, setStrictRouting] = useState(report.policy.strictRouting ? "true" : "false");
  const [defaultProviderName, setDefaultProviderName] = useState(report.policy.defaultProviderName);
  const [fallbackProviderName, setFallbackProviderName] = useState(report.policy.fallbackProviderName);
  const [rows, setRows] = useState<EditableRoute[]>(report.policy.routes.map(toEditable));
  const [message, setMessage] = useState("Ready");
  const [isPending, startTransition] = useTransition();

  function updateRow(index: number, patch: Partial<EditableRoute>) {
    setRows((current) => current.map((item, idx) => (idx === index ? { ...item, ...patch } : item)));
  }

  function addRow() {
    setRows((current) => [
      ...current,
      {
        providerName: "manual",
        enabled: "true",
        fallbackProviderName: "manual",
        priority: String((current.length + 1) * 10),
        notes: "",
      },
    ]);
  }

  function removeRow(index: number) {
    setRows((current) => current.filter((_, idx) => idx !== index));
  }

  async function save() {
    setMessage("Saving settlement gateway...");
    try {
      const payload: WorkspaceBillingSettlementGatewayPolicyUpdateRequest = {
        gatewayEnabled: gatewayEnabled === "true",
        strictRouting: strictRouting === "true",
        defaultProviderName: defaultProviderName.trim() || "manual",
        fallbackProviderName: fallbackProviderName.trim() || "manual",
        routes: rows
          .map((row) => ({
            providerName: row.providerName.trim() || "manual",
            enabled: row.enabled === "true",
            fallbackProviderName: row.fallbackProviderName.trim() || "manual",
            priority: asPriority(row.priority),
            notes: row.notes
              .split("\n")
              .map((item) => item.trim())
              .filter((item) => item.length > 0),
          }))
          .filter((route) => route.providerName.length > 0),
      };
      const result = await updateWorkspaceBillingGatewayPolicy(payload);
      setGatewayEnabled(result.policy.gatewayEnabled ? "true" : "false");
      setStrictRouting(result.policy.strictRouting ? "true" : "false");
      setDefaultProviderName(result.policy.defaultProviderName);
      setFallbackProviderName(result.policy.fallbackProviderName);
      setRows(result.policy.routes.map(toEditable));
      setMessage(`Saved ${result.routeReadyCount}/${result.routeCount} ready settlement routes.`);
      startTransition(() => router.refresh());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save settlement gateway.");
    }
  }

  return (
    <div className="stack" style={{ marginTop: 12 }}>
      <div className="stat-grid">
        <section className="stat-card stat-card-accent">
          <div className="stat-card-label">Gateway</div>
          <div className="stat-card-value">{report.gatewayReady ? "ready" : "partial"}</div>
          <div className="stat-card-caption">{report.routeReadyCount}/{report.routeCount} routes are ready</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Enabled</div>
          <div className="stat-card-value">{report.policy.gatewayEnabled ? "on" : "off"}</div>
          <div className="stat-card-caption">Strict routing {report.policy.strictRouting ? "enabled" : "disabled"}</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Providers</div>
          <div className="stat-card-value">{report.providerCount}</div>
          <div className="stat-card-caption">Settlement routing providers configured</div>
        </section>
      </div>
      <div className="project-foot">
        <span>Settlement gateway</span>
        <StatusPill tone={report.gatewayReady ? "good" : "warn"}>{report.gatewayReady ? "ready" : "needs routes"}</StatusPill>
      </div>
      <div className="stack" style={{ marginTop: 12 }}>
        <select value={gatewayEnabled} onChange={(event) => setGatewayEnabled(event.target.value as "true" | "false")}>
          <option value="true">gateway enabled</option>
          <option value="false">gateway disabled</option>
        </select>
        <select value={strictRouting} onChange={(event) => setStrictRouting(event.target.value as "true" | "false")}>
          <option value="true">strict routing on</option>
          <option value="false">strict routing off</option>
        </select>
        <input value={defaultProviderName} onChange={(event) => setDefaultProviderName(event.target.value)} placeholder="default settlement provider" />
        <input value={fallbackProviderName} onChange={(event) => setFallbackProviderName(event.target.value)} placeholder="fallback settlement provider" />
      </div>
      <div className="project-foot">
        <span>{report.warnings.length ? report.warnings.join(" · ") : "No settlement gateway warnings."}</span>
        <button className="button button-secondary" type="button" onClick={addRow}>
          Add route
        </button>
        <button className="button button-primary" type="button" onClick={() => void save()} disabled={isPending}>
          Save settlement gateway
        </button>
      </div>
      <div className="grid-two">
        <div className="suite-card">
          <div className="project-foot">
            <span>Route readiness</span>
            <StatusPill tone={report.gatewayReady ? "good" : "warn"}>{report.routeReadyCount}</StatusPill>
          </div>
          <ul className="metric-list">
            {report.routes.slice(0, 5).map((route) => (
              <li key={`${route.providerName}-${route.priority}`}>
                {route.providerName}: {route.resolvedProviderName} ({route.routeReady ? "ready" : "fallback"}) · priority {route.priority}
              </li>
            ))}
          </ul>
        </div>
        <div className="suite-card">
          <div className="project-foot">
            <span>Recommendations</span>
            <StatusPill tone={report.recommendations.length ? "warn" : "good"}>{report.recommendations.length}</StatusPill>
          </div>
          <ul className="metric-list">
            {report.recommendations.length === 0 ? <li>No recommendations.</li> : report.recommendations.map((item) => <li key={item}>{item}</li>)}
          </ul>
          <div className="project-copy">This gateway models routed settlement execution. External payment network integration can be layered later.</div>
        </div>
        <div className="suite-card">
          <div className="project-foot">
            <span>Gateway replay</span>
            <StatusPill tone={history && history.total > 0 ? "good" : "neutral"}>{history?.total ?? 0}</StatusPill>
          </div>
          <ul className="metric-list">
            <li>Projects: {history?.projectCount ?? 0}</li>
            <li>Gateway ready: {history?.gatewayReadyCount ?? 0}</li>
            <li>Route ready: {history?.gatewayRouteReadyCount ?? 0}</li>
            <li>Live: {history?.liveCount ?? 0}</li>
            <li>Dry-run: {history?.dryRunCount ?? 0}</li>
            <li>Blocked: {history?.blockedCount ?? 0}</li>
            <li>Failed: {history?.failedCount ?? 0}</li>
            <li>
              Latest:{" "}
              {history?.latestProjectName
                ? `${history.latestProjectName} (${history.latestProjectId ?? "n/a"})`
                : "n/a"}
            </li>
            <li>
              Latest route: {history?.latestGatewayRouteProviderName ?? "n/a"} · priority {history?.latestGatewayRoutePriority ?? "n/a"} · reason{" "}
              {history?.latestGatewayRouteReason ?? "n/a"}
            </li>
            <li>
              Latest execution: {history?.latestGatewayProviderName ?? "n/a"} · failure {history?.latestFailureCode ?? "none"} · retryable{" "}
              {history?.latestRetryable ? "yes" : "no"}
            </li>
          </ul>
        </div>
      </div>
      {rows.map((row, index) => (
        <article className="audit-card" key={`${row.providerName}-${index}`}>
          <div className="project-foot">
            <span>{row.providerName}</span>
            <button className="button button-secondary" type="button" onClick={() => removeRow(index)}>
              Delete
            </button>
          </div>
          <div className="stack" style={{ marginTop: 12 }}>
            <input value={row.providerName} onChange={(event) => updateRow(index, { providerName: event.target.value })} placeholder="provider name" />
            <select value={row.enabled} onChange={(event) => updateRow(index, { enabled: event.target.value as EditableRoute["enabled"] })}>
              <option value="true">enabled</option>
              <option value="false">disabled</option>
            </select>
            <input value={row.fallbackProviderName} onChange={(event) => updateRow(index, { fallbackProviderName: event.target.value })} placeholder="fallback provider" />
            <input value={row.priority} onChange={(event) => updateRow(index, { priority: event.target.value })} placeholder="priority" />
            <textarea value={row.notes} onChange={(event) => updateRow(index, { notes: event.target.value })} placeholder="notes, one per line" rows={3} />
          </div>
        </article>
      ))}
      <div className="alert-box">{message}</div>
    </div>
  );
}
