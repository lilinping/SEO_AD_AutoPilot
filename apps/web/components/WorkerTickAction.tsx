"use client";

import { useState } from "react";

import { runWorkerOnce } from "@/lib/api";
import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";

type ActionStatus = "idle" | "working" | "done" | "error";

export function WorkerTickAction() {
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("No worker tick yet");

  async function triggerTick() {
    setStatus("working");
    setMessage("Running worker tick...");
    try {
      const result = await runWorkerOnce();
      setStatus("done");
      setMessage(
        result.processed > 0
          ? `Processed ${result.processed} task${result.processed === 1 ? "" : "s"}.`
          : "No pending tasks were processed.",
      );
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Worker tick failed.");
    }
  }

  return (
    <div className="action-rail">
      <ActionSummaryBadge tone={status === "working" ? "working" : status === "done" ? "done" : status === "error" ? "error" : "idle"} title={status} description={message} />
      <div className="action-caption">
        <span>API</span>
        <code>/api/worker/run-once</code>
      </div>
      <button className="button button-primary" disabled={status === "working"} onClick={() => void triggerTick()}>
        Run worker tick
      </button>
    </div>
  );
}
