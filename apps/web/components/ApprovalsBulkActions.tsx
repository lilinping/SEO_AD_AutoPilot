"use client";

import { useMemo, useState } from "react";

import type { ApprovalRequest } from "@seo-ad-autopilot/contracts";

import { BulkApproveAction } from "@/components/BulkApproveAction";

export function ApprovalsBulkActions({ approvals }: { approvals: ApprovalRequest[] }) {
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
            <div className="eyebrow">Selection</div>
            <h3>Batch approve selected tasks</h3>
          </div>
          <button className="button button-secondary" type="button" onClick={toggleAll}>
            {allSelected ? "Clear selection" : "Select all"}
          </button>
        </div>
        <div className="project-copy">
          {selectedTaskIds.length
            ? `${selectedTaskIds.length} task${selectedTaskIds.length === 1 ? "" : "s"} selected for release gating.`
            : "Pick a subset of approvals if you do not want to release the full queue."}
        </div>
        <div className="stack" style={{ marginTop: 16 }}>
          <BulkApproveAction taskIds={selectedTaskIds} label="Approve selected tasks" />
        </div>
      </div>

      <div className="stack">
        {approvals.map((approval) => {
          const selected = selectedTaskIds.includes(approval.taskId);
          return (
            <article className="project-card" key={approval.approvalId} data-selected={selected ? "true" : "false"}>
              <div className="project-title">
                <div>
                  <div className="eyebrow">Task {approval.taskId}</div>
                  <h3>{approval.status}</h3>
                </div>
                <label className="selection-cell">
                  <input type="checkbox" checked={selected} onChange={() => toggleSelected(approval.taskId)} />
                  <span>Select</span>
                </label>
              </div>
              <div className="project-copy">{approval.decisionHint}</div>
              <div className="project-foot">
                <span>{approval.requiredApprovers.join(", ")}</span>
                <span>{approval.riskSummary}</span>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
