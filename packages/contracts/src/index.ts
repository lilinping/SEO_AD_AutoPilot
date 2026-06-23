export type SiteClass =
  | "ecommerce"
  | "content"
  | "saas"
  | "tool"
  | "local"
  | "brand"
  | "ymyl";

export type DeploymentMode = "github_pr" | "cms_draft" | "universal_script" | "static_export";
export type ApprovalStatus = "pending" | "approved" | "rejected";
export type ConnectorKind = "search_console" | "ga4" | "github" | "cms" | "script_api" | "ad_network" | "sitemap" | "playwright" | "trend" | "news" | "qa";
export type ConnectorStatus = "connected" | "missing_credentials" | "unavailable" | "synthetic" | "error";
export type ConnectionHealth = "healthy" | "degraded" | "unavailable" | "unknown";
export type RunTrigger = "manual" | "schedule" | "approval" | "deploy" | "monitor" | "rollback";
export type RunStatus = "queued" | "running" | "completed" | "failed" | "rolled_back";
export type WorkflowStage =
  | "queued"
  | "sensing"
  | "profiled"
  | "planned"
  | "previewed"
  | "awaiting_approval"
  | "approved"
  | "deployed"
  | "monitoring"
  | "rolled_back"
  | "closed"
  | "rejected";

export type SkillSuite = "read" | "seo" | "ad" | "deploy" | "observe";

export interface SiteIntake {
  url: string;
  siteName?: string;
  repoUrl?: string;
  cmsName?: string;
  sitemapUrls?: string[];
  searchConsole?: Record<string, unknown>;
  ga4?: Record<string, unknown>;
  keywords?: string[];
  brandWhitelist?: string[];
  competitors?: string[];
  approvalRules?: Record<string, unknown>;
  locale?: string;
  language?: string;
  notes?: string;
}

export interface SourceEvidence {
  provider: ConnectorKind;
  status: ConnectorStatus;
  summary: string;
  provenance: string[];
  details: Record<string, unknown>;
  sourceType?: "connector" | "trend" | "news" | "qa";
  sourceRef?: string | null;
  fetchedAt?: string;
  fallbackReason?: string | null;
  failureCode?: string | null;
  retryable?: boolean;
  latencyMs?: number | null;
  authSource?: string | null;
  checkedAt: string;
}

export interface IngestionReport {
  reportId: string;
  projectId: string;
  taskId?: string | null;
  status: ConnectorStatus;
  generatedAt: string;
  evidence: SourceEvidence[];
  connectorStatus: Record<string, ConnectorStatus>;
  provenance: Record<string, string[]>;
  notes: string[];
}

export interface MarketEvidenceReport {
  reportId: string;
  projectId: string;
  generatedAt: string;
  trend: SourceEvidence[];
  news: SourceEvidence[];
  qa: SourceEvidence[];
  summaries: MarketEvidenceSummary[];
  notes: string[];
}

export interface MarketEvidenceHealthReport {
  reportId: string;
  projectId: string;
  generatedAt: string;
  strictProvidersEnabled: boolean;
  connectedCount: number;
  syntheticCount: number;
  failedCount: number;
  freshCount: number;
  staleCount: number;
  latestFetchedAt?: string | null;
  strictReady: boolean;
  notes: string[];
}

export interface WorkspaceMarketEvidenceHealthReport {
  reportId: string;
  generatedAt: string;
  strictProvidersEnabled: boolean;
  projectCount: number;
  connectedCount: number;
  syntheticCount: number;
  failedCount: number;
  freshCount: number;
  staleCount: number;
  strictReadyProjectCount: number;
  strictReadyProjectRatePercent: number;
  latestFetchedAt?: string | null;
  strictReadyProjectIds: string[];
  staleProjectIds: string[];
  notes: string[];
}

export interface MarketEvidenceProviderStatus {
  provider: ConnectorKind;
  providerLabel: string;
  endpoint?: string | null;
  configured: boolean;
  authConfigured: boolean;
  authHeader: string;
  authSource: string;
  strictReady: boolean;
  fallbackReason?: string | null;
  notes: string[];
}

export interface MarketEvidenceProviderStatusReport {
  reportId: string;
  generatedAt: string;
  providerCount: number;
  configuredCount: number;
  authConfiguredCount: number;
  strictReadyCount: number;
  entries: MarketEvidenceProviderStatus[];
  notes: string[];
}

export interface WorkspaceCruiseProjectHealthItem {
  projectId: string;
  name: string;
  url: string;
  autoCruiseEnabled: boolean;
  connectionHealth: ConnectionHealth;
  syncIntervalMinutes: number;
  lastSyncAt?: string | null;
  nextSyncAt?: string | null;
  dueNow: boolean;
  overdue: boolean;
  lastRunStatus?: string | null;
}

export interface WorkspaceCruiseHealthReport {
  reportId: string;
  generatedAt: string;
  autoCruiseEnabled: boolean;
  projectCount: number;
  enabledProjectCount: number;
  dueProjectCount: number;
  overdueProjectCount: number;
  nextDueAt?: string | null;
  lastSyncAt?: string | null;
  enabledProjectIds: string[];
  dueProjectIds: string[];
  overdueProjectIds: string[];
  projectSamples: WorkspaceCruiseProjectHealthItem[];
  notes: string[];
}

export interface ProjectCruiseHealthReport {
  reportId: string;
  projectId: string;
  generatedAt: string;
  autoCruiseEnabled: boolean;
  connectionHealth: ConnectionHealth;
  syncIntervalMinutes: number;
  lastSyncAt?: string | null;
  nextSyncAt?: string | null;
  dueNow: boolean;
  overdue: boolean;
  lastRunStatus?: string | null;
  projectSample?: WorkspaceCruiseProjectHealthItem | null;
  notes: string[];
}

export interface MarketEvidenceSummary {
  sourceType: "trend" | "news" | "qa";
  totalCount: number;
  connectedCount: number;
  syntheticCount: number;
  failedCount: number;
  latestFetchedAt?: string | null;
  authSources: string[];
  fallbackReasons: string[];
  connectedEndpoints: string[];
  connectedSourceRefs: string[];
  averageLatencyMs?: number | null;
}

export interface PageSnapshot {
  url: string;
  title: string;
  description: string;
  headings: string[];
  wordCount: number;
  internalLinks: number;
  externalLinks: number;
  images: number;
  missingAltCount: number;
  structuredData: string[];
  ctaCount: number;
  performanceBudget: {
    lcpMs: number;
    cls: number;
    inpMs: number;
  };
}

export interface SiteProfile {
  siteId: string;
  name: string;
  url: string;
  vertical: SiteClass;
  language: string;
  locale: string;
  brandVoice: string;
  pageCountEstimate: number;
  trustSignals: string[];
  pages: PageSnapshot[];
  evidence: string[];
  riskScore: number;
}

export interface BusinessClassifierRule {
  ruleId: string;
  name: string;
  description: string;
  vertical: SiteClass;
  triggers: string[];
  confidence: number;
  enabled: boolean;
}

export interface BusinessClassifierReport {
  reportId: string;
  siteId: string;
  inferredVertical: SiteClass;
  brandVoice: string;
  matchedRules: BusinessClassifierRule[];
  signals: string[];
  notes: string[];
}

export interface StyleToken {
  token: string;
  value: string;
  source: string;
  confidence: number;
}

export interface StyleExtractionReport {
  reportId: string;
  projectId: string;
  siteId: string;
  brandVoice: string;
  tone: string;
  density: "compact" | "balanced" | "expansive";
  trustLevel: "low" | "medium" | "high";
  tokens: StyleToken[];
  moduleGuidance: string[];
  notes: string[];
}

export interface ProjectConnection {
  connectionId: string;
  provider: ConnectorKind;
  label: string;
  enabled: boolean;
  status: ConnectorStatus;
  providerMode: "real" | "fallback" | "unconfigured";
  strictEligible: boolean;
  blockingReason?: string | null;
  config: Record<string, unknown>;
  details: Record<string, unknown>;
  provenance: string[];
  lastCheckedAt?: string | null;
  lastSuccessAt?: string | null;
  lastErrorAt?: string | null;
  recentEvidenceLabel?: string | null;
  recentEvidenceRef?: string | null;
  recentEvidenceAt?: string | null;
  lastSyncedAt?: string | null;
  nextSyncAt?: string | null;
}

export interface ProjectState {
  projectId: string;
  connectionHealth: ConnectionHealth;
  autoCruiseEnabled: boolean;
  syncIntervalMinutes: number;
  lastSyncAt?: string | null;
  nextSyncAt?: string | null;
  lastRunId?: string | null;
  lastRunStatus?: RunStatus | "idle";
}

export interface ProjectConnections {
  projectId: string;
  state: ProjectState;
  connections: ProjectConnection[];
}

export interface ProjectConnectionEvidenceEntry {
  provider: ConnectorKind;
  label: string;
  status: ConnectorStatus;
  providerMode: "real" | "fallback" | "unconfigured";
  strictEligible: boolean;
  authSource?: string | null;
  fallbackReason?: string | null;
  latencyMs?: number | null;
  recentEvidenceLabel?: string | null;
  recentEvidenceRef?: string | null;
  recentEvidenceAt?: string | null;
  lastSuccessAt?: string | null;
  lastErrorAt?: string | null;
}

export interface ProjectConnectionEvidenceReport {
  projectId: string;
  generatedAt: string;
  total: number;
  realCount: number;
  fallbackCount: number;
  unconfiguredCount: number;
  entries: ProjectConnectionEvidenceEntry[];
}

export interface WorkspaceConnectionEvidenceEntry extends ProjectConnectionEvidenceEntry {
  projectId: string;
  projectName: string;
  projectUrl: string;
}

export interface WorkspaceConnectionEvidenceProviderSummary {
  provider: ConnectorKind;
  total: number;
  realCount: number;
  fallbackCount: number;
  unconfiguredCount: number;
  projectCount: number;
  recentEvidenceLabel?: string | null;
  recentEvidenceRef?: string | null;
  recentEvidenceAt?: string | null;
}

export interface WorkspaceConnectionEvidenceReport {
  generatedAt: string;
  total: number;
  realCount: number;
  fallbackCount: number;
  unconfiguredCount: number;
  entries: WorkspaceConnectionEvidenceEntry[];
  providerSummaries: WorkspaceConnectionEvidenceProviderSummary[];
}

export interface Opportunity {
  id: string;
  category: "seo" | "ad" | "technical" | "ux";
  title: string;
  description: string;
  impactScore: number;
  effortScore: number;
  riskScore: number;
  skillIds: string[];
  previewTarget: string;
  evidence: string[];
}

export interface OpportunitySet {
  seo: Opportunity[];
  ad: Opportunity[];
  technical: Opportunity[];
  ux: Opportunity[];
}

export interface PlanStep {
  id: string;
  skillId: string;
  action: string;
  target: string;
  expectedOutput: string;
  approvalRequired: boolean;
  destructive: boolean;
  rollbackSupported: boolean;
}

export interface Plan {
  planId: string;
  siteId: string;
  deploymentMode: DeploymentMode;
  riskScore: number;
  releaseStrategy: string;
  steps: PlanStep[];
  rationale: string[];
  requiresManualApproval: boolean;
  autoDeployAllowed: boolean;
}

export interface UXReview {
  score: number;
  issues: string[];
  notes: string[];
  recommendations: string[];
}

export interface ApprovalRequest {
  approvalId: string;
  taskId: string;
  status: ApprovalStatus;
  requiredApprovers: string[];
  policySnapshot: Record<string, unknown>;
  riskSummary: string;
  decisionHint: string;
}

export interface ProjectRun {
  runId: string;
  projectId: string;
  taskId?: string | null;
  trigger: RunTrigger;
  status: RunStatus;
  startedAt: string;
  finishedAt?: string | null;
  riskScore: number;
  connectorStatus: Record<string, ConnectorStatus>;
  evidence: string[];
  notes: string[];
  autoDeploy: boolean;
  rollbackReady: boolean;
  runtimeRouteReady: boolean;
  runtimeRouteSummary?: string | null;
  runtimeRouteRequestPath?: string | null;
  runtimeRouteRequestMethod?: string | null;
  runtimeRouteExecutionMode?: "runtime" | "preview" | "blocked" | null;
  runtimeRouteExecutionAction?: "serve_runtime" | "serve_preview" | "block" | null;
  runtimeRouteExecutionReason?: string | null;
  runtimeRouteExecutionEntrypoint?: string | null;
  gatewayRouteProviderName?: string | null;
  gatewayRouteFallbackProviderName?: string | null;
  gatewayRoutePriority?: number | null;
}

export interface ProjectRuntimeRouteHistoryReport {
  generatedAt: string;
  projectId: string;
  total: number;
  runtimeReadyCount: number;
  previewOnlyCount: number;
  entries: ProjectRun[];
}

export interface PreviewArtifact {
  previewId: string;
  beforeHtml: string;
  afterHtml: string;
  domInsertions: string[];
  cssDiff: string;
  performanceBudget: {
    baselineLcpMs: number;
    estimatedLcpMs: number;
    budgetDeltaMs: number;
  };
  diffSummary: string;
}

export interface DeploymentRecord {
  deploymentId: string;
  taskId: string;
  mode: DeploymentMode;
  status: "blocked" | "scheduled" | "deployed" | "failed";
  artifactRef: string;
  releaseNotes: string[];
  rollbackReady: boolean;
  strictMode?: boolean;
  verifiedPatch?: boolean;
  patchAudit?: Record<string, unknown>;
  patchManifestRef?: string | null;
  writebackTarget?: string | null;
  writebackAuthSource?: string | null;
  writebackAttempts?: Record<string, unknown>[];
  providerArtifactId?: string | null;
  providerUrl?: string | null;
  writebackSummary?: Record<string, unknown>;
  strictBlockers?: Record<string, unknown>[];
  fallbackReason?: string | null;
  failureCode?: string | null;
}

export interface DeploymentHistoryEntry {
  deployment: DeploymentRecord;
  taskStatus: WorkflowStage;
  approvalStatus: ApprovalStatus;
  updatedAt: string;
  rollbackId?: string | null;
}

export interface RollbackHistoryEntry {
  rollback: RollbackBundle;
  taskId: string;
  taskStatus: WorkflowStage;
  approvalStatus: ApprovalStatus;
  updatedAt: string;
}

export interface DeploymentHistoryReport {
  projectId: string;
  total: number;
  entries: DeploymentHistoryEntry[];
}

export interface RollbackHistoryReport {
  projectId: string;
  total: number;
  entries: RollbackHistoryEntry[];
}

export interface MetricSnapshot {
  snapshotId: string;
  projectId: string;
  taskId: string;
  seoScore: number;
  adFitScore: number;
  coreWebVitals: {
    lcpMs: number;
    cls: number;
    inpMs: number;
  };
  trafficDelta: number;
  conversionDelta: number;
  sourceStatus: Record<string, ConnectorStatus>;
  sourceMetricsSummary: SourceMetricSummary[];
  externalMetrics: Record<string, unknown>;
  evidence: string[];
  createdAt: string;
}

export interface SourceMetricSummary {
  source: "search_console" | "ga4" | "ad_network";
  status: ConnectorStatus;
  primaryMetric: string;
  secondaryMetric: string;
  tertiaryMetric?: string | null;
  authSource?: string | null;
  fallbackReason?: string | null;
}

export interface RollbackBundle {
  rollbackId: string;
  deploymentId: string;
  commands: string[];
  safeWindowMinutes: number;
  reason: string;
  expectedEffect: string;
}

export interface WorkflowBundle {
  project: ProjectSummary;
  task: TaskSummary;
  siteProfile: SiteProfile;
  ingestionReport?: IngestionReport | null;
  experimentAssignment?: WorkspaceExperimentAssignmentReport | null;
  localizationAssignment?: WorkspaceLocalizationAssignmentReport | null;
  runtimeRoute?: RuntimeRouteReport | null;
  opportunitySet: OpportunitySet;
  plan: Plan;
  uxReview: UXReview;
  approvalRequest: ApprovalRequest;
  preview: PreviewArtifact;
  deployment?: DeploymentRecord | null;
  metricSnapshot?: MetricSnapshot | null;
  rollbackBundle?: RollbackBundle | null;
}

export interface DashboardSnapshot {
  generatedAt: string;
  projects: ProjectSummary[];
  tasks: TaskSummary[];
  approvals: ApprovalRequest[];
  skills: SkillDefinition[];
  policy: WorkspacePolicy;
  marketEvidenceProviders?: MarketEvidenceProviderStatusReport | null;
  billingGatewayProviders?: WorkspaceBillingSettlementGatewayProviderStatusReport | null;
  modelGatewayProviders?: WorkspaceModelGatewayProviderStatusReport | null;
  runtimeEdgeGatewayProviders?: RuntimeEdgeGatewayProviderStatusReport | null;
  visualFarmGatewayProviders?: VisualFarmGatewayProviderStatusReport | null;
  runtimeRouteHealth?: WorkspaceRuntimeRouteHealthReport | null;
  runtimeRouteHistory?: WorkspaceRuntimeRouteHistoryReport | null;
  adAuditHistory?: WorkspaceAdAuditHistoryReport | null;
  billingSettlementHistory?: WorkspaceBillingSettlementExecutionHistoryReport | null;
  billingGatewayHistory?: WorkspaceBillingSettlementGatewayHistoryReport | null;
  modelGatewayHistory?: WorkspaceModelGatewayHistoryReport | null;
  alerts: string[];
}

export interface ConnectorFailureEntry {
  failureCode: string;
  category: "auth" | "permission" | "rate_limit" | "network" | "validation" | "config" | "unavailable" | "other";
  count: number;
  providers: string[];
  affectedProjects: number;
  projectIds: string[];
  lastSeenAt: string;
}

export interface ConnectorFailureReport {
  reportId: string;
  generatedAt: string;
  totalFailures: number;
  activeProjectCount: number;
  entries: ConnectorFailureEntry[];
  notes: string[];
}

export interface ConnectorRetryRequest {
  categories: Array<"auth" | "permission" | "rate_limit" | "network" | "validation" | "config" | "unavailable" | "other">;
  projectIds: string[];
  providers: ConnectorKind[];
  retryableOnly: boolean;
  maxRetries: number;
}

export interface ConnectorRetryResult {
  attempted: number;
  refreshed: number;
  skipped: number;
  failed: number;
  categories: string[];
  notes: string[];
}

export interface VisualRegressionRetryRequest {
  categories: Array<"auth" | "permission" | "rate_limit" | "network" | "validation" | "config" | "unavailable" | "other">;
  retryableOnly: boolean;
  maxCases: number;
}

export interface VisualRegressionRetryResult {
  attempted: number;
  rerunPassed: number;
  rerunFailed: number;
  skipped: number;
  categories: string[];
  runId?: string | null;
  notes: string[];
}

export interface VisualRegressionRetryHistoryEntry {
  auditId: string;
  actor: string;
  createdAt: string;
  attempted: number;
  rerunPassed: number;
  rerunFailed: number;
  skipped: number;
  categories: string[];
  runId?: string | null;
  notes: string[];
  spanId?: string | null;
}

export interface VisualRegressionRetryHistoryReport {
  generatedAt: string;
  entries: VisualRegressionRetryHistoryEntry[];
}

export interface VisualRegressionRunExecuteRequest {
  strictMode?: boolean | null;
  projectIds: string[];
  taskIds?: string[];
  maxCases: number;
}

export interface VisualRegressionRunEnqueueResult {
  enqueued: boolean;
  skippedDuplicate: boolean;
  jobId: string;
  stage: string;
  strictMode?: boolean | null;
  projectIds: string[];
  taskIds: string[];
  maxCases: number;
  message: string;
}

export interface VisualRegressionRunHistoryEntry {
  auditId: string;
  actor: string;
  createdAt: string;
  strictMode: boolean;
  projectIds: string[];
  maxCases: number;
  runCount: number;
  caseCount: number;
  runIds: string[];
  notes: string[];
}

export interface VisualRegressionRunHistoryReport {
  generatedAt: string;
  entries: VisualRegressionRunHistoryEntry[];
}

export interface VisualRegressionRemediationItem {
  remediationId: string;
  category: "auth" | "permission" | "rate_limit" | "network" | "validation" | "config" | "unavailable" | "other";
  failureCode: string;
  priority: "p0" | "p1" | "p2" | "p3";
  action: string;
  rationale: string;
  blocking: boolean;
  affectedCases: number;
  affectedProjects: number;
  projectIds: string[];
  quickActionPath: string;
  quickActionLabel: string;
  retryRequestTemplate: VisualRegressionRetryRequest;
}

export interface VisualRegressionRemediationReport {
  reportId: string;
  generatedAt: string;
  itemCount: number;
  items: VisualRegressionRemediationItem[];
  notes: string[];
}

export interface ConnectorRetryHistoryEntry {
  auditId: string;
  actor: string;
  createdAt: string;
  attempted: number;
  refreshed: number;
  failed: number;
  skipped: number;
  categories: string[];
  notes: string[];
  spanId?: string | null;
  alertIds?: string[];
}

export interface ConnectorRetryHistoryReport {
  generatedAt: string;
  entries: ConnectorRetryHistoryEntry[];
}

export interface BulkConnectorActionHistoryEntry {
  auditId: string;
  action: string;
  createdAt: string;
  actor: string;
  providerCount: number;
  providers: string[];
  refreshedCount: number;
  skippedProjectCount: number;
  projectScopeCount: number;
  projectIds?: string[];
  maxProviders: number;
  spanId?: string | null;
  traceId?: string | null;
}

export interface BulkConnectorActionHistoryReport {
  generatedAt: string;
  total: number;
  entries: BulkConnectorActionHistoryEntry[];
}

export interface ProjectConnectionHistoryEntry {
  auditId: string;
  provider: string;
  action: string;
  status: string;
  summary: string;
  authSource?: string | null;
  failureCode?: string | null;
  fallbackReason?: string | null;
  latencyMs?: number | null;
  retryable: boolean;
  provenance: string[];
  actor: string;
  createdAt: string;
}

export interface ProjectConnectionHistoryReport {
  projectId: string;
  generatedAt: string;
  entries: ProjectConnectionHistoryEntry[];
}

export interface WorkspaceConnectionHistoryEntry extends ProjectConnectionHistoryEntry {
  projectId: string;
  taskId?: string | null;
}

export interface WorkspaceConnectionHistoryReport {
  generatedAt: string;
  entries: WorkspaceConnectionHistoryEntry[];
}

export interface ConnectorRemediationItem {
  remediationId: string;
  failureCode: string;
  category: "auth" | "permission" | "rate_limit" | "network" | "validation" | "config" | "unavailable" | "other";
  priority: "p0" | "p1" | "p2" | "p3";
  action: string;
  rationale: string;
  target: "settings" | "monitor" | "project" | "provider";
  quickActionPath: string;
  quickActionLabel: string;
  retryAfterMinutes?: number | null;
  affectedProjects: number;
  projectIds: string[];
  providers: string[];
  blocking?: boolean;
  alertSeverity?: "critical" | "warning" | "info";
}

export interface ConnectorRemediationReport {
  reportId: string;
  generatedAt: string;
  itemCount: number;
  items: ConnectorRemediationItem[];
  notes: string[];
}

export interface ProjectSummary {
  projectId: string;
  name: string;
  url: string;
  siteClass: SiteClass;
  latestStage: WorkflowStage;
  riskScore: number;
  deploymentMode?: DeploymentMode | null;
  recommendation: string;
  updatedAt: string;
  connectionHealth?: ConnectionHealth;
  lastSyncAt?: string | null;
  nextSyncAt?: string | null;
  runCount?: number;
}

export interface TaskSummary {
  taskId: string;
  projectId: string;
  status: WorkflowStage;
  riskScore: number;
  approvalStatus: ApprovalStatus;
  siteClass: SiteClass;
  updatedAt: string;
}

export interface SkillDefinition {
  skillId: string;
  suite: SkillSuite;
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  isDestructive: boolean;
  requiredApproval: boolean;
  rollbackSupported: boolean;
  observability: Record<string, unknown>;
  failureContract: string;
}

export interface WorkspacePolicy {
  autoDeployEnabled: boolean;
  approvalRequiredThreshold: number;
  blockAutoDeployThreshold: number;
  monitorWindowMinutes: number;
  rollbackWindowMinutes: number;
  autoCruiseEnabled: boolean;
  allowedDeploymentModes: DeploymentMode[];
}

export interface WorkspacePolicyUpdateRequest {
  autoDeployEnabled?: boolean | null;
  approvalRequiredThreshold?: number | null;
  blockAutoDeployThreshold?: number | null;
  monitorWindowMinutes?: number | null;
  rollbackWindowMinutes?: number | null;
  autoCruiseEnabled?: boolean | null;
  allowedDeploymentModes?: DeploymentMode[] | null;
}

export interface WorkspaceBillingPolicy {
  planTier: "starter" | "growth" | "scale" | "enterprise";
  commercialModeEnabled: boolean;
  settlementEnabled: boolean;
  settlementProviderName: string;
  settlementAccountRef?: string | null;
  settlementCurrency: string;
  settlementWindowDays: number;
  settlementHoldbackPercent: number;
  settlementPayoutThresholdCents: number;
  monthlyProjectLimit: number;
  monthlyTaskLimit: number;
  monthlyDeployLimit: number;
  monthlyBudgetCents: number;
  overageBlocking: boolean;
  notes: string[];
}

export interface WorkspaceBillingPolicyUpdateRequest {
  planTier?: "starter" | "growth" | "scale" | "enterprise" | null;
  commercialModeEnabled?: boolean | null;
  settlementEnabled?: boolean | null;
  settlementProviderName?: string | null;
  settlementAccountRef?: string | null;
  settlementCurrency?: string | null;
  settlementWindowDays?: number | null;
  settlementHoldbackPercent?: number | null;
  settlementPayoutThresholdCents?: number | null;
  monthlyProjectLimit?: number | null;
  monthlyTaskLimit?: number | null;
  monthlyDeployLimit?: number | null;
  monthlyBudgetCents?: number | null;
  overageBlocking?: boolean | null;
  notes?: string[] | null;
}

export interface WorkspaceBillingUsage {
  generatedAt: string;
  activeProjectCount: number;
  taskCount: number;
  runCount30d: number;
  deployCount30d: number;
  rollbackCount30d: number;
  autoDeployCount30d: number;
  strictReadyProjectCount: number;
  estimatedUsageCents: number;
  projectLimitUsedPercent: number;
  taskLimitUsedPercent: number;
  deployLimitUsedPercent: number;
  budgetLimitUsedPercent: number;
  overProjectLimit: boolean;
  overTaskLimit: boolean;
  overDeployLimit: boolean;
  overBudgetLimit: boolean;
  notes: string[];
}

export interface WorkspaceBillingSettlement {
  settlementEnabled: boolean;
  settlementProviderName: string;
  settlementAccountRef?: string | null;
  settlementCurrency: string;
  settlementWindowDays: number;
  settlementHoldbackPercent: number;
  payoutThresholdCents: number;
  grossEstimatedCents: number;
  holdbackCents: number;
  netSettlementCents: number;
  settlementDueCents: number;
  settlementReady: boolean;
  settlementBlocked: boolean;
  notes: string[];
}

export interface WorkspaceBillingSettlementGatewayRoute {
  providerName: string;
  enabled: boolean;
  fallbackProviderName: string;
  priority: number;
  notes: string[];
}

export interface WorkspaceBillingSettlementGatewayPolicy {
  gatewayEnabled: boolean;
  defaultProviderName: string;
  fallbackProviderName: string;
  strictRouting: boolean;
  routes: WorkspaceBillingSettlementGatewayRoute[];
  notes: string[];
}

export interface WorkspaceBillingSettlementGatewayPolicyUpdateRequest {
  gatewayEnabled?: boolean | null;
  defaultProviderName?: string | null;
  fallbackProviderName?: string | null;
  strictRouting?: boolean | null;
  routes?: WorkspaceBillingSettlementGatewayRoute[] | null;
  notes?: string[] | null;
}

export interface WorkspaceBillingSettlementGatewayRouteStatus {
  providerName: string;
  enabled: boolean;
  fallbackProviderName: string;
  resolvedProviderName: string;
  priority: number;
  routeReady: boolean;
  notes: string[];
}

export interface WorkspaceBillingSettlementGatewayPublishReport {
  generatedAt: string;
  projectId?: string | null;
  providerName: string;
  strictRouting: boolean;
  status: "blocked" | "completed" | "failed";
  gatewayEndpoint?: string | null;
  gatewayUrl?: string | null;
  gatewayArtifactId?: string | null;
  gatewayMode: "external" | "local";
  authSource: string;
  message: string;
  failureCode?: string | null;
  retryable: boolean;
  notes: string[];
}

export interface WorkspaceBillingSettlementGatewayReport {
  generatedAt: string;
  policy: WorkspaceBillingSettlementGatewayPolicy;
  routeCount: number;
  enabledRouteCount: number;
  providerCount: number;
  routeReadyCount: number;
  gatewayReady: boolean;
  routes: WorkspaceBillingSettlementGatewayRouteStatus[];
  gatewayPublish?: WorkspaceBillingSettlementGatewayPublishReport | null;
  warnings: string[];
  recommendations: string[];
}

export interface WorkspaceBillingSettlementGatewayHistoryReport {
  generatedAt: string;
  projectId?: string | null;
  total: number;
  projectCount: number;
  gatewayReadyCount: number;
  gatewayRouteReadyCount: number;
  dryRunCount: number;
  liveCount: number;
  blockedCount: number;
  failedCount: number;
  latestProjectId?: string | null;
  latestProjectName?: string | null;
  latestGatewayProviderName?: string | null;
  latestGatewayRouteProviderName?: string | null;
  latestGatewayRouteReason?: string | null;
  latestGatewayRoutePriority?: number | null;
  latestFailureCode?: string | null;
  latestRetryable?: boolean | null;
  entries: WorkspaceBillingSettlementExecution[];
}

export interface WorkspaceBillingSettlementGatewayProviderStatus {
  providerName: string;
  providerLabel: string;
  endpoint?: string | null;
  configured: boolean;
  authConfigured: boolean;
  authHeader: string;
  authSource: string;
  routeEnabled: boolean;
  fallbackProviderName: string;
  resolvedProviderName: string;
  priority: number;
  routeReady: boolean;
  strictReady: boolean;
  fallbackReason?: string | null;
  notes: string[];
}

export interface WorkspaceBillingSettlementGatewayProviderStatusReport {
  generatedAt: string;
  projectId?: string | null;
  gatewayEnabled: boolean;
  providerCount: number;
  configuredCount: number;
  authConfiguredCount: number;
  routeReadyCount: number;
  strictReadyCount: number;
  gatewayReady: boolean;
  entries: WorkspaceBillingSettlementGatewayProviderStatus[];
  warnings: string[];
  recommendations: string[];
}

export interface WorkspaceBillingSettlementProviderRequirement {
  conditionalRequirements: Array<{
    whenField: string;
    whenValue: string;
    requiredFields: string[];
    metadataFields: string[];
    notes: string[];
  }>;
  providerName: string;
  providerLabel: string;
  destinationTypes: string[];
  rails: string[];
  requiredFields: string[];
  metadataFields: string[];
  notes: string[];
}

export interface WorkspaceBillingSettlementProviderRequirementsReport {
  generatedAt: string;
  providerCount: number;
  entries: WorkspaceBillingSettlementProviderRequirement[];
  warnings: string[];
  recommendations: string[];
}

export interface WorkspaceBillingReport {
  generatedAt: string;
  policy: WorkspaceBillingPolicy;
  usage: WorkspaceBillingUsage;
  settlement: WorkspaceBillingSettlement;
  settlementGateway?: WorkspaceBillingSettlementGatewayReport | null;
  settlementGatewayHistory?: WorkspaceBillingSettlementGatewayHistoryReport | null;
  commercialReady: boolean;
  warnings: string[];
  recommendations: string[];
}

export interface WorkspaceBillingSettlementExecutionRequest {
  dryRun?: boolean;
  providerName?: string | null;
  accountRef?: string | null;
  currency?: string | null;
  amountCents?: number | null;
  memo?: string | null;
  projectId?: string | null;
  destinationType?: string | null;
  destinationRef?: string | null;
  beneficiaryName?: string | null;
  beneficiaryEmail?: string | null;
  rail?: string | null;
  countryCode?: string | null;
  metadata?: Record<string, unknown>;
  providerPayload?: Record<string, unknown>;
}

export interface WorkspaceBillingSettlementExecution {
  auditId: string;
  createdAt: string;
  actor: string;
  projectId?: string | null;
  projectName?: string | null;
  requestPath?: string | null;
  requestMethod?: string | null;
  dryRun: boolean;
  providerName: string;
  accountRef?: string | null;
  destinationType?: string | null;
  destinationRef?: string | null;
  beneficiaryName?: string | null;
  beneficiaryEmail?: string | null;
  rail?: string | null;
  countryCode?: string | null;
  metadata?: Record<string, unknown>;
  providerPayload?: Record<string, unknown>;
  currency: string;
  grossCents: number;
  holdbackCents: number;
  netCents: number;
  dueCents: number;
  status: "previewed" | "completed" | "failed" | "blocked";
  failureCode?: string | null;
  retryable: boolean;
  transactionRef?: string | null;
  message?: string | null;
  memo?: string | null;
  settlementReady: boolean;
  gatewayProviderName?: string | null;
  gatewayRouteProviderName?: string | null;
  gatewayRouteFallbackProviderName?: string | null;
  gatewayRoutePriority?: number | null;
  gatewayRouteReason?: string | null;
  gatewayReady: boolean;
  gatewayRouteReady: boolean;
  notes: string[];
}

export interface WorkspaceBillingSettlementExecutionReport {
  generatedAt: string;
  billing: WorkspaceBillingReport;
  execution: WorkspaceBillingSettlementExecution;
  warnings: string[];
  recommendations: string[];
}

export interface WorkspaceBillingSettlementExecutionHistoryReport {
  total: number;
  entries: WorkspaceBillingSettlementExecution[];
}

export interface WorkspaceExperimentVariant {
  variantName: string;
  allocationPercent: number;
  enabled: boolean;
  notes: string[];
}

export interface WorkspaceExperiment {
  experimentKey: string;
  enabled: boolean;
  targetSurface: "site" | "seo" | "content" | "ad" | "ui";
  targetLocale?: string | null;
  targetProjectIds: string[];
  controlVariantName: string;
  assignmentStrategy: "hash" | "sticky" | "round_robin";
  primaryMetric: string;
  variants: WorkspaceExperimentVariant[];
  notes: string[];
}

export interface WorkspaceExperimentPolicy {
  experimentsEnabled: boolean;
  strictAssignment: boolean;
  defaultAssignmentStrategy: "hash" | "sticky" | "round_robin";
  experiments: WorkspaceExperiment[];
  notes: string[];
}

export interface WorkspaceExperimentPolicyUpdateRequest {
  experimentsEnabled?: boolean | null;
  strictAssignment?: boolean | null;
  defaultAssignmentStrategy?: "hash" | "sticky" | "round_robin" | null;
  experiments?: WorkspaceExperiment[] | null;
  notes?: string[] | null;
}

export interface WorkspaceExperimentStatus {
  experimentKey: string;
  enabled: boolean;
  targetSurface: "site" | "seo" | "content" | "ad" | "ui";
  targetLocale?: string | null;
  targetProjectCount: number;
  variantCount: number;
  totalAllocationPercent: number;
  balancedAllocation: boolean;
  controlVariantPresent: boolean;
  experimentReady: boolean;
  warnings: string[];
  notes: string[];
}

export interface WorkspaceExperimentReport {
  generatedAt: string;
  policy: WorkspaceExperimentPolicy;
  experimentCount: number;
  enabledExperimentCount: number;
  readyExperimentCount: number;
  variantCount: number;
  balancedExperimentCount: number;
  projectScopeCount: number;
  workspaceReady: boolean;
  experiments: WorkspaceExperimentStatus[];
  warnings: string[];
  recommendations: string[];
}

export interface WorkspaceExperimentAssignmentRequest {
  projectId?: string | null;
  subjectKey?: string | null;
  sessionKey?: string | null;
  targetSurface: "site" | "seo" | "content" | "ad" | "ui";
  targetLocale?: string | null;
  experimentKey?: string | null;
}

export interface WorkspaceExperimentAssignment {
  experimentKey: string;
  enabled: boolean;
  targetSurface: "site" | "seo" | "content" | "ad" | "ui";
  targetLocale?: string | null;
  targetProjectMatch: boolean;
  assignmentStrategy: "hash" | "sticky" | "round_robin";
  subjectKey: string;
  bucketKey: string;
  bucketRoll: number;
  bucketSize: number;
  eligible: boolean;
  controlVariantName: string;
  assignedVariantName?: string | null;
  assignedVariantIndex?: number | null;
  variantCount: number;
  totalAllocationPercent: number;
  warnings: string[];
  notes: string[];
}

export interface WorkspaceExperimentAssignmentReport {
  generatedAt: string;
  policy: WorkspaceExperimentPolicy;
  projectId?: string | null;
  subjectKey: string;
  sessionKey?: string | null;
  targetSurface: "site" | "seo" | "content" | "ad" | "ui";
  targetLocale?: string | null;
  experimentCount: number;
  matchedExperimentCount: number;
  assignedExperimentCount: number;
  strictAssignment: boolean;
  assignments: WorkspaceExperimentAssignment[];
  warnings: string[];
  recommendations: string[];
}

export interface WorkspaceSiteCluster {
  clusterKey: string;
  enabled: boolean;
  canonicalProjectId?: string | null;
  projectIds: string[];
  supportedLocales: string[];
  primaryLocale?: string | null;
  localeStrategy: "path" | "subdomain" | "cctld";
  notes: string[];
}

export interface WorkspaceLocalizationPolicy {
  localizationEnabled: boolean;
  strictLocalization: boolean;
  defaultLocale: string;
  defaultLanguage: string;
  clusters: WorkspaceSiteCluster[];
  notes: string[];
}

export interface WorkspaceLocalizationPolicyUpdateRequest {
  localizationEnabled?: boolean | null;
  strictLocalization?: boolean | null;
  defaultLocale?: string | null;
  defaultLanguage?: string | null;
  clusters?: WorkspaceSiteCluster[] | null;
  notes?: string[] | null;
}

export interface WorkspaceLocalizationClusterStatus {
  clusterKey: string;
  enabled: boolean;
  canonicalProjectId?: string | null;
  projectCount: number;
  localeCount: number;
  supportedLocaleCount: number;
  hasCanonicalProject: boolean;
  localeCoverageReady: boolean;
  clusterReady: boolean;
  warnings: string[];
  notes: string[];
}

export interface WorkspaceLocalizationReport {
  generatedAt: string;
  policy: WorkspaceLocalizationPolicy;
  clusterCount: number;
  enabledClusterCount: number;
  readyClusterCount: number;
  projectCount: number;
  localeCount: number;
  workspaceReady: boolean;
  clusters: WorkspaceLocalizationClusterStatus[];
  warnings: string[];
  recommendations: string[];
}

export interface WorkspaceLocalizationAssignmentRequest {
  projectId?: string | null;
  targetLocale?: string | null;
  host?: string | null;
  subjectKey?: string | null;
}

export interface WorkspaceLocalizationAssignment {
  clusterKey: string;
  enabled: boolean;
  localeStrategy: "path" | "subdomain" | "cctld";
  subjectKey: string;
  projectId?: string | null;
  targetLocale?: string | null;
  matchedByProject: boolean;
  matchedByLocale: boolean;
  matchedByHost: boolean;
  canonicalProjectId?: string | null;
  projectCount: number;
  localeCount: number;
  clusterReady: boolean;
  routePrefix: string;
  warnings: string[];
  notes: string[];
}

export interface WorkspaceLocalizationAssignmentReport {
  generatedAt: string;
  policy: WorkspaceLocalizationPolicy;
  projectId?: string | null;
  targetLocale?: string | null;
  host?: string | null;
  subjectKey: string;
  clusterCount: number;
  matchedClusterCount: number;
  assignedClusterCount: number;
  strictLocalization: boolean;
  assignments: WorkspaceLocalizationAssignment[];
  warnings: string[];
  recommendations: string[];
}

export interface RuntimeRouteReport {
  generatedAt: string;
  projectId: string;
  taskId: string;
  subjectKey: string;
  requestPath?: string | null;
  requestMethod?: string | null;
  targetSurface: "site" | "seo" | "content" | "ad" | "ui";
  targetLocale?: string | null;
  host?: string | null;
  experimentAssignment?: WorkspaceExperimentAssignmentReport | null;
  localizationAssignment?: WorkspaceLocalizationAssignmentReport | null;
  gatewayReport?: WorkspaceModelGatewayReport | null;
  resolvedProviders: Record<string, string>;
  gatewayRouteProviderName?: string | null;
  gatewayRouteFallbackProviderName?: string | null;
  gatewayRoutePriority?: number | null;
  runtimeReady: boolean;
  executionMode: "runtime" | "preview" | "blocked";
  executionAction: "serve_runtime" | "serve_preview" | "block";
  executionReason?: string | null;
  executionEntrypoint?: string | null;
  warnings: string[];
  recommendations: string[];
}

export interface WorkspaceRuntimeRouteHealthItem {
  projectId: string;
  projectName: string;
  runtimeReady: boolean;
  runtimeSummary?: string | null;
  requestPath?: string | null;
  requestMethod?: string | null;
  experimentVariant: string;
  localizationCluster: string;
  gatewayProviderName: string;
  gatewayRouteProviderName?: string | null;
  gatewayRouteFallbackProviderName?: string | null;
  gatewayRoutePriority?: number | null;
  gatewayReady: boolean;
  executionMode?: "runtime" | "preview" | "blocked" | null;
  executionAction?: "serve_runtime" | "serve_preview" | "block" | null;
  executionReason?: string | null;
  executionEntrypoint?: string | null;
}

export interface WorkspaceRuntimeRouteHealthReport {
  generatedAt: string;
  projectCount: number;
  runtimeReadyCount: number;
  previewOnlyCount: number;
  gatewayReadyCount: number;
  strictReadyCount: number;
  runtimeReadyRatePercent: number;
  gatewayReadyRatePercent: number;
  readyProjectIds: string[];
  previewOnlyProjectIds: string[];
  items: WorkspaceRuntimeRouteHealthItem[];
  notes: string[];
}

export interface WorkspaceRuntimeRouteHistoryItem {
  projectId: string;
  projectName: string;
  runId: string;
  taskId?: string | null;
  trigger: RunTrigger | string;
  status: RunStatus | string;
  startedAt: string;
  runtimeReady: boolean;
  runtimeSummary?: string | null;
  requestPath?: string | null;
  requestMethod?: string | null;
  experimentVariant: string;
  localizationCluster: string;
  gatewayProviderName: string;
  gatewayRouteProviderName?: string | null;
  gatewayRouteFallbackProviderName?: string | null;
  gatewayRoutePriority?: number | null;
  gatewayReady: boolean;
  executionMode?: "runtime" | "preview" | "blocked" | null;
  executionAction?: "serve_runtime" | "serve_preview" | "block" | null;
  executionReason?: string | null;
  executionEntrypoint?: string | null;
}

export interface WorkspaceRuntimeRouteHistoryReport {
  generatedAt: string;
  total: number;
  runtimeReadyCount: number;
  previewOnlyCount: number;
  items: WorkspaceRuntimeRouteHistoryItem[];
}

export interface WorkspaceRuntimeRouteHistoryRequest {
  limit?: number | null;
  projectId?: string | null;
}

export interface RuntimeRouteRequest {
  taskId?: string | null;
  subjectKey?: string | null;
  requestPath?: string | null;
  requestMethod?: string | null;
  targetSurface: "site" | "seo" | "content" | "ad" | "ui";
  targetLocale?: string | null;
  host?: string | null;
}

export interface WorkspaceTemplateMarketTemplate {
  templateKey: string;
  enabled: boolean;
  templateSurface: "site" | "content" | "ad" | "technical_seo" | "ui";
  targetLocale?: string | null;
  targetProjectIds: string[];
  coverageRequirements: string[];
  templateSource: string;
  notes: string[];
}

export interface WorkspaceTemplateMarketPolicy {
  marketEnabled: boolean;
  strictMarket: boolean;
  defaultTemplateSurface: "site" | "content" | "ad" | "technical_seo" | "ui";
  templates: WorkspaceTemplateMarketTemplate[];
  notes: string[];
}

export interface WorkspaceTemplateMarketPolicyUpdateRequest {
  marketEnabled?: boolean | null;
  strictMarket?: boolean | null;
  defaultTemplateSurface?: "site" | "content" | "ad" | "technical_seo" | "ui" | null;
  templates?: WorkspaceTemplateMarketTemplate[] | null;
  notes?: string[] | null;
}

export interface WorkspaceTemplateMarketStatus {
  templateKey: string;
  enabled: boolean;
  templateSurface: "site" | "content" | "ad" | "technical_seo" | "ui";
  targetLocale?: string | null;
  targetProjectCount: number;
  coverageRequirementCount: number;
  coverageReady: boolean;
  templateReady: boolean;
  warnings: string[];
  notes: string[];
}

export interface WorkspaceTemplateMarketReport {
  generatedAt: string;
  policy: WorkspaceTemplateMarketPolicy;
  templateCount: number;
  enabledTemplateCount: number;
  readyTemplateCount: number;
  projectScopeCount: number;
  workspaceReady: boolean;
  templates: WorkspaceTemplateMarketStatus[];
  warnings: string[];
  recommendations: string[];
}

export interface WorkspaceModelGatewayRoute {
  routeSuite: "read" | "seo" | "ad" | "deploy" | "observe";
  providerName: string;
  enabled: boolean;
  fallbackProviderName: string;
  priority: number;
  notes: string[];
}

export interface WorkspaceModelGatewayPolicy {
  gatewayEnabled: boolean;
  defaultProviderName: string;
  fallbackProviderName: string;
  strictRouting: boolean;
  routes: WorkspaceModelGatewayRoute[];
  notes: string[];
}

export interface WorkspaceModelGatewayPolicyUpdateRequest {
  gatewayEnabled?: boolean | null;
  defaultProviderName?: string | null;
  fallbackProviderName?: string | null;
  strictRouting?: boolean | null;
  routes?: WorkspaceModelGatewayRoute[] | null;
  notes?: string[] | null;
}

export interface WorkspaceModelGatewayRouteStatus {
  routeSuite: "read" | "seo" | "ad" | "deploy" | "observe";
  providerName: string;
  enabled: boolean;
  fallbackProviderName: string;
  resolvedProviderName: string;
  priority: number;
  routeReady: boolean;
  notes: string[];
}

export interface WorkspaceModelGatewayProviderStatus {
  routeSuite: "read" | "seo" | "ad" | "deploy" | "observe";
  providerName: string;
  providerLabel: string;
  enabled: boolean;
  fallbackProviderName: string;
  resolvedProviderName: string;
  priority: number;
  routeReady: boolean;
  strictReady: boolean;
  fallbackReason?: string | null;
  notes: string[];
}

export interface WorkspaceModelGatewayProviderStatusReport {
  generatedAt: string;
  projectId?: string | null;
  gatewayEnabled: boolean;
  providerCount: number;
  routeCount: number;
  routeReadyCount: number;
  strictReadyCount: number;
  gatewayReady: boolean;
  entries: WorkspaceModelGatewayProviderStatus[];
  warnings: string[];
  recommendations: string[];
}

export interface RuntimeEdgeGatewayProviderStatus {
  providerName: string;
  providerLabel: string;
  enabled: boolean;
  fallbackProviderName: string;
  resolvedProviderName: string;
  priority: number;
  routeReady: boolean;
  strictReady: boolean;
  endpoint?: string | null;
  authHeader: string;
  authConfigured: boolean;
  fallbackReason?: string | null;
  notes: string[];
}

export interface RuntimeEdgeGatewayProviderStatusReport {
  generatedAt: string;
  projectId?: string | null;
  gatewayEnabled: boolean;
  providerCount: number;
  routeCount: number;
  routeReadyCount: number;
  strictReadyCount: number;
  gatewayReady: boolean;
  entries: RuntimeEdgeGatewayProviderStatus[];
  warnings: string[];
  recommendations: string[];
}

export interface VisualFarmGatewayProviderStatus {
  providerName: string;
  providerLabel: string;
  enabled: boolean;
  fallbackProviderName: string;
  resolvedProviderName: string;
  priority: number;
  routeReady: boolean;
  strictReady: boolean;
  endpoint?: string | null;
  authHeader: string;
  authConfigured: boolean;
  fallbackReason?: string | null;
  notes: string[];
}

export interface VisualFarmGatewayProviderStatusReport {
  generatedAt: string;
  projectId?: string | null;
  gatewayEnabled: boolean;
  providerCount: number;
  routeCount: number;
  routeReadyCount: number;
  strictReadyCount: number;
  gatewayReady: boolean;
  entries: VisualFarmGatewayProviderStatus[];
  warnings: string[];
  recommendations: string[];
}

export interface WorkspaceModelGatewayReport {
  generatedAt: string;
  policy: WorkspaceModelGatewayPolicy;
  routeCount: number;
  enabledRouteCount: number;
  providerCount: number;
  suiteCount: number;
  routeReadyCount: number;
  gatewayReady: boolean;
  routes: WorkspaceModelGatewayRouteStatus[];
  warnings: string[];
  recommendations: string[];
}

export interface WorkspaceModelGatewayHistoryReport {
  generatedAt: string;
  projectId?: string | null;
  total: number;
  projectCount: number;
  runtimeReadyCount: number;
  previewOnlyCount: number;
  gatewayReadyCount: number;
  routeReadyCount: number;
  latestProjectId?: string | null;
  latestProjectName?: string | null;
  latestRequestPath?: string | null;
  latestRequestMethod?: string | null;
  latestExecutionMode?: "runtime" | "preview" | "blocked" | null;
  latestExecutionAction?: "serve_runtime" | "serve_preview" | "block" | null;
  latestExecutionReason?: string | null;
  latestExecutionEntrypoint?: string | null;
  latestGatewayProviderName?: string | null;
  latestGatewayRouteProviderName?: string | null;
  latestGatewayRouteFallbackProviderName?: string | null;
  latestGatewayRouteReason?: string | null;
  latestGatewayRoutePriority?: number | null;
  entries: WorkspaceRuntimeRouteHistoryItem[];
}

export interface ProjectSyncRequest {
  trigger?: RunTrigger;
  force?: boolean;
}

export interface BulkProjectSyncRequest {
  projectIds: string[];
  trigger?: RunTrigger;
  force?: boolean;
}

export interface BulkProjectSyncResult {
  projectIds: string[];
  processedCount: number;
  skippedProjectIds: string[];
  bundles: WorkflowBundle[];
}

export interface WorkerRunOnceRequest {
  projectIds: string[];
  includeApprovedTasks: boolean;
  claimLimit: number;
}

export interface WorkerRunOnceResult {
  processed: number;
  enqueued: number;
  skippedDuplicates: number;
  claimed: number;
  dueProjects: number;
  targetProjectIds: string[];
}

export interface WorkerQueueStageStats {
  stage: string;
  total: number;
  queued: number;
  claimed: number;
  completed: number;
  failed: number;
}

export interface WorkerQueueHealthReport {
  generatedAt: string;
  backend: string;
  backendConnected: boolean;
  backendProbeLatencyMs?: number | null;
  backendProbeFailureCode?: string | null;
  backendProbeError?: string | null;
  queueDepth?: number | null;
  total: number;
  queued: number;
  claimed: number;
  completed: number;
  failed: number;
  oldestReadyAt?: string | null;
  stageStats: WorkerQueueStageStats[];
  notes: string[];
}

export interface WorkerExecutionHistoryEntry {
  auditId: string;
  projectId: string;
  taskId?: string | null;
  action: string;
  status: string;
  stage: string;
  jobId?: string | null;
  attempt: number;
  retryDelaySeconds?: number | null;
  failureCode?: string | null;
  error?: string | null;
  actor: string;
  createdAt: string;
  spanId?: string | null;
  traceId?: string | null;
}

export interface WorkerExecutionHistoryReport {
  total: number;
  entries: WorkerExecutionHistoryEntry[];
}

export interface WorkerServiceHealthReport {
  generatedAt: string;
  stateFileConfigured: boolean;
  stateFilePath?: string | null;
  stateFileFound: boolean;
  status: "running" | "starting" | "degraded" | "stopped" | "unknown";
  startedAt?: string | null;
  lastTickAt?: string | null;
  failures: number;
  processed: number;
  enqueued: number;
  claimed: number;
  skippedDuplicates: number;
  dueProjects: number;
  targets: string[];
  lastError?: string | null;
  notes: string[];
}

export interface ObservabilityStatusReport {
  generatedAt: string;
  enableOtlp: boolean;
  otlpEndpointConfigured: boolean;
  sentryDsnConfigured: boolean;
  observabilityStrict: boolean;
  tracingBackend: string;
  otlpExporterAvailable: boolean;
  notes: string[];
}

export interface ProjectConnectionsUpdateRequest {
  autoCruiseEnabled: boolean;
  syncIntervalMinutes: number;
  connections: ProjectConnection[];
}

export interface ProjectConnectionsTestResult {
  projectId: string;
  testedAt: string;
  connectionHealth: ConnectionHealth;
  connections: ProjectConnection[];
  issues: string[];
  strictMode: boolean;
  strictBlocked: boolean;
  strictGapCount: number;
  strictBlockers: string[];
}

export interface ConnectorsHealthResult {
  projectId: string;
  checkedAt: string;
  connectionHealth: ConnectionHealth;
  totalConnectionCount: number;
  realConnectionCount: number;
  fallbackConnectionCount: number;
  unconfiguredConnectionCount: number;
  strictEligibleCount: number;
  antiBotBlockedCount: number;
  manualInterventionRequiredCount: number;
  readRealLastEvidenceAt?: string | null;
  writeRealLastEvidenceAt?: string | null;
  connections: ProjectConnection[];
  issues: string[];
}

export interface ConnectorProviderCoverageItem {
  provider: ConnectorKind;
  totalConnectionCount: number;
  affectedProjectCount: number;
  strictReadyProjectCount: number;
  strictReadyProjectRatePercent: number;
  blockingProjectCount: number;
  blockingProjectRatePercent: number;
  strictGapCount: number;
  realCoveragePercent: number;
  strictCoveragePercent: number;
  blockingRatePercent: number;
  affectedProjectIds: string[];
  strictReadyProjectIds: string[];
  blockingProjectIds: string[];
  affectedProjects: Array<{ projectId: string; name: string; url: string }>;
  strictReadyProjects: Array<{ projectId: string; name: string; url: string }>;
  blockingProjects: Array<{ projectId: string; name: string; url: string }>;
  primaryFailureCategory?: "auth" | "permission" | "rate_limit" | "network" | "validation" | "config" | "unavailable" | "other" | null;
  primaryFailureCode?: string | null;
  primaryBlockingReason?: string | null;
  suggestedActionPath?: string | null;
  suggestedActionLabel?: string | null;
  realConnectionCount: number;
  fallbackConnectionCount: number;
  unconfiguredConnectionCount: number;
  strictEligibleCount: number;
  antiBotBlockedCount: number;
  manualInterventionRequiredCount: number;
}

export interface ConnectorProjectHealthItem {
  projectId: string;
  name: string;
  url: string;
  checkedAt: string;
  connectionHealth: ConnectionHealth;
  totalConnectionCount: number;
  realConnectionCount: number;
  fallbackConnectionCount: number;
  unconfiguredConnectionCount: number;
  strictEligibleCount: number;
  issueCount: number;
  issues: string[];
}

export interface WorkspaceConnectorsHealthReport {
  generatedAt: string;
  projectCount: number;
  degradedProjectCount: number;
  unavailableProjectCount: number;
  totalConnectionCount: number;
  realConnectionCount: number;
  fallbackConnectionCount: number;
  unconfiguredConnectionCount: number;
  strictEligibleCount: number;
  strictGapCount: number;
  antiBotBlockedConnectionCount: number;
  antiBotManualInterventionCount: number;
  readConnectionCount: number;
  readRealConnectionCount: number;
  readStrictEligibleCount: number;
  readRealCoveragePercent: number;
  readStrictCoveragePercent: number;
  readRealLastEvidenceAt?: string | null;
  writeConnectionCount: number;
  writeRealConnectionCount: number;
  writeStrictEligibleCount: number;
  writeRealCoveragePercent: number;
  writeStrictCoveragePercent: number;
  writeRealLastEvidenceAt?: string | null;
  realProviderCount: number;
  realProviderRatePercent: number;
  zeroRealProviderCount: number;
  zeroRealProviderRatePercent: number;
  zeroRealProviders: ConnectorKind[];
  zeroStrictProviderCount: number;
  zeroStrictProviderRatePercent: number;
  zeroStrictProviders: ConnectorKind[];
  strictReadyProviderCount: number;
  strictReadyProviderRatePercent: number;
  strictReadyProviders: ConnectorKind[];
  partialStrictProviderCount: number;
  partialStrictProviderRatePercent: number;
  partialStrictProviders: ConnectorKind[];
  fullyStrictProviderCount: number;
  fullyStrictProviderRatePercent: number;
  fullyStrictProviders: ConnectorKind[];
  providerCoverage: ConnectorProviderCoverageItem[];
  topBlockingProviders: ConnectorProviderCoverageItem[];
  topStrictGapProviders: ConnectorProviderCoverageItem[];
  topStrictReadyProviders: ConnectorProviderCoverageItem[];
  projects: ConnectorProjectHealthItem[];
}

export interface ConnectorRefreshResult {
  projectId: string;
  provider: ConnectorKind;
  status: ConnectorStatus;
  checkedAt: string;
  connectionHealth: ConnectionHealth;
  issue?: string | null;
  connection: ProjectConnection;
  evidence: SourceEvidence;
}

export interface BulkConnectionsTestRequest {
  projectIds: string[];
}

export interface BulkConnectionsTestResult {
  projectIds: string[];
  testedCount: number;
  skippedProjectIds: string[];
  results: ProjectConnectionsTestResult[];
}

export interface BulkConnectorRefreshRequest {
  projectIds: string[];
}

export interface BulkConnectorRefreshResult {
  provider: ConnectorKind;
  projectIds: string[];
  refreshedCount: number;
  skippedProjectIds: string[];
  results: ConnectorRefreshResult[];
}

export interface BulkStrictGapRefreshRequest {
  projectIds: string[];
  providers: ConnectorKind[];
  maxProviders: number;
}

export interface BulkStrictGapRefreshResult {
  generatedAt: string;
  providerCount: number;
  refreshedCount: number;
  skippedProjectCount: number;
  providerResults: BulkConnectorRefreshResult[];
  notes: string[];
}

export interface BulkBlockingRefreshRequest {
  projectIds: string[];
  providers: ConnectorKind[];
  maxProviders: number;
}

export interface BulkBlockingRefreshResult {
  generatedAt: string;
  providerCount: number;
  refreshedCount: number;
  skippedProjectCount: number;
  providerResults: BulkConnectorRefreshResult[];
  notes: string[];
}

export interface ProjectCreateRequest {
  name: string;
  intake: SiteIntake;
}

export interface ApprovalDecisionRequest {
  decision: ApprovalStatus;
  actor?: string;
  note?: string;
}

export interface BulkApprovalRequest {
  taskIds: string[];
  actor?: string;
  note?: string;
}

export interface BulkApprovalResult {
  taskIds: string[];
  approvedCount: number;
  skippedTaskIds: string[];
  bundles: WorkflowBundle[];
}

export interface DeploymentActionRequest {
  actor?: string;
  note?: string;
}

export interface RollbackActionRequest {
  actor?: string;
  reason?: string;
}

export interface ProjectDetail {
  project: ProjectSummary;
  workflow: WorkflowBundle;
  state: ProjectState;
  connections: ProjectConnection[];
  experimentAssignment?: WorkspaceExperimentAssignmentReport | null;
  localizationAssignment?: WorkspaceLocalizationAssignmentReport | null;
  runtimeRoute?: RuntimeRouteReport | null;
  deploymentHistory: DeploymentHistoryEntry[];
  rollbackHistory: RollbackHistoryEntry[];
  runs: ProjectRun[];
  audits: Array<Record<string, unknown>>;
  marketEvidence?: MarketEvidenceReport | null;
  businessClassifier?: BusinessClassifierReport | null;
  styleExtraction?: StyleExtractionReport | null;
  contentStrategy?: ContentStrategyReport | null;
  adAudit?: AdAuditReport | null;
  adaptiveComponents?: AdaptiveComponentReport | null;
  technicalSeo?: TechnicalSeoReport | null;
  technicalSeoPatch?: TechnicalSeoPatchReport | null;
}

export interface ContentCluster {
  title: string;
  intent: "informational" | "commercial" | "transactional";
  primaryKeyword: string;
  secondaryKeywords: string[];
  contentType: string;
  targetUrl: string;
  wordCount: number;
  priority: number;
  internalLinks: string[];
  nextStep: string;
}

export interface ContentCalendarEntry {
  week: number;
  topic: string;
  targetKeyword: string;
  contentType: string;
  wordCount: number;
  internalLinkTargets: string[];
  priority: number;
}

export interface ContentStrategyReport {
  reportId: string;
  projectId: string;
  pillarPage: string;
  pillarKeyword: string;
  pillarIntent: "informational" | "commercial" | "transactional";
  topicClusters: ContentCluster[];
  calendar: ContentCalendarEntry[];
  internalLinkBlueprint: string[];
  marketSignals: string[];
  notes: string[];
}

export interface AdSlotRecommendation {
  pageUrl: string;
  slotName: string;
  placement: string;
  reason: string;
  riskScore: number;
  allowed: boolean;
  evidence?: string[];
  negativeConditions?: string[];
}

export interface AdSlotAuditPageFinding {
  pageUrl: string;
  template: string;
  slotName: string;
  placement: string;
  allowed: boolean;
  riskScore: number;
  reason: string;
  ctaDistance: number;
  layoutRisk: "low" | "medium" | "high";
  rollbackSupported: boolean;
  evidence: string[];
}

export interface AdAuditReport {
  reportId: string;
  projectId: string;
  adAllowed: boolean;
  reason: string;
  adConnectorStatus?: ConnectorStatus | null;
  adProviderFamily?: string | null;
  adProviderName?: string | null;
  adProviderRef?: string | null;
  adInventoryStatus?: string | null;
  adImpressionsDaily?: number | null;
  adClicksDaily?: number | null;
  adCtr?: number | null;
  adFillRate?: number | null;
  adRpm?: number | null;
  adRevenueEstimateDaily?: number | null;
  adRevenueEstimateMonthly?: number | null;
  adRevenueSettledDaily?: number | null;
  adRevenueSettlementWindow?: string | null;
  adRevenueCurrency?: string | null;
  adPolicyTier?: string | null;
  adPayoutThreshold?: number | null;
  adGeoCoverage: string[];
  adProviderProgram?: string | null;
  adRevenueProvenance?: string[];
  strictPublishEligible?: boolean;
  fallbackReason?: string | null;
  failureCode?: string | null;
  providerExamples: string[];
  negativeConditions: string[];
  recommendations: AdSlotRecommendation[];
  pageFindings: AdSlotAuditPageFinding[];
  templateCoverage: string[];
  notes: string[];
}

export interface WorkspaceAdAuditHistoryItem {
  reportId: string;
  generatedAt: string;
  projectId: string;
  projectName: string;
  adAllowed: boolean;
  reason: string;
  adConnectorStatus?: ConnectorStatus | null;
  adProviderFamily?: string | null;
  adProviderName?: string | null;
  adProviderRef?: string | null;
  adInventoryStatus?: string | null;
  adRevenueEstimateDaily?: number | null;
  adRevenueEstimateMonthly?: number | null;
  adRevenueSettledDaily?: number | null;
  adRevenueCurrency?: string | null;
  adPolicyTier?: string | null;
  strictPublishEligible?: boolean;
  fallbackReason?: string | null;
  failureCode?: string | null;
  providerExamples: string[];
  negativeConditions: string[];
  recommendationCount: number;
}

export interface WorkspaceAdAuditHistoryReport {
  generatedAt: string;
  projectId?: string | null;
  total: number;
  projectCount: number;
  allowedCount: number;
  blockedCount: number;
  strictPublishEligibleCount: number;
  connectorConnectedCount: number;
  latestReportId?: string | null;
  latestProjectId?: string | null;
  latestProjectName?: string | null;
  latestAdProviderFamily?: string | null;
  latestAdProviderName?: string | null;
  latestAdInventoryStatus?: string | null;
  latestAdAllowed?: boolean | null;
  latestStrictPublishEligible?: boolean | null;
  latestReason?: string | null;
  latestFailureCode?: string | null;
  latestFallbackReason?: string | null;
  latestAdRevenueEstimateDaily?: number | null;
  latestAdRevenueEstimateMonthly?: number | null;
  latestAdRevenueCurrency?: string | null;
  latestNegativeConditionCount?: number | null;
  latestRecommendationCount?: number | null;
  entries: WorkspaceAdAuditHistoryItem[];
}

export interface AdaptiveComponentSuggestion {
  componentName: string;
  previewTarget: string;
  placement: string;
  behavior: string;
  rollbackSupported: boolean;
  skillIds: string[];
  evidence: string[];
}

export interface AdaptiveComponentReport {
  reportId: string;
  projectId: string;
  siteId: string;
  suggestions: AdaptiveComponentSuggestion[];
  moduleStack: string[];
  notes: string[];
}

export interface TechnicalSeoFinding {
  area: string;
  issue: string;
  impact: "high" | "medium" | "low";
  evidence: string[];
  fix: string;
  priority: number;
}

export interface TechnicalSeoReport {
  reportId: string;
  projectId: string;
  overallHealth: "healthy" | "degraded" | "critical";
  crawlability: TechnicalSeoFinding[];
  onPage: TechnicalSeoFinding[];
  content: TechnicalSeoFinding[];
  performance: TechnicalSeoFinding[];
  actionPlan: string[];
  notes: string[];
}

export interface TechnicalSeoPatchStep {
  area: string;
  field: string;
  before: string;
  after: string;
  skillId: string;
  verified: boolean;
  rollbackSupported: boolean;
  evidence: string[];
}

export interface TechnicalSeoPatchReport {
  reportId: string;
  projectId: string;
  taskId: string;
  verifiedPatch: boolean;
  strictMode: boolean;
  patchAudit?: Record<string, unknown>;
  steps: TechnicalSeoPatchStep[];
  notes: string[];
}

export interface RegressionCaseResult {
  sampleId: string;
  name: string;
  siteClass: SiteClass;
  riskScore: number;
  deploymentMode: DeploymentMode;
  connectionHealth: ConnectionHealth;
  seoPreviewReady: boolean;
  adRecommendation: string;
  adAllowed: boolean;
  passed: boolean;
  notes: string[];
}

export interface RegressionReport {
  reportId: string;
  generatedAt: string;
  sampleCount: number;
  seoPreviewCount: number;
  adRecommendationCount: number;
  noAdCount: number;
  passCount: number;
  failCount: number;
  cases: RegressionCaseResult[];
  notes: string[];
}

export interface AcceptanceGateResult {
  gateId: string;
  name: string;
  passed: boolean;
  expected: string;
  actual: string;
  quickActionPath?: string | null;
  quickActionLabel?: string | null;
  notes: string[];
}

export interface AcceptanceProviderEvidence {
  provider: string;
  projectId: string;
  projectName: string;
  providerMode: "real" | "fallback" | "unconfigured";
  evidenceRef?: string | null;
  evidenceLabel?: string | null;
  evidenceAt?: string | null;
}

export interface AcceptanceReport {
  reportId: string;
  generatedAt: string;
  regression: RegressionReport;
  strictProvidersEnabled: boolean;
  billingGatewayReady: boolean;
  billingGatewayRouteReadyCount: number;
  billingGatewayRouteCount: number;
  promptRegistryCount: number;
  activePromptCount: number;
  rollbackReadyCount: number;
  totalProjectCount: number;
  readRealEvidenceCount: number;
  writeRealEvidenceCount: number;
  readRealProviderCount: number;
  writeRealProviderCount: number;
  readRealProviders: string[];
  writeRealProviders: string[];
  readRealEvidence: AcceptanceProviderEvidence[];
  writeRealEvidence: AcceptanceProviderEvidence[];
  marketEvidenceConnectedCount: number;
  marketEvidenceSyntheticCount: number;
  marketEvidenceFailedCount: number;
  marketEvidenceFreshCount: number;
  marketEvidenceLastFetchedAt?: string | null;
  gates: AcceptanceGateResult[];
  passed: boolean;
  notes: string[];
}

export interface AcceptanceHistoryEntry {
  reportId: string;
  generatedAt: string;
  passed: boolean;
  failedGateIds: string[];
  failedGateCount: number;
  report: AcceptanceReport;
}

export interface AcceptanceHistoryReport {
  generatedAt: string;
  total: number;
  limit: number;
  entries: AcceptanceHistoryEntry[];
}

export interface ProductBenchmarkReference {
  name: string;
  category: "seo_monitoring" | "visual_monitoring" | "edge_runtime" | "ads_reporting" | "settlement" | "experimentation";
  sourceUrl: string;
  observedCapabilities: string[];
}

export interface ProductCapabilityBenchmark {
  capabilityId: string;
  title: string;
  currentStatus: "production_ready" | "operational" | "partial" | "missing";
  maturityScore: number;
  comparableProducts: string[];
  implementedEvidence: string[];
  remainingGaps: string[];
  nextActions: string[];
  priority: "p0" | "p1" | "p2" | "p3";
}

export interface ProductBenchmarkReport {
  generatedAt: string;
  projectId?: string | null;
  referenceCount: number;
  capabilityCount: number;
  productionReadyCount: number;
  partialCount: number;
  missingCount: number;
  averageMaturityScore: number;
  references: ProductBenchmarkReference[];
  capabilities: ProductCapabilityBenchmark[];
  recommendedNextCapabilityIds: string[];
  notes: string[];
}

export interface RemainingTaskItem {
  taskId: string;
  title: string;
  priority: "p0" | "p1" | "p2" | "p3";
  sourceCapabilityId: string;
  status: "blocked" | "planned";
  blocking: boolean;
  acceptanceGateIds: string[];
  remainingGaps: string[];
  nextAction?: string | null;
  quickActionPath?: string | null;
  quickActionLabel?: string | null;
}

export interface RemainingTaskReport {
  generatedAt: string;
  projectId?: string | null;
  total: number;
  blockingCount: number;
  p0Count: number;
  p1Count: number;
  p2Count: number;
  p3Count: number;
  items: RemainingTaskItem[];
  notes: string[];
}

export interface RemainingTaskBoardGroup {
  groupId: "provider" | "visual" | "runtime" | "ads" | "billing" | "experiment" | "other";
  title: string;
  total: number;
  blockingCount: number;
  p0Count: number;
  p1Count: number;
  p2Count: number;
  p3Count: number;
  taskIds: string[];
}

export interface RemainingTaskBoardReport {
  generatedAt: string;
  projectId?: string | null;
  total: number;
  blockingCount: number;
  groups: RemainingTaskBoardGroup[];
  notes: string[];
}

export interface RegressionSample {
  sampleId: string;
  name: string;
  intake: SiteIntake;
  expectedSeoPreview: boolean;
  expectedAdAllowed: boolean;
  expectedRiskBand: "low" | "medium" | "high";
  notes: string[];
}

export interface RegressionSampleSet {
  generatedAt: string;
  sampleCount: number;
  samples: RegressionSample[];
  notes: string[];
}

export interface PromptVersion {
  promptId: string;
  role: "sniffer" | "query" | "strategist" | "ux" | "policy" | "coordinator";
  name: string;
  version: string;
  status: "active" | "draft" | "archived";
  owner: string;
  summary: string;
  checksum: string;
  lastReviewedAt: string;
  usedBy: string[];
  notes: string[];
}

export interface PromptRegistry {
  generatedAt: string;
  versions: PromptVersion[];
  notes: string[];
}

export interface VisualRegressionCase {
  sampleId: string;
  name: string;
  pageUrl: string;
  projectId?: string | null;
  projectName?: string | null;
  workflowTaskId?: string | null;
  deploymentArtifactRef?: string | null;
  baselineLabel: string;
  previewLabel: string;
  expectedMaxDiffPercent: number;
  actualDiffPercent: number;
  artifactRef: string;
  taskId: string;
  executionMode?: "playwright" | "manifest";
  baselineArtifactRef?: string | null;
  previewArtifactRef?: string | null;
  diffArtifactRef?: string | null;
  diffMethod?: "pixel-rgba" | "byte-fallback" | null;
  mismatchPixels?: number | null;
  comparedPixels?: number | null;
  mismatchRatio?: number | null;
  meanChannelDelta?: number | null;
  maxChannelDelta?: number | null;
  thresholdDelta?: number | null;
  thresholdExceededPixels?: number | null;
  thresholdExceededRatio?: number | null;
  providerStatus?: "connected" | "failed" | "not_configured" | "fallback" | null;
  providerFailureCode?: string | null;
  visualFarmProvider?: string | null;
  visualFarmRunId?: string | null;
  visualFarmEndpoint?: string | null;
  visualFarmLatencyMs?: number | null;
  visualFarmStrictBlocked?: boolean;
  screenshotCount?: number | null;
  providerAttempts?: Record<string, unknown>[];
  ctaPreserved: boolean;
  layoutShiftRisk: "low" | "medium" | "high";
  passed: boolean;
  notes: string[];
}

export interface VisualRegressionReport {
  reportId: string;
  generatedAt: string;
  sampleCount: number;
  passCount: number;
  failCount: number;
  averageDiffPercent: number;
  cases: VisualRegressionCase[];
  notes: string[];
}

export interface VisualRegressionRun {
  runId: string;
  executedAt: string;
  sampleCount: number;
  passCount: number;
  failCount: number;
  averageDiffPercent: number;
  strictMode: boolean;
  farmProvider?: string | null;
  connectedCaseCount: number;
  strictBlockedCaseCount: number;
  failedCaseCount: number;
  fallbackCaseCount: number;
  notConfiguredCaseCount: number;
  configuredEndpointCount: number;
  configuredEndpoints: string[];
  attemptedEndpointCount: number;
  attemptedEndpoints: string[];
  failedEndpoints: string[];
  providerAttemptCount: number;
  averageFarmLatencyMs?: number | null;
  cases: VisualRegressionCase[];
}

export interface VisualRegressionRunsReport {
  generatedAt: string;
  runs: VisualRegressionRun[];
}

export interface VisualRegressionFailureBucket {
  category: string;
  count: number;
  retryable: boolean;
  failureCodes: string[];
  sampleIds: string[];
  suggestedAction: string;
  quickActionPath?: string | null;
}

export interface VisualRegressionHealthReport {
  generatedAt: string;
  strictMode: boolean;
  configuredEndpointCount: number;
  configuredEndpoints: string[];
  runCount: number;
  lastRunId?: string | null;
  lastRunExecutedAt?: string | null;
  lastRunConnectedCaseCount: number;
  lastRunFailedCaseCount: number;
  lastRunFallbackCaseCount: number;
  lastRunNotConfiguredCaseCount: number;
  lastRunStrictBlockedCaseCount: number;
  lastRunAttemptedEndpointCount: number;
  lastRunFailedEndpoints: string[];
  failureBuckets: VisualRegressionFailureBucket[];
  notes: string[];
}

export interface VisualFarmStatusReport {
  generatedAt: string;
  strictMode: boolean;
  configuredEndpointCount: number;
  configuredEndpoints: string[];
  accessTokenConfigured: boolean;
  timeoutMs: number;
  runCount: number;
  lastRunId?: string | null;
  lastRunExecutedAt?: string | null;
  lastRunConnectedCaseCount: number;
  lastRunFailedCaseCount: number;
  lastRunFallbackCaseCount: number;
  lastRunNotConfiguredCaseCount: number;
  lastRunStrictBlockedCaseCount: number;
  probeFreshnessMinutes: number;
  lastProbeExecutedAt?: string | null;
  lastProbeConnectedCount: number;
  lastProbeFailedCount: number;
  lastProbeBlockingCount: number;
  lastProbeRecoverableCount: number;
  probeFresh: boolean;
  probeStale: boolean;
  strictPublishReady: boolean;
  failureBuckets: VisualRegressionFailureBucket[];
  notes: string[];
}

export interface VisualFarmEndpointProbe {
  endpoint: string;
  status: "connected" | "failed" | "not_configured";
  latencyMs?: number | null;
  httpStatus?: number | null;
  failureCode?: string | null;
  retryable: boolean;
  blocking: boolean;
  alertSeverity: "critical" | "warning" | "info";
  message?: string | null;
}

export interface VisualFarmProbeReport {
  generatedAt: string;
  strictMode: boolean;
  configuredEndpointCount: number;
  probedEndpointCount: number;
  connectedCount: number;
  failedCount: number;
  notConfiguredCount: number;
  blockingCount: number;
  recoverableCount: number;
  accessTokenConfigured: boolean;
  timeoutMs: number;
  probes: VisualFarmEndpointProbe[];
  notes: string[];
}

export interface VisualFarmProbeEnqueueResult {
  enqueued: boolean;
  skippedDuplicate: boolean;
  jobId: string;
  stage: string;
  message: string;
}

export interface VisualFarmProbeHistoryEntry {
  auditId: string;
  actor: string;
  createdAt: string;
  strictMode: boolean;
  configuredEndpointCount: number;
  probedEndpointCount: number;
  connectedCount: number;
  failedCount: number;
  notConfiguredCount: number;
  blockingCount: number;
  recoverableCount: number;
  accessTokenConfigured: boolean;
  timeoutMs: number;
  probes: VisualFarmEndpointProbe[];
  notes: string[];
  spanId?: string | null;
  traceId?: string | null;
}

export interface VisualFarmProbeHistoryReport {
  generatedAt: string;
  entries: VisualFarmProbeHistoryEntry[];
}

export interface AlertItem {
  alertId: string;
  createdAt: string;
  category: "auth" | "config" | "permission" | "network" | "rate_limit" | "validation" | "unavailable" | "other";
  severity: "critical" | "warning" | "info";
  blocking: boolean;
  failureCode: string;
  provider: string;
  projectCount: number;
  projectIds: string[];
  summary: string;
  remediationPath?: string | null;
}

export interface AlertReport {
  reportId: string;
  generatedAt: string;
  blocking: AlertItem[];
  recoverable: AlertItem[];
  notes: string[];
}

export interface AlertHistoryReport {
  generatedAt: string;
  total: number;
  limit: number;
  offset: number;
  order: "desc" | "asc";
  cursor?: string | null;
  nextCursor?: string | null;
  hasMore: boolean;
  snapshots: AlertReport[];
}

export interface AlertDeliveryEntry {
  auditId: string;
  createdAt: string;
  status: "sent" | "failed";
  route: string;
  target: string;
  channel: string;
  reportId?: string | null;
  blockingCount: number;
  recoverableCount: number;
  statusCode?: number | null;
  error?: string | null;
  spanId?: string | null;
  traceId?: string | null;
}

export interface AlertDeliveryReport {
  generatedAt: string;
  total: number;
  sent: number;
  failed: number;
  entries: AlertDeliveryEntry[];
}

export interface AlertEmitStatusReport {
  generatedAt: string;
  cooldownSeconds: number;
  executedCount24h: number;
  suppressedCount24h: number;
  lastExecutedAt?: string | null;
  lastSuppressedAt?: string | null;
  lastSignature?: string | null;
  notes: string[];
}

export interface AlertEmitHistoryEntry {
  auditId: string;
  createdAt: string;
  status: "executed" | "suppressed";
  signature?: string | null;
  cooldownSeconds: number;
  blockingCount: number;
  recoverableCount: number;
  spanId?: string | null;
  traceId?: string | null;
}

export interface AlertEmitHistoryReport {
  generatedAt: string;
  total: number;
  executed: number;
  suppressed: number;
  entries: AlertEmitHistoryEntry[];
}

export interface AlertPreset {
  presetId: string;
  name: string;
  description: string;
  projectIds: string[];
  categories: string[];
  severities: string[];
  providers: string[];
  blocking?: boolean | null;
  updatedAt: string;
}

export interface AlertPresetCollection {
  generatedAt: string;
  presets: AlertPreset[];
}

export interface AlertPresetUpdateRequest {
  presets: AlertPreset[];
}

export interface AlertRule {
  ruleId: string;
  enabled: boolean;
  description: string;
  categories: string[];
  failureCodes: string[];
  providers: string[];
  setBlocking?: boolean | null;
  setSeverity?: "critical" | "warning" | "info" | null;
  priority: number;
  updatedAt: string;
}

export interface AlertRuleCollection {
  generatedAt: string;
  rules: AlertRule[];
}

export interface AlertRuleUpdateRequest {
  rules: AlertRule[];
}

export interface OnCallRoute {
  routeId: string;
  enabled: boolean;
  description: string;
  categories: string[];
  severities: string[];
  providers: string[];
  blocking?: boolean | null;
  primaryChannels: string[];
  escalationChannels: string[];
  escalationAfterMinutes: number;
  rotationMembers: string[];
  rotationTimezone: string;
  rotationHandoffHour: number;
  updatedAt: string;
}

export interface OnCallPolicyCollection {
  generatedAt: string;
  routes: OnCallRoute[];
  notes: string[];
}

export interface OnCallPolicyUpdateRequest {
  routes: OnCallRoute[];
}

export interface OnCallCoverageItem {
  routeId: string;
  enabled: boolean;
  rotationEnabled: boolean;
  rotationTimezone: string;
  rotationHandoffHour: number;
  memberCount: number;
  currentMember?: string | null;
  nextMember?: string | null;
  nextHandoffAt?: string | null;
}

export interface OnCallCoverageReport {
  generatedAt: string;
  routeCount: number;
  rotatingRouteCount: number;
  items: OnCallCoverageItem[];
}

export interface SkillRegressionCase {
  skillId: string;
  suite: string;
  name: string;
  destructive: boolean;
  requiredApproval: boolean;
  rollbackSupported: boolean;
  observabilityReady: boolean;
  failureContractPresent: boolean;
  passed: boolean;
  notes: string[];
}

export interface SkillRegressionReport {
  reportId: string;
  generatedAt: string;
  sampleCount: number;
  passCount: number;
  failCount: number;
  destructiveCount: number;
  rollbackSupportedCount: number;
  cases: SkillRegressionCase[];
  notes: string[];
}
