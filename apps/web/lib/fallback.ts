import type {
  ConnectionHealth,
  ConnectorKind,
  ConnectorStatus,
  ConnectorProviderCoverageItem,
  ConnectorFailureReport,
  ConnectorsHealthResult,
  ProjectConnectionEvidenceReport,
  BulkConnectorActionHistoryReport,
  ConnectorRetryHistoryReport,
  VisualRegressionRetryHistoryReport,
  VisualRegressionRunHistoryReport,
  VisualRegressionRemediationReport,
  DeploymentHistoryReport,
  ProjectConnectionHistoryReport,
  WorkspaceConnectionEvidenceReport,
  WorkspaceConnectionHistoryReport,
  ConnectorRemediationReport,
  AdAuditReport,
  WorkspaceAdAuditHistoryReport,
  AlertReport,
  AlertDeliveryReport,
  AlertEmitStatusReport,
  AlertEmitHistoryReport,
  AlertPresetCollection,
  AlertRuleCollection,
  OnCallPolicyCollection,
  OnCallCoverageReport,
  WorkspaceBillingReport,
  WorkspaceBillingSettlementExecution,
  WorkspaceBillingSettlementExecutionHistoryReport,
  WorkspaceBillingSettlementExecutionReport,
  WorkspaceBillingSettlementExecutionRequest,
  WorkspaceBillingSettlementGatewayPolicy,
  WorkspaceBillingSettlementGatewayPolicyUpdateRequest,
  WorkspaceBillingSettlementGatewayHistoryReport,
  WorkspaceBillingSettlementGatewayReport,
  WorkspaceBillingSettlementGatewayProviderStatus,
  WorkspaceBillingSettlementGatewayProviderStatusReport,
  WorkspaceBillingSettlement,
  WorkspaceExperimentAssignmentReport,
  WorkspaceExperimentAssignmentRequest,
  WorkspaceExperiment,
  WorkspaceExperimentReport,
  WorkspaceExperimentPolicy,
  WorkspaceExperimentVariant,
  WorkspaceLocalizationClusterStatus,
  WorkspaceLocalizationAssignmentReport,
  WorkspaceLocalizationAssignmentRequest,
  WorkspaceLocalizationPolicy,
  WorkspaceLocalizationReport,
  WorkspaceSiteCluster,
  RuntimeRouteRequest,
  RuntimeRouteReport,
  RuntimeEdgeGatewayProviderStatus,
  RuntimeEdgeGatewayProviderStatusReport,
  WorkspaceTemplateMarketPolicy,
  WorkspaceTemplateMarketReport,
  WorkspaceTemplateMarketTemplate,
  WorkspaceModelGatewayHistoryReport,
  WorkspaceModelGatewayReport,
  WorkspaceModelGatewayProviderStatus,
  WorkspaceModelGatewayProviderStatusReport,
  WorkspaceModelGatewayPolicy,
  WorkspaceModelGatewayPolicyUpdateRequest,
  VisualFarmGatewayProviderStatus,
  VisualFarmGatewayProviderStatusReport,
  MarketEvidenceProviderStatus,
  MarketEvidenceProviderStatusReport,
  DashboardSnapshot,
  DeploymentMode,
  ContentStrategyReport,
  IngestionReport,
  MarketEvidenceReport,
  MarketEvidenceHealthReport,
  ProjectCruiseHealthReport,
  WorkspaceCruiseHealthReport,
  WorkspaceMarketEvidenceHealthReport,
  WorkspaceRuntimeRouteHealthItem,
  WorkspaceRuntimeRouteHealthReport,
  WorkspaceRuntimeRouteHistoryItem,
  WorkspaceRuntimeRouteHistoryReport,
  PromptRegistry,
  ProjectDetail,
  ProjectConnection,
  ProjectRun,
  ProjectRuntimeRouteHistoryReport,
  ProjectState,
  WorkspaceConnectorsHealthReport,
  AcceptanceReport,
  AcceptanceHistoryReport,
  ProductBenchmarkReport,
  RemainingTaskReport,
  RemainingTaskBoardReport,
  RegressionReport,
  RegressionSample,
  RegressionSampleSet,
  RollbackHistoryReport,
  PromptVersion,
  SkillRegressionReport,
  VisualRegressionReport,
  VisualRegressionHealthReport,
  VisualRegressionRunsReport,
  VisualFarmStatusReport,
  VisualFarmProbeReport,
  VisualFarmProbeHistoryReport,
  ObservabilityStatusReport,
  WorkerExecutionHistoryReport,
  WorkerServiceHealthReport,
  WorkerQueueHealthReport,
  TechnicalSeoReport,
  TechnicalSeoPatchReport,
  SiteClass,
  WorkflowBundle,
} from "@seo-ad-autopilot/contracts";

const commonPolicy = {
  autoDeployEnabled: true,
  approvalRequiredThreshold: 60,
  blockAutoDeployThreshold: 80,
  monitorWindowMinutes: 90,
  rollbackWindowMinutes: 5,
  autoCruiseEnabled: false,
  allowedDeploymentModes: ["github_pr", "cms_draft", "universal_script", "static_export"] as DeploymentMode[],
};

function sampleWorkflow(projectId: string, name: string, siteClass: SiteClass, riskScore: number, deploymentMode: DeploymentMode): WorkflowBundle {
  const taskId = `${projectId}-task`;
  const connectionHealth: ConnectionHealth = siteClass === "ymyl" ? "degraded" : "healthy";
  const now = new Date().toISOString();
  return {
    project: {
      projectId,
      name,
      url: `https://${projectId}.example`,
      siteClass,
      latestStage: "awaiting_approval",
      riskScore,
      deploymentMode,
      recommendation: riskScore >= 60 ? "Manual approval required" : "Auto deploy eligible",
      updatedAt: new Date().toISOString(),
      connectionHealth,
      lastSyncAt: now,
      nextSyncAt: now,
      runCount: 1,
    },
    task: {
      taskId,
      projectId,
      status: "awaiting_approval",
      riskScore,
      approvalStatus: "pending",
      siteClass,
      updatedAt: new Date().toISOString(),
    },
    siteProfile: {
      siteId: projectId,
      name,
      url: `https://${projectId}.example`,
      vertical: siteClass,
      language: "en",
      locale: "en-US",
      brandVoice: siteClass === "content" ? "editorial" : "brand-led",
      pageCountEstimate: 12,
      trustSignals: ["navigation_depth", "author_pages"],
      pages: [
        {
          url: `https://${projectId}.example`,
          title: `${name} Home`,
          description: "Fallback snapshot used when the API is offline.",
          headings: ["Home", "Why it matters", "What changes"],
          wordCount: 920,
          internalLinks: 18,
          externalLinks: 4,
          images: 24,
          missingAltCount: 2,
          structuredData: ["Organization"],
          ctaCount: 2,
          performanceBudget: { lcpMs: 2300, cls: 4, inpMs: 130 },
        },
      ],
      evidence: ["fallback-data"],
      riskScore,
    },
    ingestionReport: {
      reportId: `${projectId}-ingest`,
      projectId,
      taskId,
      status: siteClass === "ymyl" ? "synthetic" : "connected",
      generatedAt: now,
      evidence: [
        {
          provider: "search_console",
          status: "connected",
          summary: "Fallback Search Console evidence.",
          provenance: ["fallback"],
          details: { property: projectId },
          checkedAt: now,
        },
        {
          provider: "sitemap",
          status: "synthetic",
          summary: "Fallback sitemap evidence.",
          provenance: ["fallback"],
          details: { sourceCount: 1 },
          checkedAt: now,
        },
      ],
      connectorStatus: { search_console: "connected", sitemap: "synthetic" },
      provenance: { search_console: ["fallback"], sitemap: ["fallback"] },
      notes: ["Fallback ingestion report."],
    } satisfies IngestionReport,
    experimentAssignment: fallbackWorkspaceExperimentAssignmentReport({
      projectId,
      subjectKey: taskId,
      targetSurface: "site",
      targetLocale: "en-US",
    }),
    localizationAssignment: fallbackWorkspaceLocalizationAssignmentReport({
      projectId,
      targetLocale: "en-US",
      host: `${projectId}.example`,
      subjectKey: taskId,
    }),
    runtimeRoute: {
      generatedAt: now,
      projectId,
      taskId,
      subjectKey: taskId,
      requestPath: `/api/projects/${projectId}/runtime-route`,
      requestMethod: "POST",
      targetSurface: "site",
      targetLocale: "en-US",
      host: `${projectId}.example`,
      experimentAssignment: fallbackWorkspaceExperimentAssignmentReport({
        projectId,
        subjectKey: taskId,
        targetSurface: "site",
        targetLocale: "en-US",
      }),
      localizationAssignment: fallbackWorkspaceLocalizationAssignmentReport({
        projectId,
        targetLocale: "en-US",
        host: `${projectId}.example`,
        subjectKey: taskId,
      }),
      gatewayReport: fallbackWorkspaceModelGatewayReport(),
      resolvedProviders: {
        read: "fallback",
        seo: "fallback",
        ad: "fallback",
        deploy: "fallback",
        observe: "fallback",
      },
      runtimeReady: false,
      executionMode: "preview",
      executionAction: "serve_preview",
      executionReason: "Fallback runtime route report is non-authoritative.",
      executionEntrypoint: `/api/projects/${projectId}/runtime-route`,
      warnings: ["Fallback runtime route report is non-authoritative."],
      recommendations: ["Enable experiments, localization, and model gateway routing for runtime readiness."],
    } satisfies RuntimeRouteReport,
    opportunitySet: {
      seo: [
        {
          id: `${projectId}-seo-1`,
          category: "seo",
          title: "Meta and snippet tuning",
          description: "Align titles and descriptions with search intent.",
          impactScore: 82,
          effortScore: 3,
          riskScore: 18,
          skillIds: ["seo/content-opportunity-finder", "seo/schema-builder"],
          previewTarget: "hero-meta",
          evidence: ["fallback"],
        },
      ],
      ad:
        siteClass === "ymyl"
          ? [
              {
                id: `${projectId}-ad-1`,
                category: "ad",
                title: "Do not recommend ads",
                description: "Trust-sensitive page should stay ad-free.",
                impactScore: 30,
                effortScore: 1,
                riskScore: 92,
                skillIds: ["ad/ad-slot-auditor"],
                previewTarget: "no-ad-rail",
                evidence: ["fallback"],
              },
            ]
          : [
              {
                id: `${projectId}-ad-1`,
                category: "ad",
                title: "Native sponsorship rail",
                description: "Add a contextual sponsorship rail away from CTAs.",
                impactScore: 80,
                effortScore: 4,
                riskScore: 28,
                skillIds: ["ad/ad-slot-auditor", "ad/provider-integrator", "ad/ad-wrapper-renderer"],
                previewTarget: "sponsor-rail",
                evidence: ["fallback"],
              },
            ],
      technical: [
        {
          id: `${projectId}-tech-1`,
          category: "technical",
          title: "Canonical and crawl hygiene patch",
          description: "Normalize canonical signals.",
          impactScore: 84,
          effortScore: 4,
          riskScore: 26,
          skillIds: ["seo/technical-seo-patcher"],
          previewTarget: "head-hygiene",
          evidence: ["fallback"],
        },
      ],
      ux: [
        {
          id: `${projectId}-ux-1`,
          category: "ux",
          title: "Above-the-fold clarity pass",
          description: "Keep the CTA visible while improving hierarchy.",
          impactScore: 78,
          effortScore: 3,
          riskScore: 14,
          skillIds: ["seo/adaptive-component-generator"],
          previewTarget: "hero-band",
          evidence: ["fallback"],
        },
      ],
    },
    plan: {
      planId: `${projectId}-plan`,
      siteId: projectId,
      deploymentMode,
      riskScore,
      releaseStrategy: "Preview-first release path",
      steps: [
        {
          id: `${projectId}-step-1`,
          skillId: "read/site-sniffer",
          action: "Read profile",
          target: `https://${projectId}.example`,
          expectedOutput: "Structured evidence from Site Sniffer.",
          approvalRequired: false,
          destructive: false,
          rollbackSupported: false,
        },
      ],
      rationale: ["Fallback data from the console when the API is unavailable."],
      requiresManualApproval: riskScore >= 60,
      autoDeployAllowed: riskScore < 80,
    },
    uxReview: {
      score: riskScore >= 60 ? 72 : 86,
      issues: riskScore >= 60 ? ["Manual approval required before release."] : [],
      notes: ["Fallback UX review."],
      recommendations: ["Use preview-first changes."],
    },
    approvalRequest: {
      approvalId: `${projectId}-approval`,
      taskId,
      status: "pending",
      requiredApprovers: ["growth-owner", "brand-guardian"],
      policySnapshot: commonPolicy,
      riskSummary: `${riskScore} risk score in fallback mode.`,
      decisionHint: "Preview is ready.",
    },
    preview: {
      previewId: `${projectId}-preview`,
      beforeHtml: `<main><h1>${name}</h1></main>`,
      afterHtml: `<main><h1>${name} with stronger intent framing</h1></main>`,
      domInsertions: ["hero", "trust-band"],
      cssDiff: ".hero { display:grid; }",
      performanceBudget: { baselineLcpMs: 2300, estimatedLcpMs: 2460, budgetDeltaMs: 160 },
      diffSummary: "Fallback preview keeps the page structure intact.",
    },
    deployment: {
      deploymentId: `${projectId}-deploy`,
      taskId,
      mode: deploymentMode,
      status: riskScore >= 80 ? "blocked" : "scheduled",
      artifactRef: `${projectId}-preview`,
      releaseNotes: ["Fallback deployment record."],
      rollbackReady: true,
      patchManifestRef: `artifact://patch-manifests/${taskId}.json`,
      writebackTarget: deploymentMode,
      writebackAuthSource: "fallback",
      writebackAttempts: [{ endpoint: "fallback://writeback", status: "skipped", failureCode: "FALLBACK_MODE", latencyMs: 0 }],
      providerArtifactId: `${projectId}-provider-artifact`,
      providerUrl: deploymentMode === "github_pr" ? `https://example.com/pr/${projectId}` : null,
      writebackSummary: {
        provider: deploymentMode === "github_pr" ? "github" : deploymentMode === "cms_draft" ? "cms" : deploymentMode === "universal_script" ? "script_api" : "static_export",
        status: riskScore >= 80 ? "blocked" : "scheduled",
        successCount: 0,
        failedCount: 0,
        skippedCount: 1,
        lastEndpoint: "fallback://writeback",
        successfulEndpoints: [],
        failedEndpoints: [],
        averageLatencyMs: 0,
        providerArtifactId: `${projectId}-provider-artifact`,
        providerUrl: deploymentMode === "github_pr" ? `https://example.com/pr/${projectId}` : null,
        authSource: "fallback",
        fallbackReason: "Fallback mode active",
        failureCode: "FALLBACK_MODE",
      },
      strictBlockers: [],
      fallbackReason: "Fallback mode active",
      failureCode: "FALLBACK_MODE",
    },
    metricSnapshot:
      riskScore >= 80
        ? null
        : {
            snapshotId: `${projectId}-metric`,
            projectId,
            taskId,
            seoScore: 78,
            adFitScore: siteClass === "ymyl" ? 34 : 80,
            coreWebVitals: { lcpMs: 2440, cls: 4, inpMs: 138 },
            trafficDelta: 5,
            conversionDelta: 2,
            sourceStatus: { search_console: "synthetic", ga4: "synthetic" },
            sourceMetricsSummary: [
              {
                source: "search_console",
                status: "synthetic",
                primaryMetric: "Clicks 120",
                secondaryMetric: "Impressions 980",
                tertiaryMetric: "Themes fallback",
                authSource: "fallback",
                fallbackReason: "Synthetic metric baseline",
              },
              {
                source: "ga4",
                status: "synthetic",
                primaryMetric: "Sessions 3400",
                secondaryMetric: "Conversions 42",
                tertiaryMetric: "Engagement 0.71",
                authSource: "fallback",
                fallbackReason: "Synthetic metric baseline",
              },
              {
                source: "ad_network",
                status: "synthetic",
                primaryMetric: "Revenue/day 26.0",
                secondaryMetric: "Fill rate 0.52",
                tertiaryMetric: "RPM 3.80 · Impressions 7200",
                authSource: "fallback",
                fallbackReason: "Synthetic metric baseline",
              },
            ],
            externalMetrics: {
              searchConsole: { clicks: 120, impressions: 980, queryThemes: ["fallback"] },
              ga4: { sessions: 3400, conversions: 42, engagementRate: 0.71 },
            },
            evidence: ["fallback"],
            createdAt: new Date().toISOString(),
          },
    rollbackBundle: {
      rollbackId: `${projectId}-rollback`,
      deploymentId: `${projectId}-deploy`,
      commands: ["restore previous release", "invalidate cache"],
      safeWindowMinutes: 5,
      reason: "Fallback rollback record.",
      expectedEffect: "Restore the previous stable release.",
    },
  };
}

function sampleConnections(projectId: string, siteClass: SiteClass): ProjectConnection[] {
  const now = new Date().toISOString();
  const baseStatus: ConnectorStatus = siteClass === "ymyl" ? "synthetic" : "connected";
  return [
    {
      connectionId: `${projectId}-conn-search`,
      provider: "search_console",
      label: "Search Console",
      enabled: true,
      status: baseStatus,
      providerMode: "fallback",
      strictEligible: false,
      blockingReason: "Fallback Search Console connector.",
      config: { property: projectId },
      details: { summary: "Fallback Search Console connector." },
      provenance: ["fallback"],
      lastCheckedAt: now,
      lastSuccessAt: now,
      lastErrorAt: null,
      lastSyncedAt: now,
      nextSyncAt: now,
    },
    {
      connectionId: `${projectId}-conn-ga4`,
      provider: "ga4",
      label: "GA4",
      enabled: true,
      status: baseStatus,
      providerMode: "fallback",
      strictEligible: false,
      blockingReason: "Fallback GA4 connector.",
      config: { property: projectId },
      details: { summary: "Fallback GA4 connector." },
      provenance: ["fallback"],
      lastCheckedAt: now,
      lastSuccessAt: now,
      lastErrorAt: null,
      lastSyncedAt: now,
      nextSyncAt: now,
    },
    {
      connectionId: `${projectId}-conn-github`,
      provider: "github",
      label: "GitHub",
      enabled: true,
      status: siteClass === "ymyl" ? "unavailable" : "connected",
      providerMode: "fallback",
      strictEligible: false,
      blockingReason: "Fallback GitHub connector.",
      config: { repoUrl: `https://github.com/example/${projectId}` },
      details: { summary: "Fallback GitHub connector." },
      provenance: ["fallback"],
      lastCheckedAt: now,
      lastSuccessAt: siteClass === "ymyl" ? null : now,
      lastErrorAt: siteClass === "ymyl" ? now : null,
      lastSyncedAt: now,
      nextSyncAt: now,
    },
    {
      connectionId: `${projectId}-conn-cms`,
      provider: "cms",
      label: "CMS",
      enabled: true,
      status: siteClass === "ymyl" ? "unavailable" : "connected",
      providerMode: "fallback",
      strictEligible: false,
      blockingReason: "Fallback CMS connector.",
      config: { cmsName: siteClass === "content" ? "ghost" : "webflow" },
      details: { summary: "Fallback CMS connector." },
      provenance: ["fallback"],
      lastCheckedAt: now,
      lastSuccessAt: siteClass === "ymyl" ? null : now,
      lastErrorAt: siteClass === "ymyl" ? now : null,
      lastSyncedAt: now,
      nextSyncAt: now,
    },
    {
      connectionId: `${projectId}-conn-sitemap`,
      provider: "sitemap",
      label: "Sitemap",
      enabled: true,
      status: "synthetic",
      providerMode: "fallback",
      strictEligible: false,
      blockingReason: "Sitemap is synthetic in fallback mode.",
      config: { urls: [`https://${projectId}.example/sitemap.xml`] },
      details: { sourceCount: 1, discoveredUrls: [`https://${projectId}.example/page-1`] },
      provenance: ["fallback"],
      lastCheckedAt: now,
      lastSuccessAt: null,
      lastErrorAt: now,
      lastSyncedAt: now,
      nextSyncAt: now,
    },
    {
      connectionId: `${projectId}-conn-playwright`,
      provider: "playwright",
      label: "Playwright",
      enabled: true,
      status: "synthetic",
      providerMode: "fallback",
      strictEligible: false,
      blockingReason: "Browser crawl is running in fallback mode.",
      config: { enabled: false },
      details: { pageUrl: `https://${projectId}.example` },
      provenance: ["fallback"],
      lastCheckedAt: now,
      lastSyncedAt: now,
      nextSyncAt: now,
    },
  ];
}

function sampleRuns(projectId: string, siteClass: SiteClass): ProjectRun[] {
  const now = new Date().toISOString();
  return [
    {
      runId: `${projectId}-run-1`,
      projectId,
      taskId: `${projectId}-task`,
      trigger: "manual",
      status: siteClass === "ymyl" ? "completed" : "completed",
      startedAt: now,
      finishedAt: now,
      riskScore: siteClass === "ymyl" ? 88 : 54,
      connectorStatus: {
        search_console: siteClass === "ymyl" ? "synthetic" : "connected",
        ga4: siteClass === "ymyl" ? "synthetic" : "connected",
        sitemap: "synthetic",
      },
      evidence: ["fallback-ingestion"],
      notes: ["Fallback run history."],
      autoDeploy: siteClass !== "ymyl",
      rollbackReady: true,
      runtimeRouteReady: siteClass !== "ymyl",
      runtimeRouteSummary: siteClass !== "ymyl"
        ? "runtimeRouteReady=true|experimentVariant=control|localizationCluster=global|gateway=local|gatewayRouteProvider=local|gatewayRouteFallbackProvider=local|gatewayRoutePriority=10"
        : "runtimeRouteReady=false|experimentVariant=unassigned|localizationCluster=unassigned|gateway=local|gatewayRouteProvider=local|gatewayRouteFallbackProvider=local|gatewayRoutePriority=10",
      runtimeRouteRequestPath: `/api/projects/${projectId}/runtime-route`,
      runtimeRouteRequestMethod: "POST",
      gatewayRouteProviderName: "local",
      gatewayRouteFallbackProviderName: "local",
      gatewayRoutePriority: 10,
    },
  ];
}

export function fallbackProjectRuntimeRouteHistoryReport(projectId: string, limit = 20): ProjectRuntimeRouteHistoryReport {
  const entries = sampleRuns(projectId, "ecommerce").slice(0, Math.max(1, Math.min(100, limit)));
  const runtimeReadyCount = entries.filter((run) => run.runtimeRouteReady).length;
  return {
    generatedAt: new Date().toISOString(),
    projectId,
    total: entries.length,
    runtimeReadyCount,
    previewOnlyCount: Math.max(0, entries.length - runtimeReadyCount),
    entries,
  };
}

function sampleState(projectId: string, siteClass: SiteClass): ProjectState {
  const now = new Date().toISOString();
  return {
    projectId,
    connectionHealth: siteClass === "ymyl" ? "degraded" : "healthy",
    autoCruiseEnabled: false,
    syncIntervalMinutes: 60,
    lastSyncAt: now,
    nextSyncAt: now,
    lastRunId: `${projectId}-run-1`,
    lastRunStatus: "completed",
  };
}

const fallbackProjects = [
  sampleWorkflow("aurora-shop", "Aurora Shop", "ecommerce", 49, "github_pr"),
  sampleWorkflow("northstar-media", "Northstar Media", "content", 57, "github_pr"),
  sampleWorkflow("ledgerflow", "LedgerFlow", "saas", 54, "cms_draft"),
  sampleWorkflow("trust-clinic", "Trust Clinic", "ymyl", 88, "cms_draft"),
] as const;

export const fallbackDashboard: DashboardSnapshot = {
  generatedAt: new Date().toISOString(),
  projects: fallbackProjects.map((item) => item.project),
  tasks: fallbackProjects.map((item) => item.task),
  approvals: fallbackProjects.map((item) => item.approvalRequest),
  skills: [],
  policy: commonPolicy,
  marketEvidenceProviders: fallbackMarketEvidenceProviderStatusReport(),
  billingGatewayProviders: fallbackWorkspaceBillingGatewayProviderStatusReport(),
  modelGatewayProviders: fallbackWorkspaceModelGatewayProviderStatusReport(),
  runtimeEdgeGatewayProviders: fallbackRuntimeEdgeGatewayProviderStatusReport(),
  visualFarmGatewayProviders: fallbackVisualFarmGatewayProviderStatusReport(),
  runtimeRouteHealth: fallbackWorkspaceRuntimeRouteHealthReport(),
  runtimeRouteHistory: fallbackWorkspaceRuntimeRouteHistoryReport(),
  adAuditHistory: fallbackWorkspaceAdAuditHistoryReport(),
  billingSettlementHistory: fallbackWorkspaceBillingSettlementExecutionHistoryReport(),
  billingGatewayHistory: fallbackWorkspaceBillingGatewayHistoryReport(),
  modelGatewayHistory: fallbackWorkspaceModelGatewayHistoryReport(),
  alerts: [
    "High-risk tasks are blocked from auto deployment until manual approval is recorded.",
    "Rollback path has been exercised at least once and remains available.",
  ],
};

export function fallbackConnectorFailureReport(): ConnectorFailureReport {
  const now = new Date().toISOString();
  return {
    reportId: "conn-fail-fallback",
    generatedAt: now,
    totalFailures: 7,
    activeProjectCount: fallbackDashboard.projects.length,
    entries: [
      {
        failureCode: "CONFIG_MISSING_ACCESS_TOKEN",
        category: "config",
        count: 3,
        providers: ["search_console", "ga4"],
        affectedProjects: 2,
        projectIds: ["aurora-shop", "northstar-media"],
        lastSeenAt: now,
      },
      {
        failureCode: "CONFIG_MISSING_GITHUB",
        category: "config",
        count: 2,
        providers: ["github_pr"],
        affectedProjects: 2,
        projectIds: ["aurora-shop", "northstar-media"],
        lastSeenAt: now,
      },
      {
        failureCode: "SEARCH_CONSOLE_REQUEST_TIMEOUT",
        category: "network",
        count: 1,
        providers: ["search_console"],
        affectedProjects: 1,
        projectIds: ["aurora-shop"],
        lastSeenAt: now,
      },
      {
        failureCode: "CMS_PERMISSION_DENIED",
        category: "permission",
        count: 1,
        providers: ["cms"],
        affectedProjects: 1,
        projectIds: ["trust-clinic"],
        lastSeenAt: now,
      },
    ],
    notes: ["Fallback connector failure report."],
  };
}

export function fallbackConnectorRetryHistoryReport(): ConnectorRetryHistoryReport {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    entries: [
      {
        auditId: "audit-retry-1",
        actor: "operator",
        createdAt: now,
        attempted: 4,
        refreshed: 2,
        failed: 1,
        skipped: 1,
        categories: ["network"],
        spanId: "span-retry-1",
        alertIds: [],
        notes: ["aurora-shop:search_console -> error (SEARCH_CONSOLE_REQUEST_TIMEOUT)"],
      },
    ],
  };
}

export function fallbackBulkConnectorActionHistoryReport(): BulkConnectorActionHistoryReport {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    total: 2,
    entries: [
      {
        auditId: "audit-bulk-blocking-1",
        action: "connectors.bulk.blocking.refreshed",
        createdAt: now,
        actor: "system",
        providerCount: 2,
        providers: ["search_console", "github"],
        refreshedCount: 3,
        skippedProjectCount: 1,
        projectScopeCount: 3,
        projectIds: ["project_aurora", "project_sparkr", "project_harbor"],
        maxProviders: 5,
        spanId: "span-bulk-blocking-1",
        traceId: "trace-bulk-blocking-1",
      },
      {
        auditId: "audit-bulk-strict-gap-1",
        action: "connectors.bulk.strict_gap.refreshed",
        createdAt: now,
        actor: "system",
        providerCount: 1,
        providers: ["ga4"],
        refreshedCount: 2,
        skippedProjectCount: 0,
        projectScopeCount: 2,
        projectIds: ["project_aurora", "project_sparkr"],
        maxProviders: 5,
        spanId: "span-bulk-strict-gap-1",
        traceId: "trace-bulk-strict-gap-1",
      },
    ],
  };
}

export function fallbackVisualRegressionRetryHistoryReport(): VisualRegressionRetryHistoryReport {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    entries: [
      {
        auditId: "audit-visual-retry-1",
        actor: "operator",
        createdAt: now,
        attempted: 3,
        rerunPassed: 2,
        rerunFailed: 1,
        skipped: 4,
        categories: ["network", "unavailable"],
        runId: "visual-run-fallback-1",
        spanId: "span-visual-retry-1",
        notes: ["Selected 3 visual regression cases for retry."],
      },
    ],
  };
}

export function fallbackWorkspaceConnectorsHealthReport(): WorkspaceConnectorsHealthReport {
  const projects = fallbackDashboard.projects.map((project) => {
    const connections = sampleConnections(project.projectId, project.siteClass);
    const realConnectionCount = connections.filter((item) => item.providerMode === "real").length;
    const fallbackConnectionCount = connections.filter((item) => item.providerMode === "fallback").length;
    const unconfiguredConnectionCount = connections.filter((item) => item.providerMode === "unconfigured").length;
    const strictEligibleCount = connections.filter((item) => item.strictEligible).length;
    return {
      projectId: project.projectId,
      name: project.name,
      url: project.url,
      checkedAt: project.updatedAt,
      connectionHealth: project.connectionHealth ?? "unknown",
      totalConnectionCount: connections.length,
      realConnectionCount,
      fallbackConnectionCount,
      unconfiguredConnectionCount,
      strictEligibleCount,
      issueCount: fallbackConnectionCount + unconfiguredConnectionCount,
      issues: connections
        .filter((item) => item.blockingReason)
        .map((item) => `${item.label}: ${item.blockingReason}`),
    };
  });
  const readProviders = new Set<ConnectorKind>(["search_console", "ga4", "ad_network", "sitemap", "playwright", "trend", "news", "qa"]);
  const writeProviders = new Set<ConnectorKind>(["github", "cms", "script_api"]);
  let readConnectionCount = 0;
  let readRealConnectionCount = 0;
  let readStrictEligibleCount = 0;
  let readRealLastEvidenceAt: string | null = null;
  let writeConnectionCount = 0;
  let writeRealConnectionCount = 0;
  let writeStrictEligibleCount = 0;
  let writeRealLastEvidenceAt: string | null = null;
  const providerMap = new Map<ConnectorKind, ConnectorProviderCoverageItem>();
  for (const project of fallbackDashboard.projects) {
    for (const connection of sampleConnections(project.projectId, project.siteClass)) {
      if (readProviders.has(connection.provider)) {
        readConnectionCount += 1;
        if (connection.providerMode === "real") {
          readRealConnectionCount += 1;
          if (connection.recentEvidenceAt && (!readRealLastEvidenceAt || connection.recentEvidenceAt > readRealLastEvidenceAt)) {
            readRealLastEvidenceAt = connection.recentEvidenceAt;
          }
        }
        if (connection.strictEligible) readStrictEligibleCount += 1;
      } else if (writeProviders.has(connection.provider)) {
        writeConnectionCount += 1;
        if (connection.providerMode === "real") {
          writeRealConnectionCount += 1;
          if (connection.recentEvidenceAt && (!writeRealLastEvidenceAt || connection.recentEvidenceAt > writeRealLastEvidenceAt)) {
            writeRealLastEvidenceAt = connection.recentEvidenceAt;
          }
        }
        if (connection.strictEligible) writeStrictEligibleCount += 1;
      }
      const current = providerMap.get(connection.provider) ?? {
        provider: connection.provider,
        totalConnectionCount: 0,
        affectedProjectCount: 0,
        strictReadyProjectCount: 0,
        strictReadyProjectRatePercent: 0,
        blockingProjectCount: 0,
        blockingProjectRatePercent: 0,
        strictGapCount: 0,
        realCoveragePercent: 0,
        strictCoveragePercent: 0,
        blockingRatePercent: 0,
        affectedProjectIds: [],
        strictReadyProjectIds: [],
        blockingProjectIds: [],
        affectedProjects: [],
        strictReadyProjects: [],
        blockingProjects: [],
        primaryFailureCategory: null,
        primaryFailureCode: null,
        primaryBlockingReason: null,
        suggestedActionPath: "/monitor",
        suggestedActionLabel: "Open monitor",
        realConnectionCount: 0,
        fallbackConnectionCount: 0,
        unconfiguredConnectionCount: 0,
        strictEligibleCount: 0,
        antiBotBlockedCount: 0,
        manualInterventionRequiredCount: 0,
      };
      current.totalConnectionCount += 1;
      current.affectedProjectCount += 1;
      if (!current.affectedProjectIds.includes(project.projectId)) current.affectedProjectIds.push(project.projectId);
      if (!current.affectedProjects.some((item) => item.projectId === project.projectId)) {
        current.affectedProjects.push({ projectId: project.projectId, name: project.name, url: project.url });
      }
      if (connection.providerMode === "real") current.realConnectionCount += 1;
      else if (connection.providerMode === "fallback") current.fallbackConnectionCount += 1;
      else current.unconfiguredConnectionCount += 1;
      if (Boolean(connection.details?.antiBotBlocked)) current.antiBotBlockedCount += 1;
      if (Boolean(connection.details?.manualInterventionRequired)) current.manualInterventionRequiredCount += 1;
      if (connection.strictEligible) {
        current.strictEligibleCount += 1;
        current.strictReadyProjectCount += 1;
        if (!current.strictReadyProjectIds.includes(project.projectId)) current.strictReadyProjectIds.push(project.projectId);
        if (!current.strictReadyProjects.some((item) => item.projectId === project.projectId)) {
          current.strictReadyProjects.push({ projectId: project.projectId, name: project.name, url: project.url });
        }
      } else {
        current.strictGapCount += 1;
        current.blockingProjectCount += 1;
        if (!current.blockingProjectIds.includes(project.projectId)) current.blockingProjectIds.push(project.projectId);
        if (!current.blockingProjects.some((item) => item.projectId === project.projectId)) {
          current.blockingProjects.push({ projectId: project.projectId, name: project.name, url: project.url });
        }
        current.primaryFailureCategory ||= "config";
        current.primaryFailureCode ||= String(connection.details?.errorCode ?? "");
        current.primaryBlockingReason ||= String(connection.blockingReason ?? connection.details?.fallbackReason ?? "");
        current.suggestedActionPath ||= `/settings?focus=connector&provider=${connection.provider}`;
        current.suggestedActionLabel ||= "Open settings";
      }
      providerMap.set(connection.provider, current);
    }
  }
  return {
    generatedAt: new Date().toISOString(),
    projectCount: projects.length,
    degradedProjectCount: projects.filter((item) => item.connectionHealth === "degraded").length,
    unavailableProjectCount: projects.filter((item) => item.connectionHealth === "unavailable").length,
    totalConnectionCount: projects.reduce((sum, item) => sum + item.totalConnectionCount, 0),
    realConnectionCount: projects.reduce((sum, item) => sum + item.realConnectionCount, 0),
    fallbackConnectionCount: projects.reduce((sum, item) => sum + item.fallbackConnectionCount, 0),
    unconfiguredConnectionCount: projects.reduce((sum, item) => sum + item.unconfiguredConnectionCount, 0),
    strictEligibleCount: projects.reduce((sum, item) => sum + item.strictEligibleCount, 0),
    strictGapCount: projects.reduce((sum, item) => sum + (item.totalConnectionCount - item.strictEligibleCount), 0),
    antiBotBlockedConnectionCount: fallbackDashboard.projects.reduce(
      (sum, project) => sum + sampleConnections(project.projectId, project.siteClass).filter((item) => Boolean(item.details?.antiBotBlocked)).length,
      0,
    ),
    antiBotManualInterventionCount: fallbackDashboard.projects.reduce(
      (sum, project) =>
        sum + sampleConnections(project.projectId, project.siteClass).filter((item) => Boolean(item.details?.manualInterventionRequired)).length,
      0,
    ),
    readConnectionCount,
    readRealConnectionCount,
    readStrictEligibleCount,
    readRealCoveragePercent: readConnectionCount ? Number(((readRealConnectionCount / readConnectionCount) * 100).toFixed(1)) : 0,
    readStrictCoveragePercent: readConnectionCount ? Number(((readStrictEligibleCount / readConnectionCount) * 100).toFixed(1)) : 0,
    readRealLastEvidenceAt,
    writeConnectionCount,
    writeRealConnectionCount,
    writeStrictEligibleCount,
    writeRealCoveragePercent: writeConnectionCount ? Number(((writeRealConnectionCount / writeConnectionCount) * 100).toFixed(1)) : 0,
    writeStrictCoveragePercent: writeConnectionCount ? Number(((writeStrictEligibleCount / writeConnectionCount) * 100).toFixed(1)) : 0,
    writeRealLastEvidenceAt,
    realProviderCount: Array.from(providerMap.values()).filter((item) => item.realConnectionCount > 0).length,
    realProviderRatePercent: Array.from(providerMap.values()).length
      ? Number(((Array.from(providerMap.values()).filter((item) => item.realConnectionCount > 0).length / Array.from(providerMap.values()).length) * 100).toFixed(1))
      : 0,
    zeroRealProviderCount: Array.from(providerMap.values()).filter((item) => item.realConnectionCount === 0).length,
    zeroRealProviderRatePercent: Array.from(providerMap.values()).length
      ? Number(((Array.from(providerMap.values()).filter((item) => item.realConnectionCount === 0).length / Array.from(providerMap.values()).length) * 100).toFixed(1))
      : 0,
    zeroRealProviders: Array.from(providerMap.values()).filter((item) => item.realConnectionCount === 0).map((item) => item.provider),
    zeroStrictProviderCount: Array.from(providerMap.values()).filter((item) => item.strictEligibleCount === 0).length,
    zeroStrictProviderRatePercent: Array.from(providerMap.values()).length
      ? Number(((Array.from(providerMap.values()).filter((item) => item.strictEligibleCount === 0).length / Array.from(providerMap.values()).length) * 100).toFixed(1))
      : 0,
    zeroStrictProviders: Array.from(providerMap.values()).filter((item) => item.strictEligibleCount === 0).map((item) => item.provider),
    strictReadyProviderCount: Array.from(providerMap.values()).filter((item) => item.strictReadyProjectCount > 0).length,
    strictReadyProviderRatePercent: Array.from(providerMap.values()).length
      ? Number(((Array.from(providerMap.values()).filter((item) => item.strictReadyProjectCount > 0).length / Array.from(providerMap.values()).length) * 100).toFixed(1))
      : 0,
    strictReadyProviders: Array.from(providerMap.values()).filter((item) => item.strictReadyProjectCount > 0).map((item) => item.provider),
    partialStrictProviderCount: Array.from(providerMap.values()).filter(
      (item) => item.strictReadyProjectCount > 0 && !(item.totalConnectionCount > 0 && item.strictEligibleCount === item.totalConnectionCount),
    ).length,
    partialStrictProviderRatePercent: Array.from(providerMap.values()).length
      ? Number(
          (
            (Array.from(providerMap.values()).filter(
              (item) => item.strictReadyProjectCount > 0 && !(item.totalConnectionCount > 0 && item.strictEligibleCount === item.totalConnectionCount),
            ).length /
              Array.from(providerMap.values()).length) *
            100
          ).toFixed(1),
        )
      : 0,
    partialStrictProviders: Array.from(providerMap.values())
      .filter((item) => item.strictReadyProjectCount > 0 && !(item.totalConnectionCount > 0 && item.strictEligibleCount === item.totalConnectionCount))
      .map((item) => item.provider),
    fullyStrictProviderCount: Array.from(providerMap.values()).filter(
      (item) => item.totalConnectionCount > 0 && item.strictEligibleCount === item.totalConnectionCount,
    ).length,
    fullyStrictProviderRatePercent: Array.from(providerMap.values()).length
      ? Number(
          (
            (Array.from(providerMap.values()).filter(
              (item) => item.totalConnectionCount > 0 && item.strictEligibleCount === item.totalConnectionCount,
            ).length /
              Array.from(providerMap.values()).length) *
            100
          ).toFixed(1),
        )
      : 0,
    fullyStrictProviders: Array.from(providerMap.values())
      .filter((item) => item.totalConnectionCount > 0 && item.strictEligibleCount === item.totalConnectionCount)
      .map((item) => item.provider),
    providerCoverage: Array.from(providerMap.values())
      .map((item) => ({
        ...item,
        strictReadyProjectRatePercent: item.affectedProjectCount
          ? Number(((item.strictReadyProjectCount / item.affectedProjectCount) * 100).toFixed(1))
          : 0,
        blockingProjectRatePercent: item.affectedProjectCount
          ? Number(((item.blockingProjectCount / item.affectedProjectCount) * 100).toFixed(1))
          : 0,
        realCoveragePercent: item.totalConnectionCount ? Number(((item.realConnectionCount / item.totalConnectionCount) * 100).toFixed(1)) : 0,
        strictCoveragePercent: item.totalConnectionCount ? Number(((item.strictEligibleCount / item.totalConnectionCount) * 100).toFixed(1)) : 0,
        blockingRatePercent: item.affectedProjectCount ? Number(((item.blockingProjectCount / item.affectedProjectCount) * 100).toFixed(1)) : 0,
      }))
      .sort((a, b) => a.provider.localeCompare(b.provider)),
    topBlockingProviders: Array.from(providerMap.values())
      .sort((a, b) => b.blockingProjectCount - a.blockingProjectCount || b.unconfiguredConnectionCount - a.unconfiguredConnectionCount || a.provider.localeCompare(b.provider))
      .slice(0, 5),
    topStrictGapProviders: Array.from(providerMap.values())
      .sort((a, b) => b.strictGapCount - a.strictGapCount || b.blockingProjectCount - a.blockingProjectCount || a.provider.localeCompare(b.provider))
      .slice(0, 5),
    topStrictReadyProviders: Array.from(providerMap.values())
      .sort((a, b) => b.strictCoveragePercent - a.strictCoveragePercent || b.strictEligibleCount - a.strictEligibleCount || a.provider.localeCompare(b.provider))
      .slice(0, 5),
    projects,
  };
}

export function fallbackProjectConnectionHistoryReport(projectId: string): ProjectConnectionHistoryReport {
  const now = new Date().toISOString();
  return {
    projectId,
    generatedAt: now,
    entries: [
      {
        auditId: `${projectId}-probe-1`,
        provider: "search_console",
        action: "connector.probe",
        status: "connected",
        summary: "Search Console probe completed.",
        authSource: "env",
        latencyMs: 182,
        retryable: false,
        provenance: ["fallback", "endpoint=sample"],
        actor: "system",
        createdAt: now,
      },
      {
        auditId: `${projectId}-probe-2`,
        provider: "cms",
        action: "connector.refreshed",
        status: "synthetic",
        summary: "CMS connector fell back to synthetic mode.",
        authSource: "fallback",
        failureCode: "CMS_PERMISSION_DENIED",
        fallbackReason: "Fallback mode active",
        latencyMs: 241,
        retryable: true,
        provenance: ["fallback", "mode=synthetic"],
        actor: "system",
        createdAt: now,
      },
    ],
  };
}

export function fallbackProjectConnectionEvidenceReport(projectId: string): ProjectConnectionEvidenceReport {
  const detail = fallbackProjectDetail(projectId);
  const entries = detail.connections.map((connection) => ({
    provider: connection.provider,
    label: connection.label,
    status: connection.status,
    providerMode: connection.providerMode,
    strictEligible: connection.strictEligible,
    authSource: typeof connection.details?.authSource === "string" ? connection.details.authSource : null,
    fallbackReason: typeof connection.details?.fallbackReason === "string" ? connection.details.fallbackReason : null,
    latencyMs: typeof connection.details?.latencyMs === "number" ? connection.details.latencyMs : null,
    recentEvidenceLabel: connection.recentEvidenceLabel ?? null,
    recentEvidenceRef: connection.recentEvidenceRef ?? null,
    recentEvidenceAt: connection.recentEvidenceAt ?? null,
    lastSuccessAt: connection.lastSuccessAt ?? null,
    lastErrorAt: connection.lastErrorAt ?? null,
  }));
  return {
    projectId,
    generatedAt: new Date().toISOString(),
    total: entries.length,
    realCount: entries.filter((item) => item.providerMode === "real").length,
    fallbackCount: entries.filter((item) => item.providerMode === "fallback").length,
    unconfiguredCount: entries.filter((item) => item.providerMode === "unconfigured").length,
    entries,
  };
}

export function fallbackProjectConnectorsHealth(projectId: string): ConnectorsHealthResult {
  const detail = fallbackProjectDetail(projectId);
  const connections = detail.connections;
  const readProviders = new Set<ConnectorKind>(["search_console", "ga4", "ad_network", "sitemap", "playwright", "trend", "news", "qa"]);
  const writeProviders = new Set<ConnectorKind>(["github", "cms", "script_api"]);
  const readRealEvidenceTimes = connections
    .filter((item) => item.providerMode === "real" && readProviders.has(item.provider) && item.recentEvidenceAt)
    .map((item) => String(item.recentEvidenceAt))
    .sort();
  const writeRealEvidenceTimes = connections
    .filter((item) => item.providerMode === "real" && writeProviders.has(item.provider) && item.recentEvidenceAt)
    .map((item) => String(item.recentEvidenceAt))
    .sort();
  return {
    projectId,
    checkedAt: new Date().toISOString(),
    connectionHealth: detail.state.connectionHealth,
    totalConnectionCount: connections.length,
    realConnectionCount: connections.filter((item) => item.providerMode === "real").length,
    fallbackConnectionCount: connections.filter((item) => item.providerMode === "fallback").length,
    unconfiguredConnectionCount: connections.filter((item) => item.providerMode === "unconfigured").length,
    strictEligibleCount: connections.filter((item) => item.strictEligible).length,
    antiBotBlockedCount: connections.filter((item) => Boolean(item.details?.antiBotBlocked)).length,
    manualInterventionRequiredCount: connections.filter((item) => Boolean(item.details?.manualInterventionRequired)).length,
    readRealLastEvidenceAt: readRealEvidenceTimes.at(-1) ?? null,
    writeRealLastEvidenceAt: writeRealEvidenceTimes.at(-1) ?? null,
    connections,
    issues: connections
      .filter((item) => item.blockingReason)
      .map((item) => `${item.label}: ${item.blockingReason}`),
  };
}

export function fallbackWorkspaceConnectionHistoryReport(): WorkspaceConnectionHistoryReport {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    entries: [
      {
        auditId: "workspace-probe-1",
        projectId: "project_demo",
        taskId: "task_demo",
        provider: "search_console",
        action: "connector.probe",
        status: "connected",
        summary: "Search Console probe completed.",
        authSource: "env",
        latencyMs: 182,
        retryable: false,
        provenance: ["fallback", "endpoint=sample"],
        actor: "system",
        createdAt: now,
      },
      {
        auditId: "workspace-probe-2",
        projectId: "project_demo",
        taskId: "task_demo",
        provider: "cms",
        action: "connector.refreshed",
        status: "synthetic",
        summary: "CMS connector fell back to synthetic mode.",
        authSource: "fallback",
        failureCode: "CMS_PERMISSION_DENIED",
        fallbackReason: "Fallback mode active",
        latencyMs: 241,
        retryable: true,
        provenance: ["fallback", "mode=synthetic"],
        actor: "system",
        createdAt: now,
      },
    ],
  };
}

export function fallbackWorkspaceConnectionEvidenceReport(): WorkspaceConnectionEvidenceReport {
  const details = fallbackProjects.map((project) => fallbackProjectConnectionEvidenceReport(project.project.projectId));
  const entries = details.flatMap((report) =>
    report.entries.map((entry) => ({
      projectId: report.projectId,
      projectName: fallbackProjects.find((item) => item.project.projectId === report.projectId)?.project.name ?? report.projectId,
      projectUrl: fallbackProjects.find((item) => item.project.projectId === report.projectId)?.project.url ?? "https://example.com",
      ...entry,
    })),
  );
  return {
    generatedAt: new Date().toISOString(),
    total: entries.length,
    realCount: entries.filter((item) => item.providerMode === "real").length,
    fallbackCount: entries.filter((item) => item.providerMode === "fallback").length,
    unconfiguredCount: entries.filter((item) => item.providerMode === "unconfigured").length,
    entries,
    providerSummaries: Array.from(new Set(entries.map((item) => item.provider))).map((provider) => {
      const items = entries.filter((entry) => entry.provider === provider);
      const latest = items
        .filter((entry) => entry.recentEvidenceAt)
        .sort((a, b) => new Date(b.recentEvidenceAt ?? 0).getTime() - new Date(a.recentEvidenceAt ?? 0).getTime())[0];
      return {
        provider,
        total: items.length,
        realCount: items.filter((item) => item.providerMode === "real").length,
        fallbackCount: items.filter((item) => item.providerMode === "fallback").length,
        unconfiguredCount: items.filter((item) => item.providerMode === "unconfigured").length,
        projectCount: new Set(items.map((item) => item.projectId)).size,
        recentEvidenceLabel: latest?.recentEvidenceLabel ?? null,
        recentEvidenceRef: latest?.recentEvidenceRef ?? null,
        recentEvidenceAt: latest?.recentEvidenceAt ?? null,
      };
    }),
  };
}

export function fallbackConnectorRemediationReport(): ConnectorRemediationReport {
  return {
    reportId: "conn-remediate-fallback",
    generatedAt: new Date().toISOString(),
    itemCount: 3,
    items: [
      {
        remediationId: "remediate-1",
        failureCode: "CONFIG_MISSING_ACCESS_TOKEN",
        category: "config",
        priority: "p0",
        action: "Open settings and complete missing connector credentials/config fields.",
        rationale: "Configuration blockers are deterministic and cannot be fixed via retry.",
        target: "settings",
        quickActionPath: "/settings?focus=connector&code=CONFIG_MISSING_ACCESS_TOKEN&provider=search_console",
        quickActionLabel: "Open settings",
        retryAfterMinutes: null,
        affectedProjects: 2,
        projectIds: ["aurora-shop", "northstar-media"],
        providers: ["search_console", "ga4"],
        blocking: true,
        alertSeverity: "critical",
      },
      {
        remediationId: "remediate-2",
        failureCode: "SEARCH_CONSOLE_REQUEST_TIMEOUT",
        category: "network",
        priority: "p1",
        action: "Run batch retry for retryable connectors and verify network reachability.",
        rationale: "Timeouts are commonly transient and often recover on delayed retry.",
        target: "monitor",
        quickActionPath: "/monitor?focus=retry&category=network&code=SEARCH_CONSOLE_REQUEST_TIMEOUT",
        quickActionLabel: "Retry now",
        retryAfterMinutes: 10,
        affectedProjects: 1,
        projectIds: ["aurora-shop"],
        providers: ["search_console"],
        blocking: false,
        alertSeverity: "warning",
      },
      {
        remediationId: "remediate-3",
        failureCode: "CMS_PERMISSION_DENIED",
        category: "permission",
        priority: "p0",
        action: "Grant required provider scopes and workspace permissions for the connector.",
        rationale: "Permission failures require external provider policy updates.",
        target: "provider",
        quickActionPath: "/settings?focus=provider-access&code=CMS_PERMISSION_DENIED&provider=cms",
        quickActionLabel: "Review provider access",
        retryAfterMinutes: null,
        affectedProjects: 1,
        projectIds: ["trust-clinic"],
        providers: ["cms"],
        blocking: true,
        alertSeverity: "critical",
      },
    ],
    notes: ["Fallback remediation report."],
  };
}

export function fallbackWorkerQueueHealthReport(): WorkerQueueHealthReport {
  return {
    generatedAt: new Date().toISOString(),
    backend: "memory",
    backendConnected: true,
    backendProbeLatencyMs: 0,
    backendProbeFailureCode: null,
    backendProbeError: null,
    queueDepth: 1,
    total: 4,
    queued: 1,
    claimed: 1,
    completed: 1,
    failed: 1,
    oldestReadyAt: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    stageStats: [
      { stage: "sync", total: 1, queued: 0, claimed: 0, completed: 1, failed: 0 },
      { stage: "deploy", total: 1, queued: 0, claimed: 0, completed: 0, failed: 1 },
      { stage: "monitor", total: 1, queued: 0, claimed: 1, completed: 0, failed: 0 },
      { stage: "rollback", total: 1, queued: 1, claimed: 0, completed: 0, failed: 0 },
    ],
    notes: ["Fallback worker queue health report."],
  };
}

export function fallbackWorkerExecutionHistoryReport(): WorkerExecutionHistoryReport {
  const now = new Date().toISOString();
  return {
    total: 5,
    entries: [
      {
        auditId: "audit-worker-enqueued",
        projectId: "aurora-shop",
        taskId: "aurora-shop-task",
        action: "worker.job.enqueued",
        status: "queued",
        stage: "deploy",
        jobId: "job_deploy_001",
        attempt: 0,
        actor: "worker",
        createdAt: now,
        traceId: "trace-worker-001",
      },
      {
        auditId: "audit-worker-completed",
        projectId: "aurora-shop",
        taskId: "aurora-shop-task",
        action: "worker.job.completed",
        status: "completed",
        stage: "deploy",
        jobId: "job_deploy_001",
        attempt: 0,
        actor: "worker",
        createdAt: now,
      },
      {
        auditId: "audit-worker-failed",
        projectId: "northstar-media",
        taskId: "northstar-media-task",
        action: "worker.job.failed",
        status: "failed",
        stage: "monitor",
        jobId: "job_monitor_003",
        attempt: 1,
        failureCode: "WORKER_TIMEOUT",
        error: "provider timeout during monitor step",
        actor: "worker",
        createdAt: now,
      },
      {
        auditId: "audit-worker-requeued",
        projectId: "northstar-media",
        taskId: "northstar-media-task",
        action: "worker.job.requeued",
        status: "requeued",
        stage: "monitor",
        jobId: "job_monitor_004",
        attempt: 2,
        retryDelaySeconds: 30,
        failureCode: "WORKER_TIMEOUT",
        actor: "worker",
        createdAt: now,
      },
      {
        auditId: "audit-worker-skipped-duplicate",
        projectId: "trust-clinic",
        taskId: "trust-clinic-task",
        action: "worker.job.skipped_duplicate",
        status: "skipped_duplicate",
        stage: "rollback",
        jobId: "job_rollback_009",
        attempt: 0,
        actor: "worker",
        createdAt: now,
      },
    ],
  };
}

export function fallbackWorkerServiceHealthReport(): WorkerServiceHealthReport {
  return {
    generatedAt: new Date().toISOString(),
    stateFileConfigured: false,
    stateFilePath: null,
    stateFileFound: false,
    status: "unknown",
    startedAt: null,
    lastTickAt: null,
    failures: 0,
    processed: 0,
    enqueued: 0,
    claimed: 0,
    skippedDuplicates: 0,
    dueProjects: 0,
    targets: [],
    lastError: null,
    notes: ["Configure SEO_AD_BOT_WORKER_STATE_FILE to view worker service status."],
  };
}

export function fallbackObservabilityStatusReport(): ObservabilityStatusReport {
  return {
    generatedAt: new Date().toISOString(),
    enableOtlp: false,
    otlpEndpointConfigured: false,
    sentryDsnConfigured: false,
    observabilityStrict: false,
    tracingBackend: "disabled",
    otlpExporterAvailable: false,
    notes: ["Fallback observability status used when the API is unavailable."],
  };
}

export function fallbackAlertReport(): AlertReport {
  const remediations = fallbackConnectorRemediationReport();
  const blocking = remediations.items
    .filter((item) => item.blocking)
    .map((item, index) => ({
      alertId: `alert-blocking-${index + 1}`,
      createdAt: new Date().toISOString(),
      category: item.category,
      severity: item.alertSeverity ?? "critical",
      blocking: true,
      failureCode: item.failureCode,
      provider: item.providers[0] ?? "unknown",
      projectCount: item.affectedProjects,
      projectIds: item.projectIds,
      summary: item.action,
      remediationPath: item.quickActionPath,
    }));
  const recoverable = remediations.items
    .filter((item) => !item.blocking)
    .map((item, index) => ({
      alertId: `alert-recoverable-${index + 1}`,
      createdAt: new Date().toISOString(),
      category: item.category,
      severity: item.alertSeverity ?? "warning",
      blocking: false,
      failureCode: item.failureCode,
      provider: item.providers[0] ?? "unknown",
      projectCount: item.affectedProjects,
      projectIds: item.projectIds,
      summary: item.action,
      remediationPath: item.quickActionPath,
    }));
  return {
    reportId: "alerts-fallback",
    generatedAt: new Date().toISOString(),
    blocking,
    recoverable,
    notes: ["Fallback alert queues generated from fallback remediations."],
  };
}

export function fallbackAlertDeliveryReport(): AlertDeliveryReport {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    total: 2,
    sent: 1,
    failed: 1,
    entries: [
      {
        auditId: "audit-alert-delivery-1",
        createdAt: now,
        status: "sent",
        route: "all",
        target: "file:///tmp/alerts-webhook.ndjson",
        channel: "file",
        reportId: "alerts-fallback",
        blockingCount: 1,
        recoverableCount: 1,
        statusCode: 200,
        error: null,
        spanId: "span-delivery-1",
        traceId: "trace-delivery-1",
      },
      {
        auditId: "audit-alert-delivery-2",
        createdAt: now,
        status: "failed",
        route: "oncall:default:primary",
        target: "https://alerts.example/hooks/oncall",
        channel: "http",
        reportId: "alerts-fallback",
        blockingCount: 1,
        recoverableCount: 0,
        statusCode: null,
        error: "fallback simulated network error",
        spanId: "span-delivery-2",
        traceId: "trace-delivery-2",
      },
    ],
  };
}

export function fallbackAlertEmitStatusReport(): AlertEmitStatusReport {
  return {
    generatedAt: new Date().toISOString(),
    cooldownSeconds: 0,
    executedCount24h: 0,
    suppressedCount24h: 0,
    lastExecutedAt: null,
    lastSuppressedAt: null,
    lastSignature: null,
    notes: ["Fallback alert emit status used when the API is unavailable."],
  };
}

export function fallbackAlertEmitHistoryReport(): AlertEmitHistoryReport {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    total: 1,
    executed: 1,
    suppressed: 0,
    entries: [
      {
        auditId: "audit-alert-emit-history-1",
        createdAt: now,
        status: "executed",
        signature: "fallback-signature",
        cooldownSeconds: 0,
        blockingCount: 1,
        recoverableCount: 1,
        spanId: "span-alert-emit-1",
        traceId: "trace-alert-emit-1",
      },
    ],
  };
}

export function fallbackAlertPresetCollection(): AlertPresetCollection {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    presets: [
      {
        presetId: "blocking_critical",
        name: "blocking_critical",
        description: "Critical blocking alerts only.",
        projectIds: [],
        categories: [],
        severities: ["critical"],
        providers: [],
        blocking: true,
        updatedAt: now,
      },
      {
        presetId: "auth_config",
        name: "auth_config",
        description: "Auth/config blockers.",
        projectIds: [],
        categories: ["auth", "config"],
        severities: [],
        providers: [],
        blocking: true,
        updatedAt: now,
      },
      {
        presetId: "network_recoverable",
        name: "network_recoverable",
        description: "Recoverable network/rate-limit alerts.",
        projectIds: [],
        categories: ["network", "rate_limit"],
        severities: [],
        providers: [],
        blocking: false,
        updatedAt: now,
      },
    ],
  };
}

export function fallbackAlertRuleCollection(): AlertRuleCollection {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    rules: [
      {
        ruleId: "blocking_critical",
        enabled: true,
        description: "Escalate critical blocking alerts.",
        categories: [],
        failureCodes: [],
        providers: [],
        setBlocking: true,
        setSeverity: "critical",
        priority: 10,
        updatedAt: now,
      },
      {
        ruleId: "network_retryable",
        enabled: true,
        description: "Mark network and rate limit alerts as recoverable.",
        categories: ["network", "rate_limit"],
        failureCodes: [],
        providers: [],
        setBlocking: false,
        setSeverity: "warning",
        priority: 20,
        updatedAt: now,
      },
    ],
  };
}

export function fallbackOnCallPolicyCollection(): OnCallPolicyCollection {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    routes: [
      {
        routeId: "blocking_primary",
        enabled: true,
        description: "Blocking alerts to primary on-call.",
        categories: [],
        severities: ["critical"],
        providers: [],
        blocking: true,
        primaryChannels: ["file:///tmp/alerts-oncall-primary.ndjson"],
        escalationChannels: ["file:///tmp/alerts-oncall-escalation.ndjson"],
        escalationAfterMinutes: 15,
        rotationMembers: ["alice", "bob", "carol"],
        rotationTimezone: "UTC",
        rotationHandoffHour: 9,
        updatedAt: now,
      },
    ],
    notes: ["Fallback on-call policy."],
  };
}

export function fallbackOnCallCoverageReport(): OnCallCoverageReport {
  const now = new Date();
  const next = new Date(now.getTime() + 8 * 60 * 60 * 1000);
  return {
    generatedAt: now.toISOString(),
    routeCount: 2,
    rotatingRouteCount: 1,
    items: [
      {
        routeId: "blocking_primary",
        enabled: true,
        rotationEnabled: true,
        rotationTimezone: "UTC",
        rotationHandoffHour: 9,
        memberCount: 3,
        currentMember: "alice",
        nextMember: "bob",
        nextHandoffAt: next.toISOString(),
      },
      {
        routeId: "recoverable_primary",
        enabled: true,
        rotationEnabled: false,
        rotationTimezone: "UTC",
        rotationHandoffHour: 9,
        memberCount: 0,
        currentMember: null,
        nextMember: null,
        nextHandoffAt: null,
      },
    ],
  };
}

export function fallbackProjectDetail(projectId: string): ProjectDetail {
  const pick = fallbackProjects.find((item) => item.project.projectId === projectId) ?? fallbackProjects[0];
  return {
    project: pick.project,
    workflow: pick,
    state: sampleState(pick.project.projectId, pick.project.siteClass),
    connections: sampleConnections(pick.project.projectId, pick.project.siteClass),
    experimentAssignment: pick.experimentAssignment,
    deploymentHistory: [
      {
        deployment:
          pick.deployment ?? {
            deploymentId: `${projectId}-deployment-live`,
            taskId: pick.task.taskId,
            mode: pick.plan.deploymentMode,
            status: "scheduled" as const,
            artifactRef: pick.preview.previewId,
            releaseNotes: [],
            rollbackReady: false,
          },
        taskStatus: pick.task.status,
        approvalStatus: pick.task.approvalStatus,
        updatedAt: pick.task.updatedAt,
        rollbackId: pick.rollbackBundle?.rollbackId ?? null,
      },
      {
        deployment: {
          deploymentId: `${projectId}-deployment-previous`,
          taskId: `${pick.task.taskId}-previous`,
          mode: pick.plan.deploymentMode,
          status: "deployed",
          artifactRef: `${pick.preview.previewId}-previous`,
          releaseNotes: ["Fallback previous deployment record."],
          rollbackReady: true,
          providerArtifactId: `${projectId}-provider-previous`,
          providerUrl: `https://deployments.example/${projectId}/previous`,
          writebackAuthSource: "fallback",
          writebackSummary: {
            provider: "fallback",
            successCount: 1,
            failedCount: 0,
            skippedCount: 0,
            lastEndpoint: "fallback://history",
            successfulEndpoints: ["fallback://history"],
            failedEndpoints: [],
            averageLatencyMs: 180,
          },
        },
        taskStatus: "deployed",
        approvalStatus: "approved",
        updatedAt: new Date(Date.now() - 86400000).toISOString(),
        rollbackId: `${projectId}-rollback-previous`,
      },
    ],
    rollbackHistory: [
      {
        rollback: {
          rollbackId: `${projectId}-rollback-live`,
          deploymentId: pick.deployment?.deploymentId ?? `${projectId}-deployment-live`,
          commands: ["git revert fallback-release", "re-publish fallback snapshot"],
          safeWindowMinutes: 10,
          reason: "Fallback rollback history sample.",
          expectedEffect: "Restore the previous stable preview.",
        },
        taskId: pick.task.taskId,
        taskStatus: "rolled_back",
        approvalStatus: "approved",
        updatedAt: pick.task.updatedAt,
      },
    ],
    runs: sampleRuns(pick.project.projectId, pick.project.siteClass),
    audits: [
      {
        id: `${projectId}-audit-1`,
        actor: "fallback",
        action: "analysis.completed",
        payload: { source: "fallback" },
        createdAt: new Date().toISOString(),
      },
    ],
    businessClassifier: {
      reportId: `${projectId}-classifier`,
      siteId: pick.project.projectId,
      inferredVertical: pick.project.siteClass,
      brandVoice: "fallback",
      matchedRules: [],
      signals: ["fallback"],
      notes: ["Fallback business classifier report."],
    },
    styleExtraction: {
      reportId: `${projectId}-style`,
      projectId,
      siteId: pick.project.projectId,
      brandVoice: "fallback",
      tone: "direct",
      density: "balanced",
      trustLevel: pick.project.siteClass === "ymyl" ? "high" : "medium",
      tokens: [],
      moduleGuidance: ["Fallback style extraction report."],
      notes: ["Fallback style extraction report."],
    },
    marketEvidence: {
      reportId: `${projectId}-market`,
      projectId,
      generatedAt: new Date().toISOString(),
      trend: [
        {
          provider: "trend",
          status: "synthetic",
          summary: "Fallback trend evidence.",
          provenance: ["fallback"],
          details: { topic: "fallback" },
          sourceType: "trend",
          sourceRef: "fallback-trend",
          fetchedAt: new Date().toISOString(),
          retryable: false,
          checkedAt: new Date().toISOString(),
        },
      ],
      news: [
        {
          provider: "news",
          status: "synthetic",
          summary: "Fallback news evidence.",
          provenance: ["fallback"],
          details: { topic: "fallback" },
          sourceType: "news",
          sourceRef: "fallback-news",
          fetchedAt: new Date().toISOString(),
          retryable: false,
          checkedAt: new Date().toISOString(),
        },
      ],
      qa: [
        {
          provider: "qa",
          status: "synthetic",
          summary: "Fallback QA evidence.",
          provenance: ["fallback"],
          details: { topic: "fallback" },
          sourceType: "qa",
          sourceRef: "fallback-qa",
          fetchedAt: new Date().toISOString(),
          retryable: false,
          checkedAt: new Date().toISOString(),
        },
      ],
      summaries: [
        {
          sourceType: "trend",
          totalCount: 1,
          connectedCount: 0,
          syntheticCount: 1,
          failedCount: 0,
          latestFetchedAt: new Date().toISOString(),
          authSources: ["fallback"],
          fallbackReasons: ["Fallback market evidence report."],
          connectedEndpoints: [],
          connectedSourceRefs: [],
          averageLatencyMs: 182,
        },
        {
          sourceType: "news",
          totalCount: 1,
          connectedCount: 0,
          syntheticCount: 1,
          failedCount: 0,
          latestFetchedAt: new Date().toISOString(),
          authSources: ["fallback"],
          fallbackReasons: ["Fallback market evidence report."],
          connectedEndpoints: [],
          connectedSourceRefs: [],
          averageLatencyMs: 241,
        },
        {
          sourceType: "qa",
          totalCount: 1,
          connectedCount: 0,
          syntheticCount: 1,
          failedCount: 0,
          latestFetchedAt: new Date().toISOString(),
          authSources: ["fallback"],
          fallbackReasons: ["Fallback market evidence report."],
          connectedEndpoints: [],
          connectedSourceRefs: [],
          averageLatencyMs: 197,
        },
      ],
      notes: ["Fallback market evidence report."],
    } satisfies MarketEvidenceReport,
    contentStrategy: {
      reportId: `${projectId}-content`,
      projectId,
      pillarPage: `${pick.project.name} Pillar`,
      pillarKeyword: pick.project.name.toLowerCase(),
      pillarIntent: "informational",
      topicClusters: [
        {
          title: "Meta and snippet tuning",
          intent: "informational",
          primaryKeyword: "meta title and description",
          secondaryKeywords: ["snippet", "title tag"],
          contentType: "pillar page",
          targetUrl: pick.project.url,
          wordCount: 1800,
          priority: 10,
          internalLinks: [pick.project.url],
          nextStep: "Link supporting content back to the pillar.",
        },
      ],
      calendar: [
        {
          week: 1,
          topic: "Meta and snippet tuning",
          targetKeyword: "meta title and description",
          contentType: "pillar page",
          wordCount: 1800,
          internalLinkTargets: [pick.project.url],
          priority: 10,
        },
      ],
      internalLinkBlueprint: [`${pick.project.url} -> ${pick.project.url}`],
      marketSignals: ["fallback trend cluster", "fallback news freshness", "fallback question expansion"],
      notes: ["Fallback content strategy report."],
    } satisfies ContentStrategyReport,
    adAudit: {
      reportId: `${projectId}-ad`,
      projectId,
      adAllowed: pick.project.siteClass !== "ymyl",
      reason: pick.project.siteClass === "ymyl" ? "Trust-sensitive pages should stay ad-free." : "Brand-safe sponsorship rail is acceptable.",
      adConnectorStatus: pick.project.siteClass === "ymyl" ? "missing_credentials" : "synthetic",
      adProviderFamily: pick.project.siteClass === "ymyl" ? null : "adsense",
      adProviderName: pick.project.siteClass === "ymyl" ? null : "Google AdSense",
      adProviderRef: pick.project.siteClass === "ymyl" ? null : "fallback-network",
      adInventoryStatus: pick.project.siteClass === "ymyl" ? "blocked" : "synthetic-ready",
      adImpressionsDaily: pick.project.siteClass === "ymyl" ? 0 : 5400,
      adClicksDaily: pick.project.siteClass === "ymyl" ? 0 : 63,
      adCtr: pick.project.siteClass === "ymyl" ? 0 : 0.0117,
      adFillRate: pick.project.siteClass === "ymyl" ? 0 : 0.52,
      adRpm: pick.project.siteClass === "ymyl" ? 0 : 3.44,
      adRevenueEstimateDaily: pick.project.siteClass === "ymyl" ? 0 : 18.6,
      adRevenueEstimateMonthly: pick.project.siteClass === "ymyl" ? 0 : 558,
      adRevenueSettledDaily: pick.project.siteClass === "ymyl" ? 0 : 16.9,
      adRevenueSettlementWindow: pick.project.siteClass === "ymyl" ? "blocked" : "T+7 fallback",
      adRevenueCurrency: pick.project.siteClass === "ymyl" ? null : "USD",
      adPolicyTier: pick.project.siteClass === "ymyl" ? null : "standard",
      adPayoutThreshold: pick.project.siteClass === "ymyl" ? null : 100,
      adGeoCoverage: pick.project.siteClass === "ymyl" ? [] : ["US", "CA", "GB"],
      adProviderProgram: pick.project.siteClass === "ymyl" ? null : "self-serve",
      adRevenueProvenance: ["status=synthetic", "providerFamily=adsense", "providerName=Google AdSense", "providerRef=fallback", "impressions=5400", "clicks=63", "ctr=0.0117", "fillRate=0.52", "rpm=3.44", "settledRevenueDaily=16.9", "settlementWindow=T+7 fallback", "currency=USD", "policyTier=standard", "payoutThreshold=100", "geoCoverage=US,CA,GB", "providerProgram=self-serve"],
      strictPublishEligible: false,
      fallbackReason: "Fallback mode active",
      providerExamples: pick.project.siteClass === "ymyl" ? [] : ["native sponsorship", "contextual affiliate"],
      pageFindings: [],
      templateCoverage: [pick.project.url],
      recommendations:
        pick.project.siteClass === "ymyl"
          ? [
              {
                pageUrl: pick.project.url,
                slotName: "no-ad",
                placement: "none",
                reason: "No ad inventory should be inserted on this page type.",
                riskScore: 92,
                allowed: false,
                evidence: ["fallback"],
                negativeConditions: ["Fallback policy marks this project as no-ad.", "Trust-sensitive content should remain ad-free."],
              },
            ]
          : [
              {
                pageUrl: pick.project.url,
                slotName: "slot-1",
                placement: "sidebar",
                reason: "Contextual sponsorship rail.",
                riskScore: 28,
                allowed: true,
                evidence: ["fallback"],
                negativeConditions: ["Block this slot if CTA overlap appears in preview.", "Block this slot if connector stays in fallback mode."],
              },
      ],
      negativeConditions: pick.project.siteClass === "ymyl"
        ? ["Fallback policy marks this project as no-ad.", "Trust-sensitive content should remain ad-free."]
        : ["Block ads if CTA overlap appears in preview.", "Block ads if connector stays in fallback mode."],
      notes: ["Fallback ad audit report."],
    } satisfies AdAuditReport,
    adaptiveComponents: {
      reportId: `${projectId}-adaptive`,
      projectId,
      siteId: pick.project.projectId,
      suggestions: [],
      moduleStack: [],
      notes: ["Fallback adaptive component report."],
    },
    technicalSeo: {
      reportId: `${projectId}-seo`,
      projectId,
      overallHealth: pick.project.siteClass === "ymyl" ? "degraded" : "healthy",
      crawlability: [
        {
          area: "crawlability",
          issue: "Sitemap is synthetic in fallback mode.",
          impact: "medium",
          evidence: ["fallback"],
          fix: "Connect sitemap and Search Console for live crawl validation.",
          priority: 2,
        },
      ],
      onPage: [
        {
          area: "title tags",
          issue: "Primary title is a fallback sample.",
          impact: "low",
          evidence: ["fallback"],
          fix: "Write a unique title under 60 characters.",
          priority: 4,
        },
        {
          area: "heading structure",
          issue: "Heading hierarchy is only partially represented.",
          impact: "medium",
          evidence: ["fallback"],
          fix: "Keep one H1 and supporting H2/H3 headings.",
          priority: 3,
        },
      ],
      content: [
        {
          area: "content depth",
          issue: "Topic coverage can be expanded with a pillar-plus-cluster model.",
          impact: "medium",
          evidence: ["fallback"],
          fix: "Publish pillar and supporting articles with explicit internal links.",
          priority: 2,
        },
      ],
      performance: [
        {
          area: "core web vitals",
          issue: "Live performance is not measured in fallback mode.",
          impact: "low",
          evidence: ["fallback"],
          fix: "Attach real metrics or lab data before launch.",
          priority: 4,
        },
      ],
      actionPlan: [
        "Fix crawlability issues first.",
        "Tighten on-page metadata and heading structure.",
        "Publish the pillar plus cluster content plan.",
      ],
      notes: ["Fallback technical SEO report."],
    } satisfies TechnicalSeoReport,
    technicalSeoPatch: {
      reportId: `${projectId}-seo-patch`,
      projectId,
      taskId: `${projectId}-task`,
      verifiedPatch: true,
      strictMode: false,
      patchAudit: {
        checkedTargets: 5,
        passedTargets: 5,
        failedTargets: 0,
        requiredChecks: ["ctaPreserved", "domDiff", "domInsertions"],
        failedRequiredChecks: [],
        checks: {
          domDiff: true,
          ctaPreserved: true,
          domInsertions: true,
          metaPresence: true,
          schemaPresence: true,
        },
        beforeAfter: {
          title: {
            before: `${pick.project.name} fallback title`,
            after: `${pick.project.name} fallback title`,
            changed: false,
          },
          meta: {
            description: {
              before: "Fallback project description",
              after: "Fallback project description",
              changed: false,
            },
          },
          schemaTypes: {
            before: ["WebSite"],
            after: ["WebSite"],
            added: [],
            removed: [],
          },
          domTargets: {
            before: [],
            after: ["main.hero", "section.value-props"],
          },
        },
      },
      steps: [
        {
          area: "title tags",
          field: "title",
          before: `${pick.project.name} fallback title`,
          after: `${pick.project.name} fallback title`,
          skillId: "seo/technical-seo-patcher",
          verified: true,
          rollbackSupported: true,
          evidence: ["fallback"],
        },
      ],
      notes: ["Fallback technical SEO patch report."],
    } satisfies TechnicalSeoPatchReport,
  };
}

export function fallbackProjectDeploymentHistory(projectId: string): DeploymentHistoryReport {
  const detail = fallbackProjectDetail(projectId);
  return {
    projectId,
    total: detail.deploymentHistory.length,
    entries: detail.deploymentHistory,
  };
}

export function fallbackProjectRollbackHistory(projectId: string): RollbackHistoryReport {
  const detail = fallbackProjectDetail(projectId);
  return {
    projectId,
    total: detail.rollbackHistory.length,
    entries: detail.rollbackHistory,
  };
}

export function fallbackContentStrategyReport(projectId: string): ContentStrategyReport {
  return fallbackProjectDetail(projectId).contentStrategy as ContentStrategyReport;
}

export function fallbackAdAuditReport(projectId: string): AdAuditReport {
  return fallbackProjectDetail(projectId).adAudit as AdAuditReport;
}

export function fallbackWorkspaceAdAuditHistoryReport(projectId?: string): WorkspaceAdAuditHistoryReport {
  const now = new Date().toISOString();
  const selected = projectId ? fallbackProjects.filter((item) => item.project.projectId === projectId) : [...fallbackProjects];
  const entries = selected.slice(0, 8).map((item) => {
    const adAudit = fallbackProjectDetail(item.project.projectId).adAudit!;
    return {
      reportId: adAudit.reportId,
      generatedAt: now,
      projectId: item.project.projectId,
      projectName: item.project.name,
      adAllowed: adAudit.adAllowed,
      reason: adAudit.reason,
      adConnectorStatus: adAudit.adConnectorStatus,
      adProviderFamily: adAudit.adProviderFamily,
      adProviderName: adAudit.adProviderName,
      adProviderRef: adAudit.adProviderRef,
      adInventoryStatus: adAudit.adInventoryStatus,
      adRevenueEstimateDaily: adAudit.adRevenueEstimateDaily,
      adRevenueEstimateMonthly: adAudit.adRevenueEstimateMonthly,
      adRevenueSettledDaily: adAudit.adRevenueSettledDaily,
      adRevenueCurrency: adAudit.adRevenueCurrency,
      adPolicyTier: adAudit.adPolicyTier,
      strictPublishEligible: Boolean(adAudit.strictPublishEligible),
      fallbackReason: adAudit.fallbackReason,
      failureCode: adAudit.failureCode,
      providerExamples: adAudit.providerExamples,
      negativeConditions: adAudit.negativeConditions,
      recommendationCount: adAudit.recommendations.length,
    };
  });
  const latest = entries[0] ?? null;
  return {
    generatedAt: now,
    projectId: projectId ?? null,
    total: entries.length,
    projectCount: new Set(entries.map((item) => item.projectId)).size,
    allowedCount: entries.filter((item) => item.adAllowed).length,
    blockedCount: entries.filter((item) => !item.adAllowed).length,
    strictPublishEligibleCount: entries.filter((item) => item.strictPublishEligible).length,
    connectorConnectedCount: entries.filter((item) => item.adConnectorStatus === "connected").length,
    latestReportId: latest?.reportId ?? null,
    latestProjectId: latest?.projectId ?? null,
    latestProjectName: latest?.projectName ?? null,
    latestAdProviderFamily: latest?.adProviderFamily ?? null,
    latestAdProviderName: latest?.adProviderName ?? null,
    latestAdInventoryStatus: latest?.adInventoryStatus ?? null,
    latestAdAllowed: latest?.adAllowed ?? null,
    latestStrictPublishEligible: latest?.strictPublishEligible ?? null,
    latestReason: latest?.reason ?? null,
    latestFailureCode: latest?.failureCode ?? null,
    latestFallbackReason: latest?.fallbackReason ?? null,
    latestAdRevenueEstimateDaily: latest?.adRevenueEstimateDaily ?? null,
    latestAdRevenueEstimateMonthly: latest?.adRevenueEstimateMonthly ?? null,
    latestAdRevenueCurrency: latest?.adRevenueCurrency ?? null,
    latestNegativeConditionCount: latest ? latest.negativeConditions.length : null,
    latestRecommendationCount: latest?.recommendationCount ?? null,
    entries,
  };
}

export function fallbackTechnicalSeoReport(projectId: string): TechnicalSeoReport {
  return fallbackProjectDetail(projectId).technicalSeo as TechnicalSeoReport;
}

function fallbackPromptVersions(): PromptVersion[] {
  const reviewedAt = new Date().toISOString();
  return [
    {
      promptId: "sniffer-site-profile",
      role: "sniffer",
      name: "Site profiling prompt",
      version: "v1.2.0",
      status: "active",
      owner: "analysis-team",
      summary: "Extracts the site's business, trust signals, template shape, and visible CTA structure.",
      checksum: "sha256:1f7e4f5c7d2d",
      lastReviewedAt: reviewedAt,
      usedBy: ["Coordinator", "RegressionReport"],
      notes: ["Stable prompt for turning a URL into a structured site profile."],
    },
    {
      promptId: "query-opportunity-discovery",
      role: "query",
      name: "Opportunity discovery prompt",
      version: "v1.1.0",
      status: "active",
      owner: "growth-strategy",
      summary: "Surfaces content, technical, and monetization opportunities without inventing unsupported demand.",
      checksum: "sha256:66a83b56e1f9",
      lastReviewedAt: reviewedAt,
      usedBy: ["Strategist"],
      notes: ["Used for keyword, topic, and placement discovery."],
    },
    {
      promptId: "strategist-plan-builder",
      role: "strategist",
      name: "Plan builder prompt",
      version: "v1.3.0",
      status: "active",
      owner: "product-growth",
      summary: "Turns opportunities into a preview-first plan with approval thresholds and rollback notes.",
      checksum: "sha256:0d32e5a4c8bb",
      lastReviewedAt: reviewedAt,
      usedBy: ["Coordinator"],
      notes: ["Aligns release strategy with risk score and deployment mode."],
    },
    {
      promptId: "ux-reviewer-layout-safety",
      role: "ux",
      name: "UX safety review prompt",
      version: "v1.0.3",
      status: "active",
      owner: "design-system",
      summary: "Checks that proposed modules preserve CTA visibility, hierarchy, and page trust.",
      checksum: "sha256:bb8f16b023a1",
      lastReviewedAt: reviewedAt,
      usedBy: ["Coordinator", "Approval flow"],
      notes: ["Used before a visible module can leave preview."],
    },
    {
      promptId: "policy-guard-release-policy",
      role: "policy",
      name: "Policy guard prompt",
      version: "v1.1.1",
      status: "active",
      owner: "trust-and-safety",
      summary: "Rejects proposals that are off-brand, high-risk, or unsafe for the page category.",
      checksum: "sha256:2f95d7c0b4a0",
      lastReviewedAt: reviewedAt,
      usedBy: ["Coordinator", "Approval Gateway"],
      notes: ["Ensures no-ad pages remain ad-free."],
    },
    {
      promptId: "coordinator-execution-graph",
      role: "coordinator",
      name: "Coordinator orchestration prompt",
      version: "v1.4.0",
      status: "active",
      owner: "platform",
      summary: "Assembles the execution graph, chooses the skill chain, and routes to approval when needed.",
      checksum: "sha256:49d1b8f70951",
      lastReviewedAt: reviewedAt,
      usedBy: ["WorkflowService"],
      notes: ["Keeps the execution graph deterministic and auditable."],
    },
  ];
}

export function fallbackPromptRegistry(): PromptRegistry {
  return {
    generatedAt: new Date().toISOString(),
    versions: fallbackPromptVersions(),
    notes: [
      "Fallback prompt registry used when the API is unavailable.",
      "Prompt versions are intentionally explicit so reviewers can trace behavior back to a named prompt revision.",
    ],
  };
}

function fallbackRegressionSamples(): RegressionSample[] {
  return [
    {
      sampleId: "aurora-shop",
      name: "Aurora Shop",
      intake: {
        url: "https://aurora-shop.example",
        siteName: "Aurora Shop",
        repoUrl: "https://github.com/example/aurora-shop",
        sitemapUrls: ["/sitemap.xml"],
        keywords: ["winter jackets", "outdoor gear", "membrane shell"],
        brandWhitelist: ["Aurora"],
        competitors: ["northpeak", "snowtrail"],
        language: "en",
        locale: "en-US",
        notes: "Fallback regression sample.",
      },
      expectedSeoPreview: true,
      expectedAdAllowed: true,
      expectedRiskBand: "medium",
      notes: ["ecommerce sample"],
    },
    {
      sampleId: "northstar-media",
      name: "Northstar Media",
      intake: {
        url: "https://northstar-media.example",
        siteName: "Northstar Media",
        repoUrl: "https://github.com/example/northstar-media",
        sitemapUrls: ["/sitemap.xml", "/news-sitemap.xml"],
        keywords: ["industry insights", "growth signals", "editorial brief"],
        brandWhitelist: ["Northstar"],
        competitors: ["dailybrief", "signalroom"],
        language: "en",
        locale: "en-US",
        notes: "Fallback regression sample.",
      },
      expectedSeoPreview: true,
      expectedAdAllowed: true,
      expectedRiskBand: "medium",
      notes: ["content sample"],
    },
    {
      sampleId: "ledgerflow",
      name: "LedgerFlow",
      intake: {
        url: "https://ledgerflow.example",
        siteName: "LedgerFlow",
        cmsName: "webflow",
        sitemapUrls: ["/sitemap.xml"],
        keywords: ["budget tracker", "cash flow", "monthly plan"],
        brandWhitelist: ["LedgerFlow"],
        competitors: ["finpilot", "budgetwise"],
        language: "en",
        locale: "en-US",
        notes: "Fallback regression sample.",
      },
      expectedSeoPreview: true,
      expectedAdAllowed: true,
      expectedRiskBand: "medium",
      notes: ["saas sample"],
    },
    {
      sampleId: "pixel-notes",
      name: "Pixel Notes",
      intake: {
        url: "https://pixel-notes.example",
        siteName: "Pixel Notes",
        cmsName: "contentful",
        sitemapUrls: ["/sitemap.xml"],
        keywords: ["note taking", "knowledge base", "task memory"],
        brandWhitelist: ["Pixel Notes"],
        competitors: ["noteforge", "memolane"],
        language: "en",
        locale: "en-US",
        notes: "Fallback regression sample.",
      },
      expectedSeoPreview: true,
      expectedAdAllowed: true,
      expectedRiskBand: "medium",
      notes: ["tool sample"],
    },
    {
      sampleId: "greenhouse-recipes",
      name: "Greenhouse Recipes",
      intake: {
        url: "https://greenhouse-recipes.example",
        siteName: "Greenhouse Recipes",
        repoUrl: "https://github.com/example/greenhouse-recipes",
        sitemapUrls: ["/sitemap.xml"],
        keywords: ["seasonal meals", "meal planning", "family recipes"],
        brandWhitelist: ["Greenhouse"],
        competitors: ["pantrynote", "kitchenloop"],
        language: "en",
        locale: "en-US",
        notes: "Fallback regression sample.",
      },
      expectedSeoPreview: true,
      expectedAdAllowed: true,
      expectedRiskBand: "medium",
      notes: ["content sample"],
    },
    {
      sampleId: "peak-supplies",
      name: "Peak Supplies",
      intake: {
        url: "https://peak-supplies.example",
        siteName: "Peak Supplies",
        repoUrl: "https://github.com/example/peak-supplies",
        sitemapUrls: ["/sitemap.xml"],
        keywords: ["camping stove", "trail kit", "gear bundle"],
        brandWhitelist: ["Peak"],
        competitors: ["ridgebox", "summitkit"],
        language: "en",
        locale: "en-US",
        notes: "Fallback regression sample.",
      },
      expectedSeoPreview: true,
      expectedAdAllowed: true,
      expectedRiskBand: "medium",
      notes: ["commerce sample"],
    },
    {
      sampleId: "studycraft",
      name: "StudyCraft",
      intake: {
        url: "https://studycraft.example",
        siteName: "StudyCraft",
        cmsName: "sanity",
        sitemapUrls: ["/sitemap.xml"],
        keywords: ["study planner", "student workflow", "focus sprint"],
        brandWhitelist: ["StudyCraft"],
        competitors: ["learnflow", "noteforge"],
        language: "en",
        locale: "en-US",
        notes: "Fallback regression sample.",
      },
      expectedSeoPreview: true,
      expectedAdAllowed: true,
      expectedRiskBand: "medium",
      notes: ["saas sample"],
    },
    {
      sampleId: "retro-gear",
      name: "Retro Gear",
      intake: {
        url: "https://retro-gear.example",
        siteName: "Retro Gear",
        repoUrl: "https://github.com/example/retro-gear",
        sitemapUrls: ["/sitemap.xml"],
        keywords: ["vintage headphones", "audio gear", "retro electronics"],
        brandWhitelist: ["Retro"],
        competitors: ["oldsound", "vibeaudio"],
        language: "en",
        locale: "en-US",
        notes: "Fallback regression sample.",
      },
      expectedSeoPreview: true,
      expectedAdAllowed: true,
      expectedRiskBand: "medium",
      notes: ["commerce sample"],
    },
    {
      sampleId: "trust-clinic",
      name: "Trust Clinic",
      intake: {
        url: "https://trust-clinic.example",
        siteName: "Trust Clinic",
        cmsName: "drupal",
        sitemapUrls: ["/sitemap.xml"],
        keywords: ["medical guidance", "patient resources", "clinic reviews"],
        brandWhitelist: [],
        competitors: ["careline", "healthvault"],
        language: "en",
        locale: "en-US",
        notes: "Fallback regression sample.",
      },
      expectedSeoPreview: true,
      expectedAdAllowed: false,
      expectedRiskBand: "high",
      notes: ["YMYL no-ad sample"],
    },
    {
      sampleId: "north-forge-tools",
      name: "North Forge Tools",
      intake: {
        url: "https://northforge-tools.example",
        siteName: "North Forge Tools",
        cmsName: "ghost",
        sitemapUrls: ["/sitemap.xml"],
        keywords: ["workflow generator", "template builder", "tooling"],
        brandWhitelist: ["North Forge"],
        competitors: ["taskfoundry", "tooltrace"],
        language: "en",
        locale: "en-US",
        notes: "Fallback regression sample.",
      },
      expectedSeoPreview: true,
      expectedAdAllowed: true,
      expectedRiskBand: "medium",
      notes: ["tool sample"],
    },
  ];
}

function fallbackSiteClass(sampleId: string): SiteClass {
  if (sampleId === "trust-clinic") return "ymyl";
  if (sampleId === "northstar-media" || sampleId === "greenhouse-recipes") return "content";
  if (sampleId === "pixel-notes") return "tool";
  if (sampleId === "ledgerflow" || sampleId === "studycraft") return "saas";
  return "ecommerce";
}

export function fallbackRegressionSampleSet(): RegressionSampleSet {
  const samples = fallbackRegressionSamples();
  return {
    generatedAt: new Date().toISOString(),
    sampleCount: samples.length,
    samples,
    notes: ["Fallback regression sample set used when the API is unavailable."],
  };
}

export function fallbackRegressionReport(): RegressionReport {
  const sampleSet = fallbackRegressionSampleSet();
  return {
    reportId: "fallback-regress",
    generatedAt: new Date().toISOString(),
    sampleCount: sampleSet.sampleCount,
    seoPreviewCount: sampleSet.sampleCount,
    adRecommendationCount: sampleSet.sampleCount,
    noAdCount: 1,
    passCount: sampleSet.sampleCount,
    failCount: 0,
    cases: sampleSet.samples.map((sample) => ({
      sampleId: sample.sampleId,
      name: sample.name,
      siteClass: fallbackSiteClass(sample.sampleId),
      riskScore: sample.expectedRiskBand === "high" ? 88 : 49,
      deploymentMode: sample.intake.repoUrl ? "github_pr" : sample.intake.cmsName ? "cms_draft" : "static_export",
      connectionHealth: sample.expectedAdAllowed ? "healthy" : "degraded",
      seoPreviewReady: sample.expectedSeoPreview,
      adRecommendation: sample.expectedAdAllowed ? "Native sponsorship rail" : "Do not recommend ads",
      adAllowed: sample.expectedAdAllowed,
      passed: true,
      notes: ["fallback", ...sample.notes],
    })),
    notes: ["Fallback regression report used when the API is unavailable."],
  };
}

export function fallbackAcceptanceReport(): AcceptanceReport {
  const regression = fallbackRegressionReport();
  const promptRegistry = fallbackPromptRegistry();
  const gates = [
    {
      gateId: "mvp_samples",
      name: "样本站画像数量",
      passed: regression.sampleCount >= 10,
      expected: ">= 10",
      actual: String(regression.sampleCount),
      quickActionPath: "/acceptance",
      quickActionLabel: "查看验收总览",
      notes: ["MVP 要求至少 10 个样本站画像。"],
    },
    {
      gateId: "mvp_seo_previews",
      name: "SEO 预览数量",
      passed: regression.seoPreviewCount >= 3,
      expected: ">= 3",
      actual: String(regression.seoPreviewCount),
      quickActionPath: "/strategy",
      quickActionLabel: "补齐 SEO 预览",
      notes: ["MVP 要求至少 3 个 SEO 预览。"],
    },
    {
      gateId: "mvp_ad_recommendations",
      name: "广告建议数量",
      passed: regression.adRecommendationCount >= 2,
      expected: ">= 2",
      actual: String(regression.adRecommendationCount),
      quickActionPath: "/projects",
      quickActionLabel: "查看广告建议",
      notes: ["MVP 要求至少 2 条广告建议。"],
    },
    {
      gateId: "mvp_no_ad_negative",
      name: "不建议接广告负例",
      passed: regression.noAdCount >= 1,
      expected: ">= 1",
      actual: String(regression.noAdCount),
      quickActionPath: "/acceptance",
      quickActionLabel: "核对 no-ad 负例",
      notes: ["MVP 要求至少 1 条 no-ad 负例。"],
    },
    {
      gateId: "mvp_rollback_path",
      name: "可复现回滚链路",
      passed: true,
      expected: ">= 1",
      actual: "1",
      quickActionPath: "/monitor",
      quickActionLabel: "检查回滚链路",
      notes: ["Fallback 报告默认包含 1 条回滚可用链路。"],
    },
    {
      gateId: "prompt_registry",
      name: "Prompt 版本治理",
      passed: promptRegistry.versions.filter((item) => item.status === "active").length >= 1,
      expected: "active >= 1",
      actual: String(promptRegistry.versions.filter((item) => item.status === "active").length),
      quickActionPath: "/quality",
      quickActionLabel: "管理 Prompt 版本",
      notes: ["Prompt 注册表至少保留一个 active 版本。"],
    },
    {
      gateId: "real_provider_samples",
      name: "真实 provider 读写样例",
      passed: false,
      expected: "readReal>=1 且 writeReal>=1",
      actual: "readReal=0, writeReal=0",
      quickActionPath: "/settings",
      quickActionLabel: "连接真实 Provider",
      notes: ["Fallback 模式下默认不满足真实 provider 样例门槛。"],
    },
    {
      gateId: "market_evidence_freshness",
      name: "市场证据新鲜度",
      passed: false,
      expected: "connected>=1，strictProviders=true 时 fresh>=1",
      actual: "marketConnected=0, marketSynthetic=0, marketFailed=0, marketFresh=0, freshnessMinutes=30, lastFetchedAt=none",
      quickActionPath: "/strategy",
      quickActionLabel: "刷新市场证据",
      notes: ["Fallback 模式下默认不满足市场证据门槛。"],
    },
    {
      gateId: "market_workspace_readiness",
      name: "工作区市场证据就绪",
      passed: false,
      expected: "projectCount>=1 且 connected>=1 且 strictReadyProjectCount>=1",
      actual: "projectCount=0, connected=0, fresh=0, stale=0, strictReadyProjects=0, strictReadyRate=0%",
      quickActionPath: "/monitor",
      quickActionLabel: "检查工作区市场证据",
      notes: ["Fallback 模式下默认不满足工作区市场证据门槛。"],
    },
    {
      gateId: "visual_regression_production",
      name: "视觉回归生产就绪",
      passed: false,
      expected: "configuredEndpoints>=1 且 latestRun 无 notConfigured/fallback/failed/strictBlocked",
      actual: "configuredEndpoints=0, notConfigured=1, fallback=1, failed=0, strictBlocked=0",
      quickActionPath: "/quality?focus=visual-regressions",
      quickActionLabel: "修复视觉回归",
      notes: ["Fallback 模式下视觉回归生产就绪 gate 默认不通过。"],
    },
    {
      gateId: "blocking_alerts_clear",
      name: "阻断级风险清零",
      passed: false,
      expected: "critical blocking remediations = 0",
      actual: "criticalBlocking=1, blockingTotal=2, topFailureCodes=VISUAL_FARM_NOT_CONFIGURED",
      quickActionPath: "/monitor",
      quickActionLabel: "处理阻断告警",
      notes: ["Fallback 模式下默认存在阻断级 remediation。"],
    },
    {
      gateId: "oncall_coverage_ready",
      name: "值班覆盖就绪",
      passed: false,
      expected: "routeCount>=1 且 rotatingRouteCount>=1 且 items>=1",
      actual: "routeCount=0, rotatingRouteCount=0, items=0",
      quickActionPath: "/monitor#on-call-rotation",
      quickActionLabel: "检查值班覆盖",
      notes: ["Fallback 模式下默认不满足 on-call 覆盖门槛。"],
    },
    {
      gateId: "observability_pipeline",
      name: "可观测性链路就绪",
      passed: false,
      expected: "至少启用 OTLP 或配置 Sentry DSN",
      actual: "enableOtlp=false, sentryDsnConfigured=false, observabilityStrict=false",
      quickActionPath: "/settings",
      quickActionLabel: "配置可观测性",
      notes: ["Fallback 模式下默认未接通生产可观测性链路。"],
    },
    {
      gateId: "runtime_architecture_production",
      name: "运行时架构生产就绪",
      passed: false,
      expected: "queueBackend=redis 且 database=postgresql",
      actual: "queueBackend=memory, database=sqlite",
      quickActionPath: "/settings",
      quickActionLabel: "配置生产运行时",
      notes: ["Fallback 模式下默认不是生产级运行时架构。"],
    },
  ];
  return {
    reportId: "acceptance-fallback",
    generatedAt: new Date().toISOString(),
    regression,
    strictProvidersEnabled: false,
    billingGatewayReady: false,
    billingGatewayRouteReadyCount: 0,
    billingGatewayRouteCount: 0,
    promptRegistryCount: promptRegistry.versions.length,
    activePromptCount: promptRegistry.versions.filter((item) => item.status === "active").length,
    rollbackReadyCount: 1,
    totalProjectCount: fallbackProjects.length,
    readRealEvidenceCount: 0,
    writeRealEvidenceCount: 0,
    readRealProviderCount: 0,
    writeRealProviderCount: 0,
    readRealProviders: [],
    writeRealProviders: [],
    readRealEvidence: [],
    writeRealEvidence: [],
    marketEvidenceConnectedCount: 0,
    marketEvidenceSyntheticCount: 0,
    marketEvidenceFailedCount: 0,
    marketEvidenceFreshCount: 0,
    marketEvidenceLastFetchedAt: null,
    gates,
    passed: gates.every((item) => item.passed),
    notes: ["Fallback acceptance report used when the API is unavailable."],
  };
}

export function fallbackProductBenchmarkReport(): ProductBenchmarkReport {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    projectId: null,
    referenceCount: 7,
    capabilityCount: 6,
    productionReadyCount: 0,
    partialCount: 6,
    missingCount: 0,
    averageMaturityScore: 42,
    references: [
      {
        name: "Conductor Website Monitoring / ContentKing",
        category: "seo_monitoring",
        sourceUrl: "https://www.conductor.com/",
        observedCapabilities: ["Always-on SEO monitoring", "Issue alerts", "Page change tracking"],
      },
      {
        name: "Botify",
        category: "seo_monitoring",
        sourceUrl: "https://www.botify.com/",
        observedCapabilities: ["Enterprise crawl analytics", "Search visibility diagnostics", "Prioritized technical SEO actions"],
      },
      {
        name: "Checkly",
        category: "visual_monitoring",
        sourceUrl: "https://www.checklyhq.com/",
        observedCapabilities: ["Playwright checks", "Screenshot monitoring", "Production regression alerts"],
      },
      {
        name: "Vercel / Cloudflare edge runtime",
        category: "edge_runtime",
        sourceUrl: "https://vercel.com/docs/edge-middleware",
        observedCapabilities: ["Edge rewrites", "Request middleware", "Multi-origin routing"],
      },
      {
        name: "Google Ad Manager reporting",
        category: "ads_reporting",
        sourceUrl: "https://developers.google.com/ad-manager/api",
        observedCapabilities: ["Impression reporting", "Click reporting", "Revenue metrics"],
      },
      {
        name: "Stripe Connect",
        category: "settlement",
        sourceUrl: "https://docs.stripe.com/connect",
        observedCapabilities: ["Connected accounts", "Platform payouts", "Payment compliance flows"],
      },
      {
        name: "Optimizely Feature Experimentation",
        category: "experimentation",
        sourceUrl: "https://docs.developers.optimizely.com/feature-experimentation/",
        observedCapabilities: ["Feature flags", "Audience targeting", "Progressive rollout governance"],
      },
    ],
    capabilities: [
      {
        capabilityId: "real_provider_ingestion_writeback",
        title: "真实外部数据源与写回链路",
        currentStatus: "partial",
        maturityScore: 35,
        comparableProducts: ["Conductor Website Monitoring / ContentKing", "Botify"],
        implementedEvidence: ["Fallback report: API unavailable"],
        remainingGaps: ["扩大真实 provider 生产样本。", "strictProviders=true 下禁止 fallback 冒充成功。"],
        nextActions: ["补生产连接 smoke。", "把 provider freshness 纳入发布验收。"],
        priority: "p0",
      },
      {
        capabilityId: "visual_farm_production",
        title: "视觉回归与截图农场生产化",
        currentStatus: "partial",
        maturityScore: 45,
        comparableProducts: ["Checkly"],
        implementedEvidence: ["Fallback report: visual farm status unavailable"],
        remainingGaps: ["截图农场生产端点和部署闭环仍需收口。"],
        nextActions: ["补截图 provider production smoke。"],
        priority: "p0",
      },
      {
        capabilityId: "runtime_edge_multisite",
        title: "边缘流量、rewrite / reverse proxy 与多站点编排",
        currentStatus: "partial",
        maturityScore: 50,
        comparableProducts: ["Vercel / Cloudflare edge runtime"],
        implementedEvidence: ["Fallback report: runtime edge status unavailable"],
        remainingGaps: ["真实站点流量接入和多站点生产编排仍需验证。"],
        nextActions: ["补 runtime-edge production smoke。"],
        priority: "p1",
      },
      {
        capabilityId: "ad_revenue_reporting",
        title: "广告平台接入与收益回传",
        currentStatus: "partial",
        maturityScore: 40,
        comparableProducts: ["Google Ad Manager reporting"],
        implementedEvidence: ["Fallback report: ad revenue status unavailable"],
        remainingGaps: ["真实广告平台 reporting API 样本仍需扩展。"],
        nextActions: ["补 GAM / AdSense 风格 reporting smoke。"],
        priority: "p1",
      },
      {
        capabilityId: "merchant_settlement",
        title: "商户结算 SDK / 网关",
        currentStatus: "partial",
        maturityScore: 45,
        comparableProducts: ["Stripe Connect"],
        implementedEvidence: ["Fallback report: settlement gateway status unavailable"],
        remainingGaps: ["正式支付 SDK 和商户结算状态机仍需深化。"],
        nextActions: ["补 Stripe Connect / payout provider contract。"],
        priority: "p1",
      },
      {
        capabilityId: "experimentation_runtime_governance",
        title: "深度运行时 A/B 分流和灰度治理",
        currentStatus: "partial",
        maturityScore: 40,
        comparableProducts: ["Optimizely Feature Experimentation"],
        implementedEvidence: ["Fallback report: experimentation status unavailable"],
        remainingGaps: ["实验统计、停止条件和自动回滚联动仍需增强。"],
        nextActions: ["补 assignment history 和 guardrail 指标。"],
        priority: "p2",
      },
    ],
    recommendedNextCapabilityIds: [
      "real_provider_ingestion_writeback",
      "visual_farm_production",
      "runtime_edge_multisite",
      "ad_revenue_reporting",
    ],
    notes: ["Fallback benchmark report used when the API is unavailable."],
  };
}

export function fallbackRemainingTaskReport(): RemainingTaskReport {
  const benchmark = fallbackProductBenchmarkReport();
  const items = benchmark.capabilities
    .filter((item) => item.currentStatus !== "production_ready")
    .map((item) => ({
      taskId: `remaining_${item.capabilityId}`,
      title: item.title,
      priority: item.priority,
      sourceCapabilityId: item.capabilityId,
      status: item.priority === "p0" ? ("blocked" as const) : ("planned" as const),
      blocking: item.priority === "p0",
      acceptanceGateIds: [],
      remainingGaps: item.remainingGaps,
      nextAction: item.nextActions[0] ?? null,
      quickActionPath: "/acceptance",
      quickActionLabel: "Open acceptance",
    }));
  return {
    generatedAt: new Date().toISOString(),
    projectId: null,
    total: items.length,
    blockingCount: items.filter((item) => item.blocking).length,
    p0Count: items.filter((item) => item.priority === "p0").length,
    p1Count: items.filter((item) => item.priority === "p1").length,
    p2Count: items.filter((item) => item.priority === "p2").length,
    p3Count: items.filter((item) => item.priority === "p3").length,
    items,
    notes: ["Fallback remaining-task report used when API is unavailable."],
  };
}

export function fallbackRemainingTaskBoardReport(): RemainingTaskBoardReport {
  const remaining = fallbackRemainingTaskReport();
  return {
    generatedAt: new Date().toISOString(),
    projectId: remaining.projectId ?? null,
    total: remaining.total,
    blockingCount: remaining.blockingCount,
    groups: [
      {
        groupId: "provider",
        title: "Provider read/write",
        total: remaining.items.filter((item) => item.sourceCapabilityId === "real_provider_ingestion_writeback").length,
        blockingCount: remaining.items.filter((item) => item.sourceCapabilityId === "real_provider_ingestion_writeback" && item.blocking).length,
        p0Count: remaining.items.filter((item) => item.sourceCapabilityId === "real_provider_ingestion_writeback" && item.priority === "p0").length,
        p1Count: 0,
        p2Count: 0,
        p3Count: 0,
        taskIds: remaining.items.filter((item) => item.sourceCapabilityId === "real_provider_ingestion_writeback").map((item) => item.taskId),
      },
      {
        groupId: "visual",
        title: "Visual farm",
        total: remaining.items.filter((item) => item.sourceCapabilityId === "visual_farm_production").length,
        blockingCount: remaining.items.filter((item) => item.sourceCapabilityId === "visual_farm_production" && item.blocking).length,
        p0Count: remaining.items.filter((item) => item.sourceCapabilityId === "visual_farm_production" && item.priority === "p0").length,
        p1Count: 0,
        p2Count: 0,
        p3Count: 0,
        taskIds: remaining.items.filter((item) => item.sourceCapabilityId === "visual_farm_production").map((item) => item.taskId),
      },
    ],
    notes: ["Fallback remaining-task board report used when API is unavailable."],
  };
}

export function fallbackMarketEvidenceHealthReport(): MarketEvidenceHealthReport {
  return {
    reportId: "fallback-market-health",
    projectId: "fallback-project",
    generatedAt: new Date().toISOString(),
    strictProvidersEnabled: false,
    connectedCount: 0,
    syntheticCount: 0,
    failedCount: 0,
    freshCount: 0,
    staleCount: 0,
    latestFetchedAt: null,
    strictReady: false,
    notes: ["Fallback market evidence health report."],
  };
}

export function fallbackWorkspaceMarketEvidenceHealthReport(): WorkspaceMarketEvidenceHealthReport {
  return {
    reportId: "fallback-workspace-market-health",
    generatedAt: new Date().toISOString(),
    strictProvidersEnabled: false,
    projectCount: 0,
    connectedCount: 0,
    syntheticCount: 0,
    failedCount: 0,
    freshCount: 0,
    staleCount: 0,
    strictReadyProjectCount: 0,
    strictReadyProjectRatePercent: 0,
    latestFetchedAt: null,
    strictReadyProjectIds: [],
    staleProjectIds: [],
    notes: ["Fallback workspace market evidence health report."],
  };
}

export function fallbackMarketEvidenceProviderStatusReport(): MarketEvidenceProviderStatusReport {
  const now = new Date().toISOString();
  const entries: MarketEvidenceProviderStatus[] = [
    {
      provider: "trend",
      providerLabel: "Trend",
      endpoint: null,
      configured: false,
      authConfigured: false,
      authHeader: "Authorization",
      authSource: "none",
      strictReady: false,
      fallbackReason: "Fallback market evidence provider status uses demo data.",
      notes: ["Fallback market evidence provider status."],
    },
    {
      provider: "news",
      providerLabel: "News",
      endpoint: null,
      configured: false,
      authConfigured: false,
      authHeader: "Authorization",
      authSource: "none",
      strictReady: false,
      fallbackReason: "Fallback market evidence provider status uses demo data.",
      notes: ["Fallback market evidence provider status."],
    },
    {
      provider: "qa",
      providerLabel: "QA",
      endpoint: null,
      configured: false,
      authConfigured: false,
      authHeader: "Authorization",
      authSource: "none",
      strictReady: false,
      fallbackReason: "Fallback market evidence provider status uses demo data.",
      notes: ["Fallback market evidence provider status."],
    },
  ];
  return {
    reportId: "fallback-market-provider",
    generatedAt: now,
    providerCount: entries.length,
    configuredCount: 0,
    authConfiguredCount: 0,
    strictReadyCount: 0,
    entries,
    notes: ["Fallback market evidence provider status is non-authoritative."],
  };
}

export function fallbackWorkspaceCruiseHealthReport(): WorkspaceCruiseHealthReport {
  return {
    reportId: "fallback-workspace-cruise-health",
    generatedAt: new Date().toISOString(),
    autoCruiseEnabled: false,
    projectCount: 0,
    enabledProjectCount: 0,
    dueProjectCount: 0,
    overdueProjectCount: 0,
    nextDueAt: null,
    lastSyncAt: null,
    enabledProjectIds: [],
    dueProjectIds: [],
    overdueProjectIds: [],
    projectSamples: [],
    notes: ["Fallback workspace auto-cruise health report."],
  };
}

export function fallbackWorkspaceBillingGatewayReport(): WorkspaceBillingSettlementGatewayReport {
  const now = new Date().toISOString();
  const routes: WorkspaceBillingSettlementGatewayPolicy["routes"] = [
    { providerName: "manual", enabled: true, fallbackProviderName: "manual", priority: 10, notes: ["Fallback manual settlement route."] },
    { providerName: "local", enabled: true, fallbackProviderName: "manual", priority: 20, notes: ["Fallback local settlement route."] },
    { providerName: "mock", enabled: true, fallbackProviderName: "manual", priority: 30, notes: ["Fallback mock settlement route."] },
  ];
  return {
    generatedAt: now,
    policy: {
      gatewayEnabled: false,
      defaultProviderName: "manual",
      fallbackProviderName: "manual",
      strictRouting: false,
      routes,
      notes: ["Fallback billing gateway policy is used when the API is unavailable."],
    },
    routeCount: routes.length,
    enabledRouteCount: routes.length,
    providerCount: 1,
    routeReadyCount: 0,
    gatewayReady: false,
    routes: routes.map((route) => ({
      providerName: route.providerName,
      enabled: route.enabled,
      fallbackProviderName: route.fallbackProviderName,
      resolvedProviderName: route.fallbackProviderName,
      priority: route.priority,
      routeReady: false,
      notes: route.notes,
    })),
    warnings: ["Fallback billing gateway is non-authoritative."],
    recommendations: ["Connect the API to a routed settlement gateway before executing payouts."],
  };
}

export function fallbackWorkspaceBillingGatewayHistoryReport(projectId?: string): WorkspaceBillingSettlementGatewayHistoryReport {
  const source = projectId ? fallbackProjects.find((item) => item.project.projectId === projectId) : fallbackProjects[0];
  const project = source?.project;
  const entry = {
    auditId: "billing-gateway-fallback",
    createdAt: new Date().toISOString(),
    actor: "fallback",
    projectId: project?.projectId ?? projectId ?? "fallback-project",
    projectName: project?.name ?? projectId ?? "fallback-project",
    requestPath: "/api/billing/gateway/history",
    requestMethod: "GET",
    dryRun: true,
    providerName: "manual",
    accountRef: null,
    currency: "USD",
    grossCents: 0,
    holdbackCents: 0,
    netCents: 0,
    dueCents: 0,
    status: "previewed",
    failureCode: null,
    retryable: false,
    transactionRef: null,
    message: "Fallback settlement gateway history uses demo data.",
    memo: null,
    settlementReady: false,
    gatewayProviderName: "manual",
    gatewayRouteProviderName: "manual",
    gatewayRouteFallbackProviderName: "manual",
    gatewayRoutePriority: 10,
    gatewayRouteReason: "Fallback settlement gateway history uses demo data.",
    gatewayReady: false,
    gatewayRouteReady: false,
    notes: ["Fallback settlement gateway history is non-authoritative."],
  } as WorkspaceBillingSettlementExecution;
  const entries = [entry];
  return {
    generatedAt: new Date().toISOString(),
    projectId: projectId ?? null,
    total: entries.length,
    projectCount: new Set(entries.map((item) => item.projectId).filter(Boolean)).size,
    gatewayReadyCount: entries.filter((item) => item.gatewayReady).length,
    gatewayRouteReadyCount: entries.filter((item) => item.gatewayRouteReady).length,
    dryRunCount: entries.filter((item) => item.dryRun).length,
    liveCount: entries.filter((item) => !item.dryRun).length,
    blockedCount: entries.filter((item) => item.status === "blocked" || item.status === "failed").length,
    failedCount: entries.filter((item) => item.status === "failed").length,
    latestProjectId: entry.projectId,
    latestProjectName: entry.projectName,
    latestGatewayProviderName: entry.gatewayProviderName,
    latestGatewayRouteProviderName: entry.gatewayRouteProviderName,
    latestGatewayRouteReason: entry.gatewayRouteReason,
    latestGatewayRoutePriority: entry.gatewayRoutePriority,
    latestFailureCode: entry.failureCode,
    latestRetryable: entry.retryable,
    entries,
  };
}

export function fallbackWorkspaceBillingGatewayProviderStatusReport(projectId?: string): WorkspaceBillingSettlementGatewayProviderStatusReport {
  const now = new Date().toISOString();
  const routes: WorkspaceBillingSettlementGatewayProviderStatus[] = [
    {
      providerName: "manual",
      providerLabel: "Manual",
      endpoint: null,
      configured: false,
      authConfigured: false,
      authHeader: "Authorization",
      authSource: "none",
      routeEnabled: true,
      fallbackProviderName: "manual",
      resolvedProviderName: "manual",
      priority: 10,
      routeReady: false,
      strictReady: false,
      fallbackReason: "Fallback billing gateway provider status uses demo data.",
      notes: ["Fallback manual settlement provider."],
    },
    {
      providerName: "local",
      providerLabel: "Local",
      endpoint: null,
      configured: false,
      authConfigured: false,
      authHeader: "Authorization",
      authSource: "none",
      routeEnabled: true,
      fallbackProviderName: "manual",
      resolvedProviderName: "manual",
      priority: 20,
      routeReady: false,
      strictReady: false,
      fallbackReason: "Fallback billing gateway provider status uses demo data.",
      notes: ["Fallback local settlement provider."],
    },
    {
      providerName: "mock",
      providerLabel: "Mock",
      endpoint: null,
      configured: false,
      authConfigured: false,
      authHeader: "Authorization",
      authSource: "none",
      routeEnabled: true,
      fallbackProviderName: "manual",
      resolvedProviderName: "manual",
      priority: 30,
      routeReady: false,
      strictReady: false,
      fallbackReason: "Fallback billing gateway provider status uses demo data.",
      notes: ["Fallback mock settlement provider."],
    },
  ];
  return {
    generatedAt: now,
    projectId: projectId ?? null,
    gatewayEnabled: false,
    providerCount: routes.length,
    configuredCount: 0,
    authConfiguredCount: 0,
    routeReadyCount: 0,
    strictReadyCount: 0,
    gatewayReady: false,
    entries: routes,
    warnings: ["Fallback billing gateway provider status is non-authoritative."],
    recommendations: ["Connect the API to a routed settlement gateway before executing payouts."],
  };
}

export function fallbackWorkspaceBillingSettlementProviderRequirementsReport() {
  return {
    generatedAt: new Date().toISOString(),
    providerCount: 13,
    entries: [
      {
        providerName: "paypal",
        providerLabel: "PayPal Payouts",
        destinationTypes: ["paypal_account", "recipient"],
        rails: [],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryEmail"],
        metadataFields: [],
        conditionalRequirements: [
          {
            whenField: "destinationType",
            whenValue: "recipient",
            requiredFields: [],
            metadataFields: ["recipientType"],
            notes: ["recipient payouts require metadata.recipientType."],
          },
        ],
        notes: ["Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "stripe",
        providerLabel: "Stripe Connect",
        destinationTypes: ["connected_account", "external_account"],
        rails: [],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef"],
        metadataFields: [],
        conditionalRequirements: [
          {
            whenField: "destinationType",
            whenValue: "external_account",
            requiredFields: [],
            metadataFields: ["externalAccountToken"],
            notes: ["external_account payouts require metadata.externalAccountToken."],
          },
        ],
        notes: ["Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "ach",
        providerLabel: "ACH Transfer",
        destinationTypes: ["bank_account"],
        rails: ["ach"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode", "rail"],
        metadataFields: ["companyEntryDescription"],
        conditionalRequirements: [],
        notes: ["Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "bank_transfer",
        providerLabel: "Bank Transfer",
        destinationTypes: ["bank_account"],
        rails: ["swift", "sepa", "wire"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode", "rail"],
        metadataFields: [],
        conditionalRequirements: [
          {
            whenField: "rail",
            whenValue: "swift",
            requiredFields: [],
            metadataFields: ["swiftCode"],
            notes: ["swift rail requires metadata.swiftCode."],
          },
          {
            whenField: "rail",
            whenValue: "sepa",
            requiredFields: [],
            metadataFields: ["iban"],
            notes: ["sepa rail requires metadata.iban."],
          },
          {
            whenField: "rail",
            whenValue: "wire",
            requiredFields: [],
            metadataFields: ["routingNumber"],
            notes: ["wire rail requires metadata.routingNumber."],
          },
        ],
        notes: ["Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "wise",
        providerLabel: "Wise Payouts",
        destinationTypes: ["bank_account"],
        rails: ["sepa", "swift", "local"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "payoneer",
        providerLabel: "Payoneer Payouts",
        destinationTypes: ["bank_account"],
        rails: ["local", "swift"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "airwallex",
        providerLabel: "Airwallex Transfers",
        destinationTypes: ["bank_account"],
        rails: ["local", "swift"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "tipalti",
        providerLabel: "Tipalti Payouts",
        destinationTypes: ["bank_account"],
        rails: ["local", "swift"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode", "rail"],
        metadataFields: [],
        conditionalRequirements: [
          {
            whenField: "rail",
            whenValue: "swift",
            requiredFields: ["rail"],
            metadataFields: ["swiftCode"],
            notes: ["swift rail requires metadata.swiftCode."],
          },
        ],
        notes: ["Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "hyperwallet",
        providerLabel: "Hyperwallet Payouts",
        destinationTypes: ["bank_account"],
        rails: ["local", "swift"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode", "rail"],
        metadataFields: [],
        conditionalRequirements: [
          {
            whenField: "rail",
            whenValue: "swift",
            requiredFields: ["rail"],
            metadataFields: ["swiftCode"],
            notes: ["swift rail requires metadata.swiftCode."],
          },
        ],
        notes: ["Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "ad_network",
        providerLabel: "Ad Network Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a projectId and real ad evidence.", "Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "adsense",
        providerLabel: "Google AdSense Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a projectId and real ad evidence.", "Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "gam",
        providerLabel: "Google Ad Manager Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a projectId and real ad evidence.", "Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "mediavine",
        providerLabel: "Mediavine Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a projectId and real ad evidence.", "Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "ezoic",
        providerLabel: "Ezoic Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a projectId and real ad evidence.", "Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "freestar",
        providerLabel: "Freestar Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a projectId and real ad evidence.", "Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "raptive",
        providerLabel: "Raptive Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a projectId and real ad evidence.", "Fallback billing requirements are non-authoritative."],
      },
      {
        providerName: "monumetric",
        providerLabel: "Monumetric Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a projectId and real ad evidence.", "Fallback billing requirements are non-authoritative."],
      },
    ],
    warnings: ["Fallback billing requirements are non-authoritative."],
    recommendations: ["Connect the API to fetch live settlement provider requirement profiles."],
  };
}

export function fallbackWorkspaceBillingReport(): WorkspaceBillingReport {
  const projects = fallbackProjects.map((item) => item.project);
  const tasks = fallbackProjects.map((item) => item.task);
  const now = new Date().toISOString();
  const activeProjectCount = projects.length;
  const taskCount = tasks.length;
  const runCount30d = tasks.reduce((count, task) => count + (task.status === "approved" || task.status === "deployed" ? 1 : 0), 0);
  const deployCount30d = tasks.filter((task) => task.status === "deployed").length;
  const rollbackCount30d = tasks.filter((task) => task.status === "rolled_back").length;
  const estimatedUsageCents = activeProjectCount * 750 + taskCount * 120 + runCount30d * 80 + deployCount30d * 240 + rollbackCount30d * 350;
  return {
    generatedAt: now,
    policy: {
      planTier: "growth",
      commercialModeEnabled: false,
      settlementEnabled: false,
      settlementProviderName: "manual",
      settlementAccountRef: null,
      settlementCurrency: "USD",
      settlementWindowDays: 30,
      settlementHoldbackPercent: 0,
      settlementPayoutThresholdCents: 10000,
      monthlyProjectLimit: 10,
      monthlyTaskLimit: 100,
      monthlyDeployLimit: 30,
      monthlyBudgetCents: 50000,
      overageBlocking: true,
      notes: ["Fallback billing policy is used when the API is unavailable."],
    },
    usage: {
      generatedAt: now,
      activeProjectCount,
      taskCount,
      runCount30d,
      deployCount30d,
      rollbackCount30d,
      autoDeployCount30d: 0,
      strictReadyProjectCount: 0,
      estimatedUsageCents,
      projectLimitUsedPercent: 0,
      taskLimitUsedPercent: 0,
      deployLimitUsedPercent: 0,
      budgetLimitUsedPercent: 0,
      overProjectLimit: false,
      overTaskLimit: false,
      overDeployLimit: false,
      overBudgetLimit: false,
      notes: ["Fallback billing usage is derived from the demo dashboard."],
    },
    settlement: {
      settlementEnabled: false,
      settlementProviderName: "manual",
      settlementAccountRef: null,
      settlementCurrency: "USD",
      settlementWindowDays: 30,
      settlementHoldbackPercent: 0,
      payoutThresholdCents: 10000,
      grossEstimatedCents: estimatedUsageCents,
      holdbackCents: 0,
      netSettlementCents: estimatedUsageCents,
      settlementDueCents: estimatedUsageCents,
      settlementReady: false,
      settlementBlocked: false,
      notes: ["Fallback settlement preview is derived from the demo dashboard."],
    },
    settlementGateway: fallbackWorkspaceBillingGatewayReport(),
    settlementGatewayHistory: fallbackWorkspaceBillingGatewayHistoryReport(),
    commercialReady: false,
    warnings: ["Fallback billing report is non-authoritative."],
    recommendations: ["Connect the API to persist billing policy and usage."],
  };
}

export function fallbackWorkspaceBillingSettlementExecutionReport(
  payload: WorkspaceBillingSettlementExecutionRequest,
): WorkspaceBillingSettlementExecutionReport {
  const billing = fallbackWorkspaceBillingReport();
  const now = new Date().toISOString();
  const projectNameById = new Map(fallbackProjects.map((item) => [item.project.projectId, item.project.name] as const));
  const grossCents = Math.max(0, Math.trunc(payload.amountCents ?? billing.settlement.grossEstimatedCents));
  const holdbackCents = Math.trunc((grossCents * billing.policy.settlementHoldbackPercent) / 100);
  const netCents = Math.max(0, grossCents - holdbackCents);
  const dryRun = payload.dryRun ?? true;
  return {
    generatedAt: now,
    billing,
    execution: {
      auditId: "billing-settlement-fallback-preview",
      createdAt: now,
      actor: "fallback",
      projectId: payload.projectId ?? null,
      projectName: payload.projectId ? projectNameById.get(payload.projectId) ?? payload.projectId : null,
      requestPath: "/api/billing/settlement/execute",
      requestMethod: "POST",
      dryRun,
      providerName: payload.providerName ?? billing.policy.settlementProviderName,
      accountRef: payload.accountRef ?? billing.policy.settlementAccountRef,
      destinationType: payload.destinationType ?? null,
      destinationRef: payload.destinationRef ?? null,
      beneficiaryName: payload.beneficiaryName ?? null,
      beneficiaryEmail: payload.beneficiaryEmail ?? null,
      rail: payload.rail ?? null,
      countryCode: payload.countryCode ?? null,
      metadata: payload.metadata ?? {},
      providerPayload: payload.providerPayload ?? {},
      currency: payload.currency ?? billing.policy.settlementCurrency,
      grossCents,
      holdbackCents,
      netCents,
      dueCents: netCents,
      status: dryRun ? "previewed" : "blocked",
      failureCode: dryRun ? null : "SETTLEMENT_FALLBACK_ONLY",
      retryable: !dryRun,
      transactionRef: null,
      message: dryRun ? "Fallback settlement preview completed." : "Fallback settlement execution is not available.",
      memo: payload.memo ?? null,
      settlementReady: false,
      gatewayProviderName: payload.providerName ?? billing.policy.settlementProviderName,
      gatewayRouteProviderName: payload.providerName ?? billing.policy.settlementProviderName,
      gatewayRouteFallbackProviderName: billing.settlementGateway?.policy.fallbackProviderName ?? "manual",
      gatewayRoutePriority: 100,
      gatewayRouteReason: dryRun ? "Fallback settlement preview records the current gateway route without provider execution." : "Fallback settlement execution is not available.",
      gatewayReady: false,
      gatewayRouteReady: false,
      notes: ["Fallback settlement execution uses the demo dashboard."],
    },
    warnings: ["Fallback settlement execution is non-authoritative."],
    recommendations: ["Connect the API to a settlement provider before executing payouts."],
  };
}

export function fallbackWorkspaceBillingSettlementExecutionHistoryReport(projectId?: string): WorkspaceBillingSettlementExecutionHistoryReport {
  const report = fallbackWorkspaceBillingSettlementExecutionReport({ dryRun: true, projectId: projectId ?? null });
  return {
    total: 1,
    entries: [report.execution],
  };
}

export function fallbackWorkspaceExperimentReport(): WorkspaceExperimentReport {
  const now = new Date().toISOString();
  const variants: WorkspaceExperimentVariant[] = [
    { variantName: "control", allocationPercent: 50, enabled: true, notes: ["Fallback control variant."] },
    { variantName: "treatment", allocationPercent: 50, enabled: true, notes: ["Fallback treatment variant."] },
  ];
  const experiments: WorkspaceExperiment[] = [
    {
      experimentKey: "homepage-cta",
      enabled: false,
      targetSurface: "site",
      targetLocale: "en-US",
      targetProjectIds: ["demo-project"],
      controlVariantName: "control",
      assignmentStrategy: "hash",
      primaryMetric: "click_through_rate",
      variants,
      notes: ["Fallback experiment policy is used when the API is unavailable."],
    },
  ];
  return {
    generatedAt: now,
    policy: {
      experimentsEnabled: false,
      strictAssignment: false,
      defaultAssignmentStrategy: "hash",
      experiments,
      notes: ["Fallback experiment policy is used when the API is unavailable."],
    },
    experimentCount: experiments.length,
    enabledExperimentCount: 0,
    readyExperimentCount: 0,
    variantCount: variants.length,
    balancedExperimentCount: 1,
    projectScopeCount: 1,
    workspaceReady: false,
    experiments: experiments.map((experiment) => ({
      experimentKey: experiment.experimentKey,
      enabled: experiment.enabled,
      targetSurface: experiment.targetSurface,
      targetLocale: experiment.targetLocale,
      targetProjectCount: experiment.targetProjectIds.length,
      variantCount: experiment.variants.length,
      totalAllocationPercent: experiment.variants.reduce((sum, variant) => sum + variant.allocationPercent, 0),
      balancedAllocation: true,
      controlVariantPresent: true,
      experimentReady: false,
      warnings: ["Workspace experiments are disabled."],
      notes: experiment.notes,
    })),
    warnings: ["Fallback experiment report is non-authoritative."],
    recommendations: ["Enable the experiment policy and bind at least one controlled rollout."],
  };
}

export function fallbackWorkspaceExperimentAssignmentReport(
  payload: WorkspaceExperimentAssignmentRequest,
): WorkspaceExperimentAssignmentReport {
  const report = fallbackWorkspaceExperimentReport();
  const subjectKey = (payload.subjectKey || payload.projectId || payload.sessionKey || "workspace:default").trim() || "workspace:default";
  const targetLocale = payload.targetLocale?.trim() || null;
  const targetSurface = payload.targetSurface;
  return {
    generatedAt: new Date().toISOString(),
    policy: report.policy,
    projectId: payload.projectId ?? null,
    subjectKey,
    sessionKey: payload.sessionKey ?? null,
    targetSurface,
    targetLocale,
    experimentCount: report.policy.experiments.length,
    matchedExperimentCount: 1,
    assignedExperimentCount: 0,
    strictAssignment: report.policy.strictAssignment,
    assignments: report.policy.experiments.map((experiment) => ({
      experimentKey: experiment.experimentKey,
      enabled: experiment.enabled,
      targetSurface: experiment.targetSurface,
      targetLocale: experiment.targetLocale,
      targetProjectMatch: true,
      assignmentStrategy: experiment.assignmentStrategy,
      subjectKey,
      bucketKey: `${experiment.experimentKey}|${subjectKey}`,
      bucketRoll: 0,
      bucketSize: 100,
      eligible: false,
      controlVariantName: experiment.controlVariantName,
      assignedVariantName: null,
      assignedVariantIndex: null,
      variantCount: experiment.variants.length,
      totalAllocationPercent: experiment.variants.reduce((sum, variant) => sum + variant.allocationPercent, 0),
      warnings: ["Fallback experiment assignment is non-authoritative."],
      notes: experiment.notes,
    })),
    warnings: ["Fallback experiment assignment report is non-authoritative."],
    recommendations: ["Enable the experiment policy and use the API to preview a runtime assignment."],
  };
}

export function fallbackWorkspaceLocalizationReport(): WorkspaceLocalizationReport {
  const now = new Date().toISOString();
  const clusters: WorkspaceSiteCluster[] = [
    {
      clusterKey: "global-site",
      enabled: false,
      canonicalProjectId: "demo-project",
      projectIds: ["demo-project"],
      supportedLocales: ["en-US", "fr-FR"],
      primaryLocale: "en-US",
      localeStrategy: "path",
      notes: ["Fallback localization cluster."],
    },
  ];
  return {
    generatedAt: now,
    policy: {
      localizationEnabled: false,
      strictLocalization: false,
      defaultLocale: "en-US",
      defaultLanguage: "en",
      clusters,
      notes: ["Fallback localization policy is used when the API is unavailable."],
    },
    clusterCount: clusters.length,
    enabledClusterCount: 0,
    readyClusterCount: 0,
    projectCount: 1,
    localeCount: 2,
    workspaceReady: false,
    clusters: clusters.map((cluster) => ({
      clusterKey: cluster.clusterKey,
      enabled: cluster.enabled,
      canonicalProjectId: cluster.canonicalProjectId,
      projectCount: cluster.projectIds.length,
      localeCount: cluster.supportedLocales.length,
      supportedLocaleCount: cluster.supportedLocales.length,
      hasCanonicalProject: true,
      localeCoverageReady: true,
      clusterReady: false,
      warnings: ["Workspace localization is disabled."],
      notes: cluster.notes,
    })),
    warnings: ["Fallback localization report is non-authoritative."],
    recommendations: ["Enable localization policy and bind a canonical project plus locale variants."],
  };
}

export function fallbackWorkspaceLocalizationAssignmentReport(
  payload: WorkspaceLocalizationAssignmentRequest,
): WorkspaceLocalizationAssignmentReport {
  const report = fallbackWorkspaceLocalizationReport();
  const subjectKey = (payload.subjectKey || payload.projectId || payload.targetLocale || payload.host || "workspace:default").trim() || "workspace:default";
  const targetLocale = payload.targetLocale?.trim() || report.policy.defaultLocale;
  return {
    generatedAt: new Date().toISOString(),
    policy: report.policy,
    projectId: payload.projectId ?? null,
    targetLocale,
    host: payload.host ?? null,
    subjectKey,
    clusterCount: report.policy.clusters.length,
    matchedClusterCount: 0,
    assignedClusterCount: 0,
    strictLocalization: report.policy.strictLocalization,
    assignments: report.policy.clusters.map((cluster) => ({
      clusterKey: cluster.clusterKey,
      enabled: cluster.enabled,
      localeStrategy: cluster.localeStrategy,
      subjectKey,
      projectId: payload.projectId ?? null,
      targetLocale,
      matchedByProject: false,
      matchedByLocale: false,
      matchedByHost: false,
      canonicalProjectId: cluster.canonicalProjectId,
      projectCount: cluster.projectIds.length,
      localeCount: cluster.supportedLocales.length,
      clusterReady: false,
      routePrefix: cluster.localeStrategy === "subdomain" ? `${targetLocale}.${cluster.clusterKey}` : cluster.localeStrategy === "cctld" ? `${cluster.clusterKey}.${targetLocale.split("-")[0]}` : `/${targetLocale}`,
      warnings: ["Fallback localization assignment is non-authoritative."],
      notes: cluster.notes,
    })),
    warnings: ["Fallback localization assignment report is non-authoritative."],
    recommendations: ["Enable localization policy and use the API to preview a runtime cluster assignment."],
  };
}

export function fallbackRuntimeRouteReport(projectId: string, payload: RuntimeRouteRequest): RuntimeRouteReport {
  const taskId = (payload.taskId || `${projectId}-task`).trim() || `${projectId}-task`;
  const experimentAssignment = fallbackWorkspaceExperimentAssignmentReport({
    projectId,
    subjectKey: payload.subjectKey || taskId,
    targetSurface: payload.targetSurface,
    targetLocale: payload.targetLocale ?? "en-US",
  });
  const localizationAssignment = fallbackWorkspaceLocalizationAssignmentReport({
    projectId,
    targetLocale: payload.targetLocale ?? "en-US",
    host: payload.host ?? `${projectId}.example`,
    subjectKey: payload.subjectKey || taskId,
  });
  return {
    generatedAt: new Date().toISOString(),
    projectId,
    taskId,
    subjectKey: payload.subjectKey || taskId,
    requestPath: payload.requestPath ?? `/api/projects/${projectId}/runtime-route`,
    requestMethod: payload.requestMethod ?? "POST",
    targetSurface: payload.targetSurface,
    targetLocale: payload.targetLocale ?? "en-US",
    host: payload.host ?? `${projectId}.example`,
    experimentAssignment,
    localizationAssignment,
    gatewayReport: fallbackWorkspaceModelGatewayReport(),
    resolvedProviders: {
      read: "fallback",
      seo: "fallback",
      ad: "fallback",
      deploy: "fallback",
      observe: "fallback",
    },
    gatewayRouteProviderName: "local",
    gatewayRouteFallbackProviderName: "local",
    gatewayRoutePriority: 10,
    runtimeReady: false,
    executionMode: "preview",
    executionAction: "serve_preview",
    executionReason: "Fallback runtime route report is non-authoritative.",
    executionEntrypoint: payload.requestPath ?? `/api/projects/${projectId}/runtime-route`,
    warnings: ["Fallback runtime route report is non-authoritative."],
    recommendations: ["Enable experiments, localization, and model gateway routing for runtime readiness."],
  };
}

export function fallbackWorkspaceRuntimeRouteHealthReport(projectId?: string): WorkspaceRuntimeRouteHealthReport {
  const generatedAt = new Date().toISOString();
  const projectEntries = projectId ? fallbackProjects.filter((item) => item.project.projectId === projectId) : fallbackProjects;
  const items: WorkspaceRuntimeRouteHealthItem[] = [
  ];
  for (const item of projectEntries.slice(0, 1)) {
    items.push({
      projectId: item.project.projectId,
      projectName: item.project.name,
      runtimeReady: false,
      runtimeSummary: "runtimeReady=false|experimentVariant=unassigned|localizationCluster=unassigned|gateway=local|gatewayRouteProvider=local|gatewayRouteFallbackProvider=local|gatewayRoutePriority=10",
      requestPath: `/api/projects/${item.project.projectId}/sync`,
      requestMethod: "POST",
      experimentVariant: "unassigned",
      localizationCluster: "unassigned",
      gatewayProviderName: "local",
      gatewayReady: false,
      executionMode: "preview",
      executionAction: "serve_preview",
      executionReason: "Fallback runtime route history uses demo data.",
      executionEntrypoint: `/api/projects/${item.project.projectId}/sync`,
    });
  }
  if (items.length === 0) {
    items.push({
      projectId: "demo-project",
      projectName: "Demo Project",
      runtimeReady: false,
      runtimeSummary: "runtimeReady=false|experimentVariant=unassigned|localizationCluster=unassigned|gateway=local|gatewayRouteProvider=local|gatewayRouteFallbackProvider=local|gatewayRoutePriority=10",
      requestPath: "/api/projects/demo-project/sync",
      requestMethod: "POST",
      experimentVariant: "unassigned",
      localizationCluster: "unassigned",
      gatewayProviderName: "local",
      gatewayRouteProviderName: "local",
      gatewayRouteFallbackProviderName: "local",
      gatewayRoutePriority: 10,
      gatewayReady: false,
      executionMode: "preview",
      executionAction: "serve_preview",
      executionReason: "Fallback runtime route history uses demo data.",
      executionEntrypoint: "/api/projects/demo-project/sync",
    });
  }
  return {
    generatedAt,
    projectCount: items.length,
    runtimeReadyCount: 0,
    previewOnlyCount: items.length,
    gatewayReadyCount: 0,
    strictReadyCount: 0,
    runtimeReadyRatePercent: 0,
    gatewayReadyRatePercent: 0,
    readyProjectIds: [],
    previewOnlyProjectIds: items.map((item) => item.projectId),
    items,
    notes: ["Fallback runtime route health report is non-authoritative.", "Enable experiments, localization, and model gateway routing for runtime readiness."],
  };
}

export function fallbackWorkspaceRuntimeRouteHistoryReport(limit = 20, projectId?: string): WorkspaceRuntimeRouteHistoryReport {
  const entries: WorkspaceRuntimeRouteHistoryItem[] = [];
  const projectEntries = projectId ? fallbackProjects.filter((item) => item.project.projectId === projectId) : fallbackProjects;
  for (const item of projectEntries.slice(0, Math.max(1, Math.min(100, limit)))) {
    const project = item.project;
    const run = sampleRuns(project.projectId, project.siteClass)[0];
    entries.push({
      projectId: project.projectId,
      projectName: project.name,
      runId: run.runId,
      taskId: run.taskId,
      trigger: run.trigger,
      status: run.status,
      startedAt: run.startedAt,
      runtimeReady: run.runtimeRouteReady,
      runtimeSummary: run.runtimeRouteSummary,
      requestPath: run.runtimeRouteRequestPath,
      requestMethod: run.runtimeRouteRequestMethod,
      experimentVariant: run.runtimeRouteReady ? "control" : "unassigned",
      localizationCluster: run.runtimeRouteReady ? "global" : "unassigned",
      gatewayProviderName: "local",
      gatewayRouteProviderName: "local",
      gatewayRouteFallbackProviderName: "local",
      gatewayRoutePriority: 10,
      gatewayReady: run.runtimeRouteReady,
      executionMode: run.runtimeRouteReady ? "runtime" : "preview",
      executionAction: run.runtimeRouteReady ? "serve_runtime" : "serve_preview",
      executionReason: run.runtimeRouteReady
        ? "Fallback runtime route history indicates runtime-ready execution."
        : "Fallback runtime route history uses demo data.",
      executionEntrypoint: run.runtimeRouteRequestPath ?? `/api/projects/${project.projectId}/sync`,
    });
  }
  return {
    generatedAt: new Date().toISOString(),
    total: entries.length,
    runtimeReadyCount: entries.filter((entry) => entry.runtimeReady).length,
    previewOnlyCount: entries.filter((entry) => !entry.runtimeReady).length,
    items: entries,
  };
}

export function fallbackWorkspaceTemplateMarketReport(): WorkspaceTemplateMarketReport {
  const now = new Date().toISOString();
  const templates: WorkspaceTemplateMarketTemplate[] = [
    {
      templateKey: "content-hub",
      enabled: false,
      templateSurface: "content",
      targetLocale: "en-US",
      targetProjectIds: ["demo-project"],
      coverageRequirements: ["pillar:/", "content_type:informational"],
      templateSource: "workspace",
      notes: ["Fallback template market package."],
    },
  ];
  return {
    generatedAt: now,
    policy: {
      marketEnabled: false,
      strictMarket: false,
      defaultTemplateSurface: "content",
      templates,
      notes: ["Fallback template market policy is used when the API is unavailable."],
    },
    templateCount: templates.length,
    enabledTemplateCount: 0,
    readyTemplateCount: 0,
    projectScopeCount: 1,
    workspaceReady: false,
    templates: templates.map((template) => ({
      templateKey: template.templateKey,
      enabled: template.enabled,
      templateSurface: template.templateSurface,
      targetLocale: template.targetLocale,
      targetProjectCount: template.targetProjectIds.length,
      coverageRequirementCount: template.coverageRequirements.length,
      coverageReady: false,
      templateReady: false,
      warnings: ["Template market is disabled."],
      notes: template.notes,
    })),
    warnings: ["Fallback template market report is non-authoritative."],
    recommendations: ["Enable the template market and bind coverage requirements to real projects."],
  };
}

export function fallbackWorkspaceModelGatewayReport(): WorkspaceModelGatewayReport {
  const now = new Date().toISOString();
  const routes: WorkspaceModelGatewayPolicy["routes"] = [
    { routeSuite: "read", providerName: "local", enabled: false, fallbackProviderName: "local", priority: 10, notes: ["Fallback routing"] },
    { routeSuite: "seo", providerName: "local", enabled: false, fallbackProviderName: "local", priority: 20, notes: ["Fallback routing"] },
    { routeSuite: "ad", providerName: "local", enabled: false, fallbackProviderName: "local", priority: 30, notes: ["Fallback routing"] },
    { routeSuite: "deploy", providerName: "local", enabled: false, fallbackProviderName: "local", priority: 40, notes: ["Fallback routing"] },
    { routeSuite: "observe", providerName: "local", enabled: false, fallbackProviderName: "local", priority: 50, notes: ["Fallback routing"] },
  ];
  return {
    generatedAt: now,
    policy: {
      gatewayEnabled: false,
      defaultProviderName: "local",
      fallbackProviderName: "local",
      strictRouting: false,
      routes,
      notes: ["Fallback model gateway policy is used when the API is unavailable."],
    },
    routeCount: routes.length,
    enabledRouteCount: 0,
    providerCount: 1,
    suiteCount: 5,
    routeReadyCount: 0,
    gatewayReady: false,
    routes: routes.map((route) => ({
      ...route,
      resolvedProviderName: route.fallbackProviderName,
      routeReady: false,
    })),
    warnings: ["Fallback model gateway report is non-authoritative."],
    recommendations: ["Enable and configure the model gateway policy to route suite-specific prompts."],
  };
}

export function fallbackWorkspaceModelGatewayProviderStatusReport(projectId?: string): WorkspaceModelGatewayProviderStatusReport {
  const now = new Date().toISOString();
  const entries: WorkspaceModelGatewayProviderStatus[] = [
    {
      routeSuite: "read",
      providerName: "local",
      providerLabel: "Local",
      enabled: true,
      fallbackProviderName: "local",
      resolvedProviderName: "local",
      priority: 10,
      routeReady: false,
      strictReady: false,
      fallbackReason: "Fallback model gateway provider status uses demo data.",
      notes: ["Fallback read routing."],
    },
    {
      routeSuite: "seo",
      providerName: "local",
      providerLabel: "Local",
      enabled: true,
      fallbackProviderName: "local",
      resolvedProviderName: "local",
      priority: 20,
      routeReady: false,
      strictReady: false,
      fallbackReason: "Fallback model gateway provider status uses demo data.",
      notes: ["Fallback SEO routing."],
    },
    {
      routeSuite: "ad",
      providerName: "local",
      providerLabel: "Local",
      enabled: true,
      fallbackProviderName: "local",
      resolvedProviderName: "local",
      priority: 30,
      routeReady: false,
      strictReady: false,
      fallbackReason: "Fallback model gateway provider status uses demo data.",
      notes: ["Fallback AD routing."],
    },
    {
      routeSuite: "deploy",
      providerName: "local",
      providerLabel: "Local",
      enabled: true,
      fallbackProviderName: "local",
      resolvedProviderName: "local",
      priority: 40,
      routeReady: false,
      strictReady: false,
      fallbackReason: "Fallback model gateway provider status uses demo data.",
      notes: ["Fallback deploy routing."],
    },
    {
      routeSuite: "observe",
      providerName: "local",
      providerLabel: "Local",
      enabled: true,
      fallbackProviderName: "local",
      resolvedProviderName: "local",
      priority: 50,
      routeReady: false,
      strictReady: false,
      fallbackReason: "Fallback model gateway provider status uses demo data.",
      notes: ["Fallback observability routing."],
    },
  ];
  return {
    generatedAt: now,
    projectId: projectId ?? null,
    gatewayEnabled: false,
    providerCount: 1,
    routeCount: entries.length,
    routeReadyCount: 0,
    strictReadyCount: 0,
    gatewayReady: false,
    entries,
    warnings: ["Fallback model gateway provider status is non-authoritative."],
    recommendations: ["Connect the API to a routed model gateway before using orchestration."],
  };
}

export function fallbackRuntimeEdgeGatewayProviderStatusReport(projectId?: string): RuntimeEdgeGatewayProviderStatusReport {
  const now = new Date().toISOString();
  const entries: RuntimeEdgeGatewayProviderStatus[] = [
    {
      providerName: "runtime_edge",
      providerLabel: "Runtime Edge",
      enabled: true,
      fallbackProviderName: "runtime_edge",
      resolvedProviderName: "runtime_edge",
      priority: 10,
      routeReady: false,
      strictReady: false,
      endpoint: null,
      authHeader: "Authorization",
      authConfigured: false,
      fallbackReason: "Fallback runtime-edge provider status uses demo data.",
      notes: ["Fallback runtime-edge routing."],
    },
  ];
  return {
    generatedAt: now,
    projectId: projectId ?? null,
    gatewayEnabled: false,
    providerCount: 1,
    routeCount: entries.length,
    routeReadyCount: 0,
    strictReadyCount: 0,
    gatewayReady: false,
    entries,
    warnings: ["Fallback runtime-edge provider status is non-authoritative."],
    recommendations: ["Connect the API to a routed runtime-edge gateway before publishing."],
  };
}

export function fallbackVisualFarmGatewayProviderStatusReport(projectId?: string): VisualFarmGatewayProviderStatusReport {
  const now = new Date().toISOString();
  const entries: VisualFarmGatewayProviderStatus[] = [
    {
      providerName: "visual_farm",
      providerLabel: "Visual Farm",
      enabled: true,
      fallbackProviderName: "visual_farm",
      resolvedProviderName: "visual_farm",
      priority: 10,
      routeReady: false,
      strictReady: false,
      endpoint: null,
      authHeader: "Authorization",
      authConfigured: false,
      fallbackReason: "Fallback visual-farm provider status uses demo data.",
      notes: ["Fallback visual-farm routing."],
    },
  ];
  return {
    generatedAt: now,
    projectId: projectId ?? null,
    gatewayEnabled: false,
    providerCount: 1,
    routeCount: entries.length,
    routeReadyCount: 0,
    strictReadyCount: 0,
    gatewayReady: false,
    entries,
    warnings: ["Fallback visual-farm provider status is non-authoritative."],
    recommendations: ["Connect the API to a routed visual-farm gateway before publishing."],
  };
}

export function fallbackWorkspaceModelGatewayHistoryReport(projectId?: string): WorkspaceModelGatewayHistoryReport {
  const runtimeHistory = fallbackWorkspaceRuntimeRouteHistoryReport(20, projectId);
  const entries = runtimeHistory.items;
  const latest = entries[0] ?? null;
  return {
    generatedAt: new Date().toISOString(),
    projectId: projectId ?? null,
    total: entries.length,
    projectCount: new Set(entries.map((item) => item.projectId).filter(Boolean)).size,
    runtimeReadyCount: entries.filter((item) => item.runtimeReady).length,
    previewOnlyCount: entries.filter((item) => !item.runtimeReady).length,
    gatewayReadyCount: entries.filter((item) => item.gatewayReady).length,
    routeReadyCount: entries.filter((item) => item.gatewayReady).length,
    latestProjectId: latest?.projectId ?? null,
    latestProjectName: latest?.projectName ?? null,
    latestRequestPath: latest?.requestPath ?? null,
    latestRequestMethod: latest?.requestMethod ?? null,
    latestExecutionMode: latest?.executionMode ?? null,
    latestExecutionAction: latest?.executionAction ?? null,
    latestExecutionReason: latest?.executionReason ?? null,
    latestExecutionEntrypoint: latest?.executionEntrypoint ?? null,
    latestGatewayProviderName: latest?.gatewayProviderName ?? null,
    latestGatewayRouteProviderName: latest?.gatewayRouteProviderName ?? null,
    latestGatewayRouteFallbackProviderName: latest?.gatewayRouteFallbackProviderName ?? null,
    latestGatewayRouteReason: latest?.executionReason ?? null,
    latestGatewayRoutePriority: latest?.gatewayRoutePriority ?? null,
    entries,
  };
}

export function fallbackProjectCruiseHealthReport(projectId: string): ProjectCruiseHealthReport {
  return {
    reportId: "fallback-project-cruise-health",
    projectId,
    generatedAt: new Date().toISOString(),
    autoCruiseEnabled: false,
    connectionHealth: "unknown",
    syncIntervalMinutes: 60,
    lastSyncAt: null,
    nextSyncAt: null,
    dueNow: false,
    overdue: false,
    lastRunStatus: "idle",
    projectSample: {
      projectId,
      name: "Fallback project",
      url: "https://example.com",
      autoCruiseEnabled: false,
      connectionHealth: "unknown",
      syncIntervalMinutes: 60,
      lastSyncAt: null,
      nextSyncAt: null,
      dueNow: false,
      overdue: false,
      lastRunStatus: "idle",
    },
    notes: ["Fallback project auto-cruise health report."],
  };
}

export function fallbackAcceptanceHistoryReport(): AcceptanceHistoryReport {
  const report = fallbackAcceptanceReport();
  return {
    generatedAt: new Date().toISOString(),
    total: 1,
    limit: 20,
    entries: [
      {
        reportId: report.reportId,
        generatedAt: report.generatedAt,
        passed: report.passed,
        failedGateIds: report.gates.filter((item) => !item.passed).map((item) => item.gateId),
        failedGateCount: report.gates.filter((item) => !item.passed).length,
        report,
      },
    ],
  };
}

export function fallbackVisualRegressionReport(): VisualRegressionReport {
  const sampleSet = fallbackRegressionSampleSet();
  return {
    reportId: "fallback-visual-regress",
    generatedAt: new Date().toISOString(),
    sampleCount: sampleSet.sampleCount,
    passCount: sampleSet.sampleCount,
    failCount: 0,
    averageDiffPercent: 1.4,
    cases: sampleSet.samples.map((sample) => ({
      sampleId: sample.sampleId,
      name: sample.name,
      pageUrl: sample.intake.url,
      projectId: `${sample.sampleId}-project`,
      projectName: sample.name,
      workflowTaskId: `${sample.sampleId}-task`,
      deploymentArtifactRef: `artifact://deployments/${sample.sampleId}`,
      baselineLabel: "baseline preview",
      previewLabel: "generated preview",
      expectedMaxDiffPercent: sample.expectedRiskBand === "high" ? 2 : sample.expectedAdAllowed ? 2.5 : 2.2,
      actualDiffPercent: sample.expectedRiskBand === "high" ? 1.1 : sample.expectedAdAllowed ? 1.8 : 2.1,
      artifactRef: `visual://fallback/${sample.sampleId}`,
      taskId: `visual-task-${sample.sampleId}`,
      executionMode: "manifest",
      baselineArtifactRef: `visual://fallback/${sample.sampleId}/baseline`,
      previewArtifactRef: `visual://fallback/${sample.sampleId}/preview`,
      diffArtifactRef: `visual://fallback/${sample.sampleId}/diff`,
      visualFarmProvider: "fallback-manifest",
      visualFarmRunId: `visual-fallback-${sample.sampleId}`,
      visualFarmEndpoint: "fallback://visual-manifest",
      visualFarmLatencyMs: 0,
      visualFarmStrictBlocked: false,
      screenshotCount: 2,
      ctaPreserved: true,
      layoutShiftRisk: sample.expectedRiskBand === "high" ? "low" : "medium",
      passed: true,
      notes: ["Fallback visual regression manifest."],
    })),
    notes: ["Fallback visual regression report used when the API is unavailable."],
  };
}

export function fallbackVisualRegressionRunsReport(): VisualRegressionRunsReport {
  const visual = fallbackVisualRegressionReport();
  return {
    generatedAt: new Date().toISOString(),
    runs: [
      {
        runId: "visual-run-fallback-1",
        executedAt: new Date().toISOString(),
        sampleCount: visual.sampleCount,
        passCount: visual.passCount,
        failCount: visual.failCount,
        averageDiffPercent: visual.averageDiffPercent,
        strictMode: false,
        farmProvider: "fallback-manifest",
        connectedCaseCount: 0,
        strictBlockedCaseCount: 0,
        failedCaseCount: 0,
        fallbackCaseCount: visual.sampleCount,
        notConfiguredCaseCount: 0,
        configuredEndpointCount: 0,
        configuredEndpoints: [],
        attemptedEndpointCount: 0,
        attemptedEndpoints: [],
        failedEndpoints: [],
        providerAttemptCount: 0,
        averageFarmLatencyMs: 0,
        cases: visual.cases,
      },
    ],
  };
}

export function fallbackVisualRegressionHealthReport(): VisualRegressionHealthReport {
  const runs = fallbackVisualRegressionRunsReport();
  const latest = runs.runs[0];
  return {
    generatedAt: new Date().toISOString(),
    strictMode: false,
    configuredEndpointCount: latest?.configuredEndpointCount ?? 0,
    configuredEndpoints: latest?.configuredEndpoints ?? [],
    runCount: runs.runs.length,
    lastRunId: latest?.runId ?? null,
    lastRunExecutedAt: latest?.executedAt ?? null,
    lastRunConnectedCaseCount: latest?.connectedCaseCount ?? 0,
    lastRunFailedCaseCount: latest?.failedCaseCount ?? 0,
    lastRunFallbackCaseCount: latest?.fallbackCaseCount ?? 0,
    lastRunNotConfiguredCaseCount: latest?.notConfiguredCaseCount ?? 0,
    lastRunStrictBlockedCaseCount: latest?.strictBlockedCaseCount ?? 0,
    lastRunAttemptedEndpointCount: latest?.attemptedEndpointCount ?? 0,
    lastRunFailedEndpoints: latest?.failedEndpoints ?? [],
    failureBuckets: [
      {
        category: "unavailable",
        count: latest?.fallbackCaseCount ?? 0,
        retryable: true,
        failureCodes: ["VISUAL_FARM_FALLBACK"],
        sampleIds: latest?.cases.map((item) => item.sampleId) ?? [],
        suggestedAction: "Retry visual run after enabling visual farm provider.",
        quickActionPath: "/monitor?focus=retry&category=network",
      },
    ],
    notes: ["Fallback visual regression health report."],
  };
}

export function fallbackVisualFarmStatusReport(): VisualFarmStatusReport {
  const health = fallbackVisualRegressionHealthReport();
  return {
    generatedAt: new Date().toISOString(),
    strictMode: health.strictMode,
    configuredEndpointCount: health.configuredEndpointCount,
    configuredEndpoints: health.configuredEndpoints,
    accessTokenConfigured: false,
    timeoutMs: 12000,
    runCount: health.runCount,
    lastRunId: health.lastRunId,
    lastRunExecutedAt: health.lastRunExecutedAt,
    lastRunConnectedCaseCount: health.lastRunConnectedCaseCount,
    lastRunFailedCaseCount: health.lastRunFailedCaseCount,
    lastRunFallbackCaseCount: health.lastRunFallbackCaseCount,
    lastRunNotConfiguredCaseCount: health.lastRunNotConfiguredCaseCount,
    lastRunStrictBlockedCaseCount: health.lastRunStrictBlockedCaseCount,
    probeFreshnessMinutes: 30,
    lastProbeExecutedAt: null,
    lastProbeConnectedCount: 0,
    lastProbeFailedCount: 0,
    lastProbeBlockingCount: 0,
    lastProbeRecoverableCount: 0,
    probeFresh: false,
    probeStale: true,
    strictPublishReady: false,
    failureBuckets: health.failureBuckets,
    notes: ["Fallback visual farm status used when the API is unavailable."],
  };
}

export function fallbackVisualFarmProbeReport(): VisualFarmProbeReport {
  return {
    generatedAt: new Date().toISOString(),
    strictMode: false,
    configuredEndpointCount: 0,
    probedEndpointCount: 0,
    connectedCount: 0,
    failedCount: 0,
    notConfiguredCount: 1,
    blockingCount: 1,
    recoverableCount: 0,
    accessTokenConfigured: false,
    timeoutMs: 12000,
    probes: [],
    notes: ["Fallback visual farm probe used when the API is unavailable."],
  };
}

export function fallbackVisualFarmProbeHistoryReport(): VisualFarmProbeHistoryReport {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    entries: [
      {
        auditId: "fallback-visual-farm-probe-1",
        actor: "system:fallback",
        createdAt: now,
        strictMode: false,
        configuredEndpointCount: 0,
        probedEndpointCount: 0,
        connectedCount: 0,
        failedCount: 0,
        notConfiguredCount: 1,
        blockingCount: 1,
        recoverableCount: 0,
        accessTokenConfigured: false,
        timeoutMs: 12000,
        probes: [],
        notes: ["Fallback visual farm probe history used when API is unavailable."],
        spanId: "span_fallback",
        traceId: "trace_fallback",
      },
    ],
  };
}

export function fallbackVisualRegressionRemediationReport(): VisualRegressionRemediationReport {
  const visual = fallbackVisualRegressionReport();
  return {
    reportId: "fallback-visual-remediation-report",
    generatedAt: new Date().toISOString(),
    itemCount: 1,
    items: [
      {
        remediationId: "fallback-visual-remediation-1",
        category: "unavailable",
        failureCode: "VISUAL_FARM_FALLBACK",
        priority: "p1",
        action: "启用 visual farm provider 后重跑视觉回归。",
        rationale: "当前仅有 fallback 证据，不能作为生产发布依据。",
        blocking: false,
        affectedCases: visual.sampleCount,
        affectedProjects: visual.sampleCount,
        projectIds: visual.cases.map((item) => item.projectId).filter((item): item is string => Boolean(item)),
        quickActionPath: "/settings?focus=visual-farm",
        quickActionLabel: "配置 visual farm",
        retryRequestTemplate: {
          categories: ["unavailable"],
          retryableOnly: true,
          maxCases: visual.sampleCount,
        },
      },
    ],
    notes: ["Fallback visual remediation report used when the API is unavailable."],
  };
}

export function fallbackVisualRegressionRunHistoryReport(): VisualRegressionRunHistoryReport {
  return {
    generatedAt: new Date().toISOString(),
    entries: [
      {
        auditId: "fallback-visual-run-history-1",
        actor: "system:fallback",
        createdAt: new Date().toISOString(),
        strictMode: false,
        projectIds: ["fallback-project-1", "fallback-project-2"],
        maxCases: 12,
        runCount: 1,
        caseCount: 12,
        runIds: ["visual-run-fallback-1"],
        notes: ["Fallback visual run history used when API is unavailable."],
      },
    ],
  };
}

export function fallbackSkillRegressionReport(): SkillRegressionReport {
  const skillCases = [
    {
      skillId: "read/site-sniffer",
      suite: "read",
      name: "Site Sniffer",
      destructive: false,
      requiredApproval: false,
      rollbackSupported: false,
      observabilityReady: true,
      failureContractPresent: true,
      passed: true,
      notes: ["read-only profile extraction"],
    },
    {
      skillId: "seo/technical-seo-patcher",
      suite: "seo",
      name: "Technical SEO Patcher",
      destructive: true,
      requiredApproval: true,
      rollbackSupported: true,
      observabilityReady: true,
      failureContractPresent: true,
      passed: true,
      notes: ["destructive write path with rollback"],
    },
    {
      skillId: "deploy/rollback-executor",
      suite: "deploy",
      name: "Rollback Executor",
      destructive: true,
      requiredApproval: true,
      rollbackSupported: true,
      observabilityReady: true,
      failureContractPresent: true,
      passed: true,
      notes: ["explicit reversal path"],
    },
  ];
  return {
    reportId: "fallback-skill-regress",
    generatedAt: new Date().toISOString(),
    sampleCount: skillCases.length,
    passCount: skillCases.length,
    failCount: 0,
    destructiveCount: 2,
    rollbackSupportedCount: 2,
    cases: skillCases,
    notes: ["Fallback skill regression report used when the API is unavailable."],
  };
}
