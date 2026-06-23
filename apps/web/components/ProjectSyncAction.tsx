"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { syncProject } from "@/lib/api";
import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";

type ActionStatus = "idle" | "working" | "done" | "error";

export function ProjectSyncAction({ projectId, label = "Resync project" }: { projectId: string; label?: string }) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Ready to sync");
  const [isPending, startTransition] = useTransition();

  async function triggerSync() {
    setStatus("working");
    setMessage("Running project sync...");
    try {
      const result = await syncProject(projectId, { trigger: "manual", force: true });
      setStatus("done");
      setMessage(`Synced ${result.project.name} and refreshed its run history.`);
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Sync failed.");
    }
  }

  return (
    <div className="action-rail">
      <ActionSummaryBadge tone={status === "working" ? "working" : status === "done" ? "done" : status === "error" ? "error" : "idle"} title={status} description={message} />
      <div className="action-caption">
        <span>API</span>
        <code>/api/projects/{projectId}/sync</code>
      </div>
      <button className="button button-primary" disabled={isPending || status === "working"} onClick={() => void triggerSync()}>
        {label}
      </button>
    </div>
  );
}
