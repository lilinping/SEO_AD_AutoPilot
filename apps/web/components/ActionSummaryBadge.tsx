import type { ReactNode } from "react";

type Tone = "idle" | "working" | "done" | "error";

const toneClass: Record<Tone, string> = {
  idle: "pill pill-neutral",
  working: "pill pill-warn",
  done: "pill pill-good",
  error: "pill pill-danger",
};

export function ActionSummaryBadge({
  tone,
  title,
  description,
}: {
  tone: Tone;
  title: string;
  description: ReactNode;
}) {
  return (
    <div className="action-summary">
      <div className="action-summary-head">
        <span className={toneClass[tone]}>{title}</span>
      </div>
      <div className="action-summary-copy">{description}</div>
    </div>
  );
}
