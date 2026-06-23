"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import type {
  WorkspaceLocalizationAssignmentReport,
  WorkspaceLocalizationPolicyUpdateRequest,
  WorkspaceLocalizationReport,
  WorkspaceSiteCluster,
} from "@seo-ad-autopilot/contracts";
import { getWorkspaceLocalizationAssignment, updateWorkspaceLocalizationPolicy } from "@/lib/api";
import { StatusPill } from "@/components/StatusPill";

type EditableCluster = {
  clusterKey: string;
  enabled: "true" | "false";
  canonicalProjectId: string;
  projectIds: string;
  supportedLocales: string;
  primaryLocale: string;
  localeStrategy: WorkspaceSiteCluster["localeStrategy"];
  notes: string;
};

function toEditable(cluster: WorkspaceSiteCluster): EditableCluster {
  return {
    clusterKey: cluster.clusterKey,
    enabled: cluster.enabled ? "true" : "false",
    canonicalProjectId: cluster.canonicalProjectId ?? "",
    projectIds: cluster.projectIds.join(", "),
    supportedLocales: cluster.supportedLocales.join(", "),
    primaryLocale: cluster.primaryLocale ?? "",
    localeStrategy: cluster.localeStrategy,
    notes: cluster.notes.join("\n"),
  };
}

function parseList(value: string): string[] {
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

export function LocalizationPolicyManager({ report }: { report: WorkspaceLocalizationReport }) {
  const router = useRouter();
  const [localizationEnabled, setLocalizationEnabled] = useState(report.policy.localizationEnabled ? "true" : "false");
  const [strictLocalization, setStrictLocalization] = useState(report.policy.strictLocalization ? "true" : "false");
  const [defaultLocale, setDefaultLocale] = useState(report.policy.defaultLocale);
  const [defaultLanguage, setDefaultLanguage] = useState(report.policy.defaultLanguage);
  const [rows, setRows] = useState<EditableCluster[]>(report.policy.clusters.map(toEditable));
  const [message, setMessage] = useState("Ready");
  const [previewProjectId, setPreviewProjectId] = useState(report.policy.clusters[0]?.canonicalProjectId ?? "");
  const [previewLocale, setPreviewLocale] = useState(report.policy.defaultLocale);
  const [previewHost, setPreviewHost] = useState("");
  const [previewSubjectKey, setPreviewSubjectKey] = useState(report.policy.clusters[0]?.canonicalProjectId ?? "");
  const [assignmentPreview, setAssignmentPreview] = useState<WorkspaceLocalizationAssignmentReport | null>(null);
  const [assignmentMessage, setAssignmentMessage] = useState("Preview the cluster routing for a subject.");
  const [isPending, startTransition] = useTransition();

  function updateRow(index: number, patch: Partial<EditableCluster>) {
    setRows((current) => current.map((item, idx) => (idx === index ? { ...item, ...patch } : item)));
  }

  function addRow() {
    setRows((current) => [
      ...current,
      {
        clusterKey: `cluster-${current.length + 1}`,
        enabled: "true",
        canonicalProjectId: "",
        projectIds: "",
        supportedLocales: "en-US, fr-FR",
        primaryLocale: "en-US",
        localeStrategy: "path",
        notes: "",
      },
    ]);
  }

  function removeRow(index: number) {
    setRows((current) => current.filter((_, idx) => idx !== index));
  }

  async function save() {
    setMessage("Saving localization policy...");
    try {
      const payload: WorkspaceLocalizationPolicyUpdateRequest = {
        localizationEnabled: localizationEnabled === "true",
        strictLocalization: strictLocalization === "true",
        defaultLocale: defaultLocale.trim() || "en-US",
        defaultLanguage: defaultLanguage.trim() || "en",
        clusters: rows.map((row, index) => ({
          clusterKey: row.clusterKey.trim() || `cluster-${index + 1}`,
          enabled: row.enabled === "true",
          canonicalProjectId: row.canonicalProjectId.trim() || null,
          projectIds: parseList(row.projectIds),
          supportedLocales: parseList(row.supportedLocales),
          primaryLocale: row.primaryLocale.trim() || null,
          localeStrategy: row.localeStrategy,
          notes: parseLines(row.notes),
        })),
      };
      const result = await updateWorkspaceLocalizationPolicy(payload);
      setLocalizationEnabled(result.policy.localizationEnabled ? "true" : "false");
      setStrictLocalization(result.policy.strictLocalization ? "true" : "false");
      setDefaultLocale(result.policy.defaultLocale);
      setDefaultLanguage(result.policy.defaultLanguage);
      setRows(result.policy.clusters.map(toEditable));
      setMessage(`Saved ${result.readyClusterCount}/${result.clusterCount} ready clusters.`);
      startTransition(() => router.refresh());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save localization policy.");
    }
  }

  async function previewAssignment() {
    setAssignmentMessage("Resolving localization assignment...");
    try {
      const result = await getWorkspaceLocalizationAssignment({
        projectId: previewProjectId.trim() || null,
        targetLocale: previewLocale.trim() || null,
        host: previewHost.trim() || null,
        subjectKey: previewSubjectKey.trim() || null,
      });
      setAssignmentPreview(result);
      setAssignmentMessage(
        result.assignedClusterCount > 0
          ? `Resolved ${result.assignedClusterCount}/${result.clusterCount} clusters.`
          : `Resolved ${result.matchedClusterCount}/${result.clusterCount} clusters without a route.`,
      );
    } catch (error) {
      setAssignmentMessage(error instanceof Error ? error.message : "Failed to resolve localization assignment.");
    }
  }

  return (
    <div className="stack" style={{ marginTop: 12 }}>
      <div className="stat-grid">
        <section className="stat-card stat-card-accent">
          <div className="stat-card-label">Workspace ready</div>
          <div className="stat-card-value">{report.workspaceReady ? "ready" : "partial"}</div>
          <div className="stat-card-caption">{report.readyClusterCount}/{report.clusterCount} clusters are rollout-ready</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Enabled</div>
          <div className="stat-card-value">{report.policy.localizationEnabled ? "on" : "off"}</div>
          <div className="stat-card-caption">Strict localization {report.policy.strictLocalization ? "enabled" : "disabled"}</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Locales</div>
          <div className="stat-card-value">{report.localeCount}</div>
          <div className="stat-card-caption">{report.projectCount} projects are bound into localization clusters</div>
        </section>
      </div>
      <div className="project-foot">
        <span>Localization editor</span>
        <StatusPill tone={report.workspaceReady ? "good" : "warn"}>{report.workspaceReady ? "rollout-ready" : "needs setup"}</StatusPill>
      </div>
      <div className="stack" style={{ marginTop: 12 }}>
        <select value={localizationEnabled} onChange={(event) => setLocalizationEnabled(event.target.value as "true" | "false")}>
          <option value="true">localization enabled</option>
          <option value="false">localization disabled</option>
        </select>
        <select value={strictLocalization} onChange={(event) => setStrictLocalization(event.target.value as "true" | "false")}>
          <option value="true">strict localization on</option>
          <option value="false">strict localization off</option>
        </select>
        <input value={defaultLocale} onChange={(event) => setDefaultLocale(event.target.value)} placeholder="default locale" />
        <input value={defaultLanguage} onChange={(event) => setDefaultLanguage(event.target.value)} placeholder="default language" />
      </div>
      <div className="project-foot">
        <span>{report.warnings.length ? report.warnings.join(" · ") : "No localization warnings."}</span>
        <button className="button button-secondary" type="button" onClick={addRow}>
          Add cluster
        </button>
        <button className="button button-primary" type="button" onClick={() => void save()} disabled={isPending}>
          Save localization policy
        </button>
      </div>
      <div className="suite-card">
        <div className="project-foot">
          <span>Runtime cluster preview</span>
          <StatusPill tone={assignmentPreview?.assignedClusterCount ? "good" : "warn"}>{assignmentPreview?.assignedClusterCount ?? 0}</StatusPill>
        </div>
        <div className="grid-two" style={{ marginTop: 12 }}>
          <input value={previewProjectId} onChange={(event) => setPreviewProjectId(event.target.value)} placeholder="project id" />
          <input value={previewSubjectKey} onChange={(event) => setPreviewSubjectKey(event.target.value)} placeholder="subject key" />
          <input value={previewLocale} onChange={(event) => setPreviewLocale(event.target.value)} placeholder="target locale" />
          <input value={previewHost} onChange={(event) => setPreviewHost(event.target.value)} placeholder="host" />
        </div>
        <div className="project-foot" style={{ marginTop: 12 }}>
          <span>{assignmentMessage}</span>
          <button className="button button-primary" type="button" onClick={() => void previewAssignment()} disabled={isPending}>
            Preview cluster route
          </button>
        </div>
        {assignmentPreview ? (
          <div className="stack" style={{ marginTop: 12 }}>
            <div className="project-copy">
              Subject <strong>{assignmentPreview.subjectKey}</strong>
              {assignmentPreview.targetLocale ? <> · locale <strong>{assignmentPreview.targetLocale}</strong></> : null}
              {assignmentPreview.host ? <> · host <strong>{assignmentPreview.host}</strong></> : null}
            </div>
            <div className="metric-list">
              {assignmentPreview.assignments.slice(0, 4).map((assignment) => (
                <div className="suite-card" key={assignment.clusterKey}>
                  <div className="suite-title">
                    <strong>{assignment.clusterKey}</strong>
                    <StatusPill tone={assignment.clusterReady ? "good" : "warn"}>{assignment.clusterReady ? "ready" : "pending"}</StatusPill>
                  </div>
                  <div className="project-copy">
                    {assignment.matchedByProject || assignment.matchedByLocale || assignment.matchedByHost ? (
                      <>
                        Route <strong>{assignment.routePrefix}</strong> via {assignment.localeStrategy}
                      </>
                    ) : (
                      <>No route match · {assignment.warnings[0] ?? "preview only"}</>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div className="project-copy">
              {assignmentPreview.warnings.length ? assignmentPreview.warnings.join(" · ") : "No localization warnings."}
            </div>
          </div>
        ) : null}
      </div>
      <div className="grid-two">
        <div className="suite-card">
          <div className="project-foot">
            <span>Readiness summary</span>
            <StatusPill tone={report.workspaceReady ? "good" : "warn"}>{report.readyClusterCount}</StatusPill>
          </div>
          <ul className="metric-list">
            {report.clusters.slice(0, 5).map((cluster) => (
              <li key={cluster.clusterKey}>
                {cluster.clusterKey}: {cluster.clusterReady ? "ready" : "pending"} · {cluster.projectCount} projects · {cluster.localeCount} locales
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
          <div className="project-copy">The localization policy is persisted locally so multi-site and multi-language readiness can be audited without an external CMS plugin.</div>
        </div>
      </div>
      {rows.map((row, index) => (
        <article className="audit-card" key={`${row.clusterKey}-${index}`}>
          <div className="project-foot">
            <span>{row.clusterKey}</span>
            <button className="button button-secondary" type="button" onClick={() => removeRow(index)}>
              Delete
            </button>
          </div>
          <div className="stack" style={{ marginTop: 12 }}>
            <input value={row.clusterKey} onChange={(event) => updateRow(index, { clusterKey: event.target.value })} placeholder="cluster key" />
            <select value={row.enabled} onChange={(event) => updateRow(index, { enabled: event.target.value as EditableCluster["enabled"] })}>
              <option value="true">enabled</option>
              <option value="false">disabled</option>
            </select>
            <input value={row.canonicalProjectId} onChange={(event) => updateRow(index, { canonicalProjectId: event.target.value })} placeholder="canonical project id" />
            <input value={row.projectIds} onChange={(event) => updateRow(index, { projectIds: event.target.value })} placeholder="project ids, comma separated" />
            <input value={row.supportedLocales} onChange={(event) => updateRow(index, { supportedLocales: event.target.value })} placeholder="supported locales, comma separated" />
            <input value={row.primaryLocale} onChange={(event) => updateRow(index, { primaryLocale: event.target.value })} placeholder="primary locale" />
            <select
              value={row.localeStrategy}
              onChange={(event) => updateRow(index, { localeStrategy: event.target.value as EditableCluster["localeStrategy"] })}
            >
              <option value="path">path</option>
              <option value="subdomain">subdomain</option>
              <option value="cctld">cctld</option>
            </select>
            <textarea value={row.notes} onChange={(event) => updateRow(index, { notes: event.target.value })} placeholder="notes, one per line" rows={3} />
          </div>
        </article>
      ))}
      <div className="alert-box">{message}</div>
    </div>
  );
}
