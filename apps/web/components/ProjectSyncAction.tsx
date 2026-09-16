"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { syncProject } from "@/lib/api";
import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";
import { useI18n } from "@/lib/i18n";

type ActionStatus = "idle" | "working" | "done" | "error";

export function ProjectSyncAction({ projectId, label = "Resync project" }: { projectId: string; label?: string }) {
  const router = useRouter();
  const { t } = useI18n();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  async function triggerSync() {
    setStatus("working");
    setMessage(t("actions.running_sync"));
    try {
      const result = await syncProject(projectId, { trigger: "manual", force: true });
      setStatus("done");
      setMessage(`${result.project.name}: ${t("actions.sync_complete")}`);
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : t("actions.sync_failed"));
    }
  }

  return (
    <div className="action-rail">
      <ActionSummaryBadge tone={status === "working" ? "working" : status === "done" ? "done" : status === "error" ? "error" : "idle"} title={t(`actions.status_${status}`)} description={message || t("actions.ready_sync")} />
      <div className="action-caption">
        <span>API</span>
        <code>/api/projects/{projectId}/sync</code>
      </div>
      <button className="button button-primary" disabled={isPending || status === "working"} onClick={() => void triggerSync()}>
        {label === "Resync project" ? t("actions.resync_project") : label}
      </button>
    </div>
  );
}
