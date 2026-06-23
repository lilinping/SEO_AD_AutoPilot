import type { ReactNode } from "react";

export function StatCard({
  label,
  value,
  caption,
  accent = false,
}: {
  label: string;
  value: ReactNode;
  caption?: ReactNode;
  accent?: boolean;
}) {
  return (
    <section className={`stat-card ${accent ? "stat-card-accent" : ""}`}>
      <div className="stat-card-label">{label}</div>
      <div className="stat-card-value">{value}</div>
      {caption ? <div className="stat-card-caption">{caption}</div> : null}
    </section>
  );
}
