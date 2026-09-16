import type { PlanStep } from "@seo-ad-autopilot/contracts";

import { compactLabel } from "@/lib/format";
import { getServerI18n } from "@/lib/i18n/server";

export function WorkflowTimeline({ steps }: { steps: PlanStep[] }) {
  const { t } = getServerI18n();
  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <div className="eyebrow">{t("project_detail.workflow")}</div>
          <h2>{t("project_detail.skill_chain")}</h2>
        </div>
        <p>{t("project_detail.skill_chain_description")}</p>
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
                <span>{step.approvalRequired ? t("project_detail.approval_required") : t("project_detail.read_only")}</span>
                <span>{step.rollbackSupported ? t("project_detail.rollback_supported") : t("project_detail.no_rollback")}</span>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
