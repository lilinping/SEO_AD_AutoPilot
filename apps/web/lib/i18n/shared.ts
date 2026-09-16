import en from "./en.json";
import zh from "./zh.json";

export type Locale = "en" | "zh";
export const LOCALE_COOKIE = "seo-ad-autopilot-locale";

const translations: Record<Locale, Record<string, unknown>> = { en, zh };

export function translate(locale: Locale, key: string): string {
  let value: unknown = translations[locale];

  for (const segment of key.split(".")) {
    if (!value || typeof value !== "object" || !(segment in value)) {
      return key;
    }
    value = (value as Record<string, unknown>)[segment];
  }

  return typeof value === "string" ? value : key;
}
