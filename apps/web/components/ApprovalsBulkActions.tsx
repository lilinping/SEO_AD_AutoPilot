"use client";

import { useMemo, useState } from "react";

import Link from "next/link";

import type { ApprovalRequest, ProjectSummary, TaskSummary } from "@seo-ad-autopilot/contracts";

import { BulkApproveAction } from "@/components/BulkApproveAction";
import { TaskActions } from "@/components/TaskActions";
import { useI18n } from "@/lib/i18n";

export function ApprovalsBulkActions({
  approvals,
  projects,
  tasks,
}: {
  approvals: ApprovalRequest[];
  projects: ProjectSummary[];
  tasks: TaskSummary[];
}) {
  const { t } = useI18n();
  const [selectedTaskIds, setSelectedTaskIds] = useState<string[]>([]);

  const allSelected = useMemo(
    () => approvals.length > 0 && selectedTaskIds.length === approvals.length,
    [approvals.length, selectedTaskIds.length],
  );

  function toggleSelected(taskId: string) {
    setSelectedTaskIds((current) => (current.includes(taskId) ? current.filter((item) => item !== taskId) : [...current, taskId]));
  }

  function toggleAll() {
    setSelectedTaskIds((current) => (current.length === approvals.length ? [] : approvals.map((approval) => approval.taskId)));
  }

  return (
    <div className="stack">
      <div className="project-card">
        <div className="project-title">
          <div>
            <div className="eyebrow">{t("approvals.selection")}</div>
            <h3>{t("approvals.batch_title")}</h3>
          </div>
          <button className="button button-secondary" type="button" onClick={toggleAll}>
            {allSelected ? t("approvals.clear_selection") : t("approvals.select_all")}
          </button>
        </div>
        <div className="project-copy">
          {selectedTaskIds.length
            ? `${selectedTaskIds.length} ${t("approvals.selected_suffix")}`
            : t("approvals.selection_hint")}
        </div>
        <div className="stack" style={{ marginTop: 16 }}>
          <BulkApproveAction taskIds={selectedTaskIds} label={t("approvals.approve_selected")} />
        </div>
      </div>

      <div className="stack">
        {approvals.map((approval) => {
          const selected = selectedTaskIds.includes(approval.taskId);
          const task = tasks.find((item) => item.taskId === approval.taskId);
          const project = projects.find((item) => item.projectId === task?.projectId);
          return (
            <article className="project-card" key={approval.approvalId} data-selected={selected ? "true" : "false"}>
              <div className="project-title">
                <div>
                  <div className="eyebrow">{t("approvals.task")} {approval.taskId}</div>
                  <h3>{project?.name ?? approval.status}</h3>
                </div>
                <label className="selection-cell">
                  <input type="checkbox" checked={selected} onChange={() => toggleSelected(approval.taskId)} />
                  <span>{t("approvals.select")}</span>
                </label>
              </div>
              <div className="project-copy">{approval.decisionHint}</div>
              <div className="metric-row">
                <span>{t("approvals.risk")}</span>
                <strong>{task?.riskScore ?? approval.riskSummary}</strong>
              </div>
              <div className="project-foot">
                <span>{approval.requiredApprovers.join(", ")}</span>
                {project ? <Link href={`/projects/${project.projectId}`}>{t("approvals.view_evidence")}</Link> : <span>{approval.riskSummary}</span>}
              </div>
              {task ? (
                <TaskActions
                  taskId={task.taskId}
                  approvalStatus={task.approvalStatus}
                  taskStatus={task.status}
                  deploymentMode={project?.deploymentMode}
                  riskScore={task.riskScore}
                />
              ) : null}
            </article>
          );
        })}
      </div>
    </div>
  );
}
