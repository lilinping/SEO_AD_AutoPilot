"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

export default function StrategyPage() {
  const { t } = useI18n();

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("nav.strategy")}</div>
        <h1>{t("strategy.title")}</h1>
        <p className="hero-copy">{t("strategy.hero_description")}</p>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("strategy.strategy_by_project")}</div>
            <h2>{t("strategy.strategy_by_project")}</h2>
          </div>
        </div>
        <div className="alert-box">{t("common.requires_api")}</div>
      </section>
    </div>
  );
}
