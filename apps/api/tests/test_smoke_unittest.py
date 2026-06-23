import argparse
import base64
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from apps.api.seo_ad_autopilot.analysis import Coordinator
from apps.api.seo_ad_autopilot.app import create_app
from apps.api.seo_ad_autopilot.connectors import (
    AdNetworkAdapter,
    CmsAdapter,
    ConnectorContext,
    GitHubAdapter,
    ScriptApiAdapter,
)
from apps.api.seo_ad_autopilot.db import AlertSnapshotRow, AuditRow, Database, ProjectStateRow, TaskRow
from apps.api.seo_ad_autopilot.artifact_store import get_artifact_store
from apps.api.seo_ad_autopilot.config import get_settings
from apps.api.seo_ad_autopilot import observability
from apps.api.seo_ad_autopilot import worker as worker_module
from apps.worker import main as worker_service_module
from apps.api.seo_ad_autopilot.crawler import (
    _browser_proxies,
    _classify_crawl_error,
    _extract_block_signals_from_text,
    _select_proxy,
    _has_alternative_browser_fingerprint,
)
from apps.api.seo_ad_autopilot.queueing import RedisJobQueue, WorkerJob, build_job_queue
from apps.api.seo_ad_autopilot.models import (
    ApprovalDecisionRequest,
    ApprovalStatus,
    BulkBlockingRefreshRequest,
    BulkProjectConnectionsRefreshRequest,
    BulkMarketEvidenceRefreshRequest,
    BulkStrictGapRefreshRequest,
    ConnectorFailureEntry,
    ConnectorFailureReport,
    ConnectorKind,
    ConnectorRetryRequest,
    ConnectorStatus,
    DeploymentActionRequest,
    DeploymentRecord,
    IngestionReport,
    DeploymentMode,
    MetricSnapshot,
    MarketEvidenceReport,
    ProjectCruiseHealthReport,
    WorkspaceCruiseHealthReport,
    WorkspaceMarketEvidenceHealthReport,
    ProjectConnection,
    ProjectConnectionsUpdateRequest,
    CrawlDiagnosticsReport,
    PagePerformanceBudget,
    PageSnapshot,
    VisualRegressionCase,
    VisualRegressionRun,
    VisualRegressionRunExecuteRequest,
    VisualRegressionRunsReport,
    VisualFarmStatusReport,
    VisualFarmGatewayPolicyUpdateRequest,
    VisualFarmGatewayRoute,
    VisualFarmGatewayExportReport,
    VisualRegressionRetryRequest,
    WorkspaceBillingPolicy,
    WorkspaceBillingReport,
    WorkspaceBillingSettlement,
    WorkspaceBillingSettlementGatewayExportReport,
    WorkspaceConnectionEvidenceEntry,
    WorkspaceConnectionEvidenceReport,
    WorkspaceBillingUsage,
    WorkerRunOnceRequest,
    WorkerRunOnceResult,
    WorkerJobStatus,
    ProjectCreateRequest,
    RollbackActionRequest,
    RuntimeEdgeRolloutExecuteRequest,
    RuntimeEdgeDeploymentRequest,
    RuntimeEdgeDeploymentBatchRequest,
    RuntimeIngressBundleBatchRequest,
    RuntimeEdgeProbeRequest,
    RuntimeRouteRequest,
    SiteIntake,
    SourceEvidence,
    VisualFarmDeploymentRequest,
    VisualFarmDeploymentBatchRequest,
    VisualFarmDeploymentBatchEnqueueResult,
    WorkspaceBillingPolicyUpdateRequest,
    WorkspaceBillingSettlementExecutionRequest,
    WorkspaceBillingSettlementExecutionBatchRequest,
    WorkflowStage,
    RunTrigger,
    RunStatus,
)
from apps.api.seo_ad_autopilot.service import WorkflowService
from apps.api.seo_ad_autopilot.skill_registry import SkillRegistry, get_skill_registry


class SmokeWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self._env_backup = dict(os.environ)
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(self._tempdir.name) / 'autopilot.db'}"
        os.environ["SEO_AD_BOT_STATE_DIR"] = str(Path(self._tempdir.name) / "state")
        os.environ["SEO_AD_BOT_SKILL_REGISTRY_PATH"] = str(Path("packages/skill-registry/registry.json").resolve())
        os.environ["SEO_AD_BOT_WEB_ORIGIN"] = "http://testserver"
        get_settings.cache_clear()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env_backup)
        get_settings.cache_clear()

    def _service(self) -> WorkflowService:
        from apps.api.seo_ad_autopilot.config import Settings

        settings = Settings()
        registry = SkillRegistry.load(settings.skill_registry_path)
        service = WorkflowService(settings=settings, registry=registry)
        service.database.create_all()
        return service

    def test_coordinator_builds_preview_bundle(self) -> None:
        intake = SiteIntake(
            url="https://northstar-media.example",
            site_name="Northstar Media",
            repo_url="https://github.com/example/northstar-media",
            brand_whitelist=["Northstar"],
            keywords=["editorial", "insights"],
        )
        bundle = Coordinator(get_skill_registry()).run("task_001", intake, site_id="site_001")

        self.assertEqual(bundle.project.project_id, "site_001")
        self.assertEqual(bundle.task.status.value, "awaiting_approval")
        self.assertLess(bundle.plan.risk_score, 80)
        self.assertEqual(bundle.deployment.status, "failed")
        self.assertTrue(bundle.deployment.fallback_reason)
        self.assertTrue(bundle.deployment.failure_code)
        self.assertGreater(bundle.preview.performance_budget["estimatedLcpMs"], bundle.preview.performance_budget["baselineLcpMs"])

    def test_high_risk_site_blocks_ads(self) -> None:
        intake = SiteIntake(
            url="https://trust-clinic.example",
            site_name="Trust Clinic",
            cms_name="drupal",
            keywords=["medical guidance", "patient resources"],
        )
        bundle = Coordinator(get_skill_registry()).run("task_002", intake, site_id="site_002")

        self.assertEqual(bundle.opportunity_set.ad[0].title, "Do not recommend ads")
        self.assertGreaterEqual(bundle.plan.risk_score, 80)
        self.assertEqual(bundle.deployment.status, "blocked")
        self.assertTrue(bundle.plan.requires_manual_approval)

    def test_ad_audit_report_includes_negative_conditions(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Trust Clinic",
                intake=SiteIntake(
                    url="https://trust-clinic.example",
                    site_name="Trust Clinic",
                    cms_name="drupal",
                    keywords=["medical guidance", "patient resources"],
                ),
            )
        )
        service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://trust-clinic.example",
                site_name="Trust Clinic",
                cms_name="drupal",
                keywords=["medical guidance", "patient resources"],
            ),
        )
        report = service.build_ad_audit_report(project.project_id)

        self.assertFalse(report.ad_allowed)
        self.assertGreaterEqual(len(report.negative_conditions), 1)
        self.assertTrue(any("ad-free" in item.lower() or "trust-sensitive" in item.lower() for item in report.negative_conditions))
        self.assertTrue(report.recommendations)
        self.assertGreaterEqual(len(report.recommendations[0].negative_conditions), 1)

    def test_ad_audit_report_exposes_revenue_metrics_from_connector(self) -> None:
        service = self._service()
        intake = SiteIntake(
            url="https://northstar-media.example",
            site_name="Northstar Media",
            repo_url="https://github.com/example/northstar-media",
            brand_whitelist=["Northstar"],
        )
        project = service.create_project(
            ProjectCreateRequest(
                name="Northstar Media",
                intake=intake,
            )
        )
        service.run_analysis(project.project_id, intake)
        with service.database.session() as session:
            connections = service._load_project_connections(session, project.project_id, intake)
            ad_connection = next(item for item in connections if item.provider == ConnectorKind.ad_network)
            ad_connection.status = ConnectorStatus.connected
            ad_connection.details.update(
                {
                    "providerFamily": "mediavine",
                    "providerName": "Mediavine",
                    "providerRef": "network-demo",
                    "inventoryStatus": "ready",
                    "impressions": 7200,
                    "clicks": 86,
                    "ctr": 0.0119,
                    "fillRate": 0.64,
                    "rpm": 4.6,
                    "estimatedRevenueDaily": 21.2,
                    "settledRevenueDaily": 19.4,
                    "settlementWindow": "T+7 net",
                    "settlementCurrency": "USD",
                    "policyTier": "managed",
                    "payoutThreshold": 25.0,
                    "geoCoverage": ["US", "CA", "AU"],
                    "providerProgram": "managed-service",
                }
            )
            service._persist_project_connections(session, project.project_id, connections)
        report = service.build_ad_audit_report(project.project_id)

        self.assertEqual(report.ad_provider_family, "mediavine")
        self.assertEqual(report.ad_provider_name, "Mediavine")
        self.assertEqual(report.ad_provider_ref, "network-demo")
        self.assertEqual(report.ad_inventory_status, "ready")
        self.assertEqual(report.ad_impressions_daily, 7200)
        self.assertEqual(report.ad_clicks_daily, 86)
        self.assertAlmostEqual(report.ad_ctr or 0, 0.0119, places=4)
        self.assertAlmostEqual(report.ad_fill_rate or 0, 0.64, places=2)
        self.assertAlmostEqual(report.ad_rpm or 0, 4.6, places=2)
        self.assertAlmostEqual(report.ad_revenue_estimate_daily or 0, 21.2, places=2)
        self.assertAlmostEqual(report.ad_revenue_settled_daily or 0, 19.4, places=2)
        self.assertEqual(report.ad_revenue_settlement_window, "T+7 net")
        self.assertEqual(report.ad_revenue_currency, "USD")
        self.assertEqual(report.ad_policy_tier, "managed")
        self.assertAlmostEqual(report.ad_payout_threshold or 0, 25.0, places=2)
        self.assertEqual(report.ad_geo_coverage, ["US", "CA", "AU"])
        self.assertEqual(report.ad_provider_program, "managed-service")

    def test_workspace_ad_audit_history_api_and_dashboard(self) -> None:
        service = self._service()
        connected_intake = SiteIntake(
            url="https://northstar-media.example",
            site_name="Northstar Media",
            repo_url="https://github.com/example/northstar-media",
            brand_whitelist=["Northstar"],
        )
        connected_project = service.create_project(
            ProjectCreateRequest(
                name="Northstar Media",
                intake=connected_intake,
            )
        )
        service.run_analysis(connected_project.project_id, connected_intake)
        with service.database.session() as session:
            connections = service._load_project_connections(session, connected_project.project_id, connected_intake)
            ad_connection = next(item for item in connections if item.provider == ConnectorKind.ad_network)
            ad_connection.status = ConnectorStatus.connected
            ad_connection.details.update(
                {
                    "providerFamily": "mediavine",
                    "providerName": "Mediavine",
                    "providerRef": "network-demo",
                    "inventoryStatus": "ready",
                    "estimatedRevenueDaily": 21.2,
                    "settledRevenueDaily": 19.4,
                    "settlementCurrency": "USD",
                    "policyTier": "managed",
                    "payoutThreshold": 25.0,
                    "geoCoverage": ["US", "CA", "AU"],
                    "providerProgram": "managed-service",
                }
            )
            service._persist_project_connections(session, connected_project.project_id, connections)
        blocked_project = service.create_project(
            ProjectCreateRequest(
                name="Trust Clinic",
                intake=SiteIntake(
                    url="https://trust-clinic.example",
                    site_name="Trust Clinic",
                    cms_name="drupal",
                    keywords=["medical guidance", "patient resources"],
                ),
            )
        )
        service.run_analysis(
            blocked_project.project_id,
            SiteIntake(
                url="https://trust-clinic.example",
                site_name="Trust Clinic",
                cms_name="drupal",
                keywords=["medical guidance", "patient resources"],
            ),
        )
        app = create_app(service)

        with TestClient(app) as client:
            history = client.get("/api/ad-audit/history?limit=5")
            self.assertEqual(history.status_code, 200)
            history_payload = history.json()
            self.assertGreaterEqual(history_payload["total"], 2)
            self.assertGreaterEqual(history_payload["projectCount"], 2)
            self.assertIn("allowedCount", history_payload)
            self.assertIn("blockedCount", history_payload)
            self.assertTrue(history_payload["entries"])
            self.assertTrue(all("recommendationCount" in entry for entry in history_payload["entries"]))

            filtered_history = client.get(f"/api/ad-audit/history?limit=5&projectId={connected_project.project_id}")
            self.assertEqual(filtered_history.status_code, 200)
            filtered_history_payload = filtered_history.json()
            self.assertTrue(filtered_history_payload["entries"])
            self.assertTrue(all(entry["projectId"] == connected_project.project_id for entry in filtered_history_payload["entries"]))
            self.assertTrue(all(entry["projectName"] == connected_project.name for entry in filtered_history_payload["entries"]))

            overview = client.get("/api/overview")
            self.assertEqual(overview.status_code, 200)
            overview_payload = overview.json()
            self.assertIn("adAuditHistory", overview_payload)
            self.assertIn("marketEvidenceProviders", overview_payload)
            self.assertIn("runtimeIngressBatchHistory", overview_payload)
            self.assertIn("runtimeIngressBatchHealth", overview_payload)
            self.assertIn("visualFarmDeploymentBatchHistory", overview_payload)
            self.assertGreaterEqual(overview_payload["adAuditHistory"]["total"], 2)
            self.assertIn("entries", overview_payload["marketEvidenceProviders"])
            self.assertTrue({"trend", "news", "qa"}.issubset({entry["provider"] for entry in overview_payload["marketEvidenceProviders"]["entries"]}))

            overview_project = client.get(f"/api/overview?projectId={connected_project.project_id}")
            self.assertEqual(overview_project.status_code, 200)
            overview_project_payload = overview_project.json()
            self.assertEqual(overview_project_payload["projectId"], connected_project.project_id)
            self.assertEqual(len(overview_project_payload["projects"]), 1)
            self.assertTrue(all(item["projectId"] == connected_project.project_id for item in overview_project_payload["tasks"]))
            self.assertEqual(overview_project_payload["connectorsHealth"]["projectId"], connected_project.project_id)
            self.assertEqual(overview_project_payload["marketEvidenceHealth"]["projectId"], connected_project.project_id)
            self.assertEqual(overview_project_payload["cruiseHealth"]["projectId"], connected_project.project_id)
            self.assertEqual(overview_project_payload["adAuditHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(overview_project_payload["billingSettlementHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(overview_project_payload["billingGatewayHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(overview_project_payload["modelGatewayHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(overview_project_payload["runtimeIngressBatchHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(overview_project_payload["runtimeIngressBatchHealth"]["projectId"], connected_project.project_id)
            self.assertEqual(overview_project_payload["visualFarmDeploymentBatchHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(overview_project_payload["crawlDiagnosticsHistory"]["projectId"], connected_project.project_id)
            self.assertIn("marketEvidenceProviders", overview_project_payload)

            overview_missing = client.get("/api/overview?projectId=project_missing")
            self.assertEqual(overview_missing.status_code, 404)

            project_detail = client.get(f"/api/projects/{connected_project.project_id}")
            self.assertEqual(project_detail.status_code, 200)
            project_detail_payload = project_detail.json()
            self.assertEqual(project_detail_payload["connectorsHealth"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["marketEvidenceHealth"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["cruiseHealth"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["billing"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["billingGatewayHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["modelGateway"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["modelGatewayHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["runtimeEdgeConfig"]["projectId"], connected_project.project_id)
            self.assertTrue(project_detail_payload["alerts"])
            self.assertEqual(project_detail_payload["alertHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["alertDeliveries"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["alertEmitStatus"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["crawlDiagnosticsHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["connectorHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["connectorFailures"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["runtimeRouteHistory"]["projectId"], connected_project.project_id)
            self.assertTrue(project_detail_payload["runtimeRouteHistory"]["entries"])
            self.assertEqual(project_detail_payload["visualRegressionRuns"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["visualRegressionHealth"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["visualRegressionRemediation"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["visualFarmStatus"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["visualFarmProbeHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["visualFarmDeploymentBatchHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["runtimeIngressBatchHistory"]["projectId"], connected_project.project_id)
            self.assertEqual(project_detail_payload["runtimeIngressBatchHealth"]["projectId"], connected_project.project_id)
            self.assertTrue(project_detail_payload["deploymentHistory"])
            self.assertIsInstance(project_detail_payload["rollbackHistory"], list)
            self.assertTrue(all(item["projectId"] == connected_project.project_id for item in project_detail_payload["deploymentHistory"]))
            self.assertTrue(all(item["projectId"] == connected_project.project_id for item in project_detail_payload["rollbackHistory"]))

    def test_ad_network_adapter_normalizes_provider_specific_payloads(self) -> None:
        intake = SiteIntake(url="https://publisher.example", site_name="Publisher")
        connection = ProjectConnection(
            connection_id="conn_ad_1",
            provider=ConnectorKind.ad_network,
            label="Ad Network",
            enabled=True,
            status=ConnectorStatus.synthetic,
            config={
                "endpoint": "https://ad-provider.example/api",
                "accountId": "acct-123",
                "accessToken": "token-123",
                "providerFamily": "mediavine",
            },
        )
        adapter = AdNetworkAdapter()
        with patch(
            "apps.api.seo_ad_autopilot.connectors._http_json",
            return_value={
                "provider": "mediavine",
                "providerName": "Mediavine",
                "id": "mv-demo",
                "inventoryStatus": "managed",
                "pageviews": 18300,
                "adClicks": 211,
                "matchedRate": 0.73,
                "sessionRpm": 12.4,
                "grossRevenueDaily": 166.8,
                "publisherRevenueDaily": 151.2,
                "settlementCadence": "NET45",
                "currency": "USD",
                "policyTier": "managed",
                "minimumPayout": 100,
                "regions": ["US", "GB", "CA"],
                "program": "managed-service",
            },
        ):
            project_connection, evidence = adapter.probe(
                ConnectorContext(project_id="project_1", task_id="task_1", intake=intake, connection=connection)
            )

        self.assertEqual(project_connection.status, ConnectorStatus.connected)
        self.assertEqual(project_connection.details.get("providerFamily"), "mediavine")
        self.assertEqual(project_connection.details.get("providerName"), "Mediavine")
        self.assertEqual(project_connection.details.get("providerRef"), "mv-demo")
        self.assertEqual(project_connection.details.get("settlementCurrency"), "USD")
        self.assertEqual(project_connection.details.get("policyTier"), "managed")
        self.assertEqual(project_connection.details.get("payoutThreshold"), 100.0)
        self.assertEqual(project_connection.details.get("geoCoverage"), ["US", "GB", "CA"])
        self.assertEqual(project_connection.details.get("providerProgram"), "managed-service")
        self.assertEqual(project_connection.details.get("impressions"), 18300)
        self.assertEqual(project_connection.details.get("clicks"), 211)
        self.assertAlmostEqual(float(project_connection.details.get("rpm") or 0), 12.4, places=2)
        self.assertAlmostEqual(float(project_connection.details.get("fillRate") or 0), 0.73, places=2)
        self.assertAlmostEqual(float(project_connection.details.get("estimatedRevenueDaily") or 0), 166.8, places=2)
        self.assertAlmostEqual(float(project_connection.details.get("settledRevenueDaily") or 0), 151.2, places=2)
        self.assertEqual(project_connection.details.get("settlementWindow"), "NET45")
        self.assertIn("Mediavine", evidence.summary)

    def test_ad_network_adapter_normalizes_broader_provider_families(self) -> None:
        adapter = AdNetworkAdapter()
        self.assertEqual(adapter._normalize_provider_family("PubMatic"), "pubmatic")
        self.assertEqual(adapter._normalize_provider_family("Seedtag"), "seedtag")
        self.assertEqual(adapter._normalize_provider_family("GumGum"), "gumgum")
        self.assertEqual(adapter._normalize_provider_family("Sharethrough"), "sharethrough")
        self.assertEqual(adapter._normalize_provider_family("Teads"), "teads")
        self.assertEqual(adapter._normalize_provider_family("Index Exchange"), "index_exchange")
        self.assertEqual(adapter._normalize_provider_family("TripleLift"), "triplelift")
        self.assertEqual(adapter._provider_display_name("pubmatic"), "PubMatic")
        self.assertEqual(adapter._provider_display_name("gumgum"), "GumGum")
        self.assertEqual(adapter._provider_display_name("index_exchange"), "Index Exchange")
        self.assertIn("native_in_feed", adapter._provider_slots("gumgum"))
        self.assertIn("sidebar", adapter._provider_slots("pubmatic"))
        self.assertIn("video_anchor", adapter._provider_slots("teads"))
        self.assertIn("inline_after_content", adapter._provider_slots("triplelift"))
        self.assertIn("adhesion_footer", adapter._provider_slots("undertone"))

    def test_ad_network_adapter_supports_credentials_json_auth_header(self) -> None:
        intake = SiteIntake(url="https://publisher.example", site_name="Publisher")
        connection = ProjectConnection(
            connection_id="conn_ad_2",
            provider=ConnectorKind.ad_network,
            label="Ad Network",
            enabled=True,
            status=ConnectorStatus.synthetic,
            config={
                "endpoint": "https://ad-provider.example/api",
                "accountId": "acct-123",
                "credentialsJson": json.dumps({"accessToken": "ad-json-token", "authHeader": "X-Ad-Token"}),
                "providerFamily": "generic",
            },
        )
        adapter = AdNetworkAdapter()
        captured_headers: dict[str, str] = {}

        def _mock_http_json(  # type: ignore[no-untyped-def]
            url: str,
            *,
            method: str = "GET",
            headers: Optional[dict[str, str]] = None,
            payload: Optional[dict[str, object]] = None,
            timeout: int = 10,
        ) -> dict[str, object]:
            del url, method, payload, timeout
            captured_headers.update(headers or {})
            return {
                "provider": "generic",
                "providerName": "Ad Network",
                "id": "ad-demo-2",
                "inventoryStatus": "ready",
                "dailyImpressions": 1200,
                "dailyClicks": 22,
                "fillRate": 0.64,
                "rpm": 3.4,
                "dailyRevenue": 9.8,
                "settledRevenueDaily": 8.1,
            }

        with patch("apps.api.seo_ad_autopilot.connectors._http_json", side_effect=_mock_http_json):
            project_connection, evidence = adapter.probe(
                ConnectorContext(project_id="project_1", task_id="task_1", intake=intake, connection=connection)
            )

        self.assertEqual(project_connection.status, ConnectorStatus.connected)
        self.assertEqual(project_connection.details.get("authSource"), "config:json")
        self.assertEqual(project_connection.details.get("authHeader"), "X-Ad-Token")
        self.assertEqual(captured_headers.get("X-Ad-Token"), "Bearer ad-json-token")
        self.assertNotIn("Authorization", captured_headers)
        self.assertEqual(evidence.auth_source, "config:json")

    def test_ad_network_refresh_uses_backup_endpoint_when_primary_fails(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Ad Network Multi Endpoint",
                intake=SiteIntake(
                    url="https://ad-network-multi-endpoint.example",
                    site_name="Ad Network Multi Endpoint",
                    approval_rules={
                        "adNetworkProviderUrls": [
                            "https://ad-provider-primary.example/api",
                            "https://ad-provider-secondary.example/api",
                        ],
                        "adNetworkAccessToken": "ad-token",
                        "adNetworkAccountId": "acct_987",
                        "adNetworkProviderTimeoutMs": 9000,
                    },
                ),
            )
        )
        call_log: list[tuple[str, int]] = []

        def _mock_http_json(  # type: ignore[no-untyped-def]
            url: str,
            *,
            method: str = "GET",
            headers: Optional[dict[str, str]] = None,
            payload: Optional[dict[str, object]] = None,
            timeout: int = 10,
        ) -> dict[str, object]:
            del method, headers, payload
            call_log.append((url, timeout))
            if "primary" in url:
                raise HTTPError(url=url, code=503, msg="upstream unavailable", hdrs=None, fp=None)
            return {
                "provider": "adsense",
                "providerName": "Google AdSense",
                "id": "adsense_001",
                "inventoryStatus": "ready",
                "dailyImpressions": 2000,
                "dailyClicks": 34,
                "fillRate": 0.66,
                "rpm": 5.1,
                "dailyRevenue": 12.7,
                "settledRevenueDaily": 10.8,
            }

        with patch("apps.api.seo_ad_autopilot.connectors._http_json", side_effect=_mock_http_json):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.ad_network)

        self.assertEqual(refreshed.status, ConnectorStatus.connected)
        self.assertEqual(refreshed.connection.details.get("endpoint"), "https://ad-provider-secondary.example/api")
        self.assertEqual(refreshed.connection.details.get("timeoutMs"), 9000)
        self.assertEqual(len(refreshed.connection.details.get("endpointsTried", [])), 2)
        endpoint_attempts = refreshed.connection.details.get("endpointAttempts", [])
        self.assertEqual(endpoint_attempts[0].get("status"), "error")
        self.assertEqual(endpoint_attempts[1].get("status"), "connected")
        self.assertEqual(call_log[0], ("https://ad-provider-primary.example/api", 9))
        self.assertEqual(call_log[1], ("https://ad-provider-secondary.example/api", 9))

    def test_github_adapter_supports_credentials_json_auth_header(self) -> None:
        intake = SiteIntake(url="https://repo.example", site_name="Repo", repo_url="https://github.com/example/repo")
        connection = ProjectConnection(
            connection_id="conn_gh_1",
            provider=ConnectorKind.github,
            label="GitHub",
            enabled=True,
            status=ConnectorStatus.synthetic,
            config={
                "repoUrl": "https://github.com/example/repo",
                "owner": "example",
                "repo": "repo",
                "headBranch": "autopilot/preview",
                "apiEndpoint": "https://github.example/api/pulls",
                "credentialsJson": json.dumps({"accessToken": "gh-json-token", "authHeader": "X-GH-Token"}),
            },
        )
        adapter = GitHubAdapter()
        captured_headers: dict[str, str] = {}

        def _mock_http_json(  # type: ignore[no-untyped-def]
            url: str,
            *,
            method: str = "GET",
            headers: Optional[dict[str, str]] = None,
            payload: Optional[dict[str, object]] = None,
            timeout: int = 10,
        ) -> dict[str, object]:
            del url, method, payload, timeout
            captured_headers.update(headers or {})
            return {"number": 11, "html_url": "https://github.com/example/repo/pull/11"}

        with patch("apps.api.seo_ad_autopilot.connectors._http_json", side_effect=_mock_http_json):
            project_connection, evidence = adapter.probe(
                ConnectorContext(project_id="project_1", task_id="task_1", intake=intake, connection=connection)
            )

        self.assertEqual(project_connection.status, ConnectorStatus.connected)
        self.assertEqual(project_connection.details.get("authSource"), "config:json")
        self.assertEqual(project_connection.details.get("authHeader"), "X-GH-Token")
        self.assertEqual(captured_headers.get("X-GH-Token"), "Bearer gh-json-token")
        self.assertNotIn("Authorization", captured_headers)
        self.assertEqual(evidence.auth_source, "config:json")

    def test_cms_adapter_supports_credentials_json_auth_header(self) -> None:
        intake = SiteIntake(url="https://cms.example", site_name="CMS", cms_name="contentful")
        connection = ProjectConnection(
            connection_id="conn_cms_1",
            provider=ConnectorKind.cms,
            label="CMS",
            enabled=True,
            status=ConnectorStatus.synthetic,
            config={
                "cmsName": "contentful",
                "draftEndpoint": "https://cms.example/api/drafts",
                "credentialsJson": json.dumps({"accessToken": "cms-json-token", "authHeader": "X-CMS-Token"}),
            },
        )
        adapter = CmsAdapter()
        captured_headers: dict[str, str] = {}

        def _mock_http_json(  # type: ignore[no-untyped-def]
            url: str,
            *,
            method: str = "GET",
            headers: Optional[dict[str, str]] = None,
            payload: Optional[dict[str, object]] = None,
            timeout: int = 10,
        ) -> dict[str, object]:
            del url, method, payload, timeout
            captured_headers.update(headers or {})
            return {"draftId": "cms-draft-11"}

        with patch("apps.api.seo_ad_autopilot.connectors._http_json", side_effect=_mock_http_json):
            project_connection, evidence = adapter.probe(
                ConnectorContext(project_id="project_1", task_id="task_1", intake=intake, connection=connection)
            )

        self.assertEqual(project_connection.status, ConnectorStatus.connected)
        self.assertEqual(project_connection.details.get("authSource"), "config:json")
        self.assertEqual(project_connection.details.get("authHeader"), "X-CMS-Token")
        self.assertEqual(captured_headers.get("X-CMS-Token"), "Bearer cms-json-token")
        self.assertNotIn("Authorization", captured_headers)
        self.assertEqual(evidence.auth_source, "config:json")

    def test_script_adapter_supports_credentials_json_auth_header(self) -> None:
        intake = SiteIntake(url="https://script.example", site_name="Script")
        connection = ProjectConnection(
            connection_id="conn_script_1",
            provider=ConnectorKind.script_api,
            label="Script API",
            enabled=True,
            status=ConnectorStatus.synthetic,
            config={
                "scriptEndpoint": "https://script.example/api/health",
                "credentialsJson": json.dumps({"accessToken": "script-json-token", "authHeader": "X-Script-Token"}),
            },
        )
        adapter = ScriptApiAdapter()
        captured_headers: dict[str, str] = {}

        def _mock_http_json(  # type: ignore[no-untyped-def]
            url: str,
            *,
            method: str = "GET",
            headers: Optional[dict[str, str]] = None,
            payload: Optional[dict[str, object]] = None,
            timeout: int = 10,
        ) -> dict[str, object]:
            del url, method, payload, timeout
            captured_headers.update(headers or {})
            return {"providerRef": "script-provider-1", "health": "ok"}

        with patch("apps.api.seo_ad_autopilot.connectors._http_json", side_effect=_mock_http_json):
            project_connection, evidence = adapter.probe(
                ConnectorContext(project_id="project_1", task_id="task_1", intake=intake, connection=connection)
            )

        self.assertEqual(project_connection.status, ConnectorStatus.connected)
        self.assertEqual(project_connection.details.get("authSource"), "config:json")
        self.assertEqual(project_connection.details.get("authHeader"), "X-Script-Token")
        self.assertEqual(captured_headers.get("X-Script-Token"), "Bearer script-json-token")
        self.assertNotIn("Authorization", captured_headers)
        self.assertEqual(evidence.auth_source, "config:json")

    def test_default_connections_accept_env_credentials_json_for_github_cms_script(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_GITHUB_CREDENTIALS_JSON": json.dumps({"accessToken": "gh-env-token"}),
                "SEO_AD_BOT_CMS_PROVIDER_URL": "https://cms.example/api/drafts",
                "SEO_AD_BOT_CMS_CREDENTIALS_JSON": json.dumps({"accessToken": "cms-env-token"}),
                "SEO_AD_BOT_SCRIPT_PROVIDER_URL": "https://script.example/api",
                "SEO_AD_BOT_SCRIPT_CREDENTIALS_JSON": json.dumps({"accessToken": "script-env-token"}),
            },
            clear=False,
        ):
            service = self._service()
            project = service.create_project(
                ProjectCreateRequest(
                    name="Env JSON Connections",
                    intake=SiteIntake(
                        url="https://env-json-connections.example",
                        site_name="Env JSON Connections",
                        repo_url="https://github.com/example/env-json-connections",
                        cms_name="contentful",
                    ),
                )
            )
            connections = service.get_project_connections(project.project_id)
            by_provider = {item.provider: item for item in connections.connections}
            self.assertEqual(by_provider[ConnectorKind.github].status, ConnectorStatus.synthetic)
            self.assertEqual(by_provider[ConnectorKind.cms].status, ConnectorStatus.synthetic)
            self.assertEqual(by_provider[ConnectorKind.script_api].status, ConnectorStatus.synthetic)

    def test_market_evidence_generates_market_driven_seo_opportunities(self) -> None:
        intake = SiteIntake(
            url="https://signals.example",
            site_name="Signals",
            brand_whitelist=["Signals"],
            keywords=["seo automation", "content ops"],
        )
        ingestion = IngestionReport(
            report_id="ingest_market",
            project_id="site_market",
            status=ConnectorStatus.connected,
            evidence=[
                SourceEvidence(
                    provider=ConnectorKind.trend,
                    status=ConnectorStatus.connected,
                    summary="Trend provider returned live topics.",
                    source_type="trend",
                    source_ref="trend:signals",
                    details={"sample": {"topics": ["seo automation", "search workflow", "content ops"]}},
                ),
                SourceEvidence(
                    provider=ConnectorKind.news,
                    status=ConnectorStatus.connected,
                    summary="News provider returned headlines.",
                    source_type="news",
                    source_ref="news:signals",
                    details={"sample": {"headlines": ["Search ranking shifts", "Content freshness tactics"]}},
                ),
                SourceEvidence(
                    provider=ConnectorKind.qa,
                    status=ConnectorStatus.connected,
                    summary="QA provider returned common questions.",
                    source_type="qa",
                    source_ref="qa:signals",
                    details={"sample": {"questions": ["How to automate SEO?", "What is content decay?"]}},
                ),
            ],
        )

        bundle = Coordinator(get_skill_registry()).run("task_market", intake, site_id="site_market", ingestion_report=ingestion)
        seo_titles = {item.title for item in bundle.opportunity_set.seo}

        self.assertIn("Trend-led topic cluster sprint", seo_titles)
        self.assertIn("Freshness capture from live news signals", seo_titles)
        self.assertIn("Question-led FAQ and snippet expansion", seo_titles)

    def test_content_strategy_report_uses_market_evidence(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="SignalBoard",
                intake=SiteIntake(
                    url="https://signalboard.example",
                    site_name="SignalBoard",
                    brand_whitelist=["SignalBoard"],
                    keywords=["search demand", "seo operations"],
                ),
            )
        )
        market_evidence = [
            SourceEvidence(
                provider=ConnectorKind.trend,
                status=ConnectorStatus.connected,
                summary="Trend provider returned live topics.",
                source_type="trend",
                source_ref="trend:signalboard",
                details={"sample": {"topics": ["search demand", "seo operations"]}},
            ),
            SourceEvidence(
                provider=ConnectorKind.news,
                status=ConnectorStatus.connected,
                summary="News provider returned headlines.",
                source_type="news",
                source_ref="news:signalboard",
                details={"sample": {"headlines": ["SERP volatility update", "AI overview rollout"]}},
            ),
            SourceEvidence(
                provider=ConnectorKind.qa,
                status=ConnectorStatus.connected,
                summary="QA provider returned common questions.",
                source_type="qa",
                source_ref="qa:signalboard",
                details={"sample": {"questions": ["How do I detect demand shifts?", "What causes content decay?"]}},
            ),
        ]

        with patch.object(service, "_collect_market_evidence", return_value=market_evidence):
            service.run_analysis(
                project.project_id,
                SiteIntake(
                    url="https://signalboard.example",
                    site_name="SignalBoard",
                    brand_whitelist=["SignalBoard"],
                    keywords=["search demand", "seo operations"],
                ),
            )
        report = service.build_content_strategy_report(project.project_id)

        self.assertGreaterEqual(len(report.market_signals), 3)
        self.assertIn("search demand", [item.lower() for item in report.market_signals])
        self.assertTrue(any("Trend-led topic cluster sprint" in cluster.title for cluster in report.topic_clusters))
        self.assertTrue(any("Question-led FAQ and snippet expansion" in item.topic for item in report.calendar))
        self.assertTrue(any("Live trend, news, and question evidence" in note for note in report.notes))

    def test_service_and_api_round_trip(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Smoke",
                intake=SiteIntake(
                    url="https://smoke.example",
                    site_name="Smoke",
                    brand_whitelist=["Smoke"],
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://smoke.example",
                site_name="Smoke",
                brand_whitelist=["Smoke"],
            ),
        )

        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="test", note="release"),
        )
        rolled_back = service.rollback_task(bundle.task.task_id, RollbackActionRequest(actor="test", reason="cleanup"))

        self.assertEqual(approved.task.approval_status, ApprovalStatus.approved)
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "deployed")
        self.assertIsNotNone(approved.deployment.provider_artifact_id)
        self.assertIsNotNone(approved.deployment.writeback_target)
        self.assertIsNotNone(approved.deployment.writeback_auth_source)
        self.assertIsInstance(approved.deployment.writeback_attempts, list)
        self.assertIsInstance(approved.deployment.writeback_summary, dict)
        self.assertIn("provider", approved.deployment.writeback_summary)
        self.assertIn("successCount", approved.deployment.writeback_summary)
        self.assertIn("failedCount", approved.deployment.writeback_summary)
        self.assertIn("successfulEndpoints", approved.deployment.writeback_summary)
        self.assertIn("failedEndpoints", approved.deployment.writeback_summary)
        self.assertIn("averageLatencyMs", approved.deployment.writeback_summary)
        self.assertIn("requiredChecks", approved.deployment.patch_audit)
        self.assertIn("checks", approved.deployment.patch_audit)
        self.assertIn("beforeAfter", approved.deployment.patch_audit)
        self.assertIn("title", approved.deployment.patch_audit["beforeAfter"])
        self.assertIsNotNone(approved.deployment.patch_manifest_ref)
        self.assertIsNotNone(rolled_back.rollback_bundle)
        self.assertTrue(rolled_back.rollback_bundle.commands)

        app = create_app(service)
        with TestClient(app) as client:
            detail_response = client.get(f"/api/projects/{project.project_id}")
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.json()
        self.assertTrue(
            any(item.get("lastSuccessAt") or item.get("lastErrorAt") for item in detail_payload["connections"])
        )
        self.assertIn("recentEvidenceLabel", detail_payload["connections"][0])
        self.assertIn("recentEvidenceRef", detail_payload["connections"][0])
        self.assertIn("recentEvidenceAt", detail_payload["connections"][0])
        metric_snapshot = detail_payload["workflow"]["metricSnapshot"]
        self.assertIsNotNone(metric_snapshot)
        deployment_payload = detail_payload["workflow"]["deployment"]
        self.assertIn("writebackAuthSource", deployment_payload)
        self.assertIn("writebackAttempts", deployment_payload)
        self.assertIn("strictBlockers", deployment_payload)
        self.assertIn("successfulEndpoints", deployment_payload["writebackSummary"])
        self.assertIn("failedEndpoints", deployment_payload["writebackSummary"])
        self.assertIn("averageLatencyMs", deployment_payload["writebackSummary"])
        self.assertIn("strictMode", deployment_payload)
        self.assertIn("verifiedPatch", deployment_payload)
        self.assertIn("deploymentHistory", detail_payload)
        self.assertGreaterEqual(len(detail_payload["deploymentHistory"]), 1)
        self.assertIn("deployment", detail_payload["deploymentHistory"][0])
        self.assertIn("deploymentId", detail_payload["deploymentHistory"][0]["deployment"])
        self.assertIn("strictMode", detail_payload["deploymentHistory"][0]["deployment"])
        self.assertIn("verifiedPatch", detail_payload["deploymentHistory"][0]["deployment"])
        self.assertIn("taskStatus", detail_payload["deploymentHistory"][0])
        self.assertIn("approvalStatus", detail_payload["deploymentHistory"][0])
        self.assertIn("updatedAt", detail_payload["deploymentHistory"][0])
        self.assertIn("rollbackHistory", detail_payload)
        self.assertGreaterEqual(len(detail_payload["rollbackHistory"]), 1)
        self.assertIn("rollback", detail_payload["rollbackHistory"][0])
        self.assertIn("rollbackId", detail_payload["rollbackHistory"][0]["rollback"])
        self.assertIn("sourceStatus", metric_snapshot)
        self.assertIn("sourceMetricsSummary", metric_snapshot)
        self.assertGreaterEqual(len(metric_snapshot["sourceMetricsSummary"]), 1)
        self.assertIn("externalMetrics", metric_snapshot)
        self.assertIn("evidence", metric_snapshot)
        patch_payload = detail_payload["technicalSeoPatch"]
        self.assertIn("patchAudit", patch_payload)
        self.assertIn("beforeAfter", patch_payload["patchAudit"])

        with TestClient(app) as client:
            response = client.get("/api/overview")
            metrics_response = client.get(f"/api/projects/{project.project_id}/metrics", params={"limit": 5, "offset": 0})
            deployments_response = client.get(f"/api/projects/{project.project_id}/deployments")
            rollbacks_response = client.get(f"/api/projects/{project.project_id}/rollbacks")
            evidence_response = client.get(f"/api/projects/{project.project_id}/connections/evidence")
            market_health_response = client.get(f"/api/projects/{project.project_id}/market-evidence/health")
            cruise_health_response = client.get(f"/api/projects/{project.project_id}/cruise/health")
            workspace_evidence_response = client.get("/api/connectors/evidence")
            workspace_market_health_response = client.get("/api/market-evidence/health")
            workspace_market_health_project_response = client.get(
                f"/api/market-evidence/health?projectId={project.project_id}"
            )
            workspace_cruise_health_response = client.get("/api/worker/cruise/health")
            workspace_cruise_health_project_response = client.get(
                f"/api/worker/cruise/health?projectId={project.project_id}"
            )
            workspace_runtime_route_history_response = client.get("/api/runtime-route/history?limit=5")
            workspace_billing_gateway_history_response = client.get("/api/billing/gateway/history?limit=5")
            workspace_model_gateway_history_response = client.get("/api/model-gateway/history?limit=5")
            workspace_evidence_filtered_response = client.get(
                "/api/connectors/evidence",
                params={"provider": "ga4", "mode": "real", "strictOnly": "true", "limit": 5},
            )
            workspace_evidence_project_response = client.get(
                "/api/connectors/evidence",
                params={"projectId": project.project_id, "limit": 5},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("generatedAt", payload)
        self.assertIn("projects", payload)
        self.assertIn("policy", payload)
        self.assertIn("runtimeRouteHealth", payload)
        self.assertIn("runtimeRouteHistory", payload)
        self.assertIn("billingSettlementHistory", payload)
        self.assertIn("billingGatewayHistory", payload)
        self.assertIn("modelGatewayHistory", payload)
        self.assertIn("skillRegression", payload)
        self.assertIn("projectId", payload["projects"][0])
        self.assertEqual(metrics_response.status_code, 200)
        self.assertEqual(deployments_response.status_code, 200)
        self.assertEqual(rollbacks_response.status_code, 200)
        self.assertEqual(evidence_response.status_code, 200)
        self.assertEqual(market_health_response.status_code, 200)
        self.assertEqual(cruise_health_response.status_code, 200)
        self.assertEqual(workspace_market_health_response.status_code, 200)
        self.assertEqual(workspace_market_health_project_response.status_code, 200)
        self.assertEqual(workspace_cruise_health_response.status_code, 200)
        self.assertEqual(workspace_cruise_health_project_response.status_code, 200)
        workspace_billing_response = client.get("/api/billing")
        workspace_billing_project_response = client.get(f"/api/billing?projectId={project.project_id}")
        workspace_billing_gateway_response = client.get("/api/billing/gateway")
        workspace_billing_gateway_project_response = client.get(
            f"/api/billing/gateway?projectId={project.project_id}"
        )
        workspace_model_gateway_response = client.get("/api/model-gateway")
        workspace_model_gateway_project_response = client.get(
            f"/api/model-gateway?projectId={project.project_id}"
        )
        self.assertEqual(workspace_runtime_route_history_response.status_code, 200)
        self.assertEqual(workspace_billing_gateway_history_response.status_code, 200)
        self.assertEqual(workspace_model_gateway_history_response.status_code, 200)
        self.assertEqual(workspace_billing_response.status_code, 200)
        self.assertEqual(workspace_billing_project_response.status_code, 200)
        self.assertEqual(workspace_billing_gateway_response.status_code, 200)
        self.assertEqual(workspace_billing_gateway_project_response.status_code, 200)
        self.assertEqual(workspace_model_gateway_response.status_code, 200)
        self.assertEqual(workspace_model_gateway_project_response.status_code, 200)
        self.assertEqual(workspace_evidence_response.status_code, 200)
        self.assertEqual(workspace_evidence_filtered_response.status_code, 200)
        self.assertEqual(workspace_evidence_project_response.status_code, 200)
        metrics_payload = metrics_response.json()
        deployments_payload = deployments_response.json()
        rollbacks_payload = rollbacks_response.json()
        evidence_payload = evidence_response.json()
        market_health_payload = market_health_response.json()
        cruise_health_payload = cruise_health_response.json()
        workspace_market_health_payload = workspace_market_health_response.json()
        workspace_market_health_project_payload = workspace_market_health_project_response.json()
        workspace_cruise_health_payload = workspace_cruise_health_response.json()
        workspace_cruise_health_project_payload = workspace_cruise_health_project_response.json()
        workspace_runtime_route_history_payload = workspace_runtime_route_history_response.json()
        workspace_billing_gateway_history_payload = workspace_billing_gateway_history_response.json()
        workspace_model_gateway_history_payload = workspace_model_gateway_history_response.json()
        workspace_billing_payload = workspace_billing_response.json()
        workspace_billing_project_payload = workspace_billing_project_response.json()
        workspace_billing_gateway_payload = workspace_billing_gateway_response.json()
        workspace_billing_gateway_project_payload = workspace_billing_gateway_project_response.json()
        workspace_model_gateway_payload = workspace_model_gateway_response.json()
        workspace_model_gateway_project_payload = workspace_model_gateway_project_response.json()
        self.assertIn("projectCount", workspace_market_health_payload)
        self.assertIn("projectCount", workspace_cruise_health_payload)
        self.assertIn("projectCount", payload["runtimeRouteHealth"])
        self.assertIn("total", payload["runtimeRouteHistory"])
        self.assertIn("items", payload["runtimeRouteHistory"])
        self.assertGreaterEqual(payload["runtimeRouteHistory"]["total"], 1)
        self.assertIn("total", payload["billingSettlementHistory"])
        self.assertIn("entries", payload["billingSettlementHistory"])
        self.assertIn("total", payload["billingGatewayHistory"])
        self.assertIn("entries", payload["billingGatewayHistory"])
        self.assertIn("total", workspace_runtime_route_history_payload)
        self.assertGreaterEqual(workspace_runtime_route_history_payload["total"], 1)
        self.assertTrue(workspace_runtime_route_history_payload["items"])
        self.assertIn("total", workspace_billing_gateway_history_payload)
        self.assertIn("entries", workspace_billing_gateway_history_payload)
        self.assertIn("gatewayReadyCount", workspace_billing_gateway_history_payload)
        self.assertIn("gatewayRouteReadyCount", workspace_billing_gateway_history_payload)
        self.assertIn("total", workspace_model_gateway_history_payload)
        self.assertIn("entries", workspace_model_gateway_history_payload)
        self.assertIn("runtimeReadyCount", workspace_model_gateway_history_payload)
        self.assertIn("gatewayReadyCount", workspace_model_gateway_history_payload)
        self.assertIsNone(workspace_billing_payload["projectId"])
        self.assertEqual(workspace_billing_project_payload["projectId"], project.project_id)
        self.assertIsNone(workspace_billing_gateway_payload["projectId"])
        self.assertEqual(workspace_billing_gateway_project_payload["projectId"], project.project_id)
        self.assertIsNone(workspace_model_gateway_payload["projectId"])
        self.assertEqual(workspace_model_gateway_project_payload["projectId"], project.project_id)
        workspace_evidence_payload = workspace_evidence_response.json()
        workspace_evidence_filtered_payload = workspace_evidence_filtered_response.json()
        workspace_evidence_project_payload = workspace_evidence_project_response.json()
        self.assertEqual(metrics_payload["projectId"], project.project_id)
        self.assertGreaterEqual(metrics_payload["total"], 1)
        self.assertGreaterEqual(len(metrics_payload["snapshots"]), 1)
        self.assertIn("sourceStatus", metrics_payload["snapshots"][0])
        self.assertIn("sourceMetricsSummary", metrics_payload["snapshots"][0])
        self.assertIn("externalMetrics", metrics_payload["snapshots"][0])
        self.assertEqual(deployments_payload["projectId"], project.project_id)
        self.assertGreaterEqual(deployments_payload["total"], 1)
        self.assertIn("entries", deployments_payload)
        self.assertEqual(rollbacks_payload["projectId"], project.project_id)
        self.assertGreaterEqual(rollbacks_payload["total"], 1)
        self.assertIn("entries", rollbacks_payload)
        self.assertEqual(evidence_payload["projectId"], project.project_id)
        self.assertGreaterEqual(evidence_payload["total"], 1)
        self.assertIn("entries", evidence_payload)
        self.assertEqual(market_health_payload["projectId"], project.project_id)
        self.assertIn("strictReady", market_health_payload)
        self.assertIn("freshCount", market_health_payload)
        self.assertIn("latestFetchedAt", market_health_payload)
        self.assertEqual(cruise_health_payload["projectId"], project.project_id)
        self.assertIn("autoCruiseEnabled", cruise_health_payload)
        self.assertIn("dueNow", cruise_health_payload)
        self.assertIn("overdue", cruise_health_payload)
        self.assertIn("projectSample", cruise_health_payload)
        self.assertIn("projectCount", workspace_market_health_payload)
        self.assertIn("strictReadyProjectCount", workspace_market_health_payload)
        self.assertIn("strictReadyProjectRatePercent", workspace_market_health_payload)
        self.assertIn("strictReadyProjectIds", workspace_market_health_payload)
        self.assertIn("staleProjectIds", workspace_market_health_payload)
        self.assertEqual(workspace_market_health_payload["projectId"], None)
        self.assertEqual(workspace_market_health_project_payload["projectId"], project.project_id)
        self.assertIsInstance(workspace_market_health_payload["strictReadyProjectIds"], list)
        self.assertIsInstance(workspace_market_health_payload["staleProjectIds"], list)
        self.assertIn("enabledProjectCount", workspace_cruise_health_payload)
        self.assertIn("dueProjectCount", workspace_cruise_health_payload)
        self.assertIn("projectSamples", workspace_cruise_health_payload)
        self.assertIn("dueProjectIds", workspace_cruise_health_payload)
        self.assertEqual(workspace_cruise_health_payload["projectId"], None)
        self.assertEqual(workspace_cruise_health_project_payload["projectId"], project.project_id)
        self.assertGreaterEqual(workspace_evidence_payload["total"], 1)
        self.assertIn("entries", workspace_evidence_payload)
        self.assertIn("providerSummaries", workspace_evidence_payload)
        self.assertIsNone(workspace_evidence_payload["projectId"])
        self.assertIsInstance(workspace_evidence_payload["providerSummaries"], list)
        self.assertLessEqual(workspace_evidence_filtered_payload["total"], 5)
        self.assertTrue(all(item["provider"] == "ga4" for item in workspace_evidence_filtered_payload["entries"]))
        self.assertTrue(all(item["providerMode"] == "real" for item in workspace_evidence_filtered_payload["entries"]))
        self.assertTrue(all(bool(item["strictEligible"]) for item in workspace_evidence_filtered_payload["entries"]))
        self.assertEqual(workspace_evidence_project_payload["projectId"], project.project_id)
        self.assertTrue(
            all(item["projectId"] == project.project_id for item in workspace_evidence_project_payload["entries"])
        )

    def test_sync_connections_and_auth_guards(self) -> None:
        os.environ["SEO_AD_BOT_ENABLE_BROWSER_CRAWL"] = "true"
        os.environ["SEO_AD_BOT_BROWSER_CRAWL_TIMEOUT_MS"] = "1200"
        os.environ["SEO_AD_BOT_BROWSER_CRAWL_RETRY_COUNT"] = "2"
        os.environ["SEO_AD_BOT_BROWSER_CRAWL_USER_AGENT"] = "SEO-AD-BOT-Test-UA/1.0"
        service = self._service()
        app = create_app(service)
        project_payload = {
            "name": "Syncable",
            "intake": {
                "url": "https://syncable.example",
                "siteName": "Syncable",
                "repoUrl": "https://github.com/example/syncable",
                "brandWhitelist": ["Syncable"],
                "keywords": ["sync", "crawl", "preview"],
            },
        }

        with TestClient(app) as client:
            self.assertEqual(client.post("/api/projects", json=project_payload).status_code, 401)

            created = client.post("/api/projects", json=project_payload, headers={"X-API-Key": "dev-key"})
            self.assertEqual(created.status_code, 200)
            project_id = created.json()["projectId"]

            self.assertEqual(client.post(f"/api/projects/{project_id}/sync", headers={"X-API-Key": "wrong"}).status_code, 403)

            sync = client.post(f"/api/projects/{project_id}/sync", headers={"X-API-Key": "dev-key"})
            self.assertEqual(sync.status_code, 200)
            sync_payload = sync.json()
            self.assertIn("ingestionReport", sync_payload)
            self.assertIn(sync.headers["X-SEO-AD-Runtime-Ready"], {"true", "false"})
            self.assertIn(sync.headers["X-SEO-AD-Experiment-Variant"], {"control", "unassigned"})
            task_id = sync_payload["task"]["taskId"]
            with service.database.session() as session:
                task_row = session.get(TaskRow, task_id)
                self.assertIsNotNone(task_row)
                self.assertIn("runtimeRoute", task_row.analysis_json)
                self.assertIn("runtimeRouteSummary", task_row.analysis_json)
                self.assertIn("gatewayRouteProviderName", task_row.analysis_json["runtimeRoute"])
                self.assertIn("gatewayRoutePriority", task_row.analysis_json["runtimeRoute"])

            runs = client.get(f"/api/projects/{project_id}/runs")
            self.assertEqual(runs.status_code, 200)
            runs_payload = runs.json()
            self.assertTrue(runs_payload)
            latest_run_status = runs_payload[0]["connectorStatus"]
            self.assertIn("runtimeRouteReady", runs_payload[0])
            self.assertIn("runtimeRouteSummary", runs_payload[0])
            self.assertIn("gatewayRouteProviderName", runs_payload[0])
            self.assertIn("gatewayRoutePriority", runs_payload[0])
            self.assertIn("trend", latest_run_status)
            self.assertIn("news", latest_run_status)
            self.assertIn("qa", latest_run_status)
            filtered_runs = client.get(
                f"/api/projects/{project_id}/runs",
                params={"trigger": "manual", "status": "failed", "limit": 1},
            )
            self.assertEqual(filtered_runs.status_code, 200)
            filtered_payload = filtered_runs.json()
            self.assertLessEqual(len(filtered_payload), 1)
            self.assertTrue(all(item["trigger"] == "manual" for item in filtered_payload))
            self.assertTrue(all(item["status"] == "failed" for item in filtered_payload))

            connections = client.get(f"/api/projects/{project_id}/connections")
            self.assertEqual(connections.status_code, 200)
            connection_payload = connections.json()
            self.assertEqual(connection_payload["projectId"], project_id)
            self.assertTrue(connection_payload["connections"])
            providers = {item["provider"] for item in connection_payload["connections"]}
            self.assertIn("trend", providers)
            self.assertIn("news", providers)
            self.assertIn("qa", providers)
            self.assertTrue(connection_payload["state"]["lastSyncAt"])
            self.assertTrue(
                any(item.get("lastSuccessAt") or item.get("lastErrorAt") for item in connection_payload["connections"])
            )

            updated = client.put(
                f"/api/projects/{project_id}/connections",
                json={
                    "autoCruiseEnabled": True,
                    "syncIntervalMinutes": 30,
                    "connections": connection_payload["connections"],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated.status_code, 200)
            self.assertTrue(updated.json()["state"]["autoCruiseEnabled"])

            tested = client.post(f"/api/projects/{project_id}/connections/test", headers={"X-API-Key": "dev-key"})
            self.assertEqual(tested.status_code, 200)
            tested_payload = tested.json()
            self.assertIn(tested_payload["connectionHealth"], {"healthy", "degraded", "unavailable", "unknown"})
            self.assertIn("strictMode", tested_payload)
            self.assertIn("strictBlocked", tested_payload)
            self.assertIn("strictGapCount", tested_payload)
            self.assertIn("strictBlockers", tested_payload)
            self.assertEqual(tested_payload["strictMode"], False)
            self.assertEqual(tested_payload["strictBlocked"], False)
            self.assertTrue(
                all(
                    item["providerMode"] in {"real", "fallback", "unconfigured"}
                    and isinstance(item["strictEligible"], bool)
                    for item in tested_payload["connections"]
                )
            )

            connectors_health = client.get(f"/api/projects/{project_id}/connectors/health")
            self.assertEqual(connectors_health.status_code, 200)
            self.assertEqual(connectors_health.json()["projectId"], project_id)
            self.assertGreaterEqual(connectors_health.json()["totalConnectionCount"], connectors_health.json()["strictEligibleCount"])
            self.assertIn("readRealLastEvidenceAt", connectors_health.json())
            self.assertIn("writeRealLastEvidenceAt", connectors_health.json())
            health_connections = connectors_health.json()["connections"]
            health_providers = {item["provider"] for item in health_connections}
            self.assertIn("trend", health_providers)
            self.assertIn("news", health_providers)
            self.assertIn("qa", health_providers)
            workspace_connectors_health = client.get("/api/connectors/health")
            self.assertEqual(workspace_connectors_health.status_code, 200)
            workspace_connectors_health_payload = workspace_connectors_health.json()
            self.assertGreaterEqual(workspace_connectors_health_payload["projectCount"], 1)
            self.assertGreaterEqual(
                workspace_connectors_health_payload["totalConnectionCount"],
                workspace_connectors_health_payload["strictEligibleCount"],
            )
            self.assertGreaterEqual(workspace_connectors_health_payload["strictGapCount"], 0)
            self.assertGreaterEqual(workspace_connectors_health_payload["readConnectionCount"], 0)
            self.assertGreaterEqual(workspace_connectors_health_payload["readRealConnectionCount"], 0)
            self.assertGreaterEqual(workspace_connectors_health_payload["readStrictEligibleCount"], 0)
            self.assertGreaterEqual(float(workspace_connectors_health_payload["readRealCoveragePercent"]), 0)
            self.assertGreaterEqual(float(workspace_connectors_health_payload["readStrictCoveragePercent"]), 0)
            self.assertIn("readRealLastEvidenceAt", workspace_connectors_health_payload)
            workspace_connectors_health_project = client.get("/api/connectors/health", params={"projectId": project_id})
            self.assertEqual(workspace_connectors_health_project.status_code, 200)
            workspace_connectors_health_project_payload = workspace_connectors_health_project.json()
            self.assertEqual(workspace_connectors_health_project_payload["projectId"], project_id)
            self.assertEqual(workspace_connectors_health_project_payload["projectCount"], 1)
            self.assertGreaterEqual(workspace_connectors_health_payload["writeConnectionCount"], 0)
            self.assertGreaterEqual(workspace_connectors_health_payload["writeRealConnectionCount"], 0)
            self.assertGreaterEqual(workspace_connectors_health_payload["writeStrictEligibleCount"], 0)
            self.assertGreaterEqual(float(workspace_connectors_health_payload["writeRealCoveragePercent"]), 0)
            self.assertGreaterEqual(float(workspace_connectors_health_payload["writeStrictCoveragePercent"]), 0)
            self.assertIn("writeRealLastEvidenceAt", workspace_connectors_health_payload)
            self.assertGreaterEqual(workspace_connectors_health_payload["realProviderCount"], 0)
            self.assertGreaterEqual(float(workspace_connectors_health_payload["realProviderRatePercent"]), 0)
            self.assertGreaterEqual(workspace_connectors_health_payload["zeroRealProviderCount"], 0)
            self.assertGreaterEqual(float(workspace_connectors_health_payload["zeroRealProviderRatePercent"]), 0)
            self.assertTrue(isinstance(workspace_connectors_health_payload["zeroRealProviders"], list))
            self.assertGreaterEqual(workspace_connectors_health_payload["zeroStrictProviderCount"], 0)
            self.assertGreaterEqual(float(workspace_connectors_health_payload["zeroStrictProviderRatePercent"]), 0)
            self.assertTrue(isinstance(workspace_connectors_health_payload["zeroStrictProviders"], list))
            self.assertGreaterEqual(workspace_connectors_health_payload["strictReadyProviderCount"], 0)
            self.assertGreaterEqual(float(workspace_connectors_health_payload["strictReadyProviderRatePercent"]), 0)
            self.assertTrue(isinstance(workspace_connectors_health_payload["strictReadyProviders"], list))
            self.assertGreaterEqual(workspace_connectors_health_payload["partialStrictProviderCount"], 0)
            self.assertGreaterEqual(float(workspace_connectors_health_payload["partialStrictProviderRatePercent"]), 0)
            self.assertTrue(isinstance(workspace_connectors_health_payload["partialStrictProviders"], list))
            self.assertGreaterEqual(workspace_connectors_health_payload["fullyStrictProviderCount"], 0)
            self.assertGreaterEqual(float(workspace_connectors_health_payload["fullyStrictProviderRatePercent"]), 0)
            self.assertTrue(isinstance(workspace_connectors_health_payload["fullyStrictProviders"], list))
            self.assertTrue(isinstance(workspace_connectors_health_payload["providerCoverage"], list))
            self.assertTrue(isinstance(workspace_connectors_health_payload["topBlockingProviders"], list))
            self.assertTrue(isinstance(workspace_connectors_health_payload["topStrictGapProviders"], list))
            self.assertTrue(isinstance(workspace_connectors_health_payload["topStrictReadyProviders"], list))
            self.assertTrue(any(item["provider"] == "search_console" for item in workspace_connectors_health_payload["providerCoverage"]))
            self.assertTrue(
                all(item["affectedProjectCount"] >= item["blockingProjectCount"] for item in workspace_connectors_health_payload["providerCoverage"])
            )
            observability_status = client.get("/api/observability/status")
            self.assertEqual(observability_status.status_code, 200)
            observability_payload = observability_status.json()
            self.assertIn("tracingBackend", observability_payload)
            self.assertIn(observability_payload["tracingBackend"], {"disabled", "in-memory", "otlp"})
            self.assertIn("enableOtlp", observability_payload)
            self.assertIn("otlpEndpointConfigured", observability_payload)
            self.assertIn("sentryDsnConfigured", observability_payload)
            self.assertIn("otlpExporterAvailable", observability_payload)
            self.assertIsInstance(observability_payload["notes"], list)
            self.assertTrue(
                all(item["affectedProjectCount"] >= item["strictReadyProjectCount"] for item in workspace_connectors_health_payload["providerCoverage"])
            )
            self.assertTrue(
                all(float(item["strictReadyProjectRatePercent"]) >= 0 for item in workspace_connectors_health_payload["providerCoverage"])
            )
            self.assertTrue(
                all(float(item["blockingProjectRatePercent"]) >= 0 for item in workspace_connectors_health_payload["providerCoverage"])
            )
            self.assertTrue(all(item["strictGapCount"] >= 0 for item in workspace_connectors_health_payload["providerCoverage"]))
            self.assertTrue(all(item["strictGapCount"] >= 0 for item in workspace_connectors_health_payload["topStrictGapProviders"]))
            self.assertTrue(all(float(item["strictCoveragePercent"]) >= 0 for item in workspace_connectors_health_payload["topStrictReadyProviders"]))
            self.assertTrue(
                all(
                    float(item["realCoveragePercent"]) >= 0
                    and float(item["strictCoveragePercent"]) >= 0
                    and float(item["blockingRatePercent"]) >= 0
                    for item in workspace_connectors_health_payload["providerCoverage"]
                )
            )
            self.assertTrue(
                all(
                    isinstance(item["affectedProjectIds"], list)
                    and isinstance(item["strictReadyProjectIds"], list)
                    and isinstance(item["blockingProjectIds"], list)
                    for item in workspace_connectors_health_payload["providerCoverage"]
                )
            )
            self.assertTrue(
                all(
                    isinstance(item["affectedProjects"], list)
                    and isinstance(item["strictReadyProjects"], list)
                    and isinstance(item["blockingProjects"], list)
                    for item in workspace_connectors_health_payload["providerCoverage"]
                )
            )
            self.assertTrue(all("primaryBlockingReason" in item for item in workspace_connectors_health_payload["providerCoverage"]))
            self.assertTrue(all("primaryFailureCategory" in item for item in workspace_connectors_health_payload["providerCoverage"]))
            self.assertTrue(
                all("suggestedActionPath" in item and "suggestedActionLabel" in item for item in workspace_connectors_health_payload["providerCoverage"])
            )
            self.assertTrue(
                any(item["projectId"] == project_id for item in workspace_connectors_health_payload["projects"])
            )
            provider_coverage_map = {
                item["provider"]: item for item in workspace_connectors_health_payload["providerCoverage"]
            }
            self.assertTrue(all(item["provider"] in provider_coverage_map for item in workspace_connectors_health_payload["topBlockingProviders"]))
            self.assertTrue(all(item["provider"] in provider_coverage_map for item in workspace_connectors_health_payload["topStrictGapProviders"]))
            self.assertTrue(all(item["provider"] in provider_coverage_map for item in workspace_connectors_health_payload["topStrictReadyProviders"]))
            self.assertEqual(
                [item["blockingProjectCount"] for item in workspace_connectors_health_payload["topBlockingProviders"]],
                sorted(
                    [item["blockingProjectCount"] for item in workspace_connectors_health_payload["topBlockingProviders"]],
                    reverse=True,
                ),
            )
            self.assertEqual(
                [item["strictGapCount"] for item in workspace_connectors_health_payload["topStrictGapProviders"]],
                sorted(
                    [item["strictGapCount"] for item in workspace_connectors_health_payload["topStrictGapProviders"]],
                    reverse=True,
                ),
            )
            self.assertEqual(
                [float(item["strictCoveragePercent"]) for item in workspace_connectors_health_payload["topStrictReadyProviders"]],
                sorted(
                    [float(item["strictCoveragePercent"]) for item in workspace_connectors_health_payload["topStrictReadyProviders"]],
                    reverse=True,
                ),
            )
            for top_item in workspace_connectors_health_payload["topBlockingProviders"]:
                base = provider_coverage_map[top_item["provider"]]
                self.assertEqual(top_item["blockingProjectCount"], base["blockingProjectCount"])
                self.assertEqual(top_item["strictGapCount"], base["strictGapCount"])
            for top_item in workspace_connectors_health_payload["topStrictGapProviders"]:
                base = provider_coverage_map[top_item["provider"]]
                self.assertEqual(top_item["strictGapCount"], base["strictGapCount"])
                self.assertEqual(top_item["blockingProjectCount"], base["blockingProjectCount"])
            for top_item in workspace_connectors_health_payload["topStrictReadyProviders"]:
                base = provider_coverage_map[top_item["provider"]]
                self.assertEqual(float(top_item["strictCoveragePercent"]), float(base["strictCoveragePercent"]))
                self.assertEqual(top_item["strictEligibleCount"], base["strictEligibleCount"])
            workspace_project_map = {
                item["projectId"]: item for item in workspace_connectors_health_payload["projects"]
            }
            self.assertIn(project_id, workspace_project_map)
            self.assertEqual(
                int(workspace_project_map[project_id]["strictEligibleCount"]),
                int(connectors_health.json()["strictEligibleCount"]),
            )
            self.assertEqual(
                workspace_project_map[project_id]["connectionHealth"],
                connectors_health.json()["connectionHealth"],
            )
            workspace_connection_history = client.get("/api/connectors/history", params={"limit": 5})
            self.assertEqual(workspace_connection_history.status_code, 200)
            workspace_connection_history_payload = workspace_connection_history.json()
            self.assertIsNone(workspace_connection_history_payload["projectId"])
            self.assertIsInstance(workspace_connection_history_payload["entries"], list)
            self.assertEqual(workspace_connection_history_payload["summary"]["totalCount"], len(workspace_connection_history_payload["entries"]))
            self.assertTrue(workspace_connection_history_payload["summary"]["providerCounts"])
            self.assertTrue(
                any(item["projectId"] == project_id for item in workspace_connection_history_payload["entries"])
            )
            workspace_connection_history_project = client.get(
                "/api/connectors/history",
                params={"limit": 5, "projectId": project_id},
            )
            self.assertEqual(workspace_connection_history_project.status_code, 200)
            workspace_connection_history_project_payload = workspace_connection_history_project.json()
            self.assertEqual(workspace_connection_history_project_payload["projectId"], project_id)
            self.assertTrue(
                all(item["projectId"] == project_id for item in workspace_connection_history_project_payload["entries"])
            )
            workspace_connection_history_filtered = client.get(
                "/api/connectors/history",
                params={"limit": 5, "projectId": project_id, "provider": "search_console", "action": "connector.probe"},
            )
            self.assertEqual(workspace_connection_history_filtered.status_code, 200)
            filtered_entries = workspace_connection_history_filtered.json()["entries"]
            self.assertTrue(all(item["projectId"] == project_id for item in filtered_entries))
            self.assertTrue(all(item["provider"] == "search_console" for item in filtered_entries))
            self.assertTrue(all(item["action"] == "connector.probe" for item in filtered_entries))
            workspace_connection_history_invalid_action = client.get(
                "/api/connectors/history",
                params={"action": "invalid-action"},
            )
            self.assertEqual(workspace_connection_history_invalid_action.status_code, 422)
            connection_history = client.get(f"/api/projects/{project_id}/connections/history", params={"limit": 5})
            self.assertEqual(connection_history.status_code, 200)
            history_payload = connection_history.json()
            self.assertEqual(history_payload["projectId"], project_id)
            self.assertIsInstance(history_payload["entries"], list)
            self.assertEqual(history_payload["summary"]["totalCount"], len(history_payload["entries"]))
            self.assertTrue(history_payload["summary"]["providerCounts"])
            self.assertTrue(any(item["action"] in {"connector.probe", "connector.refreshed"} for item in history_payload["entries"]))
            connection_history_filtered = client.get(
                f"/api/projects/{project_id}/connections/history",
                params={"limit": 10, "provider": "search_console", "action": "connector.probe"},
            )
            self.assertEqual(connection_history_filtered.status_code, 200)
            filtered_project_entries = connection_history_filtered.json()["entries"]
            self.assertEqual(
                connection_history_filtered.json()["summary"]["providerCounts"][0]["label"],
                "search_console",
            )
            self.assertTrue(all(item["provider"] == "search_console" for item in filtered_project_entries))
            self.assertTrue(all(item["action"] == "connector.probe" for item in filtered_project_entries))
            self.assertTrue(all(item["status"] for item in filtered_project_entries))
            invalid_project_connection_history = client.get(
                f"/api/projects/{project_id}/connections/history",
                params={"action": "invalid-action"},
            )
            self.assertEqual(invalid_project_connection_history.status_code, 422)

            refresh_connector = client.post(
                f"/api/projects/{project_id}/connectors/search_console/refresh",
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(refresh_connector.status_code, 200)
            self.assertEqual(refresh_connector.json()["provider"], "search_console")
            refreshed_history = client.get(f"/api/projects/{project_id}/connections/history", params={"limit": 10})
            self.assertEqual(refreshed_history.status_code, 200)
            refreshed_entries = [
                item for item in refreshed_history.json()["entries"] if item["action"] == "connector.refreshed"
            ]
            self.assertTrue(refreshed_entries)
            self.assertTrue(all("authSource" in item for item in refreshed_entries))

            refresh_all = client.post(
                f"/api/projects/{project_id}/connections/refresh",
                json={"maxProviders": 5},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(refresh_all.status_code, 200)
            refresh_all_payload = refresh_all.json()
            self.assertEqual(refresh_all_payload["projectId"], project_id)
            self.assertGreaterEqual(refresh_all_payload["refreshedCount"], 1)
            self.assertTrue(isinstance(refresh_all_payload["results"], list))
            self.assertTrue(all(item["projectId"] == project_id for item in refresh_all_payload["results"]))
            self.assertIn(refresh_all_payload["connectionHealth"], {"healthy", "degraded", "unavailable", "unknown"})
            self.assertIn("strictMode", refresh_all_payload)
            self.assertIn("strictBlocked", refresh_all_payload)
            self.assertIn("strictGapCount", refresh_all_payload)
            self.assertIn("strictBlockers", refresh_all_payload)

            bulk_refresh_blocked = client.post(
                "/api/bulk/projects/connections/refresh",
                json={"projectIds": [project_id]},
            )
            self.assertEqual(bulk_refresh_blocked.status_code, 401)

            created_second = client.post(
                "/api/projects",
                json={
                    "name": "Syncable Two",
                    "intake": {
                        "url": "https://syncable-two.example",
                        "siteName": "Syncable Two",
                        "repoUrl": "https://github.com/example/syncable-two",
                        "brandWhitelist": ["Syncable"],
                        "keywords": ["sync", "refresh", "crawl"],
                    },
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(created_second.status_code, 200)
            second_project_id = created_second.json()["projectId"]

            bulk_refresh_all = client.post(
                "/api/bulk/projects/connections/refresh",
                json={"projectIds": [project_id, second_project_id, "missing-project"], "maxProviders": 5},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(bulk_refresh_all.status_code, 200)
            bulk_refresh_all_payload = bulk_refresh_all.json()
            self.assertEqual(
                bulk_refresh_all_payload["projectIds"],
                [project_id, second_project_id, "missing-project"],
            )
            self.assertEqual(bulk_refresh_all_payload["refreshedCount"], 2)
            self.assertEqual(bulk_refresh_all_payload["skippedProjectIds"], ["missing-project"])
            self.assertEqual(len(bulk_refresh_all_payload["results"]), 2)
            self.assertTrue(
                all(item["projectId"] in {project_id, second_project_id} for item in bulk_refresh_all_payload["results"])
            )

            refresh_playwright = client.post(
                f"/api/projects/{project_id}/connectors/playwright/refresh",
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(refresh_playwright.status_code, 200)
            self.assertEqual(refresh_playwright.json()["provider"], "playwright")
            self.assertIn(refresh_playwright.json()["status"], {"connected", "synthetic", "error"})
            playwright_details = refresh_playwright.json()["connection"]["details"]
            self.assertIn("attemptCount", playwright_details)
            self.assertIn("timeoutMs", playwright_details)
            self.assertIn("userAgent", playwright_details)
            self.assertIn("configuredUserAgents", playwright_details)
            self.assertIn("extraHeaders", playwright_details)
            self.assertIn("jitterMs", playwright_details)
            self.assertIn("antiBotBlocked", playwright_details)
            self.assertIn("blockSignals", playwright_details)
            self.assertIn("screenshotArtifactRef", playwright_details)
            self.assertIn("htmlArtifactRef", playwright_details)
            self.assertGreaterEqual(int(playwright_details["attemptCount"]), 0)

            refresh_trend_connector = client.post(
                f"/api/projects/{project_id}/connectors/trend/refresh",
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(refresh_trend_connector.status_code, 200)
            self.assertEqual(refresh_trend_connector.json()["provider"], "trend")
            self.assertIn(refresh_trend_connector.json()["status"], {"connected", "synthetic", "error", "unavailable"})
            self.assertEqual(refresh_trend_connector.json()["evidence"]["sourceType"], "trend")
            trend_details = refresh_trend_connector.json()["connection"]["details"]
            self.assertIn("endpointsConfigured", trend_details)
            self.assertIn("endpointsTried", trend_details)

            refresh_ad_connector = client.post(
                f"/api/projects/{project_id}/connectors/ad_network/refresh",
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(refresh_ad_connector.status_code, 200)
            self.assertEqual(refresh_ad_connector.json()["provider"], "ad_network")
            self.assertIn(refresh_ad_connector.json()["status"], {"connected", "missing_credentials", "synthetic", "error", "unavailable"})
            ad_details = refresh_ad_connector.json()["connection"]["details"]
            self.assertIn("endpointsConfigured", ad_details)
            self.assertIn("endpointsTried", ad_details)
            self.assertIn("estimatedRevenueDaily", ad_details)
            self.assertIn("rpm", ad_details)
            self.assertIn("fillRate", ad_details)
            self.assertIn("impressions", ad_details)

            refresh_script_connector = client.post(
                f"/api/projects/{project_id}/connectors/script_api/refresh",
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(refresh_script_connector.status_code, 200)
            self.assertEqual(refresh_script_connector.json()["provider"], "script_api")
            self.assertIn(refresh_script_connector.json()["status"], {"connected", "missing_credentials", "synthetic", "error", "unavailable"})
            script_details = refresh_script_connector.json()["connection"]["details"]
            self.assertIn("endpointsConfigured", script_details)
            self.assertIn("endpointsTried", script_details)

            refresh_github_connector = client.post(
                f"/api/projects/{project_id}/connectors/github/refresh",
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(refresh_github_connector.status_code, 200)
            self.assertEqual(refresh_github_connector.json()["provider"], "github")
            github_details = refresh_github_connector.json()["connection"]["details"]
            self.assertIn("endpointsConfigured", github_details)
            self.assertIn("endpointsTried", github_details)

            ad_audit = client.get(f"/api/projects/{project_id}/ad-audit")
            self.assertEqual(ad_audit.status_code, 200)
            ad_payload = ad_audit.json()
            self.assertIn("adConnectorStatus", ad_payload)
            self.assertIn("adRevenueEstimateDaily", ad_payload)
            self.assertIn("adRevenueEstimateMonthly", ad_payload)
            self.assertIn("adRevenueProvenance", ad_payload)
            self.assertIn("strictPublishEligible", ad_payload)

            regression = client.get("/api/regressions")
            self.assertEqual(regression.status_code, 200)
            regression_payload = regression.json()
            self.assertEqual(regression_payload["sampleCount"], 10)
            self.assertGreaterEqual(regression_payload["seoPreviewCount"], 3)
            self.assertGreaterEqual(regression_payload["noAdCount"], 1)
            self.assertGreaterEqual(regression_payload["passCount"], 1)
            acceptance = client.get("/api/acceptance/report")
            self.assertEqual(acceptance.status_code, 200)
            acceptance_payload = acceptance.json()
            self.assertIn("gates", acceptance_payload)
            self.assertIn("passed", acceptance_payload)
            self.assertGreaterEqual(len(acceptance_payload["gates"]), 5)
            gate_ids = {item["gateId"] for item in acceptance_payload["gates"]}
            self.assertIn("mvp_samples", gate_ids)
            self.assertIn("mvp_seo_previews", gate_ids)
            self.assertIn("mvp_ad_recommendations", gate_ids)
            self.assertIn("mvp_no_ad_negative", gate_ids)
            self.assertIn("mvp_rollback_path", gate_ids)
            self.assertIn("prompt_registry", gate_ids)
            self.assertIn("playwright_antibot_clear", gate_ids)
            self.assertIn("real_provider_samples", gate_ids)
            self.assertIn("visual_regression_production", gate_ids)
            self.assertIn("visual_farm_runtime_ready", gate_ids)
            self.assertIn("blocking_alerts_clear", gate_ids)
            self.assertIn("observability_pipeline", gate_ids)
            self.assertIn("runtime_architecture_production", gate_ids)
            self.assertIn("runtime_edge_gateway_ready", gate_ids)
            self.assertIn("runtime_edge_rollout_ready", gate_ids)
            self.assertIn("runtime_edge_probe_ready", gate_ids)
            self.assertIn("market_workspace_readiness", gate_ids)
            self.assertIn("workspace_auto_cruise", gate_ids)
            self.assertIn("regression", acceptance_payload)
            self.assertEqual(acceptance_payload["regression"]["sampleCount"], regression_payload["sampleCount"])
            self.assertIn("readRealEvidence", acceptance_payload)
            self.assertIn("writeRealEvidence", acceptance_payload)
            self.assertIn("readRealEvidenceCount", acceptance_payload)
            self.assertIn("writeRealEvidenceCount", acceptance_payload)
            self.assertIn("readRealProviderCount", acceptance_payload)
            self.assertIn("writeRealProviderCount", acceptance_payload)
            self.assertIn("readRealProviders", acceptance_payload)
            self.assertIn("writeRealProviders", acceptance_payload)
            self.assertIsInstance(acceptance_payload["readRealEvidence"], list)
            self.assertIsInstance(acceptance_payload["writeRealEvidence"], list)
            self.assertIsInstance(acceptance_payload["readRealProviders"], list)
            self.assertIsInstance(acceptance_payload["writeRealProviders"], list)
            self.assertGreaterEqual(acceptance_payload["readRealEvidenceCount"], len(acceptance_payload["readRealEvidence"]))
            self.assertGreaterEqual(acceptance_payload["writeRealEvidenceCount"], len(acceptance_payload["writeRealEvidence"]))
            self.assertGreaterEqual(acceptance_payload["readRealProviderCount"], len(set(acceptance_payload["readRealProviders"])))
            self.assertGreaterEqual(acceptance_payload["writeRealProviderCount"], len(set(acceptance_payload["writeRealProviders"])))
            self.assertTrue(all(isinstance(item.get("quickActionPath"), str) and item.get("quickActionPath") for item in acceptance_payload["gates"]))
            visual_gate = next(item for item in acceptance_payload["gates"] if item["gateId"] == "visual_regression_production")
            self.assertIn("probeFresh=", visual_gate["actual"])
            visual_farm_gate = next(item for item in acceptance_payload["gates"] if item["gateId"] == "visual_farm_runtime_ready")
            self.assertIn("strictPublishReady=", visual_farm_gate["actual"])
            workspace_market_gate = next(item for item in acceptance_payload["gates"] if item["gateId"] == "market_workspace_readiness")
            self.assertIn("projectCount=", workspace_market_gate["actual"])
            self.assertIn("strictReadyProjects=", workspace_market_gate["actual"])
            workspace_cruise_gate = next(item for item in acceptance_payload["gates"] if item["gateId"] == "workspace_auto_cruise")
            self.assertIn("enabledProjectCount=", workspace_cruise_gate["actual"])
            self.assertIn("overdueProjectCount=", workspace_cruise_gate["actual"])
            acceptance_history = client.get("/api/acceptance/history", params={"limit": 5})
            self.assertEqual(acceptance_history.status_code, 200)
            acceptance_history_payload = acceptance_history.json()
            self.assertIn("entries", acceptance_history_payload)
            self.assertGreaterEqual(acceptance_history_payload["total"], 1)
            self.assertTrue(acceptance_history_payload["entries"])
            self.assertIn("report", acceptance_history_payload["entries"][0])
            product_benchmark = client.get("/api/product-benchmark")
            self.assertEqual(product_benchmark.status_code, 200)
            product_benchmark_payload = product_benchmark.json()
            self.assertEqual(product_benchmark_payload["referenceCount"], 7)
            self.assertGreaterEqual(product_benchmark_payload["capabilityCount"], 6)
            self.assertIn("recommendedNextCapabilityIds", product_benchmark_payload)
            benchmark_ids = {item["capabilityId"] for item in product_benchmark_payload["capabilities"]}
            self.assertIn("real_provider_ingestion_writeback", benchmark_ids)
            self.assertIn("visual_farm_production", benchmark_ids)
            self.assertIn("runtime_edge_multisite", benchmark_ids)
            self.assertTrue(all(0 <= int(item["maturityScore"]) <= 100 for item in product_benchmark_payload["capabilities"]))
            remaining_tasks = client.get("/api/product-benchmark/remaining")
            self.assertEqual(remaining_tasks.status_code, 200)
            remaining_tasks_payload = remaining_tasks.json()
            self.assertIn("items", remaining_tasks_payload)
            self.assertGreaterEqual(remaining_tasks_payload["total"], 1)
            self.assertGreaterEqual(remaining_tasks_payload["blockingCount"], 0)
            self.assertTrue(all(item["status"] in {"blocked", "planned"} for item in remaining_tasks_payload["items"]))
            self.assertTrue(all(item["priority"] in {"p0", "p1", "p2", "p3"} for item in remaining_tasks_payload["items"]))
            self.assertTrue(
                all("quickActionPath" in item and "quickActionLabel" in item for item in remaining_tasks_payload["items"])
            )
            remaining_board = client.get("/api/product-benchmark/remaining/board")
            self.assertEqual(remaining_board.status_code, 200)
            remaining_board_payload = remaining_board.json()
            self.assertIn("groups", remaining_board_payload)
            self.assertGreaterEqual(remaining_board_payload["total"], remaining_board_payload["blockingCount"])
            self.assertTrue(all("groupId" in item and "title" in item for item in remaining_board_payload["groups"]))
            acceptance_history_failed = client.get(
                "/api/acceptance/history",
                params={"limit": 5, "passed": "false", "failedGateId": "real_provider_samples"},
            )
            self.assertEqual(acceptance_history_failed.status_code, 200)
            acceptance_history_failed_payload = acceptance_history_failed.json()
            self.assertIn("entries", acceptance_history_failed_payload)
            self.assertTrue(
                all("real_provider_samples" in item["failedGateIds"] for item in acceptance_history_failed_payload["entries"])
            )

            prompts = client.get("/api/prompts")
            self.assertEqual(prompts.status_code, 200)
            prompt_payload = prompts.json()
            self.assertGreaterEqual(len(prompt_payload["versions"]), 6)

            regression_samples = client.get("/api/regression-samples")
            self.assertEqual(regression_samples.status_code, 200)
            sample_payload = regression_samples.json()
            self.assertEqual(sample_payload["sampleCount"], 10)
            self.assertGreaterEqual(len(sample_payload["samples"]), 10)

            visual_regression = client.get("/api/visual-regressions")
            self.assertEqual(visual_regression.status_code, 200)
            visual_payload = visual_regression.json()
            self.assertEqual(visual_payload["sampleCount"], 10)
            self.assertGreaterEqual(visual_payload["passCount"], 1)

            execute_visual_regression_blocked = client.post(
                "/api/visual-regressions/runs/execute",
                json={"strictMode": False, "projectIds": [project_id], "maxCases": 2},
            )
            self.assertEqual(execute_visual_regression_blocked.status_code, 401)
            execute_visual_regression = client.post(
                "/api/visual-regressions/runs/execute",
                json={"strictMode": False, "projectIds": [project_id], "maxCases": 2},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(execute_visual_regression.status_code, 200)
            execute_payload = execute_visual_regression.json()
            self.assertIn("runs", execute_payload)
            self.assertTrue(execute_payload["runs"])
            self.assertEqual(execute_payload["runs"][0]["strictMode"], False)
            self.assertLessEqual(int(execute_payload["runs"][0]["sampleCount"]), 2)
            enqueue_visual_regression_blocked = client.post(
                "/api/visual-regressions/runs/enqueue",
                json={"strictMode": False, "projectIds": [project_id], "maxCases": 2},
            )
            self.assertEqual(enqueue_visual_regression_blocked.status_code, 401)
            enqueue_visual_regression = client.post(
                "/api/visual-regressions/runs/enqueue",
                json={"strictMode": False, "projectIds": [project_id], "maxCases": 2},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(enqueue_visual_regression.status_code, 200)
            enqueue_payload = enqueue_visual_regression.json()
            self.assertIn("enqueued", enqueue_payload)
            self.assertIn("jobId", enqueue_payload)
            self.assertEqual(enqueue_payload["stage"], "visual_regression")
            visual_run_history = client.get("/api/visual-regressions/runs/history", params={"limit": 5})
            self.assertEqual(visual_run_history.status_code, 200)
            visual_run_history_payload = visual_run_history.json()
            self.assertIn("entries", visual_run_history_payload)
            self.assertTrue(visual_run_history_payload["entries"])
            self.assertIsNone(visual_run_history_payload.get("projectId"))
            self.assertIn("runIds", visual_run_history_payload["entries"][0])
            self.assertIn("caseCount", visual_run_history_payload["entries"][0])
            visual_run_history_project = client.get(
                "/api/visual-regressions/runs/history",
                params={"limit": 5, "projectId": project_id, "strictMode": "false"},
            )
            self.assertEqual(visual_run_history_project.status_code, 200)
            visual_run_history_project_payload = visual_run_history_project.json()
            self.assertEqual(visual_run_history_project_payload["projectId"], project_id)
            self.assertFalse(visual_run_history_project_payload["strictMode"])
            self.assertTrue(visual_run_history_project_payload["entries"])
            self.assertTrue(all(item["projectId"] == project_id for item in visual_run_history_project_payload["entries"]))
            self.assertTrue(all(project_id in item["projectIds"] for item in visual_run_history_project_payload["entries"]))
            visual_remediations = client.get("/api/visual-regressions/remediations")
            self.assertEqual(visual_remediations.status_code, 200)
            visual_remediations_payload = visual_remediations.json()
            self.assertIn("itemCount", visual_remediations_payload)
            self.assertIn("items", visual_remediations_payload)
            if visual_remediations_payload["items"]:
                self.assertIn("retryRequestTemplate", visual_remediations_payload["items"][0])
            visual_farm_status = client.get("/api/visual-farm/status")
            self.assertEqual(visual_farm_status.status_code, 200)
            visual_farm_payload = visual_farm_status.json()
            self.assertIn("configuredEndpointCount", visual_farm_payload)
            self.assertIn("accessTokenConfigured", visual_farm_payload)
            self.assertIn("strictPublishReady", visual_farm_payload)
            self.assertIn("probeFresh", visual_farm_payload)
            self.assertIn("probeStale", visual_farm_payload)
            self.assertIn("lastProbeExecutedAt", visual_farm_payload)
            self.assertIn("failureBuckets", visual_farm_payload)
            visual_farm_probe_blocked = client.get("/api/visual-farm/probe")
            self.assertEqual(visual_farm_probe_blocked.status_code, 401)
            visual_farm_probe = client.get("/api/visual-farm/probe", headers={"X-API-Key": "dev-key"})
            self.assertEqual(visual_farm_probe.status_code, 200)
            visual_farm_probe_payload = visual_farm_probe.json()
            self.assertEqual(visual_farm_probe_payload.get("projectId"), None)
            self.assertIn("configuredEndpointCount", visual_farm_probe_payload)
            self.assertIn("probedEndpointCount", visual_farm_probe_payload)
            self.assertIn("connectedCount", visual_farm_probe_payload)
            self.assertIn("failedCount", visual_farm_probe_payload)
            self.assertIn("blockingCount", visual_farm_probe_payload)
            self.assertIn("recoverableCount", visual_farm_probe_payload)
            self.assertIn("probes", visual_farm_probe_payload)
            visual_farm_probe_project = client.get(
                "/api/visual-farm/probe",
                params={"projectId": project_id},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(visual_farm_probe_project.status_code, 200)
            visual_farm_probe_project_payload = visual_farm_probe_project.json()
            self.assertEqual(visual_farm_probe_project_payload["projectId"], project_id)
            with service.database.session() as session:
                project_probe_events = session.scalars(
                    select(AuditRow).where(
                        AuditRow.action == "visual_farm.probe.executed",
                        AuditRow.project_id == project_id,
                    )
                ).all()
            self.assertGreaterEqual(len(project_probe_events), 1)
            self.assertTrue(all(event.project_id == project_id for event in project_probe_events))
            visual_farm_enqueue_blocked = client.post("/api/visual-farm/probe/enqueue")
            self.assertEqual(visual_farm_enqueue_blocked.status_code, 401)
            visual_farm_enqueue = client.post("/api/visual-farm/probe/enqueue", headers={"X-API-Key": "dev-key"})
            self.assertEqual(visual_farm_enqueue.status_code, 200)
            visual_farm_enqueue_payload = visual_farm_enqueue.json()
            self.assertIn("enqueued", visual_farm_enqueue_payload)
            self.assertIn("jobId", visual_farm_enqueue_payload)
            self.assertEqual(visual_farm_enqueue_payload["stage"], "visual_farm_probe")
            runtime_ingress_enqueue_blocked = client.post(
                "/api/runtime-ingress/bundle/batch/enqueue",
                json={"projectIds": [project_id], "strictRoutesOnly": True, "actor": "qa"},
            )
            self.assertEqual(runtime_ingress_enqueue_blocked.status_code, 401)
            runtime_ingress_enqueue = client.post(
                "/api/runtime-ingress/bundle/batch/enqueue",
                json={"projectIds": [project_id], "strictRoutesOnly": True, "actor": "qa"},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(runtime_ingress_enqueue.status_code, 200)
            runtime_ingress_enqueue_payload = runtime_ingress_enqueue.json()
            self.assertTrue(runtime_ingress_enqueue_payload["enqueued"])
            self.assertEqual(runtime_ingress_enqueue_payload["stage"], "runtime_ingress_bundle_batch")
            self.assertIn(project_id, runtime_ingress_enqueue_payload["projectIds"])
            self.assertTrue(runtime_ingress_enqueue_payload["strictRoutesOnly"])
            visual_farm_probe_history = client.get("/api/visual-farm/probe/history", params={"limit": 5})
            self.assertEqual(visual_farm_probe_history.status_code, 200)
            visual_farm_probe_history_payload = visual_farm_probe_history.json()
            self.assertIn("entries", visual_farm_probe_history_payload)
            self.assertTrue(visual_farm_probe_history_payload["entries"])
            self.assertEqual(visual_farm_probe_history_payload["summary"]["totalCount"], len(visual_farm_probe_history_payload["entries"]))
            self.assertIsNone(visual_farm_probe_history_payload.get("projectId"))
            first_probe_entry = visual_farm_probe_history_payload["entries"][0]
            self.assertIn("auditId", first_probe_entry)
            self.assertIn("strictMode", first_probe_entry)
            self.assertIn("probedEndpointCount", first_probe_entry)
            self.assertIn("connectedCount", first_probe_entry)
            self.assertIn("failedCount", first_probe_entry)
            self.assertIn("blockingCount", first_probe_entry)
            self.assertIn("recoverableCount", first_probe_entry)
            self.assertIn("spanId", first_probe_entry)
            self.assertIn("traceId", first_probe_entry)
            visual_farm_probe_history_project = client.get(
                "/api/visual-farm/probe/history",
                params={"limit": 5, "projectId": project_id, "strictMode": "false"},
            )
            self.assertEqual(visual_farm_probe_history_project.status_code, 200)
            visual_farm_probe_history_project_payload = visual_farm_probe_history_project.json()
            self.assertEqual(visual_farm_probe_history_project_payload["projectId"], project_id)
            self.assertFalse(visual_farm_probe_history_project_payload["strictMode"])
            self.assertTrue(visual_farm_probe_history_project_payload["entries"])
            self.assertEqual(visual_farm_probe_history_project_payload["summary"]["totalCount"], len(visual_farm_probe_history_project_payload["entries"]))
            self.assertTrue(
                all(entry["projectId"] == project_id for entry in visual_farm_probe_history_project_payload["entries"])
            )

            skill_regression = client.get("/api/skill-regressions")
            self.assertEqual(skill_regression.status_code, 200)
            skill_payload = skill_regression.json()
            self.assertGreaterEqual(skill_payload["sampleCount"], 3)
            self.assertGreaterEqual(skill_payload["passCount"], 1)

            connector_failures = client.get("/api/connectors/failures")
            self.assertEqual(connector_failures.status_code, 200)
            connector_failure_payload = connector_failures.json()
            self.assertIn("totalFailures", connector_failure_payload)
            self.assertIn("entries", connector_failure_payload)
            connector_failures_project = client.get(
                "/api/connectors/failures",
                params={"projectId": project_id},
            )
            self.assertEqual(connector_failures_project.status_code, 200)
            connector_failures_project_payload = connector_failures_project.json()
            self.assertEqual(connector_failures_project_payload["projectId"], project_id)
            self.assertTrue(
                all(project_id in entry["projectIds"] for entry in connector_failures_project_payload["entries"])
            )

            retry_connectors = client.post(
                "/api/connectors/retry",
                json={"categories": ["network"], "projectIds": [project_id], "providers": [], "retryableOnly": True, "maxRetries": 10},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(retry_connectors.status_code, 200)
            self.assertIn("attempted", retry_connectors.json())

            retry_visual = client.post(
                "/api/visual-regressions/retry",
                json={
                    "projectIds": [project_id],
                    "categories": ["network", "unavailable"],
                    "retryableOnly": True,
                    "maxCases": 5,
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(retry_visual.status_code, 200)
            retry_visual_payload = retry_visual.json()
            self.assertIn("attempted", retry_visual_payload)
            self.assertIn("rerunPassed", retry_visual_payload)
            self.assertIn("rerunFailed", retry_visual_payload)
            retry_visual_history = client.get("/api/visual-regressions/retry/history")
            self.assertEqual(retry_visual_history.status_code, 200)
            retry_visual_history_payload = retry_visual_history.json()
            self.assertIn("entries", retry_visual_history_payload)
            self.assertIsNone(retry_visual_history_payload.get("projectId"))
            retry_visual_history_project = client.get(
                "/api/visual-regressions/retry/history",
                params={"limit": 10, "projectId": project_id},
            )
            self.assertEqual(retry_visual_history_project.status_code, 200)
            retry_visual_history_project_payload = retry_visual_history_project.json()
            self.assertEqual(retry_visual_history_project_payload["projectId"], project_id)

            retry_history = client.get("/api/connectors/retry/history")
            self.assertEqual(retry_history.status_code, 200)
            retry_history_payload = retry_history.json()
            self.assertIn("entries", retry_history_payload)
            self.assertIn("strictMode", retry_history_payload)
            if retry_history_payload["entries"]:
                self.assertIn("strictMode", retry_history_payload["entries"][0])
            retry_history_project = client.get(
                "/api/connectors/retry/history",
                params={"limit": 10, "projectId": project_id},
            )
            self.assertEqual(retry_history_project.status_code, 200)
            retry_history_project_payload = retry_history_project.json()
            self.assertEqual(retry_history_project_payload["projectId"], project_id)
            self.assertTrue(retry_history_project_payload["entries"])
            self.assertTrue(
                all(project_id in item["projectIds"] for item in retry_history_project_payload["entries"])
            )

            remediations = client.get("/api/connectors/remediations")
            self.assertEqual(remediations.status_code, 200)
            remediation_payload = remediations.json()
            self.assertIn("items", remediation_payload)
            self.assertIn("strictMode", remediation_payload)
            remediations_blocking = client.get("/api/connectors/remediations", params={"blocking": "true", "limit": 5})
            self.assertEqual(remediations_blocking.status_code, 200)
            self.assertTrue(all(item["blocking"] is True for item in remediations_blocking.json().get("items", [])))
            remediations_provider = client.get("/api/connectors/remediations", params={"provider": "search_console"})
            self.assertEqual(remediations_provider.status_code, 200)
            self.assertTrue(
                all(
                    "search_console" in [str(value).lower() for value in item.get("providers", [])]
                    for item in remediations_provider.json().get("items", [])
                )
            )
            remediations_project = client.get("/api/connectors/remediations", params={"projectId": project_id})
            self.assertEqual(remediations_project.status_code, 200)
            self.assertTrue(all(project_id in item.get("projectIds", []) for item in remediations_project.json().get("items", [])))
            remediations_invalid = client.get("/api/connectors/remediations", params={"category": "invalid"})
            self.assertEqual(remediations_invalid.status_code, 422)

            bulk = client.post(
                "/api/tasks/bulk/approve",
                json={"taskIds": [task_id, "missing-task"], "actor": "test", "note": "bulk approve"},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(bulk.status_code, 200)
            bulk_payload = bulk.json()
            self.assertEqual(bulk_payload["approvedCount"], 1)
            self.assertEqual(bulk_payload["skippedTaskIds"], ["missing-task"])

            bulk_sync = client.post(
                "/api/bulk/projects/sync",
                json={"projectIds": [project_id, "missing-project"], "trigger": "manual", "force": True},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(bulk_sync.status_code, 200)
            bulk_sync_payload = bulk_sync.json()
            self.assertEqual(bulk_sync_payload["processedCount"], 1)
            self.assertEqual(bulk_sync_payload["skippedProjectIds"], ["missing-project"])

            bulk_test = client.post(
                "/api/bulk/projects/connections/test",
                json={"projectIds": [project_id, "missing-project"]},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(bulk_test.status_code, 200)
            bulk_test_payload = bulk_test.json()
            self.assertEqual(bulk_test_payload["testedCount"], 1)
            self.assertEqual(bulk_test_payload["skippedProjectIds"], ["missing-project"])

            bulk_refresh_blocked = client.post(
                "/api/bulk/projects/connectors/search_console/refresh",
                json={"projectIds": [project_id]},
            )
            self.assertEqual(bulk_refresh_blocked.status_code, 401)
            bulk_refresh = client.post(
                "/api/bulk/projects/connectors/search_console/refresh",
                json={"projectIds": [project_id, "missing-project"]},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(bulk_refresh.status_code, 200)
            bulk_refresh_payload = bulk_refresh.json()
            self.assertEqual(bulk_refresh_payload["provider"], "search_console")
            self.assertEqual(bulk_refresh_payload["refreshedCount"], 1)
            self.assertEqual(bulk_refresh_payload["skippedProjectIds"], ["missing-project"])
            strict_gap_refresh_blocked = client.post(
                "/api/bulk/connectors/strict-gap/refresh",
                json={"projectIds": [project_id], "maxProviders": 3},
            )
            self.assertEqual(strict_gap_refresh_blocked.status_code, 401)
            strict_gap_refresh = client.post(
                "/api/bulk/connectors/strict-gap/refresh",
                json={"projectIds": [project_id], "maxProviders": 3},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(strict_gap_refresh.status_code, 200)
            strict_gap_refresh_payload = strict_gap_refresh.json()
            self.assertIn("providerCount", strict_gap_refresh_payload)
            self.assertIn("providerResults", strict_gap_refresh_payload)
            blocking_refresh_blocked = client.post(
                "/api/bulk/connectors/blocking/refresh",
                json={"projectIds": [project_id], "maxProviders": 3},
            )
            self.assertEqual(blocking_refresh_blocked.status_code, 401)
            blocking_refresh = client.post(
                "/api/bulk/connectors/blocking/refresh",
                json={"projectIds": [project_id], "maxProviders": 3},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(blocking_refresh.status_code, 200)
            blocking_refresh_payload = blocking_refresh.json()
            self.assertIn("providerCount", blocking_refresh_payload)
            self.assertIn("providerResults", blocking_refresh_payload)
            bulk_action_history = client.get("/api/connectors/bulk-actions/history", params={"limit": 5})
            self.assertEqual(bulk_action_history.status_code, 200)
            bulk_action_history_payload = bulk_action_history.json()
            self.assertIn("entries", bulk_action_history_payload)
            self.assertIsInstance(bulk_action_history_payload["entries"], list)
            bulk_action_history_filtered = client.get(
                "/api/connectors/bulk-actions/history",
                params={"limit": 5, "action": "strict_gap"},
            )
            self.assertEqual(bulk_action_history_filtered.status_code, 200)
            bulk_action_history_provider = client.get(
                "/api/connectors/bulk-actions/history",
                params={"limit": 5, "provider": "search_console"},
            )
            self.assertEqual(bulk_action_history_provider.status_code, 200)
            provider_entries = bulk_action_history_provider.json()["entries"]
            self.assertTrue(
                all("search_console" in [str(item).lower() for item in entry.get("providers", [])] for entry in provider_entries)
            )
            bulk_action_history_project = client.get(
                "/api/connectors/bulk-actions/history",
                params={"limit": 5, "projectId": project_id},
            )
            self.assertEqual(bulk_action_history_project.status_code, 200)
            bulk_action_history_project_payload = bulk_action_history_project.json()
            self.assertEqual(bulk_action_history_project_payload["projectId"], project_id)
            project_entries = bulk_action_history_project_payload["entries"]
            self.assertTrue(all(project_id in entry.get("projectIds", []) for entry in project_entries))

            detail = client.get(f"/api/projects/{project_id}")
            self.assertEqual(detail.status_code, 200)
            detail_payload = detail.json()
            self.assertIn(detail.headers["X-SEO-AD-Runtime-Ready"], {"true", "false"})
            self.assertTrue(detail.headers["X-SEO-AD-Route-Gateway"])
            self.assertIn("contentStrategy", detail_payload)
            self.assertIn("adAudit", detail_payload)
            self.assertIn("technicalSeo", detail_payload)
            self.assertIn("businessClassifier", detail_payload)
            self.assertIn("styleExtraction", detail_payload)
            self.assertIn("adaptiveComponents", detail_payload)
            self.assertIn("technicalSeoPatch", detail_payload)
            self.assertIn("marketEvidence", detail_payload)
            self.assertEqual(detail_payload["project"]["projectId"], project_id)

            business_classifier = client.get(f"/api/projects/{project_id}/business-classifier")
            self.assertEqual(business_classifier.status_code, 200)
            self.assertEqual(business_classifier.json()["siteId"], project_id)

            style_extraction = client.get(f"/api/projects/{project_id}/style-extraction")
            self.assertEqual(style_extraction.status_code, 200)
            self.assertEqual(style_extraction.json()["projectId"], project_id)

            content_strategy = client.get(f"/api/projects/{project_id}/content-strategy")
            self.assertEqual(content_strategy.status_code, 200)
            self.assertEqual(content_strategy.json()["projectId"], project_id)

            ad_audit = client.get(f"/api/projects/{project_id}/ad-audit")
            self.assertEqual(ad_audit.status_code, 200)
            self.assertEqual(ad_audit.json()["projectId"], project_id)
            self.assertIn("pageFindings", ad_audit.json())
            self.assertIn("templateCoverage", ad_audit.json())

            adaptive_components = client.get(f"/api/projects/{project_id}/adaptive-components")
            self.assertEqual(adaptive_components.status_code, 200)
            self.assertEqual(adaptive_components.json()["projectId"], project_id)

            technical_seo = client.get(f"/api/projects/{project_id}/technical-seo")
            self.assertEqual(technical_seo.status_code, 200)
            self.assertEqual(technical_seo.json()["projectId"], project_id)

            technical_seo_patch = client.get(f"/api/projects/{project_id}/technical-seo-patch")
            self.assertEqual(technical_seo_patch.status_code, 200)
            self.assertEqual(technical_seo_patch.json()["projectId"], project_id)
            self.assertIn("steps", technical_seo_patch.json())

            market_evidence = client.get(f"/api/projects/{project_id}/market-evidence")
            self.assertEqual(market_evidence.status_code, 200)
            market_evidence_payload = market_evidence.json()
            self.assertEqual(market_evidence_payload["projectId"], project_id)
            self.assertIn("trend", market_evidence_payload)
            self.assertIn("news", market_evidence_payload)
            self.assertIn("qa", market_evidence_payload)
            self.assertIn("summaries", market_evidence_payload)
            self.assertEqual(len(market_evidence_payload["summaries"]), 3)
            self.assertTrue(all("connectedCount" in item for item in market_evidence_payload["summaries"]))
            self.assertTrue(all("syntheticCount" in item for item in market_evidence_payload["summaries"]))
            self.assertTrue(all("failedCount" in item for item in market_evidence_payload["summaries"]))
            self.assertTrue(all("connectedEndpoints" in item for item in market_evidence_payload["summaries"]))
            self.assertTrue(all("connectedSourceRefs" in item for item in market_evidence_payload["summaries"]))
            self.assertTrue(all("averageLatencyMs" in item for item in market_evidence_payload["summaries"]))

            alerts_blocked = client.get("/api/alerts")
            self.assertEqual(alerts_blocked.status_code, 401)
            alerts = client.get("/api/alerts", headers={"X-API-Key": "dev-key"})
            self.assertEqual(alerts.status_code, 200)
            alert_payload = alerts.json()
            self.assertIn("blocking", alert_payload)
            self.assertIn("recoverable", alert_payload)
            alerts_project = client.get("/api/alerts", params={"projectId": project_id}, headers={"X-API-Key": "dev-key"})
            self.assertEqual(alerts_project.status_code, 200)
            self.assertEqual(alerts_project.json()["projectId"], project_id)
            emit_blocked = client.post("/api/alerts/emit")
            self.assertEqual(emit_blocked.status_code, 401)
            emit = client.post("/api/alerts/emit", headers={"X-API-Key": "dev-key"})
            self.assertEqual(emit.status_code, 200)
            emit_payload = emit.json()
            self.assertIn("blocking", emit_payload)
            self.assertIn("recoverable", emit_payload)
            latest_alerts = client.get("/api/alerts/latest")
            self.assertEqual(latest_alerts.status_code, 200)
            latest_alert_payload = latest_alerts.json()
            self.assertIn("blocking", latest_alert_payload)
            self.assertIn("recoverable", latest_alert_payload)
            self.assertIn("notes", latest_alert_payload)
            latest_alerts_project = client.get("/api/alerts/latest", params={"projectId": project_id})
            self.assertEqual(latest_alerts_project.status_code, 200)
            self.assertEqual(latest_alerts_project.json()["projectId"], project_id)
            emit_status = client.get("/api/alerts/emit/status")
            self.assertEqual(emit_status.status_code, 200)
            emit_status_payload = emit_status.json()
            self.assertIn("cooldownSeconds", emit_status_payload)
            self.assertIn("executedCount24h", emit_status_payload)
            self.assertIn("suppressedCount24h", emit_status_payload)
            self.assertIn("notes", emit_status_payload)
            emit_status_project = client.get("/api/alerts/emit/status", params={"projectId": project_id})
            self.assertEqual(emit_status_project.status_code, 200)
            self.assertEqual(emit_status_project.json()["projectId"], project_id)
            emit_history = client.get("/api/alerts/emit/history", params={"limit": 5})
            self.assertEqual(emit_history.status_code, 200)
            emit_history_payload = emit_history.json()
            self.assertIn("total", emit_history_payload)
            self.assertIn("executed", emit_history_payload)
            self.assertIn("suppressed", emit_history_payload)
            self.assertIn("entries", emit_history_payload)
            self.assertIn("projectId", emit_history_payload)
            self.assertTrue(all("projectIds" in entry for entry in emit_history_payload["entries"]))

            emit_history_project = client.get("/api/alerts/emit/history", params={"limit": 5, "projectId": project_id})
            self.assertEqual(emit_history_project.status_code, 200)
            emit_history_project_payload = emit_history_project.json()
            self.assertEqual(emit_history_project_payload["projectId"], project_id)
            self.assertTrue(all(project_id in entry["projectIds"] for entry in emit_history_project_payload["entries"]))

            alert_deliveries = client.get("/api/alerts/deliveries", params={"limit": 5, "projectId": project_id})
            self.assertEqual(alert_deliveries.status_code, 200)
            alert_deliveries_payload = alert_deliveries.json()
            self.assertEqual(alert_deliveries_payload["projectId"], project_id)
            self.assertTrue(all(project_id in entry["projectIds"] for entry in alert_deliveries_payload["entries"]))

            alert_filter = client.get("/api/alerts", params={"blocking": "true"}, headers={"X-API-Key": "dev-key"})
            self.assertEqual(alert_filter.status_code, 200)
            filtered_payload = alert_filter.json()
            self.assertTrue(all(item["blocking"] for item in filtered_payload["blocking"]))
            self.assertEqual(filtered_payload["recoverable"], [])

            alert_history = client.get("/api/alerts/history")
            self.assertEqual(alert_history.status_code, 200)
            alert_history_payload = alert_history.json()
            self.assertGreaterEqual(len(alert_history_payload["snapshots"]), 1)
            self.assertIn("total", alert_history_payload)
            self.assertIn("limit", alert_history_payload)
            self.assertIn("offset", alert_history_payload)
            self.assertIn("order", alert_history_payload)

            alert_history_paged = client.get("/api/alerts/history", params={"limit": 1, "offset": 0, "order": "asc"})
            self.assertEqual(alert_history_paged.status_code, 200)
            paged_payload = alert_history_paged.json()
            self.assertEqual(paged_payload["limit"], 1)
            self.assertEqual(paged_payload["offset"], 0)
            self.assertEqual(paged_payload["order"], "asc")
            self.assertLessEqual(len(paged_payload["snapshots"]), 1)
            self.assertIn("hasMore", paged_payload)
            self.assertIn("nextCursor", paged_payload)

            cursor = paged_payload.get("nextCursor")
            if cursor:
                alert_history_cursor = client.get("/api/alerts/history", params={"limit": 1, "order": "asc", "cursor": cursor})
                self.assertEqual(alert_history_cursor.status_code, 200)
                cursor_payload = alert_history_cursor.json()
                self.assertEqual(cursor_payload["cursor"], cursor)

            alert_history_project = client.get("/api/alerts/history", params={"projectId": project_id, "limit": 5})
            self.assertEqual(alert_history_project.status_code, 200)
            alert_history_project_payload = alert_history_project.json()
            self.assertEqual(alert_history_project_payload["projectId"], project_id)
            self.assertTrue(
                all(
                    project_id in item["projectIds"]
                    for snapshot in alert_history_project_payload["snapshots"]
                    for item in snapshot["blocking"] + snapshot["recoverable"]
                )
            )

            alert_presets = client.get("/api/alerts/presets")
            self.assertEqual(alert_presets.status_code, 200)
            self.assertIn("presets", alert_presets.json())

            updated_presets = client.put(
                "/api/alerts/presets",
                json={
                    "presets": [
                        {
                            "presetId": "project_alerts",
                            "name": "project_alerts",
                            "description": "Project specific alerts",
                            "projectIds": [project_id],
                            "categories": ["network"],
                            "severities": ["warning"],
                            "providers": [],
                            "blocking": False,
                        }
                    ]
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated_presets.status_code, 200)
            project_presets = client.get("/api/alerts/presets", params={"projectId": project_id})
            self.assertEqual(project_presets.status_code, 200)
            project_presets_payload = project_presets.json()
            self.assertEqual(project_presets_payload["projectId"], project_id)
            self.assertTrue(all(project_id in item["projectIds"] for item in project_presets_payload["presets"]))

            alert_rules_before = client.get("/api/alerts/rules")
            self.assertEqual(alert_rules_before.status_code, 200)
            self.assertIn("rules", alert_rules_before.json())

            updated_rules = client.put(
                "/api/alerts/rules",
                json={
                    "rules": [
                        {
                            "ruleId": "network_is_info_nonblocking",
                            "enabled": True,
                            "description": "Relax network alerts in demo mode",
                            "categories": ["network", "rate_limit"],
                            "failureCodes": [],
                            "providers": [],
                            "setBlocking": False,
                            "setSeverity": "info",
                            "priority": 1,
                        }
                    ]
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated_rules.status_code, 200)
            self.assertTrue(any(item["ruleId"] == "network_is_info_nonblocking" for item in updated_rules.json()["rules"]))

            updated_presets = client.put(
                "/api/alerts/presets",
                json={
                    "presets": [
                        {
                            "presetId": "custom_auth_only",
                            "name": "custom_auth_only",
                            "description": "Only auth category",
                            "projectIds": [],
                            "categories": ["auth"],
                            "severities": [],
                            "providers": [],
                            "blocking": True,
                            "updatedAt": "2026-01-01T00:00:00Z",
                        }
                    ]
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated_presets.status_code, 200)
            self.assertTrue(any(item["presetId"] == "custom_auth_only" for item in updated_presets.json()["presets"]))

            worker_blocked = client.post("/api/worker/run-once")
            self.assertEqual(worker_blocked.status_code, 401)

    def test_prompt_registry_write_and_activate(self) -> None:
        service = self._service()
        app = create_app(service)
        with TestClient(app) as client:
            baseline = client.get("/api/prompts")
            self.assertEqual(baseline.status_code, 200)
            self.assertTrue(baseline.json()["versions"])

            denied = client.post(
                "/api/prompts/versions",
                json={
                    "version": {
                        "promptId": "query-opportunity-discovery",
                        "role": "query",
                        "name": "Opportunity discovery prompt",
                        "version": "v1.1.1",
                        "status": "draft",
                        "owner": "growth-strategy",
                        "summary": "Adds explicit source-quality guardrails.",
                        "checksum": "sha256:999999999999",
                        "lastReviewedAt": "2026-01-01T00:00:00Z",
                        "usedBy": ["Strategist"],
                        "notes": ["candidate"],
                    }
                },
            )
            self.assertEqual(denied.status_code, 401)

            upserted = client.post(
                "/api/prompts/versions",
                json={
                    "version": {
                        "promptId": "query-opportunity-discovery",
                        "role": "query",
                        "name": "Opportunity discovery prompt",
                        "version": "v1.1.1",
                        "status": "draft",
                        "owner": "growth-strategy",
                        "summary": "Adds explicit source-quality guardrails.",
                        "checksum": "sha256:999999999999",
                        "lastReviewedAt": "2026-01-01T00:00:00Z",
                        "usedBy": ["Strategist"],
                        "notes": ["candidate"],
                    }
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(upserted.status_code, 200)
            self.assertTrue(
                any(
                    item["promptId"] == "query-opportunity-discovery" and item["version"] == "v1.1.1"
                    for item in upserted.json()["versions"]
                )
            )

            activated = client.post(
                "/api/prompts/query-opportunity-discovery/activate",
                json={"version": "v1.1.1"},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(activated.status_code, 200)
            active_versions = [
                item
                for item in activated.json()["versions"]
                if item["promptId"] == "query-opportunity-discovery" and item["status"] == "active"
            ]
            self.assertEqual(len(active_versions), 1)
            self.assertEqual(active_versions[0]["version"], "v1.1.1")

            invalid = client.put(
                "/api/prompts",
                json={
                    "versions": [
                        {
                            "promptId": "query-opportunity-discovery",
                            "role": "query",
                            "name": "Bad checksum prompt",
                            "version": "v1.1.2",
                            "status": "draft",
                            "owner": "growth-strategy",
                            "summary": "Invalid checksum format should fail.",
                            "checksum": "md5:abc",
                            "lastReviewedAt": "2026-01-01T00:00:00Z",
                            "usedBy": [],
                            "notes": [],
                        }
                    ],
                    "notes": [],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(invalid.status_code, 422)

    def test_acceptance_report_strict_gate_blocks_on_strict_gap(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Gap Site",
                intake=SiteIntake(
                    url="https://strict-gap.example",
                    site_name="Strict Gap Site",
                    repo_url="https://github.com/example/strict-gap",
                    brand_whitelist=["StrictGap"],
                ),
            )
        )
        service.sync_project(project.project_id)
        report = service.build_acceptance_report()
        self.assertTrue(report.strict_providers_enabled)
        strict_gate = next(item for item in report.gates if item.gate_id == "strict_providers")
        self.assertIn("strictProviders=true", strict_gate.actual)
        self.assertFalse(strict_gate.passed)

    def test_acceptance_report_playwright_antibot_gate_blocks_on_manual_intervention(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        service = self._service()
        workspace_health = service.get_workspace_connectors_health()
        injected_health = workspace_health.model_copy(
            update={
                "anti_bot_blocked_connection_count": 1,
                "anti_bot_manual_intervention_count": 1,
            }
        )
        with patch.object(service, "get_workspace_connectors_health", return_value=injected_health):
            report = service.build_acceptance_report()
        anti_bot_gate = next(item for item in report.gates if item.gate_id == "playwright_antibot_clear")
        self.assertFalse(anti_bot_gate.passed)
        self.assertIn("strictProviders=true", anti_bot_gate.actual)
        self.assertIn("antiBotBlocked=1", anti_bot_gate.actual)
        self.assertIn("antiBotManualIntervention=1", anti_bot_gate.actual)

    def test_acceptance_report_worker_service_gate_blocks_when_state_file_missing_in_strict_mode(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_WORKER_STATE_FILE"] = str(Path(self._tempdir.name) / "missing-worker-state.json")
        service = self._service()
        report = service.build_acceptance_report()
        worker_gate = next(item for item in report.gates if item.gate_id == "worker_service_ready")
        self.assertFalse(worker_gate.passed)
        self.assertIn("strictProviders=true", worker_gate.actual)
        self.assertIn("stateFileFound=false", worker_gate.actual)

    def test_acceptance_report_visual_farm_gate_requires_strict_publish_ready(self) -> None:
        service = self._service()
        ready_status = VisualFarmStatusReport(
            strict_mode=True,
            configured_endpoint_count=1,
            configured_endpoints=["https://visual-farm.example"],
            access_token_configured=True,
            timeout_ms=2500,
            run_count=1,
            last_run_id="visual-run-1",
            last_run_executed_at=datetime.now(timezone.utc),
            last_run_connected_case_count=1,
            last_run_failed_case_count=0,
            last_run_fallback_case_count=0,
            last_run_not_configured_case_count=0,
            last_run_strict_blocked_case_count=0,
            probe_freshness_minutes=30,
            last_probe_executed_at=datetime.now(timezone.utc),
            last_probe_connected_count=1,
            last_probe_failed_count=0,
            last_probe_blocking_count=0,
            last_probe_recoverable_count=0,
            probe_fresh=True,
            probe_stale=False,
            strict_publish_ready=True,
            failure_buckets=[],
            notes=["visual farm ready"],
        )
        with patch.object(service, "build_visual_farm_status_report", return_value=ready_status):
            report = service.build_acceptance_report()
        visual_gate = next(item for item in report.gates if item.gate_id == "visual_farm_runtime_ready")
        self.assertTrue(visual_gate.passed)
        self.assertIn("strictPublishReady=true", visual_gate.actual)
        self.assertIn("tokenConfigured=true", visual_gate.actual)

    def test_acceptance_report_alert_delivery_gate_is_present(self) -> None:
        service = self._service()
        report = service.build_acceptance_report()
        alert_gate = next(item for item in report.gates if item.gate_id == "alert_delivery_ready")
        self.assertIn("routeCount=", alert_gate.actual)
        self.assertIn("deliveries=", alert_gate.actual)

    def test_acceptance_report_real_provider_gate_requires_fresh_evidence_in_strict_mode(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_PROVIDER_EVIDENCE_FRESHNESS_MINUTES"] = "60"
        service = self._service()
        stale_at = datetime.now(timezone.utc) - timedelta(days=2)
        stale_evidence = WorkspaceConnectionEvidenceReport(
            total=2,
            real_count=2,
            fallback_count=0,
            unconfigured_count=0,
            entries=[
                WorkspaceConnectionEvidenceEntry(
                    project_id="project_read_stale",
                    project_name="Read Stale",
                    project_url="https://read-stale.example",
                    provider=ConnectorKind.search_console,
                    label="Search Console",
                    status=ConnectorStatus.connected,
                    provider_mode="real",
                    strict_eligible=True,
                    recent_evidence_label="sc property",
                    recent_evidence_ref="sc://property",
                    recent_evidence_at=stale_at,
                ),
                WorkspaceConnectionEvidenceEntry(
                    project_id="project_write_stale",
                    project_name="Write Stale",
                    project_url="https://write-stale.example",
                    provider=ConnectorKind.github,
                    label="GitHub",
                    status=ConnectorStatus.connected,
                    provider_mode="real",
                    strict_eligible=True,
                    recent_evidence_label="github pr",
                    recent_evidence_ref="https://github.com/example/repo/pull/1",
                    recent_evidence_at=stale_at,
                ),
            ],
            provider_summaries=[],
        )
        with patch.object(service, "get_workspace_connection_evidence", return_value=stale_evidence):
            report = service.build_acceptance_report()
        provider_gate = next(item for item in report.gates if item.gate_id == "real_provider_samples")
        self.assertFalse(provider_gate.passed)
        self.assertIn("readRealEvidence=1", provider_gate.actual)
        self.assertIn("writeRealEvidence=1", provider_gate.actual)
        self.assertIn("readFreshEvidence=0", provider_gate.actual)
        self.assertIn("writeFreshEvidence=0", provider_gate.actual)

    def test_acceptance_report_market_evidence_gate_requires_fresh_connected_sources_in_strict_mode(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_PROVIDER_EVIDENCE_FRESHNESS_MINUTES"] = "60"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Market Evidence Site",
                intake=SiteIntake(
                    url="https://market-evidence.example",
                    site_name="Market Evidence Site",
                    repo_url="https://github.com/example/market-evidence",
                    brand_whitelist=["MarketEvidence"],
                ),
            )
        )
        stale_at = datetime.now(timezone.utc) - timedelta(days=2)
        stale_market_report = MarketEvidenceReport(
            report_id="market-stale",
            project_id=project.project_id,
            trend=[
                SourceEvidence(
                    provider=ConnectorKind.trend,
                    status=ConnectorStatus.connected,
                    summary="trend sample",
                    provenance=["live"],
                    source_type="trend",
                    source_ref="trend://sample",
                    fetched_at=stale_at,
                    latency_ms=12,
                    auth_source="api-key",
                )
            ],
            news=[
                SourceEvidence(
                    provider=ConnectorKind.news,
                    status=ConnectorStatus.synthetic,
                    summary="news sample",
                    provenance=["fallback"],
                    source_type="news",
                    source_ref="news://sample",
                    fetched_at=stale_at,
                    fallback_reason="provider unavailable",
                )
            ],
            qa=[],
            summaries=[],
            notes=["stale market evidence fixture"],
        )
        with patch.object(service, "build_market_evidence_report", return_value=stale_market_report):
            report = service.build_acceptance_report()
        market_gate = next(item for item in report.gates if item.gate_id == "market_evidence_freshness")
        self.assertFalse(market_gate.passed)
        self.assertIn("marketConnected=1", market_gate.actual)
        self.assertIn("marketFresh=0", market_gate.actual)
        self.assertIn("freshnessMinutes=60", market_gate.actual)

    def test_acceptance_report_market_evidence_gate_allows_connected_sources_without_strict_mode(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "false"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Market Evidence Site",
                intake=SiteIntake(
                    url="https://market-evidence.example",
                    site_name="Market Evidence Site",
                    repo_url="https://github.com/example/market-evidence",
                    brand_whitelist=["MarketEvidence"],
                ),
            )
        )
        connected_market_report = MarketEvidenceReport(
            report_id="market-connected",
            project_id=project.project_id,
            trend=[
                SourceEvidence(
                    provider=ConnectorKind.trend,
                    status=ConnectorStatus.connected,
                    summary="trend sample",
                    provenance=["live"],
                    source_type="trend",
                    source_ref="trend://sample",
                    fetched_at=datetime.now(timezone.utc) - timedelta(days=2),
                    latency_ms=12,
                    auth_source="api-key",
                )
            ],
            news=[],
            qa=[],
            summaries=[],
            notes=["connected market evidence fixture"],
        )
        with patch.object(service, "build_market_evidence_report", return_value=connected_market_report):
            report = service.build_acceptance_report()
        market_gate = next(item for item in report.gates if item.gate_id == "market_evidence_freshness")
        self.assertTrue(market_gate.passed)
        self.assertIn("marketConnected=1", market_gate.actual)
        self.assertIn("marketFresh=0", market_gate.actual)

    def test_acceptance_report_market_workspace_readiness_gate_requires_strict_ready_project(self) -> None:
        service = self._service()
        workspace_market_report = WorkspaceMarketEvidenceHealthReport(
            report_id="workspace-market-ready",
            project_count=1,
            connected_count=1,
            synthetic_count=0,
            failed_count=0,
            fresh_count=1,
            stale_count=0,
            strict_ready_project_count=1,
            strict_ready_project_rate_percent=100.0,
            latest_fetched_at=datetime.now(timezone.utc),
            strict_ready_project_ids=["project-market-ready"],
            stale_project_ids=[],
            notes=["workspace market evidence ready"],
        )
        with patch.object(service, "build_workspace_market_evidence_health_report", return_value=workspace_market_report):
            report = service.build_acceptance_report()
        workspace_gate = next(item for item in report.gates if item.gate_id == "market_workspace_readiness")
        self.assertTrue(workspace_gate.passed)
        self.assertIn("projectCount=1", workspace_gate.actual)
        self.assertIn("strictReadyProjects=1", workspace_gate.actual)

    def test_workspace_market_evidence_health_report_supports_project_filter(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Market Health Site",
                intake=SiteIntake(
                    url="https://market-health.example",
                    site_name="Market Health Site",
                    repo_url="https://github.com/example/market-health",
                    brand_whitelist=["MarketHealth"],
                ),
            )
        )
        report = service.build_workspace_market_evidence_health_report(project_id=project.project_id)
        self.assertEqual(report.project_id, project.project_id)
        self.assertEqual(report.project_count, 1)

    def test_workspace_billing_report_supports_project_filter(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Billing Filter Site",
                intake=SiteIntake(
                    url="https://billing-filter.example",
                    site_name="Billing Filter Site",
                    repo_url="https://github.com/example/billing-filter",
                    brand_whitelist=["BillingFilter"],
                ),
            )
        )
        report = service.build_workspace_billing_report(project_id=project.project_id)
        self.assertEqual(report.project_id, project.project_id)
        self.assertEqual(report.usage.active_project_count, 1)
        self.assertIsNotNone(report.settlement_gateway)
        self.assertEqual(report.settlement_gateway.project_id, project.project_id)
        self.assertIsNotNone(report.settlement_gateway_history)
        self.assertEqual(report.settlement_gateway_history.project_id, project.project_id)
        self.assertTrue(all(entry.project_id == project.project_id for entry in report.settlement_gateway_history.entries))

    def test_workspace_cruise_health_report_counts_due_and_overdue_projects(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Cruise Ready Site",
                intake=SiteIntake(
                    url="https://cruise-ready.example",
                    site_name="Cruise Ready Site",
                    repo_url="https://github.com/example/cruise-ready",
                    brand_whitelist=["CruiseReady"],
                ),
            )
        )
        now = datetime.now(timezone.utc)
        with service.database.session() as session:
            state = session.get(ProjectStateRow, project.project_id)
            self.assertIsNotNone(state)
            state.auto_cruise_enabled = True
            state.last_sync_at = now - timedelta(hours=3)
            state.next_sync_at = now - timedelta(minutes=30)
            state.sync_interval_minutes = 45
            session.add(state)
        report = service.build_workspace_cruise_health_report()
        self.assertEqual(report.enabled_project_count, 1)
        self.assertEqual(report.due_project_count, 1)
        self.assertEqual(report.overdue_project_count, 1)
        self.assertIsNone(report.project_id)
        self.assertIn(project.project_id, report.enabled_project_ids)
        self.assertIn(project.project_id, report.due_project_ids)
        self.assertIn(project.project_id, report.overdue_project_ids)
        self.assertTrue(any(sample.project_id == project.project_id and sample.due_now for sample in report.project_samples))
        filtered_report = service.build_workspace_cruise_health_report(project_id=project.project_id)
        self.assertEqual(filtered_report.project_id, project.project_id)
        self.assertEqual(filtered_report.project_count, 1)

    def test_acceptance_report_workspace_auto_cruise_gate_requires_enabled_projects_when_policy_on(self) -> None:
        os.environ["SEO_AD_BOT_AUTO_CRUISE_ENABLED"] = "true"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Cruise Acceptance Site",
                intake=SiteIntake(
                    url="https://cruise-acceptance.example",
                    site_name="Cruise Acceptance Site",
                    repo_url="https://github.com/example/cruise-acceptance",
                    brand_whitelist=["CruiseAcceptance"],
                ),
            )
        )
        with service.database.session() as session:
            state = session.get(ProjectStateRow, project.project_id)
            self.assertIsNotNone(state)
            state.auto_cruise_enabled = True
            state.next_sync_at = datetime.now(timezone.utc) + timedelta(minutes=60)
            session.add(state)
        report = service.build_acceptance_report()
        gate = next(item for item in report.gates if item.gate_id == "workspace_auto_cruise")
        self.assertTrue(gate.passed)
        self.assertIn("enabledProjectCount=1", gate.actual)
        self.assertIn("overdueProjectCount=0", gate.actual)

    def test_queue_backend_redis_and_roundtrip(self) -> None:
        service = self._service()
        queue = build_job_queue("redis", service.database, "redis://127.0.0.1:6379/0")

        self.assertIsInstance(queue, RedisJobQueue)

        job = WorkerJob(
            job_id="job_test_001",
            project_id="project_001",
            task_id="task_001",
            stage="sync",
            payload={"projectId": "project_001", "stage": "sync"},
            status=WorkerJobStatus.queued,
        )
        restored = WorkerJob.from_dict(job.to_dict())

        self.assertEqual(restored.job_id, job.job_id)
        self.assertEqual(restored.project_id, job.project_id)
        self.assertEqual(restored.stage, job.stage)
        self.assertEqual(restored.payload["projectId"], "project_001")

    def test_db_queue_deduplicates_active_jobs(self) -> None:
        service = self._service()
        queue = build_job_queue("db", service.database)
        first = WorkerJob(
            job_id="job_dup_001",
            project_id="project_dup",
            task_id="task_dup",
            stage="deploy",
            payload={"projectId": "project_dup", "taskId": "task_dup", "stage": "deploy"},
            status=WorkerJobStatus.queued,
        )
        second = WorkerJob(
            job_id="job_dup_002",
            project_id="project_dup",
            task_id="task_dup",
            stage="deploy",
            payload={"projectId": "project_dup", "taskId": "task_dup", "stage": "deploy"},
            status=WorkerJobStatus.queued,
        )
        self.assertTrue(queue.enqueue(first))
        self.assertFalse(queue.enqueue(second))
        claimed = queue.claim(limit=5)
        self.assertEqual(len(claimed), 1)
        queue.complete(claimed[0])
        self.assertTrue(queue.enqueue(second))

    def test_db_queue_respects_ready_at_delay(self) -> None:
        service = self._service()
        queue = build_job_queue("db", service.database)
        delayed = WorkerJob(
            job_id="job_delay_001",
            project_id="project_delay",
            task_id="task_delay",
            stage="deploy",
            payload={"projectId": "project_delay", "taskId": "task_delay", "stage": "deploy"},
            status=WorkerJobStatus.queued,
        )
        immediate = WorkerJob(
            job_id="job_delay_002",
            project_id="project_delay_2",
            task_id="task_delay_2",
            stage="deploy",
            payload={"projectId": "project_delay_2", "taskId": "task_delay_2", "stage": "deploy"},
            status=WorkerJobStatus.queued,
        )
        self.assertTrue(queue.enqueue(delayed, delay_seconds=120))
        self.assertTrue(queue.enqueue(immediate))
        claimed = queue.claim(limit=10)
        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0].job_id, "job_delay_002")

    def test_worker_queue_health_report_counts_status_and_stage_for_db_backend(self) -> None:
        os.environ["SEO_AD_BOT_QUEUE_BACKEND"] = "db"
        service = self._service()
        queue = service.job_queue
        queued_job = WorkerJob(
            job_id="job_health_queued",
            project_id="project_health",
            task_id="task_health_queued",
            stage="rollback",
            payload={"projectId": "project_health", "taskId": "task_health_queued", "stage": "rollback"},
            status=WorkerJobStatus.queued,
        )
        complete_job = WorkerJob(
            job_id="job_health_complete",
            project_id="project_health",
            task_id="task_health_complete",
            stage="sync",
            payload={"projectId": "project_health", "taskId": "task_health_complete", "stage": "sync"},
            status=WorkerJobStatus.queued,
        )
        fail_job = WorkerJob(
            job_id="job_health_fail",
            project_id="project_health",
            task_id="task_health_fail",
            stage="deploy",
            payload={"projectId": "project_health", "taskId": "task_health_fail", "stage": "deploy"},
            status=WorkerJobStatus.queued,
        )
        self.assertTrue(queue.enqueue(queued_job))
        self.assertTrue(queue.enqueue(complete_job))
        self.assertTrue(queue.enqueue(fail_job))
        claimed = queue.claim(limit=2)
        self.assertEqual(len(claimed), 2)
        for item in claimed:
            if item.stage == "sync":
                queue.complete(item)
            else:
                queue.fail(item, "test failure")

        health = service.get_worker_queue_health()
        self.assertEqual(health.backend, "db")
        self.assertTrue(health.backend_connected)
        self.assertIsNotNone(health.backend_probe_latency_ms)
        self.assertGreaterEqual(health.total, 3)
        self.assertGreaterEqual(health.queued, 1)
        self.assertGreaterEqual(health.completed, 1)
        self.assertGreaterEqual(health.failed, 1)
        stage_map = {item.stage: item for item in health.stage_stats}
        self.assertIn("rollback", stage_map)
        self.assertGreaterEqual(stage_map["rollback"].total, 1)
        self.assertGreaterEqual(
            stage_map["rollback"].queued
            + stage_map["rollback"].claimed
            + stage_map["rollback"].completed
            + stage_map["rollback"].failed,
            1,
        )

    def test_worker_queue_health_db_probe_reports_failure_code_when_session_fails(self) -> None:
        os.environ["SEO_AD_BOT_QUEUE_BACKEND"] = "db"
        service = self._service()
        with patch.object(service.database, "session", side_effect=ConnectionError("db down")):
            health = service.get_worker_queue_health()
        self.assertEqual(health.backend, "db")
        self.assertFalse(health.backend_connected)
        self.assertIn(health.backend_probe_failure_code, {"DB_CONNECTION_FAILED", "DB_PROBE_FAILED"})
        self.assertIsNotNone(health.backend_probe_error)

    def test_worker_queue_health_api_exposes_health_report(self) -> None:
        os.environ["SEO_AD_BOT_QUEUE_BACKEND"] = "db"
        state_path = Path(self._tempdir.name) / "worker-runtime-state.json"
        state_path.write_text(
            json.dumps(
                {
                    "startedAt": datetime.now(timezone.utc).isoformat(),
                    "lastTickAt": datetime.now(timezone.utc).isoformat(),
                    "status": "running",
                    "processed": 3,
                    "enqueued": 2,
                    "claimed": 1,
                    "skippedDuplicates": 0,
                    "dueProjects": 1,
                    "targets": ["project_demo"],
                    "failures": 0,
                    "lastError": None,
                }
            ),
            encoding="utf-8",
        )
        os.environ["SEO_AD_BOT_WORKER_STATE_FILE"] = str(state_path)
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Worker History Project",
                intake=SiteIntake(url="https://worker-history.example", site_name="Worker History Project"),
            )
        )
        service.run_analysis(
            project.project_id,
            SiteIntake(url="https://worker-history.example", site_name="Worker History Project"),
        )
        service.run_worker_once(
            WorkerRunOnceRequest(
                project_ids=[project.project_id],
                include_approved_tasks=False,
                claim_limit=20,
            )
        )
        app = create_app(service)
        with TestClient(app) as client:
            response = client.get("/api/worker/queue/health")
            service_health = client.get("/api/worker/service/health")
            history = client.get("/api/worker/executions", params={"limit": 5})
            history_failed = client.get("/api/worker/executions", params={"status": "failed", "limit": 5})
            history_stage = client.get("/api/worker/executions", params={"stage": "sync", "limit": 20})
            history_action = client.get("/api/worker/executions", params={"action": "worker.job.completed", "limit": 20})
            history_project = client.get("/api/worker/executions", params={"projectId": project.project_id, "limit": 20})
            history_invalid = client.get("/api/worker/executions", params={"status": "invalid"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(service_health.status_code, 200)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history_failed.status_code, 200)
        self.assertEqual(history_stage.status_code, 200)
        self.assertEqual(history_action.status_code, 200)
        self.assertEqual(history_project.status_code, 200)
        self.assertEqual(history_invalid.status_code, 422)
        payload = response.json()
        service_payload = service_health.json()
        self.assertIn("backend", payload)
        self.assertIn("backendConnected", payload)
        self.assertIn("backendProbeFailureCode", payload)
        self.assertIn("total", payload)
        self.assertIn("queued", payload)
        self.assertIn("stageStats", payload)
        self.assertEqual(service_payload.get("status"), "running")
        self.assertEqual(service_payload.get("stateFileConfigured"), True)
        self.assertEqual(service_payload.get("stateFileFound"), True)
        history_payload = history.json()
        self.assertIsNone(history_payload["projectId"])
        self.assertIn("total", history_payload)
        self.assertIn("entries", history_payload)
        history_project_payload = history_project.json()
        self.assertEqual(history_project_payload["projectId"], project.project_id)
        self.assertTrue(all(item["projectId"] == project.project_id for item in history_project_payload["entries"]))
        self.assertTrue(all(item.get("status") == "failed" for item in history_failed.json().get("entries", [])))
        self.assertTrue(all(item.get("stage") == "sync" for item in history_stage.json().get("entries", [])))
        self.assertTrue(all(item.get("action") == "worker.job.completed" for item in history_action.json().get("entries", [])))
        self.assertTrue(all(item.get("projectId") == project.project_id for item in history_project.json().get("entries", [])))

    def test_worker_queue_health_redis_probe_reports_unreachable_backend(self) -> None:
        os.environ["SEO_AD_BOT_QUEUE_BACKEND"] = "redis"
        os.environ["REDIS_URL"] = "redis://127.0.0.1:6399/0"
        service = self._service()
        health = service.get_worker_queue_health()
        self.assertEqual(health.backend, "redis")
        self.assertFalse(health.backend_connected)
        self.assertIn(health.backend_probe_failure_code, {"REDIS_CONNECTION_FAILED", "REDIS_PROBE_FAILED"})
        self.assertIsNotNone(health.backend_probe_error)
        self.assertIsNone(health.queue_depth)

    def test_acceptance_report_runtime_gate_requires_redis_connectivity(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_QUEUE_BACKEND"] = "redis"
        os.environ["REDIS_URL"] = "redis://127.0.0.1:6399/0"
        os.environ["SEO_AD_BOT_DATABASE_URL"] = "postgresql://user:pass@127.0.0.1:5432/seo_ad_test"
        service = self._service()
        report = service.build_acceptance_report()
        runtime_gate = next(item for item in report.gates if item.gate_id == "runtime_architecture_production")
        oncall_gate = next(item for item in report.gates if item.gate_id == "oncall_coverage_ready")
        self.assertFalse(runtime_gate.passed)
        self.assertIn("queueConnected=false", runtime_gate.actual)
        self.assertIn("routeCount=", oncall_gate.actual)

    def test_acceptance_report_runtime_edge_gateway_gate_blocks_duplicate_hosts(self) -> None:
        service = self._service()
        project_a = service.create_project(
            ProjectCreateRequest(
                name="Duplicate Host A",
                intake=SiteIntake(
                    url="https://dup-runtime-edge.example/a",
                    site_name="Duplicate Host A",
                    keywords=["edge", "dup"],
                ),
            )
        )
        project_b = service.create_project(
            ProjectCreateRequest(
                name="Duplicate Host B",
                intake=SiteIntake(
                    url="https://dup-runtime-edge.example/b",
                    site_name="Duplicate Host B",
                    keywords=["edge", "dup"],
                ),
            )
        )
        service.run_analysis(
            project_a.project_id,
            SiteIntake(url="https://dup-runtime-edge.example/a", site_name="Duplicate Host A", keywords=["edge", "dup"]),
        )
        service.run_analysis(
            project_b.project_id,
            SiteIntake(url="https://dup-runtime-edge.example/b", site_name="Duplicate Host B", keywords=["edge", "dup"]),
        )
        report = service.build_acceptance_report()
        edge_gate = next(item for item in report.gates if item.gate_id == "runtime_edge_gateway_ready")
        self.assertFalse(edge_gate.passed)
        self.assertIn("duplicateHostCount=1", edge_gate.actual)

    def test_acceptance_report_runtime_edge_rollout_gate_requires_history_in_strict_mode(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        service = self._service()
        report_before = service.build_acceptance_report()
        rollout_gate_before = next(item for item in report_before.gates if item.gate_id == "runtime_edge_rollout_ready")
        self.assertFalse(rollout_gate_before.passed)
        self.assertIn("rolloutExecutionCount=0", rollout_gate_before.actual)

        service.execute_runtime_edge_rollout(
            RuntimeEdgeRolloutExecuteRequest(
                stage_id="validate",
                strict_routes_only=True,
                dry_run=True,
                actor="qa",
                note="acceptance rollout gate smoke",
            )
        )
        report_after = service.build_acceptance_report()
        rollout_gate_after = next(item for item in report_after.gates if item.gate_id == "runtime_edge_rollout_ready")
        self.assertTrue(rollout_gate_after.passed)
        self.assertIn("rolloutExecutionCount=", rollout_gate_after.actual)

    def test_runtime_edge_full_rollout_requires_executed_canary_in_strict_mode(self) -> None:
        service = self._service()
        result = service.execute_runtime_edge_rollout(
            RuntimeEdgeRolloutExecuteRequest(
                stage_id="full",
                strict_routes_only=True,
                dry_run=False,
                actor="qa",
                note="full rollout without canary",
            )
        )
        self.assertEqual(result.status, "blocked")
        self.assertTrue(any(item.blocker_code == "CANARY_REQUIRED" for item in result.blockers))

    def test_runtime_edge_rollout_execution_generates_stage_artifacts_when_executed(self) -> None:
        os.environ["SEO_AD_BOT_STATE_DIR"] = str(Path(self._tempdir.name) / "state")
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL"] = "https://runtime-edge-rollout-artifacts.example/deploy"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Rollout Artifact Project",
                intake=SiteIntake(
                    url="https://runtime-edge-rollout-artifacts.example",
                    site_name="Runtime Edge Rollout Artifact Project",
                ),
            )
        )
        class _RolloutResponse:
            status = 200

            def __enter__(self) -> "_RolloutResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "deploymentId": "edge-rollout-artifact-generation-001",
                        "artifactId": "edge-rollout-artifact-generation-001",
                        "artifactUrl": "https://runtime-edge-rollout-artifacts.example/artifact/001",
                    }
                ).encode("utf-8")

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_RolloutResponse()):
            result = service.execute_runtime_edge_rollout(
                RuntimeEdgeRolloutExecuteRequest(
                    stage_id="validate",
                    strict_routes_only=False,
                    project_id=project.project_id,
                    canary_percent=20,
                    dry_run=False,
                    actor="qa",
                    note="rollout artifact generation",
                )
            )
        self.assertEqual(result.status, "executed")
        self.assertGreaterEqual(result.rollout_host_count, 0)
        self.assertTrue(result.rollout_nginx_artifact_path)
        self.assertTrue(result.rollout_caddy_artifact_path)
        self.assertTrue(result.rollout_manifest_path)
        self.assertTrue(Path(str(result.rollout_nginx_artifact_path)).exists())
        self.assertTrue(Path(str(result.rollout_caddy_artifact_path)).exists())
        self.assertTrue(Path(str(result.rollout_manifest_path)).exists())

    def test_runtime_edge_rollout_validate_publishes_stage_export_to_gateway(self) -> None:
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL"] = "https://runtime-edge-rollout-gateway.example/deploy"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Rollout Gateway Publish",
                intake=SiteIntake(
                    url="https://runtime-edge-rollout-gateway.example",
                    site_name="Runtime Edge Rollout Gateway Publish",
                ),
            )
        )

        class _DeployResponse:
            status = 200

            def __enter__(self) -> "_DeployResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "deploymentId": "edge-rollout-deploy-001",
                        "artifactId": "edge-rollout-artifact-001",
                        "artifactUrl": "https://runtime-edge-rollout-gateway.example/artifact/001",
                    }
                ).encode("utf-8")

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_DeployResponse()) as publish_mock:
            result = service.execute_runtime_edge_rollout(
                RuntimeEdgeRolloutExecuteRequest(
                    stage_id="validate",
                    strict_routes_only=False,
                    project_id=project.project_id,
                    canary_percent=20,
                    dry_run=False,
                    actor="qa",
                    note="rollout validate publish",
                )
            )

        self.assertEqual(result.status, "executed")
        self.assertEqual(result.gateway_publish_status, "executed")
        self.assertEqual(result.provider_endpoint, "https://runtime-edge-rollout-gateway.example/deploy")
        self.assertEqual(result.provider_artifact_id, "edge-rollout-artifact-001")
        self.assertTrue(any("providerMode=external" in note for note in result.gateway_publish_notes))
        self.assertGreaterEqual(publish_mock.call_count, 1)

    def test_runtime_edge_rollout_validate_blocks_when_gateway_publish_fails(self) -> None:
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL"] = "https://runtime-edge-rollout-gateway-fail.example/deploy"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Rollout Gateway Fail",
                intake=SiteIntake(
                    url="https://runtime-edge-rollout-gateway-fail.example",
                    site_name="Runtime Edge Rollout Gateway Fail",
                ),
            )
        )

        def _mock_gateway_urlopen(request, timeout=5):
            raise HTTPError(str(request.full_url), 503, "Service Unavailable", hdrs=None, fp=None)

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
            result = service.execute_runtime_edge_rollout(
                RuntimeEdgeRolloutExecuteRequest(
                    stage_id="validate",
                    strict_routes_only=False,
                    project_id=project.project_id,
                    canary_percent=20,
                    dry_run=False,
                    actor="qa",
                    note="rollout validate publish fail",
                )
            )

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.gateway_publish_status, "blocked")
        self.assertEqual(result.failure_code, "RUNTIME_EDGE_GATEWAY_HTTP_503")
        self.assertTrue(result.retryable)
        self.assertTrue(any(item.blocker_code == "RUNTIME_EDGE_GATEWAY_PUBLISH_FAILED" for item in result.blockers))

    def test_runtime_edge_rollout_remediation_report_includes_gateway_publish_blockers_from_history(self) -> None:
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL"] = "https://runtime-edge-rollout-remediation-fail.example/deploy"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Rollout Remediation",
                intake=SiteIntake(
                    url="https://runtime-edge-rollout-remediation.example",
                    site_name="Runtime Edge Rollout Remediation",
                ),
            )
        )

        def _mock_gateway_urlopen(request, timeout=5):
            raise HTTPError(str(request.full_url), 503, "Service Unavailable", hdrs=None, fp=None)

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
            result = service.execute_runtime_edge_rollout(
                RuntimeEdgeRolloutExecuteRequest(
                    stage_id="validate",
                    strict_routes_only=False,
                    project_id=project.project_id,
                    canary_percent=20,
                    dry_run=False,
                    actor="qa",
                    note="rollout remediation failure seed",
                )
            )
        self.assertEqual(result.status, "blocked")
        remediation = service.build_runtime_edge_rollout_remediation_report(
            project_id=project.project_id,
            strict_routes_only=False,
        )
        gateway_item = next((item for item in remediation.items if item.blocker_code == "RUNTIME_EDGE_GATEWAY_PUBLISH_FAILED"), None)
        self.assertIsNotNone(gateway_item)
        assert gateway_item is not None
        self.assertGreaterEqual(gateway_item.count, 1)
        self.assertIn("retry rollout publish", gateway_item.recommendation.lower())
        self.assertTrue(any(str(note).startswith("rolloutHistoryBlockers=") for note in remediation.notes))

    def test_runtime_edge_deploy_publishes_export_to_gateway(self) -> None:
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL"] = "https://runtime-edge-gateway.example/deploy"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Deploy Gateway",
                intake=SiteIntake(url="https://runtime-edge-deploy.example", site_name="Runtime Edge Deploy Gateway"),
            )
        )

        class _DeployResponse:
            status = 200

            def __enter__(self) -> "_DeployResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps({"deploymentId": "edge-deploy-123", "artifactUrl": "https://runtime-edge-gateway.example/artifact/123"}).encode("utf-8")

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_DeployResponse()) as deploy_mock:
            result = service.execute_runtime_edge_deployment(
                RuntimeEdgeDeploymentRequest(
                    project_id=project.project_id,
                    strict_routes_only=False,
                    dry_run=False,
                    actor="qa",
                    note="runtime edge deploy gateway smoke",
                )
            )
        self.assertEqual(result.status, "executed")
        self.assertEqual(result.provider_endpoint, "https://runtime-edge-gateway.example/deploy")
        self.assertEqual(result.provider_artifact_id, "edge-deploy-123")
        self.assertEqual(result.provider_url, "https://runtime-edge-gateway.example/artifact/123")
        self.assertTrue(any("providerMode=external" in note for note in result.notes))
        self.assertGreaterEqual(deploy_mock.call_count, 1)

    def test_runtime_edge_deploy_gateway_failover_succeeds_on_secondary_endpoint(self) -> None:
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URLS"] = (
            "https://runtime-edge-gateway.example/primary,"
            "https://runtime-edge-gateway.example/secondary"
        )
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_ACCESS_TOKEN"] = "runtime-edge-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Deploy Gateway Failover",
                intake=SiteIntake(url="https://runtime-edge-deploy-failover.example", site_name="Runtime Edge Deploy Gateway Failover"),
            )
        )

        class _DeployResponse:
            status = 200

            def __enter__(self) -> "_DeployResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "deploymentId": "edge-deploy-failover-123",
                        "artifactUrl": "https://runtime-edge-gateway.example/artifact/failover/123",
                    }
                ).encode("utf-8")

        attempted_endpoints: list[str] = []

        def _mock_gateway_urlopen(request, timeout=5):
            endpoint = str(getattr(request, "full_url", ""))
            attempted_endpoints.append(endpoint)
            if endpoint.endswith("/primary"):
                raise HTTPError(endpoint, 503, "service unavailable", hdrs=None, fp=None)
            return _DeployResponse()

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
            result = service.execute_runtime_edge_deployment(
                RuntimeEdgeDeploymentRequest(
                    project_id=project.project_id,
                    strict_routes_only=False,
                    dry_run=False,
                    actor="qa",
                    note="runtime edge deploy gateway failover smoke",
                )
            )
        self.assertEqual(result.status, "executed")
        self.assertEqual(result.provider_endpoint, "https://runtime-edge-gateway.example/secondary")
        self.assertEqual(result.provider_artifact_id, "edge-deploy-failover-123")
        self.assertTrue(any("gatewayFailover=true" in note for note in result.notes))
        self.assertEqual(
            attempted_endpoints,
            [
                "https://runtime-edge-gateway.example/primary",
                "https://runtime-edge-gateway.example/secondary",
            ],
        )

    def test_runtime_edge_deploy_gateway_failover_returns_last_failure_when_all_endpoints_fail(self) -> None:
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URLS"] = (
            "https://runtime-edge-gateway.example/primary,"
            "https://runtime-edge-gateway.example/secondary"
        )
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_ACCESS_TOKEN"] = "runtime-edge-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Deploy Gateway Failover Failed",
                intake=SiteIntake(url="https://runtime-edge-deploy-failover-failed.example", site_name="Runtime Edge Deploy Gateway Failover Failed"),
            )
        )
        attempted_endpoints: list[str] = []

        def _mock_gateway_urlopen(request, timeout=5):
            endpoint = str(getattr(request, "full_url", ""))
            attempted_endpoints.append(endpoint)
            if endpoint.endswith("/primary"):
                raise HTTPError(endpoint, 502, "bad gateway", hdrs=None, fp=None)
            raise RuntimeError("network down")

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
            result = service.execute_runtime_edge_deployment(
                RuntimeEdgeDeploymentRequest(
                    project_id=project.project_id,
                    strict_routes_only=False,
                    dry_run=False,
                    actor="qa",
                    note="runtime edge deploy gateway failover failed smoke",
                )
            )
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.failure_code, "RUNTIME_EDGE_GATEWAY_REQUEST_FAILED")
        self.assertEqual(result.provider_endpoint, "https://runtime-edge-gateway.example/secondary")
        self.assertTrue(any(str(note).startswith("attempt[1]=") for note in result.notes))
        self.assertTrue(any(str(note).startswith("attempt[2]=") for note in result.notes))
        self.assertEqual(
            attempted_endpoints,
            [
                "https://runtime-edge-gateway.example/primary",
                "https://runtime-edge-gateway.example/secondary",
            ],
        )

    def test_runtime_edge_gateway_policy_publish_failover_succeeds_on_secondary_endpoint(self) -> None:
        os.environ.pop("SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL", None)
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URLS"] = (
            "https://runtime-edge-policy-primary.example/publish,"
            "https://runtime-edge-policy-secondary.example/publish"
        )
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_ACCESS_TOKEN"] = "runtime-edge-policy-token"
        service = self._service()
        gateway_report = service.build_runtime_edge_gateway_report()

        class _GatewayResponse:
            status = 200

            def __enter__(self) -> "_GatewayResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "artifactId": "runtime_edge_policy_artifact_failover_001",
                        "artifactUrl": "https://runtime-edge-policy-secondary.example/artifact/001",
                        "message": "runtime edge policy publish failover ok",
                    }
                ).encode("utf-8")

        request_urls: list[str] = []

        def _mock_urlopen(request, timeout=5):
            request_urls.append(str(request.full_url))
            if "primary" in str(request.full_url):
                raise HTTPError(str(request.full_url), 502, "Bad Gateway", hdrs=None, fp=None)
            return _GatewayResponse()

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
            publish = service._execute_runtime_edge_gateway_policy_publish(gateway_report)

        self.assertEqual(publish.status, "completed")
        self.assertEqual(publish.gateway_endpoint, "https://runtime-edge-policy-secondary.example/publish")
        self.assertEqual(publish.gateway_artifact_id, "runtime_edge_policy_artifact_failover_001")
        self.assertIn("https://runtime-edge-policy-primary.example/publish", request_urls)
        self.assertIn("https://runtime-edge-policy-secondary.example/publish", request_urls)
        self.assertTrue(any("attemptFailed=https://runtime-edge-policy-primary.example/publish:http_502" in note for note in publish.notes))

    def test_runtime_edge_gateway_policy_publish_failover_returns_last_failure_when_all_endpoints_fail(self) -> None:
        os.environ.pop("SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL", None)
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URLS"] = (
            "https://runtime-edge-policy-fail-a.example/publish,"
            "https://runtime-edge-policy-fail-b.example/publish"
        )
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_ACCESS_TOKEN"] = "runtime-edge-policy-token"
        service = self._service()
        gateway_report = service.build_runtime_edge_gateway_report()

        def _mock_urlopen(request, timeout=5):
            if "fail-a" in str(request.full_url):
                raise HTTPError(str(request.full_url), 503, "Service Unavailable", hdrs=None, fp=None)
            raise HTTPError(str(request.full_url), 429, "Too Many Requests", hdrs=None, fp=None)

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
            publish = service._execute_runtime_edge_gateway_policy_publish(gateway_report)

        self.assertEqual(publish.status, "failed")
        self.assertEqual(publish.failure_code, "RUNTIME_EDGE_GATEWAY_HTTP_429")
        self.assertFalse(publish.retryable)
        self.assertEqual(publish.gateway_endpoint, "https://runtime-edge-policy-fail-b.example/publish")
        self.assertTrue(any("attemptedEndpointCount=2" in note for note in publish.notes))

    def test_runtime_edge_gateway_api_and_routed_deployment(self) -> None:
        os.environ.pop("SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL", None)
        os.environ.pop("SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_ACCESS_TOKEN", None)
        os.environ["SEO_AD_BOT_STATE_DIR"] = str(Path(self._tempdir.name) / "state")
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Gateway Project",
                intake=SiteIntake(
                    url="https://runtime-edge-gateway-project.example",
                    site_name="Runtime Edge Gateway Project",
                ),
            )
        )
        app = create_app(service)

        class _DeployResponse:
            status = 200

            def __init__(self):
                self.request_headers = {}

            def __enter__(self) -> "_DeployResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "deploymentId": "runtime-edge-gateway-deploy-001",
                        "artifactId": "runtime-edge-gateway-artifact-001",
                        "artifactUrl": "https://runtime-edge-gateway.example/artifact/001",
                    }
                ).encode("utf-8")

        response_holder = _DeployResponse()

        def _mock_gateway_urlopen(request, timeout=5):
            response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
            return response_holder

        with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
            updated_gateway = client.put(
                "/api/runtime-edge/gateway",
                json={
                    "gatewayEnabled": True,
                    "strictRouting": True,
                    "defaultProviderName": "runtime_edge",
                    "fallbackProviderName": "runtime_edge",
                    "routes": [
                        {
                            "providerName": "runtime_edge",
                            "enabled": True,
                            "fallbackProviderName": "runtime_edge",
                            "priority": 10,
                            "endpoint": "https://runtime-edge-gateway.example/deploy",
                            "accessToken": "runtime-edge-token",
                            "authHeader": "X-Runtime-Edge-Token",
                            "notes": ["workspace runtime edge gateway"],
                        }
                    ],
                    "notes": ["runtime edge gateway smoke test"],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated_gateway.status_code, 200)
            gateway_payload = updated_gateway.json()
            self.assertTrue(gateway_payload["gatewayReady"])
            self.assertEqual(gateway_payload["routeReadyCount"], 1)
            self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "runtime_edge")

            deployed = client.post(
                "/api/runtime-edge/deploy",
                json={
                    "dryRun": False,
                    "strictRoutesOnly": False,
                    "projectId": project.project_id,
                    "actor": "qa",
                    "note": "runtime edge gateway",
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(deployed.status_code, 200)
            deployed_payload = deployed.json()
            self.assertEqual(deployed_payload["status"], "executed")
            self.assertEqual(deployed_payload["providerEndpoint"], "https://runtime-edge-gateway.example/deploy")
            self.assertEqual(deployed_payload["providerArtifactId"], "runtime-edge-gateway-artifact-001")
            self.assertEqual(deployed_payload["providerUrl"], "https://runtime-edge-gateway.example/artifact/001")
            self.assertEqual(response_holder.request_headers.get("x-runtime-edge-token"), "Bearer runtime-edge-token")
            history = client.get("/api/runtime-edge/gateway/history")
            self.assertEqual(history.status_code, 200)
            history_payload = history.json()
            self.assertGreaterEqual(history_payload["total"], 1)
            self.assertEqual(history_payload["summary"]["totalCount"], len(history_payload["entries"]))
            self.assertTrue(history_payload["entries"])
            self.assertEqual(history_payload["entries"][0]["latestProviderName"], "runtime_edge")

            deploy_history = client.get("/api/runtime-edge/deploy/history")
            self.assertEqual(deploy_history.status_code, 200)
            deploy_history_payload = deploy_history.json()
            self.assertGreaterEqual(deploy_history_payload["total"], 1)
            self.assertEqual(deploy_history_payload["summary"]["totalCount"], len(deploy_history_payload["items"]))
            self.assertTrue(deploy_history_payload["items"])
            self.assertEqual(deploy_history_payload["items"][0]["providerEndpoint"], "https://runtime-edge-gateway.example/deploy")
            self.assertEqual(deploy_history_payload["items"][0]["providerArtifactId"], "runtime-edge-gateway-artifact-001")
            self.assertEqual(deploy_history_payload["items"][0]["providerUrl"], "https://runtime-edge-gateway.example/artifact/001")
            filtered_deploy_history = client.get(f"/api/runtime-edge/deploy/history?projectId={project.project_id}")
            self.assertEqual(filtered_deploy_history.status_code, 200)
            filtered_deploy_history_payload = filtered_deploy_history.json()
            self.assertGreaterEqual(filtered_deploy_history_payload["total"], 1)
            self.assertEqual(filtered_deploy_history_payload["projectId"], project.project_id)
            self.assertEqual(filtered_deploy_history_payload["items"][0]["projectId"], project.project_id)

            publish_gateway = client.post(
                f"/api/runtime-edge/gateway/publish?projectId={project.project_id}",
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(publish_gateway.status_code, 200)
            publish_gateway_payload = publish_gateway.json()
            self.assertTrue(publish_gateway_payload["gatewayReady"])
            self.assertIsNotNone(publish_gateway_payload["gatewayPublish"])
            self.assertEqual(publish_gateway_payload["gatewayPublish"]["status"], "completed")
            self.assertEqual(publish_gateway_payload["gatewayPublish"]["gatewayEndpoint"], "https://runtime-edge-gateway.example/deploy")
            self.assertEqual(publish_gateway_payload["gatewayPublish"]["gatewayArtifactId"], "runtime-edge-gateway-artifact-001")
            self.assertEqual(publish_gateway_payload["gatewayPublish"]["gatewayUrl"], "https://runtime-edge-gateway.example/artifact/001")
            self.assertEqual(response_holder.request_headers.get("x-runtime-edge-token"), "Bearer runtime-edge-token")

    def test_runtime_edge_route_overrides_api_applies_custom_paths(self) -> None:
        os.environ["SEO_AD_BOT_STATE_DIR"] = str(Path(self._tempdir.name) / "state")
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Override Project",
                intake=SiteIntake(
                    url="https://runtime-edge-override.example",
                    site_name="Runtime Edge Override Project",
                ),
            )
        )
        service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://runtime-edge-override.example",
                site_name="Runtime Edge Override Project",
            ),
        )
        app = create_app(service)

        with TestClient(app) as client:
            blocked = client.put(
                "/api/runtime-edge/routes/overrides",
                json={"overrides": []},
            )
            self.assertEqual(blocked.status_code, 401)

            updated = client.put(
                "/api/runtime-edge/routes/overrides",
                json={
                    "replace": True,
                    "actor": "qa",
                    "note": "runtime edge override smoke",
                    "overrides": [
                        {
                            "projectId": project.project_id,
                            "enabled": True,
                            "siteHost": "edge.override.example",
                            "publicPath": "/gateway",
                            "proxyPath": f"/api/projects/{project.project_id}/runtime-execute/proxy",
                            "strictProxyPath": f"/api/projects/{project.project_id}/runtime-execute/proxy-strict",
                            "rewriteRule": f"rewrite /gateway -> /api/projects/{project.project_id}/runtime-execute/proxy",
                            "upstreamHost": "edge-api.internal:8000",
                            "notes": ["tenant gateway override"],
                        }
                    ],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated.status_code, 200)
            updated_payload = updated.json()
            self.assertEqual(updated_payload["total"], 1)
            self.assertEqual(updated_payload["enabledCount"], 1)
            self.assertEqual(updated_payload["overrides"][0]["projectId"], project.project_id)
            self.assertEqual(updated_payload["overrides"][0]["publicPath"], "/gateway")

            listed = client.get(f"/api/runtime-edge/routes/overrides?projectId={project.project_id}")
            self.assertEqual(listed.status_code, 200)
            listed_payload = listed.json()
            self.assertEqual(listed_payload["projectId"], project.project_id)
            self.assertEqual(listed_payload["total"], 1)
            self.assertEqual(listed_payload["overrides"][0]["siteHost"], "edge.override.example")

            project_config = client.get(f"/api/projects/{project.project_id}/runtime-edge/config")
            self.assertEqual(project_config.status_code, 200)
            project_config_payload = project_config.json()
            self.assertEqual(project_config_payload["siteHost"], "edge.override.example")
            self.assertEqual(project_config_payload["publicPath"], "/gateway")
            self.assertEqual(project_config_payload["upstreamHost"], "edge-api.internal:8000")
            self.assertIn("location /gateway", project_config_payload["nginxSnippet"])

            route_map = client.get("/api/runtime-edge/map")
            self.assertEqual(route_map.status_code, 200)
            route_map_payload = route_map.json()
            matching = next(item for item in route_map_payload["items"] if item["projectId"] == project.project_id)
            self.assertEqual(matching["siteHost"], "edge.override.example")
            self.assertEqual(matching["publicPath"], "/gateway")
            self.assertEqual(matching["proxyPath"], f"/api/projects/{project.project_id}/runtime-execute/proxy")

            exported = client.get("/api/runtime-edge/export")
            self.assertEqual(exported.status_code, 200)
            export_payload = exported.json()
            self.assertIn("edge.override.example", export_payload["nginxMapConf"])
            self.assertIn("/api/projects/" + project.project_id + "/runtime-execute/proxy", export_payload["caddyfileFragment"])

    def test_runtime_ingress_bundle_api_and_publish(self) -> None:
        os.environ.pop("SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL", None)
        os.environ.pop("SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_ACCESS_TOKEN", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ENDPOINT", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ACCESS_TOKEN", None)
        os.environ["SEO_AD_BOT_STATE_DIR"] = str(Path(self._tempdir.name) / "state")
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Ingress Bundle Project",
                intake=SiteIntake(
                    url="https://runtime-ingress-bundle.example",
                    site_name="Runtime Ingress Bundle Project",
                ),
            )
        )
        app = create_app(service)

        class _DeployResponse:
            def __init__(self, payload: dict[str, str]):
                self.status = 200
                self.payload = payload
                self.request_headers = {}

            def __enter__(self) -> "_DeployResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(self.payload).encode("utf-8")

        def _mock_bundle_urlopen(request, timeout=5):
            request_url = str(getattr(request, "full_url", ""))
            response_payload = {
                "artifactId": "bundle-artifact-001",
                "artifactUrl": "https://bundle.example/artifact/001",
            }
            if "visual-farm" in request_url:
                response_payload = {
                    "deploymentId": "visual-farm-bundle-deploy-001",
                    "artifactId": "visual-farm-bundle-artifact-001",
                    "artifactUrl": "https://visual-farm-bundle.example/artifact/001",
                }
            elif "runtime-edge" in request_url:
                response_payload = {
                    "deploymentId": "runtime-edge-bundle-deploy-001",
                    "artifactId": "runtime-edge-bundle-artifact-001",
                    "artifactUrl": "https://runtime-edge-bundle.example/artifact/001",
                }
            return _DeployResponse(response_payload)

        with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_bundle_urlopen):
            runtime_edge_gateway = client.put(
                "/api/runtime-edge/gateway",
                json={
                    "gatewayEnabled": True,
                    "strictRouting": True,
                    "defaultProviderName": "runtime_edge",
                    "fallbackProviderName": "runtime_edge",
                    "routes": [
                        {
                            "providerName": "runtime_edge",
                            "enabled": True,
                            "fallbackProviderName": "runtime_edge",
                            "priority": 10,
                            "endpoint": "https://runtime-edge-bundle.example/deploy",
                            "accessToken": "runtime-edge-token",
                            "authHeader": "X-Runtime-Edge-Token",
                        }
                    ],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(runtime_edge_gateway.status_code, 200)
            visual_farm_gateway = client.put(
                "/api/visual-farm/gateway",
                json={
                    "gatewayEnabled": True,
                    "strictRouting": True,
                    "defaultProviderName": "visual_farm",
                    "fallbackProviderName": "visual_farm",
                    "routes": [
                        {
                            "providerName": "visual_farm",
                            "enabled": True,
                            "fallbackProviderName": "visual_farm",
                            "priority": 10,
                            "endpoint": "https://visual-farm-bundle.example/deploy",
                            "accessToken": "visual-farm-token",
                            "authHeader": "X-Visual-Farm-Token",
                        }
                    ],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(visual_farm_gateway.status_code, 200)

            runtime_edge_deploy = client.post(
                "/api/runtime-edge/deploy",
                json={
                    "projectId": project.project_id,
                    "dryRun": False,
                    "actor": "qa",
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(runtime_edge_deploy.status_code, 200)
            self.assertEqual(runtime_edge_deploy.json()["status"], "executed")
            bundle_path = Path(self._tempdir.name) / "state" / "runtime-ingress-bundle.json"
            self.assertTrue(bundle_path.exists())

            visual_farm_deploy = client.post(
                "/api/visual-farm/deploy",
                json={
                    "projectId": project.project_id,
                    "dryRun": False,
                    "actor": "qa",
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(visual_farm_deploy.status_code, 200)
            self.assertEqual(visual_farm_deploy.json()["status"], "executed")
            self.assertTrue(bundle_path.exists())

            bundle = client.get("/api/runtime-ingress/bundle?strictRoutesOnly=true")
            self.assertEqual(bundle.status_code, 200)
            bundle_payload = bundle.json()
            self.assertEqual(bundle_payload["projectId"], None)
            self.assertTrue(bundle_payload["bundleReady"])
            self.assertIn("runtimeEdgeExport", bundle_payload)
            self.assertIn("visualFarmGateway", bundle_payload)
            self.assertIn("routeManifest", bundle_payload)
            self.assertIn("runtimeEdgeDeploymentHistory", bundle_payload)
            self.assertIn("visualFarmDeploymentHistory", bundle_payload)
            self.assertGreaterEqual(bundle_payload["runtimeEdgeDeploymentHistory"]["total"], 1)
            self.assertGreaterEqual(bundle_payload["visualFarmDeploymentHistory"]["total"], 1)
            self.assertGreaterEqual(bundle_payload["routeManifest"]["hostCount"], 1)
            self.assertTrue(bundle_payload["routeManifest"]["items"])

            published_bundle = client.post(
                "/api/runtime-ingress/bundle?strictRoutesOnly=true",
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(published_bundle.status_code, 200)
            published_bundle_payload = published_bundle.json()
            self.assertTrue(published_bundle_payload["bundleReady"])
            self.assertTrue(bundle_path.exists())
            manifest_path = Path(self._tempdir.name) / "state" / "runtime-ingress-workspace-strict-manifest.json"
            self.assertTrue(manifest_path.exists())

            nginx_artifact = client.get(f"/api/runtime-ingress/nginx?strictRoutesOnly=true&projectId={project.project_id}")
            self.assertEqual(nginx_artifact.status_code, 200)
            nginx_artifact_payload = nginx_artifact.json()
            self.assertEqual(nginx_artifact_payload["format"], "nginx")
            self.assertTrue(nginx_artifact_payload["bundleReady"])
            self.assertIn("map $host $seo_ad_runtime_proxy", nginx_artifact_payload["content"])
            self.assertIsNotNone(nginx_artifact_payload["manifestPath"])
            self.assertTrue(str(nginx_artifact_payload["manifestPath"]).endswith("-manifest.json"))

            caddy_artifact = client.get(f"/api/runtime-ingress/caddy?strictRoutesOnly=true&projectId={project.project_id}")
            self.assertEqual(caddy_artifact.status_code, 200)
            caddy_artifact_payload = caddy_artifact.json()
            self.assertEqual(caddy_artifact_payload["format"], "caddy")
            self.assertTrue(caddy_artifact_payload["bundleReady"])
            self.assertTrue(caddy_artifact_payload["content"])
            self.assertIn("Generated by SEO-AD AutoPilot runtime edge exporter", caddy_artifact_payload["content"])
            self.assertIsNotNone(caddy_artifact_payload["manifestPath"])

            publish_nginx = client.post(
                f"/api/runtime-ingress/nginx?strictRoutesOnly=true&projectId={project.project_id}",
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(publish_nginx.status_code, 200)
            self.assertTrue(Path(nginx_artifact_payload["artifactPath"]).exists())
            self.assertTrue(Path(nginx_artifact_payload["manifestPath"]).exists())

            publish_caddy = client.post(
                f"/api/runtime-ingress/caddy?strictRoutesOnly=true&projectId={project.project_id}",
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(publish_caddy.status_code, 200)
            self.assertTrue(Path(caddy_artifact_payload["artifactPath"]).exists())
            self.assertTrue(Path(caddy_artifact_payload["manifestPath"]).exists())

            history = client.get("/api/runtime-ingress/history?format=nginx")
            self.assertEqual(history.status_code, 200)
            history_payload = history.json()
            self.assertGreaterEqual(history_payload["total"], 1)
            self.assertEqual(history_payload["format"], "nginx")
            self.assertTrue(history_payload["entries"])
            self.assertTrue(history_payload["entries"][0]["artifactPath"])

            project_history = client.get(f"/api/runtime-ingress/history?projectId={project.project_id}&format=caddy")
            self.assertEqual(project_history.status_code, 200)
            project_history_payload = project_history.json()
            self.assertGreaterEqual(project_history_payload["total"], 1)
            self.assertEqual(project_history_payload["projectId"], project.project_id)
            self.assertEqual(project_history_payload["format"], "caddy")

    def test_runtime_ingress_bundle_publishes_to_gateway_when_configured(self) -> None:
        os.environ["SEO_AD_BOT_STATE_DIR"] = str(Path(self._tempdir.name) / "state")
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_URL": "https://runtime-ingress-gateway.example/publish",
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_ACCESS_TOKEN": "runtime-ingress-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            project = service.create_project(
                ProjectCreateRequest(
                    name="Runtime Ingress Gateway Project",
                    intake=SiteIntake(
                        url="https://runtime-ingress-gateway.example",
                        site_name="Runtime Ingress Gateway Project",
                    ),
                )
            )
            app = create_app(service)

            class _RuntimeIngressGatewayResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "deploymentId": "runtime-ingress-gateway-deploy-001",
                            "artifactId": "runtime-ingress-gateway-artifact-001",
                            "artifactUrl": "https://runtime-ingress-gateway.example/artifact/001",
                            "message": "runtime ingress published",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _RuntimeIngressGatewayResponse()

            def _mock_runtime_ingress_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_runtime_ingress_urlopen):
                published_bundle = client.post(
                    f"/api/runtime-ingress/bundle?projectId={project.project_id}&strictRoutesOnly=true",
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(published_bundle.status_code, 200)
            published_bundle_payload = published_bundle.json()
            self.assertTrue(published_bundle_payload["bundleReady"])
            self.assertIsNotNone(published_bundle_payload["gatewayPublish"])
            self.assertEqual(published_bundle_payload["gatewayPublish"]["status"], "completed")
            self.assertEqual(published_bundle_payload["gatewayPublish"]["gatewayEndpoint"], "https://runtime-ingress-gateway.example/publish")
            self.assertEqual(published_bundle_payload["gatewayPublish"]["gatewayArtifactId"], "runtime-ingress-gateway-artifact-001")
            self.assertEqual(published_bundle_payload["gatewayPublish"]["gatewayUrl"], "https://runtime-ingress-gateway.example/artifact/001")
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer runtime-ingress-gateway-token")
            bundle_path = Path(self._tempdir.name) / "state" / "runtime-ingress-bundle.json"
            self.assertTrue(bundle_path.exists())
            self.assertIn("gatewayPublish", json.loads(bundle_path.read_text(encoding="utf-8")))

    def test_runtime_ingress_bundle_gateway_failover_succeeds_on_secondary_endpoint(self) -> None:
        os.environ["SEO_AD_BOT_STATE_DIR"] = str(Path(self._tempdir.name) / "state")
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_URLS": "https://runtime-ingress-gateway.example/primary,https://runtime-ingress-gateway.example/secondary",
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_ACCESS_TOKEN": "runtime-ingress-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            project = service.create_project(
                ProjectCreateRequest(
                    name="Runtime Ingress Gateway Failover",
                    intake=SiteIntake(
                        url="https://runtime-ingress-failover.example",
                        site_name="Runtime Ingress Gateway Failover",
                    ),
                )
            )
            app = create_app(service)

            class _RuntimeIngressGatewayResponse:
                status = 200

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "deploymentId": "runtime-ingress-gateway-deploy-failover-001",
                            "artifactId": "runtime-ingress-gateway-artifact-failover-001",
                            "artifactUrl": "https://runtime-ingress-gateway.example/artifact/failover-001",
                            "message": "runtime ingress published with failover",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            attempted_endpoints: list[str] = []

            def _mock_runtime_ingress_urlopen(request, timeout=5):
                endpoint = str(getattr(request, "full_url", ""))
                attempted_endpoints.append(endpoint)
                if endpoint.endswith("/primary"):
                    raise HTTPError(endpoint, 503, "service unavailable", hdrs=None, fp=None)
                return _RuntimeIngressGatewayResponse()

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_runtime_ingress_urlopen):
                published_bundle = client.post(
                    f"/api/runtime-ingress/bundle?projectId={project.project_id}&strictRoutesOnly=true",
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(published_bundle.status_code, 200)
            published_bundle_payload = published_bundle.json()
            self.assertEqual(published_bundle_payload["gatewayPublish"]["status"], "completed")
            self.assertEqual(
                published_bundle_payload["gatewayPublish"]["gatewayEndpoint"],
                "https://runtime-ingress-gateway.example/secondary",
            )
            self.assertIn("gatewayFailover=true", published_bundle_payload["gatewayPublish"]["notes"])
            self.assertEqual(
                attempted_endpoints,
                [
                    "https://runtime-ingress-gateway.example/primary",
                    "https://runtime-ingress-gateway.example/secondary",
                ],
            )

    def test_runtime_ingress_bundle_gateway_failover_returns_last_failure_when_all_endpoints_fail(self) -> None:
        os.environ["SEO_AD_BOT_STATE_DIR"] = str(Path(self._tempdir.name) / "state")
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_URLS": "https://runtime-ingress-gateway.example/primary,https://runtime-ingress-gateway.example/secondary",
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_ACCESS_TOKEN": "runtime-ingress-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            project = service.create_project(
                ProjectCreateRequest(
                    name="Runtime Ingress Gateway Failover Failed",
                    intake=SiteIntake(
                        url="https://runtime-ingress-failover-failed.example",
                        site_name="Runtime Ingress Gateway Failover Failed",
                    ),
                )
            )
            app = create_app(service)
            attempted_endpoints: list[str] = []

            def _mock_runtime_ingress_urlopen(request, timeout=5):
                endpoint = str(getattr(request, "full_url", ""))
                attempted_endpoints.append(endpoint)
                if endpoint.endswith("/primary"):
                    raise HTTPError(endpoint, 503, "service unavailable", hdrs=None, fp=None)
                raise HTTPError(endpoint, 429, "rate limited", hdrs=None, fp=None)

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_runtime_ingress_urlopen):
                published_bundle = client.post(
                    f"/api/runtime-ingress/bundle?projectId={project.project_id}&strictRoutesOnly=true",
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(published_bundle.status_code, 200)
            published_bundle_payload = published_bundle.json()
            self.assertEqual(published_bundle_payload["gatewayPublish"]["status"], "failed")
            self.assertEqual(published_bundle_payload["gatewayPublish"]["failureCode"], "RUNTIME_INGRESS_GATEWAY_HTTP_429")
            self.assertEqual(
                published_bundle_payload["gatewayPublish"]["gatewayEndpoint"],
                "https://runtime-ingress-gateway.example/secondary",
            )
            self.assertTrue(
                any(str(note).startswith("attempt[1]=") for note in published_bundle_payload["gatewayPublish"]["notes"])
            )
            self.assertTrue(
                any(str(note).startswith("attempt[2]=") for note in published_bundle_payload["gatewayPublish"]["notes"])
            )
            self.assertEqual(
                attempted_endpoints,
                [
                    "https://runtime-ingress-gateway.example/primary",
                    "https://runtime-ingress-gateway.example/secondary",
                ],
            )

    def test_runtime_ingress_config_publish_to_gateway_with_failover(self) -> None:
        os.environ["SEO_AD_BOT_STATE_DIR"] = str(Path(self._tempdir.name) / "state")
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_URLS": "https://runtime-ingress-gateway.example/primary,https://runtime-ingress-gateway.example/secondary",
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_ACCESS_TOKEN": "runtime-ingress-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            project = service.create_project(
                ProjectCreateRequest(
                    name="Runtime Ingress Config Gateway Failover",
                    intake=SiteIntake(
                        url="https://runtime-ingress-config-failover.example",
                        site_name="Runtime Ingress Config Gateway Failover",
                    ),
                )
            )
            app = create_app(service)
            attempted_endpoints: list[str] = []

            class _IngressConfigGatewayResponse:
                status = 200

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "deploymentId": "runtime-ingress-config-gateway-deploy-001",
                            "artifactId": "runtime-ingress-config-gateway-artifact-001",
                            "artifactUrl": "https://runtime-ingress-gateway.example/config/artifact/001",
                            "message": "runtime ingress config published",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            def _mock_runtime_ingress_config_urlopen(request, timeout=5):
                endpoint = str(getattr(request, "full_url", ""))
                attempted_endpoints.append(endpoint)
                if endpoint.endswith("/primary"):
                    raise HTTPError(endpoint, 503, "service unavailable", hdrs=None, fp=None)
                return _IngressConfigGatewayResponse()

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_runtime_ingress_config_urlopen):
                published_artifact = client.post(
                    f"/api/runtime-ingress/nginx?projectId={project.project_id}&strictRoutesOnly=true",
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(published_artifact.status_code, 200)
            published_artifact_payload = published_artifact.json()
            self.assertTrue(published_artifact_payload["bundleReady"])
            self.assertIn("gatewayPublish", published_artifact_payload)
            self.assertEqual(published_artifact_payload["gatewayPublish"]["status"], "completed")
            self.assertEqual(
                published_artifact_payload["gatewayPublish"]["gatewayEndpoint"],
                "https://runtime-ingress-gateway.example/secondary",
            )
            self.assertIn("gatewayFailover=true", published_artifact_payload["gatewayPublish"]["notes"])
            self.assertEqual(
                attempted_endpoints,
                [
                    "https://runtime-ingress-gateway.example/primary",
                    "https://runtime-ingress-gateway.example/secondary",
                ],
            )

    def test_runtime_ingress_config_publish_gateway_returns_last_failure_when_all_endpoints_fail(self) -> None:
        os.environ["SEO_AD_BOT_STATE_DIR"] = str(Path(self._tempdir.name) / "state")
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_URLS": "https://runtime-ingress-gateway.example/primary,https://runtime-ingress-gateway.example/secondary",
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_ACCESS_TOKEN": "runtime-ingress-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            project = service.create_project(
                ProjectCreateRequest(
                    name="Runtime Ingress Config Gateway Failed",
                    intake=SiteIntake(
                        url="https://runtime-ingress-config-failed.example",
                        site_name="Runtime Ingress Config Gateway Failed",
                    ),
                )
            )
            app = create_app(service)
            attempted_endpoints: list[str] = []

            def _mock_runtime_ingress_config_urlopen(request, timeout=5):
                endpoint = str(getattr(request, "full_url", ""))
                attempted_endpoints.append(endpoint)
                if endpoint.endswith("/primary"):
                    raise HTTPError(endpoint, 502, "bad gateway", hdrs=None, fp=None)
                raise RuntimeError("network down")

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_runtime_ingress_config_urlopen):
                published_artifact = client.post(
                    f"/api/runtime-ingress/caddy?projectId={project.project_id}&strictRoutesOnly=true",
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(published_artifact.status_code, 200)
            published_artifact_payload = published_artifact.json()
            self.assertIn("gatewayPublish", published_artifact_payload)
            self.assertEqual(published_artifact_payload["gatewayPublish"]["status"], "failed")
            self.assertEqual(published_artifact_payload["gatewayPublish"]["failureCode"], "RUNTIME_INGRESS_GATEWAY_REQUEST_FAILED")
            self.assertEqual(
                published_artifact_payload["gatewayPublish"]["gatewayEndpoint"],
                "https://runtime-ingress-gateway.example/secondary",
            )
            self.assertTrue(
                any(str(note).startswith("attempt[1]=") for note in published_artifact_payload["gatewayPublish"]["notes"])
            )
            self.assertTrue(
                any(str(note).startswith("attempt[2]=") for note in published_artifact_payload["gatewayPublish"]["notes"])
            )
            self.assertEqual(
                attempted_endpoints,
                [
                    "https://runtime-ingress-gateway.example/primary",
                    "https://runtime-ingress-gateway.example/secondary",
                ],
            )

    def test_runtime_ingress_bundle_batch_publish_api(self) -> None:
        os.environ["SEO_AD_BOT_STATE_DIR"] = str(Path(self._tempdir.name) / "state")
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_URL": "https://runtime-ingress-gateway.example/publish",
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_ACCESS_TOKEN": "runtime-ingress-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            project_one = service.create_project(
                ProjectCreateRequest(
                    name="Runtime Ingress Batch One",
                    intake=SiteIntake(
                        url="https://runtime-ingress-batch-one.example",
                        site_name="Runtime Ingress Batch One",
                    ),
                )
            )
            project_two = service.create_project(
                ProjectCreateRequest(
                    name="Runtime Ingress Batch Two",
                    intake=SiteIntake(
                        url="https://runtime-ingress-batch-two.example",
                        site_name="Runtime Ingress Batch Two",
                    ),
                )
            )
            app = create_app(service)

            class _RuntimeIngressBatchResponse:
                status = 200

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "deploymentId": "runtime-ingress-batch-deploy-001",
                            "artifactId": "runtime-ingress-batch-artifact-001",
                            "artifactUrl": "https://runtime-ingress-gateway.example/artifact/batch-001",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            with TestClient(app) as client, patch(
                "apps.api.seo_ad_autopilot.service.urlopen",
                return_value=_RuntimeIngressBatchResponse(),
            ) as publish_mock:
                response = client.post(
                    "/api/runtime-ingress/bundle/batch",
                    json={
                        "projectIds": [project_one.project_id, project_two.project_id, project_one.project_id],
                        "strictRoutesOnly": True,
                        "actor": "qa",
                        "note": "runtime ingress batch publish smoke",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["totalCount"], 2)
            self.assertEqual(payload["completedCount"], 2)
            self.assertEqual(payload["blockedCount"], 0)
            self.assertEqual(payload["failedCount"], 0)
            self.assertEqual({item["projectId"] for item in payload["items"]}, {project_one.project_id, project_two.project_id})
            self.assertTrue(all(item["gatewayPublish"]["status"] == "completed" for item in payload["items"]))
            self.assertGreaterEqual(publish_mock.call_count, 2)

    def test_runtime_ingress_bundle_batch_publish_requires_api_key(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Ingress Batch Auth",
                intake=SiteIntake(
                    url="https://runtime-ingress-batch-auth.example",
                    site_name="Runtime Ingress Batch Auth",
                ),
            )
        )
        app = create_app(service)
        with TestClient(app) as client:
            blocked = client.post(
                "/api/runtime-ingress/bundle/batch",
                json={
                    "projectIds": [project.project_id],
                    "strictRoutesOnly": True,
                    "actor": "qa",
                    "note": "missing api key",
                },
            )
            self.assertEqual(blocked.status_code, 401)

    def test_runtime_ingress_bundle_batch_history_api_supports_project_filter(self) -> None:
        os.environ["SEO_AD_BOT_STATE_DIR"] = str(Path(self._tempdir.name) / "state")
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_URL": "https://runtime-ingress-gateway.example/publish",
                "SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_ACCESS_TOKEN": "runtime-ingress-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            project_one = service.create_project(
                ProjectCreateRequest(
                    name="Runtime Ingress Batch History One",
                    intake=SiteIntake(
                        url="https://runtime-ingress-batch-history-one.example",
                        site_name="Runtime Ingress Batch History One",
                    ),
                )
            )
            project_two = service.create_project(
                ProjectCreateRequest(
                    name="Runtime Ingress Batch History Two",
                    intake=SiteIntake(
                        url="https://runtime-ingress-batch-history-two.example",
                        site_name="Runtime Ingress Batch History Two",
                    ),
                )
            )
            app = create_app(service)

            class _RuntimeIngressBatchHistoryResponse:
                status = 200

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "deploymentId": "runtime-ingress-batch-history-deploy-001",
                            "artifactId": "runtime-ingress-batch-history-artifact-001",
                            "artifactUrl": "https://runtime-ingress-gateway.example/artifact/history-001",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            with TestClient(app) as client, patch(
                "apps.api.seo_ad_autopilot.service.urlopen",
                return_value=_RuntimeIngressBatchHistoryResponse(),
            ):
                publish = client.post(
                    "/api/runtime-ingress/bundle/batch",
                    json={
                        "projectIds": [project_one.project_id, project_two.project_id],
                        "strictRoutesOnly": True,
                        "actor": "qa",
                        "note": "runtime ingress batch history smoke",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(publish.status_code, 200)

                history = client.get("/api/runtime-ingress/bundle/batch/history", params={"limit": 5})
                self.assertEqual(history.status_code, 200)
                history_payload = history.json()
                self.assertGreaterEqual(history_payload["total"], 1)
                self.assertGreaterEqual(history_payload["completedCount"], 1)
                self.assertTrue(history_payload["entries"])
                self.assertIn(project_one.project_id, history_payload["entries"][0]["projectIds"])
                self.assertIn(project_two.project_id, history_payload["entries"][0]["projectIds"])

                project_history = client.get(
                    "/api/runtime-ingress/bundle/batch/history",
                    params={"projectId": project_one.project_id, "limit": 5},
                )
                self.assertEqual(project_history.status_code, 200)
                project_history_payload = project_history.json()
                self.assertEqual(project_history_payload["projectId"], project_one.project_id)
                self.assertTrue(project_history_payload["entries"])
                self.assertTrue(
                    all(project_one.project_id in entry["projectIds"] for entry in project_history_payload["entries"])
                )

                health = client.get("/api/runtime-ingress/bundle/batch/health")
                self.assertEqual(health.status_code, 200)
                health_payload = health.json()
                self.assertIn("healthy", health_payload)
                self.assertIn("stale", health_payload)
                self.assertGreaterEqual(health_payload["runCount"], 1)
                self.assertIsNotNone(health_payload["lastBatchId"])

                project_health = client.get(
                    "/api/runtime-ingress/bundle/batch/health",
                    params={"projectId": project_one.project_id},
                )
                self.assertEqual(project_health.status_code, 200)
                project_health_payload = project_health.json()
                self.assertEqual(project_health_payload["projectId"], project_one.project_id)
                self.assertGreaterEqual(project_health_payload["runCount"], 1)

    def test_runtime_edge_deploy_blocks_without_gateway_endpoint(self) -> None:
        os.environ.pop("SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL", None)
        policy_path = Path("var/runtime-edge-gateway.json")
        if policy_path.exists():
            policy_path.unlink()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Deploy Block",
                intake=SiteIntake(url="https://runtime-edge-deploy-block.example", site_name="Runtime Edge Deploy Block"),
            )
        )
        result = service.execute_runtime_edge_deployment(
            RuntimeEdgeDeploymentRequest(
                project_id=project.project_id,
                strict_routes_only=False,
                dry_run=False,
                actor="qa",
                note="runtime edge deploy missing gateway",
            )
        )
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.failure_code, "RUNTIME_EDGE_GATEWAY_ENDPOINT_MISSING")
        self.assertTrue(any("gatewayEndpointMissing=true" in note for note in result.notes))

    def test_runtime_edge_batch_deploy_publishes_multiple_projects_to_gateway(self) -> None:
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL"] = "https://runtime-edge-gateway.example/deploy"
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_ACCESS_TOKEN"] = "runtime-edge-token"
        service = self._service()
        project_one = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Batch One",
                intake=SiteIntake(url="https://runtime-edge-batch-one.example", site_name="Runtime Edge Batch One"),
            )
        )
        project_two = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Batch Two",
                intake=SiteIntake(url="https://runtime-edge-batch-two.example", site_name="Runtime Edge Batch Two"),
            )
        )

        class _DeployResponse:
            status = 200

            def __enter__(self) -> "_DeployResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "deploymentId": "runtime-edge-batch-deploy-001",
                        "artifactId": "runtime-edge-batch-artifact-001",
                        "artifactUrl": "https://runtime-edge-gateway.example/artifact/batch-001",
                    }
                ).encode("utf-8")

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_DeployResponse()) as deploy_mock:
            result = service.execute_runtime_edge_deployment_batch(
                RuntimeEdgeDeploymentBatchRequest(
                    project_ids=[project_one.project_id, project_two.project_id],
                    strict_routes_only=False,
                    dry_run=False,
                    actor="qa",
                    note="batch runtime edge deploy smoke",
                )
            )

        self.assertEqual(result.total_count, 2)
        self.assertEqual(result.executed_count, 2)
        self.assertEqual(result.blocked_count, 0)
        self.assertEqual(result.failed_count, 0)
        self.assertGreaterEqual(deploy_mock.call_count, 2)
        self.assertTrue(all(item.status == "executed" for item in result.items))
        self.assertEqual({item.project_id for item in result.items}, {project_one.project_id, project_two.project_id})

    def test_runtime_edge_batch_deploy_blocks_without_gateway_endpoint(self) -> None:
        os.environ.pop("SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL", None)
        os.environ.pop("SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_ACCESS_TOKEN", None)
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Batch Block",
                intake=SiteIntake(url="https://runtime-edge-batch-block.example", site_name="Runtime Edge Batch Block"),
            )
        )
        result = service.execute_runtime_edge_deployment_batch(
            RuntimeEdgeDeploymentBatchRequest(
                project_ids=[project.project_id],
                strict_routes_only=False,
                dry_run=False,
                actor="qa",
                note="batch runtime edge deploy missing gateway",
            )
        )
        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.executed_count, 0)
        self.assertEqual(result.blocked_count, 1)
        self.assertEqual(result.items[0].status, "blocked")
        self.assertEqual(result.items[0].failure_code, "RUNTIME_EDGE_GATEWAY_ENDPOINT_MISSING")

    def test_runtime_edge_batch_deploy_history_api_supports_project_filter(self) -> None:
        service = self._service()
        app = create_app(service)
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Batch History",
                intake=SiteIntake(url="https://runtime-edge-batch-history.example", site_name="Runtime Edge Batch History"),
            )
        )
        with TestClient(app) as client:
            response = client.get("/api/runtime-edge/deploy/batch/history", params={"limit": 5})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("entries", payload)
            self.assertIsNone(payload.get("projectId"))
            self.assertEqual(payload["summary"]["totalCount"], len(payload["entries"]))

            filtered = client.get("/api/runtime-edge/deploy/batch/history", params={"limit": 5, "projectId": project.project_id})
            self.assertEqual(filtered.status_code, 200)
            filtered_payload = filtered.json()
            self.assertEqual(filtered_payload["projectId"], project.project_id)
            self.assertIn("entries", filtered_payload)
            self.assertEqual(filtered_payload["summary"]["totalCount"], len(filtered_payload["entries"]))

    def test_runtime_edge_batch_enqueue_api_adds_worker_job(self) -> None:
        service = self._service()
        app = create_app(service)
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Batch Enqueue",
                intake=SiteIntake(url="https://runtime-edge-batch-enqueue.example", site_name="Runtime Edge Batch Enqueue"),
            )
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/runtime-edge/deploy/batch/enqueue",
                json={
                    "projectIds": [project.project_id],
                    "strictRoutesOnly": True,
                    "canaryPercent": 30,
                    "dryRun": False,
                    "actor": "qa",
                    "note": "enqueue runtime edge batch",
                },
                headers={"X-API-Key": "dev-key"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["enqueued"])
        self.assertFalse(payload["skippedDuplicate"])
        self.assertEqual(payload["stage"], "runtime_edge_deployment_batch")
        self.assertEqual(payload["projectIds"], [project.project_id])
        self.assertTrue(payload["strictRoutesOnly"])
        self.assertEqual(payload["canaryPercent"], 30)
        self.assertFalse(payload["dryRun"])

    def test_visual_farm_deploy_publishes_export_to_gateway(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINT"] = "https://visual-farm-gateway.example/deploy"
        os.environ["SEO_AD_BOT_VISUAL_FARM_ACCESS_TOKEN"] = "visual-farm-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Visual Farm Deploy Gateway",
                intake=SiteIntake(url="https://visual-farm-deploy.example", site_name="Visual Farm Deploy Gateway"),
            )
        )

        class _DeployResponse:
            status = 200

            def __enter__(self) -> "_DeployResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "deploymentId": "visual-farm-deploy-123",
                        "artifactId": "visual-farm-artifact-123",
                        "artifactUrl": "https://visual-farm-gateway.example/artifact/123",
                    }
                ).encode("utf-8")

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_DeployResponse()) as deploy_mock:
            result = service.execute_visual_farm_deployment(
                VisualFarmDeploymentRequest(
                    project_id=project.project_id,
                    task_id="task-visual-farm-deploy",
                    strict_mode=False,
                    dry_run=False,
                    actor="qa",
                    note="visual farm deploy gateway smoke",
                )
            )
        self.assertEqual(result.status, "executed")
        self.assertEqual(result.provider_endpoint, "https://visual-farm-gateway.example/deploy")
        self.assertEqual(result.provider_artifact_id, "visual-farm-artifact-123")
        self.assertEqual(result.provider_url, "https://visual-farm-gateway.example/artifact/123")
        self.assertIsNotNone(result.manifest_path)
        self.assertTrue(Path(result.manifest_path).exists())
        self.assertTrue(any("providerMode=external" in note for note in result.notes))
        self.assertGreaterEqual(deploy_mock.call_count, 1)

        app = create_app(service)
        with TestClient(app) as client:
            history = client.get("/api/visual-farm/deploy/history")
            self.assertEqual(history.status_code, 200)
            history_payload = history.json()
            self.assertGreaterEqual(history_payload["total"], 1)
            self.assertTrue(history_payload["items"])
            self.assertEqual(history_payload["items"][0]["providerEndpoint"], "https://visual-farm-gateway.example/deploy")
            self.assertEqual(history_payload["items"][0]["providerArtifactId"], "visual-farm-artifact-123")
            self.assertEqual(history_payload["items"][0]["providerUrl"], "https://visual-farm-gateway.example/artifact/123")
            filtered_history = client.get(f"/api/visual-farm/deploy/history?projectId={project.project_id}")
            self.assertEqual(filtered_history.status_code, 200)
            filtered_history_payload = filtered_history.json()
            self.assertEqual(filtered_history_payload["projectId"], project.project_id)
            self.assertEqual(filtered_history_payload["items"][0]["projectId"], project.project_id)

    def test_visual_farm_deploy_blocks_without_gateway_endpoint(self) -> None:
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ENDPOINT", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ENDPOINTS", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_GATEWAY_URL", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_GATEWAY_URLS", None)
        os.environ["SEO_AD_BOT_VISUAL_FARM_ACCESS_TOKEN"] = "visual-farm-token"
        policy_path = Path("var/visual-farm-gateway.json")
        if policy_path.exists():
            policy_path.unlink()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Visual Farm Deploy Block",
                intake=SiteIntake(url="https://visual-farm-deploy-block.example", site_name="Visual Farm Deploy Block"),
            )
        )
        result = service.execute_visual_farm_deployment(
            VisualFarmDeploymentRequest(
                project_id=project.project_id,
                task_id="task-visual-farm-deploy-block",
                strict_mode=False,
                dry_run=False,
                actor="qa",
                note="visual farm deploy missing gateway",
            )
        )
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.failure_code, "VISUAL_FARM_DEPLOYMENT_ENDPOINT_MISSING")
        self.assertTrue(any("providerMode=local" in note for note in result.notes))

    def test_visual_farm_deploy_gateway_route_failover_succeeds_on_secondary_endpoint(self) -> None:
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ENDPOINT", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ENDPOINTS", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_GATEWAY_URL", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_GATEWAY_URLS", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ACCESS_TOKEN", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_GATEWAY_ACCESS_TOKEN", None)
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Visual Farm Deploy Gateway Route Failover",
                intake=SiteIntake(url="https://visual-farm-route-failover.example", site_name="Visual Farm Route Failover"),
            )
        )
        service.update_visual_farm_gateway_policy(
            VisualFarmGatewayPolicyUpdateRequest(
                gateway_enabled=True,
                strict_routing=True,
                default_provider_name="visual_farm",
                fallback_provider_name="visual_farm",
                routes=[
                    VisualFarmGatewayRoute(
                        provider_name="visual_farm",
                        enabled=True,
                        fallback_provider_name="visual_farm",
                        priority=1,
                        endpoint="https://visual-farm-route-primary.example/deploy",
                        access_token="vf-route-token",
                        auth_header="X-Visual-Farm-Token",
                        notes=[
                            "endpoints=https://visual-farm-route-primary.example/deploy,https://visual-farm-route-secondary.example/deploy",
                        ],
                    )
                ],
            )
        )

        class _DeployResponse:
            status = 200

            def __enter__(self) -> "_DeployResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "deploymentId": "visual-farm-route-failover-001",
                        "artifactId": "visual-farm-route-artifact-001",
                        "artifactUrl": "https://visual-farm-route-secondary.example/artifact/001",
                    }
                ).encode("utf-8")

        attempted_urls: list[str] = []

        def _mock_urlopen(request, timeout=5):
            attempted_urls.append(str(request.full_url))
            if "route-primary" in str(request.full_url):
                raise HTTPError(str(request.full_url), 503, "Service Unavailable", hdrs=None, fp=None)
            return _DeployResponse()

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
            result = service.execute_visual_farm_deployment(
                VisualFarmDeploymentRequest(
                    project_id=project.project_id,
                    strict_mode=True,
                    dry_run=False,
                    actor="qa",
                    note="visual farm route failover deploy",
                )
            )

        self.assertEqual(result.status, "executed")
        self.assertEqual(result.provider_endpoint, "https://visual-farm-route-secondary.example/deploy")
        self.assertEqual(result.provider_artifact_id, "visual-farm-route-artifact-001")
        self.assertIn("https://visual-farm-route-primary.example/deploy", attempted_urls)
        self.assertIn("https://visual-farm-route-secondary.example/deploy", attempted_urls)
        self.assertTrue(any("attemptFailed=https://visual-farm-route-primary.example/deploy:http_503" in note for note in result.notes))

    def test_visual_farm_deploy_gateway_urls_all_failed_returns_last_failure(self) -> None:
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ENDPOINT", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ENDPOINTS", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_GATEWAY_URL", None)
        os.environ["SEO_AD_BOT_VISUAL_FARM_GATEWAY_URLS"] = (
            "https://visual-farm-gateway-fail-a.example/deploy,"
            "https://visual-farm-gateway-fail-b.example/deploy"
        )
        os.environ["SEO_AD_BOT_VISUAL_FARM_GATEWAY_ACCESS_TOKEN"] = "visual-farm-gateway-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Visual Farm Deploy Gateway URLs Fail",
                intake=SiteIntake(url="https://visual-farm-gateway-fail.example", site_name="Visual Farm Gateway URLs Fail"),
            )
        )

        def _mock_urlopen(request, timeout=5):
            if "fail-a" in str(request.full_url):
                raise HTTPError(str(request.full_url), 502, "Bad Gateway", hdrs=None, fp=None)
            raise HTTPError(str(request.full_url), 429, "Too Many Requests", hdrs=None, fp=None)

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
            result = service.execute_visual_farm_deployment(
                VisualFarmDeploymentRequest(
                    project_id=project.project_id,
                    strict_mode=False,
                    dry_run=False,
                    actor="qa",
                    note="visual farm gateway urls failed",
                )
            )

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.failure_code, "VISUAL_FARM_DEPLOYMENT_HTTP_429")
        self.assertFalse(result.retryable)
        self.assertIsNone(result.provider_endpoint)
        self.assertTrue(any("attemptedEndpointCount=2" in note for note in result.notes))

    def test_visual_farm_gateway_api_and_routed_deployment(self) -> None:
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ENDPOINT", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ENDPOINTS", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ACCESS_TOKEN", None)
        os.environ["SEO_AD_BOT_STATE_DIR"] = str(Path(self._tempdir.name) / "state")
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Visual Farm Gateway Publish",
                intake=SiteIntake(url="https://visual-farm-gateway-publish.example", site_name="Visual Farm Gateway Publish"),
            )
        )
        app = create_app(service)

        class _DeployResponse:
            status = 200

            def __init__(self):
                self.request_headers = {}

            def __enter__(self) -> "_DeployResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "deploymentId": "visual-farm-gateway-deploy-001",
                        "artifactId": "visual-farm-gateway-artifact-001",
                        "artifactUrl": "https://visual-farm-gateway.example/artifact/001",
                    }
                ).encode("utf-8")

        response_holder = _DeployResponse()

        def _mock_gateway_urlopen(request, timeout=5):
            response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
            return response_holder

        with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
            updated_gateway = client.put(
                "/api/visual-farm/gateway",
                json={
                    "gatewayEnabled": True,
                    "strictRouting": True,
                    "defaultProviderName": "visual_farm",
                    "fallbackProviderName": "visual_farm",
                    "routes": [
                        {
                            "providerName": "visual_farm",
                            "enabled": True,
                            "fallbackProviderName": "visual_farm",
                            "priority": 10,
                            "endpoint": "https://visual-farm-gateway.example/deploy",
                            "accessToken": "visual-farm-token",
                            "authHeader": "X-Visual-Farm-Token",
                            "notes": ["workspace visual farm gateway"],
                        }
                    ],
                    "notes": ["visual farm gateway smoke test"],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated_gateway.status_code, 200)
            gateway_payload = updated_gateway.json()
            self.assertTrue(gateway_payload["gatewayReady"])
            self.assertEqual(gateway_payload["routeReadyCount"], 1)
            self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "visual_farm")

            deployed = client.post(
                "/api/visual-farm/deploy",
                json={
                    "dryRun": False,
                    "strictMode": False,
                    "actor": "qa",
                    "note": "visual farm gateway",
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(deployed.status_code, 200)
            deployed_payload = deployed.json()
            self.assertEqual(deployed_payload["status"], "executed")
            self.assertEqual(deployed_payload["providerEndpoint"], "https://visual-farm-gateway.example/deploy")
            self.assertEqual(deployed_payload["providerArtifactId"], "visual-farm-gateway-artifact-001")
            self.assertEqual(deployed_payload["providerUrl"], "https://visual-farm-gateway.example/artifact/001")
            self.assertIsNotNone(deployed_payload["manifestPath"])
            self.assertTrue(Path(deployed_payload["manifestPath"]).exists())
            self.assertEqual(response_holder.request_headers.get("x-visual-farm-token"), "Bearer visual-farm-token")
            history = client.get("/api/visual-farm/gateway/history")
            self.assertEqual(history.status_code, 200)
            history_payload = history.json()
            self.assertGreaterEqual(history_payload["total"], 1)
            self.assertTrue(history_payload["entries"])
            self.assertEqual(history_payload["entries"][0]["latestProviderName"], "visual_farm")

            publish_gateway = client.post(
                f"/api/visual-farm/gateway/publish?projectId={project.project_id}",
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(publish_gateway.status_code, 200)
            publish_gateway_payload = publish_gateway.json()
            self.assertTrue(publish_gateway_payload["gatewayReady"])
            self.assertIsNotNone(publish_gateway_payload["gatewayPublish"])
            self.assertEqual(publish_gateway_payload["gatewayPublish"]["status"], "completed")
            self.assertEqual(publish_gateway_payload["gatewayPublish"]["gatewayEndpoint"], "https://visual-farm-gateway.example/deploy")
            self.assertEqual(publish_gateway_payload["gatewayPublish"]["gatewayArtifactId"], "visual-farm-gateway-artifact-001")
            self.assertEqual(publish_gateway_payload["gatewayPublish"]["gatewayUrl"], "https://visual-farm-gateway.example/artifact/001")
            self.assertEqual(response_holder.request_headers.get("x-visual-farm-token"), "Bearer visual-farm-token")

    def test_visual_farm_gateway_publish_failover_succeeds_on_secondary_endpoint(self) -> None:
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_GATEWAY_URL", None)
        os.environ["SEO_AD_BOT_VISUAL_FARM_GATEWAY_URLS"] = (
            "https://visual-farm-gateway-primary.example/publish,"
            "https://visual-farm-gateway-secondary.example/publish"
        )
        os.environ["SEO_AD_BOT_VISUAL_FARM_GATEWAY_ACCESS_TOKEN"] = "visual-farm-gateway-token"
        service = self._service()
        gateway_report = service.build_visual_farm_gateway_report()

        class _GatewayResponse:
            status = 200

            def __enter__(self) -> "_GatewayResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "artifactId": "visual_farm_gateway_artifact_failover_001",
                        "artifactUrl": "https://visual-farm-gateway-secondary.example/artifact/001",
                        "message": "visual farm gateway publish failover ok",
                    }
                ).encode("utf-8")

        request_urls: list[str] = []

        def _mock_urlopen(request, timeout=5):
            request_urls.append(str(request.full_url))
            if "primary" in str(request.full_url):
                raise HTTPError(str(request.full_url), 502, "Bad Gateway", hdrs=None, fp=None)
            return _GatewayResponse()

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
            publish = service._execute_visual_farm_gateway_publish(gateway_report)

        self.assertEqual(publish.status, "completed")
        self.assertEqual(publish.gateway_endpoint, "https://visual-farm-gateway-secondary.example/publish")
        self.assertEqual(publish.gateway_artifact_id, "visual_farm_gateway_artifact_failover_001")
        self.assertIn("https://visual-farm-gateway-primary.example/publish", request_urls)
        self.assertIn("https://visual-farm-gateway-secondary.example/publish", request_urls)
        self.assertTrue(any("attemptFailed=https://visual-farm-gateway-primary.example/publish:http_502" in note for note in publish.notes))

    def test_visual_farm_gateway_publish_failover_returns_last_failure_when_all_endpoints_fail(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_GATEWAY_URLS"] = (
            "https://visual-farm-gateway-fail-a.example/publish,"
            "https://visual-farm-gateway-fail-b.example/publish"
        )
        os.environ["SEO_AD_BOT_VISUAL_FARM_GATEWAY_ACCESS_TOKEN"] = "visual-farm-gateway-token"
        service = self._service()
        gateway_report = service.build_visual_farm_gateway_report()

        def _mock_urlopen(request, timeout=5):
            if "fail-a" in str(request.full_url):
                raise HTTPError(str(request.full_url), 503, "Service Unavailable", hdrs=None, fp=None)
            raise HTTPError(str(request.full_url), 429, "Too Many Requests", hdrs=None, fp=None)

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
            publish = service._execute_visual_farm_gateway_publish(gateway_report)

        self.assertEqual(publish.status, "failed")
        self.assertEqual(publish.failure_code, "VISUAL_FARM_GATEWAY_HTTP_429")
        self.assertFalse(publish.retryable)
        self.assertEqual(publish.gateway_endpoint, "https://visual-farm-gateway-fail-b.example/publish")
        self.assertTrue(any("attemptedEndpointCount=2" in note for note in publish.notes))

    def test_visual_farm_batch_deploy_publishes_multiple_projects_to_gateway(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINT"] = "https://visual-farm-gateway.example/deploy"
        os.environ["SEO_AD_BOT_VISUAL_FARM_ACCESS_TOKEN"] = "visual-farm-token"
        service = self._service()
        project_one = service.create_project(
            ProjectCreateRequest(
                name="Visual Farm Batch One",
                intake=SiteIntake(url="https://visual-farm-batch-one.example", site_name="Visual Farm Batch One"),
            )
        )
        project_two = service.create_project(
            ProjectCreateRequest(
                name="Visual Farm Batch Two",
                intake=SiteIntake(url="https://visual-farm-batch-two.example", site_name="Visual Farm Batch Two"),
            )
        )

        class _DeployResponse:
            status = 200

            def __enter__(self) -> "_DeployResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "deploymentId": "visual-farm-batch-deploy-001",
                        "artifactId": "visual-farm-batch-artifact-001",
                        "artifactUrl": "https://visual-farm-gateway.example/artifact/batch-001",
                    }
                ).encode("utf-8")

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_DeployResponse()) as deploy_mock:
            result = service.execute_visual_farm_deployment_batch(
                VisualFarmDeploymentBatchRequest(
                    project_ids=[project_one.project_id, project_two.project_id],
                    strict_mode=False,
                    dry_run=False,
                    actor="qa",
                    note="batch visual farm deploy smoke",
                )
            )

        self.assertEqual(result.total_count, 2)
        self.assertEqual(result.executed_count, 2)
        self.assertEqual(result.blocked_count, 0)
        self.assertEqual(result.failed_count, 0)
        self.assertGreaterEqual(deploy_mock.call_count, 2)
        self.assertTrue(all(item.status == "executed" for item in result.items))
        self.assertEqual({item.project_id for item in result.items}, {project_one.project_id, project_two.project_id})

    def test_visual_farm_batch_enqueue_api_adds_worker_job(self) -> None:
        service = self._service()
        app = create_app(service)
        project = service.create_project(
            ProjectCreateRequest(
                name="Visual Farm Batch Enqueue",
                intake=SiteIntake(url="https://visual-farm-batch-enqueue.example", site_name="Visual Farm Batch Enqueue"),
            )
        )
        with TestClient(app) as client:
            response = client.post(
                "/api/visual-farm/deploy/batch/enqueue",
                json={
                    "projectIds": [project.project_id],
                    "strictMode": True,
                    "dryRun": False,
                    "actor": "qa",
                    "note": "enqueue visual farm batch",
                },
                headers={"X-API-Key": "dev-key"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["enqueued"])
        self.assertFalse(payload["skippedDuplicate"])
        self.assertEqual(payload["stage"], "visual_farm_deployment_batch")
        self.assertEqual(payload["projectIds"], [project.project_id])
        self.assertTrue(payload["strictMode"])
        self.assertFalse(payload["dryRun"])

    def test_visual_farm_batch_deploy_blocks_without_gateway_endpoint(self) -> None:
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ENDPOINT", None)
        os.environ.pop("SEO_AD_BOT_VISUAL_FARM_ENDPOINTS", None)
        os.environ["SEO_AD_BOT_VISUAL_FARM_ACCESS_TOKEN"] = "visual-farm-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Visual Farm Batch Block",
                intake=SiteIntake(url="https://visual-farm-batch-block.example", site_name="Visual Farm Batch Block"),
            )
        )
        result = service.execute_visual_farm_deployment_batch(
            VisualFarmDeploymentBatchRequest(
                project_ids=[project.project_id],
                strict_mode=False,
                dry_run=False,
                actor="qa",
                note="batch visual farm deploy missing gateway",
            )
        )
        self.assertEqual(result.total_count, 1)
        self.assertEqual(result.executed_count, 0)
        self.assertEqual(result.blocked_count, 1)
        self.assertEqual(result.items[0].status, "blocked")
        self.assertEqual(result.items[0].failure_code, "VISUAL_FARM_DEPLOYMENT_ENDPOINT_MISSING")

    def test_visual_farm_deploy_batch_history_api_supports_project_filter(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINT"] = "https://visual-farm-gateway.example/deploy"
        os.environ["SEO_AD_BOT_VISUAL_FARM_ACCESS_TOKEN"] = "visual-farm-token"
        service = self._service()
        project_one = service.create_project(
            ProjectCreateRequest(
                name="Visual Farm Batch History One",
                intake=SiteIntake(url="https://visual-farm-batch-history-one.example", site_name="Visual Farm Batch History One"),
            )
        )
        project_two = service.create_project(
            ProjectCreateRequest(
                name="Visual Farm Batch History Two",
                intake=SiteIntake(url="https://visual-farm-batch-history-two.example", site_name="Visual Farm Batch History Two"),
            )
        )
        app = create_app(service)

        class _DeployResponse:
            status = 200

            def __enter__(self) -> "_DeployResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "deploymentId": "visual-farm-batch-history-deploy-001",
                        "artifactId": "visual-farm-batch-history-artifact-001",
                        "artifactUrl": "https://visual-farm-gateway.example/artifact/history-001",
                    }
                ).encode("utf-8")

        with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_DeployResponse()):
            publish = client.post(
                "/api/visual-farm/deploy/batch",
                json={
                    "projectIds": [project_one.project_id, project_two.project_id],
                    "strictMode": False,
                    "dryRun": False,
                    "actor": "qa",
                    "note": "visual farm batch history smoke",
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(publish.status_code, 200)

            history = client.get("/api/visual-farm/deploy/batch/history", params={"limit": 5})
            self.assertEqual(history.status_code, 200)
            history_payload = history.json()
            self.assertEqual(history_payload["summary"]["totalCount"], len(history_payload["entries"]))
            self.assertGreaterEqual(history_payload["total"], 1)
            self.assertGreaterEqual(history_payload["executedCount"], 2)
            self.assertTrue(history_payload["entries"])
            self.assertIn(project_one.project_id, history_payload["entries"][0]["projectIds"])
            self.assertIn(project_two.project_id, history_payload["entries"][0]["projectIds"])

            project_history = client.get(
                "/api/visual-farm/deploy/batch/history",
                params={"projectId": project_one.project_id, "limit": 5},
            )
            self.assertEqual(project_history.status_code, 200)
            project_history_payload = project_history.json()
            self.assertEqual(project_history_payload["projectId"], project_one.project_id)
            self.assertTrue(project_history_payload["entries"])
            self.assertTrue(all(project_one.project_id in entry["projectIds"] for entry in project_history_payload["entries"]))

    def test_acceptance_report_runtime_edge_probe_gate_requires_success_in_strict_mode(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        service = self._service()
        report_before = service.build_acceptance_report()
        probe_gate_before = next(item for item in report_before.gates if item.gate_id == "runtime_edge_probe_ready")
        self.assertFalse(probe_gate_before.passed)
        self.assertIn("probeExists=false", probe_gate_before.actual)

        class _ProbeOkResponse:
            status = 200
            headers = {"Content-Type": "application/json"}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"{}"

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_ProbeOkResponse()):
            service.execute_runtime_edge_probe(
                RuntimeEdgeProbeRequest(
                    strict_routes_only=True,
                    timeout_seconds=1.0,
                    actor="qa",
                )
            )
        report_after = service.build_acceptance_report()
        probe_gate_after = next(item for item in report_after.gates if item.gate_id == "runtime_edge_probe_ready")
        self.assertTrue(probe_gate_after.passed)
        self.assertIn("connected=", probe_gate_after.actual)

    def test_runtime_edge_probe_returns_connector_style_diagnostics(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Probe Meta",
                intake=SiteIntake(
                    url="https://runtime-probe-meta.example",
                    site_name="Runtime Probe Meta",
                    brand_whitelist=["Runtime"],
                    keywords=["seo", "runtime"],
                ),
            )
        )
        service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://runtime-probe-meta.example",
                site_name="Runtime Probe Meta",
                brand_whitelist=["Runtime"],
                keywords=["seo", "runtime"],
            ),
        )

        class _ProbeOkResponse:
            status = 200
            headers = {"Content-Type": "application/json"}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"{}"

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_ProbeOkResponse()):
            report = service.execute_runtime_edge_probe(
                RuntimeEdgeProbeRequest(
                    strict_routes_only=False,
                    timeout_seconds=1.0,
                    actor="qa",
                    project_id=project.project_id,
                )
            )
        self.assertGreaterEqual(report.total, 1)
        first = report.items[0]
        self.assertIsNotNone(first.auth_source)
        self.assertIsInstance(first.provenance, list)
        self.assertGreaterEqual(len(first.provenance), 1)
        if first.status == "failed":
            self.assertIsNotNone(first.failure_code)
            self.assertIsNotNone(first.fallback_reason)

    def test_worker_run_once_supports_project_filters(self) -> None:
        service = self._service()
        project_a = service.create_project(
            ProjectCreateRequest(
                name="Worker Target A",
                intake=SiteIntake(url="https://worker-target-a.example", site_name="Worker Target A"),
            )
        )
        project_b = service.create_project(
            ProjectCreateRequest(
                name="Worker Target B",
                intake=SiteIntake(url="https://worker-target-b.example", site_name="Worker Target B"),
            )
        )
        with service.database.session() as session:
            for project_id in (project_a.project_id, project_b.project_id):
                state = session.get(ProjectStateRow, project_id)
                assert state is not None
                state.auto_cruise_enabled = True
                state.next_sync_at = None
                session.add(state)

        result = service.run_worker_once(
            WorkerRunOnceRequest(
                project_ids=[project_a.project_id],
                include_approved_tasks=False,
                claim_limit=20,
            )
        )
        self.assertEqual(result.target_project_ids, [project_a.project_id])
        self.assertEqual(result.due_projects, 1)
        self.assertGreaterEqual(result.enqueued, 1)
        self.assertGreaterEqual(result.claimed, 1)
        self.assertGreaterEqual(result.processed, 1)

    def test_worker_run_once_does_not_enqueue_implicit_rollback_for_monitoring_tasks(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Worker Monitor No Rollback",
                intake=SiteIntake(
                    url="https://worker-monitor.example",
                    site_name="Worker Monitor",
                    brand_whitelist=["Worker"],
                    keywords=["seo", "growth"],
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://worker-monitor.example",
                site_name="Worker Monitor",
                brand_whitelist=["Worker"],
                keywords=["seo", "growth"],
            ),
        )
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="worker-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "deployed")

        with service.database.session() as session:
            row = session.get(TaskRow, bundle.task.task_id)
            assert row is not None
            row.status = "monitoring"
            row.stage = "monitoring"
            session.add(row)

        with patch.object(service, "monitor_task", return_value=service.get_workflow(bundle.task.task_id)) as monitor_mock:
            with patch.object(service, "rollback_task", wraps=service.rollback_task) as rollback_mock:
                result = service.run_worker_once(
                    WorkerRunOnceRequest(
                        project_ids=[project.project_id],
                        include_approved_tasks=True,
                        claim_limit=20,
                    )
                )

        self.assertGreaterEqual(result.enqueued, 1)
        self.assertGreaterEqual(result.claimed, 1)
        self.assertGreaterEqual(monitor_mock.call_count, 1)
        self.assertEqual(rollback_mock.call_count, 0)

    def test_visual_regression_run_enqueue_deduplicates_active_job(self) -> None:
        service = self._service()
        first = service.enqueue_visual_regression_run(
            VisualRegressionRunExecuteRequest(
                strict_mode=True,
                project_ids=[],
                max_cases=3,
            )
        )
        second = service.enqueue_visual_regression_run(
            VisualRegressionRunExecuteRequest(
                strict_mode=True,
                project_ids=[],
                max_cases=3,
            )
        )
        self.assertTrue(first.enqueued)
        self.assertFalse(first.skipped_duplicate)
        self.assertFalse(second.enqueued)
        self.assertTrue(second.skipped_duplicate)
        history = service.get_worker_execution_history(stage="visual_regression", status="queued", limit=20)
        self.assertGreaterEqual(history.total, 1)
        self.assertTrue(any(item.status == "queued" and item.stage == "visual_regression" for item in history.entries))

    def test_worker_processes_enqueued_visual_regression_job(self) -> None:
        service = self._service()
        enqueue_result = service.enqueue_visual_regression_run(
            VisualRegressionRunExecuteRequest(
                strict_mode=True,
                project_ids=[],
                max_cases=2,
            )
        )
        self.assertTrue(enqueue_result.enqueued)

        run_once = service.run_worker_once(
            WorkerRunOnceRequest(
                project_ids=[],
                include_approved_tasks=False,
                claim_limit=20,
            )
        )
        self.assertGreaterEqual(run_once.claimed, 1)
        self.assertGreaterEqual(run_once.processed, 1)

        completed = service.get_worker_execution_history(stage="visual_regression", status="completed", limit=20)
        self.assertGreaterEqual(completed.total, 1)
        self.assertTrue(any(item.stage == "visual_regression" and item.status == "completed" for item in completed.entries))

        with service.database.session() as session:
            visual_run_events = session.scalars(select(AuditRow).where(AuditRow.action == "visual_regressions.run.executed")).all()
        self.assertGreaterEqual(len(visual_run_events), 1)

    def test_deploy_task_enqueues_task_scoped_visual_regression_job(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Northstar Media",
                intake=SiteIntake(
                    url="https://northstar-media.example",
                    site_name="Northstar Media",
                    repo_url="https://github.com/example/northstar-media",
                    brand_whitelist=["Northstar"],
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://northstar-media.example",
                site_name="Northstar Media",
                repo_url="https://github.com/example/northstar-media",
                brand_whitelist=["Northstar"],
            ),
        )
        deployment_record = DeploymentRecord(
            deployment_id="deploy_test_visual_regression",
            task_id=bundle.task.task_id,
            mode=bundle.plan.deployment_mode,
            status="deployed",
            artifact_ref=bundle.preview.preview_id,
            release_notes=["Forced deployed for visual regression enqueue test."],
            rollback_ready=True,
        )
        with patch.object(service.coordinator.strategist, "build_deployment", return_value=deployment_record), patch.object(
            service, "_strict_publish_block_reason", return_value=None
        ), patch.object(service, "_strict_publish_blockers", return_value=[]), patch.object(
            service, "_verify_patch", return_value=(True, [], {})
        ):
            approved = service.approve_task(
                bundle.task.task_id,
                ApprovalDecisionRequest(
                    decision=ApprovalStatus.approved,
                    actor="ui",
                    note="Approve and deploy",
                ),
            )
        self.assertEqual(approved.deployment.status, "deployed")

        queued = service.get_worker_execution_history(stage="visual_regression", status="queued", project_id=project.project_id, limit=20)
        self.assertTrue(any(item.task_id == bundle.task.task_id and item.status == "queued" for item in queued.entries))

        with patch.object(service, "execute_visual_regression_runs", wraps=service.execute_visual_regression_runs) as execute_mock:
            run_once = service.run_worker_once(
                WorkerRunOnceRequest(
                    project_ids=[project.project_id],
                    include_approved_tasks=True,
                    claim_limit=20,
                )
            )

        self.assertGreaterEqual(run_once.claimed, 1)
        self.assertGreaterEqual(run_once.processed, 1)
        self.assertGreaterEqual(execute_mock.call_count, 1)
        request = execute_mock.call_args.args[0]
        self.assertIn(bundle.task.task_id, request.task_ids)
        self.assertIn(project.project_id, request.project_ids)

    def test_deploy_task_enqueues_runtime_edge_jobs(self) -> None:
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL"] = "https://runtime-edge-gateway.example/deploy"
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_ACCESS_TOKEN"] = "runtime-edge-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Northstar Media",
                intake=SiteIntake(
                    url="https://northstar-media.example",
                    site_name="Northstar Media",
                    repo_url="https://github.com/example/northstar-media",
                    brand_whitelist=["Northstar"],
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://northstar-media.example",
                site_name="Northstar Media",
                repo_url="https://github.com/example/northstar-media",
                brand_whitelist=["Northstar"],
            ),
        )
        deployment_record = DeploymentRecord(
            deployment_id="deploy_test_runtime_edge",
            task_id=bundle.task.task_id,
            mode=bundle.plan.deployment_mode,
            status="deployed",
            artifact_ref=bundle.preview.preview_id,
            release_notes=["Forced deployed for runtime edge enqueue test."],
            rollback_ready=True,
        )
        class _DeployResponse:
            status = 200

            def __enter__(self) -> "_DeployResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "deploymentId": "runtime-edge-deploy-789",
                        "artifactId": "runtime-edge-artifact-789",
                        "artifactUrl": "https://runtime-edge-gateway.example/artifact/789",
                    }
                ).encode("utf-8")

        with patch.object(service.coordinator.strategist, "build_deployment", return_value=deployment_record), patch.object(
            service, "_strict_publish_block_reason", return_value=None
        ), patch.object(service, "_strict_publish_blockers", return_value=[]), patch.object(
            service, "_verify_patch", return_value=(True, [], {})
        ), patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_DeployResponse()) as deploy_mock:
            service.approve_task(
                bundle.task.task_id,
                ApprovalDecisionRequest(
                    decision=ApprovalStatus.approved,
                    actor="ui",
                    note="Approve and deploy",
                ),
            )

        probe_history = service.get_worker_execution_history(stage="runtime_edge_probe", status="queued", project_id=project.project_id, limit=20)
        rollout_history = service.get_worker_execution_history(stage="runtime_edge_rollout", status="queued", project_id=project.project_id, limit=20)
        self.assertTrue(any(item.task_id == bundle.task.task_id and item.status == "queued" for item in probe_history.entries))
        self.assertTrue(any(item.task_id == bundle.task.task_id and item.status == "queued" for item in rollout_history.entries))

        with patch.object(service, "execute_runtime_edge_probe", return_value=None) as probe_mock, patch.object(
            service, "execute_runtime_edge_rollout", return_value=None
        ) as rollout_mock:
            run_once = service.run_worker_once(
                WorkerRunOnceRequest(
                    project_ids=[project.project_id],
                    include_approved_tasks=True,
                    claim_limit=20,
                )
            )

        self.assertGreaterEqual(run_once.claimed, 1)
        self.assertGreaterEqual(run_once.processed, 1)
        self.assertGreaterEqual(probe_mock.call_count, 1)
        self.assertGreaterEqual(rollout_mock.call_count, 1)
        self.assertGreaterEqual(deploy_mock.call_count, 1)
        approved = service.get_workflow(bundle.task.task_id)
        assert approved.deployment is not None
        self.assertEqual(approved.deployment.writeback_summary.get("runtimeEdgeDeployment", {}).get("status"), "executed")
        self.assertEqual(
            approved.deployment.writeback_summary.get("runtimeEdgeDeployment", {}).get("providerArtifactId"),
            "runtime-edge-artifact-789",
        )

    def test_deploy_task_enqueues_project_scoped_visual_farm_probe(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINT"] = "https://visual-farm-gateway.example/deploy"
        os.environ["SEO_AD_BOT_VISUAL_FARM_ACCESS_TOKEN"] = "visual-farm-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Northstar Visual Farm",
                intake=SiteIntake(
                    url="https://northstar-visual-farm.example",
                    site_name="Northstar Visual Farm",
                    repo_url="https://github.com/example/northstar-visual-farm",
                    brand_whitelist=["Northstar"],
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://northstar-visual-farm.example",
                site_name="Northstar Visual Farm",
                repo_url="https://github.com/example/northstar-visual-farm",
                brand_whitelist=["Northstar"],
            ),
        )
        deployment_record = DeploymentRecord(
            deployment_id="deploy_test_visual_farm",
            task_id=bundle.task.task_id,
            mode=bundle.plan.deployment_mode,
            status="deployed",
            artifact_ref=bundle.preview.preview_id,
            release_notes=["Forced deployed for visual farm enqueue test."],
            rollback_ready=True,
        )
        with patch.object(service.coordinator.strategist, "build_deployment", return_value=deployment_record), patch.object(
            service, "_strict_publish_block_reason", return_value=None
        ), patch.object(service, "_strict_publish_blockers", return_value=[]), patch.object(
            service, "_verify_patch", return_value=(True, [], {})
        ), patch("apps.api.seo_ad_autopilot.service.urlopen") as deploy_mock:
            deploy_mock.return_value.__enter__.return_value.status = 200
            deploy_mock.return_value.__enter__.return_value.read.return_value = json.dumps(
                {
                    "deploymentId": "visual-farm-deploy-456",
                    "artifactId": "visual-farm-artifact-456",
                    "artifactUrl": "https://visual-farm-gateway.example/artifact/456",
                }
            ).encode("utf-8")
            approved = service.approve_task(
                bundle.task.task_id,
                ApprovalDecisionRequest(
                    decision=ApprovalStatus.approved,
                    actor="ui",
                    note="Approve and deploy",
                ),
            )
        self.assertEqual(approved.deployment.status, "deployed")
        self.assertEqual(approved.deployment.writeback_summary.get("visualFarmDeployment", {}).get("status"), "executed")
        self.assertEqual(
            approved.deployment.writeback_summary.get("visualFarmDeployment", {}).get("providerArtifactId"),
            "visual-farm-artifact-456",
        )
        self.assertGreaterEqual(deploy_mock.call_count, 1)

        queued = service.get_worker_execution_history(stage="visual_farm_probe", status="queued", project_id=project.project_id, limit=20)
        self.assertTrue(any(item.task_id == bundle.task.task_id and item.status == "queued" for item in queued.entries))

        with patch.object(service, "probe_visual_farm", wraps=service.probe_visual_farm) as probe_mock:
            run_once = service.run_worker_once(
                WorkerRunOnceRequest(
                    project_ids=[project.project_id],
                    include_approved_tasks=True,
                    claim_limit=20,
                )
            )

        self.assertGreaterEqual(run_once.claimed, 1)
        self.assertGreaterEqual(run_once.processed, 1)
        self.assertGreaterEqual(probe_mock.call_count, 1)
        self.assertTrue(any(call.kwargs.get("project_id") == project.project_id for call in probe_mock.call_args_list))

    def test_visual_farm_probe_enqueue_deduplicates_active_job(self) -> None:
        service = self._service()
        first = service.enqueue_visual_farm_probe()
        second = service.enqueue_visual_farm_probe()
        self.assertTrue(first.enqueued)
        self.assertFalse(first.skipped_duplicate)
        self.assertFalse(second.enqueued)
        self.assertTrue(second.skipped_duplicate)
        history = service.get_worker_execution_history(stage="visual_farm_probe", status="queued", limit=20)
        self.assertGreaterEqual(history.total, 1)
        self.assertTrue(any(item.status == "queued" and item.stage == "visual_farm_probe" for item in history.entries))

    def test_runtime_ingress_bundle_batch_enqueue_deduplicates_active_job(self) -> None:
        service = self._service()
        first = service.enqueue_runtime_ingress_bundle_batch(
            RuntimeIngressBundleBatchRequest(
                project_ids=["project_a", "project_b"],
                strict_routes_only=True,
                actor="qa",
                note="runtime ingress batch enqueue test",
            )
        )
        second = service.enqueue_runtime_ingress_bundle_batch(
            RuntimeIngressBundleBatchRequest(
                project_ids=["project_a", "project_b"],
                strict_routes_only=True,
                actor="qa",
                note="runtime ingress batch enqueue test",
            )
        )
        self.assertTrue(first.enqueued)
        self.assertFalse(first.skipped_duplicate)
        self.assertFalse(second.enqueued)
        self.assertTrue(second.skipped_duplicate)
        history = service.get_worker_execution_history(stage="runtime_ingress_bundle_batch", status="queued", limit=20)
        self.assertGreaterEqual(history.total, 1)
        self.assertTrue(any(item.status == "queued" and item.stage == "runtime_ingress_bundle_batch" for item in history.entries))

    def test_worker_processes_enqueued_visual_farm_probe_job(self) -> None:
        service = self._service()
        enqueue_result = service.enqueue_visual_farm_probe()
        self.assertTrue(enqueue_result.enqueued)

        run_once = service.run_worker_once(
            WorkerRunOnceRequest(
                project_ids=[],
                include_approved_tasks=False,
                claim_limit=20,
            )
        )
        self.assertGreaterEqual(run_once.claimed, 1)
        self.assertGreaterEqual(run_once.processed, 1)

        completed = service.get_worker_execution_history(stage="visual_farm_probe", status="completed", limit=20)
        self.assertGreaterEqual(completed.total, 1)
        self.assertTrue(any(item.stage == "visual_farm_probe" and item.status == "completed" for item in completed.entries))

        with service.database.session() as session:
            visual_probe_events = session.scalars(select(AuditRow).where(AuditRow.action == "visual_farm.probe.executed")).all()
        self.assertGreaterEqual(len(visual_probe_events), 1)

    def test_worker_tick_auto_enqueues_visual_farm_probe_for_due_projects(self) -> None:
        probe_file = Path(self._tempdir.name) / "visual-farm-probe-ok.json"
        probe_file.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINT"] = probe_file.as_uri()

        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Visual Probe Due Project",
                intake=SiteIntake(url="https://visual-probe-due.example", site_name="Visual Probe Due Project"),
            )
        )
        with service.database.session() as session:
            state = session.get(ProjectStateRow, project.project_id)
            assert state is not None
            state.auto_cruise_enabled = True
            state.next_sync_at = None
            session.add(state)

        with patch.object(service, "execute_runtime_edge_probe", wraps=service.execute_runtime_edge_probe) as probe_mock, patch.object(
            service, "execute_runtime_edge_rollout", wraps=service.execute_runtime_edge_rollout
        ) as rollout_mock:
            result = service.run_worker_once(
                WorkerRunOnceRequest(
                    project_ids=[project.project_id],
                    include_approved_tasks=False,
                    claim_limit=20,
                )
            )
        self.assertGreaterEqual(result.due_projects, 1)
        self.assertGreaterEqual(result.enqueued, 1)
        self.assertGreaterEqual(result.claimed, 1)
        self.assertGreaterEqual(probe_mock.call_count, 1)
        runtime_edge_request = probe_mock.call_args.args[0]
        self.assertEqual(runtime_edge_request.project_id, project.project_id)
        self.assertGreaterEqual(rollout_mock.call_count, 3)
        rollout_stage_ids = [call.args[0].stage_id for call in rollout_mock.call_args_list]
        self.assertEqual(rollout_stage_ids.count("validate"), 1)
        self.assertEqual(rollout_stage_ids.count("canary"), 1)
        self.assertEqual(rollout_stage_ids.count("full"), 1)
        self.assertTrue(all(call.args[0].project_id == project.project_id for call in rollout_mock.call_args_list))
        self.assertTrue(any(call.args[0].stage_id == "validate" and call.args[0].dry_run for call in rollout_mock.call_args_list))
        self.assertTrue(any(call.args[0].stage_id == "canary" and not call.args[0].dry_run for call in rollout_mock.call_args_list))
        self.assertTrue(any(call.args[0].stage_id == "full" and not call.args[0].dry_run for call in rollout_mock.call_args_list))

        runtime_edge_queued = service.get_worker_execution_history(stage="runtime_edge_probe", status="queued", project_id=project.project_id, limit=20)
        self.assertTrue(any(item.stage == "runtime_edge_probe" and item.project_id == project.project_id for item in runtime_edge_queued.entries))
        rollout_queued = service.get_worker_execution_history(stage="runtime_edge_rollout", status="queued", project_id=project.project_id, limit=20)
        self.assertTrue(any(item.stage == "runtime_edge_rollout" and item.project_id == project.project_id for item in rollout_queued.entries))
        queued = service.get_worker_execution_history(stage="visual_farm_probe", status="queued", project_id=project.project_id, limit=20)
        self.assertTrue(any(item.stage == "visual_farm_probe" and item.project_id == project.project_id for item in queued.entries))

        runtime_edge_completed = service.get_worker_execution_history(stage="runtime_edge_probe", status="completed", project_id=project.project_id, limit=20)
        self.assertGreaterEqual(runtime_edge_completed.total, 1)
        self.assertTrue(any(item.stage == "runtime_edge_probe" and item.status == "completed" and item.project_id == project.project_id for item in runtime_edge_completed.entries))
        rollout_completed = service.get_worker_execution_history(stage="runtime_edge_rollout", status="completed", project_id=project.project_id, limit=20)
        self.assertGreaterEqual(rollout_completed.total, 3)
        self.assertTrue(any(item.stage == "runtime_edge_rollout" and item.status == "completed" and item.project_id == project.project_id and item.task_id == "rollout:validate" for item in rollout_completed.entries))
        self.assertTrue(any(item.stage == "runtime_edge_rollout" and item.status == "completed" and item.project_id == project.project_id and item.task_id == "rollout:canary" for item in rollout_completed.entries))
        self.assertTrue(any(item.stage == "runtime_edge_rollout" and item.status == "completed" and item.project_id == project.project_id and item.task_id == "rollout:full" for item in rollout_completed.entries))
        completed = service.get_worker_execution_history(stage="visual_farm_probe", status="completed", limit=20)
        self.assertGreaterEqual(completed.total, 1)
        self.assertTrue(any(item.stage == "visual_farm_probe" and item.status == "completed" and item.project_id == project.project_id for item in completed.entries))

    def test_worker_tick_auto_enqueues_visual_regression_for_due_projects(self) -> None:
        probe_file = Path(self._tempdir.name) / "visual-farm-regression-ok.json"
        probe_file.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINT"] = probe_file.as_uri()
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"

        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Visual Regression Due Project",
                intake=SiteIntake(url="https://visual-regression-due.example", site_name="Visual Regression Due Project"),
            )
        )
        with service.database.session() as session:
            state = session.get(ProjectStateRow, project.project_id)
            assert state is not None
            state.auto_cruise_enabled = True
            state.next_sync_at = None
            session.add(state)

        with patch.object(service, "execute_visual_regression_runs", return_value=None) as visual_mock, patch.object(
            service, "execute_runtime_edge_probe", return_value=None
        ), patch.object(service, "execute_runtime_edge_rollout", return_value=None), patch.object(
            service, "probe_visual_farm", return_value=None
        ):
            result = service.run_worker_once(
                WorkerRunOnceRequest(
                    project_ids=[project.project_id],
                    include_approved_tasks=False,
                    claim_limit=30,
                )
            )

        self.assertGreaterEqual(result.due_projects, 1)
        self.assertGreaterEqual(result.enqueued, 1)
        self.assertGreaterEqual(result.claimed, 1)
        self.assertGreaterEqual(result.processed, 1)
        self.assertGreaterEqual(visual_mock.call_count, 1)
        request = visual_mock.call_args.args[0]
        self.assertTrue(request.strict_mode)
        self.assertIn(project.project_id, request.project_ids)
        self.assertEqual(request.max_cases, 20)

        queued = service.get_worker_execution_history(stage="visual_regression", status="queued", project_id=project.project_id, limit=20)
        self.assertTrue(any(item.stage == "visual_regression" and item.project_id == project.project_id for item in queued.entries))
        completed = service.get_worker_execution_history(
            stage="visual_regression",
            status="completed",
            project_id=project.project_id,
            limit=20,
        )
        self.assertTrue(any(item.stage == "visual_regression" and item.status == "completed" and item.project_id == project.project_id for item in completed.entries))

    def test_worker_tick_auto_enqueues_visual_farm_deployment_batch_for_due_projects(self) -> None:
        probe_file = Path(self._tempdir.name) / "visual-farm-deployment-ok.json"
        probe_file.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINT"] = probe_file.as_uri()
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"

        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Visual Farm Deploy Due Project",
                intake=SiteIntake(url="https://visual-farm-deploy-due.example", site_name="Visual Farm Deploy Due Project"),
            )
        )
        with service.database.session() as session:
            state = session.get(ProjectStateRow, project.project_id)
            assert state is not None
            state.auto_cruise_enabled = True
            state.next_sync_at = None
            session.add(state)

        with patch.object(service, "execute_visual_farm_deployment_batch", return_value=None) as deploy_batch_mock, patch.object(
            service, "execute_runtime_edge_probe", return_value=None
        ), patch.object(service, "execute_runtime_edge_rollout", return_value=None), patch.object(
            service, "execute_visual_regression_runs", return_value=None
        ), patch.object(
            service, "probe_visual_farm", return_value=None
        ):
            result = service.run_worker_once(
                WorkerRunOnceRequest(
                    project_ids=[project.project_id],
                    include_approved_tasks=False,
                    claim_limit=40,
                )
            )

        self.assertGreaterEqual(result.due_projects, 1)
        self.assertGreaterEqual(result.enqueued, 1)
        self.assertGreaterEqual(result.claimed, 1)
        self.assertGreaterEqual(result.processed, 1)
        self.assertGreaterEqual(deploy_batch_mock.call_count, 1)
        batch_request = deploy_batch_mock.call_args.args[0]
        self.assertIn(project.project_id, batch_request.project_ids)
        self.assertTrue(batch_request.strict_mode)
        self.assertEqual(batch_request.actor, "worker")

        queued = service.get_worker_execution_history(
            stage="visual_farm_deployment_batch",
            status="queued",
            project_id="workspace",
            limit=20,
        )
        self.assertTrue(any(item.stage == "visual_farm_deployment_batch" for item in queued.entries))
        completed = service.get_worker_execution_history(
            stage="visual_farm_deployment_batch",
            status="completed",
            project_id="workspace",
            limit=20,
        )
        self.assertTrue(any(item.stage == "visual_farm_deployment_batch" and item.status == "completed" for item in completed.entries))

    def test_worker_tick_auto_enqueues_runtime_edge_deployment_batch_for_due_projects(self) -> None:
        edge_file = Path(self._tempdir.name) / "runtime-edge-deployment-ok.json"
        edge_file.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_URL"] = edge_file.as_uri()
        os.environ["SEO_AD_BOT_RUNTIME_EDGE_GATEWAY_ACCESS_TOKEN"] = "runtime-edge-token"
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"

        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Edge Batch Due Project",
                intake=SiteIntake(url="https://runtime-edge-batch-due.example", site_name="Runtime Edge Batch Due Project"),
            )
        )
        with service.database.session() as session:
            state = session.get(ProjectStateRow, project.project_id)
            assert state is not None
            state.auto_cruise_enabled = True
            state.next_sync_at = None
            session.add(state)

        with patch.object(service, "execute_runtime_edge_deployment_batch", return_value=None) as batch_mock, patch.object(
            service, "execute_runtime_edge_probe", return_value=None
        ), patch.object(service, "execute_runtime_edge_rollout", return_value=None), patch.object(
            service, "execute_visual_farm_deployment_batch", return_value=None
        ), patch.object(service, "execute_visual_regression_runs", return_value=None), patch.object(
            service, "probe_visual_farm", return_value=None
        ):
            result = service.run_worker_once(
                WorkerRunOnceRequest(
                    project_ids=[project.project_id],
                    include_approved_tasks=False,
                    claim_limit=40,
                )
            )

        self.assertGreaterEqual(result.due_projects, 1)
        self.assertGreaterEqual(result.enqueued, 1)
        self.assertGreaterEqual(result.claimed, 1)
        self.assertGreaterEqual(result.processed, 1)
        self.assertGreaterEqual(batch_mock.call_count, 1)
        batch_request = batch_mock.call_args.args[0]
        self.assertIn(project.project_id, batch_request.project_ids)
        self.assertTrue(batch_request.strict_routes_only)
        self.assertEqual(batch_request.actor, "worker")

        queued = service.get_worker_execution_history(
            stage="runtime_edge_deployment_batch",
            status="queued",
            project_id="workspace",
            limit=20,
        )
        self.assertTrue(any(item.stage == "runtime_edge_deployment_batch" for item in queued.entries))
        completed = service.get_worker_execution_history(
            stage="runtime_edge_deployment_batch",
            status="completed",
            project_id="workspace",
            limit=20,
        )
        self.assertTrue(any(item.stage == "runtime_edge_deployment_batch" and item.status == "completed" for item in completed.entries))

    def test_worker_tick_auto_enqueues_visual_farm_probe_when_probe_is_stale(self) -> None:
        probe_file = Path(self._tempdir.name) / "visual-farm-probe-refresh.json"
        probe_file.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINT"] = probe_file.as_uri()
        os.environ["SEO_AD_BOT_VISUAL_FARM_PROBE_FRESHNESS_MINUTES"] = "30"

        service = self._service()
        with service.database.session() as session:
            session.add(
                AuditRow(
                    id="audit_worker_stale_probe",
                    project_id="workspace",
                    task_id="",
                    action="visual_farm.probe.executed",
                    actor="system",
                    payload_json={
                        "strictMode": True,
                        "configuredEndpointCount": 1,
                        "probedEndpointCount": 1,
                        "connectedCount": 1,
                        "failedCount": 0,
                        "notConfiguredCount": 0,
                        "blockingCount": 0,
                        "recoverableCount": 0,
                        "accessTokenConfigured": True,
                        "timeoutMs": 12000,
                        "probes": [],
                        "notes": [],
                    },
                    created_at=datetime.now(timezone.utc) - timedelta(minutes=90),
                )
            )

        run_once = service.run_worker_once(
            WorkerRunOnceRequest(
                project_ids=[],
                include_approved_tasks=False,
                claim_limit=20,
            )
        )
        self.assertEqual(run_once.due_projects, 0)
        self.assertGreaterEqual(run_once.enqueued, 1)
        self.assertGreaterEqual(run_once.claimed, 1)

        completed = service.get_worker_execution_history(stage="visual_farm_probe", status="completed", limit=20)
        self.assertGreaterEqual(completed.total, 1)
        self.assertTrue(any(item.stage == "visual_farm_probe" and item.status == "completed" for item in completed.entries))
        visual_regression_queued = service.get_worker_execution_history(stage="visual_regression", status="queued", project_id="workspace", limit=20)
        self.assertTrue(any(item.stage == "visual_regression" and item.project_id == "workspace" for item in visual_regression_queued.entries))
        visual_regression_completed = service.get_worker_execution_history(
            stage="visual_regression",
            status="completed",
            project_id="workspace",
            limit=20,
        )
        self.assertTrue(
            any(item.stage == "visual_regression" and item.status == "completed" and item.project_id == "workspace" for item in visual_regression_completed.entries)
        )

    def test_worker_tick_auto_enqueues_runtime_ingress_bundle_batch_for_due_projects(self) -> None:
        os.environ["SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_URL"] = "https://runtime-ingress-worker.example/publish"
        os.environ["SEO_AD_BOT_RUNTIME_INGRESS_GATEWAY_ACCESS_TOKEN"] = "runtime-ingress-worker-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Ingress Worker Due Project",
                intake=SiteIntake(
                    url="https://runtime-ingress-worker-due.example",
                    site_name="Runtime Ingress Worker Due Project",
                ),
            )
        )
        with service.database.session() as session:
            state = session.get(ProjectStateRow, project.project_id)
            assert state is not None
            state.auto_cruise_enabled = True
            state.next_sync_at = None
            session.add(state)

        with patch.object(service, "execute_runtime_ingress_bundle_batch", return_value=None) as ingress_batch_mock:
            result = service.run_worker_once(
                WorkerRunOnceRequest(
                    project_ids=[project.project_id],
                    include_approved_tasks=False,
                    claim_limit=30,
                )
            )

        self.assertGreaterEqual(result.due_projects, 1)
        self.assertGreaterEqual(result.enqueued, 1)
        self.assertGreaterEqual(result.claimed, 1)
        self.assertGreaterEqual(result.processed, 1)
        self.assertGreaterEqual(ingress_batch_mock.call_count, 1)
        request = ingress_batch_mock.call_args.args[0]
        self.assertIn(project.project_id, request.project_ids)
        self.assertFalse(request.strict_routes_only)

        queued = service.get_worker_execution_history(
            stage="runtime_ingress_bundle_batch",
            status="queued",
            project_id="workspace",
            limit=20,
        )
        self.assertTrue(any(item.stage == "runtime_ingress_bundle_batch" and item.project_id == "workspace" for item in queued.entries))
        completed = service.get_worker_execution_history(
            stage="runtime_ingress_bundle_batch",
            status="completed",
            project_id="workspace",
            limit=20,
        )
        self.assertTrue(any(item.stage == "runtime_ingress_bundle_batch" and item.status == "completed" for item in completed.entries))

    def test_worker_cli_once_uses_run_once_request_options(self) -> None:
        service = self._service()
        args = worker_module.build_parser().parse_args(
            [
                "--once",
                "--project-id",
                "project_a",
                "--project-id",
                "project_b",
                "--claim-limit",
                "33",
                "--exclude-approved-tasks",
            ]
        )
        expected = WorkerRunOnceResult(
            processed=1,
            enqueued=2,
            skipped_duplicates=0,
            claimed=1,
            due_projects=2,
            target_project_ids=["project_a", "project_b"],
        )
        with patch.object(service, "run_worker_once", return_value=expected) as run_once_mock:
            worker_module.run_worker(args, service)
        self.assertEqual(run_once_mock.call_count, 1)
        request = run_once_mock.call_args[0][0]
        self.assertEqual(request.project_ids, ["project_a", "project_b"])
        self.assertFalse(request.include_approved_tasks)
        self.assertEqual(request.claim_limit, 33)

    def test_worker_cli_daemon_stops_on_max_iterations(self) -> None:
        service = self._service()
        args = worker_module.build_parser().parse_args(["--interval", "1", "--max-iterations", "2"])
        results = [
            WorkerRunOnceResult(
                processed=0,
                enqueued=0,
                skipped_duplicates=0,
                claimed=0,
                due_projects=0,
                target_project_ids=[],
            ),
            WorkerRunOnceResult(
                processed=1,
                enqueued=1,
                skipped_duplicates=0,
                claimed=1,
                due_projects=1,
                target_project_ids=[],
            ),
        ]
        with patch.object(service, "run_worker_once", side_effect=results) as run_once_mock:
            with patch("apps.api.seo_ad_autopilot.worker.time.sleep") as sleep_mock:
                worker_module.run_worker(args, service)
        self.assertEqual(run_once_mock.call_count, 2)
        self.assertEqual(sleep_mock.call_count, 1)

    def test_worker_service_once_writes_state_file(self) -> None:
        service = self._service()
        state_path = Path(self._tempdir.name) / "worker-state.json"
        args = argparse.Namespace(
            once=True,
            interval=1,
            max_iterations=0,
            project_id=[],
            claim_limit=50,
            exclude_approved_tasks=False,
            max_failures=0,
            health_host="127.0.0.1",
            health_port=0,
            pid_file="",
            state_file=str(state_path),
        )
        code = worker_service_module.run_service(args, service)
        self.assertEqual(code, 0)
        self.assertTrue(state_path.exists())
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(payload.get("status"), "stopped")
        self.assertIn("processed", payload)

    def test_worker_service_respects_max_failures(self) -> None:
        service = self._service()
        args = argparse.Namespace(
            once=False,
            interval=1,
            max_iterations=5,
            project_id=[],
            claim_limit=50,
            exclude_approved_tasks=False,
            max_failures=1,
            health_host="127.0.0.1",
            health_port=0,
            pid_file="",
            state_file="",
        )
        with patch.object(service, "run_worker_once", side_effect=RuntimeError("worker boom")):
            code = worker_service_module.run_service(args, service)
        self.assertEqual(code, 1)

    def test_monitor_task_enqueues_rollback_job_on_regression(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Monitor Regression Queue",
                intake=SiteIntake(
                    url="https://monitor-regression.example",
                    site_name="Monitor Regression",
                    brand_whitelist=["Monitor"],
                    keywords=["seo", "growth"],
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://monitor-regression.example",
                site_name="Monitor Regression",
                brand_whitelist=["Monitor"],
                keywords=["seo", "growth"],
            ),
        )
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="monitor-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "deployed")
        self.assertIsNotNone(approved.metric_snapshot)

        regressed_metric = approved.metric_snapshot.model_copy(
            update={
                "snapshot_id": "metric_regressed_test",
                "traffic_delta": -12,
                "core_web_vitals": {"lcpMs": 9999, "cls": 10, "inpMs": 400},
            }
        )
        with patch.object(service.coordinator.strategist, "build_metrics", return_value=regressed_metric):
            monitored = service.monitor_task(bundle.task.task_id)

        self.assertEqual(monitored.task.status, WorkflowStage.monitoring)
        self.assertIsNone(monitored.rollback_bundle)
        queued = service.job_queue.claim(limit=20)
        rollback_jobs = [job for job in queued if job.stage == "rollback" and job.task_id == bundle.task.task_id]
        self.assertTrue(rollback_jobs)

    def test_monitor_and_rollback_are_recorded_in_project_runs(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Monitor Rollback Run History",
                intake=SiteIntake(
                    url="https://monitor-runs.example",
                    site_name="Monitor Runs",
                    brand_whitelist=["Monitor"],
                    keywords=["seo", "growth"],
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://monitor-runs.example",
                site_name="Monitor Runs",
                brand_whitelist=["Monitor"],
                keywords=["seo", "growth"],
            ),
        )
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="monitor-run-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "deployed")
        self.assertIsNotNone(approved.metric_snapshot)

        regressed_metric = approved.metric_snapshot.model_copy(
            update={
                "snapshot_id": "metric_regressed_run_history_test",
                "traffic_delta": -20,
                "core_web_vitals": {"lcpMs": 9999, "cls": 10, "inpMs": 500},
            }
        )
        with patch.object(service.coordinator.strategist, "build_metrics", return_value=regressed_metric):
            service.monitor_task(bundle.task.task_id)

        # Process the rollback job generated by monitor_task.
        service.run_worker_once(
            WorkerRunOnceRequest(
                project_ids=[project.project_id],
                include_approved_tasks=False,
                claim_limit=20,
            )
        )

        runs = service.list_project_runs(project.project_id)
        self.assertTrue(runs)
        monitor_failed = [run for run in runs if run.trigger == RunTrigger.monitor and run.status == RunStatus.failed]
        rolled_back = [run for run in runs if run.trigger == RunTrigger.rollback and run.status == RunStatus.rolled_back]
        self.assertTrue(monitor_failed)
        self.assertTrue(rolled_back)

    def test_list_project_runs_supports_trigger_status_and_limit_filters(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Run Filter Project",
                intake=SiteIntake(
                    url="https://run-filter.example",
                    site_name="Run Filter",
                    brand_whitelist=["Run"],
                    keywords=["seo", "growth"],
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://run-filter.example",
                site_name="Run Filter",
                brand_whitelist=["Run"],
                keywords=["seo", "growth"],
            ),
        )
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="run-filter-test"),
        )
        self.assertIsNotNone(approved.metric_snapshot)
        regressed_metric = approved.metric_snapshot.model_copy(
            update={
                "snapshot_id": "metric_regressed_filter_test",
                "traffic_delta": -9,
                "core_web_vitals": {"lcpMs": 9999, "cls": 8, "inpMs": 390},
            }
        )
        with patch.object(service.coordinator.strategist, "build_metrics", return_value=regressed_metric):
            service.monitor_task(bundle.task.task_id)
        service.run_worker_once(
            WorkerRunOnceRequest(project_ids=[project.project_id], include_approved_tasks=False, claim_limit=20)
        )

        all_runs = service.list_project_runs(project.project_id)
        self.assertGreaterEqual(len(all_runs), 2)
        monitor_runs = service.list_project_runs(project.project_id, trigger=RunTrigger.monitor)
        self.assertTrue(monitor_runs)
        self.assertTrue(all(item.trigger == RunTrigger.monitor for item in monitor_runs))
        failed_runs = service.list_project_runs(project.project_id, status=RunStatus.failed)
        self.assertTrue(failed_runs)
        self.assertTrue(all(item.status == RunStatus.failed for item in failed_runs))
        monitor_failed_limited = service.list_project_runs(
            project.project_id,
            trigger=RunTrigger.monitor,
            status=RunStatus.failed,
            limit=1,
        )
        self.assertEqual(len(monitor_failed_limited), 1)
        self.assertEqual(monitor_failed_limited[0].trigger, RunTrigger.monitor)
        self.assertEqual(monitor_failed_limited[0].status, RunStatus.failed)
        rollback_limited = service.list_project_runs(
            project.project_id,
            trigger=RunTrigger.rollback,
            status=RunStatus.rolled_back,
            limit=1,
        )
        self.assertEqual(len(rollback_limited), 1)
        self.assertEqual(rollback_limited[0].trigger, RunTrigger.rollback)
        self.assertEqual(rollback_limited[0].status, RunStatus.rolled_back)

    def test_project_runs_api_supports_trigger_status_and_limit_filters(self) -> None:
        service = self._service()
        app = create_app(service)
        project_payload = {
            "name": "Runs API Filter",
            "intake": {
                "url": "https://runs-api-filter.example",
                "siteName": "Runs API Filter",
                "brandWhitelist": ["Runs"],
                "keywords": ["seo", "growth"],
            },
        }
        with TestClient(app) as client:
            created = client.post("/api/projects", json=project_payload, headers={"X-API-Key": "dev-key"})
            self.assertEqual(created.status_code, 200)
            project_id = created.json()["projectId"]

            sync = client.post(f"/api/projects/{project_id}/sync", headers={"X-API-Key": "dev-key"})
            self.assertEqual(sync.status_code, 200)
            task_id = sync.json()["task"]["taskId"]

            approve = client.post(
                f"/api/tasks/{task_id}/approve",
                json={"decision": "approved", "actor": "runs-api-test"},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(approve.status_code, 200)
            approved_payload = approve.json()
            self.assertIn("metricSnapshot", approved_payload)
            self.assertIsNotNone(approved_payload["metricSnapshot"])

            metric_payload = dict(approved_payload["metricSnapshot"])
            metric_payload["snapshotId"] = "metric_regressed_runs_api_test"
            metric_payload["trafficDelta"] = -15
            metric_payload["coreWebVitals"] = {"lcpMs": 9999, "cls": 9, "inpMs": 420}
            regressed_metric = MetricSnapshot.model_validate(metric_payload)
            with patch.object(service.coordinator.strategist, "build_metrics", return_value=regressed_metric):
                monitored = service.monitor_task(task_id)
                self.assertEqual(monitored.task.status, WorkflowStage.monitoring)
            service.run_worker_once(
                WorkerRunOnceRequest(project_ids=[project_id], include_approved_tasks=False, claim_limit=20)
            )

            filtered = client.get(
                f"/api/projects/{project_id}/runs",
                params={"trigger": "monitor", "status": "failed", "limit": 1},
            )
            self.assertEqual(filtered.status_code, 200)
            payload = filtered.json()
            self.assertLessEqual(len(payload), 1)
            self.assertTrue(payload)
            self.assertTrue(all(item["trigger"] == "monitor" for item in payload))
            self.assertTrue(all(item["status"] == "failed" for item in payload))
            rollback_filtered = client.get(
                f"/api/projects/{project_id}/runs",
                params={"trigger": "rollback", "status": "rolled_back", "limit": 1},
            )
            self.assertEqual(rollback_filtered.status_code, 200)
            rollback_payload = rollback_filtered.json()
            self.assertLessEqual(len(rollback_payload), 1)
            self.assertTrue(rollback_payload)
            self.assertTrue(all(item["trigger"] == "rollback" for item in rollback_payload))
            self.assertTrue(all(item["status"] == "rolled_back" for item in rollback_payload))

    def test_artifact_store_http_backend_returns_remote_refs(self) -> None:
        os.environ["SEO_AD_BOT_ARTIFACT_STORE_BACKEND"] = "http"
        os.environ["SEO_AD_BOT_ARTIFACT_STORE_HTTP_BASE_URL"] = "https://artifact.example/upload"
        os.environ["SEO_AD_BOT_ARTIFACT_STORE_HTTP_TOKEN"] = "token-123"
        get_settings.cache_clear()

        class _DummyResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.artifact_store.urlopen", return_value=_DummyResponse()) as mocked:
            store = get_artifact_store()
            artifact = store.write_text("runs/sample.json", '{"ok":true}')

        self.assertTrue(artifact.artifact_ref.startswith("artifact+http://runs/sample.json"))
        self.assertIn("https://artifact.example/upload/runs/sample.json", artifact.path)
        self.assertEqual(mocked.call_count, 1)

    def test_artifact_store_http_backend_supports_remote_read_bytes(self) -> None:
        os.environ["SEO_AD_BOT_ARTIFACT_STORE_BACKEND"] = "http"
        os.environ["SEO_AD_BOT_ARTIFACT_STORE_HTTP_BASE_URL"] = "https://artifact.example/upload"
        os.environ["SEO_AD_BOT_ARTIFACT_STORE_HTTP_TOKEN"] = "token-123"
        get_settings.cache_clear()

        class _DummyReadResponse:
            def __init__(self, payload: bytes) -> None:
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                return self._payload

        with patch(
            "apps.api.seo_ad_autopilot.artifact_store.urlopen",
            return_value=_DummyReadResponse(b'{"ok":true}'),
        ) as mocked:
            store = get_artifact_store()
            payload = store.read_bytes("runs/sample.json")

        self.assertEqual(payload, b'{"ok":true}')
        self.assertEqual(mocked.call_count, 1)
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "https://artifact.example/upload/runs/sample.json")
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Authorization"), "Bearer token-123")

    def test_artifact_store_http_backend_supports_remote_read_text(self) -> None:
        os.environ["SEO_AD_BOT_ARTIFACT_STORE_BACKEND"] = "http"
        os.environ["SEO_AD_BOT_ARTIFACT_STORE_HTTP_BASE_URL"] = "https://artifact.example/upload"
        os.environ["SEO_AD_BOT_ARTIFACT_STORE_HTTP_TOKEN"] = "token-123"
        get_settings.cache_clear()

        class _DummyReadResponse:
            def __init__(self, payload: bytes) -> None:
                self._payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self) -> bytes:
                return self._payload

        with patch(
            "apps.api.seo_ad_autopilot.artifact_store.urlopen",
            return_value=_DummyReadResponse("中文-ok".encode("utf-8")),
        ):
            store = get_artifact_store()
            payload = store.read_text("runs/sample.txt")
        self.assertEqual(payload, "中文-ok")

    def test_require_postgres_rejects_sqlite_url(self) -> None:
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(self._tempdir.name) / 'sqlite-forbidden.db'}"
        os.environ["SEO_AD_BOT_REQUIRE_POSTGRES"] = "true"
        get_settings.cache_clear()
        with self.assertRaises(RuntimeError):
            Database(get_settings())

    def test_project_runs_schema_auto_migrates_runtime_route_columns(self) -> None:
        database = Database(get_settings())
        with database._engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE IF EXISTS project_runs")
            connection.exec_driver_sql(
                """
                CREATE TABLE project_runs (
                    id VARCHAR(32) PRIMARY KEY,
                    project_id VARCHAR(32) NOT NULL,
                    task_id VARCHAR(32),
                    trigger VARCHAR(32) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    risk_score INTEGER DEFAULT 0,
                    started_at DATETIME,
                    finished_at DATETIME,
                    connector_status_json JSON DEFAULT '{}',
                    evidence_json JSON DEFAULT '[]',
                    notes_json JSON DEFAULT '[]',
                    auto_deploy BOOLEAN DEFAULT 0,
                    rollback_ready BOOLEAN DEFAULT 0,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        database.create_all()
        columns = {column["name"] for column in inspect(database._engine).get_columns("project_runs")}
        self.assertIn("runtime_route_request_path", columns)
        self.assertIn("runtime_route_request_method", columns)

    def test_observability_strict_requires_dependencies(self) -> None:
        os.environ["SEO_AD_BOT_ENABLE_OTLP"] = "true"
        os.environ["SEO_AD_BOT_OBSERVABILITY_STRICT"] = "true"
        get_settings.cache_clear()
        settings = get_settings()
        with patch.object(observability, "otel_trace", None), patch.object(observability, "TracerProvider", None):
            with self.assertRaises(RuntimeError):
                observability.initialize_observability(settings)

    def test_observability_parses_otlp_headers(self) -> None:
        headers = observability._parse_otlp_headers("Authorization=Bearer demo-token, x-tenant = acme ")
        self.assertEqual(headers.get("Authorization"), "Bearer demo-token")
        self.assertEqual(headers.get("x-tenant"), "acme")

    def test_worker_failure_code_normalization(self) -> None:
        service = self._service()
        self.assertEqual(service._worker_failure_code("strict blocked: STRICT_PROVIDER_BLOCKED"), "STRICT_PROVIDER_BLOCKED")
        self.assertEqual(service._worker_failure_code("request timeout while deploying"), "WORKER_TIMEOUT")
        self.assertEqual(service._worker_failure_code(""), "WORKER_STAGE_FAILED")

    def test_crawler_classifies_anti_bot_block_error(self) -> None:
        code = _classify_crawl_error(RuntimeError("Access denied by challenge page / captcha"))
        self.assertEqual(code, "PLAYWRIGHT_ANTI_BOT_BLOCKED")

    def test_crawler_extracts_block_signals(self) -> None:
        signals = _extract_block_signals_from_text("Cloudflare security check: 429 Too Many Requests and captcha required")
        self.assertIn("cloudflare", signals)
        self.assertIn("security-check", signals)
        self.assertIn("http-429", signals)
        self.assertIn("captcha", signals)
        extended = _extract_block_signals_from_text(
            "DataDome human verification: please enable JavaScript and cookies before accessing this page."
        )
        self.assertIn("datadome", extended)
        self.assertIn("human-verification", extended)
        self.assertIn("enable-js-cookies", extended)
        challenge = _extract_block_signals_from_text(
            "Checking your browser before accessing. Turnstile and hCaptcha challenge detected by DDoS-Guard."
        )
        self.assertIn("js-challenge", challenge)
        self.assertIn("turnstile", challenge)
        self.assertIn("hcaptcha", challenge)
        self.assertIn("ddos-guard", challenge)

    def test_crawler_parses_proxy_pool(self) -> None:
        os.environ["SEO_AD_BOT_BROWSER_CRAWL_PROXY"] = "http://single-proxy.example:8080"
        os.environ["SEO_AD_BOT_BROWSER_CRAWL_PROXIES"] = (
            "http://alice:secret@proxy-a.example:3128, proxy-b.example:9000,not-a-valid-proxy"
        )
        proxies = _browser_proxies()
        servers = [str(item.get("server") or "") for item in proxies]
        self.assertIn("http://single-proxy.example:8080", servers)
        self.assertIn("http://proxy-a.example:3128", servers)
        self.assertIn("http://proxy-b.example:9000", servers)
        auth_entry = next((item for item in proxies if item.get("server") == "http://proxy-a.example:3128"), None)
        self.assertIsNotNone(auth_entry)
        self.assertEqual(auth_entry.get("username"), "alice")
        self.assertEqual(auth_entry.get("password"), "secret")

    def test_crawler_select_proxy_round_robin_and_random(self) -> None:
        proxies = [
            {"server": "http://proxy-1.example:8080"},
            {"server": "http://proxy-2.example:8080"},
        ]
        self.assertEqual(_select_proxy(proxies, 0, "round_robin"), proxies[0])
        self.assertEqual(_select_proxy(proxies, 1, "round_robin"), proxies[1])
        self.assertEqual(_select_proxy(proxies, 2, "round_robin"), proxies[0])
        with patch("apps.api.seo_ad_autopilot.crawler.random.choice", return_value=proxies[1]):
            self.assertEqual(_select_proxy(proxies, 5, "random"), proxies[1])

    def test_crawler_detects_alternative_browser_fingerprints_for_antibot_retry(self) -> None:
        proxies = [
            {"server": "http://proxy-1.example:8080"},
            {"server": "http://proxy-2.example:8080"},
        ]
        user_agents = ["UA-1", "UA-2"]
        self.assertTrue(
            _has_alternative_browser_fingerprint(
                selected_proxy=proxies[0],
                proxies=proxies,
                selected_user_agent=user_agents[0],
                user_agents=user_agents,
                attempt=0,
            )
        )
        self.assertFalse(
            _has_alternative_browser_fingerprint(
                selected_proxy=proxies[0],
                proxies=[proxies[0]],
                selected_user_agent=user_agents[0],
                user_agents=[user_agents[0]],
                attempt=0,
            )
        )

    def test_playwright_refresh_strict_mode_returns_error_on_crawl_failure(self) -> None:
        os.environ["SEO_AD_BOT_ENABLE_BROWSER_CRAWL"] = "true"
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Crawl",
                intake=SiteIntake(url="https://strict-crawl.example", site_name="Strict Crawl"),
            )
        )
        diagnostics = {
            "attempts": [{"attempt": 1, "status": "error", "failureCode": "PLAYWRIGHT_TIMEOUT"}],
            "attemptCount": 1,
            "configuredRetryCount": 0,
            "timeoutMs": 7000,
            "userAgent": "SEO-AD-AutoPilot/1.0",
            "configuredUserAgents": ["SEO-AD-AutoPilot/1.0"],
            "extraHeaders": {"Accept-Language": "en-US,en;q=0.9"},
            "jitterMs": 120,
            "jsEnabled": True,
            "responseStatus": 0,
            "antiBotBlocked": False,
            "blockSignals": [],
            "failureCode": "PLAYWRIGHT_TIMEOUT",
            "fallbackReason": "navigation timeout",
        }
        with patch("apps.api.seo_ad_autopilot.connectors.crawl_page_with_diagnostics", return_value=(None, diagnostics)):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.playwright)
        self.assertEqual(refreshed.status, ConnectorStatus.error)
        self.assertEqual(refreshed.evidence.status, ConnectorStatus.error)
        self.assertEqual(refreshed.connection.status, ConnectorStatus.error)
        self.assertEqual(refreshed.connection.details.get("mode"), "strict-error")

    def test_playwright_refresh_passes_runtime_options_from_connection_config(self) -> None:
        os.environ["SEO_AD_BOT_ENABLE_BROWSER_CRAWL"] = "true"
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "false"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Override Crawl",
                intake=SiteIntake(url="https://runtime-override.example", site_name="Runtime Override"),
            )
        )
        project_connections = service.get_project_connections(project.project_id)
        patched_connections: list[ProjectConnection] = []
        for connection in project_connections.connections:
            cloned = connection.model_copy()
            if cloned.provider == ConnectorKind.playwright:
                cloned.config = {
                    **cloned.config,
                    "enabled": True,
                    "timeoutMs": 9000,
                    "retryCount": 2,
                    "proxyRotation": "random",
                    "proxy": "http://proxy-main.example:8080",
                    "proxies": ["http://proxy-a.example:8081", "http://proxy-b.example:8082"],
                    "extraHeaders": {"X-Debug": "crawl"},
                }
            patched_connections.append(cloned)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=project_connections.state.auto_cruise_enabled,
                sync_interval_minutes=project_connections.state.sync_interval_minutes,
                connections=patched_connections,
            ),
        )
        diagnostics = {
            "attempts": [{"attempt": 1, "status": "error", "failureCode": "PLAYWRIGHT_TIMEOUT"}],
            "attemptCount": 1,
            "configuredRetryCount": 2,
            "timeoutMs": 9000,
            "userAgent": "SEO-AD-AutoPilot/1.0",
            "configuredUserAgents": ["SEO-AD-AutoPilot/1.0"],
            "configuredProxyCount": 2,
            "configuredProxies": ["http://proxy-a.example:8081", "http://proxy-b.example:8082"],
            "proxyRotationStrategy": "random",
            "selectedProxy": {"server": "http://proxy-a.example:8081", "hasAuth": False},
            "extraHeaders": {"X-Debug": "crawl"},
            "jitterMs": 120,
            "jsEnabled": True,
            "responseStatus": 0,
            "antiBotBlocked": False,
            "blockSignals": [],
            "runtimeOverrides": {"timeoutMs": 9000, "proxyConfigured": True},
            "failureCode": "PLAYWRIGHT_TIMEOUT",
            "fallbackReason": "navigation timeout",
        }
        with patch("apps.api.seo_ad_autopilot.connectors.crawl_page_with_diagnostics", return_value=(None, diagnostics)) as mocked_crawl:
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.playwright)
        _, kwargs = mocked_crawl.call_args
        runtime_options = kwargs.get("runtime_options") or {}
        self.assertEqual(runtime_options.get("timeoutMs"), 9000)
        self.assertEqual(runtime_options.get("retryCount"), 2)
        self.assertEqual(runtime_options.get("proxyRotation"), "random")
        self.assertEqual(runtime_options.get("proxy"), "http://proxy-main.example:8080")
        self.assertIn("http://proxy-a.example:8081", runtime_options.get("proxies", []))
        self.assertEqual(refreshed.connection.details.get("runtimeOverrides", {}).get("proxyConfigured"), True)
        self.assertEqual(refreshed.connection.details.get("strictMode"), False)
        self.assertEqual(refreshed.evidence.failure_code, "PLAYWRIGHT_TIMEOUT")

    def test_playwright_refresh_anti_bot_escalation_marks_manual_intervention(self) -> None:
        os.environ["SEO_AD_BOT_ENABLE_BROWSER_CRAWL"] = "true"
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_BROWSER_CRAWL_ANTI_BOT_COOLDOWN_MINUTES"] = "30"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Crawl AntiBot",
                intake=SiteIntake(url="https://strict-crawl-antibot.example", site_name="Strict Crawl AntiBot"),
            )
        )
        diagnostics = {
            "attempts": [
                {"attempt": 1, "status": "error", "failureCode": "PLAYWRIGHT_ANTI_BOT_BLOCKED"},
                {"attempt": 2, "status": "error", "failureCode": "PLAYWRIGHT_ANTI_BOT_BLOCKED"},
            ],
            "attemptCount": 2,
            "configuredRetryCount": 1,
            "timeoutMs": 7000,
            "userAgent": "SEO-AD-AutoPilot/1.0",
            "configuredUserAgents": ["SEO-AD-AutoPilot/1.0"],
            "extraHeaders": {"Accept-Language": "en-US,en;q=0.9"},
            "jitterMs": 120,
            "jsEnabled": True,
            "responseStatus": 403,
            "antiBotBlocked": True,
            "antiBotBlockCount": 2,
            "antiBotConsecutiveCount": 2,
            "antiBotEscalated": True,
            "manualInterventionRequired": True,
            "remediationHint": "anti-bot challenge persisted; rotate proxy/cookies and re-verify crawl permissions.",
            "blockSignals": ["cloudflare", "challenge"],
            "failureCode": "PLAYWRIGHT_ANTI_BOT_BLOCKED",
            "fallbackReason": "anti-bot challenge detected",
        }
        with patch("apps.api.seo_ad_autopilot.connectors.crawl_page_with_diagnostics", return_value=(None, diagnostics)):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.playwright)
        self.assertEqual(refreshed.status, ConnectorStatus.error)
        self.assertEqual(refreshed.evidence.failure_code, "PLAYWRIGHT_ANTI_BOT_BLOCKED")
        self.assertEqual(refreshed.evidence.retryable, False)
        self.assertEqual(refreshed.connection.details.get("antiBotEscalated"), True)
        self.assertEqual(refreshed.connection.details.get("manualInterventionRequired"), True)
        self.assertEqual(refreshed.connection.details.get("antiBotBlockCount"), 2)
        self.assertEqual(refreshed.connection.details.get("cooldownActive"), True)
        self.assertEqual(refreshed.connection.details.get("antiBotCooldownMinutes"), 60)
        self.assertIsNotNone(refreshed.connection.details.get("antiBotCooldownUntil"))

    def test_playwright_refresh_skips_live_crawl_when_antibot_cooldown_active(self) -> None:
        os.environ["SEO_AD_BOT_ENABLE_BROWSER_CRAWL"] = "true"
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_BROWSER_CRAWL_ANTI_BOT_COOLDOWN_MINUTES"] = "30"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Crawl Cooldown",
                intake=SiteIntake(url="https://strict-crawl-cooldown.example", site_name="Strict Crawl Cooldown"),
            )
        )
        diagnostics = {
            "attempts": [
                {"attempt": 1, "status": "error", "failureCode": "PLAYWRIGHT_ANTI_BOT_BLOCKED"},
                {"attempt": 2, "status": "error", "failureCode": "PLAYWRIGHT_ANTI_BOT_BLOCKED"},
            ],
            "attemptCount": 2,
            "configuredRetryCount": 1,
            "timeoutMs": 7000,
            "userAgent": "SEO-AD-AutoPilot/1.0",
            "configuredUserAgents": ["SEO-AD-AutoPilot/1.0"],
            "extraHeaders": {"Accept-Language": "en-US,en;q=0.9"},
            "jitterMs": 120,
            "jsEnabled": True,
            "responseStatus": 403,
            "antiBotBlocked": True,
            "antiBotBlockCount": 2,
            "antiBotConsecutiveCount": 2,
            "antiBotEscalated": True,
            "manualInterventionRequired": True,
            "remediationHint": "manual intervention required",
            "blockSignals": ["cloudflare", "challenge"],
            "failureCode": "PLAYWRIGHT_ANTI_BOT_BLOCKED",
            "fallbackReason": "anti-bot challenge detected",
        }
        with patch("apps.api.seo_ad_autopilot.connectors.crawl_page_with_diagnostics", return_value=(None, diagnostics)):
            first = service.refresh_project_connector(project.project_id, ConnectorKind.playwright)
        self.assertEqual(first.evidence.failure_code, "PLAYWRIGHT_ANTI_BOT_BLOCKED")
        with patch("apps.api.seo_ad_autopilot.connectors.crawl_page_with_diagnostics", side_effect=AssertionError("should not crawl during cooldown")):
            second = service.refresh_project_connector(project.project_id, ConnectorKind.playwright)
        self.assertEqual(second.status, ConnectorStatus.error)
        self.assertEqual(second.evidence.failure_code, "PLAYWRIGHT_ANTI_BOT_COOLDOWN")
        self.assertEqual(second.evidence.retryable, False)
        self.assertEqual(second.connection.details.get("cooldownActive"), True)
        self.assertEqual(second.connection.details.get("manualInterventionRequired"), True)

    def test_playwright_refresh_antibot_cooldown_respects_max_cap(self) -> None:
        os.environ["SEO_AD_BOT_ENABLE_BROWSER_CRAWL"] = "true"
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_BROWSER_CRAWL_ANTI_BOT_COOLDOWN_MINUTES"] = "30"
        os.environ["SEO_AD_BOT_BROWSER_CRAWL_ANTI_BOT_COOLDOWN_MAX_MINUTES"] = "45"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Crawl Cooldown Cap",
                intake=SiteIntake(url="https://strict-crawl-cooldown-cap.example", site_name="Strict Crawl Cooldown Cap"),
            )
        )
        diagnostics = {
            "attempts": [
                {"attempt": 1, "status": "error", "failureCode": "PLAYWRIGHT_ANTI_BOT_BLOCKED"},
                {"attempt": 2, "status": "error", "failureCode": "PLAYWRIGHT_ANTI_BOT_BLOCKED"},
                {"attempt": 3, "status": "error", "failureCode": "PLAYWRIGHT_ANTI_BOT_BLOCKED"},
            ],
            "attemptCount": 3,
            "configuredRetryCount": 2,
            "timeoutMs": 7000,
            "userAgent": "SEO-AD-AutoPilot/1.0",
            "configuredUserAgents": ["SEO-AD-AutoPilot/1.0"],
            "extraHeaders": {"Accept-Language": "en-US,en;q=0.9"},
            "jitterMs": 120,
            "jsEnabled": True,
            "responseStatus": 403,
            "antiBotBlocked": True,
            "antiBotBlockCount": 3,
            "antiBotConsecutiveCount": 3,
            "antiBotEscalated": True,
            "manualInterventionRequired": True,
            "remediationHint": "manual intervention required",
            "blockSignals": ["cloudflare", "challenge"],
            "failureCode": "PLAYWRIGHT_ANTI_BOT_BLOCKED",
            "fallbackReason": "anti-bot challenge detected",
        }
        with patch("apps.api.seo_ad_autopilot.connectors.crawl_page_with_diagnostics", return_value=(None, diagnostics)):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.playwright)
        self.assertEqual(refreshed.status, ConnectorStatus.error)
        self.assertEqual(refreshed.evidence.failure_code, "PLAYWRIGHT_ANTI_BOT_BLOCKED")
        self.assertEqual(refreshed.connection.details.get("antiBotConsecutiveCount"), 3)
        self.assertEqual(refreshed.connection.details.get("antiBotCooldownMinutes"), 45)

    def test_connector_remediation_prioritizes_playwright_antibot_as_blocking(self) -> None:
        service = self._service()
        failure_report = ConnectorFailureReport(
            report_id="conn-failure-antibot",
            generated_at=datetime.now(timezone.utc),
            total_failures=1,
            entries=[
                ConnectorFailureEntry(
                    failure_code="PLAYWRIGHT_ANTI_BOT_BLOCKED",
                    category="other",
                    count=3,
                    providers=[ConnectorKind.playwright.value],
                    affected_projects=1,
                    project_ids=["project_antibot_1"],
                    last_seen_at=datetime.now(timezone.utc),
                )
            ],
        )
        with patch.object(service, "build_connector_failure_report", return_value=failure_report):
            remediation = service.build_connector_remediation_report()
        self.assertEqual(remediation.item_count, 1)
        item = remediation.items[0]
        self.assertEqual(item.failure_code, "PLAYWRIGHT_ANTI_BOT_BLOCKED")
        self.assertEqual(item.category, "permission")
        self.assertEqual(item.priority, "p0")
        self.assertTrue(item.blocking)
        self.assertEqual(item.alert_severity, "critical")
        self.assertIn("反爬", item.action)

    def test_connector_remediation_prioritizes_playwright_antibot_cooldown_as_blocking(self) -> None:
        service = self._service()
        failure_report = ConnectorFailureReport(
            report_id="conn-failure-antibot-cooldown",
            generated_at=datetime.now(timezone.utc),
            total_failures=1,
            entries=[
                ConnectorFailureEntry(
                    failure_code="PLAYWRIGHT_ANTI_BOT_COOLDOWN",
                    category="other",
                    count=2,
                    providers=[ConnectorKind.playwright.value],
                    affected_projects=1,
                    project_ids=["project_antibot_cooldown_1"],
                    last_seen_at=datetime.now(timezone.utc),
                )
            ],
        )
        with patch.object(service, "build_connector_failure_report", return_value=failure_report):
            remediation = service.build_connector_remediation_report()
        self.assertEqual(remediation.item_count, 1)
        item = remediation.items[0]
        self.assertEqual(item.failure_code, "PLAYWRIGHT_ANTI_BOT_COOLDOWN")
        self.assertEqual(item.category, "permission")
        self.assertEqual(item.priority, "p0")
        self.assertTrue(item.blocking)
        self.assertEqual(item.alert_severity, "critical")
        self.assertIn("冷却", item.action)

    def test_connector_failure_report_includes_connection_level_errors_without_tasks(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Connection Error Only",
                intake=SiteIntake(url="https://conn-error-only.example", site_name="Connection Error Only"),
            )
        )
        current = service.get_project_connections(project.project_id)
        mutated: list[ProjectConnection] = []
        for connection in current.connections:
            clone = connection.model_copy(deep=True)
            if clone.provider == ConnectorKind.playwright:
                clone.status = ConnectorStatus.error
                clone.details = {
                    **clone.details,
                    "errorCode": "PLAYWRIGHT_ANTI_BOT_COOLDOWN",
                    "fallbackReason": "anti-bot cooldown active",
                    "manualInterventionRequired": True,
                    "retryable": False,
                }
            mutated.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=current.state.auto_cruise_enabled,
                sync_interval_minutes=current.state.sync_interval_minutes,
                connections=mutated,
            ),
        )
        report = service.build_connector_failure_report()
        target = next((item for item in report.entries if item.failure_code == "PLAYWRIGHT_ANTI_BOT_COOLDOWN"), None)
        self.assertIsNotNone(target)
        assert target is not None
        self.assertIn(ConnectorKind.playwright.value, target.providers)
        self.assertIn(project.project_id, target.project_ids)
        project_report = service.build_connector_failure_report(project_id=project.project_id)
        self.assertEqual(project_report.project_id, project.project_id)
        self.assertTrue(all(project.project_id in item.project_ids for item in project_report.entries))

    def test_retry_connectors_skips_playwright_antibot_cooldown(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Retry Skip Cooldown",
                intake=SiteIntake(url="https://retry-skip-cooldown.example", site_name="Retry Skip Cooldown"),
            )
        )
        current = service.get_project_connections(project.project_id)
        mutated: list[ProjectConnection] = []
        for connection in current.connections:
            clone = connection.model_copy(deep=True)
            if clone.provider == ConnectorKind.playwright:
                clone.status = ConnectorStatus.error
                clone.details = {
                    **clone.details,
                    "errorCode": "PLAYWRIGHT_ANTI_BOT_COOLDOWN",
                    "fallbackReason": "anti-bot cooldown active",
                    "manualInterventionRequired": True,
                    "retryable": True,
                }
            mutated.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=current.state.auto_cruise_enabled,
                sync_interval_minutes=current.state.sync_interval_minutes,
                connections=mutated,
            ),
        )
        with patch.object(service, "refresh_project_connector", side_effect=AssertionError("cooldown entries must be skipped")):
            result = service.retry_connectors(
                ConnectorRetryRequest(
                    categories=["permission"],
                    project_ids=[project.project_id],
                    providers=[ConnectorKind.playwright],
                    retryable_only=False,
                    max_retries=5,
                )
            )
        self.assertEqual(result.attempted, 0)
        self.assertEqual(result.refreshed, 0)
        self.assertEqual(result.failed, 0)
        self.assertGreaterEqual(result.skipped, 1)
        self.assertTrue(any("PLAYWRIGHT_ANTI_BOT_COOLDOWN" in note for note in result.notes))

    def test_retry_connectors_skips_playwright_antibot_blocked_manual_intervention(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Retry Skip AntiBot Blocked",
                intake=SiteIntake(url="https://retry-skip-antibot.example", site_name="Retry Skip AntiBot Blocked"),
            )
        )
        current = service.get_project_connections(project.project_id)
        mutated: list[ProjectConnection] = []
        for connection in current.connections:
            clone = connection.model_copy(deep=True)
            if clone.provider == ConnectorKind.playwright:
                clone.status = ConnectorStatus.error
                clone.details = {
                    **clone.details,
                    "errorCode": "PLAYWRIGHT_ANTI_BOT_BLOCKED",
                    "fallbackReason": "anti-bot challenge detected",
                    "manualInterventionRequired": True,
                    "retryable": True,
                }
            mutated.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=current.state.auto_cruise_enabled,
                sync_interval_minutes=current.state.sync_interval_minutes,
                connections=mutated,
            ),
        )
        with patch.object(service, "refresh_project_connector", side_effect=AssertionError("manual anti-bot blocks must be skipped")):
            result = service.retry_connectors(
                ConnectorRetryRequest(
                    categories=["permission"],
                    project_ids=[project.project_id],
                    providers=[ConnectorKind.playwright],
                    retryable_only=False,
                    max_retries=5,
                )
            )
        self.assertEqual(result.attempted, 0)
        self.assertEqual(result.refreshed, 0)
        self.assertEqual(result.failed, 0)
        self.assertGreaterEqual(result.skipped, 1)
        self.assertTrue(any("PLAYWRIGHT_ANTI_BOT_BLOCKED" in note for note in result.notes))

    def test_search_console_refresh_marks_invalid_payload_as_non_retryable_error(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="SC Invalid Payload",
                intake=SiteIntake(
                    url="https://sc-invalid.example",
                    site_name="SC Invalid Payload",
                    search_console={"accessToken": "sc-token", "endpoint": "https://sc.invalid/api"},
                ),
            )
        )
        with patch("apps.api.seo_ad_autopilot.connectors._http_json", return_value={"raw": "<html>bad gateway</html>"}):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.search_console)
        self.assertEqual(refreshed.status, ConnectorStatus.error)
        self.assertEqual(refreshed.evidence.failure_code, "SEARCH_CONSOLE_INVALID_PAYLOAD")
        self.assertEqual(refreshed.evidence.retryable, False)
        self.assertIn("invalid", str(refreshed.connection.details.get("error", "")).lower())

    def test_search_console_refresh_supports_credentials_json(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="SC Credentials JSON",
                intake=SiteIntake(
                    url="https://sc-json.example",
                    site_name="SC Credentials JSON",
                    search_console={
                        "credentialsJson": json.dumps({"accessToken": "sc-json-token"}),
                        "endpoint": "https://sc-json.invalid/api",
                    },
                ),
            )
        )
        with patch(
            "apps.api.seo_ad_autopilot.connectors._http_json",
            return_value={"rows": [{"keys": ["json token"], "clicks": 9, "impressions": 90}]},
        ):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.search_console)
        self.assertEqual(refreshed.status, ConnectorStatus.connected)
        self.assertEqual(refreshed.evidence.auth_source, "config:json")
        self.assertEqual(refreshed.connection.details.get("endpoint"), "https://sc-json.invalid/api")
        self.assertEqual(refreshed.connection.details.get("clicks"), 9)

    def test_ga4_refresh_marks_invalid_payload_as_non_retryable_error(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="GA4 Invalid Payload",
                intake=SiteIntake(
                    url="https://ga4-invalid.example",
                    site_name="GA4 Invalid Payload",
                    ga4={"accessToken": "ga4-token", "endpoint": "https://ga4.invalid/api", "propertyId": "12345"},
                ),
            )
        )
        with patch("apps.api.seo_ad_autopilot.connectors._http_json", return_value={"rows": {"bad": "shape"}}):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.ga4)
        self.assertEqual(refreshed.status, ConnectorStatus.error)
        self.assertEqual(refreshed.evidence.failure_code, "GA4_INVALID_PAYLOAD")
        self.assertEqual(refreshed.evidence.retryable, False)
        self.assertIn("invalid", str(refreshed.connection.details.get("error", "")).lower())

    def test_ga4_refresh_supports_credentials_json(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="GA4 Credentials JSON",
                intake=SiteIntake(
                    url="https://ga4-json.example",
                    site_name="GA4 Credentials JSON",
                    ga4={
                        "credentialsJson": json.dumps({"accessToken": "ga4-json-token"}),
                        "endpoint": "https://ga4-json.invalid/api",
                        "propertyId": "12345",
                    },
                ),
            )
        )
        with patch(
            "apps.api.seo_ad_autopilot.connectors._http_json",
            return_value={"rows": [{"metricValues": [{"value": "321"}, {"value": "12"}, {"value": "0.55"}]}]},
        ):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.ga4)
        self.assertEqual(refreshed.status, ConnectorStatus.connected)
        self.assertEqual(refreshed.evidence.auth_source, "config:json")
        self.assertEqual(refreshed.connection.details.get("endpoint"), "https://ga4-json.invalid/api")
        self.assertEqual(refreshed.connection.details.get("sessions"), 321)

    def test_search_console_refresh_uses_backup_endpoint_when_primary_fails(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        primary = "file:///missing-sc-primary.json"
        backup_path = Path(self._tempdir.name) / "sc-backup.json"
        backup_path.write_text(
            json.dumps({"rows": [{"keys": ["seo automation"], "clicks": 11, "impressions": 120}]}),
            encoding="utf-8",
        )
        project = service.create_project(
            ProjectCreateRequest(
                name="SC Multi Endpoint",
                intake=SiteIntake(
                    url="https://sc-multi-endpoint.example",
                    site_name="SC Multi Endpoint",
                    search_console={"accessToken": "sc-token", "endpoint": primary},
                ),
            )
        )
        connections = service.get_project_connections(project.project_id)
        updated_connections: list[ProjectConnection] = []
        for connection in connections.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.search_console:
                clone.config = {
                    **clone.config,
                    "accessToken": "sc-token",
                    "endpoints": [primary, backup_path.as_uri()],
                }
            updated_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=connections.state.auto_cruise_enabled,
                sync_interval_minutes=connections.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.search_console)
        self.assertEqual(refreshed.status, ConnectorStatus.connected)
        self.assertEqual(refreshed.connection.details.get("endpoint"), backup_path.as_uri())
        self.assertEqual(len(refreshed.connection.details.get("endpointsTried", [])), 2)
        self.assertEqual(refreshed.connection.details.get("endpointAttempts", [])[0].get("status"), "error")
        self.assertEqual(refreshed.connection.details.get("endpointAttempts", [])[1].get("status"), "connected")

    def test_ga4_refresh_uses_backup_endpoint_when_primary_fails(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        primary = "file:///missing-ga4-primary.json"
        backup_path = Path(self._tempdir.name) / "ga4-backup.json"
        backup_path.write_text(
            json.dumps({"rows": [{"metricValues": [{"value": "2100"}, {"value": "24"}, {"value": "0.63"}]}]}),
            encoding="utf-8",
        )
        project = service.create_project(
            ProjectCreateRequest(
                name="GA4 Multi Endpoint",
                intake=SiteIntake(
                    url="https://ga4-multi-endpoint.example",
                    site_name="GA4 Multi Endpoint",
                    ga4={"accessToken": "ga4-token", "endpoint": primary, "propertyId": "76543"},
                ),
            )
        )
        connections = service.get_project_connections(project.project_id)
        updated_connections: list[ProjectConnection] = []
        for connection in connections.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.ga4:
                clone.config = {
                    **clone.config,
                    "accessToken": "ga4-token",
                    "propertyId": "76543",
                    "endpoints": [primary, backup_path.as_uri()],
                }
            updated_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=connections.state.auto_cruise_enabled,
                sync_interval_minutes=connections.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.ga4)
        self.assertEqual(refreshed.status, ConnectorStatus.connected)
        self.assertEqual(refreshed.connection.details.get("endpoint"), backup_path.as_uri())
        self.assertEqual(len(refreshed.connection.details.get("endpointsTried", [])), 2)
        self.assertEqual(refreshed.connection.details.get("endpointAttempts", [])[0].get("status"), "error")
        self.assertEqual(refreshed.connection.details.get("endpointAttempts", [])[1].get("status"), "connected")

    def test_github_refresh_marks_invalid_payload_as_non_retryable_error(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="GitHub Invalid Payload",
                intake=SiteIntake(
                    url="https://github-invalid.example",
                    site_name="GitHub Invalid Payload",
                    repo_url="https://github.com/example/github-invalid",
                ),
            )
        )
        connections = service.get_project_connections(project.project_id)
        updated_connections: list[ProjectConnection] = []
        for connection in connections.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.github:
                clone.config = {
                    **clone.config,
                    "repoUrl": "https://github.com/example/github-invalid",
                    "owner": "example",
                    "repo": "github-invalid",
                    "headBranch": "autopilot/preview",
                    "baseBranch": "main",
                    "apiEndpoint": "https://github.invalid/api",
                    "accessToken": "github-token",
                }
            updated_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=connections.state.auto_cruise_enabled,
                sync_interval_minutes=connections.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        with patch("apps.api.seo_ad_autopilot.connectors._http_json", return_value={"raw": "<html>bad gateway</html>"}):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.github)
        self.assertEqual(refreshed.status, ConnectorStatus.error)
        self.assertEqual(refreshed.evidence.failure_code, "GITHUB_INVALID_PAYLOAD")
        self.assertEqual(refreshed.evidence.retryable, False)

    def test_cms_refresh_marks_invalid_payload_as_non_retryable_error(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="CMS Invalid Payload",
                intake=SiteIntake(
                    url="https://cms-invalid.example",
                    site_name="CMS Invalid Payload",
                    cms_name="wordpress",
                ),
            )
        )
        connections = service.get_project_connections(project.project_id)
        updated_connections: list[ProjectConnection] = []
        for connection in connections.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.cms:
                clone.config = {
                    **clone.config,
                    "cmsName": "wordpress",
                    "draftEndpoint": "https://cms.invalid/api",
                    "authToken": "cms-token",
                }
            updated_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=connections.state.auto_cruise_enabled,
                sync_interval_minutes=connections.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        with patch("apps.api.seo_ad_autopilot.connectors._http_json", return_value={"raw": "not-json"}):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.cms)
        self.assertEqual(refreshed.status, ConnectorStatus.error)
        self.assertEqual(refreshed.evidence.failure_code, "CMS_INVALID_PAYLOAD")
        self.assertEqual(refreshed.evidence.retryable, False)

    def test_script_refresh_marks_invalid_payload_as_non_retryable_error(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Script Invalid Payload",
                intake=SiteIntake(
                    url="https://script-invalid.example",
                    site_name="Script Invalid Payload",
                ),
            )
        )
        connections = service.get_project_connections(project.project_id)
        updated_connections: list[ProjectConnection] = []
        for connection in connections.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.script_api:
                clone.config = {
                    **clone.config,
                    "scriptEndpoint": "https://script.invalid/api",
                    "accessToken": "script-token",
                }
            updated_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=connections.state.auto_cruise_enabled,
                sync_interval_minutes=connections.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        with patch("apps.api.seo_ad_autopilot.connectors._http_json", return_value={"raw": "bad"}):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.script_api)
        self.assertEqual(refreshed.status, ConnectorStatus.error)
        self.assertEqual(refreshed.evidence.failure_code, "SCRIPT_INVALID_PAYLOAD")
        self.assertEqual(refreshed.evidence.retryable, False)

    def test_sitemap_refresh_supports_provider_endpoint_and_auth_header(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Sitemap Provider Endpoint",
                intake=SiteIntake(
                    url="https://sitemap-provider.example",
                    site_name="Sitemap Provider Endpoint",
                    sitemap_urls=["/sitemap.xml"],
                ),
            )
        )
        existing = service.get_project_connections(project.project_id)
        updated_connections = []
        for connection in existing.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.sitemap:
                clone.config = {
                    **clone.config,
                    "providerUrl": "https://sitemap-provider.invalid/api",
                    "credentialsJson": json.dumps({"accessToken": "sitemap-json-token", "authHeader": "X-Sitemap-Token"}),
                    "providerTimeoutMs": 2000,
                }
            updated_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing.state.auto_cruise_enabled,
                sync_interval_minutes=existing.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        with patch(
            "apps.api.seo_ad_autopilot.connectors._http_json",
            return_value={
                "providerRef": "sitemap-provider-001",
                "locations": [
                    "https://sitemap-provider.example/articles/alpha",
                    {"loc": "https://sitemap-provider.example/articles/beta"},
                ],
            },
        ) as mocked_http_json:
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.sitemap)
        self.assertEqual(refreshed.status, ConnectorStatus.connected)
        self.assertEqual(refreshed.evidence.auth_source, "config:json")
        self.assertEqual(refreshed.connection.details.get("providerEndpoint"), "https://sitemap-provider.invalid/api")
        self.assertEqual(refreshed.connection.details.get("providerResponseRef"), "sitemap-provider-001")
        self.assertIn("https://sitemap-provider.example/articles/alpha", refreshed.connection.details.get("discoveredUrls", []))
        headers = mocked_http_json.call_args.kwargs.get("headers", {})
        self.assertEqual(headers.get("X-Sitemap-Token"), "sitemap-json-token")
        self.assertEqual(headers.get("Accept"), "application/json, application/xml, text/xml;q=0.9,*/*;q=0.8")

    def test_sitemap_refresh_strict_blocks_when_provider_and_direct_fetch_fail(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Sitemap Strict Failure",
                intake=SiteIntake(
                    url="https://sitemap-strict-failure.example",
                    site_name="Sitemap Strict Failure",
                    sitemap_urls=["/sitemap.xml"],
                ),
            )
        )
        existing = service.get_project_connections(project.project_id)
        updated_connections = []
        for connection in existing.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.sitemap:
                clone.config = {
                    **clone.config,
                    "providerUrl": "https://sitemap-provider.invalid/api",
                    "accessToken": "sitemap-token",
                }
            updated_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing.state.auto_cruise_enabled,
                sync_interval_minutes=existing.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        with patch("apps.api.seo_ad_autopilot.connectors._http_json", return_value={"raw": "<html>bad</html>"}), patch(
            "apps.api.seo_ad_autopilot.connectors._fetch_text", side_effect=AssertionError("direct sitemap fallback should not recover provider failure")
        ):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.sitemap)
        self.assertEqual(refreshed.status, ConnectorStatus.error)
        self.assertEqual(refreshed.evidence.failure_code, "SITEMAP_INVALID_PAYLOAD")
        self.assertFalse(refreshed.evidence.retryable)
        self.assertEqual(refreshed.connection.details.get("providerEndpoint"), "https://sitemap-provider.invalid/api")
        self.assertEqual(refreshed.connection.details.get("providerAttempts", [])[0].get("status"), "failed")

    def test_playwright_refresh_non_strict_keeps_synthetic_on_crawl_failure(self) -> None:
        os.environ["SEO_AD_BOT_ENABLE_BROWSER_CRAWL"] = "true"
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "false"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Non Strict Crawl",
                intake=SiteIntake(url="https://non-strict-crawl.example", site_name="Non Strict Crawl"),
            )
        )
        diagnostics = {
            "attempts": [{"attempt": 1, "status": "error", "failureCode": "PLAYWRIGHT_TIMEOUT"}],
            "attemptCount": 1,
            "configuredRetryCount": 0,
            "timeoutMs": 7000,
            "userAgent": "SEO-AD-AutoPilot/1.0",
            "configuredUserAgents": ["SEO-AD-AutoPilot/1.0"],
            "extraHeaders": {"Accept-Language": "en-US,en;q=0.9"},
            "jitterMs": 120,
            "jsEnabled": True,
            "responseStatus": 0,
            "antiBotBlocked": False,
            "blockSignals": [],
            "failureCode": "PLAYWRIGHT_TIMEOUT",
            "fallbackReason": "navigation timeout",
        }
        with patch("apps.api.seo_ad_autopilot.connectors.crawl_page_with_diagnostics", return_value=(None, diagnostics)):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.playwright)
        self.assertEqual(refreshed.status, ConnectorStatus.synthetic)
        self.assertEqual(refreshed.evidence.status, ConnectorStatus.synthetic)
        self.assertEqual(refreshed.connection.details.get("mode"), "synthetic")
        self.assertEqual(refreshed.connection.details.get("strictMode"), False)

    def test_playwright_refresh_non_strict_uses_synthetic_when_live_crawl_env_disabled(self) -> None:
        os.environ["SEO_AD_BOT_ENABLE_BROWSER_CRAWL"] = "false"
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "false"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Env Disabled Crawl",
                intake=SiteIntake(url="https://env-disabled-crawl.example", site_name="Env Disabled Crawl"),
            )
        )
        project_connections = service.get_project_connections(project.project_id)
        patched_connections: list[ProjectConnection] = []
        for connection in project_connections.connections:
            cloned = connection.model_copy()
            if cloned.provider == ConnectorKind.playwright:
                cloned.config = {**cloned.config, "enabled": True}
            patched_connections.append(cloned)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=project_connections.state.auto_cruise_enabled,
                sync_interval_minutes=project_connections.state.sync_interval_minutes,
                connections=patched_connections,
            ),
        )
        with patch("apps.api.seo_ad_autopilot.connectors.crawl_page_with_diagnostics") as mocked_crawl:
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.playwright)
        mocked_crawl.assert_not_called()
        self.assertEqual(refreshed.status, ConnectorStatus.synthetic)
        self.assertEqual(refreshed.evidence.failure_code, "PLAYWRIGHT_ENV_DISABLED")
        self.assertEqual(refreshed.connection.details.get("liveCrawlEnabled"), False)

    def test_playwright_refresh_strict_blocks_when_live_crawl_env_disabled(self) -> None:
        os.environ["SEO_AD_BOT_ENABLE_BROWSER_CRAWL"] = "false"
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Env Disabled Crawl",
                intake=SiteIntake(url="https://strict-env-disabled-crawl.example", site_name="Strict Env Disabled Crawl"),
            )
        )
        project_connections = service.get_project_connections(project.project_id)
        patched_connections: list[ProjectConnection] = []
        for connection in project_connections.connections:
            cloned = connection.model_copy()
            if cloned.provider == ConnectorKind.playwright:
                cloned.config = {**cloned.config, "enabled": True}
            patched_connections.append(cloned)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=project_connections.state.auto_cruise_enabled,
                sync_interval_minutes=project_connections.state.sync_interval_minutes,
                connections=patched_connections,
            ),
        )
        with patch("apps.api.seo_ad_autopilot.connectors.crawl_page_with_diagnostics") as mocked_crawl:
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.playwright)
        mocked_crawl.assert_not_called()
        self.assertEqual(refreshed.status, ConnectorStatus.error)
        self.assertEqual(refreshed.evidence.failure_code, "PLAYWRIGHT_ENV_DISABLED")
        self.assertEqual(refreshed.connection.details.get("mode"), "strict-error")
        self.assertEqual(refreshed.connection.details.get("liveCrawlEnabled"), False)

    def test_playwright_refresh_supports_provider_endpoint_and_auth_header(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Playwright Provider Endpoint",
                intake=SiteIntake(
                    url="https://playwright-provider.example",
                    site_name="Playwright Provider Endpoint",
                ),
            )
        )
        existing = service.get_project_connections(project.project_id)
        updated_connections = []
        for connection in existing.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.playwright:
                clone.config = {
                    **clone.config,
                    "enabled": True,
                    "providerUrl": "https://playwright-provider.invalid/api",
                    "credentialsJson": json.dumps({"accessToken": "playwright-json-token", "authHeader": "X-Playwright-Token"}),
                    "providerTimeoutMs": 2500,
                }
            updated_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing.state.auto_cruise_enabled,
                sync_interval_minutes=existing.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        with patch(
            "apps.api.seo_ad_autopilot.connectors._http_json",
            return_value={
                "providerRef": "playwright-provider-001",
                "snapshot": {
                    "url": "https://playwright-provider.example",
                    "title": "Provider Captured Page",
                    "description": "Captured by remote browser farm.",
                    "headings": ["Provider Heading"],
                    "wordCount": 412,
                    "internalLinks": 11,
                    "externalLinks": 4,
                    "images": 9,
                    "missingAltCount": 1,
                    "structuredData": ["BreadcrumbList"],
                    "ctaCount": 2,
                    "performanceBudget": {"lcpMs": 1200, "cls": 0.08, "inpMs": 180},
                },
            },
        ) as mocked_http_json, patch("apps.api.seo_ad_autopilot.connectors.crawl_page_with_diagnostics") as mocked_crawl:
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.playwright)
        mocked_crawl.assert_not_called()
        self.assertEqual(refreshed.status, ConnectorStatus.connected)
        self.assertEqual(refreshed.evidence.auth_source, "config:json")
        self.assertEqual(refreshed.connection.details.get("providerEndpoint"), "https://playwright-provider.invalid/api")
        self.assertEqual(refreshed.connection.details.get("providerResponseRef"), "playwright-provider-001")
        self.assertEqual(refreshed.connection.details.get("title"), "Provider Captured Page")
        self.assertEqual(refreshed.connection.details.get("wordCount"), 412)
        headers = mocked_http_json.call_args.kwargs.get("headers", {})
        self.assertEqual(headers.get("X-Playwright-Token"), "playwright-json-token")
        self.assertEqual(headers.get("Accept"), "application/json")

    def test_project_crawl_diagnostics_exports_snapshot_and_artifacts(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Crawl Diagnostics",
                intake=SiteIntake(
                    url="https://crawl-diagnostics.example",
                    site_name="Crawl Diagnostics",
                ),
            )
        )
        snapshot = PageSnapshot(
            url="https://crawl-diagnostics.example",
            title="Live Title",
            description="Live Description",
            headings=["H1"],
            word_count=321,
            internal_links=5,
            external_links=2,
            images=3,
            missing_alt_count=1,
            structured_data=["BreadcrumbList"],
            cta_count=2,
            performance_budget=PagePerformanceBudget(lcp_ms=1400, cls=0.07, inp_ms=170),
        )
        diagnostics = {
            "attempts": [{"attempt": 1, "status": "connected", "elapsedMs": 512}],
            "attemptCount": 1,
            "configuredRetryCount": 1,
            "timeoutMs": 7000,
            "userAgent": "SEO-AD-AutoPilot/1.0",
            "configuredUserAgents": ["SEO-AD-AutoPilot/1.0"],
            "configuredProxyCount": 0,
            "configuredProxies": [],
            "proxyRotationStrategy": "round_robin",
            "selectedProxy": None,
            "extraHeaders": {"Accept-Language": "en-US,en;q=0.9"},
            "jitterMs": 120,
            "jsEnabled": True,
            "responseStatus": 200,
            "antiBotBlocked": False,
            "antiBotBlockCount": 0,
            "antiBotConsecutiveCount": 0,
            "antiBotEscalated": False,
            "manualInterventionRequired": False,
            "remediationHint": "none",
            "blockSignals": [],
            "failureCode": None,
            "fallbackReason": None,
            "_htmlContent": "<html><head><title>Live Title</title></head><body><h1>H1</h1></body></html>",
            "_screenshotB64": base64.b64encode(b"PNGDATA").decode("ascii"),
        }
        with patch("apps.api.seo_ad_autopilot.service.crawl_page_with_diagnostics", return_value=(snapshot, diagnostics)):
            app = create_app(service)
            with TestClient(app) as client:
                response = client.get(f"/api/projects/{project.project_id}/crawl/diagnostics")
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                history_response = client.get(f"/api/projects/{project.project_id}/crawl/diagnostics/history?limit=5")
                self.assertEqual(history_response.status_code, 200)
                history_payload = history_response.json()
        self.assertEqual(payload["projectId"], project.project_id)
        self.assertEqual(payload["url"], "https://crawl-diagnostics.example")
        self.assertEqual(payload["snapshot"]["title"], "Live Title")
        self.assertEqual(payload["snapshot"]["ctaCount"], 2)
        self.assertTrue(payload["htmlArtifactRef"].startswith("artifact://crawl-diagnostics/"))
        self.assertTrue(payload["screenshotArtifactRef"].startswith("artifact://crawl-diagnostics/"))
        self.assertEqual(payload["diagnostics"]["failureCode"], None)
        self.assertEqual(history_payload["projectId"], project.project_id)
        self.assertEqual(history_payload["total"], 1)
        self.assertEqual(history_payload["entries"][0]["url"], "https://crawl-diagnostics.example")
        self.assertTrue(history_payload["entries"][0]["snapshotAvailable"])
        artifact_store = get_artifact_store()
        html_relative = payload["htmlArtifactRef"].split("artifact://", 1)[1]
        screenshot_relative = payload["screenshotArtifactRef"].split("artifact://", 1)[1]
        self.assertIn("Live Title", artifact_store.read_text(html_relative))
        self.assertEqual(artifact_store.read_bytes(screenshot_relative), b"PNGDATA")

    def test_playwright_refresh_strict_blocks_when_provider_endpoint_returns_invalid_payload(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        get_settings.cache_clear()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Playwright Provider Failure",
                intake=SiteIntake(
                    url="https://strict-playwright-provider.example",
                    site_name="Strict Playwright Provider Failure",
                ),
            )
        )
        existing = service.get_project_connections(project.project_id)
        updated_connections = []
        for connection in existing.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.playwright:
                clone.config = {
                    **clone.config,
                    "enabled": True,
                    "providerUrl": "https://playwright-provider.invalid/api",
                    "accessToken": "playwright-token",
                    "providerTimeoutMs": 2500,
                }
            updated_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing.state.auto_cruise_enabled,
                sync_interval_minutes=existing.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        with patch("apps.api.seo_ad_autopilot.connectors._http_json", return_value={"raw": "no snapshot payload"}), patch(
            "apps.api.seo_ad_autopilot.connectors.crawl_page_with_diagnostics", side_effect=AssertionError("strict provider failure should not fallback to local crawl")
        ):
            refreshed = service.refresh_project_connector(project.project_id, ConnectorKind.playwright)
        self.assertEqual(refreshed.status, ConnectorStatus.error)
        self.assertEqual(refreshed.evidence.failure_code, "PLAYWRIGHT_PROVIDER_INVALID_PAYLOAD")
        self.assertFalse(refreshed.evidence.retryable)
        self.assertEqual(refreshed.connection.details.get("providerEndpoint"), "https://playwright-provider.invalid/api")
        self.assertEqual(refreshed.connection.details.get("providerAttempts", [])[0].get("status"), "failed")

    def test_alert_report_includes_visual_regression_failures(self) -> None:
        service = self._service()
        visual_case = VisualRegressionCase(
            sample_id="visual-fail-1",
            name="Visual Fail",
            page_url="https://visual-fail.example",
            project_id="project_visual_1",
            baseline_label="baseline",
            preview_label="preview",
            expected_max_diff_percent=1.0,
            actual_diff_percent=5.2,
            artifact_ref="artifact://visual/fail-1",
            task_id="visual-task-1",
            cta_preserved=False,
            layout_shift_risk="high",
            passed=False,
            provider_status="failed",
            provider_failure_code="VISUAL_FARM_HTTP_ERROR",
            visual_farm_strict_blocked=True,
        )
        visual_run = VisualRegressionRun(
            run_id="visual_run_1",
            sample_count=1,
            pass_count=0,
            fail_count=1,
            average_diff_percent=5.2,
            strict_mode=True,
            cases=[visual_case],
        )
        with patch.object(service, "build_visual_regression_runs_report", return_value=VisualRegressionRunsReport(runs=[visual_run])):
            alert_report = service.build_alert_report()
        visual_alerts = [item for item in [*alert_report.blocking, *alert_report.recoverable] if item.provider == "visual_farm"]
        self.assertTrue(visual_alerts)
        self.assertTrue(any(item.blocking for item in visual_alerts))
        self.assertTrue(any(item.failure_code == "VISUAL_FARM_HTTP_ERROR" for item in visual_alerts))
        target = next(item for item in visual_alerts if item.failure_code == "VISUAL_FARM_HTTP_ERROR")
        self.assertIsNotNone(target.remediation_path)
        self.assertIn("focus=visual-regressions", target.remediation_path or "")
        self.assertIn("runId=visual_run_1", target.remediation_path or "")
        self.assertIn("sampleIds=visual-fail-1", target.remediation_path or "")

    def test_visual_regression_remediation_report_exposes_retry_template(self) -> None:
        service = self._service()
        visual_case = VisualRegressionCase(
            sample_id="visual-remediate-1",
            name="Visual Remediate",
            page_url="https://visual-remediate.example",
            project_id="project_visual_remediate",
            baseline_label="baseline",
            preview_label="preview",
            expected_max_diff_percent=1.0,
            actual_diff_percent=4.1,
            artifact_ref="artifact://visual/remediate-1",
            task_id="visual-remediate-task-1",
            cta_preserved=True,
            layout_shift_risk="medium",
            passed=False,
            provider_status="failed",
            provider_failure_code="VISUAL_FARM_HTTP_ERROR",
            visual_farm_strict_blocked=False,
        )
        visual_run = VisualRegressionRun(
            run_id="visual_remediate_run_1",
            sample_count=1,
            pass_count=0,
            fail_count=1,
            average_diff_percent=4.1,
            strict_mode=False,
            cases=[visual_case],
        )
        with patch.object(service, "build_visual_regression_runs_report", return_value=VisualRegressionRunsReport(runs=[visual_run])):
            remediation = service.build_visual_regression_remediation_report()
        self.assertGreaterEqual(remediation.item_count, 1)
        self.assertTrue(remediation.items)
        first = remediation.items[0]
        self.assertEqual(first.failure_code, "VISUAL_FARM_HTTP_ERROR")
        self.assertIn(first.category, ["network", "rate_limit", "unavailable", "other", "validation", "config", "auth", "permission"])
        self.assertIsNotNone(first.retry_request_template)
        self.assertTrue(first.retry_request_template.categories)

    def test_visual_regression_remediation_report_supports_project_filter(self) -> None:
        service = self._service()
        report = service.build_visual_regression_remediation_report(project_id="project_visual_filter")
        self.assertEqual(report.project_id, "project_visual_filter")
        self.assertEqual(report.item_count, 0)
        with TestClient(create_app(service)) as client:
            response = client.get("/api/visual-regressions/remediations", params={"projectId": "project_visual_filter"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["projectId"], "project_visual_filter")

    def test_visual_regression_runs_support_external_visual_farm_adapter(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINT"] = "https://visual-farm.example/render"
        get_settings.cache_clear()
        service = self._service()
        with patch(
            "apps.api.seo_ad_autopilot.quality._run_visual_farm_case",
            return_value={
                "status": "completed",
                "provider": "browsercat",
                "runId": "vf-run-001",
                "endpoint": "https://visual-farm.example/render",
                "latencyMs": 842,
                "screenshotCount": 3,
                "actualDiffPercent": 1.23,
                "mismatchPixels": 120,
                "comparedPixels": 10240,
                "mismatchRatio": 1.1719,
                "meanChannelDelta": 3.2,
                "maxChannelDelta": 41,
                "thresholdDelta": 16,
                "thresholdExceededPixels": 48,
                "thresholdExceededRatio": 0.4688,
                "mismatchBytes": 0,
                "comparedBytes": 0,
                "baselineArtifactRef": "vf://baseline",
                "previewArtifactRef": "vf://preview",
            },
        ):
            runs = service.build_visual_regression_runs_report()
        self.assertTrue(runs.runs)
        self.assertIsNone(runs.project_id)
        self.assertTrue(runs.runs[0].cases)
        self.assertEqual(runs.runs[0].farm_provider, "browsercat")
        self.assertGreaterEqual(runs.runs[0].connected_case_count, 1)
        self.assertEqual(runs.runs[0].strict_blocked_case_count, 0)
        self.assertEqual(runs.runs[0].failed_case_count, 0)
        self.assertEqual(runs.runs[0].fallback_case_count, 0)
        self.assertEqual(runs.runs[0].not_configured_case_count, 0)
        self.assertGreaterEqual(runs.runs[0].configured_endpoint_count, 1)
        self.assertIn("https://visual-farm.example/render", runs.runs[0].configured_endpoints)
        self.assertEqual(runs.runs[0].average_farm_latency_ms, 842)
        case = runs.runs[0].cases[0]
        self.assertEqual(case.diff_method, "pixel-rgba")
        self.assertEqual(case.execution_mode, "playwright")
        self.assertEqual(case.actual_diff_percent, 1.23)
        self.assertEqual(case.mismatch_pixels, 120)
        self.assertEqual(case.threshold_exceeded_pixels, 48)
        self.assertEqual(case.provider_status, "connected")
        self.assertEqual(case.visual_farm_provider, "browsercat")
        self.assertEqual(case.visual_farm_run_id, "vf-run-001")
        self.assertEqual(case.visual_farm_endpoint, "https://visual-farm.example/render")
        self.assertEqual(case.visual_farm_latency_ms, 842)
        self.assertFalse(case.visual_farm_strict_blocked)
        self.assertEqual(case.screenshot_count, 3)

        with TestClient(create_app(service)) as client:
            response = client.get("/api/visual-regressions/runs", params={"projectId": "proj_visual_regression_filter"})
            health_response = client.get("/api/visual-regressions/health", params={"projectId": "proj_visual_regression_filter"})
            status_response = client.get("/api/visual-farm/status", params={"projectId": "proj_visual_regression_filter"})
        self.assertEqual(response.status_code, 200)
        response_payload = response.json()
        self.assertEqual(response_payload["projectId"], "proj_visual_regression_filter")
        self.assertIsInstance(response_payload["runs"], list)
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["projectId"], "proj_visual_regression_filter")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["projectId"], "proj_visual_regression_filter")

    def test_visual_farm_probe_marks_blocking_and_recoverable_failures(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINTS"] = "https://visual-farm.example/auth,https://visual-farm.example/rate"
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"
        get_settings.cache_clear()
        service = self._service()

        def _mock_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
            url = str(getattr(request, "full_url", ""))
            if url.endswith("/auth"):
                raise HTTPError(url=url, code=401, msg="unauthorized", hdrs=None, fp=None)
            if url.endswith("/rate"):
                raise HTTPError(url=url, code=429, msg="rate limited", hdrs=None, fp=None)
            raise RuntimeError(f"unexpected url: {url}")

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
            report = service.probe_visual_farm()

        self.assertEqual(report.failed_count, 2)
        self.assertEqual(report.blocking_count, 1)
        self.assertEqual(report.recoverable_count, 1)
        self.assertTrue(any(item.failure_code == "VISUAL_FARM_AUTH_INVALID" and item.blocking for item in report.probes))
        self.assertTrue(any(item.failure_code == "VISUAL_FARM_RATE_LIMITED" and not item.blocking for item in report.probes))
        self.assertTrue(any(item.alert_severity == "critical" for item in report.probes))
        self.assertTrue(any(item.alert_severity == "warning" for item in report.probes))

    def test_visual_farm_supports_credentials_json(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_VISUAL_FARM_ENDPOINTS": "https://visual-farm.example/render",
                "SEO_AD_BOT_VISUAL_FARM_ACCESS_TOKEN": json.dumps(
                    {
                        "accessToken": "vf-json-token",
                        "authHeader": "X-VF-Token",
                    }
                ),
            },
            clear=False,
        ):
            get_settings.cache_clear()
            service = self._service()
            seen_headers: list[dict[str, str]] = []

            class _MockResponse:
                def __enter__(self) -> "_MockResponse":
                    return self

                def __exit__(self, exc_type, exc, tb) -> bool:
                    return False

                def read(self) -> bytes:
                    return b'{"status":"ok","provider":"browsercat","runId":"vf-json-001","endpoint":"https://visual-farm.example/render","latencyMs":321,"screenshotCount":2,"actualDiffPercent":0.9,"authSource":"config:json"}'

            def _mock_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
                seen_headers.append({str(key).lower(): str(value) for key, value in request.header_items()})
                return _MockResponse()

            with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
                probe_report = service.probe_visual_farm()
                status_report = service.build_visual_farm_status_report()

        self.assertEqual(probe_report.auth_source, "config:json")
        self.assertEqual(status_report.auth_source, "config:json")
        self.assertTrue(seen_headers)
        self.assertEqual(seen_headers[0].get("x-vf-token"), "Bearer vf-json-token")
        self.assertNotIn("authorization", seen_headers[0])
        self.assertTrue(probe_report.probes)
        self.assertIsNotNone(status_report.last_probe_executed_at)

    def test_visual_farm_probe_supports_dedicated_credentials_json_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_VISUAL_FARM_ENDPOINTS": "https://visual-farm.example/render",
                "SEO_AD_BOT_VISUAL_FARM_ACCESS_TOKEN": "",
                "SEO_AD_BOT_VISUAL_FARM_CREDENTIALS_JSON": json.dumps(
                    {
                        "accessToken": "vf-json-env-token",
                        "authHeader": "X-VF-Env-Token",
                    }
                ),
            },
            clear=False,
        ):
            get_settings.cache_clear()
            service = self._service()
            seen_headers: list[dict[str, str]] = []

            class _MockResponse:
                status = 200

                def __enter__(self) -> "_MockResponse":
                    return self

                def __exit__(self, exc_type, exc, tb) -> bool:
                    return False

            def _mock_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
                seen_headers.append({str(key).lower(): str(value) for key, value in request.header_items()})
                return _MockResponse()

            with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
                report = service.probe_visual_farm()

        self.assertEqual(report.auth_source, "config:credentialsJson:json")
        self.assertTrue(report.access_token_configured)
        self.assertTrue(seen_headers)
        self.assertEqual(seen_headers[0].get("x-vf-env-token"), "Bearer vf-json-env-token")
        self.assertNotIn("authorization", seen_headers[0])

    def test_visual_regression_run_supports_dedicated_visual_farm_credentials_json_env(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_VISUAL_FARM_ENDPOINTS": "https://visual-farm.example/render",
                "SEO_AD_BOT_VISUAL_FARM_ACCESS_TOKEN": "",
                "SEO_AD_BOT_VISUAL_FARM_CREDENTIALS_JSON": json.dumps(
                    {
                        "accessToken": "vf-run-json-token",
                        "authHeader": "X-VF-Run-Token",
                    }
                ),
            },
            clear=False,
        ):
            get_settings.cache_clear()
            service = self._service()
            seen_headers: list[dict[str, str]] = []

            class _MockResponse:
                def __enter__(self) -> "_MockResponse":
                    return self

                def __exit__(self, exc_type, exc, tb) -> bool:
                    return False

                def read(self) -> bytes:
                    return (
                        b'{"status":"completed","provider":"browsercat","runId":"vf-run-json-001",'
                        b'"endpoint":"https://visual-farm.example/render","latencyMs":210,'
                        b'"screenshotCount":2,"actualDiffPercent":0.73}'
                    )

            def _mock_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
                seen_headers.append({str(key).lower(): str(value) for key, value in request.header_items()})
                return _MockResponse()

            with patch("apps.api.seo_ad_autopilot.quality.urlopen", side_effect=_mock_urlopen):
                runs = service.build_visual_regression_runs_report()

        self.assertTrue(runs.runs)
        case = runs.runs[0].cases[0]
        self.assertEqual(case.provider_status, "connected")
        self.assertEqual(case.visual_farm_auth_source, "config:credentialsJson:json")
        self.assertTrue(seen_headers)
        self.assertEqual(seen_headers[0].get("x-vf-run-token"), "Bearer vf-run-json-token")
        self.assertNotIn("authorization", seen_headers[0])

    def test_alert_report_includes_visual_farm_probe_failures(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINTS"] = "https://visual-farm.example/auth,https://visual-farm.example/rate"
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"
        get_settings.cache_clear()
        service = self._service()

        def _mock_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
            url = str(getattr(request, "full_url", ""))
            if url.endswith("/auth"):
                raise HTTPError(url=url, code=401, msg="unauthorized", hdrs=None, fp=None)
            if url.endswith("/rate"):
                raise HTTPError(url=url, code=429, msg="rate limited", hdrs=None, fp=None)
            raise RuntimeError(f"unexpected url: {url}")

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
            service.probe_visual_farm()

        with patch.object(service, "build_visual_regression_runs_report", return_value=VisualRegressionRunsReport(runs=[])):
            report = service.build_alert_report()

        probe_alerts = [item for item in [*report.blocking, *report.recoverable] if item.rule_id == "visual_farm_probe_default"]
        self.assertTrue(probe_alerts)
        self.assertTrue(any(item.failure_code == "VISUAL_FARM_AUTH_INVALID" and item.blocking for item in probe_alerts))
        self.assertTrue(any(item.failure_code == "VISUAL_FARM_RATE_LIMITED" and not item.blocking for item in probe_alerts))
        auth_alert = next(item for item in probe_alerts if item.failure_code == "VISUAL_FARM_AUTH_INVALID")
        self.assertIsNotNone(auth_alert.remediation_path)
        self.assertIn("focus=visual-farm", auth_alert.remediation_path or "")

    def test_alert_report_includes_visual_farm_probe_missing_when_strict(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"
        service = self._service()
        with patch.object(service, "build_visual_regression_runs_report", return_value=VisualRegressionRunsReport(runs=[])):
            report = service.build_alert_report()
        probe_missing = [item for item in [*report.blocking, *report.recoverable] if item.failure_code == "VISUAL_FARM_PROBE_MISSING"]
        self.assertTrue(probe_missing)
        self.assertTrue(all(item.blocking for item in probe_missing))

    def test_alert_report_includes_visual_farm_probe_stale(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"
        os.environ["SEO_AD_BOT_VISUAL_FARM_PROBE_FRESHNESS_MINUTES"] = "30"
        service = self._service()
        with service.database.session() as session:
            session.add(
                AuditRow(
                    id="audit_visual_probe_stale_alert_1",
                    project_id="workspace",
                    task_id="",
                    action="visual_farm.probe.executed",
                    actor="system",
                    payload_json={
                        "strictMode": True,
                        "configuredEndpointCount": 1,
                        "probedEndpointCount": 1,
                        "connectedCount": 1,
                        "failedCount": 0,
                        "notConfiguredCount": 0,
                        "blockingCount": 0,
                        "recoverableCount": 0,
                        "accessTokenConfigured": True,
                        "timeoutMs": 12000,
                        "probes": [],
                        "notes": [],
                    },
                    created_at=datetime.now(timezone.utc) - timedelta(minutes=120),
                )
            )
        with patch.object(service, "build_visual_regression_runs_report", return_value=VisualRegressionRunsReport(runs=[])):
            report = service.build_alert_report()
        probe_stale = [item for item in [*report.blocking, *report.recoverable] if item.failure_code == "VISUAL_FARM_PROBE_STALE"]
        self.assertTrue(probe_stale)
        self.assertTrue(all(item.blocking for item in probe_stale))

    def test_visual_farm_status_marks_stale_probe(self) -> None:
        service = self._service()
        stale_at = datetime.now(timezone.utc) - timedelta(minutes=120)
        with service.database.session() as session:
            session.add(
                AuditRow(
                    id="audit_visual_probe_stale_1",
                    project_id="workspace",
                    task_id="",
                    action="visual_farm.probe.executed",
                    actor="system",
                    payload_json={
                        "strictMode": True,
                        "configuredEndpointCount": 1,
                        "probedEndpointCount": 1,
                        "connectedCount": 1,
                        "failedCount": 0,
                        "notConfiguredCount": 0,
                        "blockingCount": 0,
                        "recoverableCount": 0,
                        "accessTokenConfigured": True,
                        "timeoutMs": 12000,
                        "probes": [],
                        "notes": [],
                    },
                    created_at=stale_at,
                )
            )
        report = service.build_visual_farm_status_report()
        self.assertFalse(report.probe_fresh)
        self.assertTrue(report.probe_stale)
        self.assertEqual(report.last_probe_blocking_count, 0)

    def test_visual_regression_runs_download_visual_farm_screenshot_urls(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINT"] = "https://visual-farm.example/render"
        get_settings.cache_clear()
        service = self._service()

        class _MockResponse:
            def __init__(self, payload: bytes) -> None:
                self._payload = payload

            def __enter__(self) -> "_MockResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return self._payload

        def _mock_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
            url = str(getattr(request, "full_url", ""))
            if "baseline.png" in url:
                return _MockResponse(b"\x89PNG\r\nbaseline")
            if "preview.png" in url:
                return _MockResponse(b"\x89PNG\r\npreview")
            raise RuntimeError(f"unexpected url: {url}")

        with patch(
            "apps.api.seo_ad_autopilot.quality._run_visual_farm_case",
            return_value={
                "status": "completed",
                "provider": "browsercat",
                "runId": "vf-run-asset-001",
                "endpoint": "https://visual-farm.example/render",
                "latencyMs": 500,
                "screenshotCount": 2,
                "actualDiffPercent": 0.92,
                "mismatchPixels": 32,
                "comparedPixels": 2048,
                "mismatchRatio": 1.56,
                "baselineScreenshotUrl": "https://visual-farm.example/assets/baseline.png",
                "previewScreenshotUrl": "https://visual-farm.example/assets/preview.png",
            },
        ), patch("apps.api.seo_ad_autopilot.quality.urlopen", side_effect=_mock_urlopen):
            runs = service.build_visual_regression_runs_report()
        self.assertTrue(runs.runs)
        case = runs.runs[0].cases[0]
        self.assertEqual(case.provider_status, "connected")
        self.assertIsNotNone(case.baseline_artifact_ref)
        self.assertIsNotNone(case.preview_artifact_ref)
        self.assertTrue(str(case.baseline_artifact_ref).startswith("artifact://visual-regressions/"))
        self.assertTrue(str(case.preview_artifact_ref).startswith("artifact://visual-regressions/"))
        self.assertTrue(any("downloaded" in note for note in case.notes))

    def test_visual_regression_runs_strict_blocks_when_screenshot_urls_are_not_downloadable(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINT"] = "https://visual-farm.example/render"
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"
        get_settings.cache_clear()
        service = self._service()

        def _mock_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
            del request, timeout
            raise RuntimeError("download failed")

        with patch(
            "apps.api.seo_ad_autopilot.quality._run_visual_farm_case",
            return_value={
                "status": "completed",
                "provider": "browsercat",
                "runId": "vf-run-asset-strict-fail-001",
                "endpoint": "https://visual-farm.example/render",
                "latencyMs": 500,
                "screenshotCount": 2,
                "actualDiffPercent": 0.42,
                "mismatchPixels": 8,
                "comparedPixels": 2048,
                "mismatchRatio": 0.39,
                "baselineScreenshotUrl": "https://visual-farm.example/assets/baseline.png",
                "previewScreenshotUrl": "https://visual-farm.example/assets/preview.png",
            },
        ), patch("apps.api.seo_ad_autopilot.quality.urlopen", side_effect=_mock_urlopen):
            runs = service.build_visual_regression_runs_report()

        self.assertTrue(runs.runs)
        run = runs.runs[0]
        case = run.cases[0]
        self.assertEqual(case.provider_status, "failed")
        self.assertEqual(case.provider_failure_code, "VISUAL_FARM_SCREENSHOT_FETCH_FAILED")
        self.assertTrue(case.visual_farm_strict_blocked)
        self.assertFalse(case.passed)
        self.assertGreaterEqual(run.strict_blocked_case_count, 1)
        self.assertGreaterEqual(run.failed_case_count, 1)

    def test_visual_regression_runs_strict_blocks_when_provider_artifacts_missing(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINT"] = "https://visual-farm.example/render"
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"
        get_settings.cache_clear()
        service = self._service()

        with patch(
            "apps.api.seo_ad_autopilot.quality._run_visual_farm_case",
            return_value={
                "status": "completed",
                "provider": "browsercat",
                "runId": "vf-run-artifact-missing-001",
                "endpoint": "https://visual-farm.example/render",
                "latencyMs": 420,
                "screenshotCount": 2,
                "actualDiffPercent": 0.35,
                "mismatchPixels": 6,
                "comparedPixels": 2048,
                "mismatchRatio": 0.29,
            },
        ):
            runs = service.build_visual_regression_runs_report()

        self.assertTrue(runs.runs)
        run = runs.runs[0]
        case = run.cases[0]
        self.assertEqual(case.provider_status, "failed")
        self.assertEqual(case.provider_failure_code, "VISUAL_FARM_ARTIFACT_MISSING")
        self.assertTrue(case.visual_farm_strict_blocked)
        self.assertFalse(case.passed)
        self.assertGreaterEqual(run.strict_blocked_case_count, 1)
        self.assertGreaterEqual(run.failed_case_count, 1)

    def test_visual_regression_runs_visual_farm_strict_blocks_fallback(self) -> None:
        os.environ["SEO_AD_BOT_VISUAL_FARM_ENDPOINT"] = "https://visual-farm.example/render"
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"
        get_settings.cache_clear()
        service = self._service()
        with patch(
            "apps.api.seo_ad_autopilot.quality._run_visual_farm_case",
            return_value={
                "status": "failed",
                "provider": "browsercat",
                "runId": "vf-run-err-1",
                "endpoint": "https://visual-farm.example/render",
                "latencyMs": 1290,
                "screenshotCount": 1,
                "failureCode": "VISUAL_FARM_HTTP_ERROR",
                "attempts": [{"endpoint": "https://visual-farm.example/render", "status": "error"}],
            },
        ):
            runs = service.build_visual_regression_runs_report()
        self.assertTrue(runs.runs)
        self.assertEqual(runs.runs[0].farm_provider, "browsercat")
        self.assertGreaterEqual(runs.runs[0].strict_blocked_case_count, 1)
        self.assertGreaterEqual(runs.runs[0].failed_case_count, 1)
        self.assertGreaterEqual(runs.runs[0].attempted_endpoint_count, 1)
        self.assertGreaterEqual(runs.runs[0].provider_attempt_count, 1)
        self.assertIn("https://visual-farm.example/render", runs.runs[0].configured_endpoints)
        self.assertEqual(runs.runs[0].average_farm_latency_ms, 1290)
        case = runs.runs[0].cases[0]
        self.assertEqual(case.provider_status, "failed")
        self.assertEqual(case.provider_failure_code, "VISUAL_FARM_HTTP_ERROR")
        self.assertEqual(case.visual_farm_provider, "browsercat")
        self.assertEqual(case.visual_farm_run_id, "vf-run-err-1")
        self.assertEqual(case.visual_farm_endpoint, "https://visual-farm.example/render")
        self.assertEqual(case.visual_farm_latency_ms, 1290)
        self.assertTrue(case.visual_farm_strict_blocked)
        self.assertEqual(case.screenshot_count, 1)
        self.assertFalse(case.passed)
        health = service.build_visual_regression_health_report()
        self.assertTrue(health.failure_buckets)
        config_bucket = next(item for item in health.failure_buckets if item.category == "config")
        self.assertGreaterEqual(config_bucket.count, 1)
        self.assertTrue(any(code.startswith("VISUAL_FARM_") for code in config_bucket.failure_codes))
        self.assertFalse(config_bucket.retryable)

    def test_visual_regression_runs_report_uses_visual_farm_strict_flag(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "false"
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"
        get_settings.cache_clear()
        service = self._service()
        runs = service.build_visual_regression_runs_report()
        self.assertTrue(runs.runs)
        self.assertTrue(all(run.strict_mode for run in runs.runs))

    def test_execute_visual_regression_runs_defaults_to_visual_farm_strict(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "false"
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"
        get_settings.cache_clear()
        service = self._service()
        report = service.execute_visual_regression_runs(VisualRegressionRunExecuteRequest())
        self.assertTrue(report.runs)
        self.assertTrue(all(run.strict_mode for run in report.runs))

    def test_visual_regression_cases_link_to_real_project_and_task(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Northstar Media",
                intake=SiteIntake(
                    url="https://northstar-media.example",
                    site_name="Northstar Media",
                    repo_url="https://github.com/example/northstar-media",
                    brand_whitelist=["Northstar"],
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://northstar-media.example",
                site_name="Northstar Media",
                repo_url="https://github.com/example/northstar-media",
                brand_whitelist=["Northstar"],
            ),
        )
        report = service.build_visual_regression_report()
        case = next(item for item in report.cases if item.page_url == "https://northstar-media.example")

        self.assertEqual(case.project_id, project.project_id)
        self.assertEqual(case.project_name, "Northstar Media")
        self.assertEqual(case.workflow_task_id, bundle.task.task_id)

    def test_visual_regression_runs_report_recalculates_counts_and_links_for_project_filter(self) -> None:
        service = self._service()
        first_project = service.create_project(
            ProjectCreateRequest(
                name="Northstar Media",
                intake=SiteIntake(
                    url="https://northstar-media.example",
                    site_name="Northstar Media",
                    repo_url="https://github.com/example/northstar-media",
                ),
            )
        )
        second_project = service.create_project(
            ProjectCreateRequest(
                name="Tool Forge",
                intake=SiteIntake(
                    url="https://tool-forge.example",
                    site_name="Tool Forge",
                    repo_url="https://github.com/example/tool-forge",
                ),
            )
        )
        service.run_analysis(
            first_project.project_id,
            SiteIntake(
                url="https://northstar-media.example",
                site_name="Northstar Media",
                repo_url="https://github.com/example/northstar-media",
            ),
        )
        service.run_analysis(
            second_project.project_id,
            SiteIntake(
                url="https://tool-forge.example",
                site_name="Tool Forge",
                repo_url="https://github.com/example/tool-forge",
            ),
        )

        runs = service.build_visual_regression_runs_report(project_id=first_project.project_id)
        self.assertTrue(runs.runs)
        run = runs.runs[0]
        self.assertGreaterEqual(run.sample_count, 1)
        self.assertTrue(all(case.project_id == first_project.project_id for case in run.cases))
        self.assertEqual(run.sample_count, len(run.cases))
        self.assertEqual(run.pass_count + run.fail_count, run.sample_count)
        self.assertEqual(run.project_ids, [first_project.project_id])
        self.assertTrue(run.workflow_task_ids)
        self.assertTrue(all(str(task_id).strip() for task_id in run.workflow_task_ids))

    def test_execute_visual_regression_runs_audit_uses_effective_project_ids_for_task_scoped_runs(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Northstar Media",
                intake=SiteIntake(
                    url="https://northstar-media.example",
                    site_name="Northstar Media",
                    repo_url="https://github.com/example/northstar-media",
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://northstar-media.example",
                site_name="Northstar Media",
                repo_url="https://github.com/example/northstar-media",
            ),
        )

        report = service.execute_visual_regression_runs(
            VisualRegressionRunExecuteRequest(
                task_ids=[bundle.task.task_id],
            )
        )
        self.assertTrue(report.runs)
        self.assertTrue(any(project.project_id in run.project_ids for run in report.runs))

        with service.database.session() as session:
            latest_event = session.scalar(
                select(AuditRow)
                .where(AuditRow.action == "visual_regressions.run.executed")
                .order_by(AuditRow.created_at.desc())
            )
        self.assertIsNotNone(latest_event)
        payload = (latest_event.payload_json if latest_event is not None else {}) or {}
        self.assertIn(project.project_id, [str(item) for item in payload.get("projectIds", [])])
        self.assertIn(bundle.task.task_id, [str(item) for item in payload.get("taskIds", [])])

    def test_visual_regression_retry_history_filters_by_project(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Northstar Media",
                intake=SiteIntake(
                    url="https://northstar-media.example",
                    site_name="Northstar Media",
                    repo_url="https://github.com/example/northstar-media",
                    brand_whitelist=["Northstar"],
                ),
            )
        )
        fake_case = VisualRegressionCase(
            sample_id="northstar-failure-1",
            name="Northstar Media",
            page_url="https://northstar-media.example",
            project_id=project.project_id,
            project_name="Northstar Media",
            workflow_task_id="task_fake",
            deployment_artifact_ref="artifact://visual/fake",
            baseline_label="baseline",
            preview_label="preview",
            expected_max_diff_percent=1.0,
            actual_diff_percent=4.5,
            artifact_ref="artifact://visual/fake-case",
            task_id="task_fake",
            cta_preserved=False,
            layout_shift_risk="high",
            passed=False,
            provider_status="failed",
            provider_failure_code="VISUAL_FARM_UNAVAILABLE",
            visual_farm_strict_blocked=False,
        )
        fake_run = VisualRegressionRun(
            run_id="northstar-failure-run",
            sample_count=1,
            pass_count=0,
            fail_count=1,
            average_diff_percent=4.5,
            strict_mode=False,
            failed_case_count=1,
            strict_blocked_case_count=0,
            cases=[fake_case],
        )
        with patch.object(
            service,
            "build_visual_regression_runs_report",
            return_value=VisualRegressionRunsReport(runs=[fake_run]),
        ):
            retry_response = service.retry_visual_regressions(
                VisualRegressionRetryRequest(
                    project_ids=[project.project_id],
                    categories=["network", "unavailable"],
                    retryable_only=True,
                    max_cases=5,
                )
            )
        self.assertEqual(retry_response.attempted, 1)

        history = service.get_visual_regression_retry_history(limit=10, project_id=project.project_id)
        self.assertEqual(history.project_id, project.project_id)
        self.assertTrue(history.entries)
        self.assertTrue(all(project.project_id in item.project_ids for item in history.entries))

    def test_alert_report_is_persisted(self) -> None:
        webhook_path = Path(self._tempdir.name) / "alerts-webhook.ndjson"
        os.environ["SEO_AD_BOT_ALERT_WEBHOOK_URL"] = webhook_path.as_uri()
        service = self._service()
        report = service.build_alert_report()

        self.assertTrue(report.report_id)
        self.assertTrue(webhook_path.exists())
        content = webhook_path.read_text(encoding="utf-8").strip()
        self.assertTrue(content)
        self.assertIn(report.report_id, content)
        self.assertTrue(any("Webhook delivered" in note for note in report.notes))

        with service.database.session() as session:
            persisted = session.query(AlertSnapshotRow).count()
        self.assertGreaterEqual(persisted, 1)
        deliveries = service.build_alert_delivery_report(limit=10)
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.status == "sent" for item in deliveries.entries))

    def test_alert_report_emit_cooldown_suppresses_duplicate_webhook(self) -> None:
        webhook_path = Path(self._tempdir.name) / "alerts-cooldown.ndjson"
        os.environ["SEO_AD_BOT_ALERT_WEBHOOK_URL"] = webhook_path.as_uri()
        os.environ["SEO_AD_BOT_ALERT_EMIT_COOLDOWN_SECONDS"] = "3600"

        service = self._service()
        first_report = service.build_alert_report()
        first_lines = webhook_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertTrue(first_lines)
        self.assertTrue(any("Webhook delivered" in note for note in first_report.notes))

        second_report = service.build_alert_report()
        second_lines = webhook_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(second_lines), len(first_lines))
        self.assertTrue(any("suppressed" in note.lower() for note in second_report.notes))

        with service.database.session() as session:
            suppressed_count = session.query(AuditRow).where(AuditRow.action == "alerts.emit.suppressed").count()
            executed_count = session.query(AuditRow).where(AuditRow.action == "alerts.emit.executed").count()
        self.assertGreaterEqual(executed_count, 1)
        self.assertGreaterEqual(suppressed_count, 1)

    def test_alert_report_multi_channel_routing(self) -> None:
        all_path = Path(self._tempdir.name) / "alerts-all.ndjson"
        blocking_path = Path(self._tempdir.name) / "alerts-blocking.ndjson"
        recoverable_path = Path(self._tempdir.name) / "alerts-recoverable.ndjson"
        os.environ["SEO_AD_BOT_ALERT_WEBHOOK_URLS"] = all_path.as_uri()
        os.environ["SEO_AD_BOT_ALERT_BLOCKING_WEBHOOK_URLS"] = blocking_path.as_uri()
        os.environ["SEO_AD_BOT_ALERT_RECOVERABLE_WEBHOOK_URLS"] = recoverable_path.as_uri()

        service = self._service()
        report = service.build_alert_report()

        self.assertTrue(all_path.exists())
        self.assertIn('"route": "all"', all_path.read_text(encoding="utf-8"))
        if report.blocking:
            self.assertTrue(blocking_path.exists())
            self.assertIn('"route": "blocking"', blocking_path.read_text(encoding="utf-8"))
        if report.recoverable:
            self.assertTrue(recoverable_path.exists())
            self.assertIn('"route": "recoverable"', recoverable_path.read_text(encoding="utf-8"))

    def test_alert_report_pagerduty_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_PAGERDUTY_ROUTING_KEY"] = "pd-routing-key"
        os.environ["SEO_AD_BOT_ALERT_PAGERDUTY_ENDPOINT"] = "https://events.pagerduty.com/v2/enqueue"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="PagerDuty Sample",
                intake=SiteIntake(url="https://pagerduty.example", site_name="PagerDuty Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://pagerduty.example", site_name="PagerDuty Sample"))

        class _PagerDummyResponse:
            status = 202

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_PagerDummyResponse()):
            report = service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="pagerduty")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "pagerduty" for item in deliveries.entries))

    def test_alert_report_opsgenie_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_OPSGENIE_API_KEY"] = "og-api-key"
        os.environ["SEO_AD_BOT_ALERT_OPSGENIE_ENDPOINT"] = "https://api.opsgenie.com/v2/alerts"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Opsgenie Sample",
                intake=SiteIntake(url="https://opsgenie.example", site_name="Opsgenie Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://opsgenie.example", site_name="Opsgenie Sample"))

        class _OpsgenieDummyResponse:
            status = 202

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_OpsgenieDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="opsgenie")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "opsgenie" for item in deliveries.entries))

    def test_alert_report_splunk_oncall_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_SPLUNK_ONCALL_API_KEY"] = "splunk-oncall-key"
        os.environ["SEO_AD_BOT_ALERT_SPLUNK_ONCALL_ENDPOINT"] = "https://alert.victorops.com/integrations/generic/20131114/alert/test"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Splunk OnCall Sample",
                intake=SiteIntake(url="https://splunk-oncall.example", site_name="Splunk OnCall Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://splunk-oncall.example", site_name="Splunk OnCall Sample"))

        class _SplunkOnCallDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_SplunkOnCallDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="splunk-oncall")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "splunk_oncall" for item in deliveries.entries))

    def test_alert_report_grafana_oncall_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_GRAFANA_ONCALL_INTEGRATION_KEY"] = "grafana-oncall-token"
        os.environ["SEO_AD_BOT_ALERT_GRAFANA_ONCALL_ENDPOINT"] = "https://oncall.example/api/v1/alerts"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Grafana OnCall Sample",
                intake=SiteIntake(url="https://grafana-oncall.example", site_name="Grafana OnCall Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://grafana-oncall.example", site_name="Grafana OnCall Sample"))

        class _GrafanaOnCallDummyResponse:
            status = 202

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_GrafanaOnCallDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="grafana-oncall")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "grafana_oncall" for item in deliveries.entries))

    def test_alert_report_feishu_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_FEISHU_WEBHOOK_URL"] = "https://open.feishu.cn/open-apis/bot/v2/hook/test"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Feishu Sample",
                intake=SiteIntake(url="https://feishu.example", site_name="Feishu Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://feishu.example", site_name="Feishu Sample"))

        class _FeishuDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_FeishuDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="feishu")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "feishu" for item in deliveries.entries))

    def test_alert_report_dingtalk_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_DINGTALK_WEBHOOK_URL"] = "https://oapi.dingtalk.com/robot/send?access_token=test"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="DingTalk Sample",
                intake=SiteIntake(url="https://dingtalk.example", site_name="DingTalk Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://dingtalk.example", site_name="DingTalk Sample"))

        class _DingTalkDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_DingTalkDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="dingtalk")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "dingtalk" for item in deliveries.entries))

    def test_alert_report_wecom_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_WECOM_WEBHOOK_URL"] = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="WeCom Sample",
                intake=SiteIntake(url="https://wecom.example", site_name="WeCom Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://wecom.example", site_name="WeCom Sample"))

        class _WeComDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_WeComDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="wecom")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "wecom" for item in deliveries.entries))

    def test_alert_report_google_chat_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_GOOGLE_CHAT_WEBHOOK_URL"] = "https://chat.googleapis.com/v1/spaces/AAA/messages?key=test&token=test"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Google Chat Sample",
                intake=SiteIntake(url="https://google-chat.example", site_name="Google Chat Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://google-chat.example", site_name="Google Chat Sample"))

        class _GoogleChatDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_GoogleChatDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="google-chat")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "google_chat" for item in deliveries.entries))

    def test_alert_report_discord_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_DISCORD_WEBHOOK_URL"] = "https://discord.com/api/webhooks/test/token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Discord Sample",
                intake=SiteIntake(url="https://discord.example", site_name="Discord Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://discord.example", site_name="Discord Sample"))

        class _DiscordDummyResponse:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_DiscordDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="discord")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "discord" for item in deliveries.entries))

    def test_alert_report_slack_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_SLACK_WEBHOOK_URL"] = "https://hooks.slack.com/services/T000/B000/TEST"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Slack Sample",
                intake=SiteIntake(url="https://slack.example", site_name="Slack Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://slack.example", site_name="Slack Sample"))

        class _SlackDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_SlackDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="slack")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "slack" for item in deliveries.entries))

    def test_alert_report_teams_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_TEAMS_WEBHOOK_URL"] = "https://example.webhook.office.com/webhookb2/test"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Teams Sample",
                intake=SiteIntake(url="https://teams.example", site_name="Teams Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://teams.example", site_name="Teams Sample"))

        class _TeamsDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_TeamsDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="teams")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "teams" for item in deliveries.entries))

    def test_alert_report_jira_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_JIRA_ENDPOINT"] = "https://jira.example/rest/api/3/issue"
        os.environ["SEO_AD_BOT_ALERT_JIRA_PROJECT_KEY"] = "SEO"
        os.environ["SEO_AD_BOT_ALERT_JIRA_EMAIL"] = "bot@example.com"
        os.environ["SEO_AD_BOT_ALERT_JIRA_API_TOKEN"] = "jira-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Jira Sample",
                intake=SiteIntake(url="https://jira.example", site_name="Jira Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://jira.example", site_name="Jira Sample"))

        class _JiraDummyResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_JiraDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="jira")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "jira" for item in deliveries.entries))

    def test_alert_report_linear_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_LINEAR_ENDPOINT"] = "https://api.linear.app/graphql"
        os.environ["SEO_AD_BOT_ALERT_LINEAR_API_KEY"] = "linear-api-key"
        os.environ["SEO_AD_BOT_ALERT_LINEAR_TEAM_ID"] = "team-seo"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Linear Sample",
                intake=SiteIntake(url="https://linear.example", site_name="Linear Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://linear.example", site_name="Linear Sample"))

        class _LinearDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_LinearDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="linear")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "linear" for item in deliveries.entries))

    def test_alert_report_asana_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_ASANA_ENDPOINT"] = "https://app.asana.com/api/1.0/tasks"
        os.environ["SEO_AD_BOT_ALERT_ASANA_API_TOKEN"] = "asana-token"
        os.environ["SEO_AD_BOT_ALERT_ASANA_PROJECT_GID"] = "1200000000000001"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Asana Sample",
                intake=SiteIntake(url="https://asana.example", site_name="Asana Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://asana.example", site_name="Asana Sample"))

        class _AsanaDummyResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_AsanaDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="asana")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "asana" for item in deliveries.entries))

    def test_alert_report_manageengine_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_MANAGEENGINE_ENDPOINT"] = "https://manageengine.example/api/v3/requests"
        os.environ["SEO_AD_BOT_ALERT_MANAGEENGINE_API_KEY"] = "manageengine-key"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="ManageEngine Sample",
                intake=SiteIntake(url="https://manageengine.example", site_name="ManageEngine Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://manageengine.example", site_name="ManageEngine Sample"))

        class _ManageEngineDummyResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_ManageEngineDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="manageengine")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "manageengine" for item in deliveries.entries))

    def test_alert_report_bmc_helix_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_BMC_HELIX_ENDPOINT"] = "https://bmc.example/api/arsys/v1/entry/HPD:IncidentInterface_Create"
        os.environ["SEO_AD_BOT_ALERT_BMC_HELIX_USERNAME"] = "bmc-user"
        os.environ["SEO_AD_BOT_ALERT_BMC_HELIX_PASSWORD"] = "bmc-pass"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="BMC Helix Sample",
                intake=SiteIntake(url="https://bmc.example", site_name="BMC Helix Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://bmc.example", site_name="BMC Helix Sample"))

        class _BMCHelixDummyResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_BMCHelixDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="bmc-helix")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "bmc_helix" for item in deliveries.entries))

    def test_alert_report_monday_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_MONDAY_ENDPOINT"] = "https://api.monday.com/v2"
        os.environ["SEO_AD_BOT_ALERT_MONDAY_API_TOKEN"] = "monday-token"
        os.environ["SEO_AD_BOT_ALERT_MONDAY_BOARD_ID"] = "123456789"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Monday Sample",
                intake=SiteIntake(url="https://monday.example", site_name="Monday Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://monday.example", site_name="Monday Sample"))

        class _MondayDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_MondayDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="monday")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "monday" for item in deliveries.entries))

    def test_alert_report_clickup_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_CLICKUP_ENDPOINT"] = "https://api.clickup.com/api/v2/list/123/task"
        os.environ["SEO_AD_BOT_ALERT_CLICKUP_API_TOKEN"] = "clickup-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="ClickUp Sample",
                intake=SiteIntake(url="https://clickup.example", site_name="ClickUp Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://clickup.example", site_name="ClickUp Sample"))

        class _ClickUpDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_ClickUpDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="clickup")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "clickup" for item in deliveries.entries))

    def test_alert_report_redmine_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_REDMINE_ENDPOINT"] = "https://redmine.example/issues.json"
        os.environ["SEO_AD_BOT_ALERT_REDMINE_API_KEY"] = "redmine-api-key"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Redmine Sample",
                intake=SiteIntake(url="https://redmine.example", site_name="Redmine Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://redmine.example", site_name="Redmine Sample"))

        class _RedmineDummyResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_RedmineDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="redmine")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "redmine" for item in deliveries.entries))

    def test_alert_report_zoho_desk_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_ZOHO_DESK_ENDPOINT"] = "https://desk.zoho.com/api/v1/tickets"
        os.environ["SEO_AD_BOT_ALERT_ZOHO_DESK_API_TOKEN"] = "zoho-token"
        os.environ["SEO_AD_BOT_ALERT_ZOHO_DESK_DEPARTMENT_ID"] = "70000000000001"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Zoho Desk Sample",
                intake=SiteIntake(url="https://zoho.example", site_name="Zoho Desk Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://zoho.example", site_name="Zoho Desk Sample"))

        class _ZohoDeskDummyResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_ZohoDeskDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="zoho-desk")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "zoho_desk" for item in deliveries.entries))

    def test_alert_report_gitlab_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_GITLAB_ENDPOINT"] = "https://gitlab.example/api/v4/projects/12/issues"
        os.environ["SEO_AD_BOT_ALERT_GITLAB_API_TOKEN"] = "gitlab-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="GitLab Sample",
                intake=SiteIntake(url="https://gitlab.example", site_name="GitLab Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://gitlab.example", site_name="GitLab Sample"))

        class _GitLabDummyResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_GitLabDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="gitlab")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "gitlab" for item in deliveries.entries))

    def test_alert_report_youtrack_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_YOUTRACK_ENDPOINT"] = "https://youtrack.example/api/issues"
        os.environ["SEO_AD_BOT_ALERT_YOUTRACK_API_TOKEN"] = "youtrack-token"
        os.environ["SEO_AD_BOT_ALERT_YOUTRACK_PROJECT_ID"] = "0-0"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="YouTrack Sample",
                intake=SiteIntake(url="https://youtrack.example", site_name="YouTrack Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://youtrack.example", site_name="YouTrack Sample"))

        class _YouTrackDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_YouTrackDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="youtrack")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "youtrack" for item in deliveries.entries))

    def test_alert_report_freshdesk_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_FRESHDESK_ENDPOINT"] = "https://freshdesk.example/api/v2/tickets"
        os.environ["SEO_AD_BOT_ALERT_FRESHDESK_API_KEY"] = "freshdesk-key"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Freshdesk Sample",
                intake=SiteIntake(url="https://freshdesk.example", site_name="Freshdesk Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://freshdesk.example", site_name="Freshdesk Sample"))

        class _FreshdeskDummyResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_FreshdeskDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="freshdesk")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "freshdesk" for item in deliveries.entries))

    def test_alert_report_intercom_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_INTERCOM_ENDPOINT"] = "https://intercom.example/tickets"
        os.environ["SEO_AD_BOT_ALERT_INTERCOM_API_TOKEN"] = "intercom-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Intercom Sample",
                intake=SiteIntake(url="https://intercom.example", site_name="Intercom Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://intercom.example", site_name="Intercom Sample"))

        class _IntercomDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_IntercomDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="intercom")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "intercom" for item in deliveries.entries))

    def test_alert_report_trello_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_TRELLO_ENDPOINT"] = "https://trello.example/1/cards"
        os.environ["SEO_AD_BOT_ALERT_TRELLO_KEY"] = "trello-key"
        os.environ["SEO_AD_BOT_ALERT_TRELLO_TOKEN"] = "trello-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Trello Sample",
                intake=SiteIntake(url="https://trello.example", site_name="Trello Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://trello.example", site_name="Trello Sample"))

        class _TrelloDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_TrelloDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="trello")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "trello" for item in deliveries.entries))

    def test_alert_report_airtable_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_AIRTABLE_ENDPOINT"] = "https://api.airtable.com/v0/app123/Alerts"
        os.environ["SEO_AD_BOT_ALERT_AIRTABLE_API_TOKEN"] = "airtable-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Airtable Sample",
                intake=SiteIntake(url="https://airtable.example", site_name="Airtable Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://airtable.example", site_name="Airtable Sample"))

        class _AirtableDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_AirtableDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="airtable")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "airtable" for item in deliveries.entries))

    def test_alert_report_servicenow_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_SERVICENOW_ENDPOINT"] = "https://servicenow.example/api/now/table/incident"
        os.environ["SEO_AD_BOT_ALERT_SERVICENOW_USERNAME"] = "bot-user"
        os.environ["SEO_AD_BOT_ALERT_SERVICENOW_PASSWORD"] = "bot-pass"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="ServiceNow Sample",
                intake=SiteIntake(url="https://servicenow.example", site_name="ServiceNow Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://servicenow.example", site_name="ServiceNow Sample"))

        class _ServiceNowDummyResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_ServiceNowDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="servicenow")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "servicenow" for item in deliveries.entries))

    def test_alert_report_zendesk_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_ZENDESK_ENDPOINT"] = "https://zendesk.example/api/v2/tickets.json"
        os.environ["SEO_AD_BOT_ALERT_ZENDESK_EMAIL"] = "bot@example.com"
        os.environ["SEO_AD_BOT_ALERT_ZENDESK_API_TOKEN"] = "zendesk-token"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Zendesk Sample",
                intake=SiteIntake(url="https://zendesk.example", site_name="Zendesk Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://zendesk.example", site_name="Zendesk Sample"))

        class _ZendeskDummyResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_ZendeskDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="zendesk")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "zendesk" for item in deliveries.entries))

    def test_alert_report_freshservice_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_FRESHSERVICE_ENDPOINT"] = "https://freshservice.example/api/v2/tickets"
        os.environ["SEO_AD_BOT_ALERT_FRESHSERVICE_API_KEY"] = "freshservice-key"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Freshservice Sample",
                intake=SiteIntake(url="https://freshservice.example", site_name="Freshservice Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://freshservice.example", site_name="Freshservice Sample"))

        class _FreshserviceDummyResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_FreshserviceDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="freshservice")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "freshservice" for item in deliveries.entries))

    def test_alert_report_azure_devops_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_AZURE_DEVOPS_ENDPOINT"] = "https://dev.azure.com/example/project/_apis/wit/workitems/$Issue?api-version=7.0"
        os.environ["SEO_AD_BOT_ALERT_AZURE_DEVOPS_PAT"] = "azure-devops-pat"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Azure DevOps Sample",
                intake=SiteIntake(url="https://azure-devops.example", site_name="Azure DevOps Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://azure-devops.example", site_name="Azure DevOps Sample"))

        class _AzureDevOpsDummyResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_AzureDevOpsDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=20, route="azure-devops")
        self.assertGreaterEqual(deliveries.total, 1)
        self.assertTrue(any(item.channel == "azure_devops" for item in deliveries.entries))

    def test_alert_report_twilio_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_TWILIO_ACCOUNT_SID"] = "AC123456789"
        os.environ["SEO_AD_BOT_ALERT_TWILIO_AUTH_TOKEN"] = "twilio-token"
        os.environ["SEO_AD_BOT_ALERT_TWILIO_FROM_NUMBER"] = "+15550000001"
        os.environ["SEO_AD_BOT_ALERT_TWILIO_TO_NUMBERS"] = "+15550000002,+15550000003"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Twilio Sample",
                intake=SiteIntake(url="https://twilio.example", site_name="Twilio Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://twilio.example", site_name="Twilio Sample"))

        class _TwilioDummyResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_TwilioDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=50, route="twilio")
        self.assertGreaterEqual(deliveries.total, 2)
        self.assertTrue(any(item.channel == "twilio" for item in deliveries.entries))

    def test_alert_report_email_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_SMTP_HOST"] = "smtp.example.com"
        os.environ["SEO_AD_BOT_ALERT_SMTP_PORT"] = "587"
        os.environ["SEO_AD_BOT_ALERT_SMTP_USERNAME"] = "bot-user"
        os.environ["SEO_AD_BOT_ALERT_SMTP_PASSWORD"] = "bot-pass"
        os.environ["SEO_AD_BOT_ALERT_SMTP_FROM_ADDRESS"] = "bot@example.com"
        os.environ["SEO_AD_BOT_ALERT_SMTP_TO_ADDRESSES"] = "ops@example.com,oncall@example.com"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Email Sample",
                intake=SiteIntake(url="https://email.example", site_name="Email Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://email.example", site_name="Email Sample"))

        class _DummySMTP:
            def __init__(self, *args, **kwargs):
                self.started_tls = False
                self.logged_in = False
                self.sent = False

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def ehlo(self):
                return None

            def starttls(self):
                self.started_tls = True

            def login(self, username, password):
                self.logged_in = username == "bot-user" and password == "bot-pass"

            def send_message(self, message):
                self.sent = True
                self.message = message

        with patch("apps.api.seo_ad_autopilot.service.smtplib.SMTP", _DummySMTP):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=50, route="email")
        self.assertGreaterEqual(deliveries.total, 2)
        self.assertTrue(any(item.channel == "email" for item in deliveries.entries))

    def test_alert_report_voice_delivery_is_audited(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_TWILIO_ACCOUNT_SID"] = "AC123456789"
        os.environ["SEO_AD_BOT_ALERT_TWILIO_AUTH_TOKEN"] = "twilio-token"
        os.environ["SEO_AD_BOT_ALERT_TWILIO_FROM_NUMBER"] = "+15550000001"
        os.environ["SEO_AD_BOT_ALERT_TWILIO_VOICE_TO_NUMBERS"] = "+15550000004,+15550000005"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Voice Sample",
                intake=SiteIntake(url="https://voice.example", site_name="Voice Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://voice.example", site_name="Voice Sample"))

        class _TwilioVoiceDummyResponse:
            status = 201

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_TwilioVoiceDummyResponse()):
            service.build_alert_report()
        deliveries = service.build_alert_delivery_report(limit=50, route="voice")
        self.assertGreaterEqual(deliveries.total, 2)
        self.assertTrue(any(item.channel == "voice" for item in deliveries.entries))

    def test_oncall_policy_api_and_delivery(self) -> None:
        primary_path = Path(self._tempdir.name) / "alerts-oncall-primary.ndjson"
        escalation_path = Path(self._tempdir.name) / "alerts-oncall-escalation.ndjson"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Oncall Sample",
                intake=SiteIntake(url="https://oncall.example", site_name="Oncall Sample"),
            )
        )
        service.run_analysis(project.project_id, SiteIntake(url="https://oncall.example", site_name="Oncall Sample"))
        app = create_app(service)

        with TestClient(app) as client:
            fetched = client.get("/api/alerts/oncall-policy")
            self.assertEqual(fetched.status_code, 200)
            self.assertIn("routes", fetched.json())

            updated = client.put(
                "/api/alerts/oncall-policy",
                json={
                    "routes": [
                        {
                            "routeId": "critical_path",
                            "enabled": True,
                            "description": "critical route",
                            "categories": [],
                            "severities": ["critical", "warning"],
                            "providers": [],
                            "blocking": None,
                            "primaryChannels": [primary_path.as_uri()],
                            "escalationChannels": [escalation_path.as_uri()],
                            "escalationAfterMinutes": 20,
                            "rotationMembers": ["alice", "bob", "carol"],
                            "rotationTimezone": "UTC",
                            "rotationHandoffHour": 9,
                        }
                    ]
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated.status_code, 200)
            coverage = client.get("/api/alerts/oncall/coverage")
            self.assertEqual(coverage.status_code, 200)
            coverage_payload = coverage.json()
            self.assertGreaterEqual(coverage_payload["routeCount"], 1)
            self.assertTrue(any(item["routeId"] == "critical_path" for item in coverage_payload["items"]))
            critical_item = next(item for item in coverage_payload["items"] if item["routeId"] == "critical_path")
            self.assertTrue(critical_item["rotationEnabled"])
            self.assertEqual(critical_item["memberCount"], 3)
            coverage_project = client.get("/api/alerts/oncall/coverage", params={"projectId": project.project_id})
            self.assertEqual(coverage_project.status_code, 200)
            self.assertEqual(coverage_project.json()["projectId"], project.project_id)

            alerts = client.get("/api/alerts", headers={"X-API-Key": "dev-key"})
            self.assertEqual(alerts.status_code, 200)

        self.assertTrue(primary_path.exists())
        primary_payload = primary_path.read_text(encoding="utf-8")
        self.assertIn('"route": "oncall:critical_path:primary"', primary_payload)
        self.assertTrue(escalation_path.exists())
        escalation_payload = escalation_path.read_text(encoding="utf-8")
        self.assertIn('"route": "oncall:critical_path:escalation"', escalation_payload)

    def test_alert_rule_api_and_delivery(self) -> None:
        service = self._service()
        app = create_app(service)

        with TestClient(app) as client:
            fetched = client.get("/api/alerts/rules")
            self.assertEqual(fetched.status_code, 200)
            self.assertIn("rules", fetched.json())

            updated = client.put(
                "/api/alerts/rules",
                json={
                    "rules": [
                        {
                            "ruleId": "network_warn",
                            "enabled": True,
                            "description": "network recoverable rule",
                            "categories": ["network"],
                            "failureCodes": ["NETWORK_TIMEOUT"],
                            "providers": ["search_console"],
                            "setBlocking": False,
                            "setSeverity": "warning",
                            "priority": 15,
                        }
                    ]
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated.status_code, 200)
            payload = updated.json()
            self.assertTrue(any(item["ruleId"] == "network_warn" for item in payload["rules"]))
            updated_rule = next(item for item in payload["rules"] if item["ruleId"] == "network_warn")
            self.assertFalse(updated_rule["setBlocking"])
            self.assertEqual(updated_rule["setSeverity"], "warning")
            self.assertEqual(updated_rule["priority"], 15)

    def test_workspace_policy_api_persists_auto_cruise_toggle(self) -> None:
        service = self._service()
        app = create_app(service)

        with TestClient(app) as client:
            fetched = client.get("/api/policy")
            self.assertEqual(fetched.status_code, 200)
            self.assertIn("autoCruiseEnabled", fetched.json())

            updated = client.put(
                "/api/policy",
                json={"autoCruiseEnabled": True},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated.status_code, 200)
            self.assertTrue(updated.json()["autoCruiseEnabled"])

            fetched_again = client.get("/api/policy")
            self.assertEqual(fetched_again.status_code, 200)
            self.assertTrue(fetched_again.json()["autoCruiseEnabled"])

    def test_workspace_billing_api_persists_plan_and_usage(self) -> None:
        service = self._service()
        app = create_app(service)

        with TestClient(app) as client:
            fetched = client.get("/api/billing")
            self.assertEqual(fetched.status_code, 200)
            payload = fetched.json()
            self.assertIn("policy", payload)
            self.assertIn("usage", payload)
            self.assertIn(payload["policy"]["planTier"], {"starter", "growth", "scale", "enterprise"})
            self.assertIn("commercialReady", payload)
            self.assertIn("warnings", payload)
            self.assertIn("recommendations", payload)

            updated = client.put(
                "/api/billing",
                json={
                    "planTier": "scale",
                    "commercialModeEnabled": True,
                    "settlementEnabled": True,
                    "settlementProviderName": "manual",
                    "settlementAccountRef": "acct_demo_001",
                    "settlementCurrency": "USD",
                    "settlementWindowDays": 15,
                    "settlementHoldbackPercent": 10,
                    "settlementPayoutThresholdCents": 5000,
                    "monthlyProjectLimit": 25,
                    "monthlyTaskLimit": 250,
                    "monthlyDeployLimit": 50,
                    "monthlyBudgetCents": 125000,
                    "overageBlocking": True,
                    "notes": ["scale plan", "billing smoke test"],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated.status_code, 200)
            updated_payload = updated.json()
            self.assertEqual(updated_payload["policy"]["planTier"], "scale")
            self.assertTrue(updated_payload["policy"]["commercialModeEnabled"])
            self.assertTrue(updated_payload["policy"]["settlementEnabled"])
            self.assertEqual(updated_payload["policy"]["settlementAccountRef"], "acct_demo_001")
            self.assertEqual(updated_payload["policy"]["settlementWindowDays"], 15)
            self.assertEqual(updated_payload["policy"]["settlementHoldbackPercent"], 10)
            self.assertEqual(updated_payload["policy"]["settlementPayoutThresholdCents"], 5000)
            self.assertEqual(updated_payload["policy"]["monthlyProjectLimit"], 25)
            self.assertEqual(updated_payload["policy"]["monthlyTaskLimit"], 250)
            self.assertEqual(updated_payload["policy"]["monthlyDeployLimit"], 50)
            self.assertEqual(updated_payload["policy"]["monthlyBudgetCents"], 125000)
            self.assertTrue(isinstance(updated_payload["usage"], dict))
            self.assertTrue(isinstance(updated_payload["settlement"], dict))

    def test_workspace_billing_settlement_execute_and_history(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Settlement Ready",
                intake=SiteIntake(
                    url="https://settlement-ready.example",
                    site_name="Settlement Ready",
                    repo_url="https://github.com/example/settlement-ready",
                    keywords=["settlement", "billing"],
                ),
            )
        )
        with service.database.session() as session:
            connections = service._load_project_connections(
                session,
                project.project_id,
                SiteIntake(
                    url="https://settlement-ready.example",
                    site_name="Settlement Ready",
                    repo_url="https://github.com/example/settlement-ready",
                    keywords=["settlement", "billing"],
                ),
            )
            for connection in connections:
                connection.status = ConnectorStatus.connected
                connection.details["authSource"] = "token"
                connection.details["mode"] = "direct"
                connection.details["sourceRef"] = f"{connection.provider.value}:demo"
                connection.details["sourceUrl"] = "https://settlement-ready.example"
                connection.provenance = ["authSource=token", "mode=direct"]
            service._persist_project_connections(session, project.project_id, connections)
        app = create_app(service)

        with TestClient(app) as client:
            updated = client.put(
                "/api/billing",
                json={
                    "commercialModeEnabled": True,
                    "settlementEnabled": True,
                    "settlementProviderName": "manual",
                    "settlementAccountRef": "acct_demo_001",
                    "settlementCurrency": "USD",
                    "settlementHoldbackPercent": 10,
                    "settlementPayoutThresholdCents": 500,
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated.status_code, 200)

            preview = client.post(
                "/api/billing/settlement/execute",
                json={"dryRun": True, "memo": "preview", "projectId": project.project_id},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(preview.status_code, 200)
            preview_payload = preview.json()
            self.assertEqual(preview_payload["execution"]["status"], "previewed")
            self.assertTrue(preview_payload["execution"]["dryRun"])
            self.assertEqual(preview_payload["execution"]["providerName"], "manual")
            self.assertEqual(preview_payload["execution"]["requestPath"], "/api/billing/settlement/execute")
            self.assertEqual(preview_payload["execution"]["requestMethod"], "POST")
            self.assertEqual(preview_payload["execution"]["projectId"], project.project_id)
            self.assertEqual(preview_payload["execution"]["projectName"], project.name)
            self.assertEqual(preview_payload["execution"]["memo"], "preview")
            self.assertEqual(preview_payload["projectId"], project.project_id)
            self.assertIn("gatewayRouteReason", preview_payload["execution"])
            self.assertTrue(preview_payload["execution"]["gatewayRouteReason"])
            self.assertIn("billing", preview_payload)

            executed = client.post(
                "/api/billing/settlement/execute",
                json={"dryRun": False, "memo": "live", "projectId": project.project_id},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertFalse(executed_payload["execution"]["dryRun"])
            self.assertTrue(executed_payload["execution"]["transactionRef"])
            self.assertTrue(executed_payload["execution"]["settlementReady"])
            self.assertEqual(executed_payload["execution"]["requestPath"], "/api/billing/settlement/execute")
            self.assertEqual(executed_payload["execution"]["requestMethod"], "POST")
            self.assertEqual(executed_payload["execution"]["projectId"], project.project_id)
            self.assertEqual(executed_payload["execution"]["projectName"], project.name)
            self.assertEqual(executed_payload["projectId"], project.project_id)
            self.assertIn("gatewayRouteReason", executed_payload["execution"])
            self.assertTrue(executed_payload["execution"]["gatewayRouteReason"])

            history = client.get("/api/billing/settlement/history?limit=10")
            self.assertEqual(history.status_code, 200)
            history_payload = history.json()
            self.assertIsNone(history_payload["projectId"])
            self.assertGreaterEqual(history_payload["total"], 2)
            self.assertGreaterEqual(len(history_payload["entries"]), 2)
            self.assertTrue(any(entry["status"] == "completed" for entry in history_payload["entries"]))
            self.assertTrue(all("gatewayRouteReason" in entry for entry in history_payload["entries"]))

            filtered_history = client.get(f"/api/billing/settlement/history?limit=10&projectId={project.project_id}")
            self.assertEqual(filtered_history.status_code, 200)
            filtered_history_payload = filtered_history.json()
            self.assertEqual(filtered_history_payload["projectId"], project.project_id)
            self.assertTrue(filtered_history_payload["entries"])
            self.assertTrue(all(entry["projectId"] == project.project_id for entry in filtered_history_payload["entries"]))
            self.assertTrue(all(entry["projectName"] == project.name for entry in filtered_history_payload["entries"]))
            self.assertEqual(filtered_history_payload["entries"][0]["projectName"], project.name)
            self.assertTrue(all("gatewayRouteReason" in entry for entry in filtered_history_payload["entries"]))

    def test_workspace_billing_settlement_batch_execute_and_history(self) -> None:
        service = self._service()
        project_one = service.create_project(
            ProjectCreateRequest(
                name="Settlement Batch One",
                intake=SiteIntake(
                    url="https://settlement-batch-one.example",
                    site_name="Settlement Batch One",
                    repo_url="https://github.com/example/settlement-batch-one",
                    keywords=["settlement", "billing"],
                ),
            )
        )
        project_two = service.create_project(
            ProjectCreateRequest(
                name="Settlement Batch Two",
                intake=SiteIntake(
                    url="https://settlement-batch-two.example",
                    site_name="Settlement Batch Two",
                    repo_url="https://github.com/example/settlement-batch-two",
                    keywords=["settlement", "billing"],
                ),
            )
        )
        with service.database.session() as session:
            for project_id in [project_one.project_id, project_two.project_id]:
                connections = service._load_project_connections(
                    session,
                    project_id,
                    SiteIntake(
                        url=f"https://{project_id}.example",
                        site_name="Settlement Batch",
                        repo_url="https://github.com/example/settlement-batch",
                        keywords=["settlement", "billing"],
                    ),
                )
                for connection in connections:
                    connection.status = ConnectorStatus.connected
                    connection.details["authSource"] = "token"
                    connection.details["mode"] = "direct"
                    connection.details["sourceRef"] = f"{connection.provider.value}:batch"
                    connection.details["sourceUrl"] = "https://settlement-batch.example"
                    connection.provenance = ["authSource=token", "mode=direct"]
                service._persist_project_connections(session, project_id, connections)

        app = create_app(service)

        with TestClient(app) as client:
            updated = client.put(
                "/api/billing",
                json={
                    "commercialModeEnabled": True,
                    "settlementEnabled": True,
                    "settlementProviderName": "manual",
                    "settlementAccountRef": "acct_demo_001",
                    "settlementCurrency": "USD",
                    "settlementHoldbackPercent": 10,
                    "settlementPayoutThresholdCents": 500,
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated.status_code, 200)

            batch = client.post(
                "/api/billing/settlement/execute/batch",
                json={
                    "dryRun": True,
                    "memo": "batch settlement preview",
                    "projectIds": [project_one.project_id, project_two.project_id],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(batch.status_code, 200)
            batch_payload = batch.json()
            self.assertEqual(batch_payload["totalCount"], 2)
            self.assertEqual(batch_payload["previewedCount"], 2)
            self.assertEqual(batch_payload["completedCount"], 0)
            self.assertEqual(batch_payload["blockedCount"], 0)
            self.assertEqual(batch_payload["failedCount"], 0)
            self.assertEqual({item["projectId"] for item in batch_payload["items"]}, {project_one.project_id, project_two.project_id})
            self.assertTrue(all(item["execution"]["status"] == "previewed" for item in batch_payload["items"]))

    def test_worker_enqueues_and_executes_workspace_billing_settlement(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Settlement Ready Worker",
                intake=SiteIntake(
                    url="https://settlement-ready-worker.example",
                    site_name="Settlement Ready Worker",
                    repo_url="https://github.com/example/settlement-ready-worker",
                    keywords=["settlement", "worker"],
                ),
            )
        )
        now = datetime.now(timezone.utc)
        billing_report = WorkspaceBillingReport(
            generated_at=now,
            project_id=project.project_id,
            policy=WorkspaceBillingPolicy(
                commercial_mode_enabled=True,
                settlement_enabled=True,
                settlement_provider_name="manual",
                settlement_account_ref="acct_demo_001",
                settlement_currency="USD",
                settlement_payout_threshold_cents=1,
            ),
            usage=WorkspaceBillingUsage(
                generated_at=now,
                active_project_count=1,
                task_count=1,
                run_count_30d=1,
                deploy_count_30d=0,
                rollback_count_30d=0,
                auto_deploy_count_30d=0,
                strict_ready_project_count=1,
                estimated_usage_cents=500,
            ),
            settlement=WorkspaceBillingSettlement(
                settlement_enabled=True,
                settlement_provider_name="manual",
                settlement_account_ref="acct_demo_001",
                settlement_currency="USD",
                payout_threshold_cents=1,
                gross_estimated_cents=500,
                holdback_cents=0,
                net_settlement_cents=500,
                settlement_due_cents=500,
                settlement_ready=True,
                settlement_blocked=False,
                notes=["ready"],
            ),
            commercial_ready=True,
            warnings=[],
            recommendations=[],
        )

        with patch.object(service, "build_workspace_billing_report", return_value=billing_report), patch.object(
            service,
            "execute_workspace_billing_settlement",
            wraps=service.execute_workspace_billing_settlement,
        ) as execute_mock:
            result = service.run_worker_once(WorkerRunOnceRequest(project_ids=[], include_approved_tasks=False, claim_limit=10))

        self.assertGreaterEqual(result.enqueued, 1)
        self.assertGreaterEqual(result.claimed, 1)
        self.assertGreaterEqual(result.processed, 1)
        self.assertTrue(execute_mock.called)
        settlement_request = execute_mock.call_args.args[0]
        self.assertTrue(settlement_request.dry_run)
        self.assertEqual(settlement_request.provider_name, "manual")
        self.assertEqual(settlement_request.project_id, project.project_id)
        self.assertEqual(settlement_request.currency, "USD")

    def test_workspace_billing_gateway_api_and_routed_settlement(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_URL": "https://billing-gateway.example/stripe/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_TOKEN": "stripe-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            project = service.create_project(
                ProjectCreateRequest(
                    name="Gateway Settlement",
                    intake=SiteIntake(
                        url="https://gateway-settlement.example",
                        site_name="Gateway Settlement",
                        repo_url="https://github.com/example/gateway-settlement",
                        keywords=["gateway", "settlement"],
                    ),
                )
            )
            with service.database.session() as session:
                connections = service._load_project_connections(
                    session,
                    project.project_id,
                    SiteIntake(
                        url="https://gateway-settlement.example",
                        site_name="Gateway Settlement",
                        repo_url="https://github.com/example/gateway-settlement",
                        keywords=["gateway", "settlement"],
                    ),
                )
                for connection in connections:
                    connection.status = ConnectorStatus.connected
                    connection.details["authSource"] = "token"
                    connection.details["mode"] = "direct"
                    connection.details["sourceRef"] = f"{connection.provider.value}:gateway"
                    connection.details["sourceUrl"] = "https://gateway-settlement.example"
                    connection.provenance = ["authSource=token", "mode=direct"]
                service._persist_project_connections(session, project.project_id, connections)
            app = create_app(service)

            with TestClient(app) as client:
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "stripe",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "stripe",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 10,
                                "notes": [
                                    "stripe settlement route",
                                    "endpoint=https://billing-gateway.example/stripe/publish",
                                    "token=stripe-publish-token",
                                    "authHeader=X-API-Key",
                                ],
                            }
                        ],
                        "notes": ["billing gateway smoke test"],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertTrue(gateway_payload["gatewayReady"])
                self.assertEqual(gateway_payload["routeReadyCount"], 1)
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "stripe")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "stripe",
                        "settlementAccountRef": "acct_demo_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 10,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)

                class _SettlementGatewayResponse:
                    status = 200

                    def read(self) -> bytes:
                        return json.dumps({"transactionRef": "stripe_txn_001", "message": "remote settlement ok"}).encode("utf-8")

                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc, tb):
                        return False

                with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_SettlementGatewayResponse()):
                    executed = client.post(
                        "/api/billing/settlement/execute",
                        json={"dryRun": False, "memo": "gateway live", "providerName": "stripe"},
                        headers={"X-API-Key": "dev-key"},
                    )
                self.assertEqual(executed.status_code, 200)
                executed_payload = executed.json()
                self.assertEqual(executed_payload["execution"]["status"], "completed")
                self.assertEqual(executed_payload["execution"]["providerName"], "stripe")
                self.assertEqual(executed_payload["execution"]["gatewayProviderName"], "stripe")
                self.assertTrue(executed_payload["execution"]["gatewayReady"])
                self.assertTrue(executed_payload["execution"]["gatewayRouteReady"])

                class _BillingGatewayPublishResponse:
                    status = 200

                    def read(self) -> bytes:
                        return json.dumps({"artifactId": "billing_gateway_artifact_001", "artifactUrl": "https://billing-gateway.example/stripe/publish", "message": "gateway publish ok"}).encode("utf-8")

                    def __enter__(self):
                        return self

                    def __exit__(self, exc_type, exc, tb):
                        return False

                with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_BillingGatewayPublishResponse()):
                    published = client.post("/api/billing/gateway/publish", headers={"X-API-Key": "dev-key"})
                self.assertEqual(published.status_code, 200)
                published_payload = published.json()
                self.assertEqual(published_payload["status"], "completed")
                self.assertEqual(published_payload["providerName"], "stripe")
                self.assertEqual(published_payload["gatewayArtifactId"], "billing_gateway_artifact_001")
                self.assertEqual(published_payload["gatewayUrl"], "https://billing-gateway.example/stripe/publish")
                self.assertEqual(published_payload["authSource"], "config")
                self.assertEqual(executed_payload["execution"]["transactionRef"], "stripe_txn_001")
                self.assertEqual(executed_payload["execution"]["requestPath"], "/api/billing/settlement/execute")
                self.assertEqual(executed_payload["execution"]["requestMethod"], "POST")
                self.assertIn("gatewayRouteReason", executed_payload["execution"])
                self.assertTrue(executed_payload["execution"]["gatewayRouteReason"])

    def test_workspace_billing_gateway_publish_blocks_without_endpoint(self) -> None:
        service = self._service()
        app = create_app(service)

        with TestClient(app) as client:
            published = client.post("/api/billing/gateway/publish", headers={"X-API-Key": "dev-key"})

        self.assertEqual(published.status_code, 200)
        payload = published.json()
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["failureCode"], "BILLING_GATEWAY_ENDPOINT_MISSING")
        self.assertFalse(payload["retryable"])

    def test_workspace_billing_gateway_publish_failover_succeeds_on_secondary_endpoint(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_TOKEN": "stripe-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)
            attempted_endpoints: list[str] = []

            class _BillingGatewayPublishResponse:
                status = 200

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "artifactId": "billing_gateway_artifact_failover_001",
                            "artifactUrl": "https://billing-gateway.example/stripe/publish/secondary",
                            "message": "gateway publish failover ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            def _mock_urlopen(request, timeout=5):
                endpoint = str(getattr(request, "full_url", ""))
                attempted_endpoints.append(endpoint)
                if endpoint.endswith("/primary"):
                    raise HTTPError(endpoint, 503, "service unavailable", hdrs=None, fp=None)
                return _BillingGatewayPublishResponse()

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "stripe",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "stripe",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 3,
                                "notes": [
                                    "endpoints=https://billing-gateway.example/stripe/publish/primary,https://billing-gateway.example/stripe/publish/secondary",
                                ],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                published = client.post("/api/billing/gateway/publish", headers={"X-API-Key": "dev-key"})
            self.assertEqual(published.status_code, 200)
            payload = published.json()
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["gatewayEndpoint"], "https://billing-gateway.example/stripe/publish/secondary")
            self.assertEqual(payload["gatewayArtifactId"], "billing_gateway_artifact_failover_001")
            self.assertIn("gatewayFailover=true", payload["notes"])
            self.assertEqual(
                attempted_endpoints,
                [
                    "https://billing-gateway.example/stripe/publish/primary",
                    "https://billing-gateway.example/stripe/publish/secondary",
                ],
            )

    def test_workspace_billing_gateway_publish_failover_returns_last_failure_when_all_endpoints_fail(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_TOKEN": "stripe-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)
            attempted_endpoints: list[str] = []

            def _mock_urlopen(request, timeout=5):
                endpoint = str(getattr(request, "full_url", ""))
                attempted_endpoints.append(endpoint)
                if endpoint.endswith("/primary"):
                    raise HTTPError(endpoint, 502, "bad gateway", hdrs=None, fp=None)
                raise RuntimeError("network down")

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "stripe",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "stripe",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 3,
                                "notes": [
                                    "endpoints=https://billing-gateway.example/stripe/publish/primary,https://billing-gateway.example/stripe/publish/secondary",
                                ],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                published = client.post("/api/billing/gateway/publish", headers={"X-API-Key": "dev-key"})
            self.assertEqual(published.status_code, 200)
            payload = published.json()
            self.assertEqual(payload["status"], "failed")
            self.assertEqual(payload["failureCode"], "BILLING_GATEWAY_REQUEST_FAILED")
            self.assertEqual(payload["gatewayEndpoint"], "https://billing-gateway.example/stripe/publish/secondary")
            self.assertTrue(any(str(note).startswith("attempt[1]=") for note in payload["notes"]))
            self.assertTrue(any(str(note).startswith("attempt[2]=") for note in payload["notes"]))
            self.assertEqual(
                attempted_endpoints,
                [
                    "https://billing-gateway.example/stripe/publish/primary",
                    "https://billing-gateway.example/stripe/publish/secondary",
                ],
            )

    def test_workspace_billing_gateway_supports_credentials_json(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_URL": "https://billing-gateway.example/stripe/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_TOKEN": json.dumps({"accessToken": "stripe-json-token"}),
            },
            clear=False,
        ):
            service = self._service()
            project = service.create_project(
                ProjectCreateRequest(
                    name="Gateway Settlement JSON",
                    intake=SiteIntake(
                        url="https://gateway-settlement-json.example",
                        site_name="Gateway Settlement JSON",
                        repo_url="https://github.com/example/gateway-settlement-json",
                        keywords=["gateway", "settlement"],
                    ),
                )
            )
            with service.database.session() as session:
                connections = service._load_project_connections(
                    session,
                    project.project_id,
                    SiteIntake(
                        url="https://gateway-settlement-json.example",
                        site_name="Gateway Settlement JSON",
                        repo_url="https://github.com/example/gateway-settlement-json",
                        keywords=["gateway", "settlement"],
                    ),
                )
                for connection in connections:
                    connection.status = ConnectorStatus.connected
                    connection.details["authSource"] = "token"
                    connection.details["mode"] = "direct"
                    connection.details["sourceRef"] = f"{connection.provider.value}:gateway"
                    connection.details["sourceUrl"] = "https://gateway-settlement-json.example"
                    connection.provenance = ["authSource=token", "mode=direct"]
                service._persist_project_connections(session, project.project_id, connections)
            app = create_app(service)

            class _SettlementGatewayResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}

                def read(self) -> bytes:
                    return json.dumps({"transactionRef": "stripe_txn_json_001", "message": "remote settlement ok"}).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _SettlementGatewayResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "stripe",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "stripe",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 10,
                                "notes": ["stripe settlement route", "authHeader=X-Stripe-Token"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "stripe",
                        "settlementAccountRef": "acct_demo_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 10,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={"dryRun": False, "memo": "gateway json", "providerName": "stripe"},
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["transactionRef"], "stripe_txn_json_001")
            self.assertTrue(any("authSource=config:json" in note for note in executed_payload["execution"]["notes"]))
            self.assertEqual(response_holder.request_headers.get("x-stripe-token"), "Bearer stripe-json-token")

    def test_workspace_billing_gateway_external_provider_requires_endpoint(self) -> None:
        with patch.dict(os.environ, {"SEO_AD_BOT_BILLING_GATEWAY_STRIPE_URL": ""}, clear=False):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "stripe",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "stripe",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 10,
                                "notes": ["stripe settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "stripe",
                        "settlementAccountRef": "acct_demo_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)

                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "gateway missing endpoint",
                        "providerName": "stripe",
                        "destinationType": "external_account",
                        "destinationRef": "ba_missing_endpoint_001",
                        "metadata": {"externalAccountToken": "btok_missing_endpoint_001"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(executed.status_code, 200)
                executed_payload = executed.json()
                self.assertEqual(executed_payload["execution"]["status"], "blocked")
                self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_GATEWAY_ENDPOINT_MISSING")
                self.assertFalse(executed_payload["execution"]["retryable"])

            fetched_gateway = client.get("/api/billing/gateway")
            self.assertEqual(fetched_gateway.status_code, 200)
            fetched_gateway_payload = fetched_gateway.json()
            self.assertFalse(fetched_gateway_payload["gatewayReady"])
            self.assertEqual(fetched_gateway_payload["routeReadyCount"], 0)

            gateway_history = client.get("/api/billing/gateway/history?limit=5&projectId=demo-gateway")
            self.assertEqual(gateway_history.status_code, 200)
            gateway_history_payload = gateway_history.json()
            self.assertIn("total", gateway_history_payload)
            self.assertIn("entries", gateway_history_payload)
            self.assertIn("gatewayReadyCount", gateway_history_payload)
            self.assertIn("gatewayRouteReadyCount", gateway_history_payload)

            model_gateway_history = client.get("/api/model-gateway/history?limit=5&projectId=demo-gateway")
            self.assertEqual(model_gateway_history.status_code, 200)
            model_gateway_history_payload = model_gateway_history.json()
            self.assertIn("total", model_gateway_history_payload)
            self.assertIn("entries", model_gateway_history_payload)
            self.assertIn("gatewayReadyCount", model_gateway_history_payload)
            self.assertIn("runtimeReadyCount", model_gateway_history_payload)
            self.assertIn("latestGatewayRouteProviderName", model_gateway_history_payload)
            self.assertIn("latestGatewayRouteFallbackProviderName", model_gateway_history_payload)
            self.assertIn("latestGatewayRoutePriority", model_gateway_history_payload)
            self.assertTrue(
                all("gatewayRouteProviderName" in entry and "gatewayRoutePriority" in entry for entry in model_gateway_history_payload["entries"])
            )

    def test_workspace_billing_gateway_ad_network_route_uses_provider_settings(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_AD_NETWORK_PROVIDER_URL": "https://ad-network.example/settlement",
                "SEO_AD_BOT_AD_NETWORK_ACCESS_TOKEN": "ad-network-token",
                "SEO_AD_BOT_AD_NETWORK_ACCOUNT_ID": "acct_ad_001",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _AdNetworkSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "adnet_txn_001",
                            "providerArtifactId": "adnet_receipt_001",
                            "providerUrl": "https://ad-network.example/receipts/001",
                            "message": "ad network settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _AdNetworkSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "ad_network",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "ad_network",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 5,
                                "notes": ["real ad network settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertTrue(gateway_payload["gatewayReady"])
                self.assertEqual(gateway_payload["routeReadyCount"], 1)

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "ad_network",
                        "settlementAccountRef": "acct_ad_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 10,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "ad network gateway",
                        "providerName": "ad_network",
                        "amountCents": 5000,
                        "projectId": "project_ad_network_001",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["transactionRef"], "adnet_txn_001")
            self.assertEqual(executed_payload["execution"]["providerName"], "ad_network")
            self.assertEqual(executed_payload["execution"]["providerArtifactId"], "adnet_receipt_001")
            self.assertEqual(executed_payload["execution"]["providerUrl"], "https://ad-network.example/receipts/001")
            self.assertEqual(executed_payload["execution"]["providerEndpoint"], "https://ad-network.example/settlement")
            self.assertTrue(any("authSource=config" in note or "authSource=config:json" in note for note in executed_payload["execution"]["notes"]))
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer ad-network-token")

    def test_workspace_billing_gateway_ad_network_route_supports_provider_urls_failover(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_AD_NETWORK_PROVIDER_URL": "",
                "SEO_AD_BOT_AD_NETWORK_PROVIDER_URLS": (
                    "https://ad-network-primary.example/settlement,"
                    "https://ad-network-secondary.example/settlement"
                ),
                "SEO_AD_BOT_AD_NETWORK_ACCESS_TOKEN": "ad-network-token",
                "SEO_AD_BOT_AD_NETWORK_ACCOUNT_ID": "acct_ad_002",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)
            request_log: list[str] = []

            class _AdNetworkFailoverSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers: dict[str, str] = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "adnet_txn_failover_001",
                            "providerArtifactId": "adnet_receipt_failover_001",
                            "providerUrl": "https://ad-network-secondary.example/receipts/001",
                            "message": "ad network settlement failover ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _AdNetworkFailoverSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                del timeout
                url = getattr(request, "full_url", "")
                request_log.append(str(url))
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                if "primary" in str(url):
                    raise HTTPError(url=str(url), code=502, msg="bad gateway", hdrs=None, fp=None)
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "ad_network",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "ad_network",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 5,
                                "notes": ["real ad network settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertTrue(gateway_payload["gatewayReady"])
                self.assertEqual(gateway_payload["routeReadyCount"], 1)

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "ad_network",
                        "settlementAccountRef": "acct_ad_002",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 10,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "ad network gateway failover",
                        "providerName": "ad_network",
                        "amountCents": 5000,
                        "projectId": "project_ad_network_failover_001",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["transactionRef"], "adnet_txn_failover_001")
            self.assertEqual(executed_payload["execution"]["providerEndpoint"], "https://ad-network-secondary.example/settlement")
            self.assertTrue(any("gatewayFailover=true" in note for note in executed_payload["execution"]["notes"]))
            self.assertEqual(
                request_log,
                [
                    "https://ad-network-primary.example/settlement",
                    "https://ad-network-secondary.example/settlement",
                ],
            )
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer ad-network-token")

    def test_workspace_billing_gateway_adsense_route_uses_provider_settings(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_ADSENSE_URL": "https://billing-gateway.example/adsense/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_ADSENSE_TOKEN": "adsense-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _AdsenseSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "adsense_txn_001",
                            "providerArtifactId": "adsense_receipt_001",
                            "providerUrl": "https://billing-gateway.example/adsense/receipts/001",
                            "message": "adsense settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _AdsenseSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "adsense",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "adsense",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 6,
                                "notes": ["adsense settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertTrue(gateway_payload["gatewayReady"])
                self.assertEqual(gateway_payload["routeReadyCount"], 1)
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "adsense")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "adsense",
                        "settlementAccountRef": "acct_adsense_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 10,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "adsense gateway",
                        "providerName": "adsense",
                        "amountCents": 5000,
                        "projectId": "project_adsense_001",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["transactionRef"], "adsense_txn_001")
            self.assertEqual(executed_payload["execution"]["providerName"], "adsense")
            self.assertEqual(executed_payload["execution"]["providerArtifactId"], "adsense_receipt_001")
            self.assertEqual(executed_payload["execution"]["providerUrl"], "https://billing-gateway.example/adsense/receipts/001")
            self.assertEqual(executed_payload["execution"]["providerEndpoint"], "https://billing-gateway.example/adsense/settle")
            self.assertTrue(any("authSource=config" in note or "authSource=config:json" in note for note in executed_payload["execution"]["notes"]))
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer adsense-gateway-token")

    def test_workspace_billing_gateway_adsense_requires_project_id_for_live_settlement(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_ADSENSE_URL": "https://billing-gateway.example/adsense/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_ADSENSE_TOKEN": "adsense-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "adsense",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "adsense", "enabled": True, "fallbackProviderName": "manual", "priority": 6}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "adsense",
                        "settlementAccountRef": "acct_adsense_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 10,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={"dryRun": False, "memo": "adsense gateway", "providerName": "adsense", "amountCents": 5000},
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            payload = executed.json()
            self.assertEqual(payload["execution"]["status"], "blocked")
            self.assertEqual(payload["execution"]["failureCode"], "SETTLEMENT_PROJECT_ID_MISSING")

    def test_workspace_billing_gateway_mediavine_route_uses_ad_network_settings(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_AD_NETWORK_PROVIDER_URL": "https://billing-gateway.example/mediavine/settle",
                "SEO_AD_BOT_AD_NETWORK_ACCESS_TOKEN": "mediavine-gateway-token",
                "SEO_AD_BOT_AD_NETWORK_ACCOUNT_ID": "acct_mediavine_001",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _MediavineSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "mediavine_txn_001",
                            "providerArtifactId": "mediavine_receipt_001",
                            "providerUrl": "https://billing-gateway.example/mediavine/receipts/001",
                            "message": "mediavine settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _MediavineSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "mediavine",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "mediavine",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 7,
                                "notes": ["mediavine settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertTrue(gateway_payload["gatewayReady"])
                self.assertEqual(gateway_payload["routeReadyCount"], 1)
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "mediavine")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "mediavine",
                        "settlementAccountRef": "acct_mediavine_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 10,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "mediavine gateway",
                        "providerName": "mediavine",
                        "amountCents": 6500,
                        "projectId": "project_mediavine_001",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["transactionRef"], "mediavine_txn_001")
            self.assertEqual(executed_payload["execution"]["providerName"], "mediavine")
            self.assertEqual(executed_payload["execution"]["providerArtifactId"], "mediavine_receipt_001")
            self.assertEqual(executed_payload["execution"]["providerUrl"], "https://billing-gateway.example/mediavine/receipts/001")
            self.assertEqual(executed_payload["execution"]["providerEndpoint"], "https://billing-gateway.example/mediavine/settle")
            self.assertTrue(any("authSource=config" in note or "authSource=config:json" in note for note in executed_payload["execution"]["notes"]))
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer mediavine-gateway-token")

    def test_workspace_billing_gateway_ezoic_route_uses_ad_network_settings(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_AD_NETWORK_PROVIDER_URL": "https://billing-gateway.example/ezoic/settle",
                "SEO_AD_BOT_AD_NETWORK_ACCESS_TOKEN": "ezoic-gateway-token",
                "SEO_AD_BOT_AD_NETWORK_ACCOUNT_ID": "acct_ezoic_001",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _EzoicSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "ezoic_txn_001",
                            "providerArtifactId": "ezoic_receipt_001",
                            "providerUrl": "https://billing-gateway.example/ezoic/receipts/001",
                            "message": "ezoic settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _EzoicSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "ezoic",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "ezoic",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 8,
                                "notes": ["ezoic settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertTrue(gateway_payload["gatewayReady"])
                self.assertEqual(gateway_payload["routeReadyCount"], 1)
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "ezoic")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "ezoic",
                        "settlementAccountRef": "acct_ezoic_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 10,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "ezoic gateway",
                        "providerName": "ezoic",
                        "amountCents": 7200,
                        "projectId": "project_ezoic_001",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["transactionRef"], "ezoic_txn_001")
            self.assertEqual(executed_payload["execution"]["providerName"], "ezoic")
            self.assertEqual(executed_payload["execution"]["providerArtifactId"], "ezoic_receipt_001")
            self.assertEqual(executed_payload["execution"]["providerUrl"], "https://billing-gateway.example/ezoic/receipts/001")
            self.assertEqual(executed_payload["execution"]["providerEndpoint"], "https://billing-gateway.example/ezoic/settle")
            self.assertTrue(any("authSource=config" in note or "authSource=config:json" in note for note in executed_payload["execution"]["notes"]))
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer ezoic-gateway-token")

    def test_workspace_billing_gateway_raptive_route_uses_ad_network_settings(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_AD_NETWORK_PROVIDER_URL": "https://billing-gateway.example/raptive/settle",
                "SEO_AD_BOT_AD_NETWORK_ACCESS_TOKEN": "raptive-gateway-token",
                "SEO_AD_BOT_AD_NETWORK_ACCOUNT_ID": "acct_raptive_001",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _RaptiveSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "raptive_txn_001",
                            "providerArtifactId": "raptive_receipt_001",
                            "providerUrl": "https://billing-gateway.example/raptive/receipts/001",
                            "message": "raptive settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _RaptiveSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "raptive",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "raptive",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 10,
                                "notes": ["raptive settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertTrue(gateway_payload["gatewayReady"])
                self.assertEqual(gateway_payload["routeReadyCount"], 1)
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "raptive")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "raptive",
                        "settlementAccountRef": "acct_raptive_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 10,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "raptive gateway",
                        "providerName": "raptive",
                        "amountCents": 4800,
                        "projectId": "project_raptive_001",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["transactionRef"], "raptive_txn_001")
            self.assertEqual(executed_payload["execution"]["providerName"], "raptive")
            self.assertEqual(executed_payload["execution"]["providerArtifactId"], "raptive_receipt_001")
            self.assertEqual(executed_payload["execution"]["providerUrl"], "https://billing-gateway.example/raptive/receipts/001")
            self.assertEqual(executed_payload["execution"]["providerEndpoint"], "https://billing-gateway.example/raptive/settle")
            self.assertTrue(any("authSource=config" in note or "authSource=config:json" in note for note in executed_payload["execution"]["notes"]))
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer raptive-gateway-token")

    def test_workspace_billing_gateway_gam_route_uses_ad_network_settings(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_AD_NETWORK_PROVIDER_URL": "https://billing-gateway.example/gam/settle",
                "SEO_AD_BOT_AD_NETWORK_ACCESS_TOKEN": "gam-gateway-token",
                "SEO_AD_BOT_AD_NETWORK_ACCOUNT_ID": "acct_gam_001",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _GamSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "gam_txn_001",
                            "providerArtifactId": "gam_receipt_001",
                            "providerUrl": "https://billing-gateway.example/gam/receipts/001",
                            "message": "gam settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _GamSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "gam",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "gam",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 7,
                                "notes": ["gam settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertTrue(gateway_payload["gatewayReady"])
                self.assertEqual(gateway_payload["routeReadyCount"], 1)
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "gam")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "gam",
                        "settlementAccountRef": "acct_gam_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 10,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "gam gateway",
                        "providerName": "gam",
                        "amountCents": 9100,
                        "projectId": "project_gam_001",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["transactionRef"], "gam_txn_001")
            self.assertEqual(executed_payload["execution"]["providerName"], "gam")
            self.assertEqual(executed_payload["execution"]["providerArtifactId"], "gam_receipt_001")
            self.assertEqual(executed_payload["execution"]["providerUrl"], "https://billing-gateway.example/gam/receipts/001")
            self.assertEqual(executed_payload["execution"]["providerEndpoint"], "https://billing-gateway.example/gam/settle")
            self.assertTrue(any("authSource=config" in note or "authSource=config:json" in note for note in executed_payload["execution"]["notes"]))
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer gam-gateway-token")

    def test_workspace_billing_gateway_google_ad_manager_alias_routes_to_gam(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_AD_NETWORK_PROVIDER_URL": "https://billing-gateway.example/google-ad-manager/settle",
                "SEO_AD_BOT_AD_NETWORK_ACCESS_TOKEN": "google-ad-manager-gateway-token",
                "SEO_AD_BOT_AD_NETWORK_ACCOUNT_ID": "acct_google_ad_manager_001",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _GoogleAdManagerSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "gam_alias_txn_001",
                            "providerArtifactId": "gam_alias_receipt_001",
                            "providerUrl": "https://billing-gateway.example/google-ad-manager/receipts/001",
                            "message": "google ad manager settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _GoogleAdManagerSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Google Ad Manager",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "Google Ad Manager",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 7,
                                "notes": ["google ad manager settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertTrue(gateway_payload["gatewayReady"])
                self.assertEqual(gateway_payload["routeReadyCount"], 1)
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "gam")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Google Ad Manager",
                        "settlementAccountRef": "acct_google_ad_manager_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 10,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "google ad manager gateway",
                        "providerName": "Google Ad Manager",
                        "amountCents": 9100,
                        "projectId": "project_google_ad_manager_001",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["providerName"], "gam")
            self.assertEqual(executed_payload["execution"]["gatewayProviderName"], "gam")
            self.assertEqual(executed_payload["execution"]["transactionRef"], "gam_alias_txn_001")
            self.assertEqual(executed_payload["execution"]["providerArtifactId"], "gam_alias_receipt_001")
            self.assertEqual(executed_payload["execution"]["providerUrl"], "https://billing-gateway.example/google-ad-manager/receipts/001")
            self.assertEqual(executed_payload["execution"]["providerEndpoint"], "https://billing-gateway.example/google-ad-manager/settle")
            self.assertTrue(any("authSource=config" in note or "authSource=config:json" in note for note in executed_payload["execution"]["notes"]))
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer google-ad-manager-gateway-token")

    def test_workspace_billing_gateway_paypal_payouts_alias_routes_to_paypal(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_PAYPAL_URL": "https://billing-gateway.example/paypal/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_PAYPAL_TOKEN": "paypal-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _PayPalSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "paypal_txn_001",
                            "providerArtifactId": "paypal_receipt_001",
                            "providerUrl": "https://billing-gateway.example/paypal/receipts/001",
                            "message": "paypal settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _PayPalSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "PayPal Payouts",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "PayPal Payouts",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 4,
                                "notes": ["paypal merchant settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertTrue(gateway_payload["gatewayReady"])
                self.assertEqual(gateway_payload["routeReadyCount"], 1)
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "paypal")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "PayPal Payouts",
                        "settlementAccountRef": "merchant_paypal_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 5,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "paypal merchant payout",
                        "providerName": "PayPal Payouts",
                        "amountCents": 9100,
                        "destinationType": "paypal_account",
                        "destinationRef": "merchant-paypal-destination-001",
                        "beneficiaryName": "SEO AD Merchant",
                        "beneficiaryEmail": "merchant@example.com",
                        "rail": "payouts",
                        "countryCode": "us",
                        "metadata": {"batchId": "batch_paypal_001", "invoiceRef": "invoice_2026_04"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["providerName"], "paypal")
            self.assertEqual(executed_payload["execution"]["gatewayProviderName"], "paypal")
            self.assertEqual(executed_payload["execution"]["transactionRef"], "paypal_txn_001")
            self.assertEqual(executed_payload["execution"]["providerArtifactId"], "paypal_receipt_001")
            self.assertEqual(executed_payload["execution"]["providerUrl"], "https://billing-gateway.example/paypal/receipts/001")
            self.assertEqual(executed_payload["execution"]["providerEndpoint"], "https://billing-gateway.example/paypal/settle")
            self.assertEqual(executed_payload["execution"]["destinationType"], "paypal_account")
            self.assertEqual(executed_payload["execution"]["destinationRef"], "merchant-paypal-destination-001")
            self.assertEqual(executed_payload["execution"]["beneficiaryName"], "SEO AD Merchant")
            self.assertEqual(executed_payload["execution"]["beneficiaryEmail"], "merchant@example.com")
            self.assertEqual(executed_payload["execution"]["rail"], "payouts")
            self.assertEqual(executed_payload["execution"]["countryCode"], "US")
            self.assertEqual(executed_payload["execution"]["metadata"]["batchId"], "batch_paypal_001")
            self.assertTrue(any("authSource=config" in note or "authSource=config:json" in note for note in executed_payload["execution"]["notes"]))
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer paypal-gateway-token")
            self.assertEqual(response_holder.request_payload["destinationType"], "paypal_account")
            self.assertEqual(response_holder.request_payload["destinationRef"], "merchant-paypal-destination-001")
            self.assertEqual(response_holder.request_payload["beneficiaryName"], "SEO AD Merchant")
            self.assertEqual(response_holder.request_payload["beneficiaryEmail"], "merchant@example.com")
            self.assertEqual(response_holder.request_payload["rail"], "payouts")
            self.assertEqual(response_holder.request_payload["countryCode"], "US")
            self.assertEqual(response_holder.request_payload["metadata"]["invoiceRef"], "invoice_2026_04")

    def test_workspace_billing_gateway_wise_payouts_alias_routes_to_wise(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_WISE_URL": "https://billing-gateway.example/wise/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_WISE_TOKEN": "wise-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _WiseSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "wise_txn_001",
                            "providerArtifactId": "wise_transfer_001",
                            "providerUrl": "https://billing-gateway.example/wise/transfers/001",
                            "message": "wise settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _WiseSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Wise Payouts",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "Wise Payouts",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 5,
                                "notes": ["wise merchant settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertTrue(gateway_payload["gatewayReady"])
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "wise")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Wise Payouts",
                        "settlementAccountRef": "merchant_wise_001",
                        "settlementCurrency": "EUR",
                        "settlementHoldbackPercent": 2,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "wise merchant payout",
                        "providerName": "Wise Payouts",
                        "amountCents": 22100,
                        "destinationType": "bank_account",
                        "destinationRef": "iban_de89370400440532013000",
                        "beneficiaryName": "SEO AD GmbH",
                        "beneficiaryEmail": "finance@example.de",
                        "rail": "sepa",
                        "countryCode": "de",
                        "metadata": {"transferGroup": "europe_apr", "statementRef": "seo-ad-2026-04"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["providerName"], "wise")
            self.assertEqual(executed_payload["execution"]["gatewayProviderName"], "wise")
            self.assertEqual(executed_payload["execution"]["transactionRef"], "wise_txn_001")
            self.assertEqual(executed_payload["execution"]["providerArtifactId"], "wise_transfer_001")
            self.assertEqual(executed_payload["execution"]["providerUrl"], "https://billing-gateway.example/wise/transfers/001")
            self.assertEqual(executed_payload["execution"]["providerEndpoint"], "https://billing-gateway.example/wise/settle")
            self.assertEqual(executed_payload["execution"]["destinationType"], "bank_account")
            self.assertEqual(executed_payload["execution"]["destinationRef"], "iban_de89370400440532013000")
            self.assertEqual(executed_payload["execution"]["beneficiaryName"], "SEO AD GmbH")
            self.assertEqual(executed_payload["execution"]["beneficiaryEmail"], "finance@example.de")
            self.assertEqual(executed_payload["execution"]["rail"], "sepa")
            self.assertEqual(executed_payload["execution"]["countryCode"], "DE")
            self.assertEqual(executed_payload["execution"]["metadata"]["transferGroup"], "europe_apr")
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer wise-gateway-token")
            self.assertEqual(response_holder.request_payload["providerName"], "wise")
            self.assertEqual(response_holder.request_payload["rail"], "sepa")
            self.assertEqual(response_holder.request_payload["countryCode"], "DE")
            self.assertEqual(response_holder.request_payload["metadata"]["statementRef"], "seo-ad-2026-04")

    def test_workspace_billing_gateway_payoneer_payouts_alias_routes_to_payoneer(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_PAYONEER_URL": "https://billing-gateway.example/payoneer/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_PAYONEER_TOKEN": "payoneer-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _PayoneerSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "payoneer_txn_001",
                            "providerArtifactId": "payoneer_transfer_001",
                            "providerUrl": "https://billing-gateway.example/payoneer/transfers/001",
                            "message": "payoneer settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _PayoneerSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Payoneer Payouts",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "Payoneer Payouts",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 6,
                                "notes": ["payoneer merchant settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "payoneer")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Payoneer Payouts",
                        "settlementAccountRef": "merchant_payoneer_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 3,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "payoneer payout",
                        "providerName": "Payoneer Payouts",
                        "amountCents": 13200,
                        "destinationType": "bank_account",
                        "destinationRef": "payoneer-destination-001",
                        "beneficiaryName": "SEO AD Merchant",
                        "beneficiaryEmail": "ops@example.com",
                        "rail": "local",
                        "countryCode": "us",
                        "metadata": {"batchId": "payoneer_apr_2026"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["providerName"], "payoneer")
            self.assertEqual(executed_payload["execution"]["providerEndpoint"], "https://billing-gateway.example/payoneer/settle")
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer payoneer-gateway-token")
            self.assertEqual(response_holder.request_payload["providerName"], "payoneer")
            self.assertEqual(response_holder.request_payload["destinationType"], "bank_account")
            self.assertEqual(response_holder.request_payload["countryCode"], "US")

    def test_workspace_billing_gateway_airwallex_transfers_alias_routes_to_airwallex(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_AIRWALLEX_URL": "https://billing-gateway.example/airwallex/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_AIRWALLEX_TOKEN": "airwallex-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _AirwallexSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "airwallex_txn_001",
                            "providerArtifactId": "airwallex_transfer_001",
                            "providerUrl": "https://billing-gateway.example/airwallex/transfers/001",
                            "message": "airwallex settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _AirwallexSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Airwallex Transfers",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "Airwallex Transfers",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 7,
                                "notes": ["airwallex merchant settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "airwallex")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Airwallex Transfers",
                        "settlementAccountRef": "merchant_airwallex_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 4,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "airwallex payout",
                        "providerName": "Airwallex Transfers",
                        "amountCents": 15400,
                        "destinationType": "bank_account",
                        "destinationRef": "airwallex-destination-001",
                        "beneficiaryName": "SEO AD Merchant",
                        "beneficiaryEmail": "ops@example.com",
                        "rail": "swift",
                        "countryCode": "sg",
                        "metadata": {"batchId": "airwallex_apr_2026"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["providerName"], "airwallex")
            self.assertEqual(executed_payload["execution"]["providerEndpoint"], "https://billing-gateway.example/airwallex/settle")
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer airwallex-gateway-token")
            self.assertEqual(response_holder.request_payload["providerName"], "airwallex")
            self.assertEqual(response_holder.request_payload["destinationType"], "bank_account")
            self.assertEqual(response_holder.request_payload["countryCode"], "SG")

    def test_workspace_billing_gateway_tipalti_payouts_alias_routes_to_tipalti(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_TIPALTI_URL": "https://billing-gateway.example/tipalti/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_TIPALTI_TOKEN": "tipalti-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _TipaltiSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "tipalti_txn_001",
                            "providerArtifactId": "tipalti_transfer_001",
                            "providerUrl": "https://billing-gateway.example/tipalti/transfers/001",
                            "message": "tipalti settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _TipaltiSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Tipalti Payouts",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "Tipalti Payouts",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 8,
                                "notes": ["tipalti merchant settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "tipalti")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Tipalti Payouts",
                        "settlementAccountRef": "merchant_tipalti_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 3,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)

                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "tipalti payout",
                        "providerName": "Tipalti Payouts",
                        "amountCents": 12100,
                        "destinationType": "bank_account",
                        "destinationRef": "tipalti-destination-001",
                        "beneficiaryName": "SEO AD Merchant",
                        "countryCode": "us",
                        "rail": "local",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["providerName"], "tipalti")
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer tipalti-gateway-token")
            self.assertEqual(response_holder.request_payload["providerName"], "tipalti")
            self.assertEqual(response_holder.request_payload["destinationType"], "bank_account")

    def test_workspace_billing_gateway_hyperwallet_payouts_alias_routes_to_hyperwallet(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_HYPERWALLET_URL": "https://billing-gateway.example/hyperwallet/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_HYPERWALLET_TOKEN": "hyperwallet-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _HyperwalletSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "hyperwallet_txn_001",
                            "providerArtifactId": "hyperwallet_transfer_001",
                            "providerUrl": "https://billing-gateway.example/hyperwallet/transfers/001",
                            "message": "hyperwallet settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _HyperwalletSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Hyperwallet Payouts",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "Hyperwallet Payouts",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 9,
                                "notes": ["hyperwallet merchant settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "hyperwallet")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Hyperwallet Payouts",
                        "settlementAccountRef": "merchant_hyperwallet_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 3,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)

                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "hyperwallet payout",
                        "providerName": "Hyperwallet Payouts",
                        "amountCents": 12800,
                        "destinationType": "bank_account",
                        "destinationRef": "hyperwallet-destination-001",
                        "beneficiaryName": "SEO AD Merchant",
                        "countryCode": "gb",
                        "rail": "swift",
                        "metadata": {"swiftCode": "HYPWGB2L"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["providerName"], "hyperwallet")
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer hyperwallet-gateway-token")
            self.assertEqual(response_holder.request_payload["providerName"], "hyperwallet")
            self.assertEqual(response_holder.request_payload["destinationType"], "bank_account")
            self.assertEqual(response_holder.request_payload["rail"], "swift")
            self.assertEqual(response_holder.request_payload["metadata"]["swiftCode"], "HYPWGB2L")

    def test_workspace_billing_gateway_stripe_connect_alias_routes_to_stripe(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_URL": "https://billing-gateway.example/stripe/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_TOKEN": "stripe-connect-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _StripeSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "stripe_connect_txn_001",
                            "providerArtifactId": "stripe_payout_001",
                            "providerUrl": "https://billing-gateway.example/stripe/payouts/001",
                            "message": "stripe connect settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _StripeSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Stripe Connect",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "Stripe Connect",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 3,
                                "notes": ["stripe connect merchant settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "stripe")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Stripe Connect",
                        "settlementAccountRef": "merchant_stripe_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 3,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "stripe connect payout",
                        "providerName": "Stripe Connect",
                        "amountCents": 14500,
                        "destinationType": "connected_account",
                        "destinationRef": "acct_1STRIPECONNECTED",
                        "beneficiaryEmail": "ops@example.com",
                        "metadata": {"transferGroup": "stripe_apr_2026"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["providerName"], "stripe")
            self.assertEqual(executed_payload["execution"]["destinationType"], "connected_account")
            self.assertEqual(executed_payload["execution"]["destinationRef"], "acct_1STRIPECONNECTED")
            self.assertEqual(executed_payload["execution"]["metadata"]["transferGroup"], "stripe_apr_2026")
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer stripe-connect-token")
            self.assertEqual(response_holder.request_payload["providerName"], "stripe")
            self.assertEqual(response_holder.request_payload["destinationType"], "connected_account")
            self.assertEqual(response_holder.request_payload["destinationRef"], "acct_1STRIPECONNECTED")

    def test_workspace_billing_gateway_ach_transfer_alias_routes_to_ach(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_ACH_URL": "https://billing-gateway.example/ach/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_ACH_TOKEN": "ach-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _AchSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "ach_txn_001",
                            "providerArtifactId": "ach_transfer_001",
                            "providerUrl": "https://billing-gateway.example/ach/transfers/001",
                            "message": "ach settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _AchSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "ACH transfer",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "ACH transfer",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 7,
                                "notes": ["ach merchant settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "ach")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "ACH transfer",
                        "settlementAccountRef": "merchant_ach_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 1,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "ach merchant payout",
                        "providerName": "ACH transfer",
                        "amountCents": 18750,
                        "destinationType": "bank_account",
                        "destinationRef": "us_ach_account_token_001",
                        "beneficiaryName": "SEO AD LLC",
                        "beneficiaryEmail": "ap@example.com",
                        "rail": "ach",
                        "countryCode": "us",
                        "metadata": {"companyEntryDescription": "VENDORPAY"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["providerName"], "ach")
            self.assertEqual(executed_payload["execution"]["rail"], "ach")
            self.assertEqual(executed_payload["execution"]["countryCode"], "US")
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer ach-gateway-token")
            self.assertEqual(response_holder.request_payload["providerName"], "ach")
            self.assertEqual(response_holder.request_payload["rail"], "ach")
            self.assertEqual(response_holder.request_payload["metadata"]["companyEntryDescription"], "VENDORPAY")

    def test_workspace_billing_gateway_ach_requires_destination_fields(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_ACH_URL": "https://billing-gateway.example/ach/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_ACH_TOKEN": "ach-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "ACH transfer",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "ACH transfer",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 7,
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "ACH transfer",
                        "settlementAccountRef": "merchant_ach_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "ACH transfer",
                        "amountCents": 8000,
                        "destinationType": "bank_account",
                        "beneficiaryName": "SEO AD LLC",
                        "rail": "ach",
                        "countryCode": "US",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "blocked")
            self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_DESTINATION_REF_MISSING")
            self.assertIn("blocked=settlement_destination_ref_missing", executed_payload["execution"]["notes"])

    def test_workspace_billing_gateway_wire_transfer_alias_routes_to_bank_transfer(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_URL": "https://billing-gateway.example/bank-transfer/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_TOKEN": "bank-transfer-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _BankTransferSettlementResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "bank_transfer_txn_001",
                            "providerArtifactId": "bank_transfer_receipt_001",
                            "providerUrl": "https://billing-gateway.example/bank-transfer/transfers/001",
                            "message": "bank transfer settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _BankTransferSettlementResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                updated_gateway = client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "wire transfer",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "wire transfer",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 6,
                                "notes": ["bank transfer merchant settlement route"],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_gateway.status_code, 200)
                gateway_payload = updated_gateway.json()
                self.assertEqual(gateway_payload["routes"][0]["resolvedProviderName"], "bank_transfer")

                updated_billing = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "wire transfer",
                        "settlementAccountRef": "merchant_bank_transfer_001",
                        "settlementCurrency": "USD",
                        "settlementHoldbackPercent": 2,
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated_billing.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "memo": "wire transfer merchant payout",
                        "providerName": "wire transfer",
                        "amountCents": 26400,
                        "destinationType": "bank_account",
                        "destinationRef": "swift_us_boaaus3n_001",
                        "beneficiaryName": "SEO AD Global Ltd",
                        "beneficiaryEmail": "treasury@example.com",
                        "rail": "swift",
                        "countryCode": "us",
                        "metadata": {"swiftCode": "BOFAUS3N", "statementRef": "WIRE-APR-2026"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "completed")
            self.assertEqual(executed_payload["execution"]["providerName"], "bank_transfer")
            self.assertEqual(executed_payload["execution"]["gatewayProviderName"], "bank_transfer")
            self.assertEqual(executed_payload["execution"]["transactionRef"], "bank_transfer_txn_001")
            self.assertEqual(executed_payload["execution"]["providerArtifactId"], "bank_transfer_receipt_001")
            self.assertEqual(executed_payload["execution"]["providerUrl"], "https://billing-gateway.example/bank-transfer/transfers/001")
            self.assertEqual(executed_payload["execution"]["providerEndpoint"], "https://billing-gateway.example/bank-transfer/settle")
            self.assertEqual(executed_payload["execution"]["rail"], "swift")
            self.assertEqual(executed_payload["execution"]["countryCode"], "US")
            self.assertEqual(executed_payload["execution"]["metadata"]["swiftCode"], "BOFAUS3N")
            self.assertEqual(response_holder.request_headers.get("authorization"), "Bearer bank-transfer-gateway-token")
            self.assertEqual(response_holder.request_payload["providerName"], "bank_transfer")
            self.assertEqual(response_holder.request_payload["rail"], "swift")
            self.assertEqual(response_holder.request_payload["metadata"]["statementRef"], "WIRE-APR-2026")

    def test_workspace_billing_gateway_bank_transfer_requires_rail(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_URL": "https://billing-gateway.example/bank-transfer/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_TOKEN": "bank-transfer-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "wire transfer",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "wire transfer",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 6,
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "wire transfer",
                        "settlementAccountRef": "merchant_bank_transfer_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "wire transfer",
                        "amountCents": 8000,
                        "destinationType": "bank_account",
                        "destinationRef": "swift_us_boaaus3n_001",
                        "beneficiaryName": "SEO AD Global Ltd",
                        "countryCode": "US",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "blocked")
            self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_RAIL_MISSING")
            self.assertIn("blocked=settlement_rail_missing", executed_payload["execution"]["notes"])

    def test_workspace_billing_gateway_paypal_requires_beneficiary_email(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_PAYPAL_URL": "https://billing-gateway.example/paypal/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_PAYPAL_TOKEN": "paypal-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "PayPal Payouts",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "PayPal Payouts", "enabled": True, "fallbackProviderName": "manual", "priority": 4}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "PayPal Payouts",
                        "settlementAccountRef": "merchant_paypal_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "PayPal Payouts",
                        "amountCents": 8000,
                        "destinationType": "paypal_account",
                        "destinationRef": "merchant-paypal-destination-001",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "blocked")
            self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_BENEFICIARY_EMAIL_MISSING")

    def test_workspace_billing_gateway_stripe_requires_supported_destination_type(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_URL": "https://billing-gateway.example/stripe/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_TOKEN": "stripe-connect-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Stripe Connect",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "Stripe Connect", "enabled": True, "fallbackProviderName": "manual", "priority": 3}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Stripe Connect",
                        "settlementAccountRef": "merchant_stripe_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "Stripe Connect",
                        "amountCents": 8000,
                        "destinationType": "bank_account",
                        "destinationRef": "acct_1STRIPECONNECTED",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "blocked")
            self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_DESTINATION_TYPE_INVALID")

    def test_workspace_billing_gateway_tipalti_requires_bank_account_destination_type(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_TIPALTI_URL": "https://billing-gateway.example/tipalti/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_TIPALTI_TOKEN": "tipalti-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Tipalti Payouts",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "Tipalti Payouts", "enabled": True, "fallbackProviderName": "manual", "priority": 8}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Tipalti Payouts",
                        "settlementAccountRef": "merchant_tipalti_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "Tipalti Payouts",
                        "amountCents": 8000,
                        "destinationType": "recipient",
                        "destinationRef": "tipalti-destination-001",
                        "beneficiaryName": "SEO AD Merchant",
                        "countryCode": "US",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "blocked")
            self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_DESTINATION_TYPE_INVALID")

    def test_workspace_billing_gateway_hyperwallet_requires_bank_account_destination_type(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_HYPERWALLET_URL": "https://billing-gateway.example/hyperwallet/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_HYPERWALLET_TOKEN": "hyperwallet-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Hyperwallet Payouts",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "Hyperwallet Payouts", "enabled": True, "fallbackProviderName": "manual", "priority": 9}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Hyperwallet Payouts",
                        "settlementAccountRef": "merchant_hyperwallet_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "Hyperwallet Payouts",
                        "amountCents": 8000,
                        "destinationType": "recipient",
                        "destinationRef": "hyperwallet-destination-001",
                        "beneficiaryName": "SEO AD Merchant",
                        "countryCode": "GB",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "blocked")
            self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_DESTINATION_TYPE_INVALID")

    def test_workspace_billing_gateway_hyperwallet_requires_swift_code_for_swift_rail(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_HYPERWALLET_URL": "https://billing-gateway.example/hyperwallet/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_HYPERWALLET_TOKEN": "hyperwallet-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Hyperwallet Payouts",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "Hyperwallet Payouts", "enabled": True, "fallbackProviderName": "manual", "priority": 9}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Hyperwallet Payouts",
                        "settlementAccountRef": "merchant_hyperwallet_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "Hyperwallet Payouts",
                        "amountCents": 8000,
                        "destinationType": "bank_account",
                        "destinationRef": "hyperwallet-destination-001",
                        "beneficiaryName": "SEO AD Merchant",
                        "countryCode": "GB",
                        "rail": "swift",
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "blocked")
            self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_METADATA_MISSING")

    def test_workspace_billing_gateway_ach_requires_company_entry_description(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_ACH_URL": "https://billing-gateway.example/ach/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_ACH_TOKEN": "ach-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "ACH transfer",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "ACH transfer", "enabled": True, "fallbackProviderName": "manual", "priority": 7}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "ACH transfer",
                        "settlementAccountRef": "merchant_ach_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "ACH transfer",
                        "amountCents": 8000,
                        "destinationType": "bank_account",
                        "destinationRef": "us_ach_account_token_001",
                        "beneficiaryName": "SEO AD LLC",
                        "rail": "ach",
                        "countryCode": "US",
                        "metadata": {},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "blocked")
            self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_METADATA_MISSING")

    def test_workspace_billing_gateway_swift_requires_swift_code(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_URL": "https://billing-gateway.example/bank-transfer/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_TOKEN": "bank-transfer-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "wire transfer",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "wire transfer", "enabled": True, "fallbackProviderName": "manual", "priority": 6}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "wire transfer",
                        "settlementAccountRef": "merchant_bank_transfer_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "wire transfer",
                        "amountCents": 8000,
                        "destinationType": "bank_account",
                        "destinationRef": "swift_us_boaaus3n_001",
                        "beneficiaryName": "SEO AD Global Ltd",
                        "countryCode": "US",
                        "rail": "swift",
                        "metadata": {"statementRef": "WIRE-APR-2026"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "blocked")
            self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_METADATA_MISSING")

    def test_workspace_billing_gateway_sepa_requires_iban(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_URL": "https://billing-gateway.example/bank-transfer/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_TOKEN": "bank-transfer-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "wire transfer",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "wire transfer", "enabled": True, "fallbackProviderName": "manual", "priority": 6}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "wire transfer",
                        "settlementAccountRef": "merchant_bank_transfer_001",
                        "settlementCurrency": "EUR",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "wire transfer",
                        "amountCents": 8000,
                        "destinationType": "bank_account",
                        "destinationRef": "sepa_destination_001",
                        "beneficiaryName": "SEO AD GmbH",
                        "countryCode": "DE",
                        "rail": "sepa",
                        "metadata": {"statementRef": "SEPA-APR-2026"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "blocked")
            self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_METADATA_MISSING")

    def test_workspace_billing_gateway_wire_requires_routing_number(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_URL": "https://billing-gateway.example/bank-transfer/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_TOKEN": "bank-transfer-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "wire transfer",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "wire transfer", "enabled": True, "fallbackProviderName": "manual", "priority": 6}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "wire transfer",
                        "settlementAccountRef": "merchant_bank_transfer_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "wire transfer",
                        "amountCents": 8000,
                        "destinationType": "bank_account",
                        "destinationRef": "wire_destination_001",
                        "beneficiaryName": "SEO AD Inc",
                        "countryCode": "US",
                        "rail": "wire",
                        "metadata": {"statementRef": "WIRE-APR-2026"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "blocked")
            self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_METADATA_MISSING")

    def test_workspace_billing_gateway_paypal_recipient_requires_recipient_type(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_PAYPAL_URL": "https://billing-gateway.example/paypal/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_PAYPAL_TOKEN": "paypal-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "PayPal Payouts",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "PayPal Payouts", "enabled": True, "fallbackProviderName": "manual", "priority": 4}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "PayPal Payouts",
                        "settlementAccountRef": "merchant_paypal_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "PayPal Payouts",
                        "amountCents": 8000,
                        "destinationType": "recipient",
                        "destinationRef": "recipient_001",
                        "beneficiaryEmail": "merchant@example.com",
                        "metadata": {},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "blocked")
            self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_METADATA_MISSING")

    def test_workspace_billing_gateway_stripe_external_account_requires_token(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_URL": "https://billing-gateway.example/stripe/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_TOKEN": "stripe-connect-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Stripe Connect",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "Stripe Connect", "enabled": True, "fallbackProviderName": "manual", "priority": 3}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Stripe Connect",
                        "settlementAccountRef": "merchant_stripe_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "Stripe Connect",
                        "amountCents": 8000,
                        "destinationType": "external_account",
                        "destinationRef": "ba_external_001",
                        "metadata": {},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            executed_payload = executed.json()
            self.assertEqual(executed_payload["execution"]["status"], "blocked")
            self.assertEqual(executed_payload["execution"]["failureCode"], "SETTLEMENT_METADATA_MISSING")

    def test_workspace_billing_gateway_paypal_recipient_succeeds_with_recipient_type(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_PAYPAL_URL": "https://billing-gateway.example/paypal/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_PAYPAL_TOKEN": "paypal-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _PayPalRecipientResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "paypal_recipient_txn_001",
                            "providerArtifactId": "paypal_recipient_receipt_001",
                            "providerUrl": "https://billing-gateway.example/paypal/recipients/001",
                            "message": "paypal recipient payout ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _PayPalRecipientResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "PayPal Payouts",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "PayPal Payouts", "enabled": True, "fallbackProviderName": "manual", "priority": 4}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "PayPal Payouts",
                        "settlementAccountRef": "merchant_paypal_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "PayPal Payouts",
                        "amountCents": 8100,
                        "destinationType": "recipient",
                        "destinationRef": "recipient_001",
                        "beneficiaryEmail": "merchant@example.com",
                        "metadata": {"recipientType": "EMAIL"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            payload = executed.json()
            self.assertEqual(payload["execution"]["status"], "completed")
            self.assertEqual(payload["execution"]["providerName"], "paypal")
            self.assertEqual(payload["execution"]["transactionRef"], "paypal_recipient_txn_001")
            self.assertEqual(payload["execution"]["providerPayload"]["recipientType"], "EMAIL")
            self.assertEqual(response_holder.request_payload["metadata"]["recipientType"], "EMAIL")
            self.assertEqual(response_holder.request_payload["providerPayload"]["recipientType"], "EMAIL")
            self.assertEqual(response_holder.request_payload["providerPayload"]["recipientEmail"], "merchant@example.com")

    def test_workspace_billing_gateway_stripe_external_account_succeeds_with_token(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_URL": "https://billing-gateway.example/stripe/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_TOKEN": "stripe-connect-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _StripeExternalResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "stripe_external_txn_001",
                            "providerArtifactId": "stripe_external_payout_001",
                            "providerUrl": "https://billing-gateway.example/stripe/external-accounts/001",
                            "message": "stripe external payout ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _StripeExternalResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Stripe Connect",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "Stripe Connect", "enabled": True, "fallbackProviderName": "manual", "priority": 3}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Stripe Connect",
                        "settlementAccountRef": "merchant_stripe_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "Stripe Connect",
                        "amountCents": 9100,
                        "destinationType": "external_account",
                        "destinationRef": "ba_external_001",
                        "metadata": {"externalAccountToken": "btok_us_verified_001"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            payload = executed.json()
            self.assertEqual(payload["execution"]["status"], "completed")
            self.assertEqual(payload["execution"]["providerName"], "stripe")
            self.assertEqual(payload["execution"]["transactionRef"], "stripe_external_txn_001")
            self.assertEqual(payload["execution"]["providerPayload"]["externalAccountToken"], "btok_us_verified_001")
            self.assertEqual(response_holder.request_payload["metadata"]["externalAccountToken"], "btok_us_verified_001")
            self.assertEqual(response_holder.request_payload["providerPayload"]["externalAccountToken"], "btok_us_verified_001")
            self.assertEqual(response_holder.request_payload["providerPayload"]["destinationType"], "external_account")

    def test_workspace_billing_gateway_sepa_succeeds_with_iban(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_URL": "https://billing-gateway.example/bank-transfer/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_TOKEN": "bank-transfer-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _SepaResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "bank_transfer_sepa_txn_001",
                            "providerArtifactId": "bank_transfer_sepa_receipt_001",
                            "providerUrl": "https://billing-gateway.example/bank-transfer/sepa/001",
                            "message": "sepa settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _SepaResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "wire transfer",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "wire transfer", "enabled": True, "fallbackProviderName": "manual", "priority": 6}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "wire transfer",
                        "settlementAccountRef": "merchant_bank_transfer_001",
                        "settlementCurrency": "EUR",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "wire transfer",
                        "amountCents": 9900,
                        "destinationType": "bank_account",
                        "destinationRef": "sepa_destination_001",
                        "beneficiaryName": "SEO AD GmbH",
                        "countryCode": "DE",
                        "rail": "sepa",
                        "metadata": {"iban": "DE89370400440532013000"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            payload = executed.json()
            self.assertEqual(payload["execution"]["status"], "completed")
            self.assertEqual(payload["execution"]["providerName"], "bank_transfer")
            self.assertEqual(payload["execution"]["transactionRef"], "bank_transfer_sepa_txn_001")
            self.assertEqual(payload["execution"]["providerPayload"]["iban"], "DE89370400440532013000")
            self.assertEqual(response_holder.request_payload["metadata"]["iban"], "DE89370400440532013000")
            self.assertEqual(response_holder.request_payload["providerPayload"]["rail"], "sepa")
            self.assertEqual(response_holder.request_payload["providerPayload"]["iban"], "DE89370400440532013000")

    def test_workspace_billing_gateway_wire_succeeds_with_routing_number(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_URL": "https://billing-gateway.example/bank-transfer/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_BANK_TRANSFER_TOKEN": "bank-transfer-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _WireResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "bank_transfer_wire_txn_001",
                            "providerArtifactId": "bank_transfer_wire_receipt_001",
                            "providerUrl": "https://billing-gateway.example/bank-transfer/wire/001",
                            "message": "wire settlement ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _WireResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "wire transfer",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "wire transfer", "enabled": True, "fallbackProviderName": "manual", "priority": 6}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "wire transfer",
                        "settlementAccountRef": "merchant_bank_transfer_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "wire transfer",
                        "amountCents": 11100,
                        "destinationType": "bank_account",
                        "destinationRef": "wire_destination_001",
                        "beneficiaryName": "SEO AD Inc",
                        "countryCode": "US",
                        "rail": "wire",
                        "metadata": {"routingNumber": "021000021"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            payload = executed.json()
            self.assertEqual(payload["execution"]["status"], "completed")
            self.assertEqual(payload["execution"]["providerName"], "bank_transfer")
            self.assertEqual(payload["execution"]["transactionRef"], "bank_transfer_wire_txn_001")
            self.assertEqual(payload["execution"]["providerPayload"]["routingNumber"], "021000021")
            self.assertEqual(response_holder.request_payload["metadata"]["routingNumber"], "021000021")
            self.assertEqual(response_holder.request_payload["providerPayload"]["rail"], "wire")
            self.assertEqual(response_holder.request_payload["providerPayload"]["routingNumber"], "021000021")

    def test_workspace_billing_gateway_ach_succeeds_with_company_entry_description(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_ACH_URL": "https://billing-gateway.example/ach/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_ACH_TOKEN": "ach-gateway-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _AchProviderResponse:
                status = 200

                def __init__(self):
                    self.request_headers = {}
                    self.request_payload = {}

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "ach_company_txn_001",
                            "providerArtifactId": "ach_company_receipt_001",
                            "providerUrl": "https://billing-gateway.example/ach/company/001",
                            "message": "ach company payout ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            response_holder = _AchProviderResponse()

            def _mock_gateway_urlopen(request, timeout=5):
                response_holder.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                payload = getattr(request, "data", b"") or b""
                response_holder.request_payload = json.loads(payload.decode("utf-8")) if payload else {}
                return response_holder

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "ACH transfer",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "ACH transfer", "enabled": True, "fallbackProviderName": "manual", "priority": 7}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "ACH transfer",
                        "settlementAccountRef": "merchant_ach_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "ACH transfer",
                        "amountCents": 8800,
                        "destinationType": "bank_account",
                        "destinationRef": "us_ach_account_token_001",
                        "beneficiaryName": "SEO AD LLC",
                        "beneficiaryEmail": "ap@example.com",
                        "rail": "ach",
                        "countryCode": "US",
                        "metadata": {"companyEntryDescription": "VENDORPAY"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            payload = executed.json()
            self.assertEqual(payload["execution"]["status"], "completed")
            self.assertEqual(payload["execution"]["providerName"], "ach")
            self.assertEqual(payload["execution"]["transactionRef"], "ach_company_txn_001")
            self.assertEqual(payload["execution"]["providerPayload"]["companyEntryDescription"], "VENDORPAY")
            self.assertEqual(response_holder.request_payload["metadata"]["companyEntryDescription"], "VENDORPAY")
            self.assertEqual(response_holder.request_payload["providerPayload"]["rail"], "ach")
            self.assertEqual(response_holder.request_payload["providerPayload"]["companyEntryDescription"], "VENDORPAY")

    def test_workspace_billing_gateway_provider_status_report_includes_routes(self) -> None:
        with patch.dict(os.environ, {"SEO_AD_BOT_STATE_DIR": str(Path(self._tempdir.name) / "state")}, clear=False):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                response = client.get("/api/billing/gateway/providers")
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertIn("entries", payload)
                self.assertIn("gatewayReady", payload)
                self.assertIn("strictReadyCount", payload)
                provider_names = {entry["providerName"] for entry in payload["entries"]}
                self.assertTrue({"ad_network", "adsense", "gam"}.issubset(provider_names))

    def test_workspace_billing_gateway_provider_requirements_report_includes_merchant_profiles(self) -> None:
        service = self._service()
        app = create_app(service)

        with TestClient(app) as client:
            response = client.get("/api/billing/gateway/provider-requirements")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("entries", payload)
            self.assertIn("providerCount", payload)
            provider_names = {entry["providerName"] for entry in payload["entries"]}
            self.assertTrue(
                {
                    "paypal",
                    "stripe",
                    "ach",
                    "bank_transfer",
                    "wise",
                    "payoneer",
                    "airwallex",
                    "tipalti",
                    "hyperwallet",
                    "ad_network",
                    "adsense",
                    "gam",
                    "mediavine",
                    "ezoic",
                    "freestar",
                    "raptive",
                    "monumetric",
                }.issubset(provider_names)
            )
            paypal = next(entry for entry in payload["entries"] if entry["providerName"] == "paypal")
            stripe = next(entry for entry in payload["entries"] if entry["providerName"] == "stripe")
            bank_transfer = next(entry for entry in payload["entries"] if entry["providerName"] == "bank_transfer")
            self.assertTrue(paypal["conditionalRequirements"])
            self.assertEqual(paypal["conditionalRequirements"][0]["whenField"], "destinationType")
            self.assertEqual(paypal["conditionalRequirements"][0]["whenValue"], "recipient")
            self.assertIn("recipientType", paypal["conditionalRequirements"][0]["metadataFields"])
            self.assertTrue(stripe["conditionalRequirements"])
            self.assertEqual(stripe["conditionalRequirements"][0]["whenValue"], "external_account")
            self.assertIn("externalAccountToken", stripe["conditionalRequirements"][0]["metadataFields"])
            bank_transfer_conditions = {item["whenValue"]: item for item in bank_transfer["conditionalRequirements"]}
            self.assertIn("swift", bank_transfer_conditions)
            self.assertIn("swiftCode", bank_transfer_conditions["swift"]["metadataFields"])
            self.assertIn("sepa", bank_transfer_conditions)
            self.assertIn("iban", bank_transfer_conditions["sepa"]["metadataFields"])
            self.assertIn("wire", bank_transfer_conditions)
            self.assertIn("routingNumber", bank_transfer_conditions["wire"]["metadataFields"])
            tipalti = next(entry for entry in payload["entries"] if entry["providerName"] == "tipalti")
            hyperwallet = next(entry for entry in payload["entries"] if entry["providerName"] == "hyperwallet")
            self.assertIn("rail", tipalti["requiredFields"])
            self.assertIn("rail", hyperwallet["requiredFields"])
            self.assertTrue(tipalti["conditionalRequirements"])
            self.assertEqual(tipalti["conditionalRequirements"][0]["whenField"], "rail")
            self.assertEqual(tipalti["conditionalRequirements"][0]["whenValue"], "swift")
            self.assertIn("swiftCode", tipalti["conditionalRequirements"][0]["metadataFields"])
            self.assertTrue(hyperwallet["conditionalRequirements"])
            self.assertEqual(hyperwallet["conditionalRequirements"][0]["whenField"], "rail")
            self.assertEqual(hyperwallet["conditionalRequirements"][0]["whenValue"], "swift")
            self.assertIn("swiftCode", hyperwallet["conditionalRequirements"][0]["metadataFields"])
            adsense = next(entry for entry in payload["entries"] if entry["providerName"] == "adsense")
            self.assertIn("providerName", adsense["requiredFields"])
            self.assertIn("amountCents", adsense["requiredFields"])
            self.assertIn("projectId", adsense["requiredFields"])
            self.assertIn("projectId", adsense["notes"][0])

    def test_ad_network_adapter_normalizes_broader_provider_families(self) -> None:
        service = self._service()
        report = service.build_billing_gateway_provider_status_report()
        provider_names = {entry.provider_name for entry in report.entries}
        self.assertTrue(
            {
                "pubmatic",
                "seedtag",
                "gumgum",
                "sovrn",
                "sharethrough",
                "revcontent",
                "outbrain",
                "taboola",
                "yieldmo",
                "teads",
                "magnite",
                "triplelift",
                "index_exchange",
                "adform",
                "criteo",
                "undertone",
            }.issubset(provider_names)
        )
        settlement_report = service.build_billing_settlement_provider_requirements_report()
        self.assertTrue(
            {
                "pubmatic",
                "seedtag",
                "gumgum",
                "sovrn",
                "sharethrough",
                "revcontent",
                "outbrain",
                "taboola",
                "yieldmo",
                "teads",
                "magnite",
                "triplelift",
                "index_exchange",
                "adform",
                "criteo",
                "undertone",
            }.issubset({entry.provider_name for entry in settlement_report.entries})
        )

    def test_workspace_billing_settlement_history_preserves_provider_payload(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_URL": "https://billing-gateway.example/stripe/settle",
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_TOKEN": "stripe-connect-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _StripeExternalResponse:
                status = 200

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "stripe_external_txn_history_001",
                            "providerArtifactId": "stripe_external_payout_history_001",
                            "providerUrl": "https://billing-gateway.example/stripe/external-accounts/history-001",
                            "message": "stripe external payout ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_StripeExternalResponse()):
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Stripe Connect",
                        "fallbackProviderName": "manual",
                        "routes": [{"providerName": "Stripe Connect", "enabled": True, "fallbackProviderName": "manual", "priority": 3}],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Stripe Connect",
                        "settlementAccountRef": "merchant_stripe_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "Stripe Connect",
                        "amountCents": 9100,
                        "destinationType": "external_account",
                        "destinationRef": "ba_external_history_001",
                        "metadata": {"externalAccountToken": "btok_us_verified_history_001"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(executed.status_code, 200)
                history = client.get("/api/billing/settlement/history?limit=1")
            self.assertEqual(history.status_code, 200)
            payload = history.json()
            self.assertEqual(payload["entries"][0]["providerPayload"]["externalAccountToken"], "btok_us_verified_history_001")
            self.assertEqual(payload["entries"][0]["providerEndpoint"], "https://billing-gateway.example/stripe/settle")
            self.assertEqual(payload["entries"][0]["providerArtifactId"], "stripe_external_payout_history_001")

    def test_workspace_billing_gateway_failover_succeeds_on_secondary_endpoint(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_TOKEN": "stripe-connect-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)

            class _StripeSecondaryResponse:
                status = 200

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "transactionRef": "stripe_failover_txn_001",
                            "providerArtifactId": "stripe_failover_receipt_001",
                            "providerUrl": "https://billing-gateway.example/stripe/secondary/settle/001",
                            "message": "stripe failover payout ok",
                        }
                    ).encode("utf-8")

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            attempted_endpoints: list[str] = []

            def _mock_gateway_urlopen(request, timeout=5):
                endpoint = str(getattr(request, "full_url", ""))
                attempted_endpoints.append(endpoint)
                if endpoint.endswith("/primary"):
                    raise HTTPError(endpoint, 503, "service unavailable", hdrs=None, fp=None)
                return _StripeSecondaryResponse()

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Stripe Connect",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "Stripe Connect",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 3,
                                "notes": [
                                    "endpoints=https://billing-gateway.example/stripe/primary,https://billing-gateway.example/stripe/secondary",
                                ],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Stripe Connect",
                        "settlementAccountRef": "merchant_stripe_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "Stripe Connect",
                        "amountCents": 9100,
                        "destinationType": "external_account",
                        "destinationRef": "ba_external_failover_001",
                        "metadata": {"externalAccountToken": "btok_us_verified_failover_001"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            payload = executed.json()
            self.assertEqual(payload["execution"]["status"], "completed")
            self.assertEqual(payload["execution"]["providerEndpoint"], "https://billing-gateway.example/stripe/secondary")
            self.assertEqual(payload["execution"]["failureCode"], None)
            self.assertIn("gatewayFailover=true", payload["execution"]["notes"])
            self.assertEqual(attempted_endpoints, ["https://billing-gateway.example/stripe/primary", "https://billing-gateway.example/stripe/secondary"])

    def test_workspace_billing_gateway_failover_returns_last_failure_when_all_endpoints_fail(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_BILLING_GATEWAY_STRIPE_TOKEN": "stripe-connect-token",
            },
            clear=False,
        ):
            service = self._service()
            app = create_app(service)
            attempted_endpoints: list[str] = []

            def _mock_gateway_urlopen(request, timeout=5):
                endpoint = str(getattr(request, "full_url", ""))
                attempted_endpoints.append(endpoint)
                if endpoint.endswith("/primary"):
                    raise HTTPError(endpoint, 502, "bad gateway", hdrs=None, fp=None)
                raise RuntimeError("network down")

            with TestClient(app) as client, patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_gateway_urlopen):
                client.put(
                    "/api/billing/gateway",
                    json={
                        "gatewayEnabled": True,
                        "strictRouting": True,
                        "defaultProviderName": "Stripe Connect",
                        "fallbackProviderName": "manual",
                        "routes": [
                            {
                                "providerName": "Stripe Connect",
                                "enabled": True,
                                "fallbackProviderName": "manual",
                                "priority": 3,
                                "notes": [
                                    "endpoints=https://billing-gateway.example/stripe/primary,https://billing-gateway.example/stripe/secondary",
                                ],
                            }
                        ],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "Stripe Connect",
                        "settlementAccountRef": "merchant_stripe_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 500,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={
                        "dryRun": False,
                        "providerName": "Stripe Connect",
                        "amountCents": 9100,
                        "destinationType": "external_account",
                        "destinationRef": "ba_external_failover_002",
                        "metadata": {"externalAccountToken": "btok_us_verified_failover_002"},
                    },
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(executed.status_code, 200)
            payload = executed.json()
            self.assertEqual(payload["execution"]["status"], "failed")
            self.assertEqual(payload["execution"]["failureCode"], "SETTLEMENT_GATEWAY_REQUEST_FAILED")
            self.assertEqual(payload["execution"]["providerEndpoint"], "https://billing-gateway.example/stripe/secondary")
            self.assertTrue(any(str(note).startswith("attempt[1]=") for note in payload["execution"]["notes"]))
            self.assertTrue(any(str(note).startswith("attempt[2]=") for note in payload["execution"]["notes"]))
            self.assertEqual(attempted_endpoints, ["https://billing-gateway.example/stripe/primary", "https://billing-gateway.example/stripe/secondary"])

    def test_market_evidence_provider_status_report_includes_sources(self) -> None:
        service = self._service()
        app = create_app(service)

        with TestClient(app) as client:
            response = client.get("/api/market-evidence/providers")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("entries", payload)
            self.assertIn("providerCount", payload)
            self.assertIn("strictReadyCount", payload)
            providers = {entry["provider"] for entry in payload["entries"]}
            self.assertTrue({"trend", "news", "qa"}.issubset(providers))

    def test_runtime_edge_gateway_provider_status_report_includes_routes(self) -> None:
        with patch.dict(os.environ, {"SEO_AD_BOT_STATE_DIR": str(Path(self._tempdir.name) / "state")}, clear=False):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                response = client.get("/api/runtime-edge/gateway/providers?projectId=project_runtime_edge")
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertIn("entries", payload)
                self.assertIn("gatewayReady", payload)
                self.assertIn("strictReadyCount", payload)
                self.assertEqual(payload["projectId"], "project_runtime_edge")
                self.assertEqual(payload["routeCount"], 1)
                self.assertEqual(payload["entries"][0]["providerName"], "runtime_edge")
                self.assertFalse(payload["gatewayReady"])
                self.assertTrue(payload["warnings"])

    def test_workspace_billing_gateway_export_report_exposes_gateway_snippets(self) -> None:
        with patch.dict(os.environ, {"SEO_AD_BOT_STATE_DIR": str(Path(self._tempdir.name) / "state")}, clear=False):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                response = client.get("/api/billing/gateway/export?projectId=project_billing_gateway")
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["projectId"], "project_billing_gateway")
                self.assertIn("nginxSnippet", payload)
                self.assertIn("caddyfileFragment", payload)
                self.assertIn("haproxyConf", payload)
                self.assertIn("/api/billing/", payload["nginxSnippet"])
                self.assertIn("reverse_proxy", payload["caddyfileFragment"])
                self.assertIn("frontend seo_ad_billing_gateway", payload["haproxyConf"])
                self.assertIn("backend seo_ad_billing_gateway_backend", payload["haproxyConf"])
                self.assertGreaterEqual(payload["routeCount"], 1)
                self.assertGreaterEqual(payload["providerCount"], 1)

    def test_visual_farm_gateway_provider_status_report_includes_routes(self) -> None:
        with patch.dict(os.environ, {"SEO_AD_BOT_STATE_DIR": str(Path(self._tempdir.name) / "state")}, clear=False):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                response = client.get("/api/visual-farm/gateway/providers?projectId=project_visual_farm")
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertIn("entries", payload)
                self.assertIn("gatewayReady", payload)
                self.assertIn("strictReadyCount", payload)
                self.assertEqual(payload["projectId"], "project_visual_farm")
                self.assertEqual(payload["routeCount"], 1)
                self.assertEqual(payload["entries"][0]["providerName"], "visual_farm")
                self.assertFalse(payload["gatewayReady"])
                self.assertTrue(payload["warnings"])

    def test_visual_farm_export_report_exposes_gateway_snippets(self) -> None:
        with patch.dict(os.environ, {"SEO_AD_BOT_STATE_DIR": str(Path(self._tempdir.name) / "state")}, clear=False):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                response = client.get("/api/visual-farm/export?projectId=project_visual_farm")
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["projectId"], "project_visual_farm")
                self.assertIn("nginxSnippet", payload)
                self.assertIn("caddyfileFragment", payload)
                self.assertIn("haproxyConf", payload)
                self.assertIn("/api/visual-farm/", payload["nginxSnippet"])
                self.assertIn("reverse_proxy", payload["caddyfileFragment"])
                self.assertIn("frontend seo_ad_visual_farm_gateway", payload["haproxyConf"])
                self.assertIn("backend seo_ad_visual_farm_gateway_backend", payload["haproxyConf"])
                self.assertGreaterEqual(payload["routeCount"], 1)
                self.assertGreaterEqual(payload["providerCount"], 1)

    def test_workspace_billing_settlement_strict_blocks_without_real_ad_evidence(self) -> None:
        with patch.dict(os.environ, {"SEO_AD_BOT_STRICT_PROVIDERS": "true"}, clear=False):
            service = self._service()
            intake = SiteIntake(
                url="https://strict-settlement-missing.example",
                site_name="Strict Settlement Missing Ad Evidence",
                repo_url="https://github.com/example/strict-settlement-missing",
                keywords=["billing", "settlement"],
            )
            project = service.create_project(
                ProjectCreateRequest(
                    name="Strict Settlement Missing Ad Evidence",
                    intake=intake,
                )
            )
            with service.database.session() as session:
                connections = service._load_project_connections(session, project.project_id, intake)
                for connection in connections:
                    if connection.provider == ConnectorKind.ad_network:
                        connection.status = ConnectorStatus.synthetic
                        connection.details["authSource"] = "fallback"
                        connection.details["mode"] = "synthetic"
                        connection.details["fallbackReason"] = "missing provider credentials"
                        connection.provenance = ["mode=synthetic", "authSource=fallback"]
                    else:
                        connection.status = ConnectorStatus.connected
                        connection.details["authSource"] = "token"
                        connection.details["mode"] = "direct"
                        connection.provenance = ["authSource=token", "mode=direct"]
                service._persist_project_connections(session, project.project_id, connections)
            app = create_app(service)

            with TestClient(app) as client:
                updated = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "manual",
                        "settlementAccountRef": "acct_demo_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 0,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={"dryRun": False, "memo": "strict missing ad evidence", "projectId": project.project_id},
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(executed.status_code, 200)
                payload = executed.json()
                self.assertEqual(payload["execution"]["status"], "blocked")
                self.assertEqual(payload["execution"]["failureCode"], "SETTLEMENT_AD_EVIDENCE_MISSING")

    def test_workspace_billing_settlement_strict_blocks_stale_ad_evidence(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_STRICT_PROVIDERS": "true",
                "SEO_AD_BOT_PROVIDER_EVIDENCE_FRESHNESS_MINUTES": "60",
            },
            clear=False,
        ):
            service = self._service()
            intake = SiteIntake(
                url="https://strict-settlement-stale.example",
                site_name="Strict Settlement Stale Ad Evidence",
                repo_url="https://github.com/example/strict-settlement-stale",
                keywords=["billing", "settlement"],
            )
            project = service.create_project(
                ProjectCreateRequest(
                    name="Strict Settlement Stale Ad Evidence",
                    intake=intake,
                )
            )
            stale_at = datetime.now(timezone.utc) - timedelta(days=2)
            with service.database.session() as session:
                connections = service._load_project_connections(session, project.project_id, intake)
                for connection in connections:
                    connection.status = ConnectorStatus.connected
                    connection.details["authSource"] = "token"
                    connection.details["mode"] = "direct"
                    connection.provenance = ["authSource=token", "mode=direct"]
                    if connection.provider == ConnectorKind.ad_network:
                        connection.last_success_at = stale_at
                        connection.last_checked_at = stale_at
                        connection.last_synced_at = stale_at
                        connection.details["recentEvidenceAt"] = stale_at.isoformat()
                        connection.details["sourceRef"] = "ad_network:stale"
                service._persist_project_connections(session, project.project_id, connections)
            app = create_app(service)

            with TestClient(app) as client:
                updated = client.put(
                    "/api/billing",
                    json={
                        "commercialModeEnabled": True,
                        "settlementEnabled": True,
                        "settlementProviderName": "manual",
                        "settlementAccountRef": "acct_demo_001",
                        "settlementCurrency": "USD",
                        "settlementPayoutThresholdCents": 0,
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(updated.status_code, 200)
                executed = client.post(
                    "/api/billing/settlement/execute",
                    json={"dryRun": False, "memo": "strict stale ad evidence", "projectId": project.project_id},
                    headers={"X-API-Key": "dev-key"},
                )
                self.assertEqual(executed.status_code, 200)
                payload = executed.json()
                self.assertEqual(payload["execution"]["status"], "blocked")
                self.assertEqual(payload["execution"]["failureCode"], "SETTLEMENT_AD_EVIDENCE_STALE")

    def test_workspace_billing_settlement_strict_refreshes_ad_evidence_before_blocking(self) -> None:
        with patch.dict(os.environ, {"SEO_AD_BOT_STRICT_PROVIDERS": "true"}, clear=False):
            service = self._service()
            intake = SiteIntake(
                url="https://strict-settlement-refresh.example",
                site_name="Strict Settlement Refresh Ad Evidence",
                repo_url="https://github.com/example/strict-settlement-refresh",
                keywords=["billing", "settlement"],
            )
            project = service.create_project(
                ProjectCreateRequest(
                    name="Strict Settlement Refresh Ad Evidence",
                    intake=intake,
                )
            )
            stale_at = datetime.now(timezone.utc) - timedelta(days=2)
            refreshed_at = datetime.now(timezone.utc)
            refreshed_ad_connection: Optional[ProjectConnection] = None
            with service.database.session() as session:
                connections = service._load_project_connections(session, project.project_id, intake)
                for connection in connections:
                    if connection.provider == ConnectorKind.ad_network:
                        connection.status = ConnectorStatus.synthetic
                        connection.provider_mode = "fallback"
                        connection.strict_eligible = False
                        connection.blocking_reason = "fallback provider evidence"
                        connection.last_success_at = stale_at
                        connection.last_checked_at = stale_at
                        connection.last_synced_at = stale_at
                        connection.recent_evidence_at = stale_at
                        connection.recent_evidence_ref = "ad_network:stale"
                        connection.details["authSource"] = "fallback"
                        connection.details["mode"] = "synthetic"
                        connection.details["sourceRef"] = "ad_network:stale"
                        refreshed_ad_connection = connection.model_copy(
                            update={
                                "status": ConnectorStatus.connected,
                                "provider_mode": "real",
                                "strict_eligible": True,
                                "blocking_reason": None,
                                "last_success_at": refreshed_at,
                                "last_checked_at": refreshed_at,
                                "last_synced_at": refreshed_at,
                                "recent_evidence_at": refreshed_at,
                                "recent_evidence_ref": "ad_network:live",
                                "details": {
                                    **connection.details,
                                    "authSource": "token",
                                    "mode": "direct",
                                    "sourceRef": "ad_network:live",
                                },
                            }
                        )
                service._persist_project_connections(session, project.project_id, connections)
            self.assertIsNotNone(refreshed_ad_connection)
            service.update_billing_policy(
                WorkspaceBillingPolicyUpdateRequest(
                    commercial_mode_enabled=True,
                    settlement_enabled=True,
                    settlement_provider_name="manual",
                    settlement_account_ref="acct_demo_001",
                    settlement_currency="USD",
                    settlement_payout_threshold_cents=0,
                )
            )

            with patch.object(
                service,
                "refresh_project_connector",
                return_value=SimpleNamespace(connection=refreshed_ad_connection),
            ) as refresh_mock:
                executed = service.execute_workspace_billing_settlement(
                    WorkspaceBillingSettlementExecutionRequest(
                        dry_run=False,
                        provider_name="ad_network",
                        project_id=project.project_id,
                        memo="strict refresh ad evidence",
                    )
                )

            self.assertEqual(executed.execution.status, "blocked")
            self.assertNotEqual(executed.execution.failure_code, "SETTLEMENT_AD_EVIDENCE_MISSING")
            self.assertNotEqual(executed.execution.failure_code, "SETTLEMENT_AD_EVIDENCE_STALE")
            self.assertIn("adEvidenceRefresh=attempted", executed.execution.notes)
            self.assertIn("adEvidenceMode=real", executed.execution.notes)
            refresh_mock.assert_called_once_with(project.project_id, ConnectorKind.ad_network)

    def test_workspace_billing_settlement_strict_refresh_ad_evidence_failure_keeps_blocking(self) -> None:
        with patch.dict(os.environ, {"SEO_AD_BOT_STRICT_PROVIDERS": "true"}, clear=False):
            service = self._service()
            intake = SiteIntake(
                url="https://strict-settlement-refresh-fail.example",
                site_name="Strict Settlement Refresh Fail",
                repo_url="https://github.com/example/strict-settlement-refresh-fail",
                keywords=["billing", "settlement"],
            )
            project = service.create_project(
                ProjectCreateRequest(
                    name="Strict Settlement Refresh Fail",
                    intake=intake,
                )
            )
            with service.database.session() as session:
                connections = service._load_project_connections(session, project.project_id, intake)
                for connection in connections:
                    if connection.provider == ConnectorKind.ad_network:
                        connection.status = ConnectorStatus.synthetic
                        connection.provider_mode = "fallback"
                        connection.strict_eligible = False
                        connection.blocking_reason = "fallback provider evidence"
                        connection.details["authSource"] = "fallback"
                        connection.details["mode"] = "synthetic"
                service._persist_project_connections(session, project.project_id, connections)
            service.update_billing_policy(
                WorkspaceBillingPolicyUpdateRequest(
                    commercial_mode_enabled=True,
                    settlement_enabled=True,
                    settlement_provider_name="manual",
                    settlement_account_ref="acct_demo_001",
                    settlement_currency="USD",
                    settlement_payout_threshold_cents=0,
                )
            )
            with patch.object(service, "refresh_project_connector", side_effect=RuntimeError("connector refresh failed")) as refresh_mock:
                executed = service.execute_workspace_billing_settlement(
                    WorkspaceBillingSettlementExecutionRequest(
                        dry_run=False,
                        provider_name="ad_network",
                        project_id=project.project_id,
                        memo="strict refresh ad evidence failure",
                    )
                )

            self.assertEqual(executed.execution.status, "blocked")
            self.assertEqual(executed.execution.failure_code, "SETTLEMENT_AD_EVIDENCE_MISSING")
            self.assertIn("adEvidenceRefresh=failed", executed.execution.notes)
            refresh_mock.assert_called_once_with(project.project_id, ConnectorKind.ad_network)

    def test_workspace_billing_settlement_strict_blocks_manual_provider_execution(self) -> None:
        with patch.dict(os.environ, {"SEO_AD_BOT_STRICT_PROVIDERS": "true"}, clear=False):
            service = self._service()
            service.update_billing_policy(
                WorkspaceBillingPolicyUpdateRequest(
                    commercial_mode_enabled=True,
                    settlement_enabled=True,
                    settlement_provider_name="manual",
                    settlement_account_ref="acct_demo_001",
                    settlement_payout_threshold_cents=1,
                )
            )
            executed = service.execute_workspace_billing_settlement(
                WorkspaceBillingSettlementExecutionRequest(
                    dry_run=False,
                    provider_name="manual",
                    account_ref="acct_demo_001",
                    amount_cents=5000,
                    currency="USD",
                )
            )

            self.assertEqual(executed.execution.status, "blocked")
            self.assertEqual(executed.execution.failure_code, "SETTLEMENT_STRICT_PROVIDER_REQUIRED")
            self.assertIn("blocked=strict_provider_required", executed.execution.notes)

    def test_workspace_billing_settlement_ad_network_payload_contains_ad_evidence_snapshot(self) -> None:
        service = self._service()
        intake = SiteIntake(
            url="https://ad-settlement-evidence.example",
            site_name="Ad Settlement Evidence",
            repo_url="https://github.com/example/ad-settlement-evidence",
            keywords=["ads", "settlement"],
        )
        project = service.create_project(
            ProjectCreateRequest(
                name="Ad Settlement Evidence",
                intake=intake,
            )
        )
        now = datetime.now(timezone.utc)
        with service.database.session() as session:
            connections = service._load_project_connections(session, project.project_id, intake)
            for connection in connections:
                if connection.provider == ConnectorKind.ad_network:
                    connection.status = ConnectorStatus.connected
                    connection.provider_mode = "real"
                    connection.strict_eligible = True
                    connection.recent_evidence_at = now
                    connection.recent_evidence_ref = "ad_network:publisher-live"
                    connection.details.update(
                        {
                            "providerFamily": "adsense",
                            "providerName": "Google AdSense",
                            "providerRef": "pub-123456",
                            "accountId": "acct_ads_001",
                            "inventoryStatus": "ready",
                            "settlementWindow": "T+7",
                            "settlementCurrency": "USD",
                            "estimatedRevenueDaily": 44.2,
                            "settledRevenueDaily": 40.7,
                            "impressions": 12800,
                            "clicks": 132,
                            "ctr": 0.0103,
                            "fillRate": 0.64,
                            "rpm": 5.2,
                        }
                    )
            service._persist_project_connections(session, project.project_id, connections)

        executed = service.execute_workspace_billing_settlement(
            WorkspaceBillingSettlementExecutionRequest(
                dry_run=True,
                provider_name="ad_network",
                project_id=project.project_id,
                memo="ad evidence payload snapshot",
            )
        )
        self.assertEqual(executed.execution.status, "previewed")
        self.assertIn("adEvidence", executed.execution.provider_payload)
        ad_evidence = executed.execution.provider_payload["adEvidence"]
        self.assertEqual(ad_evidence["providerMode"], "real")
        self.assertEqual(ad_evidence["providerRef"], "pub-123456")
        self.assertEqual(ad_evidence["impressions"], 12800)
        self.assertEqual(ad_evidence["estimatedRevenueDaily"], 44.2)
        self.assertTrue(any("adEvidenceMetrics=" in note for note in executed.execution.notes))

    def test_workspace_experiment_api_persists_policy_and_readiness(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Experiment Hub",
                intake=SiteIntake(
                    url="https://experiment-hub.example",
                    site_name="Experiment Hub",
                    locale="en-US",
                    language="en",
                    keywords=["experiment", "rollout"],
                ),
            )
        )
        app = create_app(service)

        with TestClient(app) as client:
            fetched = client.get("/api/experiments")
            self.assertEqual(fetched.status_code, 200)
            payload = fetched.json()
            self.assertIn("policy", payload)
            self.assertIn("experiments", payload)
            self.assertIn("workspaceReady", payload)

            updated = client.put(
                "/api/experiments",
                json={
                    "experimentsEnabled": True,
                    "strictAssignment": True,
                    "defaultAssignmentStrategy": "hash",
                    "experiments": [
                        {
                            "experimentKey": "homepage-cta",
                            "enabled": True,
                            "targetSurface": "site",
                            "targetLocale": "en-US",
                            "targetProjectIds": [project.project_id],
                            "controlVariantName": "control",
                            "assignmentStrategy": "hash",
                            "primaryMetric": "click_through_rate",
                            "variants": [
                                {"variantName": "control", "allocationPercent": 50, "enabled": True, "notes": ["control variant"]},
                                {"variantName": "treatment", "allocationPercent": 50, "enabled": True, "notes": ["treatment variant"]},
                            ],
                            "notes": ["experiment smoke test"],
                        }
                    ],
                    "notes": ["workspace experiment smoke test"],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated.status_code, 200)
            updated_payload = updated.json()
            self.assertTrue(updated_payload["policy"]["experimentsEnabled"])
            self.assertTrue(updated_payload["policy"]["strictAssignment"])
            self.assertEqual(updated_payload["experimentCount"], 1)
            self.assertEqual(updated_payload["readyExperimentCount"], 1)
            self.assertEqual(updated_payload["variantCount"], 2)
            self.assertTrue(updated_payload["workspaceReady"])

            localization_updated = client.put(
                "/api/localization",
                json={
                    "localizationEnabled": True,
                    "strictLocalization": True,
                    "defaultLocaleStrategy": "subpath",
                    "clusters": [
                        {
                            "clusterKey": "experiment-hub-en",
                            "canonicalProjectId": project.project_id,
                            "projectIds": [project.project_id],
                            "supportedLocales": ["en-US", "en-GB"],
                            "primaryLocale": "en-US",
                            "localeStrategy": "path",
                            "notes": ["experiment localization smoke test"],
                        }
                    ],
                    "notes": ["workspace localization smoke test"],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(localization_updated.status_code, 200)
            localization_updated_payload = localization_updated.json()
            self.assertTrue(localization_updated_payload["policy"]["localizationEnabled"])
            self.assertEqual(localization_updated_payload["clusterCount"], 1)
            self.assertEqual(localization_updated_payload["readyClusterCount"], 1)

            assignment = client.post(
                "/api/experiments/assign",
                json={
                    "projectId": project.project_id,
                    "subjectKey": f"{project.project_id}:visitor-1",
                    "sessionKey": "session-123",
                    "targetSurface": "site",
                    "targetLocale": "en-US",
                },
            )
            self.assertEqual(assignment.status_code, 200)
            assignment_payload = assignment.json()
            self.assertEqual(assignment_payload["projectId"], project.project_id)
            self.assertEqual(assignment_payload["experimentCount"], 1)
            self.assertEqual(assignment_payload["matchedExperimentCount"], 1)
            self.assertEqual(assignment_payload["assignedExperimentCount"], 1)
            self.assertTrue(assignment_payload["assignments"][0]["eligible"])
            self.assertIn(assignment_payload["assignments"][0]["assignedVariantName"], {"control", "treatment"})

            bundle = service.run_analysis(
                project.project_id,
                SiteIntake(
                    url="https://experiment-hub.example",
                    site_name="Experiment Hub",
                    locale="en-US",
                    language="en",
                    keywords=["experiment", "rollout"],
                ),
            )
            self.assertIsNotNone(bundle.experiment_assignment)
            assert bundle.experiment_assignment is not None
            self.assertEqual(bundle.experiment_assignment.project_id, project.project_id)
            self.assertEqual(bundle.experiment_assignment.experiment_count, 1)
            self.assertEqual(bundle.experiment_assignment.matched_experiment_count, 1)
            self.assertIn(bundle.experiment_assignment.assignments[0].experiment_key, {"homepage-cta"})

            detail = client.get(f"/api/projects/{project.project_id}")
            self.assertEqual(detail.status_code, 200)
            detail_payload = detail.json()
            self.assertIn("experimentAssignment", detail_payload)
            self.assertIn("localizationAssignment", detail_payload)
            self.assertIn("runtimeRoute", detail_payload)
            self.assertIn("experimentAssignment", detail_payload["workflow"])
            self.assertIn("localizationAssignment", detail_payload["workflow"])
            self.assertIn("runtimeRoute", detail_payload["workflow"])
            self.assertEqual(detail_payload["experimentAssignment"]["projectId"], project.project_id)
            self.assertEqual(detail_payload["workflow"]["experimentAssignment"]["experimentCount"], 1)
            self.assertEqual(detail_payload["workflow"]["experimentAssignment"]["assignedExperimentCount"], 1)
            self.assertEqual(detail_payload["localizationAssignment"]["projectId"], project.project_id)
            self.assertEqual(detail_payload["workflow"]["localizationAssignment"]["clusterCount"], 1)
            self.assertEqual(detail_payload["workflow"]["localizationAssignment"]["assignedClusterCount"], 1)
            self.assertEqual(detail_payload["runtimeRoute"]["projectId"], project.project_id)
            self.assertTrue(detail_payload["runtimeRoute"]["experimentAssignment"])
            self.assertTrue(detail_payload["runtimeRoute"]["localizationAssignment"])
            self.assertTrue(detail_payload["runtimeRoute"]["gatewayReport"])
            self.assertIn("executionMode", detail_payload["runtimeRoute"])
            self.assertIn("executionAction", detail_payload["runtimeRoute"])
            self.assertIn("executionReason", detail_payload["runtimeRoute"])
            self.assertIn("executionEntrypoint", detail_payload["runtimeRoute"])
            self.assertIn("read", detail_payload["runtimeRoute"]["resolvedProviders"])
            self.assertIn("seo", detail_payload["runtimeRoute"]["resolvedProviders"])
            self.assertIn("ad", detail_payload["runtimeRoute"]["resolvedProviders"])
            self.assertIn("deploy", detail_payload["runtimeRoute"]["resolvedProviders"])
            self.assertIn("observe", detail_payload["runtimeRoute"]["resolvedProviders"])

            runtime_route = client.post(
                f"/api/projects/{project.project_id}/runtime-route",
                json={
                    "taskId": "task-runtime-route",
                    "subjectKey": "runtime-route-subject",
                    "targetSurface": "seo",
                    "targetLocale": "en-US",
                    "host": "experiment-hub.example",
                },
            )
            self.assertEqual(runtime_route.status_code, 200)
            runtime_route_payload = runtime_route.json()
            self.assertEqual(runtime_route_payload["projectId"], project.project_id)
            self.assertEqual(runtime_route_payload["taskId"], "task-runtime-route")
            self.assertEqual(runtime_route_payload["requestPath"], f"/api/projects/{project.project_id}/runtime-route")
            self.assertEqual(runtime_route_payload["requestMethod"], "POST")
            self.assertEqual(runtime_route_payload["targetSurface"], "seo")
            self.assertEqual(runtime_route_payload["subjectKey"], "runtime-route-subject")
            self.assertIn("gatewayReport", runtime_route_payload)
            self.assertIn("experimentAssignment", runtime_route_payload)
            self.assertIn("localizationAssignment", runtime_route_payload)
            self.assertIn("executionMode", runtime_route_payload)
            self.assertIn("executionAction", runtime_route_payload)
            self.assertIn("executionReason", runtime_route_payload)
            self.assertIn("executionEntrypoint", runtime_route_payload)
            self.assertIn("gatewayRouteProviderName", runtime_route_payload)
            self.assertIn("gatewayRouteFallbackProviderName", runtime_route_payload)
            self.assertIn("gatewayRoutePriority", runtime_route_payload)
            expected_runtime_mode = "runtime" if runtime_route_payload["runtimeReady"] else "preview"
            expected_runtime_action = "serve_runtime" if runtime_route_payload["runtimeReady"] else "serve_preview"
            self.assertEqual(runtime_route_payload["executionMode"], expected_runtime_mode)
            self.assertEqual(runtime_route_payload["executionAction"], expected_runtime_action)
            self.assertTrue(runtime_route_payload["executionReason"])
            self.assertEqual(runtime_route_payload["executionEntrypoint"], f"/api/projects/{project.project_id}/runtime-route")
            self.assertEqual(runtime_route.headers["X-SEO-AD-Request-Project"], project.project_id)
            self.assertEqual(runtime_route.headers["X-SEO-AD-Request-Path"], f"/api/projects/{project.project_id}/runtime-route")
            self.assertEqual(runtime_route.headers["X-SEO-AD-Request-Method"], "POST")
            self.assertIn(runtime_route.headers["X-SEO-AD-Route-Mode"], {"runtime", "preview", "blocked"})
            self.assertIn(runtime_route.headers["X-SEO-AD-Route-Action"], {"serve_runtime", "serve_preview", "block"})
            self.assertEqual(runtime_route.headers["X-SEO-AD-Route-Entrypoint"], f"/api/projects/{project.project_id}/runtime-route")
            self.assertTrue(runtime_route.headers["X-SEO-AD-Route-Provider"])
            self.assertTrue(runtime_route.headers["X-SEO-AD-Route-Fallback-Provider"])
            self.assertTrue(runtime_route.headers["X-SEO-AD-Route-Priority"].isdigit())

            runtime_execute = client.get(
                f"/api/projects/{project.project_id}/runtime-execute",
                params={
                    "subjectKey": "runtime-route-subject",
                    "targetSurface": "seo",
                    "targetLocale": "en-US",
                    "host": "experiment-hub.example",
                },
            )
            self.assertEqual(runtime_execute.status_code, 200)
            runtime_execute_payload = runtime_execute.json()
            self.assertEqual(runtime_execute_payload["projectId"], project.project_id)
            self.assertEqual(runtime_execute_payload["requestPath"], f"/api/projects/{project.project_id}/runtime-execute")
            self.assertEqual(runtime_execute_payload["requestMethod"], "GET")
            self.assertIn(runtime_execute_payload["servedMode"], {"runtime", "preview"})
            self.assertIn(runtime_execute_payload["servedTarget"], {"deployment", "preview_artifact"})
            self.assertIn("runtimeRoute", runtime_execute_payload)
            self.assertIn("workflowStatus", runtime_execute_payload)
            self.assertTrue(runtime_execute_payload["servedArtifactRef"])
            self.assertTrue(runtime_execute_payload["servedUrl"])
            self.assertIn(runtime_execute_payload["servedResponseMode"], {"redirect", "html"})
            self.assertEqual(
                runtime_execute.headers["X-SEO-AD-Served-Mode"],
                runtime_execute_payload["servedMode"],
            )
            self.assertEqual(
                runtime_execute.headers["X-SEO-AD-Served-Target"],
                runtime_execute_payload["servedTarget"],
            )
            self.assertEqual(
                runtime_execute.headers["X-SEO-AD-Served-Response-Mode"],
                runtime_execute_payload["servedResponseMode"],
            )
            self.assertEqual(
                runtime_execute.headers["X-SEO-AD-Served-URL"],
                runtime_execute_payload["servedUrl"],
            )

            runtime_execute_redirect = client.get(
                f"/api/projects/{project.project_id}/runtime-execute",
                params={"responseMode": "redirect"},
                follow_redirects=False,
            )
            self.assertEqual(runtime_execute_redirect.status_code, 307)
            self.assertEqual(runtime_execute_redirect.headers["location"], runtime_execute_payload["servedUrl"])

            runtime_execute_render = client.get(
                f"/api/projects/{project.project_id}/runtime-execute",
                params={
                    "responseMode": "render",
                    "subjectKey": "runtime-route-subject",
                    "targetSurface": "seo",
                    "targetLocale": "en-US",
                    "host": "experiment-hub.example",
                },
            )
            self.assertEqual(runtime_execute_render.status_code, 200)
            self.assertIn("text/html", runtime_execute_render.headers["content-type"])
            self.assertIn("<", runtime_execute_render.text)

            runtime_execute_preview = client.get(
                f"/api/projects/{project.project_id}/runtime-execute/preview",
                params={
                    "subjectKey": "runtime-route-subject",
                    "targetSurface": "seo",
                    "targetLocale": "en-US",
                    "host": "experiment-hub.example",
                },
            )
            self.assertEqual(runtime_execute_preview.status_code, 200)
            self.assertIn("text/html", runtime_execute_preview.headers["content-type"])
            self.assertIn("<", runtime_execute_preview.text)

            runtime_execute_proxy_preview = client.get(
                f"/api/projects/{project.project_id}/runtime-execute",
                params={
                    "responseMode": "proxy",
                    "subjectKey": "runtime-route-subject",
                    "targetSurface": "seo",
                    "targetLocale": "en-US",
                    "host": "experiment-hub.example",
                },
            )
            self.assertEqual(runtime_execute_proxy_preview.status_code, 200)
            self.assertIn("text/html", runtime_execute_proxy_preview.headers["content-type"])
            self.assertIn("<", runtime_execute_proxy_preview.text)

            runtime_execute_strict_blocked = client.get(
                f"/api/projects/{project.project_id}/runtime-execute",
                params={
                    "enforceRuntimeReady": "true",
                    "subjectKey": "runtime-route-subject",
                    "targetSurface": "seo",
                    "targetLocale": "en-US",
                    "host": "experiment-hub.example",
                },
            )
            expected_runtime_strict_status = 200 if runtime_execute_payload["servedMode"] == "runtime" else 409
            self.assertEqual(runtime_execute_strict_blocked.status_code, expected_runtime_strict_status)

            runtime_execute_proxy_strict_blocked = client.get(
                f"/api/projects/{project.project_id}/runtime-execute/proxy-strict/content/article",
                params={
                    "subjectKey": "runtime-route-subject",
                    "targetSurface": "seo",
                    "targetLocale": "en-US",
                    "host": "experiment-hub.example",
                    "slot": "hero",
                },
            )
            self.assertIn(runtime_execute_proxy_strict_blocked.status_code, {200, 409})

            with service.database.session() as session:
                latest_task = session.scalars(
                    select(TaskRow).where(TaskRow.project_id == project.project_id).order_by(TaskRow.updated_at.desc())
                ).first()
                self.assertIsNotNone(latest_task)
                deployment_payload = dict(latest_task.deployment_json or {})
                deployment_payload["providerUrl"] = "https://runtime-proxy.example/runtime"
                deployment_payload["status"] = "deployed"
                latest_task.deployment_json = deployment_payload
                session.add(latest_task)
                session.commit()

            class _MockProxyResponse:
                status = 200
                headers = {"Content-Type": "text/html; charset=utf-8"}

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return b"<html><body>proxied runtime deployment</body></html>"

            with patch("apps.api.seo_ad_autopilot.app.urlopen", return_value=_MockProxyResponse()):
                runtime_execute_proxy_runtime = client.get(
                    f"/api/projects/{project.project_id}/runtime-execute",
                    params={
                        "responseMode": "proxy",
                        "subjectKey": "runtime-route-subject",
                        "targetSurface": "seo",
                        "targetLocale": "en-US",
                        "host": "experiment-hub.example",
                    },
                )
            self.assertEqual(runtime_execute_proxy_runtime.status_code, 200)
            self.assertIn("proxied runtime deployment", runtime_execute_proxy_runtime.text)
            self.assertEqual(
                runtime_execute_proxy_runtime.headers["X-SEO-AD-Proxied-URL"],
                "https://runtime-proxy.example/runtime",
            )

            class _MockProxyPathResponse:
                status = 200
                headers = {
                    "Content-Type": "text/html; charset=utf-8",
                    "Cache-Control": "max-age=60",
                    "X-Upstream-Route": "content/article",
                }

                def __init__(self):
                    self.request_url = ""
                    self.request_headers = {}

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return f"<html><body>{self.request_url}</body></html>".encode("utf-8")

            proxy_path_response = _MockProxyPathResponse()

            def _mock_urlopen(request, timeout=5):
                proxy_path_response.request_url = request.full_url
                proxy_path_response.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                return proxy_path_response

            with patch("apps.api.seo_ad_autopilot.app.urlopen", side_effect=_mock_urlopen):
                runtime_execute_proxy_path = client.get(
                    f"/api/projects/{project.project_id}/runtime-execute/proxy/content/article",
                    params={
                        "subjectKey": "runtime-route-subject",
                        "targetSurface": "seo",
                        "targetLocale": "en-US",
                        "host": "experiment-hub.example",
                        "slot": "hero",
                    },
                    headers={
                        "User-Agent": "SEO-AD-Proxy-Test/1.0",
                        "Authorization": "Bearer proxy-token",
                        "Cookie": "session=proxy",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                    },
                )
            self.assertEqual(runtime_execute_proxy_path.status_code, 200)
            self.assertIn(
                "https://runtime-proxy.example/runtime/content/article?subjectKey=runtime-route-subject&targetSurface=seo&targetLocale=en-US&host=experiment-hub.example&slot=hero",
                runtime_execute_proxy_path.text,
            )
            self.assertEqual(
                runtime_execute_proxy_path.headers["X-SEO-AD-Proxied-URL"],
                "https://runtime-proxy.example/runtime/content/article?subjectKey=runtime-route-subject&targetSurface=seo&targetLocale=en-US&host=experiment-hub.example&slot=hero",
            )
            self.assertEqual(runtime_execute_proxy_path.headers["Cache-Control"], "max-age=60")
            self.assertEqual(runtime_execute_proxy_path.headers["X-Upstream-Route"], "content/article")
            self.assertEqual(proxy_path_response.request_headers.get("user-agent"), "SEO-AD-Proxy-Test/1.0")
            self.assertEqual(proxy_path_response.request_headers.get("authorization"), "Bearer proxy-token")
            self.assertEqual(proxy_path_response.request_headers.get("cookie"), "session=proxy")
            self.assertEqual(proxy_path_response.request_headers.get("accept-language"), "zh-CN,zh;q=0.9")
            self.assertEqual(proxy_path_response.request_headers.get("x-forwarded-host"), "experiment-hub.example")
            self.assertEqual(proxy_path_response.request_headers.get("x-forwarded-proto"), "http")
            self.assertEqual(proxy_path_response.request_headers.get("x-forwarded-method"), "GET")
            self.assertEqual(proxy_path_response.request_headers.get("x-forwarded-path"), f"/api/projects/{project.project_id}/runtime-execute/proxy/content/article")

            with patch("apps.api.seo_ad_autopilot.app.urlopen", side_effect=_mock_urlopen):
                runtime_execute_proxy_path_forwarded = client.get(
                    f"/api/projects/{project.project_id}/runtime-execute/proxy/content/article",
                    params={
                        "subjectKey": "runtime-route-subject",
                        "targetSurface": "seo",
                        "targetLocale": "en-US",
                        "slot": "hero",
                    },
                    headers={
                        "X-Forwarded-Host": "edge.example:443, internal.gateway.local:8080",
                        "User-Agent": "SEO-AD-Proxy-Test/2.0",
                    },
                )
            self.assertEqual(runtime_execute_proxy_path_forwarded.status_code, 200)
            self.assertEqual(proxy_path_response.request_headers.get("x-forwarded-host"), "edge.example")
            self.assertEqual(proxy_path_response.request_headers.get("host"), "edge.example")
            self.assertEqual(proxy_path_response.request_headers.get("user-agent"), "SEO-AD-Proxy-Test/2.0")

            site_host = urlparse(project.url).hostname or "experiment-hub.example"
            site_execution = service.build_runtime_execution_response(
                project.project_id,
                request=RuntimeRouteRequest(
                    request_path="/content/article",
                    request_method="GET",
                    target_surface="site",
                    host=site_host,
                ),
            )
            if site_execution.deployment is None:
                site_execution = site_execution.model_copy(
                    update={
                        "deployment": DeploymentRecord(
                            deployment_id="deploy-site-dispatch",
                            task_id=site_execution.task_id,
                            mode=DeploymentMode.scheduled,
                            status="deployed",
                            artifact_ref=site_execution.served_artifact_ref or "artifact-site-dispatch",
                            release_notes=["site dispatch smoke"],
                            rollback_ready=True,
                            provider_artifact_id="provider-site-dispatch",
                            provider_url="https://runtime-proxy.example/runtime",
                        ),
                    }
                )
            else:
                site_execution = site_execution.model_copy(
                    update={
                        "deployment": site_execution.deployment.model_copy(
                            update={
                                "status": "deployed",
                                "provider_url": "https://runtime-proxy.example/runtime",
                                "provider_artifact_id": "provider-site-dispatch",
                            }
                        )
                    }
                )
            with patch.object(service, "build_runtime_execution_response", return_value=site_execution):
                with patch("apps.api.seo_ad_autopilot.app.urlopen", side_effect=_mock_urlopen):
                    site_dispatch = client.get(
                        "/content/article",
                        params={"slot": "hero"},
                        headers={
                            "Host": site_host,
                            "User-Agent": "SEO-AD-Site-Dispatch/1.0",
                        },
                    )
            self.assertEqual(site_dispatch.status_code, 200)
            self.assertEqual(site_dispatch.headers["X-SEO-AD-Site-Dispatch"], "host")
            self.assertEqual(site_dispatch.headers["X-SEO-AD-Request-Project"], project.project_id)
            self.assertEqual(site_dispatch.headers["X-SEO-AD-Request-Host"], site_host)
            self.assertIn(site_dispatch.headers["X-SEO-AD-Served-Mode"], {"runtime", "preview"})
            self.assertIn(site_dispatch.headers["X-SEO-AD-Served-Target"], {"deployment", "preview_artifact"})
            if site_dispatch.headers["X-SEO-AD-Served-Target"] == "deployment":
                self.assertEqual(
                    site_dispatch.headers["X-SEO-AD-Proxied-URL"],
                    "https://runtime-proxy.example/runtime/content/article?slot=hero",
                )
                self.assertIn("runtime-proxy.example/runtime/content/article?slot=hero", site_dispatch.text)
            else:
                self.assertIn("text/html", site_dispatch.headers["content-type"])
                self.assertIn("<", site_dispatch.text)

            with service.database.session() as session:
                proxy_audits = session.scalars(
                    select(AuditRow)
                    .where(AuditRow.project_id == project.project_id)
                    .where(AuditRow.action == "runtime.proxy.requested")
                    .order_by(AuditRow.created_at.desc())
                ).all()
            self.assertTrue(proxy_audits)
            first_proxy_audit_payload = proxy_audits[0].payload_json or {}
            self.assertEqual(first_proxy_audit_payload.get("proxyPath"), "content/article")
            self.assertTrue(str(first_proxy_audit_payload.get("proxiedUrl") or "").startswith("https://runtime-proxy.example/runtime/content/article"))
            self.assertIn("strictRuntimeReady", first_proxy_audit_payload)

            runtime_execute_proxy_strict_blocked = client.get(
                f"/api/projects/{project.project_id}/runtime-execute/proxy-strict/content/article",
                params={
                    "subjectKey": "runtime-route-subject",
                    "targetSurface": "seo",
                    "targetLocale": "en-US",
                    "host": "experiment-hub.example",
                    "slot": "hero",
                },
            )
            self.assertIn(runtime_execute_proxy_strict_blocked.status_code, {200, 409})
            with service.database.session() as session:
                blocked_proxy_audits = session.scalars(
                    select(AuditRow)
                    .where(AuditRow.project_id == project.project_id)
                    .where(AuditRow.action == "runtime.proxy.blocked")
                    .order_by(AuditRow.created_at.desc())
                ).all()
            self.assertTrue(blocked_proxy_audits)
            blocked_proxy_payload = blocked_proxy_audits[0].payload_json or {}
            self.assertIn("reason", blocked_proxy_payload)
            self.assertIn("strictRuntimeReady", blocked_proxy_payload)

            class _MockProxyPostResponse:
                status = 200
                headers = {
                    "Content-Type": "application/json; charset=utf-8",
                    "Cache-Control": "no-store",
                }

                def __init__(self):
                    self.request_url = ""
                    self.request_method = ""
                    self.request_body = b""
                    self.request_headers = {}

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    body_text = self.request_body.decode("utf-8")
                    return json.dumps(
                        {
                            "url": self.request_url,
                            "method": self.request_method,
                            "body": body_text,
                        }
                    ).encode("utf-8")

            proxy_post_response = _MockProxyPostResponse()

            def _mock_post_urlopen(request, timeout=5):
                proxy_post_response.request_url = request.full_url
                proxy_post_response.request_method = request.get_method()
                proxy_post_response.request_body = request.data or b""
                proxy_post_response.request_headers = {str(key).lower(): value for key, value in request.header_items()}
                return proxy_post_response

            with patch("apps.api.seo_ad_autopilot.app.urlopen", side_effect=_mock_post_urlopen):
                runtime_execute_proxy_post = client.post(
                    f"/api/projects/{project.project_id}/runtime-execute/proxy/forms/submit",
                    params={
                        "subjectKey": "runtime-route-subject",
                        "targetSurface": "seo",
                        "targetLocale": "en-US",
                        "host": "experiment-hub.example",
                        "slot": "form",
                    },
                    json={"email": "demo@example.com", "consent": True},
                )
            self.assertEqual(runtime_execute_proxy_post.status_code, 200)
            proxy_post_payload = runtime_execute_proxy_post.json()
            self.assertEqual(proxy_post_payload["method"], "POST")
            self.assertEqual(json.loads(proxy_post_payload["body"]), {"email": "demo@example.com", "consent": True})
            self.assertEqual(
                proxy_post_payload["url"],
                "https://runtime-proxy.example/runtime/forms/submit?subjectKey=runtime-route-subject&targetSurface=seo&targetLocale=en-US&host=experiment-hub.example&slot=form",
            )
            self.assertEqual(
                runtime_execute_proxy_post.headers["X-SEO-AD-Proxied-URL"],
                "https://runtime-proxy.example/runtime/forms/submit?subjectKey=runtime-route-subject&targetSurface=seo&targetLocale=en-US&host=experiment-hub.example&slot=form",
            )
            self.assertEqual(runtime_execute_proxy_post.headers["Cache-Control"], "no-store")
            self.assertTrue(str(proxy_post_response.request_headers.get("content-type") or "").startswith("application/json"))
            self.assertEqual(proxy_post_response.request_headers.get("authorization"), None)
            self.assertEqual(proxy_post_response.request_headers.get("x-forwarded-method"), "POST")
            self.assertEqual(proxy_post_response.request_headers.get("x-forwarded-path"), f"/api/projects/{project.project_id}/runtime-execute/proxy/forms/submit")

            with patch("apps.api.seo_ad_autopilot.app.urlopen", side_effect=_mock_urlopen):
                runtime_execute_proxy_strict_ready = client.get(
                    f"/api/projects/{project.project_id}/runtime-execute/proxy-strict/content/article",
                    params={
                        "subjectKey": "runtime-route-subject",
                        "targetSurface": "seo",
                        "targetLocale": "en-US",
                        "host": "experiment-hub.example",
                        "slot": "hero",
                    },
                )
            self.assertIn(runtime_execute_proxy_strict_ready.status_code, {200, 409})
            if runtime_execute_proxy_strict_ready.status_code == 200:
                self.assertIn(
                    "https://runtime-proxy.example/runtime/content/article?subjectKey=runtime-route-subject&targetSurface=seo&targetLocale=en-US&host=experiment-hub.example&slot=hero",
                    runtime_execute_proxy_strict_ready.text,
                )

            runs = client.get(f"/api/projects/{project.project_id}/runs")
            self.assertEqual(runs.status_code, 200)
            runs_payload = runs.json()
            self.assertTrue(runs_payload)
            self.assertEqual(runs_payload[0]["runtimeRouteRequestPath"], f"/api/projects/{project.project_id}/sync")
            self.assertEqual(runs_payload[0]["runtimeRouteRequestMethod"], "POST")
            self.assertIn(runs_payload[0]["runtimeRouteExecutionMode"], {"runtime", "preview", "blocked"})
            self.assertIn("gatewayRouteProviderName", runs_payload[0])
            self.assertIn("gatewayRouteFallbackProviderName", runs_payload[0])
            self.assertIn("gatewayRoutePriority", runs_payload[0])
            self.assertIn(runs_payload[0]["runtimeRouteExecutionAction"], {"serve_runtime", "serve_preview", "block"})
            self.assertTrue(runs_payload[0]["runtimeRouteExecutionReason"])
            self.assertEqual(runs_payload[0]["runtimeRouteExecutionEntrypoint"], f"/api/projects/{project.project_id}/sync")

            detail_after_runtime = client.get(f"/api/projects/{project.project_id}")
            self.assertEqual(detail_after_runtime.status_code, 200)
            detail_after_runtime_payload = detail_after_runtime.json()
            self.assertTrue(
                any(item["action"] == "runtime.route.previewed" for item in detail_after_runtime_payload["audits"])
            )
            self.assertTrue(
                any(item["action"] == "runtime.route.resolved" for item in detail_after_runtime_payload["audits"])
            )

            runtime_route_health = client.get("/api/runtime-route/health")
            self.assertEqual(runtime_route_health.status_code, 200)
            runtime_route_health_payload = runtime_route_health.json()
            self.assertIsNone(runtime_route_health_payload["projectId"])
            runtime_route_health_item = runtime_route_health_payload["items"][0]
            self.assertEqual(runtime_route_health_payload["projectCount"], 1)
            self.assertEqual(runtime_route_health_payload["items"][0]["projectId"], project.project_id)
            self.assertEqual(
                runtime_route_health_payload["runtimeReadyCount"] + runtime_route_health_payload["previewOnlyCount"],
                runtime_route_health_payload["projectCount"],
            )
            self.assertEqual(
                runtime_route_health_payload["runtimeReadyCount"],
                1 if runtime_route_health_item["runtimeReady"] else 0,
            )
            self.assertEqual(
                runtime_route_health_payload["previewOnlyCount"],
                0 if runtime_route_health_item["runtimeReady"] else 1,
            )
            self.assertEqual(
                runtime_route_health_payload["gatewayReadyCount"],
                1 if runtime_route_health_item["gatewayReady"] else 0,
            )
            self.assertEqual(
                runtime_route_health_payload["strictReadyCount"],
                1 if runtime_route_health_item["runtimeReady"] and runtime_route_health_item["gatewayReady"] else 0,
            )
            self.assertEqual(runtime_route_health_item["requestPath"], f"/api/projects/{project.project_id}/sync")
            self.assertEqual(runtime_route_health_item["requestMethod"], "POST")

            filtered_runtime_route_health = client.get(f"/api/runtime-route/health?projectId={project.project_id}")
            self.assertEqual(filtered_runtime_route_health.status_code, 200)
            filtered_runtime_route_health_payload = filtered_runtime_route_health.json()
            self.assertEqual(filtered_runtime_route_health_payload["projectId"], project.project_id)
            self.assertEqual(filtered_runtime_route_health_payload["projectCount"], 1)
            self.assertEqual(filtered_runtime_route_health_payload["items"][0]["projectId"], project.project_id)
            self.assertEqual(
                filtered_runtime_route_health_payload["runtimeReadyCount"] + filtered_runtime_route_health_payload["previewOnlyCount"],
                1,
            )

            runtime_route_history = client.get(f"/api/projects/{project.project_id}/runtime-route/history?limit=5")
            self.assertEqual(runtime_route_history.status_code, 200)
            runtime_route_history_payload = runtime_route_history.json()
            self.assertEqual(runtime_route_history_payload["projectId"], project.project_id)
            self.assertGreaterEqual(runtime_route_history_payload["total"], 1)
            self.assertTrue(runtime_route_history_payload["entries"])
            self.assertEqual(
                runtime_route_history_payload["entries"][0]["runtimeRouteRequestPath"],
                f"/api/projects/{project.project_id}/sync",
            )
            self.assertEqual(runtime_route_history_payload["entries"][0]["runtimeRouteRequestMethod"], "POST")

            workspace_runtime_route_history = client.get("/api/runtime-route/history?limit=5")
            self.assertEqual(workspace_runtime_route_history.status_code, 200)
            workspace_runtime_route_history_payload = workspace_runtime_route_history.json()
            self.assertIsNone(workspace_runtime_route_history_payload["projectId"])
            self.assertGreaterEqual(workspace_runtime_route_history_payload["total"], 1)
            self.assertTrue(workspace_runtime_route_history_payload["items"])
            self.assertEqual(workspace_runtime_route_history_payload["items"][0]["projectId"], project.project_id)
            self.assertEqual(
                workspace_runtime_route_history_payload["items"][0]["requestPath"],
                f"/api/projects/{project.project_id}/sync",
            )
            self.assertTrue(workspace_runtime_route_history_payload["items"][0]["executionReason"])

            runtime_edge_project = client.get(f"/api/projects/{project.project_id}/runtime-edge/config")
            self.assertEqual(runtime_edge_project.status_code, 200)
            runtime_edge_project_payload = runtime_edge_project.json()
            self.assertEqual(runtime_edge_project_payload["projectId"], project.project_id)
            self.assertTrue(runtime_edge_project_payload["edgeProxyUrl"].endswith(f"/api/projects/{project.project_id}/runtime-execute/proxy"))
            self.assertTrue(
                runtime_edge_project_payload["edgeProxyStrictUrl"].endswith(
                    f"/api/projects/{project.project_id}/runtime-execute/proxy-strict"
                )
            )
            self.assertTrue(runtime_edge_project_payload["edgeHealthUrl"].endswith(f"/api/runtime-route/health?projectId={project.project_id}"))
            self.assertEqual(runtime_edge_project_payload["edgeMode"], "proxy")
            self.assertEqual(runtime_edge_project_payload["publicPath"], "/")
            self.assertTrue(runtime_edge_project_payload["proxyPath"].endswith("/runtime-execute/proxy"))
            self.assertTrue(runtime_edge_project_payload["strictProxyPath"].endswith("/runtime-execute/proxy-strict"))
            self.assertIn("rewrite", runtime_edge_project_payload["rewriteRule"])
            self.assertTrue(runtime_edge_project_payload["upstreamHost"])
            self.assertIn("/runtime-execute/proxy", runtime_edge_project_payload["nginxSnippet"])
            self.assertIn("reverse_proxy", runtime_edge_project_payload["caddySnippet"])
            self.assertIn("enforceRuntimeReadyDefault", runtime_edge_project_payload)
            self.assertIn(
                runtime_edge_project_payload["executionAction"],
                {"serve_runtime", "serve_preview", "block"},
            )

            runtime_edge_workspace = client.get("/api/runtime-edge/routes")
            self.assertEqual(runtime_edge_workspace.status_code, 200)
            runtime_edge_workspace_payload = runtime_edge_workspace.json()
            self.assertGreaterEqual(runtime_edge_workspace_payload["projectCount"], 1)
            self.assertTrue(runtime_edge_workspace_payload["items"])
            self.assertEqual(runtime_edge_workspace_payload["items"][0]["projectId"], project.project_id)
            self.assertEqual(runtime_edge_workspace_payload["edgeMode"], "proxy")

            runtime_edge_workspace_filtered = client.get(f"/api/runtime-edge/routes?projectId={project.project_id}")
            self.assertEqual(runtime_edge_workspace_filtered.status_code, 200)
            runtime_edge_workspace_filtered_payload = runtime_edge_workspace_filtered.json()
            self.assertEqual(runtime_edge_workspace_filtered_payload["projectCount"], 1)
            self.assertEqual(runtime_edge_workspace_filtered_payload["items"][0]["projectId"], project.project_id)

            runtime_edge_map = client.get("/api/runtime-edge/map")
            self.assertEqual(runtime_edge_map.status_code, 200)
            runtime_edge_map_payload = runtime_edge_map.json()
            self.assertGreaterEqual(runtime_edge_map_payload["projectCount"], 1)
            self.assertGreaterEqual(runtime_edge_map_payload["hostCount"], 1)
            self.assertTrue(runtime_edge_map_payload["items"])
            self.assertEqual(runtime_edge_map_payload["items"][0]["projectId"], project.project_id)
            self.assertEqual(runtime_edge_map_payload["items"][0]["routeMode"], "default")
            self.assertTrue(runtime_edge_map_payload["items"][0]["proxyUrl"].endswith("/runtime-execute/proxy"))
            self.assertEqual(runtime_edge_map_payload["items"][0]["publicPath"], "/")
            self.assertTrue(runtime_edge_map_payload["items"][0]["proxyPath"].endswith("/runtime-execute/proxy"))
            self.assertTrue(runtime_edge_map_payload["items"][0]["strictProxyPath"].endswith("/runtime-execute/proxy-strict"))
            self.assertIn("rewrite", runtime_edge_map_payload["items"][0]["rewriteRule"])
            self.assertTrue(runtime_edge_map_payload["items"][0]["upstreamHost"])

            runtime_edge_map_strict = client.get("/api/runtime-edge/map?strictRoutesOnly=true")
            self.assertEqual(runtime_edge_map_strict.status_code, 200)
            runtime_edge_map_strict_payload = runtime_edge_map_strict.json()
            self.assertTrue(runtime_edge_map_strict_payload["strictRoutesOnly"])
            self.assertTrue(runtime_edge_map_strict_payload["items"][0]["proxyUrl"].endswith("/runtime-execute/proxy-strict"))
            self.assertEqual(runtime_edge_map_strict_payload["items"][0]["routeMode"], "strict")
            self.assertTrue(runtime_edge_map_strict_payload["items"][0]["strictProxyPath"].endswith("/runtime-execute/proxy-strict"))

            runtime_edge_export = client.get("/api/runtime-edge/export")
            self.assertEqual(runtime_edge_export.status_code, 200)
            runtime_edge_export_payload = runtime_edge_export.json()
            self.assertEqual(runtime_edge_export_payload["projectId"], None)
            self.assertIn("map $host $seo_ad_runtime_proxy", runtime_edge_export_payload["nginxMapConf"])
            self.assertIn(project.project_id, runtime_edge_export_payload["nginxMapConf"])
            self.assertIn("rewrite * /api/projects/", runtime_edge_export_payload["caddyfileFragment"])
            self.assertIn("reverse_proxy", runtime_edge_export_payload["caddyfileFragment"])
            self.assertIn("frontend seo_ad_runtime_edge", runtime_edge_export_payload["haproxyConf"])
            self.assertIn("backend seo_ad_runtime_edge_backend", runtime_edge_export_payload["haproxyConf"])
            self.assertGreaterEqual(runtime_edge_export_payload["hostCount"], 1)

            runtime_edge_export_project = client.get(f"/api/runtime-edge/export?projectId={project.project_id}")
            self.assertEqual(runtime_edge_export_project.status_code, 200)
            runtime_edge_export_project_payload = runtime_edge_export_project.json()
            self.assertEqual(runtime_edge_export_project_payload["projectId"], project.project_id)

            runtime_edge_export_strict = client.get("/api/runtime-edge/export?strictRoutesOnly=true")
            self.assertEqual(runtime_edge_export_strict.status_code, 200)
            runtime_edge_export_strict_payload = runtime_edge_export_strict.json()
            self.assertTrue(runtime_edge_export_strict_payload["strictRoutesOnly"])
            self.assertIn("/runtime-execute/proxy-strict", runtime_edge_export_strict_payload["nginxMapConf"])
            self.assertIn("frontend seo_ad_runtime_edge", runtime_edge_export_strict_payload["haproxyConf"])

            runtime_edge_validate = client.get("/api/runtime-edge/validate")
            self.assertEqual(runtime_edge_validate.status_code, 200)
            runtime_edge_validate_payload = runtime_edge_validate.json()
            self.assertIn("passed", runtime_edge_validate_payload)
            self.assertIn("blockers", runtime_edge_validate_payload)

            runtime_edge_validate_strict = client.get("/api/runtime-edge/validate?strictRoutesOnly=true")
            self.assertEqual(runtime_edge_validate_strict.status_code, 200)
            runtime_edge_validate_strict_payload = runtime_edge_validate_strict.json()
            self.assertTrue(runtime_edge_validate_strict_payload["strictRoutesOnly"])

            runtime_edge_validate_project = client.get(f"/api/runtime-edge/validate?projectId={project.project_id}")
            self.assertEqual(runtime_edge_validate_project.status_code, 200)
            runtime_edge_validate_project_payload = runtime_edge_validate_project.json()
            self.assertEqual(runtime_edge_validate_project_payload["projectId"], project.project_id)

            runtime_edge_rollout_plan = client.get("/api/runtime-edge/rollout-plan")
            self.assertEqual(runtime_edge_rollout_plan.status_code, 200)
            runtime_edge_rollout_plan_payload = runtime_edge_rollout_plan.json()
            self.assertIn("stages", runtime_edge_rollout_plan_payload)
            self.assertEqual(len(runtime_edge_rollout_plan_payload["stages"]), 3)
            self.assertEqual(runtime_edge_rollout_plan_payload["stages"][0]["stageId"], "validate")
            self.assertEqual(runtime_edge_rollout_plan_payload["stages"][1]["stageId"], "canary")
            self.assertEqual(runtime_edge_rollout_plan_payload["stages"][2]["stageId"], "full")
            self.assertGreaterEqual(runtime_edge_rollout_plan_payload["canaryPercent"], 1)

            runtime_edge_rollout_plan_project = client.get(
                f"/api/runtime-edge/rollout-plan?projectId={project.project_id}"
            )
            self.assertEqual(runtime_edge_rollout_plan_project.status_code, 200)
            runtime_edge_rollout_plan_project_payload = runtime_edge_rollout_plan_project.json()
            self.assertEqual(runtime_edge_rollout_plan_project_payload["projectId"], project.project_id)

            runtime_edge_rollout_plan_strict = client.get(
                "/api/runtime-edge/rollout-plan?strictRoutesOnly=true&canaryPercent=30"
            )
            self.assertEqual(runtime_edge_rollout_plan_strict.status_code, 200)
            runtime_edge_rollout_plan_strict_payload = runtime_edge_rollout_plan_strict.json()
            self.assertTrue(runtime_edge_rollout_plan_strict_payload["strictRoutesOnly"])
            self.assertEqual(runtime_edge_rollout_plan_strict_payload["canaryPercent"], 30)

            runtime_edge_rollout_history_project = client.get(
                f"/api/runtime-edge/rollout/history?projectId={project.project_id}"
            )
            self.assertEqual(runtime_edge_rollout_history_project.status_code, 200)
            self.assertEqual(runtime_edge_rollout_history_project.json()["projectId"], project.project_id)

            runtime_edge_rollout_remediations_project = client.get(
                f"/api/runtime-edge/rollout/remediations?projectId={project.project_id}"
            )
            self.assertEqual(runtime_edge_rollout_remediations_project.status_code, 200)
            self.assertEqual(runtime_edge_rollout_remediations_project.json()["projectId"], project.project_id)

            runtime_edge_probe_history_project = client.get(
                f"/api/runtime-edge/probe/history?projectId={project.project_id}"
            )
            self.assertEqual(runtime_edge_probe_history_project.status_code, 200)
            self.assertEqual(runtime_edge_probe_history_project.json()["projectId"], project.project_id)

            rollout_execute_blocked = client.post(
                "/api/runtime-edge/rollout/execute",
                json={
                    "stageId": "validate",
                    "strictRoutesOnly": False,
                    "dryRun": True,
                    "actor": "qa",
                },
            )
            self.assertEqual(rollout_execute_blocked.status_code, 401)

            rollout_execute = client.post(
                "/api/runtime-edge/rollout/execute",
                json={
                    "stageId": "validate",
                    "strictRoutesOnly": False,
                    "dryRun": True,
                    "actor": "qa",
                    "note": "runtime edge rollout dry-run",
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(rollout_execute.status_code, 200)
            rollout_execute_payload = rollout_execute.json()
            self.assertEqual(rollout_execute_payload["status"], "planned")
            self.assertEqual(rollout_execute_payload["stageId"], "validate")
            self.assertTrue(rollout_execute_payload["dryRun"])
            self.assertIn("executionId", rollout_execute_payload)

            rollout_execute_live = client.post(
                "/api/runtime-edge/rollout/execute",
                json={
                    "stageId": "canary",
                    "strictRoutesOnly": True,
                    "canaryPercent": 30,
                    "dryRun": False,
                    "actor": "qa",
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(rollout_execute_live.status_code, 200)
            rollout_execute_live_payload = rollout_execute_live.json()
            self.assertIn(rollout_execute_live_payload["status"], {"executed", "blocked"})
            self.assertEqual(rollout_execute_live_payload["stageId"], "canary")
            self.assertFalse(rollout_execute_live_payload["dryRun"])

            rollout_history = client.get("/api/runtime-edge/rollout/history?limit=5")
            self.assertEqual(rollout_history.status_code, 200)
            rollout_history_payload = rollout_history.json()
            self.assertGreaterEqual(rollout_history_payload["total"], 1)
            self.assertEqual(rollout_history_payload["summary"]["totalCount"], len(rollout_history_payload["items"]))
            self.assertTrue(rollout_history_payload["items"])
            self.assertIn(rollout_history_payload["items"][0]["status"], {"planned", "blocked", "executed"})

            rollout_history_stage = client.get("/api/runtime-edge/rollout/history", params={"limit": 5, "stageId": "validate"})
            self.assertEqual(rollout_history_stage.status_code, 200)
            rollout_history_stage_payload = rollout_history_stage.json()
            self.assertTrue(rollout_history_stage_payload["items"])
            self.assertTrue(all(item["stageId"] == "validate" for item in rollout_history_stage_payload["items"]))

            rollout_history_status = client.get("/api/runtime-edge/rollout/history", params={"limit": 5, "status": "planned"})
            self.assertEqual(rollout_history_status.status_code, 200)
            rollout_history_status_payload = rollout_history_status.json()
            self.assertTrue(all(item["status"] == "planned" for item in rollout_history_status_payload["items"]))

            rollout_history_strict = client.get(
                "/api/runtime-edge/rollout/history",
                params={"limit": 5, "strictRoutesOnly": "true"},
            )
            self.assertEqual(rollout_history_strict.status_code, 200)
            rollout_history_strict_payload = rollout_history_strict.json()
            self.assertTrue(all(item["strictRoutesOnly"] for item in rollout_history_strict_payload["items"]))

            rollout_remediations = client.get("/api/runtime-edge/rollout/remediations")
            self.assertEqual(rollout_remediations.status_code, 200)
            rollout_remediations_payload = rollout_remediations.json()
            self.assertIn("items", rollout_remediations_payload)
            self.assertIn("blockerCount", rollout_remediations_payload)

            rollout_remediations_strict = client.get(
                "/api/runtime-edge/rollout/remediations",
                params={"strictRoutesOnly": "true"},
            )
            self.assertEqual(rollout_remediations_strict.status_code, 200)
            rollout_remediations_strict_payload = rollout_remediations_strict.json()
            self.assertTrue(rollout_remediations_strict_payload["strictRoutesOnly"])

            probe_blocked = client.post(
                "/api/runtime-edge/probe",
                json={"strictRoutesOnly": True, "timeoutSeconds": 1.5, "actor": "qa"},
            )
            self.assertEqual(probe_blocked.status_code, 401)

            class _MockProbeResponse:
                status = 200
                headers = {"Content-Type": "application/json"}

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return b"{}"

            with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_MockProbeResponse()):
                probe_ok = client.post(
                    "/api/runtime-edge/probe",
                    json={"strictRoutesOnly": False, "timeoutSeconds": 1.5, "actor": "qa"},
                    headers={"X-API-Key": "dev-key"},
                )
            self.assertEqual(probe_ok.status_code, 200)
            probe_ok_payload = probe_ok.json()
            self.assertIn("probeId", probe_ok_payload)
            self.assertGreaterEqual(probe_ok_payload["total"], 1)
            self.assertGreaterEqual(probe_ok_payload["connected"], 1)

            probe_history = client.get("/api/runtime-edge/probe/history?limit=5")
            self.assertEqual(probe_history.status_code, 200)
            probe_history_payload = probe_history.json()
            self.assertGreaterEqual(probe_history_payload["total"], 1)
            self.assertEqual(probe_history_payload["summary"]["totalCount"], len(probe_history_payload["items"]))
            self.assertTrue(probe_history_payload["items"])

            probe_history_strict = client.get("/api/runtime-edge/probe/history", params={"strictRoutesOnly": "false"})
            self.assertEqual(probe_history_strict.status_code, 200)
            probe_history_strict_payload = probe_history_strict.json()
            self.assertTrue(all(item["strictRoutesOnly"] is False for item in probe_history_strict_payload["items"]))

            second_project = service.create_project(
                ProjectCreateRequest(
                    name="Second Route Project",
                    intake=SiteIntake(
                        url="https://second-route.example",
                        site_name="Second Route Project",
                        keywords=["route", "replay"],
                    ),
                )
            )
            service.run_analysis(
                second_project.project_id,
                SiteIntake(
                    url="https://second-route.example",
                    site_name="Second Route Project",
                    keywords=["route", "replay"],
                ),
            )

            filtered_workspace_runtime_route_history = client.get(
                f"/api/runtime-route/history?limit=5&projectId={project.project_id}"
            )
            self.assertEqual(filtered_workspace_runtime_route_history.status_code, 200)
            filtered_workspace_runtime_route_history_payload = filtered_workspace_runtime_route_history.json()
            self.assertEqual(filtered_workspace_runtime_route_history_payload["projectId"], project.project_id)
            self.assertGreaterEqual(filtered_workspace_runtime_route_history_payload["total"], 1)
            self.assertTrue(filtered_workspace_runtime_route_history_payload["items"])
            self.assertTrue(
                all(item["projectId"] == project.project_id for item in filtered_workspace_runtime_route_history_payload["items"])
            )

    def test_runtime_execute_blocks_when_request_chain_is_not_eligible(self) -> None:
        with patch.dict(
            os.environ,
            {"SEO_AD_BOT_STATE_DIR": str(Path(self._tempdir.name) / "blocked-runtime-state")},
            clear=False,
        ):
            get_settings.cache_clear()
            service = self._service()
            project = service.create_project(
                ProjectCreateRequest(
                    name="Blocked Runtime Execute",
                    intake=SiteIntake(
                        url="https://blocked-runtime.example",
                        site_name="Blocked Runtime Execute",
                        locale="en-US",
                        language="en",
                        keywords=["blocked", "runtime"],
                    ),
                )
            )
            service.run_analysis(
                project.project_id,
                SiteIntake(
                    url="https://blocked-runtime.example",
                    site_name="Blocked Runtime Execute",
                    locale="en-US",
                    language="en",
                    keywords=["blocked", "runtime"],
                ),
            )
            app = create_app(service)

            with TestClient(app) as client:
                client.put(
                    "/api/experiments",
                    json={
                        "experimentsEnabled": False,
                        "strictAssignment": True,
                        "experiments": [],
                        "notes": ["blocked runtime execute test"],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/localization",
                    json={
                        "localizationEnabled": False,
                        "strictLocalization": True,
                        "clusters": [],
                        "notes": ["blocked runtime execute test"],
                    },
                    headers={"X-API-Key": "dev-key"},
                )
                client.put(
                    "/api/model-gateway",
                    json={
                        "gatewayEnabled": False,
                        "strictRouting": True,
                        "routes": [],
                        "notes": ["blocked runtime execute test"],
                    },
                    headers={"X-API-Key": "dev-key"},
                )

                runtime_execute = client.get(f"/api/projects/{project.project_id}/runtime-execute")
                self.assertEqual(runtime_execute.status_code, 409)
                runtime_execute_payload = runtime_execute.json()
                self.assertEqual(runtime_execute_payload["servedMode"], "blocked")
                self.assertEqual(runtime_execute_payload["servedTarget"], "none")
                self.assertEqual(runtime_execute_payload["statusCode"], 409)
                self.assertEqual(runtime_execute_payload["runtimeRoute"]["executionAction"], "block")
                self.assertEqual(runtime_execute.headers["X-SEO-AD-Served-Mode"], "blocked")
                self.assertEqual(runtime_execute.headers["X-SEO-AD-Served-Target"], "none")
                self.assertEqual(runtime_execute.headers["X-SEO-AD-Served-Response-Mode"], "blocked")

    def test_workspace_localization_api_persists_policy_and_readiness(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Localization Hub",
                intake=SiteIntake(
                    url="https://localization-hub.example",
                    site_name="Localization Hub",
                    locale="fr-FR",
                    language="fr",
                    keywords=["locale", "multilingual"],
                ),
            )
        )
        app = create_app(service)

        with TestClient(app) as client:
            fetched = client.get("/api/localization")
            self.assertEqual(fetched.status_code, 200)
            payload = fetched.json()
            self.assertIn("policy", payload)
            self.assertIn("clusters", payload)
            self.assertIn("workspaceReady", payload)

            updated = client.put(
                "/api/localization",
                json={
                    "localizationEnabled": True,
                    "strictLocalization": True,
                    "defaultLocale": "en-US",
                    "defaultLanguage": "en",
                    "clusters": [
                        {
                            "clusterKey": "global-site",
                            "enabled": True,
                            "canonicalProjectId": project.project_id,
                            "projectIds": [project.project_id],
                            "supportedLocales": ["en-US", "fr-FR"],
                            "primaryLocale": "en-US",
                            "localeStrategy": "path",
                            "notes": ["localized rollout"],
                        }
                    ],
                    "notes": ["workspace localization smoke test"],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated.status_code, 200)
            updated_payload = updated.json()
            self.assertTrue(updated_payload["policy"]["localizationEnabled"])
            self.assertTrue(updated_payload["policy"]["strictLocalization"])
            self.assertEqual(updated_payload["clusterCount"], 1)
            self.assertEqual(updated_payload["readyClusterCount"], 1)
            self.assertEqual(updated_payload["projectCount"], 1)
            self.assertEqual(updated_payload["localeCount"], 2)
            self.assertTrue(updated_payload["workspaceReady"])

            assignment = client.post(
                "/api/localization/assign",
                json={
                    "projectId": project.project_id,
                    "targetLocale": "fr-FR",
                    "host": "localization-hub.example",
                    "subjectKey": f"{project.project_id}:locale-page",
                },
            )
            self.assertEqual(assignment.status_code, 200)
            assignment_payload = assignment.json()
            self.assertEqual(assignment_payload["projectId"], project.project_id)
            self.assertEqual(assignment_payload["clusterCount"], 1)
            self.assertEqual(assignment_payload["matchedClusterCount"], 1)
            self.assertEqual(assignment_payload["assignedClusterCount"], 1)
            self.assertTrue(assignment_payload["assignments"][0]["clusterReady"])
            self.assertEqual(assignment_payload["assignments"][0]["routePrefix"], "/fr-FR")

    def test_workspace_runtime_route_health_report_aggregates_ready_and_preview_projects(self) -> None:
        service = self._service()
        ready_project = service.create_project(
            ProjectCreateRequest(
                name="Runtime Ready",
                intake=SiteIntake(
                    url="https://runtime-ready.example",
                    site_name="Runtime Ready",
                    locale="en-US",
                    language="en",
                    keywords=["runtime", "routing"],
                ),
            )
        )
        preview_project = service.create_project(
            ProjectCreateRequest(
                name="Preview Only",
                intake=SiteIntake(
                    url="https://preview-only.example",
                    site_name="Preview Only",
                    locale="en-US",
                    language="en",
                    keywords=["preview", "routing"],
                ),
            )
        )
        app = create_app(service)

        with TestClient(app) as client:
            exp_updated = client.put(
                "/api/experiments",
                json={
                    "experimentsEnabled": True,
                    "strictAssignment": True,
                    "defaultAssignmentStrategy": "hash",
                    "experiments": [
                        {
                            "experimentKey": "runtime-route-test",
                            "enabled": True,
                            "targetSurface": "site",
                            "targetLocale": "en-US",
                            "targetProjectIds": [ready_project.project_id],
                            "controlVariantName": "control",
                            "assignmentStrategy": "hash",
                            "primaryMetric": "click_through_rate",
                            "variants": [
                                {"variantName": "control", "allocationPercent": 50, "enabled": True},
                                {"variantName": "treatment", "allocationPercent": 50, "enabled": True},
                            ],
                        }
                    ],
                    "notes": ["runtime route smoke test"],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(exp_updated.status_code, 200)

            loc_updated = client.put(
                "/api/localization",
                json={
                    "localizationEnabled": True,
                    "strictLocalization": True,
                    "defaultLocale": "en-US",
                    "defaultLanguage": "en",
                    "clusters": [
                        {
                            "clusterKey": "runtime-route-cluster",
                            "enabled": True,
                            "canonicalProjectId": ready_project.project_id,
                            "projectIds": [ready_project.project_id],
                            "supportedLocales": ["en-US", "fr-FR"],
                            "primaryLocale": "en-US",
                            "localeStrategy": "path",
                            "notes": ["runtime route smoke test"],
                        }
                    ],
                    "notes": ["runtime route smoke test"],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(loc_updated.status_code, 200)

            gateway_updated = client.put(
                "/api/model-gateway",
                json={
                    "gatewayEnabled": True,
                    "defaultProviderName": "openai",
                    "fallbackProviderName": "local",
                    "strictRouting": True,
                    "routes": [
                        {"routeSuite": "read", "providerName": "openai", "fallbackProviderName": "local", "enabled": True, "priority": 10},
                        {"routeSuite": "seo", "providerName": "openai", "fallbackProviderName": "local", "enabled": True, "priority": 20},
                        {"routeSuite": "ad", "providerName": "openai", "fallbackProviderName": "local", "enabled": True, "priority": 30},
                        {"routeSuite": "deploy", "providerName": "openai", "fallbackProviderName": "local", "enabled": True, "priority": 40},
                        {"routeSuite": "observe", "providerName": "openai", "fallbackProviderName": "local", "enabled": True, "priority": 50},
                    ],
                    "notes": ["runtime route smoke test"],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(gateway_updated.status_code, 200)

        service.run_analysis(
            ready_project.project_id,
            SiteIntake(
                url="https://runtime-ready.example",
                site_name="Runtime Ready",
                locale="en-US",
                language="en",
                keywords=["runtime", "routing"],
            ),
        )
        service.run_analysis(
            preview_project.project_id,
            SiteIntake(
                url="https://preview-only.example",
                site_name="Preview Only",
                locale="en-US",
                language="en",
                keywords=["preview", "routing"],
            ),
        )

        report = service.build_workspace_runtime_route_health_report()
        item_by_project = {item.project_id: item for item in report.items}

        self.assertEqual(report.project_count, 2)
        self.assertEqual(report.runtime_ready_count, 1)
        self.assertEqual(report.preview_only_count, 1)
        self.assertEqual(report.gateway_ready_count, 2)
        self.assertEqual(report.strict_ready_count, 1)
        self.assertIn(ready_project.project_id, report.ready_project_ids)
        self.assertIn(preview_project.project_id, report.preview_only_project_ids)
        self.assertTrue(item_by_project[ready_project.project_id].runtime_ready)
        self.assertTrue(item_by_project[ready_project.project_id].gateway_ready)
        self.assertFalse(item_by_project[preview_project.project_id].runtime_ready)
        self.assertTrue(item_by_project[preview_project.project_id].gateway_ready)

    def test_workspace_template_market_api_persists_policy_and_readiness(self) -> None:
        service = self._service()
        app = create_app(service)
        project = service.create_project(
            ProjectCreateRequest(
                name="Template Hub",
                intake=SiteIntake(
                    url="https://template-hub.example",
                    site_name="Template Hub",
                    locale="en-US",
                    language="en",
                    keywords=["template", "market", "content"],
                ),
            )
        )

        with TestClient(app) as client:
            fetched = client.get("/api/template-market")
            self.assertEqual(fetched.status_code, 200)
            payload = fetched.json()
            self.assertIsNone(payload["projectId"])
            self.assertIn("policy", payload)
            self.assertIn("templates", payload)
            self.assertIn("workspaceReady", payload)

            fetched_project = client.get(f"/api/template-market?projectId={project.project_id}")
            self.assertEqual(fetched_project.status_code, 200)
            self.assertEqual(fetched_project.json()["projectId"], project.project_id)

            updated = client.put(
                "/api/template-market",
                json={
                    "marketEnabled": True,
                    "strictMarket": True,
                    "defaultTemplateSurface": "content",
                    "templates": [
                        {
                            "templateKey": "content-hub",
                            "enabled": True,
                            "templateSurface": "content",
                            "targetLocale": "en-US",
                            "targetProjectIds": [project.project_id],
                            "coverageRequirements": [f"project_name:{project.name}", "locale:en-US"],
                            "templateSource": "workspace",
                            "notes": ["template market smoke test"],
                        }
                    ],
                    "notes": ["workspace template market smoke test"],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated.status_code, 200)
            updated_payload = updated.json()
            self.assertTrue(updated_payload["policy"]["marketEnabled"])
            self.assertTrue(updated_payload["policy"]["strictMarket"])
            self.assertEqual(updated_payload["templateCount"], 1)
            self.assertEqual(updated_payload["readyTemplateCount"], 1)
            self.assertEqual(updated_payload["projectScopeCount"], 1)
            self.assertTrue(updated_payload["workspaceReady"])

            experiments = client.get("/api/experiments")
            self.assertEqual(experiments.status_code, 200)
            self.assertIsNone(experiments.json()["projectId"])
            experiments_project = client.get(f"/api/experiments?projectId={project.project_id}")
            self.assertEqual(experiments_project.status_code, 200)
            self.assertEqual(experiments_project.json()["projectId"], project.project_id)

            localization = client.get("/api/localization")
            self.assertEqual(localization.status_code, 200)
            self.assertIsNone(localization.json()["projectId"])
            localization_project = client.get(f"/api/localization?projectId={project.project_id}")
            self.assertEqual(localization_project.status_code, 200)
            self.assertEqual(localization_project.json()["projectId"], project.project_id)

    def test_workspace_model_gateway_api_persists_routing_policy(self) -> None:
        os.environ["SEO_AD_BOT_MODEL_GATEWAY_URL"] = "https://model-gateway-api.example/publish"
        os.environ["SEO_AD_BOT_MODEL_GATEWAY_ACCESS_TOKEN"] = "model-gateway-token"
        service = self._service()
        app = create_app(service)

        with TestClient(app) as client:
            fetched = client.get("/api/model-gateway")
            self.assertEqual(fetched.status_code, 200)
            payload = fetched.json()
            self.assertIn("policy", payload)
            self.assertIn("routes", payload)
            self.assertIn(payload["policy"]["defaultProviderName"], {"local", "openai", "anthropic", "mock"})

            updated = client.put(
                "/api/model-gateway",
                json={
                    "gatewayEnabled": True,
                    "defaultProviderName": "openai",
                    "fallbackProviderName": "local",
                    "strictRouting": True,
                    "routes": [
                        {"routeSuite": "read", "providerName": "openai", "enabled": True, "fallbackProviderName": "local", "priority": 10, "notes": ["read route"]},
                        {"routeSuite": "seo", "providerName": "anthropic", "enabled": True, "fallbackProviderName": "local", "priority": 20, "notes": ["seo route"]},
                        {"routeSuite": "ad", "providerName": "openai", "enabled": True, "fallbackProviderName": "local", "priority": 30, "notes": ["ad route"]},
                        {"routeSuite": "deploy", "providerName": "openai", "enabled": True, "fallbackProviderName": "local", "priority": 40, "notes": ["deploy route"]},
                        {"routeSuite": "observe", "providerName": "openai", "enabled": True, "fallbackProviderName": "local", "priority": 50, "notes": ["observe route"]},
                    ],
                    "notes": ["model gateway smoke test"],
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(updated.status_code, 200)
            updated_payload = updated.json()
            self.assertTrue(updated_payload["policy"]["gatewayEnabled"])
            self.assertTrue(updated_payload["policy"]["strictRouting"])
            self.assertEqual(updated_payload["routeCount"], 5)
            self.assertEqual(updated_payload["suiteCount"], 5)
            self.assertEqual(updated_payload["routeReadyCount"], 5)
            self.assertTrue(updated_payload["gatewayReady"])

            class _GatewayResponse:
                status = 200

                def __enter__(self) -> "_GatewayResponse":
                    return self

                def __exit__(self, exc_type, exc, tb) -> bool:
                    return False

                def read(self) -> bytes:
                    return json.dumps(
                        {
                            "artifactId": "model-gateway-api-artifact-001",
                            "artifactUrl": "https://model-gateway-api.example/artifact/001",
                        }
                    ).encode("utf-8")

            blocked_publish = client.post("/api/model-gateway/publish")
            self.assertEqual(blocked_publish.status_code, 401)
            with patch("apps.api.seo_ad_autopilot.service.urlopen", return_value=_GatewayResponse()):
                published = client.post("/api/model-gateway/publish", headers={"X-API-Key": "dev-key"})
            self.assertEqual(published.status_code, 200)
            published_payload = published.json()
            self.assertIsNotNone(published_payload["gatewayPublish"])
            self.assertEqual(published_payload["gatewayPublish"]["status"], "completed")
            self.assertEqual(published_payload["gatewayPublish"]["gatewayArtifactId"], "model-gateway-api-artifact-001")

    def test_workspace_model_gateway_provider_status_report_includes_routes(self) -> None:
        with patch.dict(os.environ, {"SEO_AD_BOT_STATE_DIR": str(Path(self._tempdir.name) / "state")}, clear=False):
            service = self._service()
            app = create_app(service)

            with TestClient(app) as client:
                response = client.get("/api/model-gateway/providers")
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertIn("entries", payload)
                self.assertIn("gatewayReady", payload)
                self.assertIn("strictReadyCount", payload)
                route_suites = {entry["routeSuite"] for entry in payload["entries"]}
                self.assertTrue({"read", "seo", "ad", "deploy", "observe"}.issubset(route_suites))

    def test_workspace_model_gateway_publish_failover_succeeds_on_secondary_endpoint(self) -> None:
        os.environ.pop("SEO_AD_BOT_MODEL_GATEWAY_URL", None)
        os.environ["SEO_AD_BOT_MODEL_GATEWAY_URLS"] = (
            "https://model-gateway-primary.example/publish,"
            "https://model-gateway-secondary.example/publish"
        )
        os.environ["SEO_AD_BOT_MODEL_GATEWAY_ACCESS_TOKEN"] = "model-gateway-token"
        service = self._service()
        gateway_report = service.build_workspace_model_gateway_report()

        class _GatewayResponse:
            status = 200

            def __enter__(self) -> "_GatewayResponse":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "artifactId": "model_gateway_artifact_failover_001",
                        "artifactUrl": "https://model-gateway-secondary.example/artifact/001",
                        "message": "model gateway publish failover ok",
                    }
                ).encode("utf-8")

        request_urls: list[str] = []

        def _mock_urlopen(request, timeout=5):
            request_urls.append(str(request.full_url))
            if "primary" in str(request.full_url):
                raise HTTPError(str(request.full_url), 502, "Bad Gateway", hdrs=None, fp=None)
            return _GatewayResponse()

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
            publish = service._execute_model_gateway_policy_publish(gateway_report)

        self.assertEqual(publish.status, "completed")
        self.assertEqual(publish.gateway_endpoint, "https://model-gateway-secondary.example/publish")
        self.assertEqual(publish.gateway_artifact_id, "model_gateway_artifact_failover_001")
        self.assertIn("https://model-gateway-primary.example/publish", request_urls)
        self.assertIn("https://model-gateway-secondary.example/publish", request_urls)
        self.assertTrue(any("attemptFailed=https://model-gateway-primary.example/publish:http_502" in note for note in publish.notes))

    def test_workspace_model_gateway_publish_failover_returns_last_failure_when_all_endpoints_fail(self) -> None:
        os.environ.pop("SEO_AD_BOT_MODEL_GATEWAY_URL", None)
        os.environ["SEO_AD_BOT_MODEL_GATEWAY_URLS"] = (
            "https://model-gateway-fail-a.example/publish,"
            "https://model-gateway-fail-b.example/publish"
        )
        os.environ["SEO_AD_BOT_MODEL_GATEWAY_ACCESS_TOKEN"] = "model-gateway-token"
        service = self._service()
        gateway_report = service.build_workspace_model_gateway_report()

        def _mock_urlopen(request, timeout=5):
            if "fail-a" in str(request.full_url):
                raise HTTPError(str(request.full_url), 503, "Service Unavailable", hdrs=None, fp=None)
            raise HTTPError(str(request.full_url), 429, "Too Many Requests", hdrs=None, fp=None)

        with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
            publish = service._execute_model_gateway_policy_publish(gateway_report)

        self.assertEqual(publish.status, "failed")
        self.assertEqual(publish.failure_code, "MODEL_GATEWAY_HTTP_429")
        self.assertFalse(publish.retryable)
        self.assertEqual(publish.gateway_endpoint, "https://model-gateway-fail-b.example/publish")
        self.assertTrue(any("attemptedEndpointCount=2" in note for note in publish.notes))

    def test_alert_preset_strict_admin_key(self) -> None:
        os.environ["SEO_AD_BOT_ALERT_PRESET_ADMIN_KEYS"] = "admin-key"
        os.environ["SEO_AD_BOT_ALERT_PRESET_STRICT_ADMIN"] = "true"
        service = self._service()
        app = create_app(service)
        payload = {
            "presets": [
                {
                    "presetId": "strict_test",
                    "name": "strict_test",
                    "description": "strict mode test",
                    "projectIds": [],
                    "categories": ["auth"],
                    "severities": [],
                    "providers": [],
                    "blocking": True,
                    "updatedAt": "2026-01-01T00:00:00Z",
                }
            ]
        }
        with TestClient(app) as client:
            blocked = client.put("/api/alerts/presets", json=payload, headers={"X-API-Key": "dev-key"})
            self.assertEqual(blocked.status_code, 403)

            allowed = client.put("/api/alerts/presets", json=payload, headers={"X-API-Key": "admin-key"})
            self.assertEqual(allowed.status_code, 200)
            self.assertTrue(any(item["presetId"] == "strict_test" for item in allowed.json()["presets"]))

    def test_alert_preset_validation_invalid_id_returns_422(self) -> None:
        service = self._service()
        app = create_app(service)
        payload = {
            "presets": [
                {
                    "presetId": "Invalid Space",
                    "name": "invalid_space",
                    "description": "invalid id test",
                    "projectIds": [],
                    "categories": ["auth"],
                    "severities": [],
                    "providers": [],
                    "blocking": True,
                    "updatedAt": "2026-01-01T00:00:00Z",
                }
            ]
        }
        with TestClient(app) as client:
            response = client.put("/api/alerts/presets", json=payload, headers={"X-API-Key": "dev-key"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("Invalid presetId", response.json()["detail"])

    def test_alert_preset_validation_duplicate_name_returns_422(self) -> None:
        service = self._service()
        app = create_app(service)
        payload = {
            "presets": [
                {
                    "presetId": "dup_name_1",
                    "name": "dup_name",
                    "description": "duplicate name test 1",
                    "projectIds": [],
                    "categories": ["auth"],
                    "severities": [],
                    "providers": [],
                    "blocking": True,
                    "updatedAt": "2026-01-01T00:00:00Z",
                },
                {
                    "presetId": "dup_name_2",
                    "name": "DUP_NAME",
                    "description": "duplicate name test 2",
                    "projectIds": [],
                    "categories": ["config"],
                    "severities": [],
                    "providers": [],
                    "blocking": True,
                    "updatedAt": "2026-01-01T00:00:00Z",
                },
            ]
        }
        with TestClient(app) as client:
            response = client.put("/api/alerts/presets", json=payload, headers={"X-API-Key": "dev-key"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("Duplicate preset name", response.json()["detail"])

    def test_strict_providers_blocks_deploy_without_market_providers(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Block",
                intake=SiteIntake(
                    url="https://strict-block.example",
                    site_name="Strict Block",
                    brand_whitelist=["Strict"],
                    keywords=["seo", "growth"],
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://strict-block.example",
                site_name="Strict Block",
                brand_whitelist=["Strict"],
                keywords=["seo", "growth"],
            ),
        )
        analysis_runs = service.list_project_runs(project.project_id)
        self.assertTrue(analysis_runs)
        self.assertEqual(analysis_runs[0].status.value, "failed")
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "failed")
        self.assertEqual(approved.deployment.failure_code, "STRICT_PROVIDER_BLOCKED")
        self.assertGreaterEqual(len(approved.deployment.strict_blockers), 1)
        self.assertTrue(all("provider" in item for item in approved.deployment.strict_blockers))
        runs = service.list_project_runs(project.project_id)
        self.assertTrue(runs)
        self.assertEqual(runs[0].status.value, "failed")
        connections = service.get_project_connections(project.project_id)
        self.assertEqual(connections.state.last_run_status, "failed")

    def test_strict_providers_allows_deploy_with_connected_market_providers(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend.json"
        news_path = Path(self._tempdir.name) / "news.json"
        qa_path = Path(self._tempdir.name) / "qa.json"
        search_console_path = Path(self._tempdir.name) / "search-console.json"
        ga4_path = Path(self._tempdir.name) / "ga4.json"
        trend_path.write_text(json.dumps({"id": "trend-1", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-1", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-1", "questions": ["what is seo"]}), encoding="utf-8")
        search_console_path.write_text(
            json.dumps(
                {
                    "rows": [
                        {"keys": ["seo strategy"], "clicks": 120, "impressions": 1800},
                        {"keys": ["growth plan"], "clicks": 88, "impressions": 1320},
                    ]
                }
            ),
            encoding="utf-8",
        )
        ga4_path.write_text(
            json.dumps(
                {
                    "rows": [
                        {"metricValues": [{"value": "4200"}, {"value": "64"}, {"value": "0.72"}]},
                        {"metricValues": [{"value": "3800"}, {"value": "51"}, {"value": "0.69"}]},
                    ]
                }
            ),
            encoding="utf-8",
        )

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Allow",
                intake=SiteIntake(
                    url="https://strict-allow.example",
                    site_name="Strict Allow",
                    brand_whitelist=["Strict"],
                    keywords=["seo", "growth"],
                    search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
                    ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "123456"},
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://strict-allow.example",
                site_name="Strict Allow",
                brand_whitelist=["Strict"],
                keywords=["seo", "growth"],
                search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
                ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "123456"},
            ),
        )
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "deployed")
        self.assertNotEqual(approved.deployment.failure_code, "STRICT_PROVIDER_BLOCKED")

    def test_market_provider_supports_credentials_json_auth_header(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SEO_AD_BOT_TREND_PROVIDER_URL": "https://market-provider.example/trend",
                "SEO_AD_BOT_NEWS_PROVIDER_URL": "",
                "SEO_AD_BOT_QA_PROVIDER_URL": "",
                "SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN": "",
                "SEO_AD_BOT_TREND_PROVIDER_CREDENTIALS_JSON": json.dumps(
                    {"accessToken": "trend-json-token", "authHeader": "X-Trend-Token"}
                ),
            },
            clear=False,
        ):
            get_settings.cache_clear()
            service = self._service()
            seen_headers: list[dict[str, str]] = []

            class _MockResponse:
                def __enter__(self) -> "_MockResponse":
                    return self

                def __exit__(self, exc_type, exc, tb) -> bool:
                    return False

                def read(self) -> bytes:
                    return b'{"id":"trend-json-1","topics":["seo"]}'

            def _mock_urlopen(request, timeout=0):  # type: ignore[no-untyped-def]
                seen_headers.append({str(key).lower(): str(value) for key, value in request.header_items()})
                return _MockResponse()

            with patch("apps.api.seo_ad_autopilot.service.urlopen", side_effect=_mock_urlopen):
                project = service.create_project(
                    ProjectCreateRequest(
                        name="Trend Credentials JSON",
                        intake=SiteIntake(
                            url="https://trend-cred.example",
                            site_name="Trend Credentials JSON",
                            brand_whitelist=["Trend"],
                            keywords=["seo", "growth"],
                        ),
                    )
                )
                bundle = service.run_analysis(
                    project.project_id,
                    SiteIntake(
                        url="https://trend-cred.example",
                        site_name="Trend Credentials JSON",
                        brand_whitelist=["Trend"],
                        keywords=["seo", "growth"],
                    ),
                )

        trend_evidence = next(
            item for item in (bundle.ingestion_report.evidence or []) if item.provider == ConnectorKind.trend
        )
        self.assertEqual(trend_evidence.status, ConnectorStatus.connected)
        self.assertEqual(trend_evidence.auth_source, "settings:provider:credentialsJson:json")
        self.assertTrue(seen_headers)
        self.assertEqual(seen_headers[0].get("x-trend-token"), "Bearer trend-json-token")
        self.assertNotIn("authorization", seen_headers[0])

    def test_strict_visual_gate_blocks_deploy_when_visual_run_has_failures(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-visual-block.json"
        news_path = Path(self._tempdir.name) / "news-visual-block.json"
        qa_path = Path(self._tempdir.name) / "qa-visual-block.json"
        search_console_path = Path(self._tempdir.name) / "search-console-visual-block.json"
        ga4_path = Path(self._tempdir.name) / "ga4-visual-block.json"
        trend_path.write_text(json.dumps({"id": "trend-visual-block", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-visual-block", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-visual-block", "questions": ["what is seo"]}), encoding="utf-8")
        search_console_path.write_text(json.dumps({"rows": [{"keys": ["visual block"], "clicks": 52, "impressions": 780}]}), encoding="utf-8")
        ga4_path.write_text(json.dumps({"rows": [{"metricValues": [{"value": "1800"}, {"value": "21"}, {"value": "0.63"}]}]}), encoding="utf-8")
        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()

        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Visual Block",
                intake=SiteIntake(
                    url="https://strict-visual-block.example",
                    site_name="Strict Visual Block",
                    brand_whitelist=["Strict"],
                    keywords=["seo", "growth"],
                    search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
                    ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "111222"},
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://strict-visual-block.example",
                site_name="Strict Visual Block",
                brand_whitelist=["Strict"],
                keywords=["seo", "growth"],
                search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
                ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "111222"},
            ),
        )
        failing_case = VisualRegressionCase(
            sample_id="strict-visual-block-1",
            name="Strict Visual Block",
            page_url="https://strict-visual-block.example",
            project_id=project.project_id,
            baseline_label="baseline",
            preview_label="preview",
            expected_max_diff_percent=1.0,
            actual_diff_percent=4.8,
            artifact_ref="artifact://visual/strict-block-1",
            task_id=bundle.task.task_id,
            cta_preserved=False,
            layout_shift_risk="high",
            passed=False,
            provider_status="failed",
            provider_failure_code="VISUAL_FARM_HTTP_ERROR",
            visual_farm_strict_blocked=True,
        )
        failing_run = VisualRegressionRun(
            run_id="strict_visual_run_block_1",
            sample_count=1,
            pass_count=0,
            fail_count=1,
            average_diff_percent=4.8,
            strict_mode=True,
            failed_case_count=1,
            strict_blocked_case_count=1,
            cases=[failing_case],
        )
        with service.database.session() as session:
            session.add(
                AuditRow(
                    id="audit_strict_visual_block_probe",
                    project_id="workspace",
                    task_id="",
                    action="visual_farm.probe.executed",
                    actor="system",
                    payload_json={
                        "strictMode": True,
                        "configuredEndpointCount": 1,
                        "probedEndpointCount": 1,
                        "connectedCount": 1,
                        "failedCount": 0,
                        "notConfiguredCount": 0,
                        "blockingCount": 0,
                        "recoverableCount": 0,
                        "accessTokenConfigured": True,
                        "timeoutMs": 12000,
                        "probes": [],
                        "notes": [],
                    },
                    created_at=datetime.now(timezone.utc),
                )
            )
        with patch.object(service, "build_visual_regression_runs_report", return_value=VisualRegressionRunsReport(runs=[failing_run])):
            approved = service.approve_task(
                bundle.task.task_id,
                ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-visual-test"),
            )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "failed")
        self.assertEqual(approved.deployment.failure_code, "STRICT_PROVIDER_BLOCKED")
        providers = {str(item.get("provider") or "") for item in approved.deployment.strict_blockers}
        self.assertIn("visual_farm", providers)

    def test_strict_visual_gate_allows_deploy_when_visual_run_is_clean(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-visual-allow.json"
        news_path = Path(self._tempdir.name) / "news-visual-allow.json"
        qa_path = Path(self._tempdir.name) / "qa-visual-allow.json"
        search_console_path = Path(self._tempdir.name) / "search-console-visual-allow.json"
        ga4_path = Path(self._tempdir.name) / "ga4-visual-allow.json"
        trend_path.write_text(json.dumps({"id": "trend-visual-allow", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-visual-allow", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-visual-allow", "questions": ["what is seo"]}), encoding="utf-8")
        search_console_path.write_text(json.dumps({"rows": [{"keys": ["visual allow"], "clicks": 74, "impressions": 920}]}), encoding="utf-8")
        ga4_path.write_text(json.dumps({"rows": [{"metricValues": [{"value": "2600"}, {"value": "29"}, {"value": "0.67"}]}]}), encoding="utf-8")
        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()

        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Visual Allow",
                intake=SiteIntake(
                    url="https://strict-visual-allow.example",
                    site_name="Strict Visual Allow",
                    brand_whitelist=["Strict"],
                    keywords=["seo", "growth"],
                    search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
                    ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "333444"},
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://strict-visual-allow.example",
                site_name="Strict Visual Allow",
                brand_whitelist=["Strict"],
                keywords=["seo", "growth"],
                search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
                ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "333444"},
            ),
        )
        clean_case = VisualRegressionCase(
            sample_id="strict-visual-allow-1",
            name="Strict Visual Allow",
            page_url="https://strict-visual-allow.example",
            project_id=project.project_id,
            baseline_label="baseline",
            preview_label="preview",
            expected_max_diff_percent=1.5,
            actual_diff_percent=0.8,
            artifact_ref="artifact://visual/strict-allow-1",
            task_id=bundle.task.task_id,
            cta_preserved=True,
            layout_shift_risk="low",
            passed=True,
            provider_status="connected",
            visual_farm_strict_blocked=False,
        )
        clean_run = VisualRegressionRun(
            run_id="strict_visual_run_allow_1",
            sample_count=1,
            pass_count=1,
            fail_count=0,
            average_diff_percent=0.8,
            strict_mode=True,
            cases=[clean_case],
        )
        with service.database.session() as session:
            session.add(
                AuditRow(
                    id="audit_strict_visual_allow_probe",
                    project_id="workspace",
                    task_id="",
                    action="visual_farm.probe.executed",
                    actor="system",
                    payload_json={
                        "strictMode": True,
                        "configuredEndpointCount": 1,
                        "probedEndpointCount": 1,
                        "connectedCount": 1,
                        "failedCount": 0,
                        "notConfiguredCount": 0,
                        "blockingCount": 0,
                        "recoverableCount": 0,
                        "accessTokenConfigured": True,
                        "timeoutMs": 12000,
                        "probes": [],
                        "notes": [],
                    },
                    created_at=datetime.now(timezone.utc),
                )
            )
        with patch.object(service, "build_visual_regression_runs_report", return_value=VisualRegressionRunsReport(runs=[clean_run])):
            approved = service.approve_task(
                bundle.task.task_id,
                ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-visual-test"),
            )
        self.assertIsNotNone(approved.deployment)
        self.assertNotEqual(approved.deployment.failure_code, "STRICT_PROVIDER_BLOCKED")
        providers = {str(item.get("provider") or "") for item in approved.deployment.strict_blockers}
        self.assertNotIn("visual_farm", providers)

    def test_strict_runtime_route_ready_blocks_deploy_without_runtime_edge_probe(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-runtime-edge.json"
        news_path = Path(self._tempdir.name) / "news-runtime-edge.json"
        qa_path = Path(self._tempdir.name) / "qa-runtime-edge.json"
        search_console_path = Path(self._tempdir.name) / "search-console-runtime-edge.json"
        ga4_path = Path(self._tempdir.name) / "ga4-runtime-edge.json"
        trend_path.write_text(json.dumps({"id": "trend-runtime-edge", "topics": ["runtime"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-runtime-edge", "headlines": ["runtime update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-runtime-edge", "questions": ["what is runtime"]}), encoding="utf-8")
        search_console_path.write_text(json.dumps({"rows": [{"keys": ["runtime edge"], "clicks": 41, "impressions": 640}]}), encoding="utf-8")
        ga4_path.write_text(json.dumps({"rows": [{"metricValues": [{"value": "1400"}, {"value": "17"}, {"value": "0.61"}]}]}), encoding="utf-8")
        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()

        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Runtime Edge Block",
                intake=SiteIntake(
                    url="https://strict-runtime-edge-block.example",
                    site_name="Strict Runtime Edge Block",
                    brand_whitelist=["Strict"],
                    keywords=["runtime", "edge"],
                    search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
                    ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "777888"},
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://strict-runtime-edge-block.example",
                site_name="Strict Runtime Edge Block",
                brand_whitelist=["Strict"],
                keywords=["runtime", "edge"],
                search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
                ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "777888"},
            ),
        )
        with service.database.session() as session:
            row = session.get(TaskRow, bundle.task.task_id)
            assert row is not None
            row.risk_score = 50
            analysis_json = dict(row.analysis_json or {})
            runtime_route = dict(analysis_json.get("runtimeRoute") or {})
            runtime_route["runtimeReady"] = True
            runtime_route["executionMode"] = "runtime"
            runtime_route["executionAction"] = "serve_runtime"
            runtime_route["executionReason"] = "runtime-ready for edge probe test"
            analysis_json["runtimeRoute"] = runtime_route
            analysis_json["runtimeRouteSummary"] = "runtimeRouteReady=true|experimentVariant=unassigned|localizationCluster=unassigned|gateway=local|gatewayRouteProvider=n/a|gatewayRouteFallbackProvider=n/a|gatewayRoutePriority=n/a"
            row.analysis_json = analysis_json
            session.add(row)

        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-runtime-edge-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "failed")
        self.assertEqual(approved.deployment.failure_code, "STRICT_PROVIDER_BLOCKED")
        providers = {str(item.get("provider") or "") for item in approved.deployment.strict_blockers}
        self.assertIn("runtime_edge_probe", providers)

    def test_strict_visual_gate_blocks_when_probe_is_stale(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_VISUAL_FARM_STRICT"] = "true"
        os.environ["SEO_AD_BOT_VISUAL_FARM_PROBE_FRESHNESS_MINUTES"] = "30"
        trend_path = Path(self._tempdir.name) / "trend-visual-stale.json"
        news_path = Path(self._tempdir.name) / "news-visual-stale.json"
        qa_path = Path(self._tempdir.name) / "qa-visual-stale.json"
        search_console_path = Path(self._tempdir.name) / "search-console-visual-stale.json"
        ga4_path = Path(self._tempdir.name) / "ga4-visual-stale.json"
        trend_path.write_text(json.dumps({"id": "trend-visual-stale", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-visual-stale", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-visual-stale", "questions": ["what is seo"]}), encoding="utf-8")
        search_console_path.write_text(json.dumps({"rows": [{"keys": ["visual stale"], "clicks": 74, "impressions": 920}]}), encoding="utf-8")
        ga4_path.write_text(json.dumps({"rows": [{"metricValues": [{"value": "2600"}, {"value": "29"}, {"value": "0.67"}]}]}), encoding="utf-8")
        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()

        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Visual Stale",
                intake=SiteIntake(
                    url="https://strict-visual-stale.example",
                    site_name="Strict Visual Stale",
                    brand_whitelist=["Strict"],
                    keywords=["seo", "growth"],
                    search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
                    ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "777888"},
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://strict-visual-stale.example",
                site_name="Strict Visual Stale",
                brand_whitelist=["Strict"],
                keywords=["seo", "growth"],
                search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
                ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "777888"},
            ),
        )
        clean_case = VisualRegressionCase(
            sample_id="strict-visual-stale-1",
            name="Strict Visual Stale",
            page_url="https://strict-visual-stale.example",
            project_id=project.project_id,
            baseline_label="baseline",
            preview_label="preview",
            expected_max_diff_percent=1.5,
            actual_diff_percent=0.8,
            artifact_ref="artifact://visual/strict-stale-1",
            task_id=bundle.task.task_id,
            cta_preserved=True,
            layout_shift_risk="low",
            passed=True,
            provider_status="connected",
            visual_farm_strict_blocked=False,
        )
        clean_run = VisualRegressionRun(
            run_id="strict_visual_run_stale_1",
            sample_count=1,
            pass_count=1,
            fail_count=0,
            average_diff_percent=0.8,
            strict_mode=True,
            cases=[clean_case],
        )
        with service.database.session() as session:
            session.add(
                AuditRow(
                    id="audit_strict_visual_stale_probe",
                    project_id="workspace",
                    task_id="",
                    action="visual_farm.probe.executed",
                    actor="system",
                    payload_json={
                        "strictMode": True,
                        "configuredEndpointCount": 1,
                        "probedEndpointCount": 1,
                        "connectedCount": 1,
                        "failedCount": 0,
                        "notConfiguredCount": 0,
                        "blockingCount": 0,
                        "recoverableCount": 0,
                        "accessTokenConfigured": True,
                        "timeoutMs": 12000,
                        "probes": [],
                        "notes": [],
                    },
                    created_at=datetime.now(timezone.utc) - timedelta(minutes=90),
                )
            )
        with patch.object(service, "build_visual_regression_runs_report", return_value=VisualRegressionRunsReport(runs=[clean_run])):
            approved = service.approve_task(
                bundle.task.task_id,
                ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-visual-test"),
            )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.failure_code, "STRICT_PROVIDER_BLOCKED")
        providers = {str(item.get("provider") or "") for item in approved.deployment.strict_blockers}
        self.assertIn("visual_farm", providers)
        self.assertTrue(any(str(item.get("failureCode") or "") == "VISUAL_FARM_PROBE_STALE" for item in approved.deployment.strict_blockers))

    def test_strict_providers_allows_multi_endpoint_market_fallback(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"
        trend_path = Path(self._tempdir.name) / "trend-alt.json"
        news_path = Path(self._tempdir.name) / "news-alt.json"
        qa_path = Path(self._tempdir.name) / "qa-alt.json"
        search_console_path = Path(self._tempdir.name) / "search-console-alt.json"
        ga4_path = Path(self._tempdir.name) / "ga4-alt.json"
        trend_path.write_text(json.dumps({"id": "trend-alt", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-alt", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-alt", "questions": ["what is seo"]}), encoding="utf-8")
        search_console_path.write_text(
            json.dumps({"rows": [{"keys": ["seo forecast"], "clicks": 95, "impressions": 1410}]}),
            encoding="utf-8",
        )
        ga4_path.write_text(
            json.dumps({"rows": [{"metricValues": [{"value": "3300"}, {"value": "37"}, {"value": "0.68"}]}]}),
            encoding="utf-8",
        )

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = f"file:///missing-trend.json,{trend_path.as_uri()}"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = f"file:///missing-news.json,{news_path.as_uri()}"
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = f"file:///missing-qa.json,{qa_path.as_uri()}"

        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Strict Multi Endpoint",
                intake=SiteIntake(
                    url="https://strict-multi.example",
                    site_name="Strict Multi Endpoint",
                    brand_whitelist=["Strict"],
                    keywords=["seo", "growth"],
                    search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
                    ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "654321"},
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://strict-multi.example",
                site_name="Strict Multi Endpoint",
                brand_whitelist=["Strict"],
                keywords=["seo", "growth"],
                search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
                ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "654321"},
            ),
        )
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "deployed")
        self.assertNotEqual(approved.deployment.failure_code, "STRICT_PROVIDER_BLOCKED")
        self.assertIsNotNone(bundle.ingestion_report)
        market_sources = [item for item in (bundle.ingestion_report.evidence if bundle.ingestion_report else []) if item.provider.value in {"trend", "news", "qa"}]
        self.assertEqual(len(market_sources), 3)
        for item in market_sources:
            self.assertIn(item.auth_source, {"settings:provider", "settings:shared", "env:SEO_AD_BOT_MARKET_PROVIDER_ACCESS_TOKEN", "env:SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN", "env:SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN", "env:SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"})
            self.assertIn("attempts", item.details)
            self.assertIn("endpointsConfigured", item.details)
            self.assertIn("endpointsTried", item.details)

    def test_strict_providers_block_when_configured_read_source_is_not_connected(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-read-check.json"
        news_path = Path(self._tempdir.name) / "news-read-check.json"
        qa_path = Path(self._tempdir.name) / "qa-read-check.json"
        trend_path.write_text(json.dumps({"id": "trend-read-check", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-read-check", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-read-check", "questions": ["what is seo"]}), encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-read-block.example",
            site_name="Strict Read Block",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
            search_console={"accessToken": "sc-token", "endpoint": "file:///missing-search-console.json"},
            ga4={"accessToken": "ga4-token", "endpoint": "file:///missing-ga4.json"},
        )
        project = service.create_project(ProjectCreateRequest(name="Strict Read Block", intake=intake))
        bundle = service.run_analysis(project.project_id, intake)
        self.assertIn("strict-blocked", " ".join(bundle.ingestion_report.notes).lower())
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-read-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "failed")
        providers = {str(item.get("provider") or "") for item in approved.deployment.strict_blockers}
        self.assertIn("search_console", providers)
        self.assertIn("ga4", providers)

    def test_strict_providers_block_when_configured_read_evidence_is_stale(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_PROVIDER_EVIDENCE_FRESHNESS_MINUTES"] = "60"
        trend_path = Path(self._tempdir.name) / "trend-read-stale.json"
        news_path = Path(self._tempdir.name) / "news-read-stale.json"
        qa_path = Path(self._tempdir.name) / "qa-read-stale.json"
        search_console_path = Path(self._tempdir.name) / "search-console-read-stale.json"
        ga4_path = Path(self._tempdir.name) / "ga4-read-stale.json"

        trend_path.write_text(json.dumps({"id": "trend-read-stale", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-read-stale", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-read-stale", "questions": ["what is seo"]}), encoding="utf-8")
        search_console_path.write_text(
            json.dumps({"rows": [{"clicks": 18, "impressions": 420, "ctr": 0.042, "position": 8.2}]}),
            encoding="utf-8",
        )
        ga4_path.write_text(
            json.dumps({"rows": [{"metricValues": [{"value": "2600"}, {"value": "24"}, {"value": "0.72"}]}]}),
            encoding="utf-8",
        )

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-read-stale.example",
            site_name="Strict Read Stale",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
            search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
            ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri()},
        )
        project = service.create_project(ProjectCreateRequest(name="Strict Read Stale", intake=intake))
        bundle = service.run_analysis(project.project_id, intake)
        self.assertIsNotNone(bundle.ingestion_report)
        stale_checked_at = datetime.now(timezone.utc) - timedelta(hours=6)
        for index, evidence in enumerate(bundle.ingestion_report.evidence):
            if evidence.provider in {ConnectorKind.search_console, ConnectorKind.ga4}:
                bundle.ingestion_report.evidence[index] = evidence.model_copy(update={"checked_at": stale_checked_at})

        blockers = service._strict_publish_blockers(bundle)  # noqa: SLF001 - strict gate verification
        stale_blockers = [
            item
            for item in blockers
            if str(item.get("failureCode") or "").endswith("_EVIDENCE_STALE")
            and str(item.get("provider") or "") in {"search_console", "ga4"}
        ]
        self.assertGreaterEqual(len(stale_blockers), 1)

    def test_strict_providers_block_when_explicit_sitemap_is_not_connected(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-sitemap-check.json"
        news_path = Path(self._tempdir.name) / "news-sitemap-check.json"
        qa_path = Path(self._tempdir.name) / "qa-sitemap-check.json"
        search_console_path = Path(self._tempdir.name) / "search-console-sitemap-check.json"
        ga4_path = Path(self._tempdir.name) / "ga4-sitemap-check.json"
        missing_sitemap_path = Path(self._tempdir.name) / "missing-explicit-sitemap.xml"

        trend_path.write_text(json.dumps({"id": "trend-sitemap-check", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-sitemap-check", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-sitemap-check", "questions": ["what is seo"]}), encoding="utf-8")
        search_console_path.write_text(
            json.dumps({"rows": [{"keys": ["seo audit"], "clicks": 18, "impressions": 300, "position": 6.1}]}),
            encoding="utf-8",
        )
        ga4_path.write_text(
            json.dumps({"rows": [{"metricValues": [{"value": "1900"}, {"value": "28"}, {"value": "0.57"}]}]}),
            encoding="utf-8",
        )

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-sitemap-block.example",
            site_name="Strict Sitemap Block",
            repo_url="https://github.com/example/strict-sitemap-block",
            sitemap_urls=[missing_sitemap_path.as_uri()],
            search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
            ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri()},
            keywords=["seo", "growth"],
            brand_whitelist=["Strict"],
        )
        project = service.create_project(ProjectCreateRequest(name="Strict Sitemap Block", intake=intake))
        bundle = service.run_analysis(project.project_id, intake)
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-sitemap-test"),
        )

        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "failed")
        providers = {str(item.get("provider") or "") for item in approved.deployment.strict_blockers}
        self.assertIn("sitemap", providers)

    def test_strict_providers_skip_disabled_read_connector_blocker(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-read-disable-check.json"
        news_path = Path(self._tempdir.name) / "news-read-disable-check.json"
        qa_path = Path(self._tempdir.name) / "qa-read-disable-check.json"
        ga4_path = Path(self._tempdir.name) / "ga4-read-disable-check.json"
        trend_path.write_text(json.dumps({"id": "trend-read-disable-check", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-read-disable-check", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-read-disable-check", "questions": ["what is seo"]}), encoding="utf-8")
        ga4_path.write_text(
            json.dumps({"rows": [{"metricValues": [{"value": "2100"}, {"value": "24"}, {"value": "0.61"}]}]}),
            encoding="utf-8",
        )

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-read-disable.example",
            site_name="Strict Read Disable",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
            ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "555111"},
        )
        project = service.create_project(ProjectCreateRequest(name="Strict Read Disable", intake=intake))

        existing = service.get_project_connections(project.project_id)
        updated_connections = []
        for connection in existing.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.search_console:
                clone.enabled = False
                clone.config = {**clone.config, "enabled": False}
            updated_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing.state.auto_cruise_enabled,
                sync_interval_minutes=existing.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )

        bundle = service.run_analysis(project.project_id, intake)
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-read-disable-test"),
        )
        self.assertIsNotNone(approved.deployment)
        providers = {str(item.get("provider") or "") for item in approved.deployment.strict_blockers}
        self.assertNotIn("search_console", providers)

    def test_strict_providers_block_when_playwright_is_configured_but_not_connected(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_ENABLE_BROWSER_CRAWL"] = "true"
        search_console_path = Path(self._tempdir.name) / "search-console-playwright-check.json"
        ga4_path = Path(self._tempdir.name) / "ga4-playwright-check.json"
        trend_path = Path(self._tempdir.name) / "trend-playwright-check.json"
        news_path = Path(self._tempdir.name) / "news-playwright-check.json"
        qa_path = Path(self._tempdir.name) / "qa-playwright-check.json"
        search_console_path.write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "clicks": 12,
                            "impressions": 220,
                            "ctr": 0.0545,
                            "position": 7.8,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        ga4_path.write_text(
            json.dumps({"rows": [{"metricValues": [{"value": "2800"}, {"value": "32"}, {"value": "0.66"}]}]}),
            encoding="utf-8",
        )
        trend_path.write_text(json.dumps({"id": "trend-playwright-check", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-playwright-check", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-playwright-check", "questions": ["what is seo"]}), encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"

        diagnostics = {
            "attempts": [{"attempt": 1, "status": "error", "failureCode": "PLAYWRIGHT_TIMEOUT"}],
            "attemptCount": 1,
            "configuredRetryCount": 0,
            "timeoutMs": 7000,
            "userAgent": "SEO-AD-AutoPilot/1.0",
            "configuredUserAgents": ["SEO-AD-AutoPilot/1.0"],
            "extraHeaders": {"Accept-Language": "en-US,en;q=0.9"},
            "jitterMs": 120,
            "jsEnabled": True,
            "responseStatus": 0,
            "antiBotBlocked": False,
            "blockSignals": [],
            "failureCode": "PLAYWRIGHT_TIMEOUT",
            "fallbackReason": "navigation timeout",
        }

        service = self._service()
        intake = SiteIntake(
            url="https://strict-playwright-block.example",
            site_name="Strict Playwright Block",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
            search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
            ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri()},
        )
        project = service.create_project(ProjectCreateRequest(name="Strict Playwright Block", intake=intake))
        with patch("apps.api.seo_ad_autopilot.connectors.crawl_page_with_diagnostics", return_value=(None, diagnostics)):
            bundle = service.run_analysis(project.project_id, intake)
        blockers = service._strict_publish_blockers(bundle)  # noqa: SLF001 - intentional strict-gate verification
        providers = {str(item.get("provider") or "") for item in blockers}
        self.assertIn("playwright", providers)

    def test_strict_providers_block_when_market_evidence_is_stale(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_PROVIDER_EVIDENCE_FRESHNESS_MINUTES"] = "60"
        trend_path = Path(self._tempdir.name) / "trend-stale-check.json"
        news_path = Path(self._tempdir.name) / "news-stale-check.json"
        qa_path = Path(self._tempdir.name) / "qa-stale-check.json"
        trend_path.write_text(json.dumps({"id": "trend-stale-check", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-stale-check", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-stale-check", "questions": ["what is seo"]}), encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-market-stale.example",
            site_name="Strict Market Stale",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
        )
        project = service.create_project(ProjectCreateRequest(name="Strict Market Stale", intake=intake))
        bundle = service.run_analysis(project.project_id, intake)
        self.assertIsNotNone(bundle.ingestion_report)
        stale_at = datetime.now(timezone.utc) - timedelta(hours=6)
        for index, evidence in enumerate(bundle.ingestion_report.evidence):
            if evidence.provider in {ConnectorKind.trend, ConnectorKind.news, ConnectorKind.qa}:
                bundle.ingestion_report.evidence[index] = evidence.model_copy(update={"fetched_at": stale_at})

        blockers = service._strict_publish_blockers(bundle)  # noqa: SLF001 - intentional strict-gate verification
        stale_blockers = [
            item
            for item in blockers
            if str(item.get("failureCode") or "").endswith("_EVIDENCE_STALE")
            and str(item.get("provider") or "") in {"trend", "news", "qa"}
        ]
        self.assertGreaterEqual(len(stale_blockers), 1)

    def test_strict_providers_block_required_write_provider_for_github_mode(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-write-check.json"
        news_path = Path(self._tempdir.name) / "news-write-check.json"
        qa_path = Path(self._tempdir.name) / "qa-write-check.json"
        trend_path.write_text(json.dumps({"id": "trend-write-check", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-write-check", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-write-check", "questions": ["what is seo"]}), encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-write-block.example",
            site_name="Strict Write Block",
            repo_url="https://github.com/example/strict-write-block",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
        )
        project = service.create_project(ProjectCreateRequest(name="Strict Write Block", intake=intake))
        bundle = service.run_analysis(project.project_id, intake)
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-write-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "failed")
        providers = {str(item.get("provider") or "") for item in approved.deployment.strict_blockers}
        self.assertIn("github", providers)

    def test_strict_providers_block_when_required_write_provider_evidence_is_stale(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        os.environ["SEO_AD_BOT_PROVIDER_EVIDENCE_FRESHNESS_MINUTES"] = "60"
        trend_path = Path(self._tempdir.name) / "trend-write-stale.json"
        news_path = Path(self._tempdir.name) / "news-write-stale.json"
        qa_path = Path(self._tempdir.name) / "qa-write-stale.json"
        github_path = Path(self._tempdir.name) / "github-write-stale.json"
        trend_path.write_text(json.dumps({"id": "trend-write-stale", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-write-stale", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-write-stale", "questions": ["what is seo"]}), encoding="utf-8")
        github_path.write_text(json.dumps({"number": 508, "html_url": "https://github.com/example/stale-write/pull/508"}), encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"
        os.environ["SEO_AD_BOT_GITHUB_PROVIDER_URL"] = github_path.as_uri()
        os.environ["SEO_AD_BOT_GITHUB_ACCESS_TOKEN"] = "gh-token"
        os.environ["SEO_AD_BOT_GITHUB_HEAD_BRANCH"] = "seo-ad/autopilot"
        os.environ["SEO_AD_BOT_GITHUB_BASE_BRANCH"] = "main"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-write-stale.example",
            site_name="Strict Write Stale",
            repo_url="https://github.com/example/stale-write",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
        )
        project = service.create_project(ProjectCreateRequest(name="Strict Write Stale", intake=intake))
        bundle = service.run_analysis(project.project_id, intake)
        self.assertIsNotNone(bundle.ingestion_report)
        bundle.plan = bundle.plan.model_copy(update={"deployment_mode": DeploymentMode.github_pr})
        stale_checked_at = datetime.now(timezone.utc) - timedelta(hours=6)
        github_connected_injected = False
        for index, evidence in enumerate(bundle.ingestion_report.evidence):
            if evidence.provider == ConnectorKind.github:
                bundle.ingestion_report.evidence[index] = evidence.model_copy(
                    update={
                        "status": ConnectorStatus.connected,
                        "auth_source": evidence.auth_source or "env:SEO_AD_BOT_GITHUB_ACCESS_TOKEN",
                        "checked_at": stale_checked_at,
                    }
                )
                github_connected_injected = True
        if not github_connected_injected:
            bundle.ingestion_report.evidence.append(
                SourceEvidence(
                    provider=ConnectorKind.github,
                    status=ConnectorStatus.connected,
                    summary="GitHub connector probe succeeded (injected for stale gate test).",
                    provenance=["injected-test"],
                    details={"mode": "real"},
                    source_type="connector",
                    source_ref="github://example/stale-write",
                    checked_at=stale_checked_at,
                    auth_source="env:SEO_AD_BOT_GITHUB_ACCESS_TOKEN",
                )
            )

        blockers = service._strict_publish_blockers(bundle)  # noqa: SLF001 - strict gate verification
        stale_github_blockers = [
            item
            for item in blockers
            if str(item.get("provider") or "") == "github" and str(item.get("failureCode") or "") == "GITHUB_EVIDENCE_STALE"
        ]
        self.assertGreaterEqual(len(stale_github_blockers), 1)

    def test_strict_providers_block_required_write_provider_for_cms_mode(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-cms-write-check.json"
        news_path = Path(self._tempdir.name) / "news-cms-write-check.json"
        qa_path = Path(self._tempdir.name) / "qa-cms-write-check.json"
        trend_path.write_text(json.dumps({"id": "trend-cms-write-check", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-cms-write-check", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-cms-write-check", "questions": ["what is seo"]}), encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-cms-write-block.example",
            site_name="Strict CMS Write Block",
            cms_name="contentful",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
        )
        project = service.create_project(ProjectCreateRequest(name="Strict CMS Write Block", intake=intake))
        bundle = service.run_analysis(project.project_id, intake)
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-cms-write-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "failed")
        providers = {str(item.get("provider") or "") for item in approved.deployment.strict_blockers}
        self.assertIn("cms", providers)

    def test_strict_providers_block_required_write_provider_for_script_mode(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-script-write-check.json"
        news_path = Path(self._tempdir.name) / "news-script-write-check.json"
        qa_path = Path(self._tempdir.name) / "qa-script-write-check.json"
        trend_path.write_text(json.dumps({"id": "trend-script-write-check", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-script-write-check", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-script-write-check", "questions": ["what is seo"]}), encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-script-write-block.example",
            site_name="Strict Script Write Block",
            notes="script injection mode for edge runtime",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
        )
        project = service.create_project(ProjectCreateRequest(name="Strict Script Write Block", intake=intake))
        bundle = service.run_analysis(project.project_id, intake)
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-script-write-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "failed")
        providers = {str(item.get("provider") or "") for item in approved.deployment.strict_blockers}
        self.assertIn("script_api", providers)

    def test_strict_providers_allow_required_write_provider_for_cms_mode_when_connected(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-cms-allow.json"
        news_path = Path(self._tempdir.name) / "news-cms-allow.json"
        qa_path = Path(self._tempdir.name) / "qa-cms-allow.json"
        search_console_path = Path(self._tempdir.name) / "search-console-cms-allow.json"
        ga4_path = Path(self._tempdir.name) / "ga4-cms-allow.json"
        cms_path = Path(self._tempdir.name) / "cms-allow.json"
        trend_path.write_text(json.dumps({"id": "trend-cms-allow", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-cms-allow", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-cms-allow", "questions": ["what is seo"]}), encoding="utf-8")
        search_console_path.write_text(json.dumps({"rows": [{"keys": ["seo ops"], "clicks": 66, "impressions": 990}]}), encoding="utf-8")
        ga4_path.write_text(json.dumps({"rows": [{"metricValues": [{"value": "2500"}, {"value": "33"}, {"value": "0.66"}]}]}), encoding="utf-8")
        cms_path.write_text(json.dumps({"draftId": "cms-draft-123"}), encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"
        os.environ["SEO_AD_BOT_CMS_ACCESS_TOKEN"] = "cms-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-cms-write-allow.example",
            site_name="Strict CMS Write Allow",
            cms_name="contentful",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
            search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
            ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "777000"},
        )
        project = service.create_project(ProjectCreateRequest(name="Strict CMS Write Allow", intake=intake))
        existing = service.get_project_connections(project.project_id)
        updated_connections = []
        for connection in existing.connections:
            if connection.provider == ConnectorKind.cms:
                clone = connection.model_copy()
                clone.config = {
                    **clone.config,
                    "cmsName": intake.cms_name,
                    "draftEndpoint": cms_path.as_uri(),
                    "authToken": "cms-token",
                }
                updated_connections.append(clone)
            else:
                updated_connections.append(connection.model_copy())
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing.state.auto_cruise_enabled,
                sync_interval_minutes=existing.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        bundle = service.run_analysis(project.project_id, intake)
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-cms-allow-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "deployed")
        self.assertNotEqual(approved.deployment.failure_code, "STRICT_PROVIDER_BLOCKED")
        self.assertEqual(approved.deployment.writeback_summary.get("provider"), "cms")
        self.assertGreaterEqual(int(approved.deployment.writeback_summary.get("successCount") or 0), 1)
        self.assertEqual(approved.deployment.provider_artifact_id, "cms-draft-123")
        self.assertTrue(str(approved.deployment.provider_url or "").startswith("file://"))

    def test_strict_providers_allow_required_write_provider_for_script_mode_when_connected(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-script-allow.json"
        news_path = Path(self._tempdir.name) / "news-script-allow.json"
        qa_path = Path(self._tempdir.name) / "qa-script-allow.json"
        search_console_path = Path(self._tempdir.name) / "search-console-script-allow.json"
        ga4_path = Path(self._tempdir.name) / "ga4-script-allow.json"
        script_path = Path(self._tempdir.name) / "script-allow.json"
        trend_path.write_text(json.dumps({"id": "trend-script-allow", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-script-allow", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-script-allow", "questions": ["what is seo"]}), encoding="utf-8")
        search_console_path.write_text(json.dumps({"rows": [{"keys": ["seo automation"], "clicks": 71, "impressions": 1030}]}), encoding="utf-8")
        ga4_path.write_text(json.dumps({"rows": [{"metricValues": [{"value": "2800"}, {"value": "39"}, {"value": "0.67"}]}]}), encoding="utf-8")
        script_path.write_text(json.dumps({"artifactId": "script-allow-123"}), encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"
        os.environ["SEO_AD_BOT_SCRIPT_PROVIDER_URL"] = script_path.as_uri()
        os.environ["SEO_AD_BOT_SCRIPT_ACCESS_TOKEN"] = "script-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-script-write-allow.example",
            site_name="Strict Script Write Allow",
            notes="script injection mode for edge runtime",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
            search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
            ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "888000"},
        )
        project = service.create_project(ProjectCreateRequest(name="Strict Script Write Allow", intake=intake))
        bundle = service.run_analysis(project.project_id, intake)
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-script-allow-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "deployed")
        self.assertNotEqual(approved.deployment.failure_code, "STRICT_PROVIDER_BLOCKED")
        self.assertEqual(approved.deployment.writeback_summary.get("provider"), "script_api")
        self.assertGreaterEqual(int(approved.deployment.writeback_summary.get("successCount") or 0), 1)
        self.assertEqual(approved.deployment.provider_artifact_id, "script-allow-123")
        self.assertTrue(str(approved.deployment.provider_url or "").startswith("file://"))

    def test_strict_providers_fail_script_mode_when_writeback_payload_is_invalid(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-script-invalid.json"
        news_path = Path(self._tempdir.name) / "news-script-invalid.json"
        qa_path = Path(self._tempdir.name) / "qa-script-invalid.json"
        search_console_path = Path(self._tempdir.name) / "search-console-script-invalid.json"
        ga4_path = Path(self._tempdir.name) / "ga4-script-invalid.json"
        script_valid_path = Path(self._tempdir.name) / "script-valid.json"
        script_invalid_path = Path(self._tempdir.name) / "script-invalid.txt"
        trend_path.write_text(json.dumps({"id": "trend-script-invalid", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-script-invalid", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-script-invalid", "questions": ["what is seo"]}), encoding="utf-8")
        search_console_path.write_text(json.dumps({"rows": [{"keys": ["seo automation"], "clicks": 71, "impressions": 1030}]}), encoding="utf-8")
        ga4_path.write_text(json.dumps({"rows": [{"metricValues": [{"value": "2800"}, {"value": "39"}, {"value": "0.67"}]}]}), encoding="utf-8")
        script_valid_path.write_text(json.dumps({"artifactId": "script-precheck-1"}), encoding="utf-8")
        script_invalid_path.write_text("not-json", encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"
        os.environ["SEO_AD_BOT_SCRIPT_PROVIDER_URL"] = script_valid_path.as_uri()
        os.environ["SEO_AD_BOT_SCRIPT_ACCESS_TOKEN"] = "script-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-script-write-invalid.example",
            site_name="Strict Script Write Invalid",
            notes="script injection mode for edge runtime",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
            search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
            ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "888001"},
        )
        project = service.create_project(ProjectCreateRequest(name="Strict Script Write Invalid", intake=intake))
        bundle = service.run_analysis(project.project_id, intake)
        existing = service.get_project_connections(project.project_id)
        updated_connections = []
        for connection in existing.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.script_api:
                clone.config = {
                    **clone.config,
                    "scriptEndpoint": script_invalid_path.as_uri(),
                    "accessToken": "script-token",
                }
            updated_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing.state.auto_cruise_enabled,
                sync_interval_minutes=existing.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-script-invalid-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "failed")
        self.assertEqual(approved.deployment.failure_code, "SCRIPT_INVALID_PAYLOAD")

    def test_strict_providers_allow_required_write_provider_for_github_mode_when_connected(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-github-allow.json"
        news_path = Path(self._tempdir.name) / "news-github-allow.json"
        qa_path = Path(self._tempdir.name) / "qa-github-allow.json"
        search_console_path = Path(self._tempdir.name) / "search-console-github-allow.json"
        ga4_path = Path(self._tempdir.name) / "ga4-github-allow.json"
        github_path = Path(self._tempdir.name) / "github-allow.json"
        trend_path.write_text(json.dumps({"id": "trend-github-allow", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-github-allow", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-github-allow", "questions": ["what is seo"]}), encoding="utf-8")
        search_console_path.write_text(json.dumps({"rows": [{"keys": ["seo github"], "clicks": 81, "impressions": 1430}]}), encoding="utf-8")
        ga4_path.write_text(json.dumps({"rows": [{"metricValues": [{"value": "3100"}, {"value": "42"}, {"value": "0.68"}]}]}), encoding="utf-8")
        github_path.write_text(json.dumps({"number": 108, "html_url": "https://github.com/example/strict-github-write-allow/pull/108"}), encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"
        os.environ["SEO_AD_BOT_GITHUB_ACCESS_TOKEN"] = "github-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-github-write-allow.example",
            site_name="Strict GitHub Write Allow",
            repo_url="https://github.com/example/strict-github-write-allow",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
            search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
            ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "999000"},
        )
        project = service.create_project(ProjectCreateRequest(name="Strict GitHub Write Allow", intake=intake))
        existing = service.get_project_connections(project.project_id)
        updated_connections = []
        for connection in existing.connections:
            if connection.provider == ConnectorKind.github:
                clone = connection.model_copy()
                clone.config = {
                    **clone.config,
                    "repoUrl": intake.repo_url,
                    "owner": "example",
                    "repo": "strict-github-write-allow",
                    "headBranch": "autopilot/preview",
                    "baseBranch": "main",
                    "apiEndpoint": github_path.as_uri(),
                    "accessToken": "github-token",
                }
                updated_connections.append(clone)
            else:
                updated_connections.append(connection.model_copy())
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing.state.auto_cruise_enabled,
                sync_interval_minutes=existing.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        bundle = service.run_analysis(project.project_id, intake)
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-github-allow-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "deployed")
        self.assertNotEqual(approved.deployment.failure_code, "STRICT_PROVIDER_BLOCKED")
        self.assertEqual(approved.deployment.writeback_summary.get("provider"), "github")
        self.assertGreaterEqual(int(approved.deployment.writeback_summary.get("successCount") or 0), 1)
        self.assertEqual(approved.deployment.provider_artifact_id, "108")
        self.assertEqual(
            approved.deployment.provider_url,
            "https://github.com/example/strict-github-write-allow/pull/108",
        )

    def test_github_writeback_uses_credentials_json_auth_header(self) -> None:
        service = self._service()
        intake = SiteIntake(
            url="https://github-writeback-auth-header.example",
            site_name="GitHub Writeback Auth Header",
            repo_url="https://github.com/example/github-writeback-auth-header",
            keywords=["seo", "growth"],
        )
        project = service.create_project(ProjectCreateRequest(name="GitHub Writeback Auth Header", intake=intake))
        existing = service.get_project_connections(project.project_id)
        updated_connections = []
        for connection in existing.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.github:
                clone.config = {
                    **clone.config,
                    "repoUrl": intake.repo_url,
                    "owner": "example",
                    "repo": "github-writeback-auth-header",
                    "headBranch": "autopilot/preview",
                    "baseBranch": "main",
                    "apiEndpoint": "https://github-writeback.example/api/pulls",
                    "credentialsJson": json.dumps({"accessToken": "gh-deploy-json-token", "authHeader": "X-GH-Deploy"}),
                }
            updated_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing.state.auto_cruise_enabled,
                sync_interval_minutes=existing.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )

        seen_headers: list[dict[str, str]] = []

        def _mock_http_json(  # type: ignore[no-untyped-def]
            url: str,
            *,
            method: str = "GET",
            headers: Optional[dict[str, str]] = None,
            payload: Optional[dict[str, object]] = None,
            timeout: int = 10,
        ) -> dict[str, object]:
            del method, payload, timeout
            if "github-writeback.example/api/pulls" in url:
                seen_headers.append(dict(headers or {}))
                return {"number": 512, "html_url": "https://github.com/example/github-writeback-auth-header/pull/512"}
            return {}

        with patch("apps.api.seo_ad_autopilot.connectors._http_json", side_effect=_mock_http_json):
            bundle = service.run_analysis(project.project_id, intake)
            approved = service.approve_task(
                bundle.task.task_id,
                ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="deploy-auth-header-test"),
            )

        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "deployed")
        self.assertEqual(approved.deployment.writeback_summary.get("provider"), "github")
        self.assertGreaterEqual(len(seen_headers), 1)
        self.assertTrue(all(item.get("X-GH-Deploy") == "Bearer gh-deploy-json-token" for item in seen_headers))
        self.assertTrue(all("Authorization" not in item for item in seen_headers))

    def test_strict_providers_fail_github_mode_when_writeback_payload_is_invalid(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-github-invalid.json"
        news_path = Path(self._tempdir.name) / "news-github-invalid.json"
        qa_path = Path(self._tempdir.name) / "qa-github-invalid.json"
        search_console_path = Path(self._tempdir.name) / "search-console-github-invalid.json"
        ga4_path = Path(self._tempdir.name) / "ga4-github-invalid.json"
        github_valid_path = Path(self._tempdir.name) / "github-valid.json"
        github_invalid_path = Path(self._tempdir.name) / "github-invalid.txt"
        trend_path.write_text(json.dumps({"id": "trend-github-invalid", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-github-invalid", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-github-invalid", "questions": ["what is seo"]}), encoding="utf-8")
        search_console_path.write_text(json.dumps({"rows": [{"keys": ["seo github"], "clicks": 81, "impressions": 1430}]}), encoding="utf-8")
        ga4_path.write_text(json.dumps({"rows": [{"metricValues": [{"value": "3100"}, {"value": "42"}, {"value": "0.68"}]}]}), encoding="utf-8")
        github_valid_path.write_text(
            json.dumps({"number": 201, "html_url": "https://github.com/example/strict-github-write-invalid/pull/201"}),
            encoding="utf-8",
        )
        github_invalid_path.write_text("bad-response", encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"
        os.environ["SEO_AD_BOT_GITHUB_ACCESS_TOKEN"] = "github-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-github-write-invalid.example",
            site_name="Strict GitHub Write Invalid",
            repo_url="https://github.com/example/strict-github-write-invalid",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
            search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
            ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "999001"},
        )
        project = service.create_project(ProjectCreateRequest(name="Strict GitHub Write Invalid", intake=intake))
        existing = service.get_project_connections(project.project_id)
        updated_connections = []
        for connection in existing.connections:
            if connection.provider == ConnectorKind.github:
                clone = connection.model_copy()
                clone.config = {
                    **clone.config,
                    "repoUrl": intake.repo_url,
                    "owner": "example",
                    "repo": "strict-github-write-invalid",
                    "headBranch": "autopilot/preview",
                    "baseBranch": "main",
                    "apiEndpoint": github_valid_path.as_uri(),
                    "accessToken": "github-token",
                }
                updated_connections.append(clone)
            else:
                updated_connections.append(connection.model_copy())
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing.state.auto_cruise_enabled,
                sync_interval_minutes=existing.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        bundle = service.run_analysis(project.project_id, intake)
        existing_after_analysis = service.get_project_connections(project.project_id)
        deploy_connections = []
        for connection in existing_after_analysis.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.github:
                clone.config = {
                    **clone.config,
                    "repoUrl": intake.repo_url,
                    "owner": "example",
                    "repo": "strict-github-write-invalid",
                    "headBranch": "autopilot/preview",
                    "baseBranch": "main",
                    "apiEndpoint": github_invalid_path.as_uri(),
                    "accessToken": "github-token",
                }
            deploy_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing_after_analysis.state.auto_cruise_enabled,
                sync_interval_minutes=existing_after_analysis.state.sync_interval_minutes,
                connections=deploy_connections,
            ),
        )
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-github-invalid-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "failed")
        self.assertEqual(approved.deployment.failure_code, "GITHUB_INVALID_PAYLOAD")

    def test_strict_providers_fail_cms_mode_when_writeback_payload_is_invalid(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-cms-invalid.json"
        news_path = Path(self._tempdir.name) / "news-cms-invalid.json"
        qa_path = Path(self._tempdir.name) / "qa-cms-invalid.json"
        search_console_path = Path(self._tempdir.name) / "search-console-cms-invalid.json"
        ga4_path = Path(self._tempdir.name) / "ga4-cms-invalid.json"
        cms_valid_path = Path(self._tempdir.name) / "cms-valid.json"
        cms_invalid_path = Path(self._tempdir.name) / "cms-invalid.txt"
        trend_path.write_text(json.dumps({"id": "trend-cms-invalid", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-cms-invalid", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-cms-invalid", "questions": ["what is seo"]}), encoding="utf-8")
        search_console_path.write_text(json.dumps({"rows": [{"keys": ["seo ops"], "clicks": 66, "impressions": 990}]}), encoding="utf-8")
        ga4_path.write_text(json.dumps({"rows": [{"metricValues": [{"value": "2500"}, {"value": "33"}, {"value": "0.66"}]}]}), encoding="utf-8")
        cms_valid_path.write_text(json.dumps({"draftId": "cms-valid-001"}), encoding="utf-8")
        cms_invalid_path.write_text("invalid", encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"
        os.environ["SEO_AD_BOT_CMS_ACCESS_TOKEN"] = "cms-token"

        service = self._service()
        intake = SiteIntake(
            url="https://strict-cms-write-invalid.example",
            site_name="Strict CMS Write Invalid",
            cms_name="contentful",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
            search_console={"accessToken": "sc-token", "endpoint": search_console_path.as_uri()},
            ga4={"accessToken": "ga4-token", "endpoint": ga4_path.as_uri(), "propertyId": "777001"},
        )
        project = service.create_project(ProjectCreateRequest(name="Strict CMS Write Invalid", intake=intake))
        existing = service.get_project_connections(project.project_id)
        updated_connections = []
        for connection in existing.connections:
            if connection.provider == ConnectorKind.cms:
                clone = connection.model_copy()
                clone.config = {
                    **clone.config,
                    "cmsName": intake.cms_name,
                    "draftEndpoint": cms_valid_path.as_uri(),
                    "authToken": "cms-token",
                }
                updated_connections.append(clone)
            else:
                updated_connections.append(connection.model_copy())
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing.state.auto_cruise_enabled,
                sync_interval_minutes=existing.state.sync_interval_minutes,
                connections=updated_connections,
            ),
        )
        bundle = service.run_analysis(project.project_id, intake)
        existing_after_analysis = service.get_project_connections(project.project_id)
        deploy_connections = []
        for connection in existing_after_analysis.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.cms:
                clone.config = {
                    **clone.config,
                    "cmsName": intake.cms_name,
                    "draftEndpoint": cms_invalid_path.as_uri(),
                    "authToken": "cms-token",
                }
            deploy_connections.append(clone)
        service.update_project_connections(
            project.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing_after_analysis.state.auto_cruise_enabled,
                sync_interval_minutes=existing_after_analysis.state.sync_interval_minutes,
                connections=deploy_connections,
            ),
        )
        approved = service.approve_task(
            bundle.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-cms-invalid-test"),
        )
        self.assertIsNotNone(approved.deployment)
        self.assertEqual(approved.deployment.status, "failed")
        self.assertEqual(approved.deployment.failure_code, "CMS_INVALID_PAYLOAD")

    def test_strict_provider_triage_with_project_health(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-triage.json"
        news_path = Path(self._tempdir.name) / "news-triage.json"
        qa_path = Path(self._tempdir.name) / "qa-triage.json"
        trend_path.write_text(json.dumps({"id": "trend-triage", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-triage", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-triage", "questions": ["what is seo"]}), encoding="utf-8")
        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"

        # A: read+write success
        sc_a = Path(self._tempdir.name) / "triage-a-sc.json"
        ga_a = Path(self._tempdir.name) / "triage-a-ga.json"
        gh_a = Path(self._tempdir.name) / "triage-a-gh.json"
        sc_a.write_text(json.dumps({"rows": [{"keys": ["seo triage a"], "clicks": 88, "impressions": 1550}]}), encoding="utf-8")
        ga_a.write_text(json.dumps({"rows": [{"metricValues": [{"value": "3200"}, {"value": "45"}, {"value": "0.69"}]}]}), encoding="utf-8")
        gh_a.write_text(json.dumps({"number": 208, "html_url": "https://github.com/example/triage-a/pull/208"}), encoding="utf-8")
        os.environ["SEO_AD_BOT_GITHUB_ACCESS_TOKEN"] = "github-token"
        service = self._service()
        intake_a = SiteIntake(
            url="https://triage-a.example",
            site_name="Triage A",
            repo_url="https://github.com/example/triage-a",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
            search_console={"accessToken": "sc-token", "endpoint": sc_a.as_uri()},
            ga4={"accessToken": "ga4-token", "endpoint": ga_a.as_uri(), "propertyId": "100001"},
        )
        project_a = service.create_project(ProjectCreateRequest(name="Triage A", intake=intake_a))
        existing_a = service.get_project_connections(project_a.project_id)
        updated_a: list[ProjectConnection] = []
        for connection in existing_a.connections:
            clone = connection.model_copy()
            if clone.provider == ConnectorKind.github:
                clone.config = {
                    **clone.config,
                    "repoUrl": intake_a.repo_url,
                    "owner": "example",
                    "repo": "triage-a",
                    "headBranch": "autopilot/preview",
                    "baseBranch": "main",
                    "apiEndpoint": gh_a.as_uri(),
                    "accessToken": "github-token",
                }
            updated_a.append(clone)
        service.update_project_connections(
            project_a.project_id,
            ProjectConnectionsUpdateRequest(
                auto_cruise_enabled=existing_a.state.auto_cruise_enabled,
                sync_interval_minutes=existing_a.state.sync_interval_minutes,
                connections=updated_a,
            ),
        )
        bundle_a = service.run_analysis(project_a.project_id, intake_a)
        approved_a = service.approve_task(
            bundle_a.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-triage-a"),
        )
        self.assertEqual(approved_a.deployment.status, "deployed")
        health_a = service.get_project_connectors_health(project_a.project_id)
        map_a = {item.provider: item for item in health_a.connections}
        self.assertTrue(map_a[ConnectorKind.github].strict_eligible)
        self.assertGreater(health_a.strict_eligible_count, 0)

        # B: write blocked (GitHub required but not connected)
        sc_b = Path(self._tempdir.name) / "triage-b-sc.json"
        ga_b = Path(self._tempdir.name) / "triage-b-ga.json"
        sc_b.write_text(json.dumps({"rows": [{"keys": ["seo triage b"], "clicks": 66, "impressions": 1110}]}), encoding="utf-8")
        ga_b.write_text(json.dumps({"rows": [{"metricValues": [{"value": "2600"}, {"value": "31"}, {"value": "0.63"}]}]}), encoding="utf-8")
        intake_b = SiteIntake(
            url="https://triage-b.example",
            site_name="Triage B",
            repo_url="https://github.com/example/triage-b",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
            search_console={"accessToken": "sc-token", "endpoint": sc_b.as_uri()},
            ga4={"accessToken": "ga4-token", "endpoint": ga_b.as_uri(), "propertyId": "100002"},
        )
        project_b = service.create_project(ProjectCreateRequest(name="Triage B", intake=intake_b))
        bundle_b = service.run_analysis(project_b.project_id, intake_b)
        approved_b = service.approve_task(
            bundle_b.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-triage-b"),
        )
        self.assertEqual(approved_b.deployment.status, "failed")
        blockers_b = {str(item.get("provider") or "") for item in approved_b.deployment.strict_blockers}
        self.assertIn("github", blockers_b)
        health_b = service.get_project_connectors_health(project_b.project_id)
        map_b = {item.provider: item for item in health_b.connections}
        self.assertFalse(map_b[ConnectorKind.github].strict_eligible)

        # C: read blocked (Search Console configured but failing)
        ga_c = Path(self._tempdir.name) / "triage-c-ga.json"
        ga_c.write_text(json.dumps({"rows": [{"metricValues": [{"value": "2400"}, {"value": "28"}, {"value": "0.62"}]}]}), encoding="utf-8")
        intake_c = SiteIntake(
            url="https://triage-c.example",
            site_name="Triage C",
            brand_whitelist=["Strict"],
            keywords=["seo", "growth"],
            search_console={"accessToken": "sc-token", "endpoint": "file:///missing-triage-c-sc.json"},
            ga4={"accessToken": "ga4-token", "endpoint": ga_c.as_uri(), "propertyId": "100003"},
        )
        project_c = service.create_project(ProjectCreateRequest(name="Triage C", intake=intake_c))
        bundle_c = service.run_analysis(project_c.project_id, intake_c)
        approved_c = service.approve_task(
            bundle_c.task.task_id,
            ApprovalDecisionRequest(decision=ApprovalStatus.approved, actor="strict-triage-c"),
        )
        self.assertEqual(approved_c.deployment.status, "failed")
        blockers_c = {str(item.get("provider") or "") for item in approved_c.deployment.strict_blockers}
        self.assertIn("search_console", blockers_c)
        health_c = service.get_project_connectors_health(project_c.project_id)
        map_c = {item.provider: item for item in health_c.connections}
        self.assertFalse(map_c[ConnectorKind.search_console].strict_eligible)

    def test_strict_api_consistency_for_sync_connections_health_and_approve(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "true"
        trend_path = Path(self._tempdir.name) / "trend-api-consistency.json"
        news_path = Path(self._tempdir.name) / "news-api-consistency.json"
        qa_path = Path(self._tempdir.name) / "qa-api-consistency.json"
        trend_path.write_text(json.dumps({"id": "trend-api-consistency", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-api-consistency", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-api-consistency", "questions": ["what is seo"]}), encoding="utf-8")
        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"
        os.environ["SEO_AD_BOT_GITHUB_ACCESS_TOKEN"] = "github-token"

        sc_ok = Path(self._tempdir.name) / "api-consistency-sc-ok.json"
        ga_ok = Path(self._tempdir.name) / "api-consistency-ga-ok.json"
        gh_ok = Path(self._tempdir.name) / "api-consistency-gh-ok.json"
        sc_ok.write_text(json.dumps({"rows": [{"keys": ["seo api strict"], "clicks": 77, "impressions": 1210}]}), encoding="utf-8")
        ga_ok.write_text(json.dumps({"rows": [{"metricValues": [{"value": "2900"}, {"value": "36"}, {"value": "0.66"}]}]}), encoding="utf-8")
        gh_ok.write_text(json.dumps({"number": 308, "html_url": "https://github.com/example/api-strict-ok/pull/308"}), encoding="utf-8")

        service = self._service()
        app = create_app(service)

        with TestClient(app) as client:
            create_ok = client.post(
                "/api/projects",
                json={
                    "name": "API Strict OK",
                    "intake": {
                        "url": "https://api-strict-ok.example",
                        "siteName": "API Strict OK",
                        "repoUrl": "https://github.com/example/api-strict-ok",
                        "keywords": ["seo", "growth"],
                        "searchConsole": {"accessToken": "sc-token", "endpoint": sc_ok.as_uri()},
                        "ga4": {"accessToken": "ga4-token", "endpoint": ga_ok.as_uri(), "propertyId": "200001"},
                    },
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(create_ok.status_code, 200)
            project_ok = create_ok.json()["projectId"]

            connections_ok = client.get(f"/api/projects/{project_ok}/connections")
            self.assertEqual(connections_ok.status_code, 200)
            payload_ok = connections_ok.json()
            updated_ok = []
            for connection in payload_ok["connections"]:
                clone = dict(connection)
                if clone["provider"] == "github":
                    clone["config"] = {
                        **clone.get("config", {}),
                        "repoUrl": "https://github.com/example/api-strict-ok",
                        "owner": "example",
                        "repo": "api-strict-ok",
                        "headBranch": "autopilot/preview",
                        "baseBranch": "main",
                        "apiEndpoint": gh_ok.as_uri(),
                        "accessToken": "github-token",
                    }
                updated_ok.append(clone)
            update_ok = client.put(
                f"/api/projects/{project_ok}/connections",
                json={
                    "autoCruiseEnabled": payload_ok["state"]["autoCruiseEnabled"],
                    "syncIntervalMinutes": payload_ok["state"]["syncIntervalMinutes"],
                    "connections": updated_ok,
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(update_ok.status_code, 200)

            sync_ok = client.post(f"/api/projects/{project_ok}/sync", headers={"X-API-Key": "dev-key"})
            self.assertEqual(sync_ok.status_code, 200)
            sync_ok_payload = sync_ok.json()
            self.assertIn("ingestionReport", sync_ok_payload)
            task_ok = sync_ok_payload["task"]["taskId"]

            test_ok = client.post(f"/api/projects/{project_ok}/connections/test", headers={"X-API-Key": "dev-key"})
            self.assertEqual(test_ok.status_code, 200)
            test_ok_payload = test_ok.json()
            self.assertTrue(test_ok_payload["strictMode"])
            self.assertFalse(test_ok_payload["strictBlocked"])
            self.assertEqual(test_ok_payload["strictGapCount"], 0)
            self.assertEqual(test_ok_payload["strictBlockers"], [])
            health_ok = client.get(f"/api/projects/{project_ok}/connectors/health")
            self.assertEqual(health_ok.status_code, 200)
            health_ok_payload = health_ok.json()
            strict_count_test_ok = sum(1 for item in test_ok_payload["connections"] if item.get("strictEligible"))
            self.assertGreaterEqual(health_ok_payload["strictEligibleCount"], strict_count_test_ok)
            provider_map_ok = {item["provider"]: item for item in test_ok_payload["connections"]}
            health_provider_map_ok = {item["provider"]: item for item in health_ok_payload["connections"]}
            self.assertTrue(provider_map_ok["search_console"]["strictEligible"])
            self.assertTrue(provider_map_ok["ga4"]["strictEligible"])
            self.assertTrue(provider_map_ok["github"]["strictEligible"])
            self.assertTrue(health_provider_map_ok["search_console"]["strictEligible"])
            self.assertTrue(health_provider_map_ok["ga4"]["strictEligible"])
            self.assertTrue(health_provider_map_ok["github"]["strictEligible"])
            self.assertEqual(provider_map_ok["search_console"]["providerMode"], "real")
            self.assertEqual(provider_map_ok["ga4"]["providerMode"], "real")
            self.assertEqual(provider_map_ok["github"]["providerMode"], "real")

            approve_ok = client.post(
                f"/api/tasks/{task_ok}/approve",
                json={"decision": "approved", "actor": "strict-api-consistency"},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(approve_ok.status_code, 200)
            self.assertEqual(approve_ok.json()["deployment"]["status"], "deployed")
            self.assertNotEqual(approve_ok.json()["deployment"]["failureCode"], "STRICT_PROVIDER_BLOCKED")

            create_block = client.post(
                "/api/projects",
                json={
                    "name": "API Strict Block",
                    "intake": {
                        "url": "https://api-strict-block.example",
                        "siteName": "API Strict Block",
                        "repoUrl": "https://github.com/example/api-strict-block",
                        "keywords": ["seo", "growth"],
                        "searchConsole": {"accessToken": "sc-token", "endpoint": sc_ok.as_uri()},
                        "ga4": {"accessToken": "ga4-token", "endpoint": ga_ok.as_uri(), "propertyId": "200002"},
                    },
                },
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(create_block.status_code, 200)
            project_block = create_block.json()["projectId"]

            sync_block = client.post(f"/api/projects/{project_block}/sync", headers={"X-API-Key": "dev-key"})
            self.assertEqual(sync_block.status_code, 200)
            task_block = sync_block.json()["task"]["taskId"]

            test_block = client.post(f"/api/projects/{project_block}/connections/test", headers={"X-API-Key": "dev-key"})
            self.assertEqual(test_block.status_code, 200)
            test_block_payload = test_block.json()
            self.assertTrue(test_block_payload["strictMode"])
            self.assertTrue(test_block_payload["strictBlocked"])
            self.assertGreater(test_block_payload["strictGapCount"], 0)
            self.assertTrue(any(item.startswith("github:") for item in test_block_payload["strictBlockers"]))
            health_block = client.get(f"/api/projects/{project_block}/connectors/health")
            self.assertEqual(health_block.status_code, 200)
            health_block_payload = health_block.json()
            strict_count_test_block = sum(1 for item in test_block_payload["connections"] if item.get("strictEligible"))
            self.assertGreaterEqual(health_block_payload["strictEligibleCount"], strict_count_test_block)
            provider_map_block = {item["provider"]: item for item in test_block_payload["connections"]}
            health_provider_map_block = {item["provider"]: item for item in health_block_payload["connections"]}
            self.assertFalse(provider_map_block["github"]["strictEligible"])
            self.assertFalse(health_provider_map_block["github"]["strictEligible"])

            approve_block = client.post(
                f"/api/tasks/{task_block}/approve",
                json={"decision": "approved", "actor": "strict-api-consistency"},
                headers={"X-API-Key": "dev-key"},
            )
            self.assertEqual(approve_block.status_code, 200)
            approve_block_payload = approve_block.json()
            self.assertEqual(approve_block_payload["deployment"]["status"], "failed")
            blockers = {str(item.get("provider") or "") for item in approve_block_payload["deployment"]["strictBlockers"]}
            self.assertIn("github", blockers)

    def test_market_evidence_uses_synthetic_fallback_when_not_strict(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "false"
        os.environ["SEO_AD_BOT_MARKET_PROVIDER_ACCESS_TOKEN"] = "shared-token"
        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = "file:///missing-trend.json"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = "file:///missing-news.json"
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = "file:///missing-qa.json"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Market Synthetic",
                intake=SiteIntake(
                    url="https://market-synthetic.example",
                    site_name="Market Synthetic",
                    keywords=["seo", "growth"],
                ),
            )
        )
        bundle = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://market-synthetic.example",
                site_name="Market Synthetic",
                keywords=["seo", "growth"],
            ),
        )
        self.assertIsNotNone(bundle.ingestion_report)
        market_sources = [
            item
            for item in bundle.ingestion_report.evidence
            if item.provider.value in {"trend", "news", "qa"}
        ]
        self.assertEqual(len(market_sources), 3)
        self.assertTrue(all(item.status.value == "synthetic" for item in market_sources))
        self.assertTrue(all(str(item.source_ref or "").startswith("synthetic:") for item in market_sources))
        self.assertTrue(all(item.auth_source in {"settings:shared", "env:SEO_AD_BOT_MARKET_PROVIDER_ACCESS_TOKEN"} for item in market_sources))
        self.assertTrue(all("requestTimeoutMs" in item.details for item in market_sources))

    def test_deploy_threshold_keeps_medium_risk_as_scheduled(self) -> None:
        service = self._service()
        intake = SiteIntake(
            url="https://threshold-medium.example",
            site_name="Threshold Medium",
            keywords=["seo", "growth"],
        )
        project = service.create_project(ProjectCreateRequest(name="Threshold Medium", intake=intake))
        bundle = service.run_analysis(project.project_id, intake)
        task_id = bundle.task.task_id

        with service.database.session() as session:
            row = session.get(TaskRow, task_id)
            assert row is not None
            row.risk_score = 70
            row.approval_status = ApprovalStatus.approved.value
            row.deployment_json = DeploymentRecord(
                deployment_id="deploy_threshold_medium",
                task_id=task_id,
                mode=DeploymentMode.static_export,
                status="scheduled",
                artifact_ref="artifact://preview/threshold-medium",
                release_notes=["Scheduled deployment for threshold test."],
                rollback_ready=True,
            ).model_dump(mode="json", by_alias=True)
            session.add(row)

        deployed = service.deploy_task(
            task_id,
            DeploymentActionRequest(actor="threshold-test", note="manual deploy attempt"),
        )
        self.assertIsNotNone(deployed.deployment)
        self.assertEqual(deployed.deployment.status, "scheduled")
        self.assertTrue(any("60-79" in note for note in deployed.deployment.release_notes))

    def test_deploy_threshold_promotes_only_low_risk(self) -> None:
        service = self._service()
        intake = SiteIntake(
            url="https://threshold-low.example",
            site_name="Threshold Low",
            keywords=["seo", "growth"],
        )
        project = service.create_project(ProjectCreateRequest(name="Threshold Low", intake=intake))
        bundle = service.run_analysis(project.project_id, intake)
        task_id = bundle.task.task_id

        with service.database.session() as session:
            row = session.get(TaskRow, task_id)
            assert row is not None
            row.risk_score = 59
            row.approval_status = ApprovalStatus.approved.value
            row.deployment_json = DeploymentRecord(
                deployment_id="deploy_threshold_low",
                task_id=task_id,
                mode=DeploymentMode.static_export,
                status="scheduled",
                artifact_ref="artifact://preview/threshold-low",
                release_notes=["Scheduled deployment for threshold test."],
                rollback_ready=True,
            ).model_dump(mode="json", by_alias=True)
            session.add(row)

        deployed = service.deploy_task(
            task_id,
            DeploymentActionRequest(actor="threshold-test", note="manual deploy attempt"),
        )
        self.assertIsNotNone(deployed.deployment)
        self.assertEqual(deployed.deployment.status, "deployed")

    def test_static_export_writeback_uses_provider_endpoint_when_configured(self) -> None:
        os.environ["SEO_AD_BOT_STATIC_EXPORT_PROVIDER_URL"] = "https://static-export.example/api/exports"
        os.environ["SEO_AD_BOT_STATIC_EXPORT_ACCESS_TOKEN"] = "static-token"
        service = self._service()
        intake = SiteIntake(
            url="https://static-export-writeback.example",
            site_name="Static Export Writeback",
            keywords=["seo", "growth"],
        )
        project = service.create_project(ProjectCreateRequest(name="Static Export Writeback", intake=intake))
        with patch(
            "apps.api.seo_ad_autopilot.connectors._http_json",
            return_value={"artifactId": "static-export-123", "artifactUrl": "https://cdn.example/static-export-123.zip"},
        ) as static_writeback_mock:
            bundle = service.run_analysis(project.project_id, intake)

        self.assertGreaterEqual(static_writeback_mock.call_count, 1)
        self.assertIsNotNone(bundle.deployment)
        assert bundle.deployment is not None
        self.assertEqual(bundle.plan.deployment_mode, DeploymentMode.static_export)
        self.assertEqual(bundle.deployment.writeback_summary.get("provider"), "static_export")
        self.assertGreaterEqual(int(bundle.deployment.writeback_summary.get("successCount") or 0), 1)
        self.assertEqual(bundle.deployment.provider_artifact_id, "static-export-123")
        self.assertEqual(bundle.deployment.provider_url, "https://static-export.example/api/exports")
        self.assertEqual(bundle.deployment.artifact_ref, "https://cdn.example/static-export-123.zip")

    def test_acceptance_report_includes_static_export_real_write_evidence(self) -> None:
        os.environ["SEO_AD_BOT_STATIC_EXPORT_PROVIDER_URL"] = "https://static-export.example/api/exports"
        os.environ["SEO_AD_BOT_STATIC_EXPORT_ACCESS_TOKEN"] = "static-token"
        service = self._service()
        intake = SiteIntake(
            url="https://acceptance-static-export.example",
            site_name="Acceptance Static Export",
            keywords=["seo", "growth"],
        )
        project = service.create_project(ProjectCreateRequest(name="Acceptance Static Export", intake=intake))
        with patch(
            "apps.api.seo_ad_autopilot.connectors._http_json",
            return_value={"artifactId": "static-export-accept-1", "artifactUrl": "https://cdn.example/static-export-accept-1.zip"},
        ):
            service.run_analysis(project.project_id, intake)
        report = service.build_acceptance_report()
        providers = {item.provider for item in report.write_real_evidence}
        self.assertIn("static_export", providers)

    def test_market_providers_do_not_emit_adapter_missing_on_second_sync(self) -> None:
        os.environ["SEO_AD_BOT_STRICT_PROVIDERS"] = "false"
        os.environ["SEO_AD_BOT_MARKET_PROVIDER_ACCESS_TOKEN"] = "shared-token"
        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = "file:///missing-trend.json"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = "file:///missing-news.json"
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = "file:///missing-qa.json"
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Market Adapter Missing Guard",
                intake=SiteIntake(
                    url="https://market-guard.example",
                    site_name="Market Guard",
                    keywords=["seo", "growth"],
                ),
            )
        )

        first = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://market-guard.example",
                site_name="Market Guard",
                keywords=["seo", "growth"],
            ),
        )
        second = service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://market-guard.example",
                site_name="Market Guard",
                keywords=["seo", "growth"],
            ),
        )
        self.assertIsNotNone(first.ingestion_report)
        self.assertIsNotNone(second.ingestion_report)
        first_market = [item for item in first.ingestion_report.evidence if item.provider.value in {"trend", "news", "qa"}]
        second_market = [item for item in second.ingestion_report.evidence if item.provider.value in {"trend", "news", "qa"}]
        self.assertEqual(len(first_market), 3)
        self.assertEqual(len(second_market), 3)
        self.assertTrue(all(item.status.value == "synthetic" for item in second_market))
        self.assertTrue(all("adapter-missing" not in item.provenance for item in second_market))
        self.assertTrue(all("adapter missing" not in item.summary.lower() for item in second_market))
        self.assertFalse(any("adapter missing" in note.lower() for note in second.ingestion_report.notes))

    def test_bulk_connector_refresh_actions_are_audited(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Bulk Refresh Audit",
                intake=SiteIntake(
                    url="https://bulk-refresh-audit.example",
                    site_name="Bulk Refresh Audit",
                    keywords=["seo", "growth"],
                ),
            )
        )
        service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://bulk-refresh-audit.example",
                site_name="Bulk Refresh Audit",
                keywords=["seo", "growth"],
            ),
        )
        service.refresh_blocking_connectors(
            BulkBlockingRefreshRequest(project_ids=[project.project_id], providers=[], max_providers=3),
        )
        service.refresh_strict_gap_connectors(
            BulkStrictGapRefreshRequest(project_ids=[project.project_id], providers=[], max_providers=3),
        )
        with service.database.session() as session:
            actions = set(
                session.scalars(
                    select(AuditRow.action).where(
                        AuditRow.action.in_(
                            [
                                "connectors.bulk.blocking.refreshed",
                                "connectors.bulk.strict_gap.refreshed",
                            ]
                        )
                    )
                ).all()
        )
        self.assertIn("connectors.bulk.blocking.refreshed", actions)
        self.assertIn("connectors.bulk.strict_gap.refreshed", actions)

    def test_bulk_market_evidence_refresh_action_is_audited(self) -> None:
        service = self._service()
        project = service.create_project(
            ProjectCreateRequest(
                name="Market Evidence Refresh Audit",
                intake=SiteIntake(
                    url="https://market-evidence-refresh.example",
                    site_name="Market Evidence Refresh Audit",
                    keywords=["seo", "growth"],
                ),
            )
        )
        service.run_analysis(
            project.project_id,
            SiteIntake(
                url="https://market-evidence-refresh.example",
                site_name="Market Evidence Refresh Audit",
                keywords=["seo", "growth"],
            ),
        )
        result = service.refresh_market_evidence_connectors(
            BulkMarketEvidenceRefreshRequest(project_ids=[project.project_id], providers=[], max_providers=3),
        )
        self.assertGreaterEqual(result.provider_count, 1)
        with service.database.session() as session:
            actions = set(
                session.scalars(
                    select(AuditRow.action).where(
                        AuditRow.action == "connectors.bulk.market_evidence.refreshed"
                    )
                ).all()
            )
        self.assertIn("connectors.bulk.market_evidence.refreshed", actions)

    def test_market_evidence_provider_status_report_includes_trend_news_qa(self) -> None:
        service = self._service()
        report = service.build_market_evidence_provider_status_report()

        self.assertEqual(report.provider_count, 3)
        self.assertEqual([item.provider.value for item in report.entries], ["trend", "news", "qa"])
        self.assertTrue(all(item.provider_label for item in report.entries))
        with TestClient(create_app(service)) as client:
            response = client.get("/api/market-evidence/providers")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["providerCount"], 3)
        self.assertEqual([item["provider"] for item in payload["entries"]], ["trend", "news", "qa"])

    def test_default_project_connections_include_market_providers_when_configured(self) -> None:
        trend_path = Path(self._tempdir.name) / "trend-default-connection.json"
        news_path = Path(self._tempdir.name) / "news-default-connection.json"
        qa_path = Path(self._tempdir.name) / "qa-default-connection.json"
        trend_path.write_text(json.dumps({"id": "trend-default-connection", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-default-connection", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-default-connection", "questions": ["what is seo"]}), encoding="utf-8")

        os.environ["SEO_AD_BOT_TREND_PROVIDER_URL"] = trend_path.as_uri()
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_URL"] = news_path.as_uri()
        os.environ["SEO_AD_BOT_QA_PROVIDER_URL"] = qa_path.as_uri()
        os.environ["SEO_AD_BOT_TREND_PROVIDER_ACCESS_TOKEN"] = "trend-token"
        os.environ["SEO_AD_BOT_NEWS_PROVIDER_ACCESS_TOKEN"] = "news-token"
        os.environ["SEO_AD_BOT_QA_PROVIDER_ACCESS_TOKEN"] = "qa-token"

        service = self._service()
        intake = SiteIntake(
            url="https://market-default-connection.example",
            site_name="Market Default Connection",
            keywords=["seo", "growth"],
        )
        project = service.create_project(ProjectCreateRequest(name="Market Default Connection", intake=intake))

        with service.database.session() as session:
            connections = service._load_project_connections(session, project.project_id, intake)  # noqa: SLF001 - intentional connection coverage check

        providers = {connection.provider.value for connection in connections}
        self.assertTrue({"trend", "news", "qa"}.issubset(providers))
        market_connections = [connection for connection in connections if connection.provider.value in {"trend", "news", "qa"}]
        self.assertTrue(all(connection.label in {"Trend", "News", "QA"} for connection in market_connections))

    def test_default_project_connections_include_market_providers_from_project_rules(self) -> None:
        trend_path = Path(self._tempdir.name) / "trend-project-rule-connection.json"
        news_path = Path(self._tempdir.name) / "news-project-rule-connection.json"
        qa_path = Path(self._tempdir.name) / "qa-project-rule-connection.json"
        trend_path.write_text(json.dumps({"id": "trend-project-rule-connection", "topics": ["seo"]}), encoding="utf-8")
        news_path.write_text(json.dumps({"id": "news-project-rule-connection", "headlines": ["growth update"]}), encoding="utf-8")
        qa_path.write_text(json.dumps({"id": "qa-project-rule-connection", "questions": ["what is seo"]}), encoding="utf-8")

        service = self._service()
        intake = SiteIntake(
            url="https://market-rule-connection.example",
            site_name="Market Rule Connection",
            keywords=["seo", "growth"],
            approval_rules={
                "trendProviderUrl": trend_path.as_uri(),
                "trendAccessToken": "trend-token",
                "newsProviderUrl": news_path.as_uri(),
                "newsAccessToken": "news-token",
                "qaProviderUrl": qa_path.as_uri(),
                "qaAccessToken": "qa-token",
            },
        )
        project = service.create_project(ProjectCreateRequest(name="Market Rule Connection", intake=intake))

        with service.database.session() as session:
            connections = service._load_project_connections(session, project.project_id, intake)  # noqa: SLF001 - intentional connection coverage check

        providers = {connection.provider.value for connection in connections}
        self.assertTrue({"trend", "news", "qa"}.issubset(providers))
        market_connections = [connection for connection in connections if connection.provider.value in {"trend", "news", "qa"}]
        self.assertTrue(all(connection.status in {ConnectorStatus.synthetic, ConnectorStatus.missing_credentials, ConnectorStatus.unavailable} for connection in market_connections))
        self.assertTrue(all(connection.config.get("providerUrl") for connection in market_connections))

    def test_default_project_connections_include_playwright_from_project_rules(self) -> None:
        playwright_path = Path(self._tempdir.name) / "playwright-project-rule-connection.json"
        playwright_path.write_text(
            json.dumps(
                {
                    "title": "Playwright Project Rule",
                    "description": "Project-level playwright evidence",
                    "headings": ["intro", "details"],
                    "wordCount": 1200,
                }
            ),
            encoding="utf-8",
        )

        service = self._service()
        intake = SiteIntake(
            url="https://playwright-rule-connection.example",
            site_name="Playwright Rule Connection",
            keywords=["crawl", "preview"],
            approval_rules={
                "playwrightEnabled": True,
                "playwrightProviderUrl": playwright_path.as_uri(),
                "playwrightAccessToken": "playwright-token",
                "playwrightTimeoutMs": 7500,
                "playwrightAuthHeader": "X-Playwright-Token",
                "playwrightJsEnabled": True,
            },
        )
        project = service.create_project(ProjectCreateRequest(name="Playwright Rule Connection", intake=intake))

        with service.database.session() as session:
            connections = service._load_project_connections(session, project.project_id, intake)  # noqa: SLF001 - intentional connection coverage check

        playwright_connections = [connection for connection in connections if connection.provider.value == "playwright"]
        self.assertEqual(len(playwright_connections), 1)
        connection = playwright_connections[0]
        self.assertTrue(connection.enabled)
        self.assertEqual(connection.config.get("providerUrl"), playwright_path.as_uri())
        self.assertEqual(connection.config.get("timeoutMs"), 7500)
        self.assertEqual(connection.config.get("authHeader"), "X-Playwright-Token")
        self.assertTrue(connection.config.get("jsEnabled"))
        self.assertNotEqual(connection.status, ConnectorStatus.unavailable)

    def test_default_project_connections_include_provider_credentials_from_project_rules(self) -> None:
        service = self._service()
        intake = SiteIntake(
            url="https://provider-rules-connection.example",
            site_name="Provider Rules Connection",
            keywords=["seo", "ads"],
            repo_url="https://github.com/example/repo",
            cms_name="wordpress",
            approval_rules={
                "searchConsoleAccessToken": "sc-token",
                "ga4AccessToken": "ga4-token",
                "githubAccessToken": "gh-token",
                "githubBranch": "release",
                "cmsDraftEndpoint": "https://cms-provider.example/drafts",
                "cmsAccessToken": "cms-token",
                "scriptProviderUrl": "https://script-provider.example/deploy",
                "scriptAccessToken": "script-token",
                "adNetworkProviderUrl": "https://ad-network-provider.example/metrics",
                "adNetworkProviderUrls": [
                    "https://ad-network-provider-primary.example/metrics",
                    "https://ad-network-provider-secondary.example/metrics",
                ],
                "adNetworkAccessToken": "ad-token",
                "adNetworkAccountId": "acct_123",
                "adNetworkProviderTimeoutMs": 9100,
                "adNetworkAuthHeader": "X-Ad-Auth",
            },
        )
        project = service.create_project(ProjectCreateRequest(name="Provider Rules Connection", intake=intake))

        with service.database.session() as session:
            connections = service._load_project_connections(session, project.project_id, intake)  # noqa: SLF001 - intentional connection coverage check

        by_provider = {connection.provider.value: connection for connection in connections}
        self.assertEqual(by_provider["search_console"].status, ConnectorStatus.synthetic)
        self.assertEqual(by_provider["ga4"].status, ConnectorStatus.synthetic)
        self.assertEqual(by_provider["github"].status, ConnectorStatus.synthetic)
        self.assertEqual(by_provider["cms"].status, ConnectorStatus.synthetic)
        self.assertEqual(by_provider["script_api"].status, ConnectorStatus.synthetic)
        self.assertEqual(by_provider["ad_network"].status, ConnectorStatus.synthetic)

        self.assertEqual(by_provider["github"].config.get("branch"), "release")
        self.assertEqual(by_provider["cms"].config.get("draftEndpoint"), "https://cms-provider.example/drafts")
        self.assertEqual(by_provider["script_api"].config.get("endpoint"), "https://script-provider.example/deploy")
        self.assertEqual(by_provider["ad_network"].config.get("endpoint"), "https://ad-network-provider.example/metrics")
        self.assertEqual(
            by_provider["ad_network"].config.get("endpoints"),
            [
                "https://ad-network-provider-primary.example/metrics",
                "https://ad-network-provider-secondary.example/metrics",
            ],
        )
        self.assertEqual(by_provider["ad_network"].config.get("accountId"), "acct_123")
        self.assertEqual(by_provider["ad_network"].config.get("timeoutMs"), 9100)
        self.assertEqual(by_provider["ad_network"].config.get("authHeader"), "X-Ad-Auth")


if __name__ == "__main__":
    unittest.main()
