import type { PlanStep } from "@seo-ad-autopilot/contracts";

import { compactLabel } from "@/lib/format";

export function WorkflowTimeline({ steps }: { steps: PlanStep[] }) {
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <div className="eyebrow">Workflow</div>
          <h2>Skill chain</h2>
        </div>
        <p>Read, shape, guard, release, and observe as a single loop.</p>
      </div>
      <div className="timeline">
        {steps.map((step, index) => (
          <article className={`timeline-item ${step.destructive ? "timeline-item-danger" : ""}`} key={step.id}>
            <div className="timeline-index">{String(index + 1).padStart(2, "0")}</div>
            <div className="timeline-body">
              <div className="timeline-title">{compactLabel(step.skillId)}</div>
              <div className="timeline-copy">{step.action}</div>
              <div className="timeline-meta">
                <span>{step.target}</span>
                <span>{step.approvalRequired ? "approval" : "read-only"}</span>
                <span>{step.rollbackSupported ? "rollback" : "no-rollback"}</span>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
