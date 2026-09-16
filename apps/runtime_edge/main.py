"""Minimal runtime edge gateway backed by the control-plane route map."""

from __future__ import annotations

import os
import asyncio
import hashlib
import ipaddress
import json
import re
import secrets
import socket
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@dataclass(frozen=True)
class EdgeSettings:
    api_base_url: str
    strict_routes_only: bool
    route_map_cache_seconds: int
    request_timeout_seconds: float
    api_key: str = ""
    state_dir: Path = Path("var/runtime-edge")
    max_deployments: int = 50
    verify_dns_tls: bool = False
    expected_public_ips: str = ""
    dns_tls_timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "EdgeSettings":
        return cls(
            api_base_url=os.getenv("SEO_AD_BOT_EDGE_API_BASE_URL", "http://api:8000").rstrip("/"),
            strict_routes_only=os.getenv("SEO_AD_BOT_EDGE_STRICT_ROUTES_ONLY", "true").strip().lower() in {"1", "true", "yes"},
            route_map_cache_seconds=max(0, int(os.getenv("SEO_AD_BOT_EDGE_ROUTE_MAP_CACHE_SECONDS", "30"))),
            request_timeout_seconds=max(1.0, float(os.getenv("SEO_AD_BOT_EDGE_REQUEST_TIMEOUT_SECONDS", "20"))),
            api_key=os.getenv("SEO_AD_BOT_EDGE_API_KEY", "").strip(),
            state_dir=Path(os.getenv("SEO_AD_BOT_EDGE_STATE_DIR", "var/runtime-edge")),
            max_deployments=max(2, int(os.getenv("SEO_AD_BOT_EDGE_MAX_DEPLOYMENTS", "50"))),
            verify_dns_tls=os.getenv("SEO_AD_BOT_EDGE_VERIFY_DNS_TLS", "false").strip().lower() in {"1", "true", "yes"},
            expected_public_ips=os.getenv("SEO_AD_BOT_EDGE_EXPECTED_PUBLIC_IPS", "").strip(),
            dns_tls_timeout_seconds=max(1.0, float(os.getenv("SEO_AD_BOT_EDGE_DNS_TLS_TIMEOUT_SECONDS", "5"))),
        )


class EdgeDeploymentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    project_id: Optional[str] = Field(default=None, alias="projectId")
    task_id: Optional[str] = Field(default=None, alias="taskId")
    strict_routes_only: bool = Field(default=True, alias="strictRoutesOnly")
    canary_percent: int = Field(default=100, alias="canaryPercent", ge=1, le=100)
    actor: str = "control-plane"
    note: Optional[str] = None
    routes: list[dict[str, Any]] = Field(default_factory=list)
    site_routes: Optional[list[dict[str, Any]]] = Field(default=None, alias="siteRoutes")


class EdgeRollbackRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    deployment_id: Optional[str] = Field(default=None, alias="deploymentId")
    actor: str = "control-plane"
    note: Optional[str] = None


class RuntimeEdgeGateway:
    def __init__(self, settings: EdgeSettings) -> None:
        self.settings = settings
        self._route_map: list[dict[str, Any]] = []
        self._route_map_loaded_at = 0.0
        self._deployment_lock = asyncio.Lock()
        self._state = self._load_state()

    async def route_for_host(self, host: str) -> Optional[dict[str, Any]]:
        return await self.route_for_request(host, "/")

    async def route_for_request(self, host: str, path: str) -> Optional[dict[str, Any]]:
        route_map = await self._load_route_map()
        normalized_host = host.split(":", 1)[0].strip().lower()
        request_path = self._normalize_public_path(path)
        matches = [
            item
            for item in route_map
            if str(item.get("siteHost") or "").strip().lower() == normalized_host
            and self._path_matches(str(item.get("publicPath") or "/"), request_path)
        ]
        if not matches:
            return None
        matches.sort(key=lambda item: len(self._normalize_public_path(str(item.get("publicPath") or "/"))), reverse=True)
        longest = len(self._normalize_public_path(str(matches[0].get("publicPath") or "/")))
        if sum(1 for item in matches if len(self._normalize_public_path(str(item.get("publicPath") or "/"))) == longest) != 1:
            return None
        return matches[0]

    async def forward(self, request: Request, route: dict[str, Any], path: str) -> Response:
        proxy_url = str(route.get("proxyUrl") or "").strip()
        if not self._is_control_plane_proxy(proxy_url):
            return JSONResponse(status_code=502, content={"detail": "Runtime edge route has an invalid control-plane proxy target."})
        request_path = self._normalize_public_path(path)
        public_path = self._normalize_public_path(str(route.get("publicPath") or "/"))
        rewritten_path = request_path
        if public_path != "/" and self._path_matches(public_path, request_path):
            rewritten_path = request_path[len(public_path) :] or "/"
        target = f"{proxy_url.rstrip('/')}/{rewritten_path.lstrip('/')}"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        request_headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS | {"host", "content-length"}
        }
        request_headers.update(
            {
                "Host": request.headers.get("host", ""),
                "X-Forwarded-Host": request.headers.get("host", ""),
                "X-Forwarded-Proto": request.url.scheme,
                "X-Forwarded-For": request.client.host if request.client else "",
                "X-SEO-AD-Edge-Project-Id": str(route.get("projectId") or ""),
            }
        )
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds, follow_redirects=False) as client:
                upstream = await client.request(
                    request.method,
                    target,
                    headers=request_headers,
                    content=await request.body(),
                )
        except httpx.HTTPError as exc:
            return JSONResponse(status_code=502, content={"detail": "Runtime control plane is unreachable.", "reason": str(exc)})
        response_headers = {
            key: value
            for key, value in upstream.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS | {"content-length"}
        }
        response_headers["X-SEO-AD-Edge-Project-Id"] = str(route.get("projectId") or "")
        return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers)

    async def _load_route_map(self) -> list[dict[str, Any]]:
        active = self._active_deployment()
        if active is not None:
            return [dict(item) for item in active.get("routes", [])]
        now = time.monotonic()
        if self._route_map_loaded_at and now - self._route_map_loaded_at <= self.settings.route_map_cache_seconds:
            return self._route_map
        params = {"strictRoutesOnly": "true"} if self.settings.strict_routes_only else {}
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(f"{self.settings.api_base_url}/api/runtime-edge/map", params=params)
            response.raise_for_status()
        payload = response.json()
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise ValueError("Runtime edge route map response has no items list.")
        self._route_map = [item for item in items if isinstance(item, dict)]
        self._route_map_loaded_at = now
        return self._route_map

    async def deploy(self, payload: EdgeDeploymentRequest, base_url: str) -> dict[str, Any]:
        async with self._deployment_lock:
            incoming = self._validate_routes(payload.site_routes if payload.site_routes is not None else payload.routes)
            if not incoming:
                raise HTTPException(status_code=422, detail="RUNTIME_EDGE_ROUTES_MISSING")
            active = self._active_deployment()
            current = [dict(item) for item in active.get("routes", [])] if active else []
            project_id = str(payload.project_id or "").strip()
            if project_id:
                incoming_project_ids = {str(item.get("projectId") or "").strip() for item in incoming}
                if incoming_project_ids != {project_id}:
                    raise HTTPException(status_code=422, detail="RUNTIME_EDGE_PROJECT_ROUTE_MISMATCH")
                merged = [item for item in current if str(item.get("projectId") or "").strip() != project_id]
                merged.extend(incoming)
            else:
                merged = incoming
            routes = self._validate_routes(merged)
            canonical = json.dumps(routes, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            artifact_id = f"edge-config-{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"
            if active and active.get("artifactId") == artifact_id:
                return self._deployment_response(active, base_url, unchanged=True)
            dns_tls = await self.dns_tls_report(routes) if self.settings.verify_dns_tls else None
            if dns_tls is not None and not dns_tls["ready"]:
                failed = {
                    "deploymentId": f"edge-deploy-{secrets.token_urlsafe(10)}",
                    "artifactId": artifact_id,
                    "status": "rejected",
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                    "projectId": payload.project_id,
                    "taskId": payload.task_id,
                    "strictRoutesOnly": payload.strict_routes_only,
                    "canaryPercent": payload.canary_percent,
                    "actor": payload.actor.strip() or "control-plane",
                    "note": payload.note,
                    "routeCount": len(routes),
                    "routes": routes,
                    "failureCode": "RUNTIME_EDGE_DNS_TLS_NOT_READY",
                    "dnsTls": dns_tls,
                    "retainedDeploymentId": active.get("deploymentId") if active else None,
                }
                self._state["deployments"].append(failed)
                self._state["deployments"] = self._state["deployments"][-self.settings.max_deployments :]
                self._persist_state()
                raise HTTPException(
                    status_code=503,
                    detail={
                        "failureCode": "RUNTIME_EDGE_DNS_TLS_NOT_READY",
                        "retryable": True,
                        "deploymentId": failed["deploymentId"],
                        "retainedDeploymentId": failed["retainedDeploymentId"],
                        "dnsTls": dns_tls,
                    },
                )
            deployment = {
                "deploymentId": f"edge-deploy-{secrets.token_urlsafe(10)}",
                "artifactId": artifact_id,
                "status": "active",
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "projectId": payload.project_id,
                "taskId": payload.task_id,
                "strictRoutesOnly": payload.strict_routes_only,
                "canaryPercent": payload.canary_percent,
                "actor": payload.actor.strip() or "control-plane",
                "note": payload.note,
                "routeCount": len(routes),
                "routes": routes,
            }
            if dns_tls is not None:
                deployment["dnsTls"] = dns_tls
            for item in self._state["deployments"]:
                if item.get("status") == "active":
                    item["status"] = "superseded"
            self._state["deployments"].append(deployment)
            self._state["deployments"] = self._state["deployments"][-self.settings.max_deployments :]
            self._state["activeDeploymentId"] = deployment["deploymentId"]
            self._route_map = routes
            self._route_map_loaded_at = time.monotonic()
            self._persist_state()
            return self._deployment_response(deployment, base_url)

    async def rollback(self, payload: EdgeRollbackRequest, base_url: str) -> dict[str, Any]:
        async with self._deployment_lock:
            active = self._active_deployment()
            candidates = [
                item
                for item in self._state["deployments"]
                if item.get("deploymentId") != self._state.get("activeDeploymentId")
                and item.get("status") in {"superseded", "rolled_back"}
            ]
            if payload.deployment_id:
                target = next((item for item in candidates if item.get("deploymentId") == payload.deployment_id), None)
            else:
                target = candidates[-1] if candidates else None
            if target is None:
                raise HTTPException(status_code=409, detail="RUNTIME_EDGE_ROLLBACK_TARGET_MISSING")
            restored_routes = self._validate_routes(list(target.get("routes") or []))
            if self.settings.verify_dns_tls:
                dns_tls = await self.dns_tls_report(restored_routes)
                if not dns_tls["ready"]:
                    raise HTTPException(
                        status_code=503,
                        detail={
                            "failureCode": "RUNTIME_EDGE_ROLLBACK_DNS_TLS_NOT_READY",
                            "retryable": True,
                            "retainedDeploymentId": active.get("deploymentId") if active else None,
                            "targetDeploymentId": target.get("deploymentId"),
                            "dnsTls": dns_tls,
                        },
                    )
            rollback = {
                **target,
                "deploymentId": f"edge-rollback-{secrets.token_urlsafe(10)}",
                "status": "active",
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "actor": payload.actor.strip() or "control-plane",
                "note": payload.note,
                "rollbackOf": active.get("deploymentId") if active else None,
                "restoredFrom": target.get("deploymentId"),
                "routes": restored_routes,
            }
            if self.settings.verify_dns_tls:
                rollback["dnsTls"] = dns_tls
            for item in self._state["deployments"]:
                if item.get("status") == "active":
                    item["status"] = "rolled_back"
            self._state["deployments"].append(rollback)
            self._state["deployments"] = self._state["deployments"][-self.settings.max_deployments :]
            self._state["activeDeploymentId"] = rollback["deploymentId"]
            self._route_map = restored_routes
            self._route_map_loaded_at = time.monotonic()
            self._persist_state()
            return self._deployment_response(rollback, base_url)

    def deployment_history(self) -> dict[str, Any]:
        deployments = [{key: value for key, value in item.items() if key != "routes"} for item in reversed(self._state["deployments"])]
        return {
            "status": "ok",
            "activeDeploymentId": self._state.get("activeDeploymentId"),
            "total": len(deployments),
            "items": deployments,
        }

    def deployment_artifact(self, deployment_id: str) -> Optional[dict[str, Any]]:
        return next((dict(item) for item in self._state["deployments"] if item.get("deploymentId") == deployment_id), None)

    async def dns_tls_report(self, routes: list[dict[str, Any]]) -> dict[str, Any]:
        hosts = sorted({str(item.get("siteHost") or "").strip().lower() for item in routes if item.get("siteHost")})
        items = await asyncio.gather(*(asyncio.to_thread(self._probe_dns_tls_host, host) for host in hosts))
        return {
            "required": True,
            "ready": bool(items) and all(bool(item.get("ready")) for item in items),
            "hostCount": len(hosts),
            "readyCount": sum(1 for item in items if item.get("ready")),
            "items": items,
        }

    def _probe_dns_tls_host(self, host: str) -> dict[str, Any]:
        started = time.perf_counter()
        result: dict[str, Any] = {"host": host, "dnsReady": False, "tlsReady": False, "ready": False}
        try:
            addresses = sorted(
                {
                    str(item[4][0])
                    for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
                    if item and item[4]
                }
            )
            result["addresses"] = addresses
            result["dnsReady"] = bool(addresses)
            expected = {item.strip() for item in self.settings.expected_public_ips.split(",") if item.strip()}
            if expected and not expected.intersection(addresses):
                result.update(
                    {
                        "failureCode": "RUNTIME_EDGE_DNS_TARGET_MISMATCH",
                        "message": "Resolved addresses do not include an expected edge address.",
                    }
                )
                return result
            context = ssl.create_default_context()
            with socket.create_connection((host, 443), timeout=self.settings.dns_tls_timeout_seconds) as connection:
                with context.wrap_socket(connection, server_hostname=host) as secure_connection:
                    certificate = secure_connection.getpeercert()
                    result["tlsVersion"] = secure_connection.version()
                    result["certificateExpiresAt"] = certificate.get("notAfter") if isinstance(certificate, dict) else None
            result.update({"tlsReady": True, "ready": True})
            return result
        except socket.gaierror as exc:
            result.update({"failureCode": "RUNTIME_EDGE_DNS_RESOLUTION_FAILED", "message": str(exc)})
        except ssl.SSLError as exc:
            result.update({"failureCode": "RUNTIME_EDGE_TLS_VALIDATION_FAILED", "message": str(exc)})
        except OSError as exc:
            result.update({"failureCode": "RUNTIME_EDGE_TLS_CONNECTION_FAILED", "message": str(exc)})
        finally:
            result["latencyMs"] = int((time.perf_counter() - started) * 1000)
        return result

    def _load_state(self) -> dict[str, Any]:
        path = self._state_path()
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and isinstance(payload.get("deployments"), list):
                    return payload
            except (OSError, ValueError):
                pass
        return {"version": 1, "activeDeploymentId": None, "deployments": []}

    def _persist_state(self) -> None:
        path = self._state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._state, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def _state_path(self) -> Path:
        return self.settings.state_dir / "deployments.json"

    def _active_deployment(self) -> Optional[dict[str, Any]]:
        active_id = self._state.get("activeDeploymentId")
        return next((item for item in self._state["deployments"] if item.get("deploymentId") == active_id), None)

    def _validate_routes(self, routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        route_keys: set[tuple[str, str]] = set()
        for raw in routes:
            if not isinstance(raw, dict):
                raise HTTPException(status_code=422, detail="RUNTIME_EDGE_ROUTE_INVALID")
            project_id = str(raw.get("projectId") or "").strip()
            site_host = str(raw.get("siteHost") or "").split(":", 1)[0].strip().lower()
            proxy_url = str(raw.get("proxyUrl") or "").strip()
            public_path = self._normalize_public_path(str(raw.get("publicPath") or "/"))
            if (
                not project_id
                or not self._valid_site_host(site_host)
                or not proxy_url
                or not self._is_control_plane_proxy(proxy_url)
                or not self._proxy_matches_project(proxy_url, project_id)
                or any(marker in public_path for marker in {"?", "#", "\\"})
                or ".." in public_path.split("/")
            ):
                raise HTTPException(status_code=422, detail="RUNTIME_EDGE_ROUTE_INVALID")
            key = (site_host, public_path)
            if key in route_keys:
                raise HTTPException(status_code=422, detail="RUNTIME_EDGE_ROUTE_DUPLICATE")
            route_keys.add(key)
            normalized.append({**raw, "projectId": project_id, "siteHost": site_host, "publicPath": public_path, "proxyUrl": proxy_url})
        return sorted(normalized, key=lambda item: (item["siteHost"], item["publicPath"], item["projectId"]))

    def _deployment_response(self, deployment: dict[str, Any], base_url: str, *, unchanged: bool = False) -> dict[str, Any]:
        deployment_id = str(deployment["deploymentId"])
        return {
            "status": "unchanged" if unchanged else "executed",
            "deploymentId": deployment_id,
            "artifactId": deployment.get("artifactId"),
            "artifactUrl": f"{base_url.rstrip('/')}/deployments/{deployment_id}",
            "routeCount": deployment.get("routeCount", len(deployment.get("routes", []))),
            "activeDeploymentId": self._state.get("activeDeploymentId"),
            "message": "Runtime edge route snapshot is active.",
        }

    @staticmethod
    def _normalize_public_path(value: str) -> str:
        normalized = f"/{value.strip().lstrip('/')}" if value.strip() else "/"
        return normalized.rstrip("/") or "/"

    @classmethod
    def _path_matches(cls, public_path: str, request_path: str) -> bool:
        normalized = cls._normalize_public_path(public_path)
        return normalized == "/" or request_path == normalized or request_path.startswith(f"{normalized}/")

    @staticmethod
    def _valid_site_host(host: str) -> bool:
        try:
            ipaddress.ip_address(host)
            return False
        except ValueError:
            pass
        return bool(
            len(host) <= 253
            and re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", host)
        )

    @staticmethod
    def _proxy_matches_project(proxy_url: str, project_id: str) -> bool:
        path_parts = [part for part in urlparse(proxy_url).path.split("/") if part]
        return len(path_parts) >= 3 and path_parts[0] == "api" and path_parts[1] == "projects" and path_parts[2] == project_id

    def _is_control_plane_proxy(self, proxy_url: str) -> bool:
        target = urlparse(proxy_url)
        control_plane = urlparse(self.settings.api_base_url)
        return bool(
            target.scheme in {"http", "https"}
            and target.netloc
            and target.scheme == control_plane.scheme
            and target.netloc == control_plane.netloc
            and target.path.startswith("/api/projects/")
        )


def create_app(
    settings: Optional[EdgeSettings] = None,
    gateway: Optional[RuntimeEdgeGateway] = None,
) -> FastAPI:
    active_settings = settings or EdgeSettings.from_env()
    active_gateway = gateway or RuntimeEdgeGateway(active_settings)
    app = FastAPI(title="SEO-AD AutoPilot Runtime Edge")
    app.state.gateway = active_gateway

    def require_api_key(
        x_api_key: Optional[str] = Header(default=None),
        authorization: Optional[str] = Header(default=None),
    ) -> None:
        bearer = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else ""
        presented = str(x_api_key or bearer).strip()
        if not active_settings.api_key or not presented or not secrets.compare_digest(active_settings.api_key, presented):
            raise HTTPException(status_code=401, detail="Runtime edge API key is required")

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        try:
            routes = await active_gateway._load_route_map()
        except (httpx.HTTPError, ValueError) as exc:
            return {"status": "degraded", "reason": str(exc)}
        return {"status": "ok", "routeCount": len(routes), "strictRoutesOnly": active_settings.strict_routes_only}

    @app.get("/readyz", dependencies=[Depends(require_api_key)])
    async def readyz(verify_dns_tls: bool = Query(default=False, alias="verifyDnsTls")) -> JSONResponse:
        try:
            routes = await active_gateway._load_route_map()
        except (httpx.HTTPError, ValueError) as exc:
            return JSONResponse(status_code=503, content={"status": "not_ready", "failureCode": "RUNTIME_EDGE_ROUTE_MAP_UNAVAILABLE", "message": str(exc)})
        should_verify_dns_tls = active_settings.verify_dns_tls or verify_dns_tls
        dns_tls = await active_gateway.dns_tls_report(routes) if should_verify_dns_tls else {
            "required": False,
            "ready": None,
            "hostCount": len({str(item.get("siteHost") or "") for item in routes}),
            "readyCount": 0,
            "items": [],
        }
        ready = bool(routes) and (not should_verify_dns_tls or bool(dns_tls["ready"]))
        payload = {
            "status": "ready" if ready else "not_ready",
            "routeCount": len(routes),
            "activeDeploymentId": active_gateway._state.get("activeDeploymentId"),
            "strictRoutesOnly": active_settings.strict_routes_only,
            "dnsTls": dns_tls,
        }
        if not ready:
            payload["failureCode"] = "RUNTIME_EDGE_DNS_TLS_NOT_READY" if routes and should_verify_dns_tls else "RUNTIME_EDGE_ROUTES_MISSING"
        return JSONResponse(status_code=200 if ready else 503, content=payload)

    @app.post("/deploy", dependencies=[Depends(require_api_key)])
    async def deploy(payload: EdgeDeploymentRequest, request: Request) -> dict[str, Any]:
        return await active_gateway.deploy(payload, str(request.base_url))

    @app.post("/rollback", dependencies=[Depends(require_api_key)])
    async def rollback(payload: EdgeRollbackRequest, request: Request) -> dict[str, Any]:
        return await active_gateway.rollback(payload, str(request.base_url))

    @app.get("/deployments", dependencies=[Depends(require_api_key)])
    async def deployments() -> dict[str, Any]:
        return active_gateway.deployment_history()

    @app.get("/deployments/{deployment_id}", dependencies=[Depends(require_api_key)])
    async def deployment_artifact(deployment_id: str) -> dict[str, Any]:
        artifact = active_gateway.deployment_artifact(deployment_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Runtime edge deployment not found")
        return artifact

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
    async def proxy(path: str, request: Request) -> Response:
        host = request.headers.get("host", "")
        try:
            route = await active_gateway.route_for_request(host, f"/{path.lstrip('/')}")
        except (httpx.HTTPError, ValueError) as exc:
            return JSONResponse(status_code=503, content={"detail": "Runtime edge route map is unavailable.", "reason": str(exc)})
        if route is None:
            return JSONResponse(status_code=404, content={"detail": "No unique runtime route exists for this Host."})
        return await active_gateway.forward(request, route, path)

    return app
