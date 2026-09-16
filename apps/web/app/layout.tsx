import type { ReactNode } from "react";
import { ClientLayout } from "@/components/ClientLayout";
import { getServerLocale } from "@/lib/i18n/server";

import "./globals.css";

export const metadata = {
  title: "SEO-AD AutoPilot",
  description: "Multi-Engine SEO + GEO + Auto Ad Discovery.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const locale = getServerLocale();
  return (
    <html lang={locale === "zh" ? "zh-CN" : "en"}>
      <body>
        <ClientLayout initialLocale={locale}>{children}</ClientLayout>
      </body>
    </html>
  );
}
