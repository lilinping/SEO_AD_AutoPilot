"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { testProjectConnections } from "@/lib/api";
import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";
import { StatusPill } from "@/components/StatusPill";
import { useI18n } from "@/lib/i18n";

type ActionStatus = "idle" | "working" | "done" | "error";

export function ProjectConnectionTestAction({ projectId }: { projectId: string }) {
  const router = useRouter();
  const { t } = useI18n();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("");
  const [health, setHealth] = useState<string>("unknown");
  const [strictSummary, setStrictSummary] = useState("");
  const [isPending, startTransition] = useTransition();

  async function triggerTest() {
    setStatus("working");
    setMessage(t("actions.testing_connections"));
    try {
      const result = await testProjectConnections(projectId);
      setStatus("done");
      setHealth(result.connectionHealth);
      setStrictSummary(
        `${t("actions.strict_mode")}: ${result.strictMode ? t("project_detail.on") : t("project_detail.off")} · ${t("actions.blockers")}: ${result.strictGapCount}`,
      );
      setMessage(
        result.strictBlocked
          ? `${t("actions.strict_blocked")} (${result.strictGapCount}).`
          : result.issues.length > 0
            ? `${result.issues.length} ${t("actions.issues_detected")}`
            : t("actions.all_checks_passed"),
      );
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : t("actions.connection_test_failed"));
    }
  }

  return (
    <div className="action-rail">
      <ActionSummaryBadge tone={status === "working" ? "working" : status === "done" ? "done" : status === "error" ? "error" : "idle"} title={t(`actions.status_${status}`)} description={message || t("actions.ready_test")} />
      <div className="action-caption">
        <span>API</span>
        <code>/api/projects/{projectId}/connections/test</code>
      </div>
      <div className="action-buttons">
        <button className="button button-secondary" disabled={isPending || status === "working"} onClick={() => void triggerTest()}>
          {t("actions.test_connections")}
        </button>
      </div>
      <div className="action-message">
        <StatusPill tone={health === "healthy" ? "good" : health === "degraded" ? "warn" : health === "unavailable" ? "danger" : "neutral"}>
          {health}
        </StatusPill>
        <span>{strictSummary || `${t("actions.strict_mode")}: n/a`}</span>
      </div>
    </div>
  );
}
