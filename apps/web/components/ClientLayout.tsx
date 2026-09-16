"use client";

import { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { I18nProvider, useI18n } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n/shared";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

export function ClientLayout({ children, initialLocale }: { children: ReactNode; initialLocale: Locale }) {
  return (
    <I18nProvider initialLocale={initialLocale}>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <Link className="brand-mark" href="/dashboard">SEO-AD AutoPilot</Link>
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
  const pathname = usePathname();

  const primaryItems = [
    { href: "/dashboard", labelKey: "nav.dashboard" },
    { href: "/projects", labelKey: "nav.projects" },
    { href: "/approvals", labelKey: "nav.approvals" },
    { href: "/monitor", labelKey: "nav.monitor" },
    { href: "/settings", labelKey: "nav.settings" },
  ];

  const groupedItems = [
    {
      labelKey: "nav.analysis_tools",
      items: [
        { href: "/analyze", labelKey: "nav.analyze" },
        { href: "/strategy", labelKey: "nav.strategy" },
        { href: "/ecommerce", labelKey: "nav.ecommerce" },
        { href: "/keywords", labelKey: "nav.keywords" },
      ],
    },
    {
      labelKey: "nav.governance",
      items: [
        { href: "/quality", labelKey: "nav.quality" },
        { href: "/acceptance", labelKey: "nav.acceptance" },
      ],
    },
    {
      labelKey: "nav.commercial",
      items: [{ href: "/pricing", labelKey: "nav.pricing" }],
    },
  ];

  const isActive = (href: string) => pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));

  return (
    <nav className="sidebar-nav" aria-label={t("nav.workspace")}>
      <div className="nav-section-label">{t("nav.workspace")}</div>
      {primaryItems.map((item) => {
        const active = isActive(item.href);
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={`nav-link ${active ? "active" : ""}`}
            href={item.href}
            key={item.href}
          >
            {t(item.labelKey)}
          </Link>
        );
      })}
      <div className="nav-groups">
        {groupedItems.map((group) => {
          const groupActive = group.items.some((item) => isActive(item.href));
          return (
            <details className="nav-group" open={groupActive || undefined} key={group.labelKey}>
              <summary>{t(group.labelKey)}</summary>
              <div className="nav-group-links">
                {group.items.map((item) => {
                  const active = isActive(item.href);
                  return (
                    <Link
                      aria-current={active ? "page" : undefined}
                      className={`nav-link nav-link-secondary ${active ? "active" : ""}`}
                      href={item.href}
                      key={item.href}
                    >
                      {t(item.labelKey)}
                    </Link>
                  );
                })}
              </div>
            </details>
          );
        })}
      </div>
    </nav>
  );
}

function SidebarCard() {
  const { t } = useI18n();
  
  return (
    <div className="sidebar-card">
      <h3>{t("sidebar.title")}</h3>
      <p>{t("sidebar.description")}</p>
      <div className="sidebar-actions">
        <Link className="sidebar-button" href="/analyze">
          {t("sidebar.primary_action")}
        </Link>
        <Link className="sidebar-link" href="/projects">
          {t("sidebar.secondary_action")}
        </Link>
      </div>
    </div>
  );
}
