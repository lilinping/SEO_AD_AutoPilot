import unittest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from starlette.responses import Response

from apps.runtime_edge.main import EdgeSettings, RuntimeEdgeGateway, create_app


class RuntimeEdgeGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.settings = EdgeSettings(
            api_base_url="http://control-plane:8000",
            strict_routes_only=True,
            route_map_cache_seconds=30,
            request_timeout_seconds=5,
            api_key="edge-test-key",
            state_dir=Path(self.tempdir.name),
        )
        self.gateway = RuntimeEdgeGateway(self.settings)
        self.route = {
            "projectId": "project-1",
            "siteHost": "publisher.example",
            "proxyUrl": "http://control-plane:8000/api/projects/project-1/runtime-execute/proxy-strict",
        }

    def test_gateway_forwards_path_query_and_headers_to_control_plane_proxy(self) -> None:
        requests = []

        class FakeAsyncClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def request(self, method, url, **kwargs):
                requests.append({"method": method, "url": url, **kwargs})
                return httpx.Response(200, content=b"edge content")

        self.gateway._load_route_map = AsyncMock(return_value=[self.route])

        with patch("apps.runtime_edge.main.httpx.AsyncClient", FakeAsyncClient):
            with TestClient(create_app(settings=self.settings, gateway=self.gateway)) as client:
                response = client.get("/guides/seo?locale=en", headers={"Host": "publisher.example", "X-Trace-Id": "trace-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "edge content")
        self.assertEqual(requests[0]["method"], "GET")
        self.assertEqual(requests[0]["url"], "http://control-plane:8000/api/projects/project-1/runtime-execute/proxy-strict/guides/seo?locale=en")
        self.assertEqual(requests[0]["headers"]["Host"], "publisher.example")
        self.assertEqual(requests[0]["headers"]["X-Forwarded-Host"], "publisher.example")
        self.assertEqual(requests[0]["headers"]["X-SEO-AD-Edge-Project-Id"], "project-1")
        self.assertEqual(requests[0]["headers"]["x-trace-id"], "trace-1")

    def test_gateway_rejects_unknown_or_ambiguous_host(self) -> None:
        self.gateway._load_route_map = AsyncMock(return_value=[self.route, {**self.route, "projectId": "project-2"}])

        with TestClient(create_app(settings=self.settings, gateway=self.gateway)) as client:
            ambiguous = client.get("/", headers={"Host": "publisher.example"})
            unknown = client.get("/", headers={"Host": "unknown.example"})

        self.assertEqual(ambiguous.status_code, 404)
        self.assertEqual(unknown.status_code, 404)

    def test_gateway_only_allows_control_plane_proxy_urls(self) -> None:
        self.gateway._load_route_map = AsyncMock(return_value=[{**self.route, "proxyUrl": "https://untrusted.example/proxy"}])

        with TestClient(create_app(settings=self.settings, gateway=self.gateway)) as client:
            response = client.get("/", headers={"Host": "publisher.example"})

        self.assertEqual(response.status_code, 502)

    def test_deploy_is_authenticated_versioned_and_persisted(self) -> None:
        payload = {
            "projectId": "project-1",
            "strictRoutesOnly": True,
            "routes": [
                {
                    **self.route,
                    "publicPath": "/",
                }
            ],
        }
        with TestClient(create_app(settings=self.settings, gateway=self.gateway)) as client:
            self.assertEqual(client.post("/deploy", json=payload).status_code, 401)
            deployed = client.post("/deploy", json=payload, headers={"X-API-Key": "edge-test-key"})
            self.assertEqual(deployed.status_code, 200)
            deployment = deployed.json()
            self.assertEqual(deployment["status"], "executed")
            self.assertEqual(deployment["routeCount"], 1)
            self.assertTrue(deployment["artifactId"].startswith("edge-config-"))

            repeated = client.post("/deploy", json=payload, headers={"Authorization": "Bearer edge-test-key"})
            self.assertEqual(repeated.status_code, 200)
            self.assertEqual(repeated.json()["status"], "unchanged")
            self.assertEqual(repeated.json()["deploymentId"], deployment["deploymentId"])

            history = client.get("/deployments", headers={"X-API-Key": "edge-test-key"})
            self.assertEqual(history.status_code, 200)
            self.assertEqual(history.json()["total"], 1)
            ready = client.get("/readyz", headers={"X-API-Key": "edge-test-key"})
            self.assertEqual(ready.status_code, 200)
            self.assertEqual(ready.json()["routeCount"], 1)

        reloaded = RuntimeEdgeGateway(self.settings)
        self.assertEqual(reloaded.deployment_history()["activeDeploymentId"], deployment["deploymentId"])
        self.assertEqual(len(reloaded._active_deployment()["routes"]), 1)

    def test_project_deploy_merges_routes_and_longest_prefix_wins(self) -> None:
        workspace_payload = {
            "routes": [
                {**self.route, "publicPath": "/"},
                {
                    **self.route,
                    "projectId": "project-2",
                    "siteHost": "second.example",
                    "proxyUrl": "http://control-plane:8000/api/projects/project-2/runtime-execute/proxy-strict",
                    "publicPath": "/",
                },
            ]
        }
        project_payload = {
            "projectId": "project-1",
            "routes": [
                {**self.route, "publicPath": "/"},
                {
                    **self.route,
                    "publicPath": "/docs",
                    "proxyUrl": "http://control-plane:8000/api/projects/project-1/runtime-execute/proxy-strict",
                },
            ],
        }
        with TestClient(create_app(settings=self.settings, gateway=self.gateway)) as client:
            headers = {"X-API-Key": "edge-test-key"}
            self.assertEqual(client.post("/deploy", json=workspace_payload, headers=headers).status_code, 200)
            updated = client.post("/deploy", json=project_payload, headers=headers)
            self.assertEqual(updated.status_code, 200)
            self.assertEqual(updated.json()["routeCount"], 3)

        docs_route = __import__("asyncio").run(self.gateway.route_for_request("publisher.example", "/docs/guide"))
        root_route = __import__("asyncio").run(self.gateway.route_for_request("publisher.example", "/pricing"))
        second_route = __import__("asyncio").run(self.gateway.route_for_request("second.example", "/"))
        self.assertEqual(docs_route["publicPath"], "/docs")
        self.assertEqual(root_route["publicPath"], "/")
        self.assertEqual(second_route["projectId"], "project-2")

    def test_rollback_restores_previous_snapshot_and_rejects_invalid_routes(self) -> None:
        headers = {"X-API-Key": "edge-test-key"}
        first = {"routes": [{**self.route, "publicPath": "/"}]}
        second = {
            "routes": [
                {
                    **self.route,
                    "siteHost": "new.example",
                    "publicPath": "/",
                }
            ]
        }
        invalid = {"routes": [{**self.route, "proxyUrl": "https://untrusted.example/proxy"}]}
        duplicate = {"routes": [{**self.route}, {**self.route, "projectId": "project-2"}]}
        with TestClient(create_app(settings=self.settings, gateway=self.gateway)) as client:
            first_response = client.post("/deploy", json=first, headers=headers)
            second_response = client.post("/deploy", json=second, headers=headers)
            self.assertEqual(first_response.status_code, 200)
            self.assertEqual(second_response.status_code, 200)
            self.assertEqual(client.post("/deploy", json=invalid, headers=headers).status_code, 422)
            self.assertEqual(client.post("/deploy", json=duplicate, headers=headers).status_code, 422)

            rolled_back = client.post("/rollback", json={"actor": "qa"}, headers=headers)
            self.assertEqual(rolled_back.status_code, 200)
            self.assertEqual(rolled_back.json()["status"], "executed")
            artifact = client.get(
                rolled_back.json()["artifactUrl"].replace("http://testserver", ""),
                headers=headers,
            )
            self.assertEqual(artifact.status_code, 200)
            self.assertEqual(artifact.json()["restoredFrom"], first_response.json()["deploymentId"])
            self.assertEqual(artifact.json()["routes"][0]["siteHost"], "publisher.example")

    def test_strict_rollback_revalidates_dns_tls_and_retains_active_snapshot(self) -> None:
        headers = {"X-API-Key": "edge-test-key"}
        first = {"routes": [{**self.route, "publicPath": "/"}]}
        second = {"routes": [{**self.route, "siteHost": "new.example", "publicPath": "/"}]}
        with TestClient(create_app(settings=self.settings, gateway=self.gateway)) as client:
            first_response = client.post("/deploy", json=first, headers=headers)
            second_response = client.post("/deploy", json=second, headers=headers)
        strict_settings = EdgeSettings(
            api_base_url=self.settings.api_base_url,
            strict_routes_only=True,
            route_map_cache_seconds=30,
            request_timeout_seconds=5,
            api_key="edge-test-key",
            state_dir=Path(self.tempdir.name),
            verify_dns_tls=True,
        )
        strict_gateway = RuntimeEdgeGateway(strict_settings)
        failed_dns = {
            "required": True,
            "ready": False,
            "hostCount": 1,
            "readyCount": 0,
            "items": [{"host": "publisher.example", "failureCode": "RUNTIME_EDGE_TLS_VALIDATION_FAILED"}],
        }
        with patch.object(strict_gateway, "dns_tls_report", new=AsyncMock(return_value=failed_dns)):
            with TestClient(create_app(settings=strict_settings, gateway=strict_gateway)) as client:
                rollback = client.post(
                    "/rollback",
                    json={"deploymentId": first_response.json()["deploymentId"]},
                    headers=headers,
                )
                history = client.get("/deployments", headers=headers).json()

        self.assertEqual(rollback.status_code, 503)
        self.assertEqual(rollback.json()["detail"]["failureCode"], "RUNTIME_EDGE_ROLLBACK_DNS_TLS_NOT_READY")
        self.assertEqual(history["activeDeploymentId"], second_response.json()["deploymentId"])

    def test_deploy_rejects_project_proxy_mismatch_and_invalid_public_path(self) -> None:
        headers = {"X-API-Key": "edge-test-key"}
        mismatched = {
            "projectId": "project-1",
            "routes": [
                {
                    **self.route,
                    "proxyUrl": "http://control-plane:8000/api/projects/project-2/runtime-execute/proxy-strict",
                }
            ],
        }
        traversal = {"routes": [{**self.route, "publicPath": "/docs/../admin"}]}
        with TestClient(create_app(settings=self.settings, gateway=self.gateway)) as client:
            self.assertEqual(client.post("/deploy", json=mismatched, headers=headers).status_code, 422)
            self.assertEqual(client.post("/deploy", json=traversal, headers=headers).status_code, 422)

    def test_forward_strips_public_path_prefix(self) -> None:
        requests = []

        class FakeAsyncClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def request(self, method, url, **kwargs):
                requests.append({"method": method, "url": url, **kwargs})
                return httpx.Response(200, content=b"rewritten")

        route = {**self.route, "publicPath": "/docs"}
        self.gateway._route_map = [route]
        self.gateway._route_map_loaded_at = float("inf")
        with patch("apps.runtime_edge.main.httpx.AsyncClient", FakeAsyncClient):
            with TestClient(create_app(settings=self.settings, gateway=self.gateway)) as client:
                response = client.get("/docs/guides/seo?locale=en", headers={"Host": "publisher.example"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            requests[0]["url"],
            "http://control-plane:8000/api/projects/project-1/runtime-execute/proxy-strict/guides/seo?locale=en",
        )

    def test_readiness_can_require_dns_tls_evidence(self) -> None:
        headers = {"X-API-Key": "edge-test-key"}
        self.gateway._route_map = [self.route]
        self.gateway._route_map_loaded_at = float("inf")
        dns_report = {
            "required": True,
            "ready": False,
            "hostCount": 1,
            "readyCount": 0,
            "items": [{"host": "publisher.example", "failureCode": "RUNTIME_EDGE_DNS_RESOLUTION_FAILED"}],
        }
        with patch.object(self.gateway, "dns_tls_report", new=AsyncMock(return_value=dns_report)):
            with TestClient(create_app(settings=self.settings, gateway=self.gateway)) as client:
                response = client.get("/readyz?verifyDnsTls=true", headers=headers)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["failureCode"], "RUNTIME_EDGE_DNS_TLS_NOT_READY")
        self.assertFalse(response.json()["dnsTls"]["ready"])

    def test_failed_dns_tls_deploy_retains_previous_active_snapshot(self) -> None:
        headers = {"X-API-Key": "edge-test-key"}
        first = {"routes": [{**self.route, "publicPath": "/"}]}
        second = {"routes": [{**self.route, "siteHost": "new.example", "publicPath": "/"}]}
        with TestClient(create_app(settings=self.settings, gateway=self.gateway)) as client:
            active = client.post("/deploy", json=first, headers=headers)
            self.assertEqual(active.status_code, 200)
        strict_settings = EdgeSettings(
            api_base_url=self.settings.api_base_url,
            strict_routes_only=True,
            route_map_cache_seconds=30,
            request_timeout_seconds=5,
            api_key="edge-test-key",
            state_dir=Path(self.tempdir.name),
            verify_dns_tls=True,
        )
        strict_gateway = RuntimeEdgeGateway(strict_settings)
        with TestClient(create_app(settings=strict_settings, gateway=strict_gateway)) as client:
            failed_dns = {
                "required": True,
                "ready": False,
                "hostCount": 1,
                "readyCount": 0,
                "items": [{"host": "new.example", "failureCode": "RUNTIME_EDGE_DNS_RESOLUTION_FAILED"}],
            }
            with patch.object(strict_gateway, "dns_tls_report", new=AsyncMock(return_value=failed_dns)):
                rejected = client.post("/deploy", json=second, headers=headers)

            self.assertEqual(rejected.status_code, 503)
            self.assertEqual(rejected.json()["detail"]["failureCode"], "RUNTIME_EDGE_DNS_TLS_NOT_READY")
            self.assertEqual(rejected.json()["detail"]["retainedDeploymentId"], active.json()["deploymentId"])
            history = client.get("/deployments", headers=headers).json()
            self.assertEqual(history["activeDeploymentId"], active.json()["deploymentId"])
            self.assertEqual(history["items"][0]["status"], "rejected")
            no_unsafe_rollback = client.post("/rollback", json={"actor": "qa"}, headers=headers)
            self.assertEqual(no_unsafe_rollback.status_code, 409)
            self.assertEqual(no_unsafe_rollback.json()["detail"], "RUNTIME_EDGE_ROLLBACK_TARGET_MISSING")


if __name__ == "__main__":
    unittest.main()
