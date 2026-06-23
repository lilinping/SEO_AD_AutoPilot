"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { bulkSyncProjects } from "@/lib/api";
import { ExecutionSummary } from "@/components/ExecutionSummary";

type ActionStatus = "idle" | "working" | "done" | "error";

export function BulkSyncAction({
  projectIds,
  label = "Sync all projects",
}: {
  projectIds: string[];
  label?: string;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Ready to sync");
  const [isPending, startTransition] = useTransition();

  async function triggerBulkSync() {
    if (projectIds.length === 0) {
      setStatus("error");
      setMessage("No projects available to sync.");
      return;
    }
    setStatus("working");
    setMessage("Syncing project queue...");
    try {
      const result = await bulkSyncProjects({ projectIds, trigger: "manual", force: true });
      const skipped = result.skippedProjectIds.length ? `, skipped ${result.skippedProjectIds.length}` : "";
      setStatus("done");
      setMessage(`Synced ${result.processedCount} project${result.processedCount === 1 ? "" : "s"}${skipped}.`);
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Bulk sync failed.");
    }
  }

  return (
    <ExecutionSummary
      apiPath="/api/bulk/projects/sync"
      targetCount={projectIds.length}
      targetLabel="projects"
      buttonLabel={label}
      status={status}
      message={message}
      tone="primary"
      disabled={isPending || status === "working" || projectIds.length === 0}
      onClick={() => void triggerBulkSync()}
    />
  );
}
