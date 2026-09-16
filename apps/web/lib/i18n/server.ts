import { cookies } from "next/headers";

import { LOCALE_COOKIE, translate, type Locale } from "./shared";

export function getServerLocale(): Locale {
  return cookies().get(LOCALE_COOKIE)?.value === "en" ? "en" : "zh";
}

export function getServerI18n() {
  const locale = getServerLocale();
  return {
    locale,
    t: (key: string) => translate(locale, key),
  };
}
