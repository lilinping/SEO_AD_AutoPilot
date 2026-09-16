"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { updateProjectConnections } from "@/lib/api";
import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";
import type { ProjectConnection } from "@seo-ad-autopilot/contracts";
import { useI18n } from "@/lib/i18n";

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
  const { t } = useI18n();
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("");
  const [isPending, startTransition] = useTransition();

  async function toggleCruise() {
    setStatus("working");
    setMessage(t("actions.updating_cruise"));
    try {
      const result = await updateProjectConnections(projectId, {
        autoCruiseEnabled: !autoCruiseEnabled,
        syncIntervalMinutes,
        connections,
      });
      setStatus("done");
      setMessage(result.state.autoCruiseEnabled ? t("actions.cruise_enabled_project") : t("actions.cruise_disabled_project"));
      startTransition(() => {
        router.refresh();
      });
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : t("actions.cruise_update_failed"));
    }
  }

  return (
    <div className="action-rail">
      <ActionSummaryBadge
        tone={status === "working" ? "working" : status === "done" ? "done" : status === "error" ? "error" : "idle"}
        title={t(`actions.status_${status}`)}
        description={message || (autoCruiseEnabled ? t("actions.cruise_enabled") : t("actions.cruise_disabled"))}
      />
      <div className="action-caption">
        <span>API</span>
        <code>/api/projects/{projectId}/connections</code>
      </div>
      <button className="button button-secondary" disabled={isPending || status === "working"} onClick={() => void toggleCruise()}>
        {autoCruiseEnabled ? t("actions.disable_cruise") : t("actions.enable_cruise")}
      </button>
    </div>
  );
}
