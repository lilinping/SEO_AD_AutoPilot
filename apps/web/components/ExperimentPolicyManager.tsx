"use client";

import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import type {
  WorkspaceExperiment,
  WorkspaceExperimentAssignmentReport,
  WorkspaceExperimentPolicyUpdateRequest,
  WorkspaceExperimentReport,
  WorkspaceExperimentVariant,
} from "@seo-ad-autopilot/contracts";
import { getWorkspaceExperimentAssignments, updateWorkspaceExperimentPolicy } from "@/lib/api";
import { StatusPill } from "@/components/StatusPill";

type EditableVariant = {
  variantName: string;
  allocationPercent: string;
  enabled: "true" | "false";
  notes: string;
};

type EditableExperiment = {
  experimentKey: string;
  enabled: "true" | "false";
  targetSurface: WorkspaceExperiment["targetSurface"];
  targetLocale: string;
  targetProjectIds: string;
  controlVariantName: string;
  assignmentStrategy: WorkspaceExperiment["assignmentStrategy"];
  primaryMetric: string;
  variants: EditableVariant[];
  notes: string;
};

function toEditableVariant(variant: WorkspaceExperimentVariant): EditableVariant {
  return {
    variantName: variant.variantName,
    allocationPercent: String(variant.allocationPercent),
    enabled: variant.enabled ? "true" : "false",
    notes: variant.notes.join("\n"),
  };
}

function toEditableExperiment(experiment: WorkspaceExperiment): EditableExperiment {
  return {
    experimentKey: experiment.experimentKey,
    enabled: experiment.enabled ? "true" : "false",
    targetSurface: experiment.targetSurface,
    targetLocale: experiment.targetLocale ?? "",
    targetProjectIds: experiment.targetProjectIds.join(", "),
    controlVariantName: experiment.controlVariantName,
    assignmentStrategy: experiment.assignmentStrategy,
    primaryMetric: experiment.primaryMetric,
    variants: experiment.variants.map(toEditableVariant),
    notes: experiment.notes.join("\n"),
  };
}

function toAllocation(raw: string): number {
  const value = Number(raw);
  if (Number.isNaN(value)) return 0;
  return Math.max(0, Math.trunc(value));
}

function parseLines(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

export function ExperimentPolicyManager({ report }: { report: WorkspaceExperimentReport }) {
  const router = useRouter();
  const [experimentsEnabled, setExperimentsEnabled] = useState(report.policy.experimentsEnabled ? "true" : "false");
  const [strictAssignment, setStrictAssignment] = useState(report.policy.strictAssignment ? "true" : "false");
  const [defaultAssignmentStrategy, setDefaultAssignmentStrategy] = useState(report.policy.defaultAssignmentStrategy);
  const [rows, setRows] = useState<EditableExperiment[]>(report.policy.experiments.map(toEditableExperiment));
  const [message, setMessage] = useState("Ready");
  const [previewProjectId, setPreviewProjectId] = useState(report.policy.experiments[0]?.targetProjectIds[0] ?? "");
  const [previewSubjectKey, setPreviewSubjectKey] = useState(report.policy.experiments[0]?.targetProjectIds[0] ?? "");
  const [previewLocale, setPreviewLocale] = useState(report.policy.experiments[0]?.targetLocale ?? "en-US");
  const [previewSurface, setPreviewSurface] = useState<WorkspaceExperiment["targetSurface"]>(report.policy.experiments[0]?.targetSurface ?? "site");
  const [assignmentPreview, setAssignmentPreview] = useState<WorkspaceExperimentAssignmentReport | null>(null);
  const [assignmentMessage, setAssignmentMessage] = useState("Preview the assignment for a subject key.");
  const [isPending, startTransition] = useTransition();

  const statusTone = useMemo(() => (report.workspaceReady ? "good" : "warn"), [report.workspaceReady]);

  function updateExperiment(index: number, patch: Partial<EditableExperiment>) {
    setRows((current) => current.map((item, idx) => (idx === index ? { ...item, ...patch } : item)));
  }

  function updateVariant(experimentIndex: number, variantIndex: number, patch: Partial<EditableVariant>) {
    setRows((current) =>
      current.map((experiment, idx) =>
        idx === experimentIndex
          ? {
              ...experiment,
              variants: experiment.variants.map((variant, vIdx) => (vIdx === variantIndex ? { ...variant, ...patch } : variant)),
            }
          : experiment,
      ),
    );
  }

  function addExperiment() {
    setRows((current) => [
      ...current,
      {
        experimentKey: `experiment-${current.length + 1}`,
        enabled: "true",
        targetSurface: "site",
        targetLocale: "en-US",
        targetProjectIds: "",
        controlVariantName: "control",
        assignmentStrategy: defaultAssignmentStrategy,
        primaryMetric: "conversion_rate",
        variants: [
          { variantName: "control", allocationPercent: "50", enabled: "true", notes: "" },
          { variantName: "treatment", allocationPercent: "50", enabled: "true", notes: "" },
        ],
        notes: "",
      },
    ]);
  }

  function addVariant(experimentIndex: number) {
    setRows((current) =>
      current.map((experiment, idx) =>
        idx === experimentIndex
          ? {
              ...experiment,
              variants: [
                ...experiment.variants,
                {
                  variantName: `variant-${experiment.variants.length + 1}`,
                  allocationPercent: "0",
                  enabled: "true",
                  notes: "",
                },
              ],
            }
          : experiment,
      ),
    );
  }

  function removeExperiment(index: number) {
    setRows((current) => current.filter((_, idx) => idx !== index));
  }

  function removeVariant(experimentIndex: number, variantIndex: number) {
    setRows((current) =>
      current.map((experiment, idx) =>
        idx === experimentIndex
          ? {
              ...experiment,
              variants: experiment.variants.filter((_, vIdx) => vIdx !== variantIndex),
            }
          : experiment,
      ),
    );
  }

  async function save() {
    setMessage("Saving experiment policy...");
    try {
      const payload: WorkspaceExperimentPolicyUpdateRequest = {
        experimentsEnabled: experimentsEnabled === "true",
        strictAssignment: strictAssignment === "true",
        defaultAssignmentStrategy,
        experiments: rows.map((row, index) => ({
          experimentKey: row.experimentKey.trim() || `experiment-${index + 1}`,
          enabled: row.enabled === "true",
          targetSurface: row.targetSurface,
          targetLocale: row.targetLocale.trim() || null,
          targetProjectIds: row.targetProjectIds
            .split(",")
            .map((item) => item.trim())
            .filter((item) => item.length > 0),
          controlVariantName: row.controlVariantName.trim() || "control",
          assignmentStrategy: row.assignmentStrategy,
          primaryMetric: row.primaryMetric.trim() || "conversion_rate",
          variants: row.variants
            .map((variant) => ({
              variantName: variant.variantName.trim() || "control",
              allocationPercent: toAllocation(variant.allocationPercent),
              enabled: variant.enabled === "true",
              notes: parseLines(variant.notes),
            }))
            .filter((variant) => variant.variantName.length > 0),
          notes: parseLines(row.notes),
        })),
      };
      const result = await updateWorkspaceExperimentPolicy(payload);
      setExperimentsEnabled(result.policy.experimentsEnabled ? "true" : "false");
      setStrictAssignment(result.policy.strictAssignment ? "true" : "false");
      setDefaultAssignmentStrategy(result.policy.defaultAssignmentStrategy);
      setRows(result.policy.experiments.map(toEditableExperiment));
      setMessage(`Saved ${result.readyExperimentCount}/${result.experimentCount} ready experiments.`);
      startTransition(() => router.refresh());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save experiment policy.");
    }
  }

  async function previewAssignment() {
    setAssignmentMessage("Resolving runtime assignment...");
    try {
      const result = await getWorkspaceExperimentAssignments({
        projectId: previewProjectId.trim() || null,
        subjectKey: previewSubjectKey.trim() || null,
        sessionKey: null,
        targetSurface: previewSurface,
        targetLocale: previewLocale.trim() || null,
        experimentKey: null,
      });
      setAssignmentPreview(result);
      setAssignmentMessage(
        result.assignedExperimentCount > 0
          ? `Resolved ${result.assignedExperimentCount}/${result.experimentCount} experiments.`
          : `Resolved ${result.matchedExperimentCount}/${result.experimentCount} experiments without an assignment.`,
      );
    } catch (error) {
      setAssignmentMessage(error instanceof Error ? error.message : "Failed to resolve assignment preview.");
    }
  }

  return (
    <div className="stack" style={{ marginTop: 12 }}>
      <div className="stat-grid">
        <section className="stat-card stat-card-accent">
          <div className="stat-card-label">Workspace ready</div>
          <div className="stat-card-value">{report.workspaceReady ? "ready" : "partial"}</div>
          <div className="stat-card-caption">{report.readyExperimentCount}/{report.experimentCount} experiments are rollout-ready</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Enabled</div>
          <div className="stat-card-value">{report.policy.experimentsEnabled ? "on" : "off"}</div>
          <div className="stat-card-caption">Strict assignment {report.policy.strictAssignment ? "enabled" : "disabled"}</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Variants</div>
          <div className="stat-card-value">{report.variantCount}</div>
          <div className="stat-card-caption">{report.balancedExperimentCount} experiments have balanced allocations</div>
        </section>
      </div>
      <div className="project-foot">
        <span>Experiment editor</span>
        <StatusPill tone={statusTone}>{report.workspaceReady ? "rollout-ready" : "needs setup"}</StatusPill>
      </div>
      <div className="stack" style={{ marginTop: 12 }}>
        <select value={experimentsEnabled} onChange={(event) => setExperimentsEnabled(event.target.value as "true" | "false")}>
          <option value="true">experiments enabled</option>
          <option value="false">experiments disabled</option>
        </select>
        <select value={strictAssignment} onChange={(event) => setStrictAssignment(event.target.value as "true" | "false")}>
          <option value="true">strict assignment on</option>
          <option value="false">strict assignment off</option>
        </select>
        <select
          value={defaultAssignmentStrategy}
          onChange={(event) => setDefaultAssignmentStrategy(event.target.value as WorkspaceExperiment["assignmentStrategy"])}
        >
          <option value="hash">hash</option>
          <option value="sticky">sticky</option>
          <option value="round_robin">round robin</option>
        </select>
      </div>
      <div className="project-foot">
        <span>{report.warnings.length ? report.warnings.join(" · ") : "No experiment warnings."}</span>
        <button className="button button-secondary" type="button" onClick={addExperiment}>
          Add experiment
        </button>
        <button className="button button-primary" type="button" onClick={() => void save()} disabled={isPending}>
          Save experiment policy
        </button>
      </div>
      <div className="suite-card">
        <div className="project-foot">
          <span>Runtime assignment preview</span>
          <StatusPill tone={assignmentPreview?.assignedExperimentCount ? "good" : "warn"}>{assignmentPreview?.assignedExperimentCount ?? 0}</StatusPill>
        </div>
        <div className="grid-two" style={{ marginTop: 12 }}>
          <input value={previewProjectId} onChange={(event) => setPreviewProjectId(event.target.value)} placeholder="project id" />
          <input value={previewSubjectKey} onChange={(event) => setPreviewSubjectKey(event.target.value)} placeholder="subject key" />
          <input value={previewLocale} onChange={(event) => setPreviewLocale(event.target.value)} placeholder="locale" />
          <select value={previewSurface} onChange={(event) => setPreviewSurface(event.target.value as WorkspaceExperiment["targetSurface"])}>
            <option value="site">site</option>
            <option value="seo">seo</option>
            <option value="content">content</option>
            <option value="ad">ad</option>
            <option value="ui">ui</option>
          </select>
        </div>
        <div className="project-foot" style={{ marginTop: 12 }}>
          <span>{assignmentMessage}</span>
          <button className="button button-primary" type="button" onClick={() => void previewAssignment()} disabled={isPending}>
            Preview assignment
          </button>
        </div>
        {assignmentPreview ? (
          <div className="stack" style={{ marginTop: 12 }}>
            <div className="project-copy">
              Subject <strong>{assignmentPreview.subjectKey}</strong> on <strong>{assignmentPreview.targetSurface}</strong>
              {assignmentPreview.targetLocale ? ` · ${assignmentPreview.targetLocale}` : ""}
            </div>
            <div className="metric-list">
              {assignmentPreview.assignments.slice(0, 4).map((assignment) => (
                <div key={assignment.experimentKey} className="suite-card">
                  <div className="suite-title">
                    <strong>{assignment.experimentKey}</strong>
                    <StatusPill tone={assignment.eligible ? "good" : "warn"}>{assignment.eligible ? "eligible" : "blocked"}</StatusPill>
                  </div>
                  <div className="project-copy">
                    {assignment.assignedVariantName ? (
                      <>
                        Variant <strong>{assignment.assignedVariantName}</strong> · roll {assignment.bucketRoll}/{assignment.bucketSize}
                      </>
                    ) : (
                      <>No variant assigned · {assignment.warnings[0] ?? "preview only"}</>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div className="project-copy">
              {assignmentPreview.warnings.length ? assignmentPreview.warnings.join(" · ") : "No runtime assignment warnings."}
            </div>
          </div>
        ) : null}
      </div>
      <div className="grid-two">
        <div className="suite-card">
          <div className="project-foot">
            <span>Readiness summary</span>
            <StatusPill tone={report.workspaceReady ? "good" : "warn"}>{report.readyExperimentCount}</StatusPill>
          </div>
          <ul className="metric-list">
            {report.experiments.slice(0, 5).map((experiment) => (
              <li key={experiment.experimentKey}>
                {experiment.experimentKey}: {experiment.experimentReady ? "ready" : "pending"} · {experiment.targetSurface} · {experiment.variantCount} variants
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
          <div className="project-copy">The experiment policy is persisted locally so controlled rollouts can be audited without a third-party experimentation service.</div>
        </div>
      </div>
      {rows.map((experiment, experimentIndex) => (
        <article className="audit-card" key={`${experiment.experimentKey}-${experimentIndex}`}>
          <div className="project-foot">
            <span>{experiment.experimentKey}</span>
            <button className="button button-secondary" type="button" onClick={() => removeExperiment(experimentIndex)}>
              Delete
            </button>
          </div>
          <div className="stack" style={{ marginTop: 12 }}>
            <input value={experiment.experimentKey} onChange={(event) => updateExperiment(experimentIndex, { experimentKey: event.target.value })} placeholder="experiment key" />
            <select value={experiment.enabled} onChange={(event) => updateExperiment(experimentIndex, { enabled: event.target.value as EditableExperiment["enabled"] })}>
              <option value="true">enabled</option>
              <option value="false">disabled</option>
            </select>
            <select
              value={experiment.targetSurface}
              onChange={(event) => updateExperiment(experimentIndex, { targetSurface: event.target.value as EditableExperiment["targetSurface"] })}
            >
              <option value="site">site</option>
              <option value="seo">seo</option>
              <option value="content">content</option>
              <option value="ad">ad</option>
              <option value="ui">ui</option>
            </select>
            <input value={experiment.targetLocale} onChange={(event) => updateExperiment(experimentIndex, { targetLocale: event.target.value })} placeholder="target locale" />
            <input
              value={experiment.targetProjectIds}
              onChange={(event) => updateExperiment(experimentIndex, { targetProjectIds: event.target.value })}
              placeholder="project ids, comma separated"
            />
            <input
              value={experiment.controlVariantName}
              onChange={(event) => updateExperiment(experimentIndex, { controlVariantName: event.target.value })}
              placeholder="control variant name"
            />
            <select
              value={experiment.assignmentStrategy}
              onChange={(event) => updateExperiment(experimentIndex, { assignmentStrategy: event.target.value as EditableExperiment["assignmentStrategy"] })}
            >
              <option value="hash">hash</option>
              <option value="sticky">sticky</option>
              <option value="round_robin">round robin</option>
            </select>
            <input value={experiment.primaryMetric} onChange={(event) => updateExperiment(experimentIndex, { primaryMetric: event.target.value })} placeholder="primary metric" />
            <textarea value={experiment.notes} onChange={(event) => updateExperiment(experimentIndex, { notes: event.target.value })} placeholder="notes, one per line" rows={3} />
          </div>
          <div className="project-foot" style={{ marginTop: 12 }}>
            <span>Variants</span>
            <button className="button button-secondary" type="button" onClick={() => addVariant(experimentIndex)}>
              Add variant
            </button>
          </div>
          <div className="stack" style={{ marginTop: 12 }}>
            {experiment.variants.map((variant, variantIndex) => (
              <div className="suite-card" key={`${experiment.experimentKey}-${variantIndex}`}>
                <div className="project-foot">
                  <span>{variant.variantName || `variant-${variantIndex + 1}`}</span>
                  <button className="button button-secondary" type="button" onClick={() => removeVariant(experimentIndex, variantIndex)}>
                    Remove
                  </button>
                </div>
                <div className="stack" style={{ marginTop: 12 }}>
                  <input value={variant.variantName} onChange={(event) => updateVariant(experimentIndex, variantIndex, { variantName: event.target.value })} placeholder="variant name" />
                  <input
                    value={variant.allocationPercent}
                    onChange={(event) => updateVariant(experimentIndex, variantIndex, { allocationPercent: event.target.value })}
                    placeholder="allocation percent"
                  />
                  <select
                    value={variant.enabled}
                    onChange={(event) => updateVariant(experimentIndex, variantIndex, { enabled: event.target.value as EditableVariant["enabled"] })}
                  >
                    <option value="true">enabled</option>
                    <option value="false">disabled</option>
                  </select>
                  <textarea value={variant.notes} onChange={(event) => updateVariant(experimentIndex, variantIndex, { notes: event.target.value })} placeholder="notes, one per line" rows={2} />
                </div>
              </div>
            ))}
          </div>
        </article>
      ))}
      <div className="alert-box">{message}</div>
    </div>
  );
}
