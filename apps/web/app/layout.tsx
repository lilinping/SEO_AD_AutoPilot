import type { ReactNode } from "react";
import { ClientLayout } from "@/components/ClientLayout";

import "./globals.css";

export const metadata = {
  title: "SEO-AD AutoPilot",
  description: "Multi-Engine SEO + GEO + Auto Ad Discovery.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}
