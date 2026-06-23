import type { ReactNode } from "react";

import { ActionSummaryBadge } from "@/components/ActionSummaryBadge";

type Tone = "primary" | "secondary";

export function ExecutionSummary({
  apiPath,
  targetCount,
  targetLabel,
  buttonLabel,
  status,
  message,
  tone = "primary",
  disabled,
  onClick,
}: {
  apiPath: string;
  targetCount: number;
  targetLabel: string;
  buttonLabel: string;
  status: string;
  message: ReactNode;
  tone?: Tone;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <div className="action-rail">
      <ActionSummaryBadge tone={status === "working" ? "working" : status === "done" ? "done" : status === "error" ? "error" : "idle"} title={status} description={message} />
      <div className="action-caption">
        <span>API</span>
        <code>{apiPath}</code>
        <span>
          {targetCount} {targetLabel}
        </span>
      </div>
      <button className={`button ${tone === "primary" ? "button-primary" : "button-secondary"}`} disabled={disabled} onClick={onClick}>
        {buttonLabel}
      </button>
    </div>
  );
}
