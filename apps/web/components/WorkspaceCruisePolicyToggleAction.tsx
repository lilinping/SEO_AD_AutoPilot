"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { updateWorkspacePolicy } from "@/lib/api";
import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";

type ActionStatus = "idle" | "working" | "done" | "error";

export function WorkspaceCruisePolicyToggleAction({ autoCruiseEnabled }: { autoCruiseEnabled: boolean }) {
  const router = useRouter();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState(autoCruiseEnabled ? "Workspace auto cruise enabled" : "Workspace auto cruise disabled");
  const [isPending, startTransition] = useTransition();

  async function toggleAutoCruise() {
    setStatus("working");
    setMessage("Updating workspace policy...");
    try {
      await updateWorkspacePolicy({ autoCruiseEnabled: !autoCruiseEnabled });
      setStatus("done");
      setMessage(!autoCruiseEnabled ? "Workspace auto cruise enabled." : "Workspace auto cruise disabled.");
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Workspace policy update failed.");
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
        <code>/api/policy</code>
      </div>
      <button className="button button-secondary" disabled={isPending || status === "working"} onClick={() => void toggleAutoCruise()}>
        {autoCruiseEnabled ? "Disable workspace auto cruise" : "Enable workspace auto cruise"}
      </button>
    </div>
  );
}
