"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import type { AlertRule } from "@seo-ad-autopilot/contracts";
import { updateAlertRuleCollection } from "@/lib/api";

type EditableRule = {
  ruleId: string;
  enabled: "true" | "false";
  description: string;
  categories: string;
  failureCodes: string;
  providers: string;
  setBlocking: "any" | "true" | "false";
  setSeverity: "any" | "critical" | "warning" | "info";
  priority: string;
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

function toEditable(rule: AlertRule): EditableRule {
  return {
    ruleId: rule.ruleId,
    enabled: rule.enabled ? "true" : "false",
    description: rule.description ?? "",
    categories: toCsv(rule.categories),
    failureCodes: toCsv(rule.failureCodes),
    providers: toCsv(rule.providers),
    setBlocking: rule.setBlocking === true ? "true" : rule.setBlocking === false ? "false" : "any",
    setSeverity: rule.setSeverity ?? "any",
    priority: String(rule.priority ?? 100),
  };
}

function asPriority(raw: string): number {
  const value = Number(raw);
  if (Number.isNaN(value)) return 100;
  return Math.max(0, Math.min(1000, Math.trunc(value)));
}

export function AlertRuleManager({ rules }: { rules: AlertRule[] }) {
  const router = useRouter();
  const [rows, setRows] = useState<EditableRule[]>(rules.map(toEditable));
  const [message, setMessage] = useState("Ready");
  const [isPending, startTransition] = useTransition();

  function updateRow(index: number, patch: Partial<EditableRule>) {
    setRows((current) => current.map((item, idx) => (idx === index ? { ...item, ...patch } : item)));
  }

  function addRow() {
    setRows((current) => [
      ...current,
      {
        ruleId: `rule_${Date.now()}`,
        enabled: "true",
        description: "",
        categories: "",
        failureCodes: "",
        providers: "",
        setBlocking: "any",
        setSeverity: "any",
        priority: "100",
      },
    ]);
  }

  function removeRow(index: number) {
    setRows((current) => current.filter((_, idx) => idx !== index));
  }

  async function save() {
    setMessage("Saving alert rules...");
    try {
      const payload = {
        rules: rows
          .map((row) => ({
            ruleId: row.ruleId.trim(),
            enabled: row.enabled === "true",
            description: row.description.trim(),
            categories: parseCsv(row.categories),
            failureCodes: parseCsv(row.failureCodes),
            providers: parseCsv(row.providers),
            setBlocking: row.setBlocking === "any" ? null : row.setBlocking === "true",
            setSeverity: row.setSeverity === "any" ? null : row.setSeverity,
            priority: asPriority(row.priority),
            updatedAt: new Date().toISOString(),
          }))
          .filter((row) => row.ruleId.length > 0),
      };
      const result = await updateAlertRuleCollection(payload);
      setRows(result.rules.map(toEditable));
      setMessage(`Saved ${result.rules.length} rules.`);
      startTransition(() => router.refresh());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save alert rules.");
    }
  }

  return (
    <div className="stack" style={{ marginTop: 12 }}>
      <div className="project-foot">
        <span>Manage rules</span>
        <div style={{ display: "flex", gap: 12 }}>
          <button className="button button-secondary" type="button" onClick={addRow}>
            Add rule
          </button>
          <button className="button button-primary" type="button" onClick={() => void save()} disabled={isPending}>
            Save alert rules
          </button>
        </div>
      </div>
      {rows.map((row, index) => (
        <article className="audit-card" key={`${row.ruleId}-${index}`}>
          <div className="project-foot">
            <span>{row.ruleId}</span>
            <button className="button button-secondary" type="button" onClick={() => removeRow(index)}>
              Delete
            </button>
          </div>
          <div className="stack" style={{ marginTop: 12 }}>
            <input value={row.ruleId} onChange={(event) => updateRow(index, { ruleId: event.target.value })} placeholder="rule id" />
            <select value={row.enabled} onChange={(event) => updateRow(index, { enabled: event.target.value as EditableRule["enabled"] })}>
              <option value="true">enabled</option>
              <option value="false">disabled</option>
            </select>
            <input value={row.description} onChange={(event) => updateRow(index, { description: event.target.value })} placeholder="description" />
            <input value={row.categories} onChange={(event) => updateRow(index, { categories: event.target.value })} placeholder="categories (csv)" />
            <input value={row.failureCodes} onChange={(event) => updateRow(index, { failureCodes: event.target.value })} placeholder="failure codes (csv)" />
            <input value={row.providers} onChange={(event) => updateRow(index, { providers: event.target.value })} placeholder="providers (csv)" />
            <select value={row.setBlocking} onChange={(event) => updateRow(index, { setBlocking: event.target.value as EditableRule["setBlocking"] })}>
              <option value="any">set_blocking:any</option>
              <option value="true">set_blocking:true</option>
              <option value="false">set_blocking:false</option>
            </select>
            <select value={row.setSeverity} onChange={(event) => updateRow(index, { setSeverity: event.target.value as EditableRule["setSeverity"] })}>
              <option value="any">set_severity:any</option>
              <option value="critical">critical</option>
              <option value="warning">warning</option>
              <option value="info">info</option>
            </select>
            <input value={row.priority} onChange={(event) => updateRow(index, { priority: event.target.value })} placeholder="priority" />
          </div>
        </article>
      ))}
      <div className="alert-box">{message}</div>
    </div>
  );
}
