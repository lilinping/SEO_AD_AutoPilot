"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { bulkRefreshStrictGapConnectors } from "@/lib/api";
import { ExecutionSummary } from "@/components/ExecutionSummary";

type ActionStatus = "idle" | "working" | "done" | "error";

export function BulkStrictGapRefreshAction({
  projectIds,
  maxProviders = 5,
}: {
  projectIds: string[];
  maxProviders?: number;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Ready to refresh strict-gap providers");
  const [isPending, startTransition] = useTransition();

  async function triggerBulkRefresh() {
    if (projectIds.length === 0) {
      setStatus("error");
      setMessage("No projects available.");
      return;
    }
    setStatus("working");
    setMessage("Refreshing strict-gap providers...");
    try {
      const result = await bulkRefreshStrictGapConnectors({
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
      setMessage(error instanceof Error ? error.message : "Strict-gap refresh failed.");
    }
  }

  return (
    <ExecutionSummary
      apiPath="/api/bulk/connectors/strict-gap/refresh"
      targetCount={projectIds.length}
      targetLabel="projects"
      buttonLabel="Refresh top strict-gap providers"
      status={status}
      message={message}
      tone="secondary"
      disabled={isPending || status === "working" || projectIds.length === 0}
      onClick={() => void triggerBulkRefresh()}
    />
  );
}
