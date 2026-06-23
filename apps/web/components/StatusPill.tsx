import type { ReactNode } from "react";

type Tone = "neutral" | "good" | "warn" | "danger" | "accent";

const toneMap: Record<Tone, string> = {
  neutral: "pill pill-neutral",
  good: "pill pill-good",
  warn: "pill pill-warn",
  danger: "pill pill-danger",
  accent: "pill pill-accent",
};

export function StatusPill({ children, tone = "neutral" }: { children: ReactNode; tone?: Tone }) {
  return <span className={toneMap[tone]}>{children}</span>;
}

export function toneForStatus(value: string): Tone {
  if (value === "deployed" || value === "approved") return "good";
  if (value === "awaiting_approval" || value === "scheduled") return "warn";
  if (value === "rolled_back" || value === "blocked" || value === "rejected") return "danger";
  return "neutral";
}
