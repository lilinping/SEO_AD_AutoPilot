"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { bulkApproveTasks } from "@/lib/api";
import { ExecutionSummary } from "@/components/ExecutionSummary";

type ActionStatus = "idle" | "working" | "done" | "error";

export function BulkApproveAction({
  taskIds,
  label = "Approve all pending",
}: {
  taskIds: string[];
  label?: string;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Ready to approve");
  const [isPending, startTransition] = useTransition();

  async function triggerBulkApprove() {
    if (taskIds.length === 0) {
      setStatus("error");
      setMessage("No pending tasks to approve.");
      return;
    }
    setStatus("working");
    setMessage("Approving pending tasks...");
    try {
      const result = await bulkApproveTasks({ taskIds, actor: "ui", note: "Bulk approved from console" });
      const skipped = result.skippedTaskIds.length ? `, skipped ${result.skippedTaskIds.length}` : "";
      setStatus("done");
      setMessage(`Approved ${result.approvedCount} task${result.approvedCount === 1 ? "" : "s"}${skipped}.`);
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Bulk approval failed.");
    }
  }

  return (
    <ExecutionSummary
      apiPath="/api/tasks/bulk/approve"
      targetCount={taskIds.length}
      targetLabel="queued tasks"
      buttonLabel={label}
      status={status}
      message={message}
      tone="primary"
      disabled={isPending || status === "working" || taskIds.length === 0}
      onClick={() => void triggerBulkApprove()}
    />
  );
}
