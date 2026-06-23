"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { bulkRefreshBlockingConnectors } from "@/lib/api";
import { ExecutionSummary } from "@/components/ExecutionSummary";

type ActionStatus = "idle" | "working" | "done" | "error";

export function BulkBlockingRefreshAction({
  projectIds,
  maxProviders = 5,
}: {
  projectIds: string[];
  maxProviders?: number;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Ready to refresh blocking providers");
  const [isPending, startTransition] = useTransition();

  async function triggerBulkRefresh() {
    if (projectIds.length === 0) {
      setStatus("error");
      setMessage("No projects available.");
      return;
    }
    setStatus("working");
    setMessage("Refreshing blocking providers...");
    try {
      const result = await bulkRefreshBlockingConnectors({
        projectIds,
        providers: [],
        maxProviders,
      });
      setStatus("done");
      setMessage(
        `Providers ${result.providerCount}, refreshed ${result.refreshedCount}, skipped ${result.skippedProjectCount}.`,
      );
      startTransition(() => router.refresh());
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Blocking refresh failed.");
    }
  }

  return (
    <ExecutionSummary
      apiPath="/api/bulk/connectors/blocking/refresh"
      targetCount={projectIds.length}
      targetLabel="projects"
      buttonLabel="Refresh top blocking providers"
      status={status}
      message={message}
      tone="secondary"
      disabled={isPending || status === "working" || projectIds.length === 0}
      onClick={() => void triggerBulkRefresh()}
    />
  );
}
