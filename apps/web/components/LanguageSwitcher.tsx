"use client";

import { useI18n } from "@/lib/i18n";

export function LanguageSwitcher() {
  const { locale, setLocale } = useI18n();

  return (
    <div className="language-switcher">
      <button
        className={`lang-btn ${locale === "zh" ? "active" : ""}`}
        onClick={() => setLocale("zh")}
        aria-label="中文"
      >
        中文
      </button>
      <button
        className={`lang-btn ${locale === "en" ? "active" : ""}`}
        onClick={() => setLocale("en")}
        aria-label="English"
      >
        EN
      </button>
    </div>
  );
}
