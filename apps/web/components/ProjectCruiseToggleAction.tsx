"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { updateProjectConnections } from "@/lib/api";
import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";
import type { ProjectConnection } from "@seo-ad-autopilot/contracts";

type ActionStatus = "idle" | "working" | "done" | "error";

export function ProjectCruiseToggleAction({
  projectId,
  autoCruiseEnabled,
  syncIntervalMinutes,
  connections,
}: {
  projectId: string;
  autoCruiseEnabled: boolean;
  syncIntervalMinutes: number;
  connections: ProjectConnection[];
}) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState(autoCruiseEnabled ? "Auto cruise enabled" : "Auto cruise disabled");
  const [isPending, startTransition] = useTransition();

  async function toggleCruise() {
    setStatus("working");
    setMessage("Updating cruise policy...");
    try {
      const result = await updateProjectConnections(projectId, {
        autoCruiseEnabled: !autoCruiseEnabled,
        syncIntervalMinutes,
        connections,
      });
      setStatus("done");
      setMessage(result.state.autoCruiseEnabled ? "Auto cruise enabled for this project." : "Auto cruise disabled for this project.");
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Failed to update auto cruise.");
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
        <code>/api/projects/{projectId}/connections</code>
      </div>
      <button className="button button-secondary" disabled={isPending || status === "working"} onClick={() => void toggleCruise()}>
        {autoCruiseEnabled ? "Disable auto cruise" : "Enable auto cruise"}
      </button>
    </div>
  );
}
