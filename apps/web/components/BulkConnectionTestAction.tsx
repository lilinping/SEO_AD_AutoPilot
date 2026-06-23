"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { bulkTestProjectConnections } from "@/lib/api";
import { ExecutionSummary } from "@/components/ExecutionSummary";

type ActionStatus = "idle" | "working" | "done" | "error";

export function BulkConnectionTestAction({
  projectIds,
  label = "Test all connections",
}: {
  projectIds: string[];
  label?: string;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Ready to test");
  const [isPending, startTransition] = useTransition();

  async function triggerBulkTest() {
    if (projectIds.length === 0) {
      setStatus("error");
      setMessage("No projects available to test.");
      return;
    }
    setStatus("working");
    setMessage("Testing project queue...");
    try {
      const result = await bulkTestProjectConnections({ projectIds });
      const skipped = result.skippedProjectIds.length ? `, skipped ${result.skippedProjectIds.length}` : "";
      setStatus("done");
      setMessage(`Tested ${result.testedCount} project${result.testedCount === 1 ? "" : "s"}${skipped}.`);
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Bulk connection test failed.");
    }
  }

  return (
    <ExecutionSummary
      apiPath="/api/bulk/projects/connections/test"
      targetCount={projectIds.length}
      targetLabel="projects"
      buttonLabel={label}
      status={status}
      message={message}
      tone="secondary"
      disabled={isPending || status === "working" || projectIds.length === 0}
      onClick={() => void triggerBulkTest()}
    />
  );
}
