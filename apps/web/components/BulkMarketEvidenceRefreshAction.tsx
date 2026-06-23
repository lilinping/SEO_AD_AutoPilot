"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { bulkRefreshMarketEvidenceConnectors } from "@/lib/api";
import { ExecutionSummary } from "@/components/ExecutionSummary";

type ActionStatus = "idle" | "working" | "done" | "error";

export function BulkMarketEvidenceRefreshAction({
  projectIds,
  label = "Refresh market evidence",
}: {
  projectIds: string[];
  label?: string;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Ready to refresh market evidence");
  const [isPending, startTransition] = useTransition();

  async function triggerBulkRefresh() {
    if (projectIds.length === 0) {
      setStatus("error");
      setMessage("No projects available.");
      return;
    }
    setStatus("working");
    setMessage("Refreshing trend/news/qa evidence...");
    try {
      const result = await bulkRefreshMarketEvidenceConnectors({
        projectIds,
        providers: ["trend", "news", "qa"],
        maxProviders: 3,
      });
      setStatus("done");
      setMessage(`Providers ${result.providerCount}, refreshed ${result.refreshedCount}, skipped ${result.skippedProjectCount}.`);
      startTransition(() => router.refresh());
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Market evidence refresh failed.");
    }
  }

  return (
    <ExecutionSummary
      apiPath="/api/bulk/connectors/market-evidence/refresh"
      targetCount={projectIds.length}
      targetLabel="projects"
      buttonLabel={label}
      status={status}
      message={message}
      tone="secondary"
      disabled={isPending || status === "working" || projectIds.length === 0}
      onClick={() => void triggerBulkRefresh()}
    />
  );
}
