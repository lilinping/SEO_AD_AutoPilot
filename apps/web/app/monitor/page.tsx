"use client";

import { useI18n } from "@/lib/i18n";

export default function MonitorPage() {
  const { t } = useI18n();

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("nav.monitor")}</div>
        <h1>{t("monitor.title")}</h1>
        <p className="hero-copy">{t("monitor.hero_description")}</p>
      </section>

      <section className="panel">
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">{t("monitor.health")}</div>
            <div className="stat-value">--</div>
            <div className="stat-caption">{t("monitor.system_health")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("monitor.alerts")}</div>
            <div className="stat-value">0</div>
            <div className="stat-caption">{t("monitor.active_alerts")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("monitor.rollbacks")}</div>
            <div className="stat-value">0</div>
            <div className="stat-caption">{t("monitor.available_rollbacks")}</div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("monitor.system_status")}</div>
            <h2>{t("monitor.system_status")}</h2>
          </div>
        </div>
        <div className="alert-box">{t("common.requires_api")}</div>
      </section>
    </div>
  );
}
