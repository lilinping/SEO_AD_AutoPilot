"use client";

import { useI18n } from "@/lib/i18n";

export default function QualityPage() {
  const { t } = useI18n();

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("nav.quality")}</div>
        <h1>{t("quality.title")}</h1>
        <p className="hero-copy">{t("quality.hero_description")}</p>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("quality.quality_overview")}</div>
            <h2>{t("quality.quality_overview")}</h2>
          </div>
        </div>
        <div className="alert-box">{t("common.requires_api")}</div>
      </section>
    </div>
  );
}
