"use client";

import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { bulkRefreshProjectConnector } from "@/lib/api";
import { ExecutionSummary } from "@/components/ExecutionSummary";
import type { ConnectorKind } from "@seo-ad-autopilot/contracts";

type ActionStatus = "idle" | "working" | "done" | "error";

const CONNECTOR_OPTIONS: Array<{ value: ConnectorKind; label: string }> = [
  { value: "search_console", label: "Search Console" },
  { value: "ga4", label: "GA4" },
  { value: "sitemap", label: "Sitemap" },
  { value: "playwright", label: "Playwright" },
  { value: "trend", label: "Trend" },
  { value: "news", label: "News" },
  { value: "qa", label: "QA" },
  { value: "github", label: "GitHub" },
  { value: "cms", label: "CMS" },
  { value: "script_api", label: "Universal Script" },
  { value: "ad_network", label: "Ad Network" },
];

export function BulkConnectorRefreshAction({
  projectIds,
  defaultProvider = "search_console",
  lockProvider = false,
  label,
}: {
  projectIds: string[];
  defaultProvider?: ConnectorKind;
  lockProvider?: boolean;
  label?: string;
}) {
  const router = useRouter();
  const [provider, setProvider] = useState<ConnectorKind>(defaultProvider);
  const [status, setStatus] = useState<ActionStatus>("idle");
  const [message, setMessage] = useState("Ready to refresh provider");
  const [isPending, startTransition] = useTransition();
  const selectedLabel = useMemo(
    () => CONNECTOR_OPTIONS.find((item) => item.value === provider)?.label ?? provider,
    [provider],
  );

  async function triggerBulkRefresh() {
    if (projectIds.length === 0) {
      setStatus("error");
      setMessage("No projects available to refresh.");
      return;
    }
    setStatus("working");
    setMessage(`Refreshing ${selectedLabel} across ${projectIds.length} projects...`);
    try {
      const result = await bulkRefreshProjectConnector(provider, { projectIds });
      const skipped = result.skippedProjectIds.length ? `, skipped ${result.skippedProjectIds.length}` : "";
      setStatus("done");
      setMessage(`Refreshed ${result.refreshedCount} project${result.refreshedCount === 1 ? "" : "s"}${skipped}.`);
      startTransition(() => router.refresh());
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Bulk connector refresh failed.");
    }
  }

  return (
    <div className="stack">
      <div className="action-caption">
        <span>Provider</span>
        {lockProvider ? (
          <strong>{selectedLabel}</strong>
        ) : (
          <select value={provider} onChange={(event) => setProvider(event.target.value as ConnectorKind)}>
            {CONNECTOR_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
      </div>
      <ExecutionSummary
        apiPath={`/api/bulk/projects/connectors/${provider}/refresh`}
        targetCount={projectIds.length}
        targetLabel="projects"
        buttonLabel={label ?? `Refresh ${selectedLabel}`}
        status={status}
        message={message}
        tone="secondary"
        disabled={isPending || status === "working" || projectIds.length === 0}
        onClick={() => void triggerBulkRefresh()}
      />
    </div>
  );
}
