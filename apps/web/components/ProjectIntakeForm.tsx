"use client";

import type { ReactNode } from "react";
import { FormEvent, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { analyzeProject, createProject } from "@/lib/api";
import { StatCard } from "@/components/StatCard";

type FormState = {
  projectName: string;
  url: string;
  siteName: string;
  repoUrl: string;
  cmsName: string;
  sitemapUrls: string;
  keywords: string;
  brandWhitelist: string;
  competitors: string;
  approvalRules: string;
  searchConsole: string;
  ga4: string;
  locale: string;
  language: string;
  notes: string;
};

type PresetKey = "commerce" | "content" | "saas" | "ymyl";

type PresetInput = {
  projectName: string;
  url: string;
  siteName: string;
  repoUrl?: string;
  cmsName?: string;
  sitemapUrls: string[];
  keywords: string[];
  brandWhitelist: string[];
  competitors: string[];
  approvalRules: Record<string, unknown>;
  searchConsole: Record<string, unknown>;
  ga4: Record<string, unknown>;
  locale: string;
  language: string;
  notes: string;
};

function joinLines(values: string[]): string {
  return values.join("\n");
}

function createPreset(input: PresetInput): FormState {
  return {
    projectName: input.projectName,
    url: input.url,
    siteName: input.siteName,
    repoUrl: input.repoUrl ?? "",
    cmsName: input.cmsName ?? "",
    sitemapUrls: joinLines(input.sitemapUrls),
    keywords: joinLines(input.keywords),
    brandWhitelist: joinLines(input.brandWhitelist),
    competitors: joinLines(input.competitors),
    approvalRules: JSON.stringify(input.approvalRules, null, 2),
    searchConsole: JSON.stringify(input.searchConsole, null, 2),
    ga4: JSON.stringify(input.ga4, null, 2),
    locale: input.locale,
    language: input.language,
    notes: input.notes,
  };
}

const PRESETS: Record<PresetKey, FormState> = {
  commerce: createPreset({
    projectName: "Aurora Shop",
    url: "https://aurora-shop.example",
    siteName: "Aurora Shop",
    repoUrl: "https://github.com/example/aurora-shop",
    cmsName: "shopify",
    sitemapUrls: ["/sitemap.xml", "/collections-sitemap.xml"],
    keywords: ["winter jackets", "outdoor gear", "membrane shell", "packable layers"],
    brandWhitelist: ["Aurora"],
    competitors: ["northpeak", "snowtrail"],
    approvalRules: { riskFloor: 45, autoDeploy: false, deploymentMode: "github_pr" },
    searchConsole: { property: "aurora-shop.example", indexing: "healthy", clickTrend: "stable" },
    ga4: { property: "GA4-001", conversionFocus: "add_to_cart", trafficTrend: "steady" },
    locale: "en-US",
    language: "en",
    notes: "Ecommerce storefront with scripted checkout protections and collection landing pages.",
  }),
  content: createPreset({
    projectName: "Northstar Media",
    url: "https://northstar-media.example",
    siteName: "Northstar Media",
    repoUrl: "https://github.com/example/northstar-media",
    cmsName: "ghost",
    sitemapUrls: ["/sitemap.xml", "/news-sitemap.xml"],
    keywords: ["industry insights", "growth signals", "editorial brief", "featured snippet"],
    brandWhitelist: ["Northstar"],
    competitors: ["dailybrief", "signalroom"],
    approvalRules: { riskFloor: 55, autoDeploy: false, editorialReview: true },
    searchConsole: { property: "northstar-media.example", indexing: "healthy", snippets: "opportunity-rich" },
    ga4: { property: "GA4-002", conversionFocus: "newsletter_signup", trafficTrend: "growing" },
    locale: "en-US",
    language: "en",
    notes: "Content publisher focused on deep briefs, schema, and snippet coverage.",
  }),
  saas: createPreset({
    projectName: "LedgerFlow",
    url: "https://ledgerflow.example",
    siteName: "LedgerFlow",
    repoUrl: "https://github.com/example/ledgerflow",
    cmsName: "webflow",
    sitemapUrls: ["/sitemap.xml"],
    keywords: ["budget tracker", "cash flow", "monthly plan", "pricing page"],
    brandWhitelist: ["LedgerFlow"],
    competitors: ["finpilot", "budgetwise"],
    approvalRules: { riskFloor: 50, autoDeploy: false, deploymentMode: "cms_draft" },
    searchConsole: { property: "ledgerflow.example", indexing: "moderate", impressionsTrend: "rising" },
    ga4: { property: "GA4-003", conversionFocus: "trial_start", trafficTrend: "steady" },
    locale: "en-US",
    language: "en",
    notes: "SaaS landing page with pricing, use cases, and trust-building modules.",
  }),
  ymyl: createPreset({
    projectName: "Trust Clinic",
    url: "https://trust-clinic.example",
    siteName: "Trust Clinic",
    cmsName: "drupal",
    sitemapUrls: ["/sitemap.xml"],
    keywords: ["medical guidance", "patient resources", "clinic reviews"],
    brandWhitelist: [],
    competitors: ["careline", "healthvault"],
    approvalRules: { riskFloor: 30, autoDeploy: false, disableAds: true, editorialReview: true },
    searchConsole: { property: "trust-clinic.example", indexing: "strict", snippetPolicy: "cautious" },
    ga4: { property: "GA4-004", conversionFocus: "appointment_request", trafficTrend: "flat" },
    locale: "en-US",
    language: "en",
    notes: "YMYL site where ad inventory should not be recommended.",
  }),
};

const DEFAULT_STATE = PRESETS.commerce;

function splitList(value: string): string[] {
  return value
    .split(/[\n,]/g)
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function parseJsonField(value: string, label: string): Record<string, unknown> {
  if (!value.trim()) {
    return {};
  }
  try {
    const parsed = JSON.parse(value) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
    return { value: parsed };
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
}

function Field({
  label,
  help,
  spanTwo = false,
  children,
}: {
  label: string;
  help?: string;
  spanTwo?: boolean;
  children: ReactNode;
}) {
  return (
    <label className={`field${spanTwo ? " field-span-2" : ""}`}>
      <span className="field-label">{label}</span>
      {children}
      {help ? <span className="field-help">{help}</span> : null}
    </label>
  );
}

export function ProjectIntakeForm() {
  const router = useRouter();
  const [state, setState] = useState<FormState>(DEFAULT_STATE);
  const [activePreset, setActivePreset] = useState<PresetKey>("commerce");
  const [status, setStatus] = useState<"idle" | "working" | "done" | "error">("idle");
  const [message, setMessage] = useState("Ready to launch");
  const [error, setError] = useState<string>("");
  const [isPending, startTransition] = useTransition();

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setState((current) => ({ ...current, [key]: value }));
  }

  function loadPreset(preset: PresetKey) {
    setState(PRESETS[preset]);
    setActivePreset(preset);
    setError("");
    setStatus("idle");
    setMessage(`Loaded ${preset} preset`);
  }

  async function launchProject() {
    const projectName = state.projectName.trim();
    const url = state.url.trim();
    if (!projectName || !url) {
      throw new Error("Project name and URL are required.");
    }

    const intake = {
      url,
      siteName: state.siteName.trim() || undefined,
      repoUrl: state.repoUrl.trim() || undefined,
      cmsName: state.cmsName.trim() || undefined,
      sitemapUrls: splitList(state.sitemapUrls),
      searchConsole: parseJsonField(state.searchConsole, "Search Console"),
      ga4: parseJsonField(state.ga4, "GA4"),
      keywords: splitList(state.keywords),
      brandWhitelist: splitList(state.brandWhitelist),
      competitors: splitList(state.competitors),
      approvalRules: parseJsonField(state.approvalRules, "Approval rules"),
      locale: state.locale.trim() || "en-US",
      language: state.language.trim() || "en",
      notes: state.notes.trim(),
    };

    setStatus("working");
    setMessage("Creating project...");
    const project = await createProject({ name: projectName, intake });
    setMessage("Running analysis...");
    await analyzeProject(project.projectId, intake);
    setStatus("done");
    setMessage("Analysis complete");
    startTransition(() => {
      router.push(`/projects/${project.projectId}`);
      router.refresh();
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    void launchProject().catch((launchError) => {
      setStatus("error");
      setMessage("Launch failed");
      setError(launchError instanceof Error ? launchError.message : "Project launch failed.");
    });
  }

  const signalCounts = {
    sitemapUrls: splitList(state.sitemapUrls).length,
    keywords: splitList(state.keywords).length,
    brandWhitelist: splitList(state.brandWhitelist).length,
    competitors: splitList(state.competitors).length,
  };

  const previewPayload = {
    projectName: state.projectName || "Untitled project",
    url: state.url || "https://example.com",
    siteName: state.siteName || state.projectName || "Site",
    cmsName: state.cmsName || "unspecified",
    locale: state.locale || "en-US",
    language: state.language || "en",
    signals: signalCounts,
    approvalRules: state.approvalRules ? "custom JSON provided" : "default policy",
  };
  const requiredReady = Boolean(state.projectName.trim() && state.url.trim());
  const optionalSignalCount = [
    state.siteName.trim(),
    state.repoUrl.trim(),
    state.cmsName.trim(),
    state.locale.trim(),
    state.language.trim(),
    state.searchConsole.trim(),
    state.ga4.trim(),
    state.approvalRules.trim(),
    state.notes.trim(),
  ].filter(Boolean).length;
  const intakeCompleteness = Math.round(((requiredReady ? 2 : 0) + optionalSignalCount) / 11 * 100);

  return (
    <form className="intake-layout" onSubmit={handleSubmit}>
      <section className="panel form-panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Intake</div>
            <h2>Source data</h2>
          </div>
          <p>Provide the site URL and any optional signals. The backend will classify the site, score risk, and generate a preview-first plan.</p>
        </div>

        <div className="form-grid">
          <Field label="Project name" help="Human-readable workspace label." spanTwo>
            <input
              required
              type="text"
              value={state.projectName}
              onChange={(event) => setField("projectName", event.target.value)}
              placeholder="Aurora Shop"
            />
          </Field>
          <Field label="Canonical URL" help="The production URL to analyze." spanTwo>
            <input
              required
              type="url"
              value={state.url}
              onChange={(event) => setField("url", event.target.value)}
              placeholder="https://example.com"
            />
          </Field>
          <Field label="Site name" help="Optional display name for the workspace.">
            <input
              type="text"
              value={state.siteName}
              onChange={(event) => setField("siteName", event.target.value)}
              placeholder="Aurora Shop"
            />
          </Field>
          <Field label="Repository URL" help="GitHub or Git provider URL if the site is code-managed.">
            <input
              type="url"
              value={state.repoUrl}
              onChange={(event) => setField("repoUrl", event.target.value)}
              placeholder="https://github.com/org/repo"
            />
          </Field>
          <Field label="CMS" help="Optional CMS or publishing system.">
            <input
              type="text"
              value={state.cmsName}
              onChange={(event) => setField("cmsName", event.target.value)}
              placeholder="shopify, webflow, ghost"
            />
          </Field>
          <Field label="Locale" help="Used for language-aware recommendations.">
            <input
              type="text"
              value={state.locale}
              onChange={(event) => setField("locale", event.target.value)}
              placeholder="en-US"
            />
          </Field>
          <Field label="Language" help="Primary content language.">
            <input
              type="text"
              value={state.language}
              onChange={(event) => setField("language", event.target.value)}
              placeholder="en"
            />
          </Field>
          <Field label="Sitemap URLs" help="Comma or newline separated.">
            <textarea
              value={state.sitemapUrls}
              onChange={(event) => setField("sitemapUrls", event.target.value)}
              placeholder="/sitemap.xml"
            />
          </Field>
          <Field label="Keywords" help="Seed keywords for opportunity discovery.">
            <textarea
              value={state.keywords}
              onChange={(event) => setField("keywords", event.target.value)}
              placeholder="keyword one"
            />
          </Field>
          <Field label="Brand whitelist" help="Names that should be preserved in copy and anchors.">
            <textarea
              value={state.brandWhitelist}
              onChange={(event) => setField("brandWhitelist", event.target.value)}
              placeholder="Brand name"
            />
          </Field>
          <Field label="Competitors" help="Reference sites for comparison and positioning.">
            <textarea
              value={state.competitors}
              onChange={(event) => setField("competitors", event.target.value)}
              placeholder="competitor.example"
            />
          </Field>
          <Field label="Search Console JSON" help="Optional JSON blob for source analytics." spanTwo>
            <textarea
              value={state.searchConsole}
              onChange={(event) => setField("searchConsole", event.target.value)}
              placeholder='{"property":"example.com"}'
            />
          </Field>
          <Field label="GA4 JSON" help="Optional analytics payload." spanTwo>
            <textarea
              value={state.ga4}
              onChange={(event) => setField("ga4", event.target.value)}
              placeholder='{"property":"G-XXXX"}'
            />
          </Field>
          <Field label="Approval rules JSON" help="Policy overrides for this site." spanTwo>
            <textarea
              value={state.approvalRules}
              onChange={(event) => setField("approvalRules", event.target.value)}
              placeholder='{"riskFloor":45,"autoDeploy":false}'
            />
          </Field>
          <Field label="Notes" help="Any extra context for analysis or deployment." spanTwo>
            <textarea
              value={state.notes}
              onChange={(event) => setField("notes", event.target.value)}
              placeholder="High-level site constraints, business context, or rollout notes."
            />
          </Field>
        </div>

        <div className="form-actions">
          <button className="button button-primary" disabled={status === "working" || isPending} type="submit">
            {status === "working" ? "Launching..." : "Create project and run analysis"}
          </button>
          <div className="form-status">
            <strong>{status.toUpperCase()}</strong>
            <span>{message}</span>
          </div>
        </div>
        {error ? <div className="alert-box form-error">{error}</div> : null}
      </section>

      <aside className="summary-card panel sticky-card">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Control</div>
            <h2>Preset and payload</h2>
          </div>
          <p>Use a preset to seed a representative intake, or edit the fields directly.</p>
        </div>

        <div className="stat-grid" style={{ marginBottom: 14 }}>
          <StatCard label="Preset" value={activePreset} caption="selected intake template" accent />
          <StatCard label="Signals" value={String(signalCounts.sitemapUrls + signalCounts.keywords + signalCounts.brandWhitelist + signalCounts.competitors)} caption="seed data items" />
          <StatCard label="Policy" value={state.approvalRules.trim() ? "custom" : "default"} caption="approval policy source" />
          <StatCard label="Readiness" value={state.projectName.trim() && state.url.trim() ? "ready" : "missing"} caption="minimum launch fields" />
          <StatCard label="Completeness" value={`${intakeCompleteness}%`} caption="filled launch context" accent />
          <StatCard label="Required" value={requiredReady ? "yes" : "no"} caption="project name and URL present" />
        </div>

        <div className="preset-grid">
          {(Object.keys(PRESETS) as PresetKey[]).map((preset) => (
            <button
              className={`button button-secondary preset-button${activePreset === preset ? " preset-button-active" : ""}`}
              key={preset}
              onClick={() => loadPreset(preset)}
              type="button"
            >
              <span>{preset}</span>
              <span>Load</span>
            </button>
          ))}
        </div>

        <div className="summary-list">
          <div className="summary-item">
            <span>Active preset</span>
            <strong>{activePreset}</strong>
          </div>
          <div className="summary-item">
            <span>Sitemaps</span>
            <strong>{signalCounts.sitemapUrls}</strong>
          </div>
          <div className="summary-item">
            <span>Keywords</span>
            <strong>{signalCounts.keywords}</strong>
          </div>
          <div className="summary-item">
            <span>Competitors</span>
            <strong>{signalCounts.competitors}</strong>
          </div>
        </div>

        <pre className="json-preview">{JSON.stringify(previewPayload, null, 2)}</pre>

        <div className="alert-box">
          The backend will derive site class, generate a preview artifact, and stop at the approval gate unless the policy allows automation.
        </div>
      </aside>
    </form>
  );
}
