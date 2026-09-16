"use client";

import { useRouter } from "next/navigation";

import { useI18n } from "@/lib/i18n";
import { LOCALE_COOKIE } from "@/lib/i18n/shared";

export function LanguageSwitcher() {
  const { locale, setLocale } = useI18n();
  const router = useRouter();

  const selectLocale = (nextLocale: "zh" | "en") => {
    document.cookie = `${LOCALE_COOKIE}=${nextLocale}; path=/; max-age=31536000; samesite=lax`;
    setLocale(nextLocale);
    router.refresh();
  };

  return (
    <div className="language-switcher">
      <button
        className={`lang-btn ${locale === "zh" ? "active" : ""}`}
        onClick={() => selectLocale("zh")}
        aria-label="中文"
      >
        中文
      </button>
      <button
        className={`lang-btn ${locale === "en" ? "active" : ""}`}
        onClick={() => selectLocale("en")}
        aria-label="English"
      >
        EN
      </button>
    </div>
  );
}
