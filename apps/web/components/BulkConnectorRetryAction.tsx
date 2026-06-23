"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { retryConnectors } from "@/lib/api";
import { ExecutionSummary } from "@/components/ExecutionSummary";
import type { ConnectorKind } from "@seo-ad-autopilot/contracts";

type ActionStatus = "idle" | "working" | "done" | "error";
type FailureCategory = "auth" | "permission" | "rate_limit" | "network" | "validation" | "config" | "unavailable" | "other";

export function BulkConnectorRetryAction({
  category,
  projectIds,
  providers = [],
  label,
}: {
  category: FailureCategory;
  projectIds: string[];
  providers?: ConnectorKind[];
  label?: string;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Ready to retry");
  const [isPending, startTransition] = useTransition();

  async function triggerRetry() {
    setStatus("working");
    setMessage(`Retrying ${category} connector failures...`);
    try {
      const result = await retryConnectors({
        categories: [category],
        projectIds,
        providers,
        retryableOnly: true,
        maxRetries: 50,
      });
      setStatus(result.failed > 0 ? "error" : "done");
      setMessage(
        `Attempted ${result.attempted}, refreshed ${result.refreshed}, failed ${result.failed}, skipped ${result.skipped}.`,
      );
      startTransition(() => router.refresh());
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Bulk retry failed.");
    }
  }

  return (
    <ExecutionSummary
      apiPath="/api/connectors/retry"
      targetCount={projectIds.length}
      targetLabel="projects"
      buttonLabel={label ?? `Retry ${category} failures`}
      status={status}
      message={message}
      tone="secondary"
      disabled={isPending || status === "working" || projectIds.length === 0}
      onClick={() => void triggerRetry()}
    />
  );
}

