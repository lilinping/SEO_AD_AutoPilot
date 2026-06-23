"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { enqueueVisualRegressionRuns } from "@/lib/api";
import { ExecutionSummary } from "@/components/ExecutionSummary";

type ActionStatus = "idle" | "working" | "done" | "error";

export function VisualRegressionEnqueueAction({
  strictMode,
  maxCases = 12,
  label = "Enqueue visual run",
}: {
  strictMode?: boolean;
  maxCases?: number;
  label?: string;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Queue a visual regression run for worker execution.");
  const [isPending, startTransition] = useTransition();

  async function triggerEnqueue() {
    setStatus("working");
    setMessage("Submitting visual regression job to worker queue.");
    try {
      const result = await enqueueVisualRegressionRuns({
        strictMode,
        projectIds: [],
        maxCases: Math.max(1, maxCases),
      });
      setStatus(result.enqueued ? "done" : "error");
      setMessage(result.message || (result.enqueued ? "Visual run enqueued." : "Visual run enqueue skipped."));
      startTransition(() => router.refresh());
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Visual run enqueue failed.");
    }
  }

  return (
    <ExecutionSummary
      apiPath="/api/visual-regressions/runs/enqueue"
      targetCount={maxCases}
      targetLabel="max cases"
      buttonLabel={label}
      status={status}
      message={message}
      tone="secondary"
      disabled={isPending || status === "working"}
      onClick={() => void triggerEnqueue()}
    />
  );
}
