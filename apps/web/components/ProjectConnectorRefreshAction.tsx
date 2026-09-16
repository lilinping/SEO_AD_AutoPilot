"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { refreshProjectConnector } from "@/lib/api";
import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";
import type { ConnectorKind } from "@seo-ad-autopilot/contracts";
import { useI18n } from "@/lib/i18n";

type ActionStatus = "idle" | "working" | "done" | "error";

export function ProjectConnectorRefreshAction({
  projectId,
  provider,
}: {
  projectId: string;
  provider: ConnectorKind;
}) {
  const router = useRouter();
  const { t } = useI18n();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  async function triggerRefresh() {
    setStatus("working");
    setMessage(`${t("actions.refreshing")} ${provider}...`);
    try {
      const result = await refreshProjectConnector(projectId, provider);
      const code = result.evidence.failureCode ?? result.connection.details?.errorCode;
      const retryable = result.evidence.retryable ? t("actions.retryable") : t("actions.not_retryable");
      setStatus(result.status === "connected" ? "done" : "error");
      setMessage(
        result.status === "connected"
          ? `${provider} ${t("actions.connected")}`
          : `${provider} ${result.status} · ${code ?? t("actions.no_code")} · ${retryable}`,
      );
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : t("actions.refresh_failed"));
    }
  }

  return (
    <div className="action-rail" style={{ marginTop: 12 }}>
      <ActionSummaryBadge
        tone={status === "working" ? "working" : status === "done" ? "done" : status === "error" ? "error" : "idle"}
        title={t(`actions.status_${status}`)}
        description={message || t("actions.ready_refresh")}
      />
      <div className="action-caption">
        <span>API</span>
        <code>/api/projects/{projectId}/connectors/{provider}/refresh</code>
      </div>
      <button className="button button-secondary" disabled={isPending || status === "working"} onClick={() => void triggerRefresh()}>
        {t("actions.refresh_provider")}
      </button>
    </div>
  );
}
