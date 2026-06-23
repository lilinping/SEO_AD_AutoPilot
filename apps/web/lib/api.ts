import type {
    ApprovalDecisionRequest,
    BulkApprovalRequest,
    BulkApprovalResult,
    BulkConnectorRefreshRequest,
    BulkConnectorRefreshResult,
    BulkBlockingRefreshRequest,
    BulkBlockingRefreshResult,
    BulkStrictGapRefreshRequest,
    BulkStrictGapRefreshResult,
    BulkConnectionsTestRequest,
    BulkConnectionsTestResult,
    BulkProjectSyncRequest,
    BulkProjectSyncResult,
    ConnectorKind,
    ConnectorRefreshResult,
    ConnectorsHealthResult,
    ConnectorFailureReport,
    ProjectConnectionEvidenceReport,
    ConnectorRetryRequest,
    ConnectorRetryResult,
    ConnectorRetryHistoryReport,
    BulkConnectorActionHistoryReport,
    VisualRegressionRetryRequest,
    VisualRegressionRetryResult,
    VisualRegressionRunEnqueueResult,
    VisualRegressionRunExecuteRequest,
    VisualRegressionRetryHistoryReport,
    VisualRegressionRunHistoryReport,
    VisualRegressionRemediationReport,
    DeploymentHistoryReport,
    ProjectConnectionHistoryReport,
    WorkspaceConnectionEvidenceReport,
    WorkspaceConnectionHistoryReport,
    ConnectorRemediationReport,
    WorkspaceConnectorsHealthReport,
    AlertReport,
    AlertHistoryReport,
    AlertDeliveryReport,
    AlertEmitStatusReport,
    AlertEmitHistoryReport,
    AlertPresetCollection,
    AlertPresetUpdateRequest,
    AlertRuleCollection,
    AlertRuleUpdateRequest,
    OnCallPolicyCollection,
    OnCallPolicyUpdateRequest,
    OnCallCoverageReport,
  WorkspaceBillingReport,
  WorkspaceBillingSettlementExecutionHistoryReport,
  WorkspaceBillingSettlementExecutionReport,
  WorkspaceBillingSettlementExecutionRequest,
    WorkspaceBillingSettlementGatewayHistoryReport,
    WorkspaceBillingSettlementGatewayPolicy,
    WorkspaceBillingSettlementGatewayPolicyUpdateRequest,
    WorkspaceBillingSettlementGatewayPublishReport,
    WorkspaceBillingSettlementProviderRequirementsReport,
    WorkspaceBillingSettlementGatewayReport,
    WorkspaceBillingSettlementGatewayProviderStatusReport,
    WorkspaceBillingPolicyUpdateRequest,
    WorkspaceExperimentAssignmentReport,
    WorkspaceExperimentAssignmentRequest,
    WorkspaceExperimentReport,
    WorkspaceExperimentPolicyUpdateRequest,
    WorkspaceLocalizationReport,
    WorkspaceLocalizationPolicyUpdateRequest,
    WorkspaceLocalizationAssignmentReport,
    WorkspaceLocalizationAssignmentRequest,
    WorkspaceTemplateMarketReport,
    WorkspaceTemplateMarketPolicyUpdateRequest,
    WorkspaceModelGatewayHistoryReport,
    WorkspaceModelGatewayReport,
    WorkspaceModelGatewayPolicyUpdateRequest,
    WorkspaceModelGatewayProviderStatusReport,
    RuntimeEdgeGatewayProviderStatusReport,
    VisualFarmGatewayProviderStatusReport,
    RuntimeRouteReport,
    RuntimeRouteRequest,
    AdAuditReport,
    WorkspaceAdAuditHistoryReport,
    AcceptanceReport,
    AcceptanceHistoryReport,
    ProductBenchmarkReport,
    RemainingTaskReport,
    RemainingTaskBoardReport,
    DashboardSnapshot,
    DeploymentActionRequest,
    ContentStrategyReport,
    PromptRegistry,
    ProjectConnections,
    ProjectConnectionsTestResult,
    ProjectConnectionsUpdateRequest,
    ProjectCreateRequest,
    ProjectDetail,
    ProjectRuntimeRouteHistoryReport,
    MarketEvidenceReport,
    MarketEvidenceHealthReport,
    MarketEvidenceProviderStatusReport,
    ProjectCruiseHealthReport,
    WorkspacePolicyUpdateRequest,
    WorkspaceCruiseHealthReport,
    WorkspaceMarketEvidenceHealthReport,
    WorkspaceRuntimeRouteHealthReport,
    WorkspaceRuntimeRouteHistoryReport,
  ProjectSummary,
    ProjectRun,
    RegressionReport,
    RegressionSampleSet,
    RollbackHistoryReport,
    SkillRegressionReport,
    VisualRegressionReport,
    VisualRegressionHealthReport,
    VisualFarmStatusReport,
    VisualFarmProbeReport,
    VisualFarmProbeEnqueueResult,
    VisualFarmProbeHistoryReport,
    VisualRegressionRunsReport,
    ObservabilityStatusReport,
    WorkerExecutionHistoryReport,
    WorkerQueueHealthReport,
    WorkerServiceHealthReport,
    WorkerRunOnceResult,
    ProjectSyncRequest,
    RollbackActionRequest,
    SiteIntake,
    TechnicalSeoReport,
    WorkflowBundle,
} from "@seo-ad-autopilot/contracts";

const API_BASE = process.env.NEXT_PUBLIC_AUTOPILOT_API_URL ?? "http://127.0.0.1:8000/api";
const API_KEY = process.env.NEXT_PUBLIC_SEO_AD_BOT_API_KEY ?? process.env.SEO_AD_BOT_API_KEY ?? "dev-key";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      ...(init?.headers ?? {}),
    },
  });
  
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function getOverview(): Promise<DashboardSnapshot> {
  return request<DashboardSnapshot>("/overview")
}

export async function getProjects(): Promise<ProjectSummary[]> {
  const overview = await getOverview();
  return overview.projects;
}

export async function createProject(payload: ProjectCreateRequest): Promise<ProjectSummary> {
  return request<ProjectSummary>("/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function analyzeProject(projectId: string, intake: SiteIntake): Promise<WorkflowBundle> {
  return request<WorkflowBundle>(`/projects/${projectId}/analyze`, {
    method: "POST",
    body: JSON.stringify(intake),
  });
}

export async function syncProject(projectId: string, payload?: ProjectSyncRequest): Promise<WorkflowBundle> {
  return request<WorkflowBundle>(`/projects/${projectId}/sync`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export async function bulkSyncProjects(payload: BulkProjectSyncRequest): Promise<BulkProjectSyncResult> {
  return request<BulkProjectSyncResult>("/bulk/projects/sync", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getProjectDetail(projectId: string): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/projects/${projectId}`)
}

export async function resolveProjectRuntimeRoute(
  projectId: string,
  payload: RuntimeRouteRequest,
): Promise<RuntimeRouteReport> {
  return request<RuntimeRouteReport>(
    `/projects/${projectId}/runtime-route`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function getProjectMarketEvidence(projectId: string): Promise<MarketEvidenceReport> {
  return request<MarketEvidenceReport>(`/projects/${projectId}/market-evidence`);
}

export async function getProjectMarketEvidenceHealth(projectId: string): Promise<MarketEvidenceHealthReport> {
  return request<MarketEvidenceHealthReport>(
    `/projects/${projectId}/market-evidence/health`,
  );
}

export async function getProjectCruiseHealth(projectId: string): Promise<ProjectCruiseHealthReport> {
  return request<ProjectCruiseHealthReport>(
    `/projects/${projectId}/cruise/health`,
  );
}

export async function getWorkspaceMarketEvidenceHealth(): Promise<WorkspaceMarketEvidenceHealthReport> {
  return request<WorkspaceMarketEvidenceHealthReport>(
    "/market-evidence/health",
  );
}

export async function getMarketEvidenceProviderStatusReport(): Promise<MarketEvidenceProviderStatusReport> {
  return request<MarketEvidenceProviderStatusReport>(
    "/market-evidence/providers",
  );
}

export async function getWorkspaceCruiseHealth(): Promise<WorkspaceCruiseHealthReport> {
  return request<WorkspaceCruiseHealthReport>(
    "/worker/cruise/health",
  );
}

export async function getWorkspaceRuntimeRouteHealth(projectId?: string): Promise<WorkspaceRuntimeRouteHealthReport> {
  const query = new URLSearchParams();
  if (projectId?.trim()) {
    query.set("projectId", projectId.trim());
  }
  return request<WorkspaceRuntimeRouteHealthReport>(
    query.toString() ? `/runtime-route/health?${query.toString()}` : "/runtime-route/health",
  );
}

export async function getWorkspaceRuntimeRouteHistory(limit = 20, projectId?: string): Promise<WorkspaceRuntimeRouteHistoryReport> {
  const boundedLimit = Math.max(1, Math.min(100, Number.isFinite(limit) ? limit : 20));
  const query = new URLSearchParams();
  query.set("limit", String(boundedLimit));
  if (projectId?.trim()) {
    query.set("projectId", projectId.trim());
  }
  return request<WorkspaceRuntimeRouteHistoryReport>(
    `/runtime-route/history?${query.toString()}`,
  );
}

export async function updateWorkspacePolicy(payload: WorkspacePolicyUpdateRequest): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/policy", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function getWorkspaceBillingReport(): Promise<WorkspaceBillingReport> {
  return request<WorkspaceBillingReport>("/billing")
}

export async function updateWorkspaceBillingPolicy(payload: WorkspaceBillingPolicyUpdateRequest): Promise<WorkspaceBillingReport> {
  return request<WorkspaceBillingReport>("/billing", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function executeWorkspaceBillingSettlement(
  payload: WorkspaceBillingSettlementExecutionRequest,
): Promise<WorkspaceBillingSettlementExecutionReport> {
  return request<WorkspaceBillingSettlementExecutionReport>(
    "/billing/settlement/execute",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function getWorkspaceBillingSettlementHistory(
  limit = 20,
  projectId?: string,
): Promise<WorkspaceBillingSettlementExecutionHistoryReport> {
  const query = new URLSearchParams();
  query.set("limit", String(limit));
  if (projectId?.trim()) {
    query.set("projectId", projectId.trim());
  }
  return request<WorkspaceBillingSettlementExecutionHistoryReport>(
    `/billing/settlement/history?${query.toString()}`,
  );
}

export async function getWorkspaceBillingGatewayReport(): Promise<WorkspaceBillingSettlementGatewayReport> {
  return request<WorkspaceBillingSettlementGatewayReport>("/billing/gateway")
}

export async function getWorkspaceBillingGatewayProviderStatusReport(): Promise<WorkspaceBillingSettlementGatewayProviderStatusReport> {
  return request<WorkspaceBillingSettlementGatewayProviderStatusReport>(
    "/billing/gateway/providers",
  );
}

export async function getWorkspaceBillingSettlementProviderRequirements(): Promise<WorkspaceBillingSettlementProviderRequirementsReport> {
  return request<WorkspaceBillingSettlementProviderRequirementsReport>(
    "/billing/gateway/provider-requirements",
  );
}

export async function getWorkspaceBillingGatewayHistory(
  limit = 20,
  projectId?: string,
): Promise<WorkspaceBillingSettlementGatewayHistoryReport> {
  const query = new URLSearchParams();
  query.set("limit", String(limit));
  if (projectId?.trim()) {
    query.set("projectId", projectId.trim());
  }
  return request<WorkspaceBillingSettlementGatewayHistoryReport>(
    `/billing/gateway/history?${query.toString()}`,
  );
}

export async function updateWorkspaceBillingGatewayPolicy(
  payload: WorkspaceBillingSettlementGatewayPolicyUpdateRequest,
): Promise<WorkspaceBillingSettlementGatewayReport> {
  return request<WorkspaceBillingSettlementGatewayReport>("/billing/gateway", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function publishWorkspaceBillingGatewayPolicy(): Promise<WorkspaceBillingSettlementGatewayPublishReport> {
  return request<WorkspaceBillingSettlementGatewayPublishReport>("/billing/gateway/publish", {
    method: "POST",
  });
}

export async function getWorkspaceExperimentReport(): Promise<WorkspaceExperimentReport> {
  return request<WorkspaceExperimentReport>("/experiments")
}

export async function updateWorkspaceExperimentPolicy(payload: WorkspaceExperimentPolicyUpdateRequest): Promise<WorkspaceExperimentReport> {
  return request<WorkspaceExperimentReport>("/experiments", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function getWorkspaceExperimentAssignments(
  payload: WorkspaceExperimentAssignmentRequest,
): Promise<WorkspaceExperimentAssignmentReport> {
  return request<WorkspaceExperimentAssignmentReport>("/experiments/assign", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getWorkspaceLocalizationReport(): Promise<WorkspaceLocalizationReport> {
  return request<WorkspaceLocalizationReport>("/localization")
}

export async function updateWorkspaceLocalizationPolicy(payload: WorkspaceLocalizationPolicyUpdateRequest): Promise<WorkspaceLocalizationReport> {
  return request<WorkspaceLocalizationReport>("/localization", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function getWorkspaceLocalizationAssignment(
  payload: WorkspaceLocalizationAssignmentRequest,
): Promise<WorkspaceLocalizationAssignmentReport> {
  return request<WorkspaceLocalizationAssignmentReport>(
    "/localization/assign",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function getWorkspaceTemplateMarketReport(): Promise<WorkspaceTemplateMarketReport> {
  return request<WorkspaceTemplateMarketReport>("/template-market")
}

export async function updateWorkspaceTemplateMarketPolicy(payload: WorkspaceTemplateMarketPolicyUpdateRequest): Promise<WorkspaceTemplateMarketReport> {
  return request<WorkspaceTemplateMarketReport>("/template-market", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function getWorkspaceModelGatewayReport(): Promise<WorkspaceModelGatewayReport> {
  return request<WorkspaceModelGatewayReport>("/model-gateway")
}

export async function getWorkspaceModelGatewayProviderStatusReport(): Promise<WorkspaceModelGatewayProviderStatusReport> {
  return request<WorkspaceModelGatewayProviderStatusReport>(
    "/model-gateway/providers",
  );
}

export async function getWorkspaceModelGatewayHistory(
  limit = 20,
  projectId?: string,
): Promise<WorkspaceModelGatewayHistoryReport> {
  const query = new URLSearchParams();
  query.set("limit", String(limit));
  if (projectId?.trim()) {
    query.set("projectId", projectId.trim());
  }
  return request<WorkspaceModelGatewayHistoryReport>(
    `/model-gateway/history?${query.toString()}`,
  );
}

export async function updateWorkspaceModelGatewayPolicy(payload: WorkspaceModelGatewayPolicyUpdateRequest): Promise<WorkspaceModelGatewayReport> {
  return request<WorkspaceModelGatewayReport>("/model-gateway", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function getProjectConnections(projectId: string): Promise<ProjectConnections> {
  return request<ProjectConnections>(`/projects/${projectId}/connections`);
}

export async function getProjectConnectionHistory(projectId: string, limit = 12): Promise<ProjectConnectionHistoryReport> {
  return request<ProjectConnectionHistoryReport>(
    `/projects/${projectId}/connections/history?limit=${limit}`,
  );
}

export async function getProjectConnectionEvidence(projectId: string): Promise<ProjectConnectionEvidenceReport> {
  return request<ProjectConnectionEvidenceReport>(
    `/projects/${projectId}/connections/evidence`,
  );
}

export async function updateProjectConnections(projectId: string, payload: ProjectConnectionsUpdateRequest): Promise<ProjectConnections> {
  return request<ProjectConnections>(`/projects/${projectId}/connections`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function testProjectConnections(projectId: string): Promise<ProjectConnectionsTestResult> {
  return request<ProjectConnectionsTestResult>(`/projects/${projectId}/connections/test`, {
    method: "POST",
  });
}

export async function getProjectConnectorsHealth(projectId: string): Promise<ConnectorsHealthResult> {
  return request<ConnectorsHealthResult>(`/projects/${projectId}/connectors/health`)
}

export async function getWorkspaceConnectorsHealth(): Promise<WorkspaceConnectorsHealthReport> {
  return request<WorkspaceConnectorsHealthReport>("/connectors/health")
}

export async function getWorkspaceConnectionEvidence(options?: {
  provider?: ConnectorKind;
  mode?: "real" | "fallback" | "unconfigured";
  strictOnly?: boolean;
  limit?: number;
}): Promise<WorkspaceConnectionEvidenceReport> {
  const params = new URLSearchParams();
  if (options?.provider) params.set("provider", options.provider);
  if (options?.mode) params.set("mode", options.mode);
  if (typeof options?.strictOnly === "boolean") params.set("strictOnly", String(options.strictOnly));
  if (typeof options?.limit === "number" && Number.isFinite(options.limit)) params.set("limit", String(options.limit));
  const query = params.toString();
  const path = query ? `/connectors/evidence?${query}` : "/connectors/evidence";
  return request<WorkspaceConnectionEvidenceReport>(path)
}

export async function refreshProjectConnector(projectId: string, provider: ConnectorKind): Promise<ConnectorRefreshResult> {
  return request<ConnectorRefreshResult>(`/projects/${projectId}/connectors/${provider}/refresh`, {
    method: "POST",
  });
}

export async function bulkTestProjectConnections(payload: BulkConnectionsTestRequest): Promise<BulkConnectionsTestResult> {
  return request<BulkConnectionsTestResult>("/bulk/projects/connections/test", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function bulkRefreshProjectConnector(
  provider: ConnectorKind,
  payload: BulkConnectorRefreshRequest,
): Promise<BulkConnectorRefreshResult> {
  return request<BulkConnectorRefreshResult>(`/bulk/projects/connectors/${provider}/refresh`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function bulkRefreshMarketEvidenceConnectors(payload: {
  projectIds: string[];
  providers?: Array<"trend" | "news" | "qa">;
  maxProviders?: number;
}): Promise<any> {
  return request<any>("/bulk/connectors/market-evidence/refresh", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function bulkRefreshStrictGapConnectors(
  payload: BulkStrictGapRefreshRequest,
): Promise<BulkStrictGapRefreshResult> {
  return request<BulkStrictGapRefreshResult>("/bulk/connectors/strict-gap/refresh", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function bulkRefreshBlockingConnectors(
  payload: BulkBlockingRefreshRequest,
): Promise<BulkBlockingRefreshResult> {
  return request<BulkBlockingRefreshResult>("/bulk/connectors/blocking/refresh", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getProjectRuns(
  projectId: string,
  options?: {
    trigger?: "manual" | "schedule" | "approval" | "deploy" | "monitor" | "rollback";
    status?: "queued" | "running" | "completed" | "failed" | "rolled_back";
    limit?: number;
  },
): Promise<ProjectRun[]> {
  const params = new URLSearchParams();
  if (options?.trigger) params.set("trigger", options.trigger);
  if (options?.status) params.set("status", options.status);
  if (typeof options?.limit === "number" && Number.isFinite(options.limit)) params.set("limit", String(options.limit));
  const query = params.toString();
  const path = query ? `/projects/${projectId}/runs?${query}` : `/projects/${projectId}/runs`;
  return request<ProjectRun[]>(path);
}

export async function getProjectRuntimeRouteHistory(
  projectId: string,
  limit = 20,
): Promise<ProjectRuntimeRouteHistoryReport> {
  const boundedLimit = Math.max(1, Math.min(100, Number.isFinite(limit) ? limit : 20));
  const query = new URLSearchParams();
  query.set("limit", String(boundedLimit));
  return request<ProjectRuntimeRouteHistoryReport>(
    `/projects/${projectId}/runtime-route/history?${query.toString()}`,
  );
}

export async function getProjectDeploymentHistory(projectId: string): Promise<DeploymentHistoryReport> {
  return request<DeploymentHistoryReport>(
    `/projects/${projectId}/deployments`,
  );
}

export async function getProjectRollbackHistory(projectId: string): Promise<RollbackHistoryReport> {
  return request<RollbackHistoryReport>(
    `/projects/${projectId}/rollbacks`,
  );
}

export async function getProjectContentStrategy(projectId: string): Promise<ContentStrategyReport> {
  return request<ContentStrategyReport>(`/projects/${projectId}/content-strategy`)
}

export async function getProjectAdAudit(projectId: string): Promise<AdAuditReport> {
  return request<AdAuditReport>(`/projects/${projectId}/ad-audit`)
}

export async function getWorkspaceAdAuditHistory(
  limit = 20,
  projectId?: string,
): Promise<WorkspaceAdAuditHistoryReport> {
  const query = new URLSearchParams();
  query.set("limit", String(limit));
  if (projectId?.trim()) {
    query.set("projectId", projectId.trim());
  }
  return request<WorkspaceAdAuditHistoryReport>(
    `/ad-audit/history?${query.toString()}`,
  );
}

export async function getProjectTechnicalSeo(projectId: string): Promise<TechnicalSeoReport> {
  return request<TechnicalSeoReport>(`/projects/${projectId}/technical-seo`)
}

export async function getPromptRegistry(): Promise<PromptRegistry> {
  return request<PromptRegistry>("/prompts")
}

export async function getRegressionSampleSet(): Promise<RegressionSampleSet> {
  return request<RegressionSampleSet>("/regression-samples")
}

export async function getVisualRegressionReport(): Promise<VisualRegressionReport> {
  return request<VisualRegressionReport>("/visual-regressions")
}

export async function getSkillRegressionReport(): Promise<SkillRegressionReport> {
  return request<SkillRegressionReport>("/skill-regressions")
}

export async function getAlertReport(): Promise<AlertReport> {
  return request<AlertReport>("/alerts")
}

export async function getAlertLatestReport(): Promise<AlertReport> {
  return request<AlertReport>("/alerts/latest")
}

export async function getAlertDeliveriesReport(options?: {
  limit?: number;
  route?: string;
  status?: "sent" | "failed";
}): Promise<AlertDeliveryReport> {
  const params = new URLSearchParams();
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  if (options?.route) params.set("route", options.route);
  if (options?.status) params.set("status", options.status);
  const suffix = params.toString();
  const path = suffix ? `/alerts/deliveries?${suffix}` : "/alerts/deliveries";
  return request<AlertDeliveryReport>(path)
}

export async function getAlertEmitStatusReport(): Promise<AlertEmitStatusReport> {
  return request<AlertEmitStatusReport>("/alerts/emit/status")
}

export async function getAlertEmitHistoryReport(options?: {
  limit?: number;
  status?: "executed" | "suppressed";
}): Promise<AlertEmitHistoryReport> {
  const params = new URLSearchParams();
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  if (options?.status) params.set("status", options.status);
  const suffix = params.toString();
  const path = suffix ? `/alerts/emit/history?${suffix}` : "/alerts/emit/history";
  return request<AlertEmitHistoryReport>(path)
}

export async function getAlertPresetCollection(): Promise<AlertPresetCollection> {
  return request<AlertPresetCollection>("/alerts/presets")
}

export async function updateAlertPresetCollection(payload: AlertPresetUpdateRequest): Promise<AlertPresetCollection> {
  return request<AlertPresetCollection>("/alerts/presets", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function getAlertRuleCollection(): Promise<AlertRuleCollection> {
  return request<AlertRuleCollection>("/alerts/rules")
}

export async function updateAlertRuleCollection(payload: AlertRuleUpdateRequest): Promise<AlertRuleCollection> {
  return request<AlertRuleCollection>("/alerts/rules", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function getOnCallPolicyCollection(): Promise<OnCallPolicyCollection> {
  return request<OnCallPolicyCollection>("/alerts/oncall-policy")
}

export async function getOnCallCoverageReport(): Promise<OnCallCoverageReport> {
  return request<OnCallCoverageReport>("/alerts/oncall/coverage")
}

export async function updateOnCallPolicyCollection(payload: OnCallPolicyUpdateRequest): Promise<OnCallPolicyCollection> {
  return request<OnCallPolicyCollection>("/alerts/oncall-policy", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function getAlertHistoryReport(options?: {
  limit?: number;
  offset?: number;
  order?: "asc" | "desc";
  cursor?: string;
  projectIds?: string[];
  categories?: string[];
  severities?: string[];
  providers?: string[];
  blocking?: boolean;
}): Promise<AlertHistoryReport> {
  const params = new URLSearchParams();
  if (options?.limit !== undefined) params.set("limit", String(options.limit));
  if (options?.offset !== undefined) params.set("offset", String(options.offset));
  if (options?.order) params.set("order", options.order);
  if (options?.cursor) params.set("cursor", options.cursor);
  for (const projectId of options?.projectIds ?? []) params.append("project_ids", projectId);
  for (const category of options?.categories ?? []) params.append("categories", category);
  for (const severity of options?.severities ?? []) params.append("severities", severity);
  for (const provider of options?.providers ?? []) params.append("providers", provider);
  if (options?.blocking !== undefined) params.set("blocking", String(options.blocking));
  const suffix = params.toString();
  const path = suffix ? `/alerts/history?${suffix}` : "/alerts/history";
  return request<AlertHistoryReport>(path);
}

export async function getRegressionReport(): Promise<RegressionReport> {
  return request<RegressionReport>("/regressions")
}

export async function getAcceptanceReport(): Promise<AcceptanceReport> {
  return request<AcceptanceReport>("/acceptance/report")
}

export async function getAcceptanceHistoryReport(options?: {
  limit?: number;
  passed?: boolean;
  failedGateId?: string;
}): Promise<AcceptanceHistoryReport> {
  const params = new URLSearchParams();
  params.set("limit", String(options?.limit ?? 20));
  if (options?.passed !== undefined) params.set("passed", String(options.passed));
  if (options?.failedGateId) params.set("failedGateId", options.failedGateId);
  const suffix = params.toString();
  return request<AcceptanceHistoryReport>(`/acceptance/history?${suffix}`)
}

export async function getProductBenchmarkReport(projectId?: string): Promise<ProductBenchmarkReport> {
  const query = projectId ? `?projectId=${encodeURIComponent(projectId)}` : "";
  return request<ProductBenchmarkReport>(`/product-benchmark${query}`)
}

export async function getRemainingTaskReport(projectId?: string): Promise<RemainingTaskReport> {
  const query = projectId ? `?projectId=${encodeURIComponent(projectId)}` : "";
  return request<RemainingTaskReport>(`/product-benchmark/remaining${query}`)
}

export async function getRemainingTaskBoardReport(projectId?: string): Promise<RemainingTaskBoardReport> {
  const query = projectId ? `?projectId=${encodeURIComponent(projectId)}` : "";
  return request<RemainingTaskBoardReport>(`/product-benchmark/remaining/board${query}`)
}

export async function getConnectorFailureReport(): Promise<ConnectorFailureReport> {
  return request<ConnectorFailureReport>("/connectors/failures")
}

export async function retryConnectors(payload: ConnectorRetryRequest): Promise<ConnectorRetryResult> {
  return request<ConnectorRetryResult>("/connectors/retry", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getConnectorRetryHistory(): Promise<ConnectorRetryHistoryReport> {
  return request<ConnectorRetryHistoryReport>("/connectors/retry/history")
}

export async function getBulkConnectorActionHistory(options?: {
  limit?: number;
  action?: "blocking" | "strict_gap";
  provider?: string;
  projectId?: string;
}): Promise<BulkConnectorActionHistoryReport> {
  const params = new URLSearchParams();
  if (typeof options?.limit === "number" && Number.isFinite(options.limit)) params.set("limit", String(options.limit));
  if (options?.action) params.set("action", options.action);
  if (options?.provider) params.set("provider", options.provider);
  if (options?.projectId) params.set("projectId", options.projectId);
  const query = params.toString();
  const path = query ? `/connectors/bulk-actions/history?${query}` : "/connectors/bulk-actions/history";
  return request<BulkConnectorActionHistoryReport>(path)
}

export async function retryVisualRegressions(payload: VisualRegressionRetryRequest): Promise<VisualRegressionRetryResult> {
  return request<VisualRegressionRetryResult>("/visual-regressions/retry", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getVisualRegressionRetryHistory(): Promise<VisualRegressionRetryHistoryReport> {
  return request<VisualRegressionRetryHistoryReport>(
    "/visual-regressions/retry/history",
  );
}

export async function getVisualRegressionRemediationReport(): Promise<VisualRegressionRemediationReport> {
  return request<VisualRegressionRemediationReport>(
    "/visual-regressions/remediations",
  );
}

export async function getVisualRegressionRunHistory(limit = 20): Promise<VisualRegressionRunHistoryReport> {
  return request<VisualRegressionRunHistoryReport>(
    `/visual-regressions/runs/history?limit=${limit}`,
  );
}

export async function getWorkspaceConnectionHistory(
  options?: {
    limit?: number;
    projectId?: string;
    provider?: string;
    status?: string;
    action?: "connector.probe" | "connector.refreshed";
  },
): Promise<WorkspaceConnectionHistoryReport> {
  const params = new URLSearchParams();
  if (typeof options?.limit === "number") params.set("limit", String(options.limit));
  if (options?.projectId) params.set("projectId", options.projectId);
  if (options?.provider) params.set("provider", options.provider);
  if (options?.status) params.set("status", options.status);
  if (options?.action) params.set("action", options.action);
  const query = params.toString();
  const path = query ? `/connectors/history?${query}` : "/connectors/history";
  return request<WorkspaceConnectionHistoryReport>(path)
}

export async function getConnectorRemediationReport(options?: {
  blocking?: boolean;
  severity?: "critical" | "warning" | "info";
  category?: "auth" | "permission" | "rate_limit" | "network" | "validation" | "config" | "unavailable" | "other";
  provider?: string;
  projectId?: string;
  limit?: number;
}): Promise<ConnectorRemediationReport> {
  const params = new URLSearchParams();
  if (typeof options?.blocking === "boolean") params.set("blocking", String(options.blocking));
  if (options?.severity) params.set("severity", options.severity);
  if (options?.category) params.set("category", options.category);
  if (options?.provider) params.set("provider", options.provider);
  if (options?.projectId) params.set("projectId", options.projectId);
  if (typeof options?.limit === "number" && Number.isFinite(options.limit)) params.set("limit", String(options.limit));
  const query = params.toString();
  const path = query ? `/connectors/remediations?${query}` : "/connectors/remediations";
  return request<ConnectorRemediationReport>(path)
}

export async function getVisualRegressionRunsReport(): Promise<VisualRegressionRunsReport> {
  return request<VisualRegressionRunsReport>("/visual-regressions/runs")
}

export async function enqueueVisualRegressionRuns(payload: VisualRegressionRunExecuteRequest): Promise<VisualRegressionRunEnqueueResult> {
  return request<VisualRegressionRunEnqueueResult>("/visual-regressions/runs/enqueue", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getVisualRegressionHealthReport(): Promise<VisualRegressionHealthReport> {
  return request<VisualRegressionHealthReport>("/visual-regressions/health")
}

export async function getVisualFarmStatusReport(): Promise<VisualFarmStatusReport> {
  return request<VisualFarmStatusReport>("/visual-farm/status")
}

export async function getVisualFarmProbeReport(): Promise<VisualFarmProbeReport> {
  return request<VisualFarmProbeReport>("/visual-farm/probe")
}

export async function enqueueVisualFarmProbe(): Promise<VisualFarmProbeEnqueueResult> {
  return request<VisualFarmProbeEnqueueResult>("/visual-farm/probe/enqueue", {
    method: "POST",
  });
}

export async function getVisualFarmProbeHistoryReport(limit = 20): Promise<VisualFarmProbeHistoryReport> {
  return request<VisualFarmProbeHistoryReport>(
    `/visual-farm/probe/history?limit=${limit}`,
  );
}

export async function getRuntimeEdgeGatewayReport(projectId?: string): Promise<any> {
  const query = projectId?.trim() ? `?projectId=${encodeURIComponent(projectId.trim())}` : "";
  return request<any>(`/runtime-edge/gateway${query}`);
}

export async function getRuntimeEdgeGatewayProviderStatusReport(projectId?: string): Promise<RuntimeEdgeGatewayProviderStatusReport> {
  const query = projectId?.trim() ? `?projectId=${encodeURIComponent(projectId.trim())}` : "";
  return request<RuntimeEdgeGatewayProviderStatusReport>(
    `/runtime-edge/gateway/providers${query}`,
  );
}

export async function getRuntimeEdgeGatewayHistory(limit = 6, projectId?: string): Promise<any> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (projectId?.trim()) params.set("projectId", projectId.trim());
  const query = params.toString() ? `?${params.toString()}` : "";
  return request<any>(`/runtime-edge/gateway/history${query}`);
}

export async function publishRuntimeEdgeGateway(projectId?: string): Promise<any> {
  const query = projectId?.trim() ? `?projectId=${encodeURIComponent(projectId.trim())}` : "";
  return request<any>(`/runtime-edge/gateway/publish${query}`, {
    method: "POST",
  });
}

export async function getVisualFarmGatewayReport(projectId?: string): Promise<any> {
  const query = projectId?.trim() ? `?projectId=${encodeURIComponent(projectId.trim())}` : "";
  return request<any>(`/visual-farm/gateway${query}`);
}

export async function getVisualFarmGatewayProviderStatusReport(projectId?: string): Promise<VisualFarmGatewayProviderStatusReport> {
  const query = projectId?.trim() ? `?projectId=${encodeURIComponent(projectId.trim())}` : "";
  return request<VisualFarmGatewayProviderStatusReport>(
    `/visual-farm/gateway/providers${query}`,
  );
}

export async function getVisualFarmGatewayHistory(limit = 6, projectId?: string): Promise<any> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (projectId?.trim()) params.set("projectId", projectId.trim());
  const query = params.toString() ? `?${params.toString()}` : "";
  return request<any>(`/visual-farm/gateway/history${query}`);
}

export async function publishVisualFarmGateway(projectId?: string): Promise<any> {
  const query = projectId?.trim() ? `?projectId=${encodeURIComponent(projectId.trim())}` : "";
  return request<any>(`/visual-farm/gateway/publish${query}`, {
    method: "POST",
  });
}

export async function getWorkerQueueHealth(): Promise<WorkerQueueHealthReport> {
  return request<WorkerQueueHealthReport>("/worker/queue/health")
}

export async function getWorkerExecutionHistory(options?: {
  limit?: number;
  projectId?: string;
  stage?: string;
  status?: "queued" | "completed" | "failed" | "requeued" | "skipped_duplicate";
  action?: string;
}): Promise<WorkerExecutionHistoryReport> {
  const params = new URLSearchParams();
  if (typeof options?.limit === "number" && Number.isFinite(options.limit)) params.set("limit", String(options.limit));
  if (options?.projectId) params.set("projectId", options.projectId);
  if (options?.stage) params.set("stage", options.stage);
  if (options?.status) params.set("status", options.status);
  if (options?.action) params.set("action", options.action);
  const query = params.toString();
  const path = query ? `/worker/executions?${query}` : "/worker/executions";
  return request<WorkerExecutionHistoryReport>(path)
}

export async function getWorkerServiceHealth(): Promise<WorkerServiceHealthReport> {
  return request<WorkerServiceHealthReport>("/worker/service/health")
}

export async function getObservabilityStatus(): Promise<ObservabilityStatusReport> {
  return request<ObservabilityStatusReport>("/observability/status")
}

export async function approveTask(taskId: string, payload: ApprovalDecisionRequest): Promise<WorkflowBundle> {
  return request<WorkflowBundle>(`/tasks/${taskId}/approve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function bulkApproveTasks(payload: BulkApprovalRequest): Promise<BulkApprovalResult> {
  return request<BulkApprovalResult>("/tasks/bulk/approve", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function deployTask(taskId: string, payload: DeploymentActionRequest): Promise<WorkflowBundle> {
  return request<WorkflowBundle>(`/tasks/${taskId}/deploy`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function rollbackTask(taskId: string, payload: RollbackActionRequest): Promise<WorkflowBundle> {
  return request<WorkflowBundle>(`/tasks/${taskId}/rollback`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function runWorkerOnce(): Promise<WorkerRunOnceResult> {
  return request<WorkerRunOnceResult>("/worker/run-once", { method: "POST" });
}

export { API_BASE };
