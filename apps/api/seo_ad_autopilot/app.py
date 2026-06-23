from __future__ import annotations

from contextlib import asynccontextmanager
import re
from typing import Literal, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .config import get_settings
from .db import ProjectRow
from .observability import initialize_observability
from .models import (
    ApprovalDecisionRequest,
    ApprovalStatus,
    BulkApprovalRequest,
    BulkApprovalResult,
    BulkBlockingRefreshRequest,
    BulkBlockingRefreshResult,
    BulkConnectorRefreshRequest,
    BulkConnectorRefreshResult,
    BulkStrictGapRefreshRequest,
    BulkStrictGapRefreshResult,
    BulkMarketEvidenceRefreshRequest,
    BulkMarketEvidenceRefreshResult,
    BulkConnectionsTestRequest,
    BulkConnectionsTestResult,
    BulkProjectConnectionsRefreshRequest,
    BulkProjectConnectionsRefreshResult,
    BulkProjectSyncRequest,
    BulkProjectSyncResult,
    ConnectorKind,
    ConnectorRefreshResult,
    ConnectorRetryRequest,
    ConnectorRetryResult,
    VisualRegressionRetryRequest,
    VisualRegressionRetryResult,
    VisualRegressionRunEnqueueResult,
    VisualRegressionRunExecuteRequest,
    VisualRegressionRunHistoryReport,
    VisualRegressionRemediationReport,
    VisualRegressionRetryHistoryReport,
    ConnectorRetryHistoryReport,
    BulkConnectorActionHistoryReport,
    ProjectConnectionHistoryReport,
    WorkspaceConnectionEvidenceReport,
    WorkspaceConnectionHistoryReport,
    ConnectorRemediationReport,
    ConnectorsHealthResult,
    WorkspaceConnectorsHealthReport,
    ConnectorFailureReport,
    DashboardSnapshot,
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
    OnCallCoverageReport,
    OnCallPolicyUpdateRequest,
    AdAuditReport,
    WorkspaceAdAuditHistoryReport,
    AcceptanceReport,
    AcceptanceHistoryReport,
    ProductBenchmarkReport,
    RemainingTaskReport,
    RemainingTaskBoardReport,
    AdaptiveComponentReport,
    DeploymentHistoryReport,
    DeploymentActionRequest,
    BusinessClassifierReport,
    ContentStrategyReport,
    ProjectCreateRequest,
    CrawlDiagnosticsHistoryReport,
    CrawlDiagnosticsReport,
    ProjectConnectionEvidenceReport,
    ProjectConnections,
    ProjectConnectionsTestResult,
    ProjectConnectionsRefreshRequest,
    ProjectConnectionsRefreshResult,
    ProjectConnectionsUpdateRequest,
    ProjectDetail,
    ProjectSummary,
    ProjectRuntimeRouteHistoryReport,
    MarketEvidenceReport,
    MarketEvidenceHealthReport,
    MarketEvidenceProviderStatusReport,
    ProjectCruiseHealthReport,
    WorkspaceCruiseHealthReport,
    WorkspaceMarketEvidenceHealthReport,
    WorkspacePolicy,
    WorkspaceBillingPolicy,
    WorkspaceBillingPolicyUpdateRequest,
    WorkspaceBillingSettlementExecutionHistoryReport,
    WorkspaceBillingSettlementExecutionReport,
    WorkspaceBillingSettlementExecutionRequest,
    WorkspaceBillingSettlementExecutionBatchRequest,
    WorkspaceBillingSettlementExecutionBatchReport,
    WorkspaceBillingSettlementGatewayPolicy,
    WorkspaceBillingSettlementGatewayPolicyUpdateRequest,
    WorkspaceBillingSettlementGatewayExportReport,
    WorkspaceBillingSettlementGatewayHistoryReport,
    WorkspaceBillingSettlementGatewayPublishReport,
    WorkspaceBillingSettlementGatewayReport,
    WorkspaceBillingSettlementProviderRequirementsReport,
    WorkspaceBillingSettlementGatewayProviderStatusReport,
    WorkspaceBillingReport,
    WorkspaceExperimentPolicyUpdateRequest,
    WorkspaceExperimentAssignmentRequest,
    WorkspaceExperimentAssignmentReport,
    WorkspaceExperimentReport,
    WorkspaceLocalizationPolicyUpdateRequest,
    WorkspaceLocalizationAssignmentRequest,
    WorkspaceLocalizationAssignmentReport,
    WorkspaceLocalizationReport,
    WorkspaceTemplateMarketPolicyUpdateRequest,
    WorkspaceTemplateMarketReport,
    WorkspaceModelGatewayPolicy,
    WorkspaceModelGatewayPolicyUpdateRequest,
    WorkspaceModelGatewayHistoryReport,
    WorkspaceModelGatewayProviderStatusReport,
    WorkspaceModelGatewayReport,
    WorkspacePolicyUpdateRequest,
    MetricHistoryReport,
    PromptRegistry,
    PromptRegistryUpdateRequest,
    PromptVersionActivateRequest,
    PromptVersionUpsertRequest,
    RegressionReport,
    RegressionSampleSet,
    RollbackHistoryReport,
    RollbackActionRequest,
    RunStatus,
    RunTrigger,
    SiteIntake,
    ProjectRun,
    ProjectSyncRequest,
    TaskSummary,
    TechnicalSeoReport,
    StyleExtractionReport,
    SkillRegressionReport,
    TechnicalSeoPatchReport,
    VisualRegressionReport,
    VisualRegressionHealthReport,
    VisualFarmStatusReport,
    VisualFarmProbeReport,
    VisualFarmProbeEnqueueResult,
    VisualFarmProbeHistoryReport,
    VisualFarmDeploymentRequest,
    VisualFarmDeploymentReport,
    VisualFarmDeploymentBatchRequest,
    VisualFarmDeploymentBatchReport,
    VisualFarmDeploymentBatchEnqueueResult,
    VisualFarmDeploymentBatchHistoryReport,
    VisualFarmDeploymentHistoryReport,
    VisualFarmGatewayPolicy,
    VisualFarmGatewayPolicyUpdateRequest,
    VisualFarmGatewayExportReport,
    VisualFarmGatewayReport,
    VisualFarmGatewayProviderStatusReport,
    VisualFarmGatewayHistoryReport,
    VisualRegressionRunsReport,
    WorkerRunOnceRequest,
    WorkerRunOnceResult,
    WorkerExecutionHistoryReport,
    WorkerQueueHealthReport,
    WorkerServiceHealthReport,
    ObservabilityStatusReport,
    WorkflowBundle,
    RuntimeExecutionResponse,
    ProjectRuntimeEdgeConfig,
    RuntimeEdgeGatewayExportReport,
    RuntimeEdgeDeploymentRequest,
    RuntimeEdgeDeploymentReport,
    RuntimeEdgeDeploymentBatchRequest,
    RuntimeEdgeDeploymentBatchReport,
    RuntimeEdgeDeploymentBatchEnqueueResult,
    RuntimeEdgeDeploymentBatchHistoryReport,
    RuntimeIngressBundleBatchRequest,
    RuntimeIngressBundleBatchReport,
    RuntimeIngressBundleBatchEnqueueResult,
    RuntimeIngressBundleBatchHistoryReport,
    RuntimeIngressBundleBatchHealthReport,
    RuntimeEdgeDeploymentHistoryReport,
    RuntimeIngressBundleReport,
    RuntimeIngressConfigArtifactReport,
    RuntimeIngressConfigArtifactHistoryReport,
    RuntimeEdgeGatewayPolicyUpdateRequest,
    RuntimeEdgeGatewayReport,
    RuntimeEdgeGatewayProviderStatusReport,
    RuntimeEdgeGatewayHistoryReport,
    RuntimeEdgeRolloutExecuteRequest,
    RuntimeEdgeRolloutExecutionReport,
    RuntimeEdgeRolloutHistoryReport,
    RuntimeEdgeRolloutRemediationReport,
    RuntimeEdgeProbeRequest,
    RuntimeEdgeProbeReport,
    RuntimeEdgeProbeHistoryReport,
    RuntimeEdgeRolloutPlanReport,
    RuntimeEdgeValidationReport,
    WorkspaceRuntimeEdgeRouteMapReport,
    RuntimeEdgeRouteOverridesReport,
    RuntimeEdgeRouteOverridesUpdateRequest,
    RuntimeRouteRequest,
    RuntimeRouteReport,
    WorkspaceRuntimeEdgeConfigReport,
    WorkspaceRuntimeRouteHealthReport,
    WorkspaceRuntimeRouteHistoryReport,
)
from .service import WorkflowService


def create_app(service: Optional[WorkflowService] = None) -> FastAPI:
    owned_service = service is None
    if service is None:
        settings = get_settings()
        service = WorkflowService(settings=settings)
    else:
        settings = service.settings
    initialize_observability(settings)
    if owned_service:
        service.bootstrap()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.service = service
        yield

    app = FastAPI(
        title="SEO-AD AutoPilot API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.service = service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin, "http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include analysis API router
    from .analysis_api import router as analysis_router
    app.include_router(analysis_router)
    
    # Include e-commerce analysis router
    from .routers.ecommerce import router as ecommerce_router
    app.include_router(ecommerce_router)
    
    # Include keyword research router
    from .routers.keywords import router as keywords_router
    app.include_router(keywords_router)
    
    project_path_pattern = re.compile(r"^/api/projects/([^/]+)(?:/.*)?$")

    def _normalize_runtime_host(value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip()
        if not normalized:
            return None
        normalized = normalized.split(",", 1)[0].strip()
        if not normalized:
            return None
        if "://" in normalized:
            parsed = urlsplit(normalized)
            normalized = parsed.netloc or parsed.path or normalized
        normalized = normalized.strip()
        if not normalized:
            return None
        if normalized.startswith("["):
            closing = normalized.find("]")
            if closing > 0:
                return normalized[: closing + 1].lower()
        if ":" in normalized and normalized.count(":") == 1:
            normalized = normalized.split(":", 1)[0].strip()
        return normalized.lower() or None

    def _runtime_request_host(request: Request, explicit_host: Optional[str] = None) -> Optional[str]:
        candidates = [
            explicit_host,
            request.headers.get("x-forwarded-host"),
            request.headers.get("x-original-host"),
            request.headers.get("host"),
        ]
        for candidate in candidates:
            normalized = _normalize_runtime_host(candidate)
            if normalized:
                return normalized
        return None

    def _runtime_proxy_request_headers(
        request: Request,
        *,
        content_type: Optional[str] = None,
        upstream_url: str,
        forwarded_host: Optional[str] = None,
    ) -> dict[str, str]:
        host_value = forwarded_host or request.headers.get("host") or urlsplit(upstream_url).netloc
        request_headers = {
            "Accept": request.headers.get("accept") or "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": request.headers.get("accept-language") or "en-US,en;q=0.9",
            "User-Agent": request.headers.get("user-agent") or "SEO-AD-AutoPilot/1.0",
            "X-Forwarded-Host": host_value,
            "X-Forwarded-Proto": request.url.scheme,
            "X-Forwarded-Method": request.method,
            "X-Forwarded-Path": request.url.path,
            "X-SEO-AD-Proxy-Source": "runtime-execute",
        }
        if request.url.query:
            request_headers["X-Forwarded-Query"] = request.url.query
        client_host = getattr(getattr(request, "client", None), "host", None)
        if client_host:
            request_headers["X-Forwarded-For"] = client_host
        for key in ("authorization", "cookie", "origin", "referer", "x-requested-with", "x-csrf-token"):
            value = request.headers.get(key)
            if value:
                request_headers[key.title() if key != "x-csrf-token" else "X-CSRF-Token"] = value
        if content_type:
            request_headers["Content-Type"] = content_type
        if host_value:
            request_headers["Host"] = host_value
        return request_headers

    def _proxy_runtime_response(
        target_url: str,
        *,
        request: Request,
        headers: dict[str, str],
        forwarded_host: Optional[str] = None,
        method: str = "GET",
        body: Optional[bytes] = None,
        content_type: Optional[str] = None,
    ) -> Response:
        upstream_headers = _runtime_proxy_request_headers(
            request,
            content_type=content_type,
            upstream_url=target_url,
            forwarded_host=forwarded_host,
        )
        upstream_request = UrlRequest(url=target_url, data=body, method=method.upper(), headers=upstream_headers)
        try:
            with urlopen(upstream_request, timeout=5) as upstream:
                body = bytes(upstream.read() or b"")
                content_type = upstream.headers.get("Content-Type") or "text/html; charset=utf-8"
                response = Response(content=body, status_code=int(getattr(upstream, "status", 200) or 200), media_type=content_type)
                for key, value in upstream.headers.items():
                    normalized_key = str(key).strip().lower()
                    if normalized_key in {
                        "connection",
                        "keep-alive",
                        "proxy-authenticate",
                        "proxy-authorization",
                        "te",
                        "trailer",
                        "transfer-encoding",
                        "upgrade",
                        "content-length",
                        "content-type",
                    }:
                        continue
                    response.headers[key] = value
                for key, value in headers.items():
                    response.headers[key] = value
                response.headers["X-SEO-AD-Proxied-URL"] = target_url
                return response
        except HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Runtime proxy upstream failed: {exc.code}") from exc
        except URLError as exc:
            raise HTTPException(status_code=502, detail=f"Runtime proxy upstream unavailable: {exc.reason}") from exc

    def _runtime_proxy_target(base_url: str, proxy_path: str, query_string: str) -> str:
        parsed = urlsplit(base_url)
        base_path = parsed.path or "/"
        if not base_path.endswith("/"):
            base_path = base_path.rstrip("/") + "/"
        normalized_path = proxy_path.lstrip("/")
        target_path = base_path + normalized_path if normalized_path else parsed.path
        return urlunsplit((parsed.scheme, parsed.netloc, target_path, query_string, parsed.fragment))

    @app.middleware("http")
    async def runtime_route_middleware(request: Request, call_next):
        runtime_route_report = None
        runtime_execution_response = None
        match = project_path_pattern.match(request.url.path)
        resolved_host = _runtime_request_host(request)
        if match is not None and hasattr(app.state, "service"):
            project_id = match.group(1)
            try:
                with app.state.service.database.session() as session:
                    project = session.get(ProjectRow, project_id)
                    if project is not None:
                        intake = app.state.service._project_intake(project)
                        runtime_route_report = app.state.service.build_runtime_route_report(
                            project_id,
                            intake,
                            request=RuntimeRouteRequest(
                                request_path=request.url.path,
                                request_method=request.method,
                                target_locale=intake.locale,
                                host=_runtime_request_host(request),
                            ),
                        )
                        request.state.runtime_route_report = runtime_route_report
                        if request.url.path.endswith("/runtime-execute"):
                            runtime_execution_response = app.state.service.build_runtime_execution_response(
                                project_id,
                                request=RuntimeRouteRequest(
                                    request_path=request.url.path,
                                    request_method=request.method,
                                    target_locale=intake.locale,
                                    host=_runtime_request_host(request),
                                ),
                            )
                            request.state.runtime_execution_response = runtime_execution_response
                            if runtime_execution_response.served_mode == "blocked":
                                response = JSONResponse(
                                    status_code=runtime_execution_response.status_code,
                                    content=jsonable_encoder(runtime_execution_response, by_alias=True),
                                )
                                response.headers["X-SEO-AD-Served-Mode"] = runtime_execution_response.served_mode
                                response.headers["X-SEO-AD-Served-Target"] = runtime_execution_response.served_target
                                if runtime_execution_response.served_response_mode:
                                    response.headers["X-SEO-AD-Served-Response-Mode"] = runtime_execution_response.served_response_mode
                                if runtime_execution_response.served_url:
                                    response.headers["X-SEO-AD-Served-URL"] = runtime_execution_response.served_url
                                return response
            except Exception:
                runtime_route_report = None
        elif resolved_host and hasattr(app.state, "service") and not request.url.path.startswith("/api/"):
            internal_paths = {"/healthz", "/docs", "/redoc", "/openapi.json"}
            if request.url.path not in internal_paths:
                try:
                    route_map = app.state.service.build_workspace_runtime_edge_route_map_report()
                    matched_routes = [item for item in route_map.items if item.site_host == resolved_host]
                    if len(matched_routes) > 1:
                        response = JSONResponse(
                            status_code=409,
                            content={
                                "detail": f"Host {resolved_host} is mapped by multiple projects.",
                                "host": resolved_host,
                                "duplicateProjects": [item.project_id for item in matched_routes],
                                "warnings": route_map.warnings,
                            },
                        )
                        response.headers["X-SEO-AD-Site-Dispatch"] = "host"
                        response.headers["X-SEO-AD-Request-Host"] = resolved_host
                        response.headers["X-SEO-AD-Route-Mode"] = "blocked"
                        response.headers["X-SEO-AD-Route-Action"] = "block"
                        return response
                    if len(matched_routes) == 1:
                        site_project_id = matched_routes[0].project_id
                        runtime_execution_response = app.state.service.build_runtime_execution_response(
                            site_project_id,
                            request=RuntimeRouteRequest(
                                request_path=request.url.path,
                                request_method=request.method,
                                target_surface="site",
                                target_locale=None,
                                host=resolved_host,
                            ),
                        )
                        request.state.runtime_route_report = runtime_execution_response.runtime_route
                        request.state.runtime_execution_response = runtime_execution_response
                        runtime_site_headers = {
                            "X-SEO-AD-Served-Mode": runtime_execution_response.served_mode,
                            "X-SEO-AD-Served-Target": runtime_execution_response.served_target,
                            "X-SEO-AD-Site-Dispatch": "host",
                            "X-SEO-AD-Request-Host": resolved_host,
                            "X-SEO-AD-Request-Project": site_project_id,
                        }
                        if runtime_execution_response.served_response_mode:
                            runtime_site_headers["X-SEO-AD-Served-Response-Mode"] = runtime_execution_response.served_response_mode
                        if runtime_execution_response.served_url:
                            runtime_site_headers["X-SEO-AD-Served-URL"] = runtime_execution_response.served_url
                        if runtime_execution_response.served_mode == "blocked":
                            response = JSONResponse(
                                status_code=runtime_execution_response.status_code,
                                content=jsonable_encoder(runtime_execution_response, by_alias=True),
                            )
                            for key, value in runtime_site_headers.items():
                                response.headers[key] = value
                            try:
                                app.state.service._audit(
                                    site_project_id,
                                    runtime_execution_response.task_id,
                                    "runtime.site.blocked",
                                    {
                                        "requestPath": request.url.path,
                                        "requestMethod": request.method,
                                        "requestHost": resolved_host,
                                        "servedMode": runtime_execution_response.served_mode,
                                        "servedTarget": runtime_execution_response.served_target,
                                        "reason": runtime_execution_response.runtime_route.execution_reason,
                                    },
                                )
                            except Exception:
                                pass
                            return response
                        if (
                            runtime_execution_response.deployment is not None
                            and runtime_execution_response.deployment.provider_url
                            and runtime_execution_response.deployment.provider_url.startswith(("http://", "https://"))
                        ):
                            target_url = _runtime_proxy_target(runtime_execution_response.deployment.provider_url, request.url.path, request.url.query)
                            response = _proxy_runtime_response(
                                target_url,
                                request=request,
                                headers=runtime_site_headers,
                                forwarded_host=resolved_host,
                                method=request.method,
                            )
                            try:
                                app.state.service._audit(
                                    site_project_id,
                                    runtime_execution_response.task_id,
                                    "runtime.site.requested",
                                    {
                                        "requestPath": request.url.path,
                                        "requestMethod": request.method,
                                        "requestHost": resolved_host,
                                        "proxiedUrl": target_url,
                                        "servedMode": runtime_execution_response.served_mode,
                                        "servedTarget": runtime_execution_response.served_target,
                                    },
                                )
                            except Exception:
                                pass
                            return response
                        if runtime_execution_response.preview is not None:
                            response = HTMLResponse(
                                content=runtime_execution_response.preview.after_html,
                                status_code=runtime_execution_response.status_code,
                                headers=runtime_site_headers,
                            )
                            response.headers["X-SEO-AD-Proxied-URL"] = runtime_execution_response.served_url or ""
                            try:
                                app.state.service._audit(
                                    site_project_id,
                                    runtime_execution_response.task_id,
                                    "runtime.site.requested",
                                    {
                                        "requestPath": request.url.path,
                                        "requestMethod": request.method,
                                        "requestHost": resolved_host,
                                        "proxiedUrl": runtime_execution_response.served_url or "",
                                        "servedMode": runtime_execution_response.served_mode,
                                        "servedTarget": runtime_execution_response.served_target,
                                    },
                                )
                            except Exception:
                                pass
                            return response
                        if runtime_execution_response.served_url and runtime_execution_response.served_url.startswith(("http://", "https://")):
                            target_url = _runtime_proxy_target(runtime_execution_response.served_url, request.url.path, request.url.query)
                            response = _proxy_runtime_response(
                                target_url,
                                request=request,
                                headers=runtime_site_headers,
                                forwarded_host=resolved_host,
                                method=request.method,
                            )
                            try:
                                app.state.service._audit(
                                    site_project_id,
                                    runtime_execution_response.task_id,
                                    "runtime.site.requested",
                                    {
                                        "requestPath": request.url.path,
                                        "requestMethod": request.method,
                                        "requestHost": resolved_host,
                                        "proxiedUrl": target_url,
                                        "servedMode": runtime_execution_response.served_mode,
                                        "servedTarget": runtime_execution_response.served_target,
                                    },
                                )
                            except Exception:
                                pass
                            return response
                        response = JSONResponse(
                            status_code=runtime_execution_response.status_code,
                            content=jsonable_encoder(runtime_execution_response, by_alias=True),
                        )
                        for key, value in runtime_site_headers.items():
                            response.headers[key] = value
                        try:
                            app.state.service._audit(
                                site_project_id,
                                runtime_execution_response.task_id,
                                "runtime.site.blocked",
                                {
                                    "requestPath": request.url.path,
                                    "requestMethod": request.method,
                                    "requestHost": resolved_host,
                                    "servedMode": runtime_execution_response.served_mode,
                                    "servedTarget": runtime_execution_response.served_target,
                                    "reason": "runtime site route is not resolvable",
                                },
                            )
                        except Exception:
                            pass
                        return response
                except Exception:
                    runtime_execution_response = None
        response = await call_next(request)
        if runtime_route_report is not None:
            response.headers["X-SEO-AD-Runtime-Ready"] = "true" if runtime_route_report.runtime_ready else "false"
            response.headers["X-SEO-AD-Request-Project"] = runtime_route_report.project_id
            if runtime_route_report.request_path:
                response.headers["X-SEO-AD-Request-Path"] = runtime_route_report.request_path
            if runtime_route_report.request_method:
                response.headers["X-SEO-AD-Request-Method"] = runtime_route_report.request_method
            response.headers["X-SEO-AD-Route-Mode"] = runtime_route_report.execution_mode
            response.headers["X-SEO-AD-Route-Action"] = runtime_route_report.execution_action
            if runtime_route_report.execution_reason:
                response.headers["X-SEO-AD-Route-Reason"] = runtime_route_report.execution_reason[:256]
            if runtime_route_report.execution_entrypoint:
                response.headers["X-SEO-AD-Route-Entrypoint"] = runtime_route_report.execution_entrypoint
            if runtime_route_report.gateway_route_provider_name:
                response.headers["X-SEO-AD-Route-Provider"] = runtime_route_report.gateway_route_provider_name
            if runtime_route_report.gateway_route_fallback_provider_name:
                response.headers["X-SEO-AD-Route-Fallback-Provider"] = runtime_route_report.gateway_route_fallback_provider_name
            if runtime_route_report.gateway_route_priority is not None:
                response.headers["X-SEO-AD-Route-Priority"] = str(runtime_route_report.gateway_route_priority)
            response.headers["X-SEO-AD-Experiment-Variant"] = (
                runtime_route_report.experiment_assignment.assignments[0].assigned_variant_name
                if runtime_route_report.experiment_assignment.assignments
                and runtime_route_report.experiment_assignment.assignments[0].assigned_variant_name
                else "unassigned"
            )
            response.headers["X-SEO-AD-Localization-Cluster"] = (
                runtime_route_report.localization_assignment.assignments[0].cluster_key
                if runtime_route_report.localization_assignment.assignments
                else "unassigned"
            )
            response.headers["X-SEO-AD-Localization-Ready"] = (
                "true"
                if runtime_route_report.localization_assignment.assignments
                and runtime_route_report.localization_assignment.assignments[0].cluster_ready
                else "false"
            )
            response.headers["X-SEO-AD-Route-Gateway"] = (
                runtime_route_report.gateway_report.policy.default_provider_name
                if runtime_route_report.gateway_report is not None
                else "local"
            )
            response.headers["X-SEO-AD-Route-Ready"] = "true" if runtime_route_report.runtime_ready else "false"
            if runtime_execution_response is not None:
                response.headers["X-SEO-AD-Served-Mode"] = runtime_execution_response.served_mode
                response.headers["X-SEO-AD-Served-Target"] = runtime_execution_response.served_target
                if runtime_execution_response.served_response_mode:
                    response.headers["X-SEO-AD-Served-Response-Mode"] = runtime_execution_response.served_response_mode
                if runtime_execution_response.served_url:
                    response.headers["X-SEO-AD-Served-URL"] = runtime_execution_response.served_url
            try:
                app.state.service._audit(
                    runtime_route_report.project_id,
                    runtime_route_report.task_id,
                    "runtime.route.resolved",
                    {
                        "requestPath": runtime_route_report.request_path,
                        "requestMethod": runtime_route_report.request_method,
                        "requestProject": runtime_route_report.project_id,
                        "runtimeReady": runtime_route_report.runtime_ready,
                        "executionMode": runtime_route_report.execution_mode,
                        "executionAction": runtime_route_report.execution_action,
                        "executionReason": runtime_route_report.execution_reason,
                        "executionEntrypoint": runtime_route_report.execution_entrypoint,
                        "gatewayRouteProvider": runtime_route_report.gateway_route_provider_name,
                        "gatewayRouteFallbackProvider": runtime_route_report.gateway_route_fallback_provider_name,
                        "gatewayRoutePriority": runtime_route_report.gateway_route_priority,
                        "experimentVariant": (
                            runtime_route_report.experiment_assignment.assignments[0].assigned_variant_name
                            if runtime_route_report.experiment_assignment
                            and runtime_route_report.experiment_assignment.assignments
                            and runtime_route_report.experiment_assignment.assignments[0].assigned_variant_name
                            else "unassigned"
                        ),
                        "localizationCluster": (
                            runtime_route_report.localization_assignment.assignments[0].cluster_key
                            if runtime_route_report.localization_assignment
                            and runtime_route_report.localization_assignment.assignments
                            else "unassigned"
                        ),
                        "gateway": (
                            runtime_route_report.gateway_report.policy.default_provider_name
                            if runtime_route_report.gateway_report is not None
                            else "local"
                        ),
                    },
                )
            except Exception:
                pass
        return response

    def svc() -> WorkflowService:
        return app.state.service

    def _presented_key(
        x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ) -> Optional[str]:
        presented = x_api_key
        if presented is None and authorization:
            scheme, _, token = authorization.partition(" ")
            if scheme.lower() == "bearer":
                presented = token.strip() or None
        return presented

    def require_api_key(presented: Optional[str] = Depends(_presented_key)) -> None:
        expected = settings.api_key
        if presented is None:
            raise HTTPException(status_code=401, detail="API key required")
        if presented != expected:
            raise HTTPException(status_code=403, detail="Invalid API key")

    def require_alert_preset_write(presented: Optional[str] = Depends(_presented_key)) -> None:
        if presented is None:
            raise HTTPException(status_code=401, detail="API key required")
        admin_keys = {item.strip() for item in (settings.alert_preset_admin_keys or "").split(",") if item.strip()}
        if settings.alert_preset_strict_admin:
            allowed_keys = admin_keys or {settings.api_key}
        else:
            allowed_keys = {settings.api_key, *admin_keys}
        if presented not in allowed_keys:
            raise HTTPException(status_code=403, detail="Insufficient permissions for alert preset write")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/overview", response_model=DashboardSnapshot)
    def overview(project_id: Optional[str] = Query(default=None, alias="projectId")) -> DashboardSnapshot:
        try:
            return svc().get_dashboard(project_id=project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects", response_model=list[ProjectSummary])
    def list_projects() -> list[ProjectSummary]:
        return svc().list_projects()

    @app.post("/api/projects", response_model=ProjectSummary)
    def create_project(request: ProjectCreateRequest, _: None = Depends(require_api_key)) -> ProjectSummary:
        return svc().create_project(request)

    @app.get("/api/projects/{project_id}", response_model=ProjectDetail)
    def project_detail(project_id: str) -> ProjectDetail:
        try:
            return svc().get_project_detail(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/market-evidence", response_model=MarketEvidenceReport)
    def project_market_evidence(project_id: str) -> MarketEvidenceReport:
        try:
            return svc().build_market_evidence_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/market-evidence/health", response_model=MarketEvidenceHealthReport)
    def project_market_evidence_health(project_id: str) -> MarketEvidenceHealthReport:
        try:
            return svc().build_market_evidence_health_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/cruise/health", response_model=ProjectCruiseHealthReport)
    def project_cruise_health(project_id: str) -> ProjectCruiseHealthReport:
        try:
            return svc().build_project_cruise_health_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/market-evidence/health", response_model=WorkspaceMarketEvidenceHealthReport)
    def workspace_market_evidence_health(project_id: Optional[str] = Query(default=None, alias="projectId")) -> WorkspaceMarketEvidenceHealthReport:
        return svc().build_workspace_market_evidence_health_report(project_id=project_id)

    @app.get("/api/market-evidence/providers", response_model=MarketEvidenceProviderStatusReport)
    def market_evidence_providers() -> MarketEvidenceProviderStatusReport:
        return svc().build_market_evidence_provider_status_report()

    @app.get("/api/worker/cruise/health", response_model=WorkspaceCruiseHealthReport)
    def workspace_cruise_health(project_id: Optional[str] = Query(default=None, alias="projectId")) -> WorkspaceCruiseHealthReport:
        return svc().build_workspace_cruise_health_report(project_id=project_id)

    @app.post("/api/projects/{project_id}/analyze", response_model=WorkflowBundle)
    def analyze_project(project_id: str, intake: SiteIntake, _: None = Depends(require_api_key)) -> WorkflowBundle:
        try:
            return svc().run_analysis(project_id, intake)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/sync", response_model=WorkflowBundle)
    def sync_project(
        project_id: str,
        request: Optional[ProjectSyncRequest] = None,
        _: None = Depends(require_api_key),
    ) -> WorkflowBundle:
        try:
            return svc().sync_project(project_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/bulk/projects/sync", response_model=BulkProjectSyncResult)
    def bulk_sync(request: BulkProjectSyncRequest, _: None = Depends(require_api_key)) -> BulkProjectSyncResult:
        return svc().sync_projects(request)

    @app.get("/api/projects/{project_id}/runs", response_model=list[ProjectRun])
    def project_runs(
        project_id: str,
        trigger: Optional[RunTrigger] = Query(default=None),
        status: Optional[RunStatus] = Query(default=None),
        limit: int = Query(default=0, ge=0, le=500),
    ) -> list[ProjectRun]:
        try:
            return svc().list_project_runs(project_id, trigger=trigger, status=status, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/runtime-route/history", response_model=ProjectRuntimeRouteHistoryReport)
    def project_runtime_route_history(
        project_id: str,
        limit: int = Query(default=20, ge=1, le=100),
    ) -> ProjectRuntimeRouteHistoryReport:
        try:
            return svc().list_project_runtime_route_history(project_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/metrics", response_model=MetricHistoryReport)
    def project_metrics(project_id: str, limit: int = 20, offset: int = 0) -> MetricHistoryReport:
        try:
            return svc().list_project_metrics(project_id, limit=limit, offset=offset)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/deployments", response_model=DeploymentHistoryReport)
    def project_deployments(project_id: str) -> DeploymentHistoryReport:
        try:
            return svc().list_project_deployments(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/rollbacks", response_model=RollbackHistoryReport)
    def project_rollbacks(project_id: str) -> RollbackHistoryReport:
        try:
            return svc().list_project_rollbacks(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/content-strategy", response_model=ContentStrategyReport)
    def project_content_strategy(project_id: str) -> ContentStrategyReport:
        try:
            return svc().build_content_strategy_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/business-classifier", response_model=BusinessClassifierReport)
    def project_business_classifier(project_id: str) -> BusinessClassifierReport:
        try:
            return svc().build_business_classifier_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/style-extraction", response_model=StyleExtractionReport)
    def project_style_extraction(project_id: str) -> StyleExtractionReport:
        try:
            return svc().build_style_extraction_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/ad-audit", response_model=AdAuditReport)
    def project_ad_audit(project_id: str) -> AdAuditReport:
        try:
            return svc().build_ad_audit_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/adaptive-components", response_model=AdaptiveComponentReport)
    def project_adaptive_components(project_id: str) -> AdaptiveComponentReport:
        try:
            return svc().build_adaptive_component_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/technical-seo", response_model=TechnicalSeoReport)
    def project_technical_seo(project_id: str) -> TechnicalSeoReport:
        try:
            return svc().build_technical_seo_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/technical-seo-patch", response_model=TechnicalSeoPatchReport)
    def project_technical_seo_patch(project_id: str) -> TechnicalSeoPatchReport:
        try:
            return svc().build_technical_seo_patch_report(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/crawl/diagnostics", response_model=CrawlDiagnosticsReport)
    def project_crawl_diagnostics(
        project_id: str,
        url: Optional[str] = Query(default=None),
        fallback_title: Optional[str] = Query(default=None, alias="fallbackTitle"),
        fallback_description: Optional[str] = Query(default=None, alias="fallbackDescription"),
    ) -> CrawlDiagnosticsReport:
        try:
            return svc().build_crawl_diagnostics_report(
                project_id,
                url=url,
                fallback_title=fallback_title,
                fallback_description=fallback_description,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/crawl/diagnostics/history", response_model=CrawlDiagnosticsHistoryReport)
    def project_crawl_diagnostics_history(
        project_id: str,
        limit: int = 10,
    ) -> CrawlDiagnosticsHistoryReport:
        return svc().build_crawl_diagnostics_history_report(project_id, limit=limit)

    @app.get("/api/crawl/diagnostics/history", response_model=CrawlDiagnosticsHistoryReport)
    def crawl_diagnostics_history(
        limit: int = 10,
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> CrawlDiagnosticsHistoryReport:
        return svc().build_crawl_diagnostics_history_report(project_id, limit=limit)

    @app.get("/api/projects/{project_id}/connections", response_model=ProjectConnections)
    def project_connections(project_id: str) -> ProjectConnections:
        try:
            return svc().get_project_connections(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/connectors/health", response_model=ConnectorsHealthResult)
    def project_connectors_health(project_id: str) -> ConnectorsHealthResult:
        try:
            return svc().get_project_connectors_health(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/connectors/health", response_model=WorkspaceConnectorsHealthReport)
    def workspace_connectors_health(project_id: Optional[str] = Query(default=None, alias="projectId")) -> WorkspaceConnectorsHealthReport:
        return svc().get_workspace_connectors_health(project_id=project_id)

    @app.put("/api/projects/{project_id}/connections", response_model=ProjectConnections)
    def update_project_connections(
        project_id: str,
        request: ProjectConnectionsUpdateRequest,
        _: None = Depends(require_api_key),
    ) -> ProjectConnections:
        try:
            return svc().update_project_connections(project_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/connections/test", response_model=ProjectConnectionsTestResult)
    def test_project_connections(
        project_id: str,
        _: None = Depends(require_api_key),
    ) -> ProjectConnectionsTestResult:
        try:
            return svc().test_project_connections(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/connections/refresh", response_model=ProjectConnectionsRefreshResult)
    def refresh_project_connections(
        project_id: str,
        request: ProjectConnectionsRefreshRequest,
        _: None = Depends(require_api_key),
    ) -> ProjectConnectionsRefreshResult:
        try:
            return svc().refresh_project_connections(project_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/projects/{project_id}/connectors/{provider}/refresh", response_model=ConnectorRefreshResult)
    def refresh_project_connector(
        project_id: str,
        provider: ConnectorKind,
        _: None = Depends(require_api_key),
    ) -> ConnectorRefreshResult:
        try:
            return svc().refresh_project_connector(project_id, provider)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/bulk/projects/connections/test", response_model=BulkConnectionsTestResult)
    def bulk_test_connections(
        request: BulkConnectionsTestRequest,
        _: None = Depends(require_api_key),
    ) -> BulkConnectionsTestResult:
        return svc().test_projects_connections(request)

    @app.post("/api/bulk/projects/connections/refresh", response_model=BulkProjectConnectionsRefreshResult)
    def bulk_refresh_connections(
        request: BulkProjectConnectionsRefreshRequest,
        _: None = Depends(require_api_key),
    ) -> BulkProjectConnectionsRefreshResult:
        return svc().refresh_projects_connections(request)

    @app.post("/api/bulk/projects/connectors/{provider}/refresh", response_model=BulkConnectorRefreshResult)
    def bulk_refresh_project_connector(
        provider: ConnectorKind,
        request: BulkConnectorRefreshRequest,
        _: None = Depends(require_api_key),
    ) -> BulkConnectorRefreshResult:
        return svc().refresh_projects_connector(provider, request)

    @app.post("/api/bulk/connectors/strict-gap/refresh", response_model=BulkStrictGapRefreshResult)
    def bulk_refresh_strict_gap_connectors(
        request: BulkStrictGapRefreshRequest,
        _: None = Depends(require_api_key),
    ) -> BulkStrictGapRefreshResult:
        return svc().refresh_strict_gap_connectors(request)

    @app.post("/api/bulk/connectors/market-evidence/refresh", response_model=BulkMarketEvidenceRefreshResult)
    def bulk_refresh_market_evidence_connectors(
        request: BulkMarketEvidenceRefreshRequest,
        _: None = Depends(require_api_key),
    ) -> BulkMarketEvidenceRefreshResult:
        return svc().refresh_market_evidence_connectors(request)

    @app.post("/api/bulk/connectors/blocking/refresh", response_model=BulkBlockingRefreshResult)
    def bulk_refresh_blocking_connectors(
        request: BulkBlockingRefreshRequest,
        _: None = Depends(require_api_key),
    ) -> BulkBlockingRefreshResult:
        return svc().refresh_blocking_connectors(request)

    @app.get("/api/tasks", response_model=list[TaskSummary])
    def list_tasks() -> list[TaskSummary]:
        return svc().list_tasks()

    @app.get("/api/tasks/{task_id}", response_model=WorkflowBundle)
    def task_detail(task_id: str) -> WorkflowBundle:
        try:
            return svc().get_workflow(task_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/tasks/bulk/approve", response_model=BulkApprovalResult)
    def bulk_approve(request: BulkApprovalRequest, _: None = Depends(require_api_key)) -> BulkApprovalResult:
        return svc().approve_tasks(request)

    @app.post("/api/tasks/{task_id}/approve", response_model=WorkflowBundle)
    def approve(task_id: str, request: ApprovalDecisionRequest, _: None = Depends(require_api_key)) -> WorkflowBundle:
        try:
            return svc().approve_task(task_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/tasks/{task_id}/deploy", response_model=WorkflowBundle)
    def deploy(task_id: str, request: DeploymentActionRequest, _: None = Depends(require_api_key)) -> WorkflowBundle:
        try:
            return svc().deploy_task(task_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/tasks/{task_id}/rollback", response_model=WorkflowBundle)
    def rollback(task_id: str, request: RollbackActionRequest, _: None = Depends(require_api_key)) -> WorkflowBundle:
        try:
            return svc().rollback_task(task_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/skills")
    def skills() -> list[dict[str, object]]:
        return [skill.model_dump(mode="json", by_alias=True) for skill in svc().list_skills()]

    @app.get("/api/policy")
    def policy() -> dict[str, object]:
        return svc().get_policy().model_dump(mode="json", by_alias=True)

    @app.put("/api/policy", response_model=WorkspacePolicy)
    def update_policy(request: WorkspacePolicyUpdateRequest, _: None = Depends(require_api_key)) -> WorkspacePolicy:
        return svc().update_policy(request)

    @app.get("/api/billing", response_model=WorkspaceBillingReport)
    def billing(project_id: Optional[str] = Query(default=None, alias="projectId")) -> WorkspaceBillingReport:
        return svc().build_workspace_billing_report(project_id=project_id)

    @app.put("/api/billing", response_model=WorkspaceBillingReport)
    def update_billing(request: WorkspaceBillingPolicyUpdateRequest, _: None = Depends(require_api_key)) -> WorkspaceBillingReport:
        svc().update_billing_policy(request)
        return svc().build_workspace_billing_report()

    @app.post("/api/billing/settlement/execute", response_model=WorkspaceBillingSettlementExecutionReport)
    def execute_billing_settlement(
        request: WorkspaceBillingSettlementExecutionRequest,
        _: None = Depends(require_api_key),
    ) -> WorkspaceBillingSettlementExecutionReport:
        return svc().execute_workspace_billing_settlement(request)

    @app.post("/api/billing/settlement/execute/batch", response_model=WorkspaceBillingSettlementExecutionBatchReport)
    def execute_billing_settlement_batch(
        request: WorkspaceBillingSettlementExecutionBatchRequest,
        _: None = Depends(require_api_key),
    ) -> WorkspaceBillingSettlementExecutionBatchReport:
        return svc().execute_workspace_billing_settlement_batch(request)

    @app.get("/api/billing/settlement/history", response_model=WorkspaceBillingSettlementExecutionHistoryReport)
    def billing_settlement_history(
        limit: int = 20,
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> WorkspaceBillingSettlementExecutionHistoryReport:
        return svc().get_workspace_billing_settlement_history(limit=limit, project_id=project_id)

    @app.get("/api/billing/gateway", response_model=WorkspaceBillingSettlementGatewayReport)
    def billing_gateway(project_id: Optional[str] = Query(default=None, alias="projectId")) -> WorkspaceBillingSettlementGatewayReport:
        return svc().build_billing_gateway_report(project_id=project_id)

    @app.get("/api/billing/gateway/providers", response_model=WorkspaceBillingSettlementGatewayProviderStatusReport)
    def billing_gateway_providers(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> WorkspaceBillingSettlementGatewayProviderStatusReport:
        return svc().build_billing_gateway_provider_status_report(project_id=project_id)

    @app.get("/api/billing/gateway/export", response_model=WorkspaceBillingSettlementGatewayExportReport)
    def billing_gateway_export(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> WorkspaceBillingSettlementGatewayExportReport:
        return svc().build_billing_gateway_export_report(project_id=project_id)

    @app.get("/api/billing/gateway/provider-requirements", response_model=WorkspaceBillingSettlementProviderRequirementsReport)
    def billing_gateway_provider_requirements() -> WorkspaceBillingSettlementProviderRequirementsReport:
        return svc().build_billing_settlement_provider_requirements_report()

    @app.get("/api/billing/gateway/history", response_model=WorkspaceBillingSettlementGatewayHistoryReport)
    def billing_gateway_history(
        limit: int = 20,
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> WorkspaceBillingSettlementGatewayHistoryReport:
        return svc().build_workspace_billing_gateway_history_report(limit=limit, project_id=project_id)

    @app.put("/api/billing/gateway", response_model=WorkspaceBillingSettlementGatewayReport)
    def update_billing_gateway(
        request: WorkspaceBillingSettlementGatewayPolicyUpdateRequest,
        _: None = Depends(require_api_key),
    ) -> WorkspaceBillingSettlementGatewayReport:
        svc().update_billing_gateway_policy(request)
        return svc().build_billing_gateway_report()

    @app.post("/api/billing/gateway/publish", response_model=WorkspaceBillingSettlementGatewayPublishReport)
    def publish_billing_gateway(
        _: None = Depends(require_api_key),
    ) -> WorkspaceBillingSettlementGatewayPublishReport:
        gateway_report = svc().build_billing_gateway_report()
        return svc()._execute_billing_gateway_publish(gateway_report)

    @app.get("/api/experiments", response_model=WorkspaceExperimentReport)
    def experiments(project_id: Optional[str] = Query(default=None, alias="projectId")) -> WorkspaceExperimentReport:
        return svc().build_workspace_experiment_report(project_id=project_id)

    @app.put("/api/experiments", response_model=WorkspaceExperimentReport)
    def update_experiments(
        request: WorkspaceExperimentPolicyUpdateRequest,
        _: None = Depends(require_api_key),
    ) -> WorkspaceExperimentReport:
        svc().update_experiment_policy(request)
        return svc().build_workspace_experiment_report()

    @app.post("/api/experiments/assign", response_model=WorkspaceExperimentAssignmentReport)
    def experiment_assignment(request: WorkspaceExperimentAssignmentRequest) -> WorkspaceExperimentAssignmentReport:
        return svc().build_workspace_experiment_assignment_report(request)

    @app.get("/api/localization", response_model=WorkspaceLocalizationReport)
    def localization(project_id: Optional[str] = Query(default=None, alias="projectId")) -> WorkspaceLocalizationReport:
        return svc().build_workspace_localization_report(project_id=project_id)

    @app.put("/api/localization", response_model=WorkspaceLocalizationReport)
    def update_localization(
        request: WorkspaceLocalizationPolicyUpdateRequest,
        _: None = Depends(require_api_key),
    ) -> WorkspaceLocalizationReport:
        svc().update_localization_policy(request)
        return svc().build_workspace_localization_report()

    @app.post("/api/localization/assign", response_model=WorkspaceLocalizationAssignmentReport)
    def localization_assignment(request: WorkspaceLocalizationAssignmentRequest) -> WorkspaceLocalizationAssignmentReport:
        return svc().build_workspace_localization_assignment_report(request)

    @app.get("/api/template-market", response_model=WorkspaceTemplateMarketReport)
    def template_market(project_id: Optional[str] = Query(default=None, alias="projectId")) -> WorkspaceTemplateMarketReport:
        return svc().build_workspace_template_market_report(project_id=project_id)

    @app.put("/api/template-market", response_model=WorkspaceTemplateMarketReport)
    def update_template_market(
        request: WorkspaceTemplateMarketPolicyUpdateRequest,
        _: None = Depends(require_api_key),
    ) -> WorkspaceTemplateMarketReport:
        svc().update_template_market_policy(request)
        return svc().build_workspace_template_market_report()

    @app.get("/api/model-gateway", response_model=WorkspaceModelGatewayReport)
    def model_gateway(project_id: Optional[str] = Query(default=None, alias="projectId")) -> WorkspaceModelGatewayReport:
        return svc().build_workspace_model_gateway_report(project_id=project_id)

    @app.get("/api/model-gateway/providers", response_model=WorkspaceModelGatewayProviderStatusReport)
    def model_gateway_providers(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> WorkspaceModelGatewayProviderStatusReport:
        return svc().build_model_gateway_provider_status_report(project_id=project_id)

    @app.get("/api/model-gateway/history", response_model=WorkspaceModelGatewayHistoryReport)
    def model_gateway_history(
        limit: int = 20,
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> WorkspaceModelGatewayHistoryReport:
        return svc().build_workspace_model_gateway_history_report(limit=limit, project_id=project_id)

    @app.post("/api/model-gateway/publish", response_model=WorkspaceModelGatewayReport)
    def publish_model_gateway(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        _: None = Depends(require_api_key),
    ) -> WorkspaceModelGatewayReport:
        return svc().publish_model_gateway_policy(project_id=project_id)

    @app.post("/api/projects/{project_id}/runtime-route", response_model=RuntimeRouteReport)
    def runtime_route(project_id: str, runtime_request: RuntimeRouteRequest, request: Request) -> RuntimeRouteReport:
        try:
            with app.state.service.database.session() as session:
                project = session.get(ProjectRow, project_id)
                if project is None:
                    raise ValueError(f"Unknown project: {project_id}")
                intake = app.state.service._project_intake(project)
            request = RuntimeRouteRequest(
                task_id=runtime_request.task_id,
                subject_key=runtime_request.subject_key,
                request_path=runtime_request.request_path or request.url.path,
                request_method=runtime_request.request_method or request.method,
                target_surface=runtime_request.target_surface,
                target_locale=runtime_request.target_locale or intake.locale,
                host=_runtime_request_host(request, runtime_request.host),
            )
            runtime_route_report = svc().build_runtime_route_report(project_id, intake, request=request)
            try:
                svc()._audit(
                    project_id,
                    runtime_route_report.task_id,
                    "runtime.route.previewed",
                    {
                        "requestPath": runtime_route_report.request_path,
                        "requestMethod": runtime_route_report.request_method,
                        "requestProject": project_id,
                        "runtimeReady": runtime_route_report.runtime_ready,
                        "executionMode": runtime_route_report.execution_mode,
                        "executionAction": runtime_route_report.execution_action,
                        "executionReason": runtime_route_report.execution_reason,
                        "executionEntrypoint": runtime_route_report.execution_entrypoint,
                        "gatewayRouteProvider": runtime_route_report.gateway_route_provider_name,
                        "gatewayRouteFallbackProvider": runtime_route_report.gateway_route_fallback_provider_name,
                        "gatewayRoutePriority": runtime_route_report.gateway_route_priority,
                        "experimentVariant": (
                            runtime_route_report.experiment_assignment.assignments[0].assigned_variant_name
                            if runtime_route_report.experiment_assignment
                            and runtime_route_report.experiment_assignment.assignments
                            and runtime_route_report.experiment_assignment.assignments[0].assigned_variant_name
                            else "unassigned"
                        ),
                        "localizationCluster": (
                            runtime_route_report.localization_assignment.assignments[0].cluster_key
                            if runtime_route_report.localization_assignment
                            and runtime_route_report.localization_assignment.assignments
                            else "unassigned"
                        ),
                        "gateway": (
                            runtime_route_report.gateway_report.policy.default_provider_name
                            if runtime_route_report.gateway_report is not None
                            else "local"
                        ),
                    },
                )
            except Exception:
                pass
            return runtime_route_report
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/runtime-execute", response_model=RuntimeExecutionResponse)
    def runtime_execute(
        project_id: str,
        request: Request,
        subject_key: Optional[str] = Query(default=None, alias="subjectKey"),
        target_surface: Literal["site", "seo", "content", "ad", "ui"] = Query(default="site", alias="targetSurface"),
        target_locale: Optional[str] = Query(default=None, alias="targetLocale"),
        host: Optional[str] = Query(default=None),
        response_mode: Literal["json", "redirect", "render", "proxy"] = Query(default="json", alias="responseMode"),
        enforce_runtime_ready: bool = Query(default=False, alias="enforceRuntimeReady"),
    ) -> RuntimeExecutionResponse | HTMLResponse | RedirectResponse | Response:
        try:
            existing = getattr(request.state, "runtime_execution_response", None)
            if existing is not None:
                execution = existing
            else:
                resolved_host = _runtime_request_host(request, host)
                runtime_request = RuntimeRouteRequest(
                    subject_key=subject_key,
                    request_path=request.url.path,
                    request_method=request.method,
                    target_surface=target_surface,
                    target_locale=target_locale,
                    host=resolved_host,
                )
                execution = svc().build_runtime_execution_response(project_id, request=runtime_request)
            if enforce_runtime_ready and execution.served_mode != "runtime":
                raise HTTPException(status_code=409, detail="Runtime chain is not ready for strict runtime serving.")
            headers = {
                "X-SEO-AD-Served-Mode": execution.served_mode,
                "X-SEO-AD-Served-Target": execution.served_target,
            }
            if execution.served_response_mode:
                headers["X-SEO-AD-Served-Response-Mode"] = execution.served_response_mode
            if execution.served_url:
                headers["X-SEO-AD-Served-URL"] = execution.served_url
            if response_mode == "redirect" and execution.served_mode != "blocked" and execution.served_url:
                return RedirectResponse(url=execution.served_url, status_code=307, headers=headers)
            if response_mode == "proxy" and execution.served_mode != "blocked":
                if (
                    execution.deployment is not None
                    and execution.deployment.provider_url
                    and execution.deployment.provider_url.startswith(("http://", "https://"))
                ):
                    return _proxy_runtime_response(
                        execution.deployment.provider_url,
                        request=request,
                        headers=headers,
                        forwarded_host=_runtime_request_host(request, host),
                    )
                if execution.preview is not None:
                    response = HTMLResponse(content=execution.preview.after_html, status_code=execution.status_code, headers=headers)
                    response.headers["X-SEO-AD-Proxied-URL"] = execution.served_url or ""
                    return response
                if execution.served_url:
                    return _proxy_runtime_response(
                        execution.served_url,
                        request=request,
                        headers=headers,
                        forwarded_host=_runtime_request_host(request, host),
                    )
            if response_mode == "render" and execution.served_mode != "blocked":
                if execution.preview is not None:
                    return HTMLResponse(content=execution.preview.after_html, status_code=execution.status_code, headers=headers)
                if execution.served_url:
                    return RedirectResponse(url=execution.served_url, status_code=307, headers=headers)
            return execution
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/runtime-execute/preview")
    def runtime_execute_preview(
        project_id: str,
        request: Request,
        subject_key: Optional[str] = Query(default=None, alias="subjectKey"),
        target_surface: Literal["site", "seo", "content", "ad", "ui"] = Query(default="site", alias="targetSurface"),
        target_locale: Optional[str] = Query(default=None, alias="targetLocale"),
        host: Optional[str] = Query(default=None),
    ) -> HTMLResponse:
        try:
            execution = svc().build_runtime_execution_response(
                project_id,
                request=RuntimeRouteRequest(
                    subject_key=subject_key,
                    request_path=f"/api/projects/{project_id}/runtime-execute",
                    request_method="GET",
                    target_surface=target_surface,
                    target_locale=target_locale,
                    host=_runtime_request_host(request, host),
                ),
            )
            if execution.served_mode == "blocked" or execution.preview is None:
                raise HTTPException(status_code=409, detail="Runtime preview is not available for this project.")
            headers = {
                "X-SEO-AD-Served-Mode": execution.served_mode,
                "X-SEO-AD-Served-Target": execution.served_target,
            }
            if execution.served_response_mode:
                headers["X-SEO-AD-Served-Response-Mode"] = execution.served_response_mode
            if execution.served_url:
                headers["X-SEO-AD-Served-URL"] = execution.served_url
            return HTMLResponse(content=execution.preview.after_html, status_code=200, headers=headers)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.api_route("/api/projects/{project_id}/runtime-execute/proxy/{proxy_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def runtime_execute_proxy_path(
        project_id: str,
        proxy_path: str,
        request: Request,
        enforce_runtime_ready: bool = Query(default=False, alias="enforceRuntimeReady"),
        subject_key: Optional[str] = Query(default=None, alias="subjectKey"),
        target_surface: Literal["site", "seo", "content", "ad", "ui"] = Query(default="site", alias="targetSurface"),
        target_locale: Optional[str] = Query(default=None, alias="targetLocale"),
        host: Optional[str] = Query(default=None),
    ) -> Response:
        try:
            request_body = await request.body()
            content_type = request.headers.get("content-type") or None
            resolved_host = _runtime_request_host(request, host)
            execution = svc().build_runtime_execution_response(
                project_id,
                request=RuntimeRouteRequest(
                    subject_key=subject_key,
                    request_path=f"/api/projects/{project_id}/runtime-execute/proxy/{proxy_path}",
                    request_method=request.method,
                    target_surface=target_surface,
                    target_locale=target_locale,
                    host=resolved_host,
                ),
            )
            if execution.served_mode == "blocked":
                try:
                    svc()._audit(
                        project_id,
                        execution.task_id,
                        "runtime.proxy.blocked",
                        {
                            "requestPath": request.url.path,
                            "requestMethod": request.method,
                            "proxyPath": proxy_path,
                            "servedMode": execution.served_mode,
                            "servedTarget": execution.served_target,
                            "strictRuntimeReady": bool(enforce_runtime_ready),
                            "reason": "runtime execution blocked",
                        },
                    )
                except Exception:
                    pass
                raise HTTPException(status_code=409, detail="Runtime proxy route is not available for this project.")
            if enforce_runtime_ready and execution.served_mode != "runtime":
                try:
                    svc()._audit(
                        project_id,
                        execution.task_id,
                        "runtime.proxy.blocked",
                        {
                            "requestPath": request.url.path,
                            "requestMethod": request.method,
                            "proxyPath": proxy_path,
                            "servedMode": execution.served_mode,
                            "servedTarget": execution.served_target,
                            "strictRuntimeReady": bool(enforce_runtime_ready),
                            "reason": "runtime proxy not runtime-ready in strict mode",
                        },
                    )
                except Exception:
                    pass
                raise HTTPException(status_code=409, detail="Runtime proxy route is not runtime-ready in strict mode.")
            headers = {
                "X-SEO-AD-Served-Mode": execution.served_mode,
                "X-SEO-AD-Served-Target": execution.served_target,
            }
            if execution.served_response_mode:
                headers["X-SEO-AD-Served-Response-Mode"] = execution.served_response_mode
            if execution.served_url:
                headers["X-SEO-AD-Served-URL"] = execution.served_url
            if (
                execution.deployment is not None
                and execution.deployment.provider_url
                and execution.deployment.provider_url.startswith(("http://", "https://"))
            ):
                target_url = _runtime_proxy_target(execution.deployment.provider_url, proxy_path, request.url.query)
                response = _proxy_runtime_response(
                    target_url,
                    request=request,
                    headers=headers,
                    forwarded_host=resolved_host,
                    method=request.method,
                    body=request_body or None,
                    content_type=content_type,
                )
                try:
                    svc()._audit(
                        project_id,
                        execution.task_id,
                        "runtime.proxy.requested",
                        {
                            "requestPath": request.url.path,
                            "requestMethod": request.method,
                            "proxyPath": proxy_path,
                            "proxiedUrl": target_url,
                            "servedMode": execution.served_mode,
                            "servedTarget": execution.served_target,
                            "strictRuntimeReady": bool(enforce_runtime_ready),
                        },
                    )
                except Exception:
                    pass
                return response
            if execution.served_url and execution.served_url.startswith(("http://", "https://")):
                target_url = _runtime_proxy_target(execution.served_url, proxy_path, request.url.query)
                response = _proxy_runtime_response(
                    target_url,
                    request=request,
                    headers=headers,
                    forwarded_host=resolved_host,
                    method=request.method,
                    body=request_body or None,
                    content_type=content_type,
                )
                try:
                    svc()._audit(
                        project_id,
                        execution.task_id,
                        "runtime.proxy.requested",
                        {
                            "requestPath": request.url.path,
                            "requestMethod": request.method,
                            "proxyPath": proxy_path,
                            "proxiedUrl": target_url,
                            "servedMode": execution.served_mode,
                            "servedTarget": execution.served_target,
                            "strictRuntimeReady": bool(enforce_runtime_ready),
                        },
                    )
                except Exception:
                    pass
                return response
            if execution.preview is not None:
                response = HTMLResponse(content=execution.preview.after_html, status_code=200, headers=headers)
                response.headers["X-SEO-AD-Proxied-URL"] = execution.served_url or ""
                try:
                    svc()._audit(
                        project_id,
                        execution.task_id,
                        "runtime.proxy.requested",
                        {
                            "requestPath": request.url.path,
                            "requestMethod": request.method,
                            "proxyPath": proxy_path,
                            "proxiedUrl": execution.served_url or "",
                            "servedMode": execution.served_mode,
                            "servedTarget": execution.served_target,
                            "strictRuntimeReady": bool(enforce_runtime_ready),
                        },
                    )
                except Exception:
                    pass
                return response
            try:
                svc()._audit(
                    project_id,
                    execution.task_id,
                    "runtime.proxy.blocked",
                    {
                        "requestPath": request.url.path,
                        "requestMethod": request.method,
                        "proxyPath": proxy_path,
                        "servedMode": execution.served_mode,
                        "servedTarget": execution.served_target,
                        "strictRuntimeReady": bool(enforce_runtime_ready),
                        "reason": "runtime proxy route is not resolvable",
                    },
                )
            except Exception:
                pass
            raise HTTPException(status_code=409, detail="Runtime proxy route is not resolvable for this project.")
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.api_route(
        "/api/projects/{project_id}/runtime-execute/proxy-strict/{proxy_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    )
    async def runtime_execute_proxy_path_strict(
        project_id: str,
        proxy_path: str,
        request: Request,
        subject_key: Optional[str] = Query(default=None, alias="subjectKey"),
        target_surface: Literal["site", "seo", "content", "ad", "ui"] = Query(default="site", alias="targetSurface"),
        target_locale: Optional[str] = Query(default=None, alias="targetLocale"),
        host: Optional[str] = Query(default=None),
    ) -> Response:
        return await runtime_execute_proxy_path(
            project_id=project_id,
            proxy_path=proxy_path,
            request=request,
            enforce_runtime_ready=True,
            subject_key=subject_key,
            target_surface=target_surface,
            target_locale=target_locale,
            host=host,
        )

    @app.get("/api/runtime-route/health", response_model=WorkspaceRuntimeRouteHealthReport)
    def runtime_route_health(project_id: Optional[str] = Query(default=None, alias="projectId")) -> WorkspaceRuntimeRouteHealthReport:
        return svc().build_workspace_runtime_route_health_report(project_id=project_id)

    @app.get("/api/runtime-route/history", response_model=WorkspaceRuntimeRouteHistoryReport)
    def runtime_route_history(
        limit: int = Query(default=20, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> WorkspaceRuntimeRouteHistoryReport:
        return svc().list_workspace_runtime_route_history(limit=limit, project_id=project_id)

    @app.get("/api/projects/{project_id}/runtime-edge/config", response_model=ProjectRuntimeEdgeConfig)
    def project_runtime_edge_config(project_id: str) -> ProjectRuntimeEdgeConfig:
        try:
            return svc().build_project_runtime_edge_config(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/runtime-edge/routes", response_model=WorkspaceRuntimeEdgeConfigReport)
    def runtime_edge_routes(project_id: Optional[str] = Query(default=None, alias="projectId")) -> WorkspaceRuntimeEdgeConfigReport:
        return svc().build_workspace_runtime_edge_config_report(project_id=project_id)

    @app.get("/api/runtime-edge/routes/overrides", response_model=RuntimeEdgeRouteOverridesReport)
    def runtime_edge_route_overrides(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> RuntimeEdgeRouteOverridesReport:
        return svc().get_runtime_edge_route_overrides(project_id=project_id)

    @app.put("/api/runtime-edge/routes/overrides", response_model=RuntimeEdgeRouteOverridesReport)
    def update_runtime_edge_route_overrides(
        request: RuntimeEdgeRouteOverridesUpdateRequest,
        _: None = Depends(require_api_key),
    ) -> RuntimeEdgeRouteOverridesReport:
        return svc().update_runtime_edge_route_overrides(request)

    @app.get("/api/runtime-edge/map", response_model=WorkspaceRuntimeEdgeRouteMapReport)
    def runtime_edge_map(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_routes_only: bool = Query(default=False, alias="strictRoutesOnly"),
    ) -> WorkspaceRuntimeEdgeRouteMapReport:
        return svc().build_workspace_runtime_edge_route_map_report(
            project_id=project_id,
            strict_routes_only=strict_routes_only,
        )

    @app.get("/api/runtime-edge/export", response_model=RuntimeEdgeGatewayExportReport)
    def runtime_edge_export(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_routes_only: bool = Query(default=False, alias="strictRoutesOnly"),
    ) -> RuntimeEdgeGatewayExportReport:
        return svc().build_runtime_edge_gateway_export_report(
            project_id=project_id,
            strict_routes_only=strict_routes_only,
        )

    @app.get("/api/runtime-edge/validate", response_model=RuntimeEdgeValidationReport)
    def runtime_edge_validate(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_routes_only: bool = Query(default=False, alias="strictRoutesOnly"),
    ) -> RuntimeEdgeValidationReport:
        return svc().build_runtime_edge_validation_report(
            project_id=project_id,
            strict_routes_only=strict_routes_only,
        )

    @app.get("/api/runtime-edge/rollout-plan", response_model=RuntimeEdgeRolloutPlanReport)
    def runtime_edge_rollout_plan(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_routes_only: bool = Query(default=False, alias="strictRoutesOnly"),
        canary_percent: int = Query(default=20, ge=1, le=100, alias="canaryPercent"),
    ) -> RuntimeEdgeRolloutPlanReport:
        return svc().build_runtime_edge_rollout_plan_report(
            project_id=project_id,
            strict_routes_only=strict_routes_only,
            canary_percent=canary_percent,
        )

    @app.post("/api/runtime-edge/rollout/execute", response_model=RuntimeEdgeRolloutExecutionReport)
    def runtime_edge_rollout_execute(
        request: RuntimeEdgeRolloutExecuteRequest,
        _: None = Depends(require_api_key),
    ) -> RuntimeEdgeRolloutExecutionReport:
        return svc().execute_runtime_edge_rollout(request)

    @app.post("/api/runtime-edge/deploy", response_model=RuntimeEdgeDeploymentReport)
    def runtime_edge_deploy(
        request: RuntimeEdgeDeploymentRequest,
        _: None = Depends(require_api_key),
    ) -> RuntimeEdgeDeploymentReport:
        return svc().execute_runtime_edge_deployment(request)

    @app.post("/api/runtime-edge/deploy/batch", response_model=RuntimeEdgeDeploymentBatchReport)
    def runtime_edge_deploy_batch(
        request: RuntimeEdgeDeploymentBatchRequest,
        _: None = Depends(require_api_key),
    ) -> RuntimeEdgeDeploymentBatchReport:
        return svc().execute_runtime_edge_deployment_batch(request)

    @app.post("/api/runtime-edge/deploy/batch/enqueue", response_model=RuntimeEdgeDeploymentBatchEnqueueResult)
    def runtime_edge_deploy_batch_enqueue(
        request: RuntimeEdgeDeploymentBatchRequest,
        _: None = Depends(require_api_key),
    ) -> RuntimeEdgeDeploymentBatchEnqueueResult:
        return svc().enqueue_runtime_edge_deployment_batch(request)

    @app.get("/api/runtime-edge/deploy/history", response_model=RuntimeEdgeDeploymentHistoryReport)
    def runtime_edge_deploy_history(
        limit: int = Query(default=20, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> RuntimeEdgeDeploymentHistoryReport:
        return svc().get_runtime_edge_deployment_history(limit=limit, project_id=project_id)

    @app.get("/api/runtime-edge/deploy/batch/history", response_model=RuntimeEdgeDeploymentBatchHistoryReport)
    def runtime_edge_deploy_batch_history(
        limit: int = Query(default=20, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> RuntimeEdgeDeploymentBatchHistoryReport:
        return svc().get_runtime_edge_deployment_batch_history(limit=limit, project_id=project_id)

    @app.get("/api/runtime-ingress/bundle", response_model=RuntimeIngressBundleReport)
    def runtime_ingress_bundle(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_routes_only: Optional[bool] = Query(default=None, alias="strictRoutesOnly"),
    ) -> RuntimeIngressBundleReport:
        return svc().build_runtime_ingress_bundle_report(
            project_id=project_id,
            strict_routes_only=strict_routes_only,
        )

    @app.post("/api/runtime-ingress/bundle", response_model=RuntimeIngressBundleReport)
    def publish_runtime_ingress_bundle(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_routes_only: Optional[bool] = Query(default=None, alias="strictRoutesOnly"),
        _: None = Depends(require_api_key),
    ) -> RuntimeIngressBundleReport:
        return svc().publish_runtime_ingress_bundle(
            project_id=project_id,
            strict_routes_only=strict_routes_only,
        )

    @app.post("/api/runtime-ingress/bundle/batch", response_model=RuntimeIngressBundleBatchReport)
    def publish_runtime_ingress_bundle_batch(
        request: RuntimeIngressBundleBatchRequest,
        _: None = Depends(require_api_key),
    ) -> RuntimeIngressBundleBatchReport:
        return svc().execute_runtime_ingress_bundle_batch(request)

    @app.post("/api/runtime-ingress/bundle/batch/enqueue", response_model=RuntimeIngressBundleBatchEnqueueResult)
    def enqueue_runtime_ingress_bundle_batch(
        request: RuntimeIngressBundleBatchRequest,
        _: None = Depends(require_api_key),
    ) -> RuntimeIngressBundleBatchEnqueueResult:
        return svc().enqueue_runtime_ingress_bundle_batch(request)

    @app.get("/api/runtime-ingress/bundle/batch/history", response_model=RuntimeIngressBundleBatchHistoryReport)
    def runtime_ingress_bundle_batch_history(
        limit: int = Query(default=20, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> RuntimeIngressBundleBatchHistoryReport:
        return svc().get_runtime_ingress_bundle_batch_history(limit=limit, project_id=project_id)

    @app.get("/api/runtime-ingress/bundle/batch/health", response_model=RuntimeIngressBundleBatchHealthReport)
    def runtime_ingress_bundle_batch_health(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> RuntimeIngressBundleBatchHealthReport:
        return svc().build_runtime_ingress_bundle_batch_health_report(project_id=project_id)

    @app.get("/api/runtime-ingress/nginx", response_model=RuntimeIngressConfigArtifactReport)
    def runtime_ingress_nginx(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_routes_only: Optional[bool] = Query(default=None, alias="strictRoutesOnly"),
    ) -> RuntimeIngressConfigArtifactReport:
        return svc().build_runtime_ingress_config_artifact_report(
            format="nginx",
            project_id=project_id,
            strict_routes_only=strict_routes_only,
        )

    @app.post("/api/runtime-ingress/nginx", response_model=RuntimeIngressConfigArtifactReport)
    def publish_runtime_ingress_nginx(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_routes_only: Optional[bool] = Query(default=None, alias="strictRoutesOnly"),
        _: None = Depends(require_api_key),
    ) -> RuntimeIngressConfigArtifactReport:
        return svc().publish_runtime_ingress_config_artifact(
            format="nginx",
            project_id=project_id,
            strict_routes_only=strict_routes_only,
        )

    @app.get("/api/runtime-ingress/caddy", response_model=RuntimeIngressConfigArtifactReport)
    def runtime_ingress_caddy(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_routes_only: Optional[bool] = Query(default=None, alias="strictRoutesOnly"),
    ) -> RuntimeIngressConfigArtifactReport:
        return svc().build_runtime_ingress_config_artifact_report(
            format="caddy",
            project_id=project_id,
            strict_routes_only=strict_routes_only,
        )

    @app.post("/api/runtime-ingress/caddy", response_model=RuntimeIngressConfigArtifactReport)
    def publish_runtime_ingress_caddy(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_routes_only: Optional[bool] = Query(default=None, alias="strictRoutesOnly"),
        _: None = Depends(require_api_key),
    ) -> RuntimeIngressConfigArtifactReport:
        return svc().publish_runtime_ingress_config_artifact(
            format="caddy",
            project_id=project_id,
            strict_routes_only=strict_routes_only,
        )

    @app.get("/api/runtime-ingress/history", response_model=RuntimeIngressConfigArtifactHistoryReport)
    def runtime_ingress_history(
        format: Optional[str] = Query(default=None),
        limit: int = Query(default=20, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> RuntimeIngressConfigArtifactHistoryReport:
        return svc().get_runtime_ingress_config_artifact_history(
            format=format,
            project_id=project_id,
            limit=limit,
        )

    @app.get("/api/runtime-edge/gateway", response_model=RuntimeEdgeGatewayReport)
    def runtime_edge_gateway(project_id: Optional[str] = Query(default=None, alias="projectId")) -> RuntimeEdgeGatewayReport:
        return svc().build_runtime_edge_gateway_report(project_id=project_id)

    @app.get("/api/runtime-edge/gateway/providers", response_model=RuntimeEdgeGatewayProviderStatusReport)
    def runtime_edge_gateway_providers(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> RuntimeEdgeGatewayProviderStatusReport:
        return svc().build_runtime_edge_gateway_provider_status_report(project_id=project_id)

    @app.get("/api/runtime-edge/gateway/history", response_model=RuntimeEdgeGatewayHistoryReport)
    def runtime_edge_gateway_history(
        limit: int = Query(default=10, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> RuntimeEdgeGatewayHistoryReport:
        return svc().build_runtime_edge_gateway_history_report(limit=limit, project_id=project_id)

    @app.put("/api/runtime-edge/gateway", response_model=RuntimeEdgeGatewayReport)
    def update_runtime_edge_gateway(
        request: RuntimeEdgeGatewayPolicyUpdateRequest,
        _: None = Depends(require_api_key),
    ) -> RuntimeEdgeGatewayReport:
        svc().update_runtime_edge_gateway_policy(request)
        return svc().build_runtime_edge_gateway_report()

    @app.post("/api/runtime-edge/gateway/publish", response_model=RuntimeEdgeGatewayReport)
    def publish_runtime_edge_gateway(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        _: None = Depends(require_api_key),
    ) -> RuntimeEdgeGatewayReport:
        return svc().publish_runtime_edge_gateway_policy(project_id=project_id)

    @app.get("/api/runtime-edge/rollout/history", response_model=RuntimeEdgeRolloutHistoryReport)
    def runtime_edge_rollout_history(
        limit: int = Query(default=20, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        stage_id: Optional[str] = Query(default=None, alias="stageId"),
        status: Optional[str] = Query(default=None),
        strict_routes_only: Optional[bool] = Query(default=None, alias="strictRoutesOnly"),
    ) -> RuntimeEdgeRolloutHistoryReport:
        return svc().get_runtime_edge_rollout_history(
            limit=limit,
            project_id=project_id,
            stage_id=stage_id,
            status=status,
            strict_routes_only=strict_routes_only,
        )

    @app.get("/api/runtime-edge/rollout/remediations", response_model=RuntimeEdgeRolloutRemediationReport)
    def runtime_edge_rollout_remediations(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_routes_only: bool = Query(default=False, alias="strictRoutesOnly"),
    ) -> RuntimeEdgeRolloutRemediationReport:
        return svc().build_runtime_edge_rollout_remediation_report(
            project_id=project_id,
            strict_routes_only=strict_routes_only,
        )

    @app.post("/api/runtime-edge/probe", response_model=RuntimeEdgeProbeReport)
    def runtime_edge_probe(
        request: RuntimeEdgeProbeRequest,
        _: None = Depends(require_api_key),
    ) -> RuntimeEdgeProbeReport:
        return svc().execute_runtime_edge_probe(request)

    @app.get("/api/runtime-edge/probe/history", response_model=RuntimeEdgeProbeHistoryReport)
    def runtime_edge_probe_history(
        limit: int = Query(default=20, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_routes_only: Optional[bool] = Query(default=None, alias="strictRoutesOnly"),
    ) -> RuntimeEdgeProbeHistoryReport:
        return svc().get_runtime_edge_probe_history(
            limit=limit,
            project_id=project_id,
            strict_routes_only=strict_routes_only,
        )

    @app.get("/api/ad-audit/history", response_model=WorkspaceAdAuditHistoryReport)
    def ad_audit_history(
        limit: int = Query(default=20, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> WorkspaceAdAuditHistoryReport:
        return svc().build_workspace_ad_audit_history_report(limit=limit, project_id=project_id)

    @app.put("/api/model-gateway", response_model=WorkspaceModelGatewayReport)
    def update_model_gateway(
        request: WorkspaceModelGatewayPolicyUpdateRequest,
        _: None = Depends(require_api_key),
    ) -> WorkspaceModelGatewayReport:
        svc().update_model_gateway_policy(request)
        return svc().build_workspace_model_gateway_report()

    @app.get("/api/prompts", response_model=PromptRegistry)
    def prompts() -> PromptRegistry:
        return svc().build_prompt_registry()

    @app.put("/api/prompts", response_model=PromptRegistry)
    def update_prompts(request: PromptRegistryUpdateRequest, _: None = Depends(require_api_key)) -> PromptRegistry:
        try:
            return svc().update_prompt_registry(request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/prompts/versions", response_model=PromptRegistry)
    def upsert_prompt_version(request: PromptVersionUpsertRequest, _: None = Depends(require_api_key)) -> PromptRegistry:
        try:
            return svc().upsert_prompt_version(request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/prompts/{prompt_id}/activate", response_model=PromptRegistry)
    def activate_prompt_version(
        prompt_id: str,
        request: PromptVersionActivateRequest,
        _: None = Depends(require_api_key),
    ) -> PromptRegistry:
        try:
            return svc().activate_prompt_version(prompt_id, request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/regression-samples", response_model=RegressionSampleSet)
    def regression_samples() -> RegressionSampleSet:
        return svc().build_regression_sample_set()

    @app.get("/api/regressions", response_model=RegressionReport)
    def regressions() -> RegressionReport:
        return svc().build_regression_report()

    @app.get("/api/acceptance/report", response_model=AcceptanceReport)
    def acceptance_report() -> AcceptanceReport:
        return svc().build_acceptance_report()

    @app.get("/api/acceptance/history", response_model=AcceptanceHistoryReport)
    def acceptance_history(
        limit: int = 20,
        passed: Optional[bool] = None,
        failed_gate_id: Optional[str] = Query(default=None, alias="failedGateId"),
    ) -> AcceptanceHistoryReport:
        return svc().get_acceptance_history(limit=limit, passed=passed, failed_gate_id=failed_gate_id)

    @app.get("/api/product-benchmark", response_model=ProductBenchmarkReport)
    def product_benchmark(project_id: Optional[str] = Query(default=None, alias="projectId")) -> ProductBenchmarkReport:
        return svc().build_product_benchmark_report(project_id=project_id)

    @app.get("/api/product-benchmark/remaining", response_model=RemainingTaskReport)
    def product_benchmark_remaining(project_id: Optional[str] = Query(default=None, alias="projectId")) -> RemainingTaskReport:
        return svc().build_remaining_tasks_report(project_id=project_id)

    @app.get("/api/product-benchmark/remaining/board", response_model=RemainingTaskBoardReport)
    def product_benchmark_remaining_board(project_id: Optional[str] = Query(default=None, alias="projectId")) -> RemainingTaskBoardReport:
        return svc().build_remaining_tasks_board_report(project_id=project_id)

    @app.get("/api/visual-regressions", response_model=VisualRegressionReport)
    def visual_regressions() -> VisualRegressionReport:
        return svc().build_visual_regression_report()

    @app.get("/api/visual-regressions/runs", response_model=VisualRegressionRunsReport)
    def visual_regression_runs(project_id: Optional[str] = Query(default=None, alias="projectId")) -> VisualRegressionRunsReport:
        return svc().build_visual_regression_runs_report(project_id=project_id)

    @app.post("/api/visual-regressions/runs/execute", response_model=VisualRegressionRunsReport)
    def execute_visual_regression_runs(
        request: VisualRegressionRunExecuteRequest,
        _: None = Depends(require_api_key),
    ) -> VisualRegressionRunsReport:
        return svc().execute_visual_regression_runs(request)

    @app.post("/api/visual-regressions/runs/enqueue", response_model=VisualRegressionRunEnqueueResult)
    def enqueue_visual_regression_runs(
        request: VisualRegressionRunExecuteRequest,
        _: None = Depends(require_api_key),
    ) -> VisualRegressionRunEnqueueResult:
        return svc().enqueue_visual_regression_run(request)

    @app.get("/api/visual-regressions/health", response_model=VisualRegressionHealthReport)
    def visual_regression_health(project_id: Optional[str] = Query(default=None, alias="projectId")) -> VisualRegressionHealthReport:
        return svc().build_visual_regression_health_report(project_id=project_id)

    @app.get("/api/visual-farm/status", response_model=VisualFarmStatusReport)
    def visual_farm_status(project_id: Optional[str] = Query(default=None, alias="projectId")) -> VisualFarmStatusReport:
        return svc().build_visual_farm_status_report(project_id=project_id)

    @app.get("/api/visual-farm/probe", response_model=VisualFarmProbeReport)
    def visual_farm_probe(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        _: None = Depends(require_api_key),
    ) -> VisualFarmProbeReport:
        return svc().probe_visual_farm(project_id=project_id)

    @app.post("/api/visual-farm/probe/enqueue", response_model=VisualFarmProbeEnqueueResult)
    def enqueue_visual_farm_probe(_: None = Depends(require_api_key)) -> VisualFarmProbeEnqueueResult:
        return svc().enqueue_visual_farm_probe()

    @app.post("/api/visual-farm/deploy", response_model=VisualFarmDeploymentReport)
    def visual_farm_deploy(
        request: VisualFarmDeploymentRequest,
        _: None = Depends(require_api_key),
    ) -> VisualFarmDeploymentReport:
        return svc().execute_visual_farm_deployment(request)

    @app.post("/api/visual-farm/deploy/batch", response_model=VisualFarmDeploymentBatchReport)
    def visual_farm_deploy_batch(
        request: VisualFarmDeploymentBatchRequest,
        _: None = Depends(require_api_key),
    ) -> VisualFarmDeploymentBatchReport:
        return svc().execute_visual_farm_deployment_batch(request)

    @app.post("/api/visual-farm/deploy/batch/enqueue", response_model=VisualFarmDeploymentBatchEnqueueResult)
    def visual_farm_deploy_batch_enqueue(
        request: VisualFarmDeploymentBatchRequest,
        _: None = Depends(require_api_key),
    ) -> VisualFarmDeploymentBatchEnqueueResult:
        return svc().enqueue_visual_farm_deployment_batch(request)

    @app.get("/api/visual-farm/deploy/history", response_model=VisualFarmDeploymentHistoryReport)
    def visual_farm_deploy_history(
        limit: int = Query(default=20, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> VisualFarmDeploymentHistoryReport:
        return svc().get_visual_farm_deployment_history(limit=limit, project_id=project_id)

    @app.get("/api/visual-farm/deploy/batch/history", response_model=VisualFarmDeploymentBatchHistoryReport)
    def visual_farm_deploy_batch_history(
        limit: int = Query(default=20, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> VisualFarmDeploymentBatchHistoryReport:
        return svc().get_visual_farm_deployment_batch_history(limit=limit, project_id=project_id)

    @app.get("/api/visual-farm/gateway", response_model=VisualFarmGatewayReport)
    def visual_farm_gateway(project_id: Optional[str] = Query(default=None, alias="projectId")) -> VisualFarmGatewayReport:
        return svc().build_visual_farm_gateway_report(project_id=project_id)

    @app.get("/api/visual-farm/gateway/providers", response_model=VisualFarmGatewayProviderStatusReport)
    def visual_farm_gateway_providers(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> VisualFarmGatewayProviderStatusReport:
        return svc().build_visual_farm_gateway_provider_status_report(project_id=project_id)

    @app.get("/api/visual-farm/gateway/history", response_model=VisualFarmGatewayHistoryReport)
    def visual_farm_gateway_history(
        limit: int = Query(default=10, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> VisualFarmGatewayHistoryReport:
        return svc().build_visual_farm_gateway_history_report(limit=limit, project_id=project_id)

    @app.put("/api/visual-farm/gateway", response_model=VisualFarmGatewayReport)
    def update_visual_farm_gateway(
        request: VisualFarmGatewayPolicyUpdateRequest,
        _: None = Depends(require_api_key),
    ) -> VisualFarmGatewayReport:
        svc().update_visual_farm_gateway_policy(request)
        return svc().build_visual_farm_gateway_report()

    @app.post("/api/visual-farm/gateway/publish", response_model=VisualFarmGatewayReport)
    def publish_visual_farm_gateway(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        _: None = Depends(require_api_key),
    ) -> VisualFarmGatewayReport:
        return svc().publish_visual_farm_gateway_policy(project_id=project_id)

    @app.get("/api/visual-farm/export", response_model=VisualFarmGatewayExportReport)
    def visual_farm_export(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> VisualFarmGatewayExportReport:
        return svc().build_visual_farm_gateway_export_report(project_id=project_id)

    @app.get("/api/visual-farm/probe/history", response_model=VisualFarmProbeHistoryReport)
    def visual_farm_probe_history(
        limit: int = Query(default=20, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_mode: Optional[bool] = Query(default=None, alias="strictMode"),
    ) -> VisualFarmProbeHistoryReport:
        return svc().get_visual_farm_probe_history(
            limit=limit,
            project_id=project_id,
            strict_mode=strict_mode,
        )

    @app.post("/api/visual-regressions/retry", response_model=VisualRegressionRetryResult)
    def retry_visual_regressions(request: VisualRegressionRetryRequest, _: None = Depends(require_api_key)) -> VisualRegressionRetryResult:
        return svc().retry_visual_regressions(request)

    @app.get("/api/visual-regressions/retry/history", response_model=VisualRegressionRetryHistoryReport)
    def visual_regression_retry_history(
        limit: int = Query(default=10, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> VisualRegressionRetryHistoryReport:
        return svc().get_visual_regression_retry_history(limit=limit, project_id=project_id)

    @app.get("/api/visual-regressions/runs/history", response_model=VisualRegressionRunHistoryReport)
    def visual_regression_run_history(
        limit: int = Query(default=20, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        strict_mode: Optional[bool] = Query(default=None, alias="strictMode"),
    ) -> VisualRegressionRunHistoryReport:
        return svc().get_visual_regression_run_history(limit=limit, project_id=project_id, strict_mode=strict_mode)

    @app.get("/api/visual-regressions/remediations", response_model=VisualRegressionRemediationReport)
    def visual_regression_remediations(project_id: Optional[str] = Query(default=None, alias="projectId")) -> VisualRegressionRemediationReport:
        return svc().build_visual_regression_remediation_report(project_id=project_id)

    @app.get("/api/skill-regressions", response_model=SkillRegressionReport)
    def skill_regressions() -> SkillRegressionReport:
        return svc().build_skill_regression_report()

    @app.get("/api/alerts", response_model=AlertReport)
    def alerts(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        project_ids: list[str] = Query(default_factory=list),
        categories: list[str] = Query(default_factory=list),
        severities: list[str] = Query(default_factory=list),
        providers: list[str] = Query(default_factory=list),
        blocking: Optional[bool] = None,
        _: None = Depends(require_api_key),
    ) -> AlertReport:
        combined_project_ids = list(project_ids)
        normalized_project_id = str(project_id or "").strip() or None
        if normalized_project_id and normalized_project_id not in combined_project_ids:
            combined_project_ids.append(normalized_project_id)
        report = svc().build_alert_report()
        filtered = svc().filter_alert_report(
            report,
            project_ids=combined_project_ids,
            categories=categories,
            severities=severities,
            providers=providers,
            blocking=blocking,
        )
        if normalized_project_id or len(combined_project_ids) == 1:
            filtered = filtered.model_copy(update={"project_id": normalized_project_id or combined_project_ids[0]})
        return filtered

    @app.get("/api/alerts/latest", response_model=AlertReport)
    def alerts_latest(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        project_ids: list[str] = Query(default_factory=list),
        categories: list[str] = Query(default_factory=list),
        severities: list[str] = Query(default_factory=list),
        providers: list[str] = Query(default_factory=list),
        blocking: Optional[bool] = None,
    ) -> AlertReport:
        combined_project_ids = list(project_ids)
        normalized_project_id = str(project_id or "").strip() or None
        if normalized_project_id and normalized_project_id not in combined_project_ids:
            combined_project_ids.append(normalized_project_id)
        report = svc().get_latest_alert_report()
        filtered = svc().filter_alert_report(
            report,
            project_ids=combined_project_ids,
            categories=categories,
            severities=severities,
            providers=providers,
            blocking=blocking,
        )
        if normalized_project_id or len(combined_project_ids) == 1:
            filtered = filtered.model_copy(update={"project_id": normalized_project_id or combined_project_ids[0]})
        return filtered

    @app.post("/api/alerts/emit", response_model=AlertReport)
    def alerts_emit(_: None = Depends(require_api_key)) -> AlertReport:
        return svc().build_alert_report()

    @app.get("/api/alerts/history", response_model=AlertHistoryReport)
    def alerts_history(
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        project_ids: list[str] = Query(default_factory=list),
        categories: list[str] = Query(default_factory=list),
        severities: list[str] = Query(default_factory=list),
        providers: list[str] = Query(default_factory=list),
        blocking: Optional[bool] = None,
        limit: int = 10,
        offset: int = 0,
        order: str = "desc",
        cursor: Optional[str] = None,
    ) -> AlertHistoryReport:
        return svc().build_alert_history_report(
            limit=limit,
            offset=offset,
            order="asc" if order.lower() == "asc" else "desc",
            cursor=cursor,
            project_id=project_id,
            project_ids=project_ids,
            categories=categories,
            severities=severities,
            providers=providers,
            blocking=blocking,
        )

    @app.get("/api/alerts/deliveries", response_model=AlertDeliveryReport)
    def alerts_deliveries(
        limit: int = 50,
        route: Optional[str] = None,
        status: Optional[str] = None,
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> AlertDeliveryReport:
        return svc().build_alert_delivery_report(limit=limit, route=route, status=status, project_id=project_id)

    @app.get("/api/alerts/emit/status", response_model=AlertEmitStatusReport)
    def alerts_emit_status(project_id: Optional[str] = Query(default=None, alias="projectId")) -> AlertEmitStatusReport:
        return svc().build_alert_emit_status_report(project_id=project_id)

    @app.get("/api/alerts/emit/history", response_model=AlertEmitHistoryReport)
    def alerts_emit_history(
        limit: int = 50,
        status: Optional[str] = None,
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> AlertEmitHistoryReport:
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in {"", "executed", "suppressed"}:
            raise HTTPException(status_code=422, detail="Invalid alert emit status")
        return svc().build_alert_emit_history_report(
            limit=limit,
            status=normalized_status or None,
            project_id=project_id,
        )

    @app.get("/api/alerts/presets", response_model=AlertPresetCollection)
    def alert_presets(project_id: Optional[str] = Query(default=None, alias="projectId")) -> AlertPresetCollection:
        return svc().get_alert_presets(project_id=project_id)

    @app.put("/api/alerts/presets", response_model=AlertPresetCollection)
    def update_alert_presets(request: AlertPresetUpdateRequest, _: None = Depends(require_alert_preset_write)) -> AlertPresetCollection:
        try:
            return svc().update_alert_presets(request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/alerts/rules", response_model=AlertRuleCollection)
    def alert_rules() -> AlertRuleCollection:
        return svc().get_alert_rules()

    @app.put("/api/alerts/rules", response_model=AlertRuleCollection)
    def update_alert_rules(request: AlertRuleUpdateRequest, _: None = Depends(require_alert_preset_write)) -> AlertRuleCollection:
        try:
            return svc().update_alert_rules(request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/alerts/oncall-policy", response_model=OnCallPolicyCollection)
    def oncall_policy() -> OnCallPolicyCollection:
        return svc().get_oncall_policy()

    @app.get("/api/alerts/oncall/coverage", response_model=OnCallCoverageReport)
    def oncall_coverage(project_id: Optional[str] = Query(default=None, alias="projectId")) -> OnCallCoverageReport:
        return svc().build_oncall_coverage_report(project_id=project_id)

    @app.put("/api/alerts/oncall-policy", response_model=OnCallPolicyCollection)
    def update_oncall_policy(request: OnCallPolicyUpdateRequest, _: None = Depends(require_alert_preset_write)) -> OnCallPolicyCollection:
        try:
            return svc().update_oncall_policy(request)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/connectors/failures", response_model=ConnectorFailureReport)
    def connector_failures(project_id: Optional[str] = Query(default=None, alias="projectId")) -> ConnectorFailureReport:
        return svc().build_connector_failure_report(project_id=project_id)

    @app.post("/api/connectors/retry", response_model=ConnectorRetryResult)
    def retry_connectors(request: ConnectorRetryRequest, _: None = Depends(require_api_key)) -> ConnectorRetryResult:
        return svc().retry_connectors(request)

    @app.get("/api/connectors/retry/history", response_model=ConnectorRetryHistoryReport)
    def connector_retry_history(
        limit: int = Query(default=10, ge=1, le=100),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> ConnectorRetryHistoryReport:
        return svc().get_connector_retry_history(limit=limit, project_id=project_id)

    @app.get("/api/connectors/bulk-actions/history", response_model=BulkConnectorActionHistoryReport)
    def connector_bulk_action_history(
        limit: int = Query(default=20, ge=1, le=100),
        action: Optional[Literal["blocking", "strict_gap"]] = None,
        provider: Optional[str] = None,
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> BulkConnectorActionHistoryReport:
        return svc().get_bulk_connector_action_history(limit=limit, action=action, provider=provider, project_id=project_id)

    @app.get("/api/projects/{project_id}/connections/history", response_model=ProjectConnectionHistoryReport)
    def project_connection_history(
        project_id: str,
        limit: int = 20,
        provider: Optional[ConnectorKind] = None,
        status: Optional[str] = None,
        action: Optional[str] = None,
    ) -> ProjectConnectionHistoryReport:
        normalized_action = str(action or "").strip()
        if normalized_action and normalized_action not in {"connector.probe", "connector.refreshed"}:
            raise HTTPException(status_code=422, detail="Invalid action filter")
        try:
            return svc().get_project_connection_history(
                project_id,
                limit=limit,
                provider=provider,
                status=status,
                action=normalized_action or None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/projects/{project_id}/connections/evidence", response_model=ProjectConnectionEvidenceReport)
    def project_connection_evidence(project_id: str) -> ProjectConnectionEvidenceReport:
        try:
            return svc().get_project_connection_evidence(project_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/connectors/history", response_model=WorkspaceConnectionHistoryReport)
    def workspace_connection_history(
        limit: int = 20,
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        provider: Optional[ConnectorKind] = None,
        status: Optional[str] = None,
        action: Optional[str] = None,
    ) -> WorkspaceConnectionHistoryReport:
        normalized_action = str(action or "").strip()
        if normalized_action and normalized_action not in {"connector.probe", "connector.refreshed"}:
            raise HTTPException(status_code=422, detail="Invalid action filter")
        return svc().get_workspace_connection_history(
            limit=limit,
            project_id=project_id,
            provider=provider,
            status=status,
            action=normalized_action or None,
        )

    @app.get("/api/connectors/evidence", response_model=WorkspaceConnectionEvidenceReport)
    def workspace_connection_evidence(
        provider: Optional[ConnectorKind] = None,
        mode: Optional[str] = None,
        strict_only: bool = Query(False, alias="strictOnly"),
        limit: int = Query(500, ge=1, le=2000),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
    ) -> WorkspaceConnectionEvidenceReport:
        normalized_mode = mode.strip().lower() if isinstance(mode, str) and mode.strip() else None
        if normalized_mode not in {None, "real", "fallback", "unconfigured"}:
            raise HTTPException(status_code=422, detail="Invalid mode filter")
        evidence_mode: Optional[Literal["real", "fallback", "unconfigured"]] = (
            normalized_mode if normalized_mode is not None else None
        )
        return svc().get_workspace_connection_evidence(
            provider=provider,
            mode=evidence_mode,
            strict_only=strict_only,
            limit=limit,
            project_id=project_id,
        )

    @app.get("/api/connectors/remediations", response_model=ConnectorRemediationReport)
    def connector_remediations(
        blocking: Optional[bool] = None,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        provider: Optional[str] = None,
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        limit: Optional[int] = Query(default=None, ge=1, le=500),
    ) -> ConnectorRemediationReport:
        normalized_severity = str(severity or "").strip().lower() or None
        if normalized_severity not in {None, "critical", "warning", "info"}:
            raise HTTPException(status_code=422, detail="Invalid severity filter")
        normalized_category = str(category or "").strip().lower() or None
        if normalized_category not in {None, "auth", "permission", "rate_limit", "network", "validation", "config", "unavailable", "other"}:
            raise HTTPException(status_code=422, detail="Invalid category filter")
        return svc().build_connector_remediation_report(
            blocking=blocking,
            severity=normalized_severity,  # type: ignore[arg-type]
            category=normalized_category,  # type: ignore[arg-type]
            provider=provider,
            project_id=project_id,
            limit=limit,
        )

    @app.post("/api/worker/run-once", response_model=WorkerRunOnceResult)
    def worker_once(request: Optional[WorkerRunOnceRequest] = None, _: None = Depends(require_api_key)) -> WorkerRunOnceResult:
        return svc().run_worker_once(request)

    @app.get("/api/worker/queue/health", response_model=WorkerQueueHealthReport)
    def worker_queue_health() -> WorkerQueueHealthReport:
        return svc().get_worker_queue_health()

    @app.get("/api/worker/service/health", response_model=WorkerServiceHealthReport)
    def worker_service_health() -> WorkerServiceHealthReport:
        return svc().get_worker_service_health()

    @app.get("/api/worker/executions", response_model=WorkerExecutionHistoryReport)
    def worker_execution_history(
        limit: int = Query(default=20, ge=1, le=500),
        project_id: Optional[str] = Query(default=None, alias="projectId"),
        stage: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
        action: Optional[str] = Query(default=None),
    ) -> WorkerExecutionHistoryReport:
        normalized_status = str(status or "").strip().lower() or None
        if normalized_status not in {None, "queued", "completed", "failed", "requeued", "skipped_duplicate"}:
            raise HTTPException(status_code=422, detail="Invalid worker status filter")
        return svc().get_worker_execution_history(
            limit=limit,
            project_id=project_id,
            stage=stage,
            status=normalized_status,
            action=action,
        )

    @app.get("/api/observability/status", response_model=ObservabilityStatusReport)
    def observability_status() -> ObservabilityStatusReport:
        return svc().get_observability_status()

    return app


# Lazy app creation to avoid import-time database connections
_app = None

def get_app():
    global _app
    if _app is None:
        _app = create_app()
    return _app

app = get_app()
