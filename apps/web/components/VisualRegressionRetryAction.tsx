"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { retryVisualRegressions } from "@/lib/api";
import { ExecutionSummary } from "@/components/ExecutionSummary";

type ActionStatus = "idle" | "working" | "done" | "error";
type FailureCategory = "auth" | "permission" | "rate_limit" | "network" | "validation" | "config" | "unavailable" | "other";

export function VisualRegressionRetryAction({
  categories = ["network", "rate_limit", "unavailable"],
  maxCases = 10,
  label = "Retry visual failures",
}: {
  categories?: FailureCategory[];
  maxCases?: number;
  label?: string;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Ready to retry visual failures.");
  const [isPending, startTransition] = useTransition();

  async function triggerRetry() {
    setStatus("working");
    setMessage(`Retrying visual regressions for categories: ${categories.join(", ")}.`);
    try {
      const result = await retryVisualRegressions({
        categories,
        retryableOnly: true,
        maxCases: Math.max(1, maxCases),
      });
      setStatus(result.rerunFailed > 0 ? "error" : "done");
      setMessage(
        `Attempted ${result.attempted}, passed ${result.rerunPassed}, failed ${result.rerunFailed}, skipped ${result.skipped}.`,
      );
      startTransition(() => router.refresh());
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Visual retry failed.");
    }
  }

  return (
    <ExecutionSummary
      apiPath="/api/visual-regressions/retry"
      targetCount={maxCases}
      targetLabel="max cases"
      buttonLabel={label}
      status={status}
      message={message}
      tone="secondary"
      disabled={isPending || status === "working"}
      onClick={() => void triggerRetry()}
    />
  );
}
