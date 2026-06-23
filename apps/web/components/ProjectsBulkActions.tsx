"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { formatDateTime } from "@/lib/format";

import { BulkConnectionTestAction } from "@/components/BulkConnectionTestAction";
import { BulkSyncAction } from "@/components/BulkSyncAction";
import type { ProjectSummary } from "@seo-ad-autopilot/contracts";

export function ProjectsBulkActions({
  projects,
  initialSelectedProjectIds = [],
}: {
  projects: ProjectSummary[];
  initialSelectedProjectIds?: string[];
}) {
  const [selectedProjectIds, setSelectedProjectIds] = useState<string[]>(
    initialSelectedProjectIds.filter((id) => projects.some((project) => project.projectId == id)),
  );

  const allSelected = useMemo(
    () => projects.length > 0 && selectedProjectIds.length === projects.length,
    [projects.length, selectedProjectIds.length],
  );

  function toggleSelected(projectId: string) {
    setSelectedProjectIds((current) =>
      current.includes(projectId) ? current.filter((item) => item !== projectId) : [...current, projectId],
    );
  }

  function toggleAll() {
    setSelectedProjectIds((current) => (current.length === projects.length ? [] : projects.map((project) => project.projectId)));
  }

  return (
    <div className="stack">
      <div className="project-card">
        <div className="project-title">
          <div>
            <div className="eyebrow">Selection</div>
            <h3>Batch operate on selected projects</h3>
          </div>
          <button className="button button-secondary" type="button" onClick={toggleAll}>
            {allSelected ? "Clear selection" : "Select all"}
          </button>
        </div>
        <div className="project-copy">
          {selectedProjectIds.length
            ? `${selectedProjectIds.length} project${selectedProjectIds.length === 1 ? "" : "s"} selected for bulk execution.`
            : "Pick a subset of projects to run sync or connector tests together."}
        </div>
        <div className="stack" style={{ marginTop: 16 }}>
          <BulkSyncAction projectIds={selectedProjectIds} label="Sync selected projects" />
          <BulkConnectionTestAction projectIds={selectedProjectIds} label="Test selected connections" />
        </div>
      </div>

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Select</th>
              <th>Project</th>
              <th>Class</th>
              <th>Stage</th>
              <th>Risk</th>
              <th>Updated</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {projects.map((project) => {
              const selected = selectedProjectIds.includes(project.projectId);
              return (
                <tr key={project.projectId} data-selected={selected ? "true" : "false"}>
                  <td>
                    <label className="selection-cell">
                      <input type="checkbox" checked={selected} onChange={() => toggleSelected(project.projectId)} />
                      <span>Target</span>
                    </label>
                  </td>
                  <td>{project.name}</td>
                  <td>{project.siteClass}</td>
                  <td>{project.latestStage}</td>
                  <td>{project.riskScore}</td>
                  <td>{formatDateTime(project.updatedAt)}</td>
                  <td>
                    <Link href={`/projects/${project.projectId}`}>Open</Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
