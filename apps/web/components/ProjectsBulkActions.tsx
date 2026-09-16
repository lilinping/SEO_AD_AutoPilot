"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { formatDateTime } from "@/lib/format";

import { BulkConnectionTestAction } from "@/components/BulkConnectionTestAction";
import { BulkSyncAction } from "@/components/BulkSyncAction";
import type { ProjectSummary } from "@seo-ad-autopilot/contracts";
import { useI18n } from "@/lib/i18n";

export function ProjectsBulkActions({
  projects,
  initialSelectedProjectIds = [],
}: {
  projects: ProjectSummary[];
  initialSelectedProjectIds?: string[];
}) {
  const { locale, t } = useI18n();
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
            <div className="eyebrow">{t("projects.selection")}</div>
            <h3>{t("projects.batch_title")}</h3>
          </div>
          <button className="button button-secondary" type="button" onClick={toggleAll}>
            {allSelected ? t("projects.clear_selection") : t("projects.select_all")}
          </button>
        </div>
        <div className="project-copy">
          {selectedProjectIds.length
            ? `${selectedProjectIds.length} ${t("projects.selected_suffix")}`
            : t("projects.selection_hint")}
        </div>
        <div className="stack" style={{ marginTop: 16 }}>
          <BulkSyncAction projectIds={selectedProjectIds} label={t("projects.sync_selected")} />
          <BulkConnectionTestAction projectIds={selectedProjectIds} label={t("projects.test_selected")} />
        </div>
      </div>

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>{t("projects.selection")}</th>
              <th>{t("projects.project")}</th>
              <th>{t("projects.class")}</th>
              <th>{t("projects.stage")}</th>
              <th>{t("projects.risk")}</th>
              <th>{t("projects.updated")}</th>
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
                      <span>{t("projects.target")}</span>
                    </label>
                  </td>
                  <td>{project.name}</td>
                  <td>{project.siteClass}</td>
                  <td>{t(`workflow_stages.${project.latestStage}`)}</td>
                  <td>{project.riskScore}</td>
                  <td>{formatDateTime(project.updatedAt, locale)}</td>
                  <td>
                    <Link href={`/projects/${project.projectId}`}>{t("projects.open")}</Link>
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
