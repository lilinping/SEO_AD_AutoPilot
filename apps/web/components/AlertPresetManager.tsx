"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import type { AlertPreset } from "@seo-ad-autopilot/contracts";
import { updateAlertPresetCollection } from "@/lib/api";

type EditablePreset = {
  presetId: string;
  name: string;
  description: string;
  projectIds: string;
  categories: string;
  severities: string;
  providers: string;
  blocking: "any" | "true" | "false";
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

function toEditable(preset: AlertPreset): EditablePreset {
  return {
    presetId: preset.presetId,
    name: preset.name,
    description: preset.description ?? "",
    projectIds: toCsv(preset.projectIds),
    categories: toCsv(preset.categories),
    severities: toCsv(preset.severities),
    providers: toCsv(preset.providers),
    blocking: preset.blocking === true ? "true" : preset.blocking === false ? "false" : "any",
  };
}

export function AlertPresetManager({ presets }: { presets: AlertPreset[] }) {
  const router = useRouter();
  const [rows, setRows] = useState<EditablePreset[]>(presets.map(toEditable));
  const [message, setMessage] = useState("Ready");
  const [isPending, startTransition] = useTransition();

  function updateRow(index: number, patch: Partial<EditablePreset>) {
    setRows((current) => current.map((item, idx) => (idx === index ? { ...item, ...patch } : item)));
  }

  function addRow() {
    setRows((current) => [
      ...current,
      {
        presetId: `custom_${Date.now()}`,
        name: "new_preset",
        description: "",
        projectIds: "",
        categories: "",
        severities: "",
        providers: "",
        blocking: "any",
      },
    ]);
  }

  function removeRow(index: number) {
    setRows((current) => current.filter((_, idx) => idx !== index));
  }

  async function save() {
    setMessage("Saving presets...");
    try {
      const payload = {
        presets: rows
          .map((row) => ({
            presetId: row.presetId.trim(),
            name: row.name.trim(),
            description: row.description.trim(),
            projectIds: parseCsv(row.projectIds),
            categories: parseCsv(row.categories),
            severities: parseCsv(row.severities),
            providers: parseCsv(row.providers),
            blocking: row.blocking === "any" ? null : row.blocking === "true",
            updatedAt: new Date().toISOString(),
          }))
          .filter((row) => row.presetId.length > 0 && row.name.length > 0),
      };
      const result = await updateAlertPresetCollection(payload);
      setRows(result.presets.map(toEditable));
      setMessage(`Saved ${result.presets.length} presets.`);
      startTransition(() => router.refresh());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save presets.");
    }
  }

  return (
    <div className="stack" style={{ marginTop: 12 }}>
      <div className="project-foot">
        <span>Manage presets</span>
        <div style={{ display: "flex", gap: 12 }}>
          <button className="button button-secondary" type="button" onClick={addRow}>
            Add preset
          </button>
          <button className="button button-primary" type="button" onClick={() => void save()} disabled={isPending}>
            Save presets
          </button>
        </div>
      </div>
      {rows.map((row, index) => (
        <article className="audit-card" key={`${row.presetId}-${index}`}>
          <div className="project-foot">
            <span>{row.name || row.presetId}</span>
            <button className="button button-secondary" type="button" onClick={() => removeRow(index)}>
              Delete
            </button>
          </div>
          <div className="stack" style={{ marginTop: 12 }}>
            <input value={row.presetId} onChange={(event) => updateRow(index, { presetId: event.target.value })} placeholder="preset id" />
            <input value={row.name} onChange={(event) => updateRow(index, { name: event.target.value })} placeholder="name" />
            <input value={row.description} onChange={(event) => updateRow(index, { description: event.target.value })} placeholder="description" />
            <input value={row.projectIds} onChange={(event) => updateRow(index, { projectIds: event.target.value })} placeholder="project ids (csv)" />
            <input value={row.categories} onChange={(event) => updateRow(index, { categories: event.target.value })} placeholder="categories (csv)" />
            <input value={row.severities} onChange={(event) => updateRow(index, { severities: event.target.value })} placeholder="severities (csv)" />
            <input value={row.providers} onChange={(event) => updateRow(index, { providers: event.target.value })} placeholder="providers (csv)" />
            <select value={row.blocking} onChange={(event) => updateRow(index, { blocking: event.target.value as EditablePreset["blocking"] })}>
              <option value="any">blocking:any</option>
              <option value="true">blocking:true</option>
              <option value="false">blocking:false</option>
            </select>
          </div>
        </article>
      ))}
      <div className="alert-box">{message}</div>
    </div>
  );
}
