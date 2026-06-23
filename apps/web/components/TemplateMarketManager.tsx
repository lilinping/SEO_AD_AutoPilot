"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import type {
  WorkspaceTemplateMarketPolicyUpdateRequest,
  WorkspaceTemplateMarketReport,
  WorkspaceTemplateMarketTemplate,
} from "@seo-ad-autopilot/contracts";
import { updateWorkspaceTemplateMarketPolicy } from "@/lib/api";
import { StatusPill } from "@/components/StatusPill";

type EditableTemplate = {
  templateKey: string;
  enabled: "true" | "false";
  templateSurface: WorkspaceTemplateMarketTemplate["templateSurface"];
  targetLocale: string;
  targetProjectIds: string;
  coverageRequirements: string;
  templateSource: string;
  notes: string;
};

function toEditable(template: WorkspaceTemplateMarketTemplate): EditableTemplate {
  return {
    templateKey: template.templateKey,
    enabled: template.enabled ? "true" : "false",
    templateSurface: template.templateSurface,
    targetLocale: template.targetLocale ?? "",
    targetProjectIds: template.targetProjectIds.join(", "),
    coverageRequirements: template.coverageRequirements.join("\n"),
    templateSource: template.templateSource,
    notes: template.notes.join("\n"),
  };
}

function parseCommaList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function parseLines(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

export function TemplateMarketManager({ report }: { report: WorkspaceTemplateMarketReport }) {
  const router = useRouter();
  const [marketEnabled, setMarketEnabled] = useState(report.policy.marketEnabled ? "true" : "false");
  const [strictMarket, setStrictMarket] = useState(report.policy.strictMarket ? "true" : "false");
  const [defaultTemplateSurface, setDefaultTemplateSurface] = useState(report.policy.defaultTemplateSurface);
  const [rows, setRows] = useState<EditableTemplate[]>(report.policy.templates.map(toEditable));
  const [message, setMessage] = useState("Ready");
  const [isPending, startTransition] = useTransition();

  function updateRow(index: number, patch: Partial<EditableTemplate>) {
    setRows((current) => current.map((item, idx) => (idx === index ? { ...item, ...patch } : item)));
  }

  function addRow() {
    setRows((current) => [
      ...current,
      {
        templateKey: `template-${current.length + 1}`,
        enabled: "true",
        templateSurface: defaultTemplateSurface,
        targetLocale: "en-US",
        targetProjectIds: "",
        coverageRequirements: "",
        templateSource: "workspace",
        notes: "",
      },
    ]);
  }

  function removeRow(index: number) {
    setRows((current) => current.filter((_, idx) => idx !== index));
  }

  async function save() {
    setMessage("Saving template market policy...");
    try {
      const payload: WorkspaceTemplateMarketPolicyUpdateRequest = {
        marketEnabled: marketEnabled === "true",
        strictMarket: strictMarket === "true",
        defaultTemplateSurface,
        templates: rows.map((row, index) => ({
          templateKey: row.templateKey.trim() || `template-${index + 1}`,
          enabled: row.enabled === "true",
          templateSurface: row.templateSurface,
          targetLocale: row.targetLocale.trim() || null,
          targetProjectIds: parseCommaList(row.targetProjectIds),
          coverageRequirements: parseLines(row.coverageRequirements),
          templateSource: row.templateSource.trim() || "workspace",
          notes: parseLines(row.notes),
        })),
      };
      const result = await updateWorkspaceTemplateMarketPolicy(payload);
      setMarketEnabled(result.policy.marketEnabled ? "true" : "false");
      setStrictMarket(result.policy.strictMarket ? "true" : "false");
      setDefaultTemplateSurface(result.policy.defaultTemplateSurface);
      setRows(result.policy.templates.map(toEditable));
      setMessage(`Saved ${result.readyTemplateCount}/${result.templateCount} ready templates.`);
      startTransition(() => router.refresh());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save template market policy.");
    }
  }

  return (
    <div className="stack" style={{ marginTop: 12 }}>
      <div className="stat-grid">
        <section className="stat-card stat-card-accent">
          <div className="stat-card-label">Workspace ready</div>
          <div className="stat-card-value">{report.workspaceReady ? "ready" : "partial"}</div>
          <div className="stat-card-caption">{report.readyTemplateCount}/{report.templateCount} templates are rollout-ready</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Enabled</div>
          <div className="stat-card-value">{report.policy.marketEnabled ? "on" : "off"}</div>
          <div className="stat-card-caption">Strict market {report.policy.strictMarket ? "enabled" : "disabled"}</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Coverage</div>
          <div className="stat-card-value">{report.projectScopeCount}</div>
          <div className="stat-card-caption">Projects bound to reusable template packages</div>
        </section>
      </div>
      <div className="project-foot">
        <span>Template market editor</span>
        <StatusPill tone={report.workspaceReady ? "good" : "warn"}>{report.workspaceReady ? "rollout-ready" : "needs setup"}</StatusPill>
      </div>
      <div className="stack" style={{ marginTop: 12 }}>
        <select value={marketEnabled} onChange={(event) => setMarketEnabled(event.target.value as "true" | "false")}>
          <option value="true">template market enabled</option>
          <option value="false">template market disabled</option>
        </select>
        <select value={strictMarket} onChange={(event) => setStrictMarket(event.target.value as "true" | "false")}>
          <option value="true">strict market on</option>
          <option value="false">strict market off</option>
        </select>
        <select
          value={defaultTemplateSurface}
          onChange={(event) => setDefaultTemplateSurface(event.target.value as EditableTemplate["templateSurface"])}
        >
          <option value="content">content</option>
          <option value="site">site</option>
          <option value="ad">ad</option>
          <option value="technical_seo">technical_seo</option>
          <option value="ui">ui</option>
        </select>
      </div>
      <div className="project-foot">
        <span>{report.warnings.length ? report.warnings.join(" · ") : "No template market warnings."}</span>
        <button className="button button-secondary" type="button" onClick={addRow}>
          Add template
        </button>
        <button className="button button-primary" type="button" onClick={() => void save()} disabled={isPending}>
          Save template market
        </button>
      </div>
      <div className="grid-two">
        <div className="suite-card">
          <div className="project-foot">
            <span>Readiness summary</span>
            <StatusPill tone={report.workspaceReady ? "good" : "warn"}>{report.readyTemplateCount}</StatusPill>
          </div>
          <ul className="metric-list">
            {report.templates.slice(0, 5).map((template) => (
              <li key={template.templateKey}>
                {template.templateKey}: {template.templateReady ? "ready" : "pending"} · {template.templateSurface} · {template.coverageRequirementCount} requirements
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
          <div className="project-copy">The template market persists curated packages and checks whether real project evidence covers the declared requirements.</div>
        </div>
      </div>
      {rows.map((row, index) => (
        <article className="audit-card" key={`${row.templateKey}-${index}`}>
          <div className="project-foot">
            <span>{row.templateKey}</span>
            <button className="button button-secondary" type="button" onClick={() => removeRow(index)}>
              Delete
            </button>
          </div>
          <div className="stack" style={{ marginTop: 12 }}>
            <input value={row.templateKey} onChange={(event) => updateRow(index, { templateKey: event.target.value })} placeholder="template key" />
            <select value={row.enabled} onChange={(event) => updateRow(index, { enabled: event.target.value as EditableTemplate["enabled"] })}>
              <option value="true">enabled</option>
              <option value="false">disabled</option>
            </select>
            <select
              value={row.templateSurface}
              onChange={(event) => updateRow(index, { templateSurface: event.target.value as EditableTemplate["templateSurface"] })}
            >
              <option value="content">content</option>
              <option value="site">site</option>
              <option value="ad">ad</option>
              <option value="technical_seo">technical_seo</option>
              <option value="ui">ui</option>
            </select>
            <input value={row.targetLocale} onChange={(event) => updateRow(index, { targetLocale: event.target.value })} placeholder="target locale" />
            <input
              value={row.targetProjectIds}
              onChange={(event) => updateRow(index, { targetProjectIds: event.target.value })}
              placeholder="project ids, comma separated"
            />
            <textarea
              value={row.coverageRequirements}
              onChange={(event) => updateRow(index, { coverageRequirements: event.target.value })}
              placeholder="coverage requirements, one per line"
              rows={3}
            />
            <input value={row.templateSource} onChange={(event) => updateRow(index, { templateSource: event.target.value })} placeholder="template source" />
            <textarea value={row.notes} onChange={(event) => updateRow(index, { notes: event.target.value })} placeholder="notes, one per line" rows={3} />
          </div>
        </article>
      ))}
      <div className="alert-box">{message}</div>
    </div>
  );
}
