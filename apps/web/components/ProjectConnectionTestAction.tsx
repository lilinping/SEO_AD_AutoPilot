"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { testProjectConnections } from "@/lib/api";
import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";
import { StatusPill } from "@/components/StatusPill";

type ActionStatus = "idle" | "working" | "done" | "error";

export function ProjectConnectionTestAction({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Ready to test");
  const [health, setHealth] = useState<string>("unknown");
  const [strictSummary, setStrictSummary] = useState("strict mode: n/a");
  const [isPending, startTransition] = useTransition();

  async function triggerTest() {
    setStatus("working");
    setMessage("Testing project connections...");
    try {
      const result = await testProjectConnections(projectId);
      setStatus("done");
      setHealth(result.connectionHealth);
      setStrictSummary(
        `strict mode: ${result.strictMode ? "on" : "off"} · blockers: ${result.strictGapCount}`,
      );
      setMessage(
        result.strictBlocked
          ? `Strict mode blocked (${result.strictGapCount} blocker${result.strictGapCount === 1 ? "" : "s"}).`
          : result.issues.length > 0
            ? `${result.issues.length} issue${result.issues.length === 1 ? "" : "s"} detected.`
            : "All connector checks passed.",
      );
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Connection test failed.");
    }
  }

  return (
    <div className="action-rail">
      <ActionSummaryBadge tone={status === "working" ? "working" : status === "done" ? "done" : status === "error" ? "error" : "idle"} title={status} description={message} />
      <div className="action-caption">
        <span>API</span>
        <code>/api/projects/{projectId}/connections/test</code>
      </div>
      <div className="action-buttons">
        <button className="button button-secondary" disabled={isPending || status === "working"} onClick={() => void triggerTest()}>
          Test connections
        </button>
      </div>
      <div className="action-message">
        <StatusPill tone={health === "healthy" ? "good" : health === "degraded" ? "warn" : health === "unavailable" ? "danger" : "neutral"}>
          {health}
        </StatusPill>
        <span>{strictSummary}</span>
      </div>
    </div>
  );
}
