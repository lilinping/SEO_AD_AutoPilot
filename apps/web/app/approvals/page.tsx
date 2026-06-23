"use client";

import { useI18n } from "@/lib/i18n";

export default function ApprovalsPage() {
  const { t } = useI18n();

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("nav.approvals")}</div>
        <h1>{t("approvals.title")}</h1>
        <p className="hero-copy">{t("approvals.hero_description")}</p>
      </section>

      <section className="panel">
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">{t("approvals.pending")}</div>
            <div className="stat-value">0</div>
            <div className="stat-caption">{t("approvals.awaiting_approval")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("approvals.approved")}</div>
            <div className="stat-value">0</div>
            <div className="stat-caption">{t("approvals.approved_today")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("approvals.rejected")}</div>
            <div className="stat-value">0</div>
            <div className="stat-caption">{t("approvals.rejected_today")}</div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("approvals.approval_queue")}</div>
            <h2>{t("approvals.approval_queue")}</h2>
          </div>
        </div>
        <div className="alert-box">{t("common.requires_api")}</div>
      </section>
    </div>
  );
}
