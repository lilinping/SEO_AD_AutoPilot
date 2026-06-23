"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { enqueueVisualFarmProbe } from "@/lib/api";
import { ExecutionSummary } from "@/components/ExecutionSummary";

type ActionStatus = "idle" | "working" | "done" | "error";

export function VisualFarmProbeEnqueueAction({
  label = "Enqueue visual farm probe",
}: {
  label?: string;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Queue a visual farm probe in worker.");
  const [isPending, startTransition] = useTransition();

  async function trigger() {
    setStatus("working");
    setMessage("Submitting visual farm probe job.");
    try {
      const result = await enqueueVisualFarmProbe();
      setStatus(result.enqueued ? "done" : "error");
      setMessage(result.message || (result.enqueued ? "Visual farm probe job enqueued." : "Visual farm probe enqueue skipped."));
      startTransition(() => router.refresh());
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Visual farm probe enqueue failed.");
    }
  }

  return (
    <ExecutionSummary
      apiPath="/api/visual-farm/probe/enqueue"
      targetCount={1}
      targetLabel="job"
      buttonLabel={label}
      status={status}
      message={message}
      tone="secondary"
      disabled={isPending || status === "working"}
      onClick={() => void trigger()}
    />
  );
}
