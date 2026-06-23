"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import type { OnCallCoverageReport, OnCallPolicyCollection, OnCallRoute } from "@seo-ad-autopilot/contracts";
import { updateOnCallPolicyCollection } from "@/lib/api";
import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";
import { StatusPill } from "@/components/StatusPill";

type EditableRoute = {
  routeId: string;
  enabled: "true" | "false";
  description: string;
  categories: string;
  severities: string;
  providers: string;
  blocking: "any" | "true" | "false";
  primaryChannels: string;
  escalationChannels: string;
  escalationAfterMinutes: string;
  rotationMembers: string;
  rotationTimezone: string;
  rotationHandoffHour: string;
};

function toCsv(items: string[]): string {
  return items.join(",");
}

function parseCsv(raw: string): string[] {
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function toEditable(route: OnCallRoute): EditableRoute {
  return {
    routeId: route.routeId,
    enabled: route.enabled ? "true" : "false",
    description: route.description ?? "",
    categories: toCsv(route.categories),
    severities: toCsv(route.severities),
    providers: toCsv(route.providers),
    blocking: route.blocking === true ? "true" : route.blocking === false ? "false" : "any",
    primaryChannels: toCsv(route.primaryChannels),
    escalationChannels: toCsv(route.escalationChannels),
    escalationAfterMinutes: String(route.escalationAfterMinutes ?? 15),
    rotationMembers: toCsv(route.rotationMembers),
    rotationTimezone: route.rotationTimezone ?? "UTC",
    rotationHandoffHour: String(route.rotationHandoffHour ?? 9),
  };
}

function asValidHour(raw: string): number {
  const value = Number(raw);
  if (Number.isNaN(value)) return 9;
  return Math.max(0, Math.min(23, Math.trunc(value)));
}

function asValidMinutes(raw: string): number {
  const value = Number(raw);
  if (Number.isNaN(value)) return 15;
  return Math.max(1, Math.min(240, Math.trunc(value)));
}

export function OnCallPolicyManager({
  policy,
  coverage,
}: {
  policy: OnCallPolicyCollection;
  coverage: OnCallCoverageReport;
}) {
  const router = useRouter();
  const [rows, setRows] = useState<EditableRoute[]>(policy.routes.map(toEditable));
  const [message, setMessage] = useState("Ready");
  const [isPending, startTransition] = useTransition();

  function updateRow(index: number, patch: Partial<EditableRoute>) {
    setRows((current) => current.map((item, idx) => (idx === index ? { ...item, ...patch } : item)));
  }

  function addRow() {
    setRows((current) => [
      ...current,
      {
        routeId: `route_${Date.now()}`,
        enabled: "true",
        description: "",
        categories: "",
        severities: "critical",
        providers: "",
        blocking: "any",
        primaryChannels: "file:///tmp/oncall-primary.ndjson",
        escalationChannels: "file:///tmp/oncall-escalation.ndjson",
        escalationAfterMinutes: "15",
        rotationMembers: "",
        rotationTimezone: "UTC",
        rotationHandoffHour: "9",
      },
    ]);
  }

  function removeRow(index: number) {
    setRows((current) => current.filter((_, idx) => idx !== index));
  }

  async function save() {
    setMessage("Saving on-call policy...");
    try {
      const payload = {
        routes: rows
          .map((row) => ({
            routeId: row.routeId.trim(),
            enabled: row.enabled === "true",
            description: row.description.trim(),
            categories: parseCsv(row.categories),
            severities: parseCsv(row.severities),
            providers: parseCsv(row.providers),
            blocking: row.blocking === "any" ? null : row.blocking === "true",
            primaryChannels: parseCsv(row.primaryChannels),
            escalationChannels: parseCsv(row.escalationChannels),
            escalationAfterMinutes: asValidMinutes(row.escalationAfterMinutes),
            rotationMembers: parseCsv(row.rotationMembers),
            rotationTimezone: row.rotationTimezone.trim() || "UTC",
            rotationHandoffHour: asValidHour(row.rotationHandoffHour),
            updatedAt: new Date().toISOString(),
          }))
          .filter((row) => row.routeId.length > 0),
      };
      const result = await updateOnCallPolicyCollection(payload);
      setRows(result.routes.map(toEditable));
      setMessage(`Saved ${result.routes.length} routes.`);
      startTransition(() => router.refresh());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save on-call policy.");
    }
  }

  return (
    <div className="stack" style={{ marginTop: 12 }}>
      <div className="stat-grid">
        <section className="stat-card stat-card-accent">
          <div className="stat-card-label">Configured routes</div>
          <div className="stat-card-value">{coverage.routeCount}</div>
          <div className="stat-card-caption">{coverage.rotatingRouteCount} routes currently rotate members</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Rotation coverage</div>
          <div className="stat-card-value">{coverage.rotatingRouteCount}</div>
          <div className="stat-card-caption">Deterministic handoff rules are active on these routes</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Last handoff</div>
          <div className="stat-card-value">{coverage.items.filter((item) => item.nextHandoffAt).length}</div>
          <div className="stat-card-caption">Coverage items with a scheduled next handoff</div>
        </section>
      </div>
      <div className="project-foot">
        <span>Manage routes</span>
        <div style={{ display: "flex", gap: 12 }}>
          <button className="button button-secondary" type="button" onClick={addRow}>
            Add route
          </button>
          <button className="button button-primary" type="button" onClick={() => void save()} disabled={isPending}>
            Save on-call policy
          </button>
        </div>
      </div>
      <ActionSummaryBadge
        tone={rows.length > 0 ? "idle" : "error"}
        title="On-call policy"
        description={rows.length > 0 ? `${rows.length} editable routes loaded from /api/alerts/oncall-policy.` : "No routes configured yet."}
      />
      {rows.map((row, index) => {
        const coverageItem = coverage.items.find((item) => item.routeId === row.routeId);
        return (
          <article className="audit-card" key={`${row.routeId}-${index}`}>
            <div className="audit-head">
              <strong className="audit-title">{row.routeId || `route-${index + 1}`}</strong>
              <StatusPill tone={row.enabled === "true" ? "good" : "neutral"}>{row.enabled === "true" ? "enabled" : "disabled"}</StatusPill>
            </div>
            <div className="project-foot">
              <span>Coverage</span>
              <strong>
                {coverageItem ? `${coverageItem.memberCount} members · ${coverageItem.rotationEnabled ? "rotating" : "static"}` : "not in coverage report"}
              </strong>
            </div>
            <div className="stack" style={{ marginTop: 12 }}>
              <input value={row.routeId} onChange={(event) => updateRow(index, { routeId: event.target.value })} placeholder="route id" />
              <select value={row.enabled} onChange={(event) => updateRow(index, { enabled: event.target.value as EditableRoute["enabled"] })}>
                <option value="true">enabled</option>
                <option value="false">disabled</option>
              </select>
              <input value={row.description} onChange={(event) => updateRow(index, { description: event.target.value })} placeholder="description" />
              <input value={row.categories} onChange={(event) => updateRow(index, { categories: event.target.value })} placeholder="categories (csv)" />
              <input value={row.severities} onChange={(event) => updateRow(index, { severities: event.target.value })} placeholder="severities (csv)" />
              <input value={row.providers} onChange={(event) => updateRow(index, { providers: event.target.value })} placeholder="providers (csv)" />
              <select value={row.blocking} onChange={(event) => updateRow(index, { blocking: event.target.value as EditableRoute["blocking"] })}>
                <option value="any">blocking:any</option>
                <option value="true">blocking:true</option>
                <option value="false">blocking:false</option>
              </select>
              <input value={row.primaryChannels} onChange={(event) => updateRow(index, { primaryChannels: event.target.value })} placeholder="primary channels (csv)" />
              <input value={row.escalationChannels} onChange={(event) => updateRow(index, { escalationChannels: event.target.value })} placeholder="escalation channels (csv)" />
              <input value={row.escalationAfterMinutes} onChange={(event) => updateRow(index, { escalationAfterMinutes: event.target.value })} placeholder="escalation minutes" />
              <input value={row.rotationMembers} onChange={(event) => updateRow(index, { rotationMembers: event.target.value })} placeholder="rotation members (csv)" />
              <input value={row.rotationTimezone} onChange={(event) => updateRow(index, { rotationTimezone: event.target.value })} placeholder="rotation timezone" />
              <input value={row.rotationHandoffHour} onChange={(event) => updateRow(index, { rotationHandoffHour: event.target.value })} placeholder="handoff hour" />
            </div>
            <div className="project-foot" style={{ marginTop: 12 }}>
              <span>Channels / rotation settings are stored directly in the policy JSON.</span>
              <button className="button button-secondary" type="button" onClick={() => removeRow(index)}>
                Delete route
              </button>
            </div>
          </article>
        );
      })}
      <div className="alert-box">{message}</div>
    </div>
  );
}
