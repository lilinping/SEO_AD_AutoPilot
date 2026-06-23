from fastapi.testclient import TestClient

from apps.api.seo_ad_autopilot.app import create_app
from apps.api.seo_ad_autopilot.models import ProjectCreateRequest, SiteIntake


def test_overview_uses_camel_case_payloads(isolated_service) -> None:
    service = isolated_service
    project = service.create_project(
        ProjectCreateRequest(
            name="Northstar",
            intake=SiteIntake(
                url="https://northstar-media.example",
                site_name="Northstar Media",
                repo_url="https://github.com/example/northstar-media",
                brand_whitelist=["Northstar"],
            ),
        )
    )
    service.run_analysis(
        project.project_id,
        SiteIntake(
            url="https://northstar-media.example",
            site_name="Northstar Media",
            repo_url="https://github.com/example/northstar-media",
            brand_whitelist=["Northstar"],
        ),
    )

    app = create_app(service)
    with TestClient(app) as client:
        response = client.get("/api/overview")

    assert response.status_code == 200
    payload = response.json()
    assert "generatedAt" in payload
    assert "projects" in payload
    assert "policy" in payload
    assert payload["projects"][0]["projectId"]
    assert "approvalRequiredThreshold" in payload["policy"]


def test_project_detail_returns_workflow_bundle(isolated_service) -> None:
    service = isolated_service
    project = service.create_project(
        ProjectCreateRequest(
            name="LedgerFlow",
            intake=SiteIntake(
                url="https://ledgerflow.example",
                site_name="LedgerFlow",
                cms_name="webflow",
                brand_whitelist=["LedgerFlow"],
            ),
        )
    )
    bundle = service.run_analysis(
        project.project_id,
        SiteIntake(
            url="https://ledgerflow.example",
            site_name="LedgerFlow",
            cms_name="webflow",
            brand_whitelist=["LedgerFlow"],
        ),
    )

    app = create_app(service)
    with TestClient(app) as client:
        response = client.get(f"/api/projects/{bundle.project.project_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project"]["projectId"] == bundle.project.project_id
    assert payload["workflow"]["approvalRequest"]["approvalId"]
    assert "contentStrategy" in payload
    assert "marketSignals" in payload["contentStrategy"]
    assert isinstance(payload["contentStrategy"]["marketSignals"], list)
    assert "adAudit" in payload
    assert "negativeConditions" in payload["adAudit"]
    assert isinstance(payload["adAudit"]["negativeConditions"], list)
    assert "adProviderRef" in payload["adAudit"]
    assert "adProviderFamily" in payload["adAudit"]
    assert "adProviderName" in payload["adAudit"]
    assert "adInventoryStatus" in payload["adAudit"]
    assert "adImpressionsDaily" in payload["adAudit"]
    assert "adClicksDaily" in payload["adAudit"]
    assert "adCtr" in payload["adAudit"]
    assert "adFillRate" in payload["adAudit"]
    assert "adRpm" in payload["adAudit"]
    assert "adRevenueSettledDaily" in payload["adAudit"]
    assert "adRevenueSettlementWindow" in payload["adAudit"]
    assert "adRevenueCurrency" in payload["adAudit"]
    assert "adPolicyTier" in payload["adAudit"]
    assert "adPayoutThreshold" in payload["adAudit"]
    assert "adGeoCoverage" in payload["adAudit"]
    assert "adProviderProgram" in payload["adAudit"]
    assert "marketEvidence" in payload
    assert "summaries" in payload["marketEvidence"]
    assert isinstance(payload["marketEvidence"]["summaries"], list)
    assert "connectedEndpoints" in payload["marketEvidence"]["summaries"][0]
    assert "connectedSourceRefs" in payload["marketEvidence"]["summaries"][0]
    assert "averageLatencyMs" in payload["marketEvidence"]["summaries"][0]
    assert "writebackSummary" in payload["workflow"]["deployment"]
    assert isinstance(payload["workflow"]["deployment"]["writebackSummary"], dict)
    assert "strictMode" in payload["workflow"]["deployment"]
    assert "verifiedPatch" in payload["workflow"]["deployment"]
    assert "successfulEndpoints" in payload["workflow"]["deployment"]["writebackSummary"]
    assert "failedEndpoints" in payload["workflow"]["deployment"]["writebackSummary"]
    assert "averageLatencyMs" in payload["workflow"]["deployment"]["writebackSummary"]
    assert "deploymentHistory" in payload
    assert isinstance(payload["deploymentHistory"], list)
    assert payload["deploymentHistory"]
    assert "deployment" in payload["deploymentHistory"][0]
    assert "deploymentId" in payload["deploymentHistory"][0]["deployment"]
    assert "strictMode" in payload["deploymentHistory"][0]["deployment"]
    assert "verifiedPatch" in payload["deploymentHistory"][0]["deployment"]
    assert "taskStatus" in payload["deploymentHistory"][0]
    assert "approvalStatus" in payload["deploymentHistory"][0]
    assert "updatedAt" in payload["deploymentHistory"][0]
    assert "rollbackHistory" in payload
    assert isinstance(payload["rollbackHistory"], list)
    assert payload["rollbackHistory"]
    assert "rollback" in payload["rollbackHistory"][0]
    assert "rollbackId" in payload["rollbackHistory"][0]["rollback"]
    assert "recentEvidenceLabel" in payload["connections"][0]
    assert "recentEvidenceRef" in payload["connections"][0]
    assert "recentEvidenceAt" in payload["connections"][0]
    assert "sourceMetricsSummary" in payload["workflow"]["metricSnapshot"]
    assert isinstance(payload["workflow"]["metricSnapshot"]["sourceMetricsSummary"], list)
    assert payload["workflow"]["metricSnapshot"]["sourceMetricsSummary"]

    with TestClient(app) as client:
        deployments_response = client.get(f"/api/projects/{bundle.project.project_id}/deployments")
        rollbacks_response = client.get(f"/api/projects/{bundle.project.project_id}/rollbacks")
        evidence_response = client.get(f"/api/projects/{bundle.project.project_id}/connections/evidence")
        workspace_evidence_response = client.get("/api/connectors/evidence")
        workspace_evidence_filtered_response = client.get("/api/connectors/evidence", params={"provider": "ga4", "mode": "real", "strictOnly": "true", "limit": 5})

    assert deployments_response.status_code == 200
    assert rollbacks_response.status_code == 200
    assert evidence_response.status_code == 200
    assert workspace_evidence_response.status_code == 200
    assert workspace_evidence_filtered_response.status_code == 200
    assert deployments_response.json()["projectId"] == bundle.project.project_id
    assert "entries" in deployments_response.json()
    assert rollbacks_response.json()["projectId"] == bundle.project.project_id
    assert "entries" in rollbacks_response.json()
    assert evidence_response.json()["projectId"] == bundle.project.project_id
    assert "entries" in evidence_response.json()
    assert "entries" in workspace_evidence_response.json()
    assert "providerSummaries" in workspace_evidence_response.json()
    assert isinstance(workspace_evidence_response.json()["providerSummaries"], list)
    filtered_payload = workspace_evidence_filtered_response.json()
    assert filtered_payload["total"] <= 5
    assert all(item["provider"] == "ga4" for item in filtered_payload["entries"])
    assert all(item["providerMode"] == "real" for item in filtered_payload["entries"])
    assert all(bool(item["strictEligible"]) for item in filtered_payload["entries"])


def test_sync_and_connections_endpoints_require_api_key(isolated_service) -> None:
    service = isolated_service
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
        missing_key = client.post("/api/projects", json=project_payload)
        assert missing_key.status_code == 401

        created = client.post("/api/projects", json=project_payload, headers={"X-API-Key": "dev-key"})
        assert created.status_code == 200
        project_id = created.json()["projectId"]

        forbidden = client.post(f"/api/projects/{project_id}/sync", headers={"X-API-Key": "wrong"})
        assert forbidden.status_code == 403

        sync = client.post(f"/api/projects/{project_id}/sync", headers={"X-API-Key": "dev-key"})
        assert sync.status_code == 200
        sync_payload = sync.json()
        assert sync_payload["ingestionReport"]["reportId"]
        assert sync_payload["deployment"]["status"] == "failed"
        assert sync_payload["deployment"]["fallbackReason"]
        assert sync_payload["deployment"]["failureCode"]

        connections = client.get(f"/api/projects/{project_id}/connections")
        assert connections.status_code == 200
        connection_payload = connections.json()
        assert connection_payload["projectId"] == project_id
        assert connection_payload["connections"]
        assert connection_payload["state"]["lastSyncAt"]
        assert any(item.get("lastSuccessAt") or item.get("lastErrorAt") for item in connection_payload["connections"])
        assert all(item.get("providerMode") in {"real", "fallback", "unconfigured"} for item in connection_payload["connections"])
        assert all(isinstance(item.get("strictEligible"), bool) for item in connection_payload["connections"])

        runs = client.get(f"/api/projects/{project_id}/runs")
        assert runs.status_code == 200
        assert runs.json()
        runs_filtered = client.get(
            f"/api/projects/{project_id}/runs",
            params={"trigger": "manual", "status": "failed", "limit": 1},
        )
        assert runs_filtered.status_code == 200
        filtered_payload = runs_filtered.json()
        assert len(filtered_payload) <= 1
        assert all(item["trigger"] == "manual" for item in filtered_payload)
        assert all(item["status"] == "failed" for item in filtered_payload)

        failure_report = client.get("/api/connectors/failures")
        assert failure_report.status_code == 200
        assert "totalFailures" in failure_report.json()
        for entry in failure_report.json().get("entries", []):
            assert entry.get("category") in {"auth", "permission", "rate_limit", "network", "validation", "config", "unavailable", "other"}

        retry_blocked = client.post("/api/connectors/retry", json={"categories": ["network"], "projectIds": [project_id]})
        assert retry_blocked.status_code == 401
        retry = client.post(
            "/api/connectors/retry",
            json={"categories": ["network"], "projectIds": [project_id], "providers": [], "retryableOnly": True, "maxRetries": 10},
            headers={"X-API-Key": "dev-key"},
        )
        assert retry.status_code == 200
        retry_payload = retry.json()
        assert "attempted" in retry_payload

        retry_history = client.get("/api/connectors/retry/history")
        assert retry_history.status_code == 200
        assert "entries" in retry_history.json()

        remediations = client.get("/api/connectors/remediations")
        assert remediations.status_code == 200
        payload = remediations.json()
        assert "items" in payload
        for item in payload.get("items", []):
            assert item.get("priority") in {"p0", "p1", "p2", "p3"}
            assert item.get("quickActionPath")
            assert item.get("quickActionLabel")
            assert item.get("alertSeverity") in {"critical", "warning", "info"}
            assert isinstance(item.get("blocking"), bool)
        remediations_blocking = client.get("/api/connectors/remediations", params={"blocking": "true", "limit": 5})
        assert remediations_blocking.status_code == 200
        blocking_payload = remediations_blocking.json()
        assert all(item.get("blocking") is True for item in blocking_payload.get("items", []))
        remediations_warning = client.get("/api/connectors/remediations", params={"severity": "warning"})
        assert remediations_warning.status_code == 200
        warning_payload = remediations_warning.json()
        assert all(item.get("alertSeverity") == "warning" for item in warning_payload.get("items", []))
        remediations_project = client.get("/api/connectors/remediations", params={"projectId": project_id})
        assert remediations_project.status_code == 200
        project_payload = remediations_project.json()
        assert all(project_id in item.get("projectIds", []) for item in project_payload.get("items", []))
        remediations_invalid = client.get("/api/connectors/remediations", params={"severity": "invalid"})
        assert remediations_invalid.status_code == 422

        alerts_blocked = client.get("/api/alerts")
        assert alerts_blocked.status_code == 401
        alerts = client.get("/api/alerts", headers={"X-API-Key": "dev-key"})
        assert alerts.status_code == 200
        alerts_payload = alerts.json()
        assert "blocking" in alerts_payload
        assert "recoverable" in alerts_payload
        emit_blocked = client.post("/api/alerts/emit")
        assert emit_blocked.status_code == 401
        emit = client.post("/api/alerts/emit", headers={"X-API-Key": "dev-key"})
        assert emit.status_code == 200
        emit_payload = emit.json()
        assert "blocking" in emit_payload
        assert "recoverable" in emit_payload
        latest_alerts = client.get("/api/alerts/latest")
        assert latest_alerts.status_code == 200
        latest_alerts_payload = latest_alerts.json()
        assert "blocking" in latest_alerts_payload
        assert "recoverable" in latest_alerts_payload
        assert "notes" in latest_alerts_payload
        assert any("Read-only latest snapshot returned" in item or "No historical snapshot found" in item for item in latest_alerts_payload["notes"])
        oncall_coverage = client.get("/api/alerts/oncall/coverage")
        assert oncall_coverage.status_code == 200
        oncall_payload = oncall_coverage.json()
        assert "items" in oncall_payload

        deliveries = client.get("/api/alerts/deliveries", params={"limit": 5})
        assert deliveries.status_code == 200
        deliveries_payload = deliveries.json()
        assert "entries" in deliveries_payload
        assert deliveries_payload["total"] >= 0
        emit_status = client.get("/api/alerts/emit/status")
        assert emit_status.status_code == 200
        emit_status_payload = emit_status.json()
        assert "cooldownSeconds" in emit_status_payload
        assert "executedCount24h" in emit_status_payload
        assert "suppressedCount24h" in emit_status_payload
        assert "notes" in emit_status_payload
        emit_history = client.get("/api/alerts/emit/history", params={"limit": 5})
        assert emit_history.status_code == 200
        emit_history_payload = emit_history.json()
        assert "total" in emit_history_payload
        assert "executed" in emit_history_payload
        assert "suppressed" in emit_history_payload
        assert "entries" in emit_history_payload

        tested = client.post(f"/api/projects/{project_id}/connections/test", headers={"X-API-Key": "dev-key"})
        assert tested.status_code == 200
        tested_payload = tested.json()
        assert "strictMode" in tested_payload
        assert "strictBlocked" in tested_payload
        assert "strictGapCount" in tested_payload
        assert "strictBlockers" in tested_payload


def test_prompt_registry_write_and_activate(isolated_service) -> None:
    app = create_app(isolated_service)
    with TestClient(app) as client:
        baseline = client.get("/api/prompts")
        assert baseline.status_code == 200
        baseline_payload = baseline.json()
        assert baseline_payload["versions"]

        unauthorized = client.post(
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
        assert unauthorized.status_code == 401

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
        assert upserted.status_code == 200
        upserted_payload = upserted.json()
        assert any(
            item["promptId"] == "query-opportunity-discovery" and item["version"] == "v1.1.1"
            for item in upserted_payload["versions"]
        )

        activated = client.post(
            "/api/prompts/query-opportunity-discovery/activate",
            json={"version": "v1.1.1"},
            headers={"X-API-Key": "dev-key"},
        )
        assert activated.status_code == 200
        active_versions = [
            item for item in activated.json()["versions"] if item["promptId"] == "query-opportunity-discovery" and item["status"] == "active"
        ]
        assert len(active_versions) == 1
        assert active_versions[0]["version"] == "v1.1.1"

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
        assert invalid.status_code == 422
        tested_payload = tested.json()
        assert tested_payload["connectionHealth"] in {"healthy", "degraded", "unavailable", "unknown"}
        assert any(item.get("lastSuccessAt") or item.get("lastErrorAt") for item in tested_payload["connections"])
        assert all(item.get("providerMode") in {"real", "fallback", "unconfigured"} for item in tested_payload["connections"])
        assert all(isinstance(item.get("strictEligible"), bool) for item in tested_payload["connections"])
        assert any(
            connection.get("details", {}).get("fallbackReason")
            for connection in tested_payload["connections"]
            if connection.get("status") != "connected"
        )

        health = client.get(f"/api/projects/{project_id}/connectors/health")
        assert health.status_code == 200
        health_payload = health.json()
        assert health_payload["projectId"] == project_id
        assert isinstance(health_payload["connections"], list)
        assert health_payload["totalConnectionCount"] >= health_payload["realConnectionCount"]
        assert health_payload["totalConnectionCount"] >= health_payload["fallbackConnectionCount"]
        assert health_payload["totalConnectionCount"] >= health_payload["unconfiguredConnectionCount"]
        assert health_payload["totalConnectionCount"] >= health_payload["strictEligibleCount"]
        assert health_payload["antiBotBlockedCount"] >= 0
        assert health_payload["manualInterventionRequiredCount"] >= 0
        assert "readRealLastEvidenceAt" in health_payload
        assert "writeRealLastEvidenceAt" in health_payload

        workspace_health = client.get("/api/connectors/health")
        assert workspace_health.status_code == 200
        workspace_health_payload = workspace_health.json()
        assert workspace_health_payload["projectCount"] >= 1
        assert isinstance(workspace_health_payload["projects"], list)
        assert workspace_health_payload["totalConnectionCount"] >= workspace_health_payload["realConnectionCount"]
        assert workspace_health_payload["totalConnectionCount"] >= workspace_health_payload["fallbackConnectionCount"]
        assert workspace_health_payload["totalConnectionCount"] >= workspace_health_payload["unconfiguredConnectionCount"]
        assert workspace_health_payload["totalConnectionCount"] >= workspace_health_payload["strictEligibleCount"]
        assert workspace_health_payload["strictGapCount"] >= 0
        assert workspace_health_payload["antiBotBlockedConnectionCount"] >= 0
        assert workspace_health_payload["antiBotManualInterventionCount"] >= 0
        assert workspace_health_payload["readConnectionCount"] >= 0
        assert workspace_health_payload["readRealConnectionCount"] >= 0
        assert workspace_health_payload["readStrictEligibleCount"] >= 0
        assert float(workspace_health_payload["readRealCoveragePercent"]) >= 0
        assert float(workspace_health_payload["readStrictCoveragePercent"]) >= 0
        assert "readRealLastEvidenceAt" in workspace_health_payload
        assert workspace_health_payload["writeConnectionCount"] >= 0
        assert workspace_health_payload["writeRealConnectionCount"] >= 0
        assert workspace_health_payload["writeStrictEligibleCount"] >= 0
        assert float(workspace_health_payload["writeRealCoveragePercent"]) >= 0
        assert float(workspace_health_payload["writeStrictCoveragePercent"]) >= 0
        assert "writeRealLastEvidenceAt" in workspace_health_payload
        assert workspace_health_payload["realProviderCount"] >= 0
        assert float(workspace_health_payload["realProviderRatePercent"]) >= 0
        assert workspace_health_payload["zeroRealProviderCount"] >= 0
        assert float(workspace_health_payload["zeroRealProviderRatePercent"]) >= 0
        assert isinstance(workspace_health_payload["zeroRealProviders"], list)
        assert workspace_health_payload["zeroStrictProviderCount"] >= 0
        assert float(workspace_health_payload["zeroStrictProviderRatePercent"]) >= 0
        assert isinstance(workspace_health_payload["zeroStrictProviders"], list)
        assert workspace_health_payload["strictReadyProviderCount"] >= 0
        assert float(workspace_health_payload["strictReadyProviderRatePercent"]) >= 0
        assert isinstance(workspace_health_payload["strictReadyProviders"], list)
        assert workspace_health_payload["partialStrictProviderCount"] >= 0
        assert float(workspace_health_payload["partialStrictProviderRatePercent"]) >= 0
        assert isinstance(workspace_health_payload["partialStrictProviders"], list)
        assert workspace_health_payload["fullyStrictProviderCount"] >= 0
        assert float(workspace_health_payload["fullyStrictProviderRatePercent"]) >= 0
        assert isinstance(workspace_health_payload["fullyStrictProviders"], list)
        assert isinstance(workspace_health_payload["providerCoverage"], list)
        if workspace_health_payload["providerCoverage"]:
            first_provider = workspace_health_payload["providerCoverage"][0]
            assert first_provider["antiBotBlockedCount"] >= 0
            assert first_provider["manualInterventionRequiredCount"] >= 0
        assert isinstance(workspace_health_payload["topBlockingProviders"], list)
        assert isinstance(workspace_health_payload["topStrictGapProviders"], list)
        assert isinstance(workspace_health_payload["topStrictReadyProviders"], list)
        assert any(item.get("provider") == "search_console" for item in workspace_health_payload["providerCoverage"])
        assert all(item.get("affectedProjectCount", 0) >= item.get("blockingProjectCount", 0) for item in workspace_health_payload["providerCoverage"])
        assert all(item.get("affectedProjectCount", 0) >= item.get("strictReadyProjectCount", 0) for item in workspace_health_payload["providerCoverage"])
        assert all(float(item.get("strictReadyProjectRatePercent", 0)) >= 0 for item in workspace_health_payload["providerCoverage"])
        assert all(float(item.get("blockingProjectRatePercent", 0)) >= 0 for item in workspace_health_payload["providerCoverage"])
        assert all(item.get("strictGapCount", 0) >= 0 for item in workspace_health_payload["providerCoverage"])
        assert all(item.get("blockingProjectCount", 0) >= 0 for item in workspace_health_payload["topBlockingProviders"])
        assert all(item.get("strictGapCount", 0) >= 0 for item in workspace_health_payload["topStrictGapProviders"])
        assert all(float(item.get("strictCoveragePercent", 0)) >= 0 for item in workspace_health_payload["topStrictReadyProviders"])
        assert all(float(item.get("realCoveragePercent", 0)) >= 0 for item in workspace_health_payload["providerCoverage"])
        assert all(float(item.get("strictCoveragePercent", 0)) >= 0 for item in workspace_health_payload["providerCoverage"])
        assert all(float(item.get("blockingRatePercent", 0)) >= 0 for item in workspace_health_payload["providerCoverage"])
        assert all(
            isinstance(item.get("affectedProjectIds"), list)
            and isinstance(item.get("strictReadyProjectIds"), list)
            and isinstance(item.get("blockingProjectIds"), list)
            for item in workspace_health_payload["providerCoverage"]
        )
        assert all(
            isinstance(item.get("affectedProjects"), list)
            and isinstance(item.get("strictReadyProjects"), list)
            and isinstance(item.get("blockingProjects"), list)
            for item in workspace_health_payload["providerCoverage"]
        )
        assert all("primaryBlockingReason" in item for item in workspace_health_payload["providerCoverage"])
        assert all("primaryFailureCategory" in item for item in workspace_health_payload["providerCoverage"])
        assert all("suggestedActionPath" in item and "suggestedActionLabel" in item for item in workspace_health_payload["providerCoverage"])
        assert any(item.get("projectId") == project_id for item in workspace_health_payload["projects"])

        workspace_connection_history = client.get("/api/connectors/history", params={"limit": 5})
        assert workspace_connection_history.status_code == 200
        workspace_connection_history_payload = workspace_connection_history.json()
        assert isinstance(workspace_connection_history_payload["entries"], list)
        assert any(item.get("projectId") == project_id for item in workspace_connection_history_payload["entries"])
        workspace_connection_history_filtered = client.get(
            "/api/connectors/history",
            params={"limit": 5, "projectId": project_id, "provider": "search_console", "action": "connector.probe"},
        )
        assert workspace_connection_history_filtered.status_code == 200
        filtered_entries = workspace_connection_history_filtered.json()["entries"]
        assert all(item.get("projectId") == project_id for item in filtered_entries)
        assert all(item.get("provider") == "search_console" for item in filtered_entries)
        assert all(item.get("action") == "connector.probe" for item in filtered_entries)
        workspace_connection_history_invalid_action = client.get(
            "/api/connectors/history",
            params={"action": "invalid-action"},
        )
        assert workspace_connection_history_invalid_action.status_code == 422

        connection_history = client.get(f"/api/projects/{project_id}/connections/history", params={"limit": 5})
        assert connection_history.status_code == 200
        connection_history_payload = connection_history.json()
        assert connection_history_payload["projectId"] == project_id
        assert isinstance(connection_history_payload["entries"], list)
        assert any(item.get("action") in {"connector.probe", "connector.refreshed"} for item in connection_history_payload["entries"])
        assert any("authSource" in item for item in connection_history_payload["entries"])

        refresh_forbidden = client.post(f"/api/projects/{project_id}/connectors/search_console/refresh", headers={"X-API-Key": "wrong"})
        assert refresh_forbidden.status_code == 403
        refresh = client.post(f"/api/projects/{project_id}/connectors/search_console/refresh", headers={"X-API-Key": "dev-key"})
        assert refresh.status_code == 200
        refresh_payload = refresh.json()
        assert refresh_payload["provider"] == "search_console"
        assert refresh_payload["status"] in {"connected", "missing_credentials", "unavailable", "synthetic", "error"}
        assert "fallbackReason" in refresh_payload["connection"]["details"] or refresh_payload["status"] == "connected"
        if refresh_payload["status"] in {"missing_credentials", "error"}:
            assert refresh_payload["connection"]["details"].get("errorCode")
        refreshed_history = client.get(f"/api/projects/{project_id}/connections/history", params={"limit": 10})
        assert refreshed_history.status_code == 200
        refreshed_entries = [
            item for item in refreshed_history.json()["entries"] if item.get("action") == "connector.refreshed"
        ]
        assert refreshed_entries
        assert all("authSource" in item for item in refreshed_entries)
        bulk_refresh_forbidden = client.post(
            "/api/bulk/projects/connectors/search_console/refresh",
            json={"projectIds": [project_id]},
        )
        assert bulk_refresh_forbidden.status_code == 401
        bulk_refresh = client.post(
            "/api/bulk/projects/connectors/search_console/refresh",
            json={"projectIds": [project_id, "missing-project"]},
            headers={"X-API-Key": "dev-key"},
        )
        assert bulk_refresh.status_code == 200
        bulk_refresh_payload = bulk_refresh.json()
        assert bulk_refresh_payload["provider"] == "search_console"
        assert bulk_refresh_payload["refreshedCount"] == 1
        assert bulk_refresh_payload["skippedProjectIds"] == ["missing-project"]
        assert len(bulk_refresh_payload["results"]) == 1
        strict_gap_refresh_forbidden = client.post("/api/bulk/connectors/strict-gap/refresh", json={"projectIds": [project_id]})
        assert strict_gap_refresh_forbidden.status_code == 401
        strict_gap_refresh = client.post(
            "/api/bulk/connectors/strict-gap/refresh",
            json={"projectIds": [project_id], "maxProviders": 3},
            headers={"X-API-Key": "dev-key"},
        )
        assert strict_gap_refresh.status_code == 200
        strict_gap_refresh_payload = strict_gap_refresh.json()
        assert "providerCount" in strict_gap_refresh_payload
        assert "refreshedCount" in strict_gap_refresh_payload
        assert "providerResults" in strict_gap_refresh_payload
        blocking_refresh_forbidden = client.post("/api/bulk/connectors/blocking/refresh", json={"projectIds": [project_id]})
        assert blocking_refresh_forbidden.status_code == 401
        blocking_refresh = client.post(
            "/api/bulk/connectors/blocking/refresh",
            json={"projectIds": [project_id], "maxProviders": 3},
            headers={"X-API-Key": "dev-key"},
        )
        assert blocking_refresh.status_code == 200
        blocking_refresh_payload = blocking_refresh.json()
        assert "providerCount" in blocking_refresh_payload
        assert "providerResults" in blocking_refresh_payload
        bulk_action_history = client.get("/api/connectors/bulk-actions/history", params={"limit": 5})
        assert bulk_action_history.status_code == 200
        bulk_action_history_payload = bulk_action_history.json()
        assert "entries" in bulk_action_history_payload
        assert isinstance(bulk_action_history_payload["entries"], list)
        bulk_action_history_filtered = client.get(
            "/api/connectors/bulk-actions/history",
            params={"limit": 5, "action": "blocking"},
        )
        assert bulk_action_history_filtered.status_code == 200
        bulk_action_history_provider = client.get(
            "/api/connectors/bulk-actions/history",
            params={"limit": 5, "provider": "search_console"},
        )
        assert bulk_action_history_provider.status_code == 200
        provider_entries = bulk_action_history_provider.json()["entries"]
        assert isinstance(provider_entries, list)
        assert all("search_console" in [str(item).lower() for item in entry.get("providers", [])] for entry in provider_entries)
        bulk_action_history_project = client.get(
            "/api/connectors/bulk-actions/history",
            params={"limit": 5, "projectId": project_id},
        )
        assert bulk_action_history_project.status_code == 200
        project_entries = bulk_action_history_project.json()["entries"]
        assert isinstance(project_entries, list)
        assert all(project_id in entry.get("projectIds", []) for entry in project_entries)

        visual_runs = client.get("/api/visual-regressions/runs")
        visual_health = client.get("/api/visual-regressions/health")
        visual_farm_status = client.get("/api/visual-farm/status")
        visual_farm_probe_blocked = client.get("/api/visual-farm/probe")
        assert visual_farm_probe_blocked.status_code == 401
        visual_farm_probe = client.get("/api/visual-farm/probe", headers={"X-API-Key": "dev-key"})
        visual_farm_probe_history = client.get("/api/visual-farm/probe/history", params={"limit": 5})
        assert visual_runs.status_code == 200
        assert visual_health.status_code == 200
        assert visual_farm_status.status_code == 200
        assert visual_farm_probe.status_code == 200
        assert visual_farm_probe_history.status_code == 200
        visual_runs_payload = visual_runs.json()
        visual_health_payload = visual_health.json()
        visual_farm_status_payload = visual_farm_status.json()
        visual_farm_probe_payload = visual_farm_probe.json()
        visual_farm_probe_history_payload = visual_farm_probe_history.json()
        assert visual_runs_payload["runs"]
        assert "strictMode" in visual_health_payload
        assert "configuredEndpointCount" in visual_health_payload
        assert "configuredEndpoints" in visual_health_payload
        assert "lastRunId" in visual_health_payload
        assert "lastRunFailedEndpoints" in visual_health_payload
        assert "failureBuckets" in visual_health_payload
        assert isinstance(visual_health_payload["failureBuckets"], list)
        run = visual_runs_payload["runs"][0]
        assert "failedCaseCount" in run
        assert "fallbackCaseCount" in run
        assert "notConfiguredCaseCount" in run
        assert "configuredEndpointCount" in run
        assert "configuredEndpoints" in run
        assert "attemptedEndpointCount" in run
        assert "attemptedEndpoints" in run
        assert "failedEndpoints" in run
        assert "providerAttemptCount" in run
        assert "strictPublishReady" in visual_farm_status_payload
        assert "configuredEndpointCount" in visual_farm_status_payload
        assert "connectedCount" in visual_farm_probe_payload
        assert "failedCount" in visual_farm_probe_payload
        assert isinstance(visual_farm_probe_payload["probes"], list)
        assert "entries" in visual_farm_probe_history_payload
        assert visual_farm_probe_history_payload["entries"]
        first_probe_entry = visual_farm_probe_history_payload["entries"][0]
        assert "auditId" in first_probe_entry
        assert "probedEndpointCount" in first_probe_entry
        assert "connectedCount" in first_probe_entry
        assert "failedCount" in first_probe_entry
        assert "spanId" in first_probe_entry
        assert "traceId" in first_probe_entry
        case = visual_runs_payload["runs"][0]["cases"][0]
        assert case["artifactRef"]
        assert case["taskId"]
        assert "projectId" in case

        visual_retry_blocked = client.post("/api/visual-regressions/retry", json={"categories": ["network"]})
        assert visual_retry_blocked.status_code == 401
        visual_retry = client.post(
            "/api/visual-regressions/retry",
            json={"categories": ["network", "unavailable"], "retryableOnly": True, "maxCases": 5},
            headers={"X-API-Key": "dev-key"},
        )
        assert visual_retry.status_code == 200
        visual_retry_payload = visual_retry.json()
        assert "attempted" in visual_retry_payload
        assert "rerunPassed" in visual_retry_payload
        assert "rerunFailed" in visual_retry_payload
        visual_retry_history = client.get("/api/visual-regressions/retry/history")
        assert visual_retry_history.status_code == 200
        assert "entries" in visual_retry_history.json()
        assert "projectName" in case
        assert "workflowTaskId" in case
        assert "deploymentArtifactRef" in case
        assert case.get("executionMode") in {"playwright", "manifest"}
        assert case.get("baselineArtifactRef")
        assert case.get("previewArtifactRef")
        assert case.get("diffArtifactRef")
        assert case.get("diffMethod") in {"pixel-rgba", "byte-fallback"}
        assert "mismatchPixels" in case
        assert "comparedPixels" in case
        assert "mismatchRatio" in case
        assert "thresholdDelta" in case
        assert "thresholdExceededPixels" in case
        assert "thresholdExceededRatio" in case

        worker_blocked = client.post("/api/worker/run-once")
        assert worker_blocked.status_code == 401
        worker_service_health = client.get("/api/worker/service/health")
        assert worker_service_health.status_code == 200
        worker_service_payload = worker_service_health.json()
        assert "status" in worker_service_payload
        assert "stateFileConfigured" in worker_service_payload
        worker_history = client.get("/api/worker/executions", params={"limit": 5})
        assert worker_history.status_code == 200
        worker_history_payload = worker_history.json()
        assert "entries" in worker_history_payload
        assert worker_history_payload["total"] >= 0
        worker_failed_history = client.get("/api/worker/executions", params={"status": "failed", "limit": 5})
        assert worker_failed_history.status_code == 200
        failed_entries = worker_failed_history.json()["entries"]
        assert all(item.get("status") == "failed" for item in failed_entries)
        worker_stage_history = client.get("/api/worker/executions", params={"stage": "monitor", "limit": 10})
        assert worker_stage_history.status_code == 200
        stage_entries = worker_stage_history.json()["entries"]
        assert all(item.get("stage") == "monitor" for item in stage_entries)
        worker_action_history = client.get("/api/worker/executions", params={"action": "worker.job.completed", "limit": 10})
        assert worker_action_history.status_code == 200
        action_entries = worker_action_history.json()["entries"]
        assert all(item.get("action") == "worker.job.completed" for item in action_entries)
        worker_project_history = client.get("/api/worker/executions", params={"projectId": project_id, "limit": 20})
        assert worker_project_history.status_code == 200
        project_entries = worker_project_history.json()["entries"]
        assert all(item.get("projectId") == project_id for item in project_entries)
        worker_invalid_status = client.get("/api/worker/executions", params={"status": "invalid"})
        assert worker_invalid_status.status_code == 422
