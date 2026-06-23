"use client";

import { useI18n } from "@/lib/i18n";

export default function AcceptancePage() {
  const { t } = useI18n();

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("nav.acceptance")}</div>
        <h1>{t("acceptance.title")}</h1>
        <p className="hero-copy">{t("acceptance.hero_description")}</p>
      </section>

      <section className="panel">
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">{t("acceptance.gates")}</div>
            <div className="stat-value">0</div>
            <div className="stat-caption">{t("acceptance.acceptance_gates")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("acceptance.passed")}</div>
            <div className="stat-value">0</div>
            <div className="stat-caption">{t("acceptance.gates_passed")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("acceptance.failed")}</div>
            <div className="stat-value">0</div>
            <div className="stat-caption">{t("acceptance.gates_failed")}</div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("acceptance.acceptance_status")}</div>
            <h2>{t("acceptance.acceptance_status")}</h2>
          </div>
        </div>
        <div className="alert-box">{t("common.requires_api")}</div>
      </section>
    </div>
  );
}
