"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { publishRuntimeEdgeGateway, publishVisualFarmGateway } from "@/lib/api";
import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";

type ActionStatus = "idle" | "working" | "done" | "error";
type GatewayKind = "runtime-edge" | "visual-farm";

const apiPathMap: Record<GatewayKind, string> = {
  "runtime-edge": "/api/runtime-edge/gateway/publish",
  "visual-farm": "/api/visual-farm/gateway/publish",
};

export function GatewayPublishAction({
  kind,
  projectId,
  label,
}: {
  kind: GatewayKind;
  projectId?: string;
  label?: string;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState(
    kind === "runtime-edge" ? "Publish runtime-edge gateway policy." : "Publish visual-farm gateway policy.",
  );
  const [isPending, startTransition] = useTransition();

  async function trigger() {
    setStatus("working");
    setMessage("Publishing gateway policy...");
    try {
      const result = kind === "runtime-edge" ? await publishRuntimeEdgeGateway(projectId) : await publishVisualFarmGateway(projectId);
      const gatewayPublish = result?.gatewayPublish ?? null;
      setStatus(gatewayPublish?.status === "completed" || result?.gatewayReady ? "done" : gatewayPublish?.status === "blocked" ? "error" : "idle");
      setMessage(
        gatewayPublish?.message ??
          (gatewayPublish?.status === "completed"
            ? "Gateway policy published successfully."
            : gatewayPublish?.failureCode
              ? `Publish blocked: ${gatewayPublish.failureCode}`
              : "Gateway publish completed."),
      );
      startTransition(() => router.refresh());
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Gateway publish failed.");
    }
  }

  return (
    <div className="action-rail">
      <ActionSummaryBadge
        tone={status === "working" ? "working" : status === "done" ? "done" : status === "error" ? "error" : "idle"}
        title={status}
        description={message}
      />
      <div className="action-caption">
        <span>API</span>
        <code>{apiPathMap[kind]}</code>
        <span>{projectId ? `project ${projectId}` : "workspace"}</span>
      </div>
      <button className="button button-primary" disabled={isPending || status === "working"} onClick={() => void trigger()}>
        {label ?? `Publish ${kind}`}
      </button>
    </div>
  );
}
