"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { refreshProjectConnector } from "@/lib/api";
import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";
import type { ConnectorKind } from "@seo-ad-autopilot/contracts";

type ActionStatus = "idle" | "working" | "done" | "error";

export function ProjectConnectorRefreshAction({
  projectId,
  provider,
}: {
  projectId: string;
  provider: ConnectorKind;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Ready to refresh");
  const [isPending, startTransition] = useTransition();

  async function triggerRefresh() {
    setStatus("working");
    setMessage(`Refreshing ${provider}...`);
    try {
      const result = await refreshProjectConnector(projectId, provider);
      const code = result.evidence.failureCode ?? result.connection.details?.errorCode;
      const retryable = result.evidence.retryable ? "retryable" : "not retryable";
      setStatus(result.status === "connected" ? "done" : "error");
      setMessage(
        result.status === "connected"
          ? `${provider} connected.`
          : `${provider} ${result.status} · ${code ?? "no code"} · ${retryable}`,
      );
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Connector refresh failed.");
    }
  }

  return (
    <div className="action-rail" style={{ marginTop: 12 }}>
      <ActionSummaryBadge
        tone={status === "working" ? "working" : status === "done" ? "done" : status === "error" ? "error" : "idle"}
        title={status}
        description={message}
      />
      <div className="action-caption">
        <span>API</span>
        <code>/api/projects/{projectId}/connectors/{provider}/refresh</code>
      </div>
      <button className="button button-secondary" disabled={isPending || status === "working"} onClick={() => void triggerRefresh()}>
        Refresh provider
      </button>
    </div>
  );
}

