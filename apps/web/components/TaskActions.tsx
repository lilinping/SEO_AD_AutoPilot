"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { ApprovalStatus, DeploymentMode } from "@seo-ad-autopilot/contracts";

import { approveTask, deployTask, rollbackTask, API_BASE } from "@/lib/api";
import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";
import { useI18n } from "@/lib/i18n";

type ActionStatus = "idle" | "working" | "error" | "done";

export function TaskActions({
  taskId,
  approvalStatus,
  taskStatus,
  deploymentMode,
  riskScore,
}: {
  taskId: string;
  approvalStatus: ApprovalStatus;
  taskStatus: string;
  deploymentMode?: DeploymentMode | null;
  riskScore: number;
}) {
  const router = useRouter();
  const { t } = useI18n();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState<string>("");
  const [isPending, startTransition] = useTransition();
  const [isWorking, setIsWorking] = useState(false);

  const runAction = async (label: string, action: () => Promise<unknown>) => {
    setStatus("working");
    setMessage(label);
    setIsWorking(true);
    try {
      await action();
      setStatus("done");
      setMessage(`${label} ${t("actions.complete")}`);
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : t("actions.action_failed"));
    } finally {
      setIsWorking(false);
    }
  };

  const approveLabel = approvalStatus === "pending" ? t("actions.approve") : approvalStatus === "approved" ? t("actions.approved") : t("actions.rejected");

  return (
    <div className="action-rail">
      <ActionSummaryBadge tone={status === "working" ? "working" : status === "done" ? "done" : status === "error" ? "error" : "idle"} title={t(`actions.status_${status}`)} description={message || `${t("project_detail.risk")} ${riskScore}`} />
      <div className="action-caption">
        <span>API</span>
        <code>{API_BASE}</code>
        {deploymentMode ? <span>{deploymentMode}</span> : null}
      </div>
      <div className="action-buttons">
        {approvalStatus === "pending" ? (
          <>
            <button
              className="button button-primary"
              disabled={isPending || isWorking}
              onClick={() => void runAction(t("actions.approval"), () => approveTask(taskId, { decision: "approved", actor: "ui", note: "Approved from console" }))}
            >
              {approveLabel}
            </button>
            <button
              className="button button-secondary"
              disabled={isPending || isWorking}
              onClick={() => void runAction(t("actions.reject"), () => approveTask(taskId, { decision: "rejected", actor: "ui", note: "Rejected from console" }))}
            >
              {t("actions.reject")}
            </button>
          </>
        ) : null}
        {(taskStatus === "approved" || approvalStatus === "approved") ? (
          <button
            className="button button-primary"
            disabled={isPending || isWorking}
            onClick={() => void runAction(t("actions.deployment"), () => deployTask(taskId, { actor: "ui", note: "Promote scheduled release" }))}
          >
            {t("actions.promote_release")}
          </button>
        ) : null}
        {(taskStatus === "deployed" || taskStatus === "monitoring" || taskStatus === "rolled_back") ? (
          <button
            className="button button-secondary"
            disabled={isPending || isWorking}
            onClick={() => void runAction(t("actions.rollback"), () => rollbackTask(taskId, { actor: "ui", reason: "Console rollback" }))}
          >
            {t("actions.rollback")}
          </button>
        ) : null}
      </div>
    </div>
  );
}
