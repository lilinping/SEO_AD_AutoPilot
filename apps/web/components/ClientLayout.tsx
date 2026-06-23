"use client";

import { ReactNode } from "react";
import Link from "next/link";
import { I18nProvider, useI18n } from "@/lib/i18n";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

export function ClientLayout({ children }: { children: ReactNode }) {
  return (
    <I18nProvider>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-mark">SEO-AD AutoPilot</div>
            <LanguageSwitcher />
          </div>
          <SidebarNav />
          <SidebarCard />
        </aside>
        <main className="content-shell">{children}</main>
      </div>
    </I18nProvider>
  );
}

function SidebarNav() {
  const { t } = useI18n();
  
  const navItems = [
    { href: "/", labelKey: "nav.overview" },
    { href: "/dashboard", labelKey: "nav.dashboard" },
    { href: "/analyze", labelKey: "nav.analyze" },
    { href: "/projects", labelKey: "nav.projects" },
    { href: "/strategy", labelKey: "nav.strategy" },
    { href: "/quality", labelKey: "nav.quality" },
    { href: "/acceptance", labelKey: "nav.acceptance" },
    { href: "/approvals", labelKey: "nav.approvals" },
    { href: "/ecommerce", labelKey: "nav.ecommerce" },
    { href: "/keywords", labelKey: "nav.keywords" },
    { href: "/monitor", labelKey: "nav.monitor" },
    { href: "/settings", labelKey: "nav.settings" },
  ];

  return (
    <nav className="sidebar-nav">
      {navItems.map((item) => (
        <Link className="nav-link" href={item.href} key={item.href}>
          <span>{t(item.labelKey)}</span>
          <span>→</span>
        </Link>
      ))}
    </nav>
  );
}

function SidebarCard() {
  const { t } = useI18n();
  
  return (
    <div className="sidebar-card">
      <h3>{t("home.subtitle")}</h3>
      <p>Analyze sites across SEO + GEO, discover ad platforms, and optimize for all search engines.</p>
      <div className="sidebar-actions">
        <Link className="sidebar-button" href="/analyze">
          {t("nav.analyze")}
        </Link>
        <Link className="sidebar-link" href="/projects">
          {t("nav.projects")}
        </Link>
      </div>
    </div>
  );
}
