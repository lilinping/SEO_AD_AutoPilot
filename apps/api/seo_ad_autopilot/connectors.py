from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Optional
from urllib.parse import urljoin, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .config import Settings, get_settings
from .crawler import crawl_page_with_diagnostics
from .artifact_store import get_artifact_store
from .models import (
    ConnectionHealth,
    ConnectorKind,
    ConnectorStatus,
    DeploymentMode,
    DeploymentRecord,
    IngestionReport,
    PageSnapshot,
    PagePerformanceBudget,
    Plan,
    ProjectConnection,
    SiteIntake,
    SourceEvidence,
    new_id,
    utcnow,
)

INGESTION_CONNECTOR_KINDS = [
    ConnectorKind.search_console,
    ConnectorKind.ga4,
    ConnectorKind.github,
    ConnectorKind.cms,
    ConnectorKind.script_api,
    ConnectorKind.ad_network,
    ConnectorKind.sitemap,
    ConnectorKind.playwright,
]

MARKET_EVIDENCE_CONNECTOR_KINDS = [
    ConnectorKind.trend,
    ConnectorKind.news,
    ConnectorKind.qa,
]


@dataclass(frozen=True)
class ConnectorContext:
    project_id: str
    task_id: Optional[str]
    intake: SiteIntake
    connection: ProjectConnection


def _site_host(intake: SiteIntake) -> str:
    return urlparse(intake.url).netloc.lower() or intake.url.lower()


def _coerce_list(values: Any) -> list[str]:
    if isinstance(values, list):
        return [str(value) for value in values if str(value).strip()]
    if isinstance(values, str):
        return [item.strip() for item in re.split(r"[\n,]", values) if item.strip()]
    return []


def _candidate_endpoints(config: dict[str, Any], keys: list[str], fallback: str = "") -> list[str]:
    endpoints: list[str] = []
    for key in keys:
        value = config.get(key)
        for item in _coerce_list(value):
            if item not in endpoints:
                endpoints.append(item)
        if isinstance(value, str):
            text = value.strip()
            if text and text not in endpoints:
                endpoints.append(text)
    fallback_text = fallback.strip()
    if fallback_text and fallback_text not in endpoints:
        endpoints.append(fallback_text)
    return endpoints


def _has_explicit_endpoint_config(config: dict[str, Any], keys: list[str]) -> bool:
    for key in keys:
        value = config.get(key)
        if _coerce_list(value):
            return True
        if isinstance(value, str) and value.strip():
            return True
    return False


def _connection_label(provider: ConnectorKind) -> str:
    return {
        ConnectorKind.search_console: "Search Console",
        ConnectorKind.ga4: "GA4",
        ConnectorKind.github: "GitHub",
        ConnectorKind.cms: "CMS",
        ConnectorKind.script_api: "Script API",
        ConnectorKind.ad_network: "Ad Network",
        ConnectorKind.sitemap: "Sitemap",
        ConnectorKind.playwright: "Playwright",
        ConnectorKind.trend: "Trend",
        ConnectorKind.news: "News",
        ConnectorKind.qa: "QA",
    }[provider]


def _market_provider_env_suffix(provider: ConnectorKind) -> str:
    return {
        ConnectorKind.trend: "TREND",
        ConnectorKind.news: "NEWS",
        ConnectorKind.qa: "QA",
    }[provider]


def _market_provider_setting_suffix(provider: ConnectorKind) -> str:
    return {
        ConnectorKind.trend: "trend",
        ConnectorKind.news: "news",
        ConnectorKind.qa: "qa",
    }[provider]


def _market_provider_rule_prefix(provider: ConnectorKind) -> str:
    return {
        ConnectorKind.trend: "trend",
        ConnectorKind.news: "news",
        ConnectorKind.qa: "qa",
    }[provider]


def _market_provider_rule_value(intake: SiteIntake, provider: ConnectorKind, suffix: str) -> Any:
    prefix = _market_provider_rule_prefix(provider)
    rules = intake.approval_rules or {}
    specific_keys = {
        "providerUrl": [f"{prefix}ProviderUrl", f"{prefix}Url", f"{prefix}Endpoint"],
        "providerUrls": [f"{prefix}ProviderUrls", f"{prefix}Urls", f"{prefix}Endpoints"],
        "accessToken": [f"{prefix}AccessToken", f"{prefix}Token"],
        "credentialsJson": [f"{prefix}CredentialsJson"],
        "serviceAccountJson": [f"{prefix}ServiceAccountJson"],
    }[suffix]
    for key in specific_keys:
        if key in rules and rules.get(key) not in (None, "", [], {}):
            return rules.get(key)
    shared_keys = {
        "providerUrl": ["marketProviderUrl", "providerUrl"],
        "providerUrls": ["marketProviderUrls", "providerUrls"],
        "accessToken": ["marketProviderAccessToken", "accessToken"],
        "credentialsJson": ["marketProviderCredentialsJson", "credentialsJson"],
        "serviceAccountJson": ["marketProviderServiceAccountJson", "serviceAccountJson"],
    }[suffix]
    for key in shared_keys:
        if key in rules and rules.get(key) not in (None, "", [], {}):
            return rules.get(key)
    return None


def _playwright_rule_value(intake: SiteIntake, suffix: str) -> Any:
    rules = intake.approval_rules or {}
    specific_keys = {
        "enabled": ["playwrightEnabled"],
        "providerUrl": ["playwrightProviderUrl", "playwrightUrl", "playwrightEndpoint"],
        "providerUrls": ["playwrightProviderUrls", "playwrightUrls", "playwrightEndpoints"],
        "accessToken": ["playwrightAccessToken", "playwrightToken"],
        "credentialsJson": ["playwrightCredentialsJson"],
        "serviceAccountJson": ["playwrightServiceAccountJson"],
        "timeoutMs": ["playwrightTimeoutMs"],
        "authHeader": ["playwrightAuthHeader"],
        "jsEnabled": ["playwrightJsEnabled"],
        "retryCount": ["playwrightRetryCount"],
        "backoffMs": ["playwrightBackoffMs"],
        "jitterMs": ["playwrightJitterMs"],
        "proxyRotation": ["playwrightProxyRotation"],
        "proxy": ["playwrightProxy"],
        "proxies": ["playwrightProxies"],
        "extraHeaders": ["playwrightExtraHeaders"],
        "userAgent": ["playwrightUserAgent"],
        "userAgents": ["playwrightUserAgents"],
    }[suffix]
    for key in specific_keys:
        if key in rules and rules.get(key) not in (None, "", [], {}):
            return rules.get(key)
    return None


def _connector_rule_value(intake: SiteIntake, keys: list[str]) -> Any:
    rules = intake.approval_rules or {}
    for key in keys:
        if key in rules and rules.get(key) not in (None, "", [], {}):
            return rules.get(key)
    return None


def _market_provider_configured(settings: Settings, intake: SiteIntake, provider: ConnectorKind) -> bool:
    suffix = _market_provider_env_suffix(provider)
    setting_suffix = _market_provider_setting_suffix(provider)
    rule_provider_url = _market_provider_rule_value(intake, provider, "providerUrl")
    rule_provider_urls = _market_provider_rule_value(intake, provider, "providerUrls")
    rule_access_token = _market_provider_rule_value(intake, provider, "accessToken")
    rule_credentials_json = _market_provider_rule_value(intake, provider, "credentialsJson")
    rule_service_account_json = _market_provider_rule_value(intake, provider, "serviceAccountJson")
    return bool(
        rule_provider_url
        or rule_provider_urls
        or rule_access_token
        or rule_credentials_json
        or rule_service_account_json
        or getattr(settings, f"{setting_suffix}_provider_url", "")
        or getattr(settings, f"{setting_suffix}_provider_access_token", "")
        or getattr(settings, f"{setting_suffix}_provider_credentials_json", "")
        or getattr(settings, f"{setting_suffix}_provider_service_account_json", "")
        or os.getenv(f"SEO_AD_BOT_{suffix}_PROVIDER_URL", "")
        or os.getenv(f"SEO_AD_BOT_{suffix}_PROVIDER_ACCESS_TOKEN", "")
        or os.getenv(f"SEO_AD_BOT_{suffix}_PROVIDER_CREDENTIALS_JSON", "")
        or os.getenv(f"SEO_AD_BOT_{suffix}_PROVIDER_SERVICE_ACCOUNT_JSON", "")
    )


def _market_provider_endpoint_keys() -> list[str]:
    return ["providerUrls", "providerUrl", "endpoints", "endpoint"]


def _market_provider_credential_keys() -> list[str]:
    return ["accessToken", "credentialsJson", "serviceAccountJson", "authToken"]


def _connection_config(provider: ConnectorKind, intake: SiteIntake, settings: Settings) -> dict[str, Any]:
    host = _site_host(intake)
    if provider == ConnectorKind.search_console:
        payload = dict(intake.search_console)
        payload.setdefault("property", host)
        payload.setdefault("siteUrl", intake.url)
        for key, rule_keys in (
            ("accessToken", ["searchConsoleAccessToken"]),
            ("credentialsJson", ["searchConsoleCredentialsJson"]),
            ("serviceAccountJson", ["searchConsoleServiceAccountJson"]),
            ("apiEndpoint", ["searchConsoleApiEndpoint", "searchConsoleEndpoint"]),
            ("apiEndpoints", ["searchConsoleApiEndpoints", "searchConsoleEndpoints"]),
        ):
            value = _connector_rule_value(intake, rule_keys)
            if value not in (None, "", [], {}):
                payload[key] = value
        return payload
    if provider == ConnectorKind.ga4:
        payload = dict(intake.ga4)
        payload.setdefault("property", host)
        payload.setdefault("siteUrl", intake.url)
        for key, rule_keys in (
            ("accessToken", ["ga4AccessToken"]),
            ("credentialsJson", ["ga4CredentialsJson"]),
            ("serviceAccountJson", ["ga4ServiceAccountJson"]),
            ("apiEndpoint", ["ga4ApiEndpoint", "ga4Endpoint"]),
            ("apiEndpoints", ["ga4ApiEndpoints", "ga4Endpoints"]),
        ):
            value = _connector_rule_value(intake, rule_keys)
            if value not in (None, "", [], {}):
                payload[key] = value
        return payload
    if provider == ConnectorKind.github:
        payload = {
            "repoUrl": intake.repo_url or "",
            "branch": str(_connector_rule_value(intake, ["githubBranch"]) or "main"),
        }
        for key, rule_keys in (
            ("accessToken", ["githubAccessToken"]),
            ("credentialsJson", ["githubCredentialsJson"]),
            ("serviceAccountJson", ["githubServiceAccountJson"]),
            ("apiEndpoint", ["githubApiEndpoint", "githubEndpoint"]),
            ("apiEndpoints", ["githubApiEndpoints", "githubEndpoints"]),
            ("authHeader", ["githubAuthHeader"]),
        ):
            value = _connector_rule_value(intake, rule_keys)
            if value not in (None, "", [], {}):
                payload[key] = value
        return payload
    if provider == ConnectorKind.cms:
        endpoint = str(
            _connector_rule_value(intake, ["cmsDraftEndpoint", "cmsProviderUrl", "cmsEndpoint"])
            or settings.cms_provider_url
            or ""
        )
        endpoints = _coerce_list(
            _connector_rule_value(intake, ["cmsDraftEndpoints", "cmsProviderUrls", "cmsEndpoints"])
        )
        payload: dict[str, Any] = {"cmsName": intake.cms_name or "", "siteUrl": intake.url}
        if endpoint:
            payload["draftEndpoint"] = endpoint
        if endpoints:
            payload["draftEndpoints"] = endpoints
        for key, rule_keys in (
            ("authToken", ["cmsAuthToken", "cmsAccessToken"]),
            ("accessToken", ["cmsAccessToken"]),
            ("credentialsJson", ["cmsCredentialsJson"]),
            ("serviceAccountJson", ["cmsServiceAccountJson"]),
            ("authHeader", ["cmsAuthHeader"]),
        ):
            value = _connector_rule_value(intake, rule_keys)
            if value not in (None, "", [], {}):
                payload[key] = value
        return payload
    if provider == ConnectorKind.script_api:
        endpoint = str(
            _connector_rule_value(intake, ["scriptEndpoint", "scriptProviderUrl"])
            or settings.script_provider_url
            or ""
        )
        return {
            "endpoint": endpoint,
            "siteUrl": intake.url,
            "authToken": str(_connector_rule_value(intake, ["scriptAuthToken", "scriptAccessToken"]) or "").strip(),
            "accessToken": str(_connector_rule_value(intake, ["scriptAccessToken"]) or "").strip(),
            "credentialsJson": str(_connector_rule_value(intake, ["scriptCredentialsJson"]) or "").strip(),
            "serviceAccountJson": str(_connector_rule_value(intake, ["scriptServiceAccountJson"]) or "").strip(),
            "authHeader": str(_connector_rule_value(intake, ["scriptAuthHeader"]) or "").strip(),
        }
    if provider == ConnectorKind.ad_network:
        endpoint = str(
            _connector_rule_value(intake, ["adNetworkProviderUrl", "adNetworkEndpoint"])
            or settings.ad_network_provider_url
            or ""
        )
        payload: dict[str, Any] = {
            "provider": "ad_network",
            "providerFamily": str(_connector_rule_value(intake, ["adNetworkProviderFamily"]) or settings.ad_network_provider_family),
            "currency": str(_connector_rule_value(intake, ["adNetworkCurrency"]) or settings.ad_network_currency),
            "accountId": str(_connector_rule_value(intake, ["adNetworkAccountId"]) or settings.ad_network_account_id or ""),
            "endpoint": endpoint,
            "siteUrl": intake.url,
            "authToken": str(_connector_rule_value(intake, ["adNetworkAuthToken", "adNetworkAccessToken"]) or "").strip(),
            "accessToken": str(_connector_rule_value(intake, ["adNetworkAccessToken"]) or "").strip(),
            "credentialsJson": str(_connector_rule_value(intake, ["adNetworkCredentialsJson"]) or "").strip(),
            "serviceAccountJson": str(_connector_rule_value(intake, ["adNetworkServiceAccountJson"]) or "").strip(),
            "authHeader": str(_connector_rule_value(intake, ["adNetworkAuthHeader"]) or settings.ad_network_auth_header or "").strip(),
        }
        provider_urls = (
            _coerce_list(_connector_rule_value(intake, ["adNetworkProviderUrls", "adNetworkEndpoints"]))
            or _coerce_list(settings.ad_network_provider_urls)
        )
        if provider_urls:
            payload["endpoints"] = provider_urls
        timeout_ms = _connector_rule_value(intake, ["adNetworkProviderTimeoutMs", "adNetworkTimeoutMs"]) or settings.ad_network_provider_timeout_ms
        if timeout_ms:
            payload["timeoutMs"] = int(timeout_ms)
        return payload
    if provider == ConnectorKind.sitemap:
        urls = [urljoin(intake.url.rstrip("/") + "/", entry.lstrip("/")) for entry in intake.sitemap_urls or ["/sitemap.xml"]]
        payload: dict[str, Any] = {"urls": urls, "explicitConfig": bool(intake.sitemap_urls)}
        provider_url = str(intake.approval_rules.get("sitemapProviderUrl") or settings.sitemap_provider_url or "").strip()
        if provider_url:
            payload["providerUrl"] = provider_url
        provider_urls = _coerce_list(intake.approval_rules.get("sitemapProviderUrls"))
        if provider_urls:
            payload["providerUrls"] = provider_urls
        timeout_ms = intake.approval_rules.get("sitemapProviderTimeoutMs") or settings.sitemap_provider_timeout_ms
        if timeout_ms:
            payload["providerTimeoutMs"] = int(timeout_ms)
        auth_header = str(intake.approval_rules.get("sitemapAuthHeader") or settings.sitemap_provider_auth_header or "Authorization").strip()
        if auth_header:
            payload["authHeader"] = auth_header
        return payload
    if provider == ConnectorKind.playwright:
        approval_enabled = _playwright_rule_value(intake, "enabled")
        approval_provider_url = str(_playwright_rule_value(intake, "providerUrl") or "").strip()
        approval_provider_urls = _coerce_list(_playwright_rule_value(intake, "providerUrls"))
        approval_timeout_ms = _playwright_rule_value(intake, "timeoutMs")
        approval_auth_header = str(_playwright_rule_value(intake, "authHeader") or "").strip()
        payload = {
            "enabled": bool(
                approval_enabled
                if approval_enabled is not None
                else (settings.enable_browser_crawl or approval_provider_url or approval_provider_urls or settings.playwright_provider_url)
            ),
            "providerUrl": approval_provider_url or settings.playwright_provider_url or "",
            "timeoutMs": int(approval_timeout_ms or settings.playwright_provider_timeout_ms),
            "authHeader": approval_auth_header or settings.playwright_auth_header,
        }
        if approval_provider_urls:
            payload["providerUrls"] = approval_provider_urls
        approval_access_token = str(_playwright_rule_value(intake, "accessToken") or "").strip()
        approval_credentials_json = str(_playwright_rule_value(intake, "credentialsJson") or "").strip()
        approval_service_account_json = str(_playwright_rule_value(intake, "serviceAccountJson") or "").strip()
        if approval_access_token:
            payload["accessToken"] = approval_access_token
        if approval_credentials_json:
            payload["credentialsJson"] = approval_credentials_json
        if approval_service_account_json:
            payload["serviceAccountJson"] = approval_service_account_json
        for key in ("jsEnabled", "retryCount", "backoffMs", "jitterMs", "proxyRotation", "proxy", "proxies", "extraHeaders", "userAgent", "userAgents"):
            value = _playwright_rule_value(intake, key)
            if value not in (None, "", [], {}):
                payload[key] = value
        return payload
    if provider in MARKET_EVIDENCE_CONNECTOR_KINDS:
        provider_suffix = _market_provider_env_suffix(provider)
        setting_suffix = _market_provider_setting_suffix(provider)
        rule_provider_url = str(_market_provider_rule_value(intake, provider, "providerUrl") or "").strip()
        provider_url = rule_provider_url or str(getattr(settings, f"{setting_suffix}_provider_url", "") or "").strip()
        payload: dict[str, Any] = {
            "provider": provider.value,
            "providerLabel": _connection_label(provider),
            "providerUrl": provider_url,
            "timeoutMs": settings.market_provider_timeout_ms,
            "authHeader": "Authorization",
        }
        for key in ("accessToken", "credentialsJson", "serviceAccountJson"):
            field_name = {
                "accessToken": f"{setting_suffix}_provider_access_token",
                "credentialsJson": f"{setting_suffix}_provider_credentials_json",
                "serviceAccountJson": f"{setting_suffix}_provider_service_account_json",
            }[key]
            rule_value = str(_market_provider_rule_value(intake, provider, key) or "").strip()
            value = rule_value or str(getattr(settings, field_name, "") or "").strip()
            if value:
                payload[key] = value
        rule_provider_urls = _coerce_list(_market_provider_rule_value(intake, provider, "providerUrls"))
        if rule_provider_urls:
            payload["providerUrls"] = rule_provider_urls
        elif not provider_url:
            payload["providerUrls"] = []
        shared_access_token = str((intake.approval_rules or {}).get("marketProviderAccessToken") or settings.market_provider_access_token or "").strip()
        shared_credentials = str((intake.approval_rules or {}).get("marketProviderCredentialsJson") or settings.market_provider_credentials_json or "").strip()
        shared_service_account = str((intake.approval_rules or {}).get("marketProviderServiceAccountJson") or settings.market_provider_service_account_json or "").strip()
        if shared_access_token and "accessToken" not in payload:
            payload["accessToken"] = shared_access_token
        if shared_credentials and "credentialsJson" not in payload:
            payload["credentialsJson"] = shared_credentials
        if shared_service_account and "serviceAccountJson" not in payload:
            payload["serviceAccountJson"] = shared_service_account
        env_url = os.getenv(f"SEO_AD_BOT_{provider_suffix}_PROVIDER_URL", "").strip()
        if env_url and not payload.get("providerUrl"):
            payload["providerUrl"] = env_url
        return payload
    return {}


def _has_access_credentials(provider: ConnectorKind, config: dict[str, Any]) -> bool:
    def has_secret(keys: list[str], env_keys: list[str]) -> bool:
        for key in keys:
            if str(config.get(key) or "").strip():
                return True
        for env_key in env_keys:
            if str(os.getenv(env_key, "")).strip():
                return True
        return False

    if provider == ConnectorKind.search_console:
        return has_secret(
            ["accessToken", "credentialsJson", "serviceAccountJson"],
            [
                "SEO_AD_BOT_SEARCH_CONSOLE_ACCESS_TOKEN",
                "SEO_AD_BOT_SEARCH_CONSOLE_CREDENTIALS_JSON",
                "SEO_AD_BOT_SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON",
            ],
        )
    if provider == ConnectorKind.ga4:
        return has_secret(
            ["accessToken", "credentialsJson", "serviceAccountJson"],
            [
                "SEO_AD_BOT_GA4_ACCESS_TOKEN",
                "SEO_AD_BOT_GA4_CREDENTIALS_JSON",
                "SEO_AD_BOT_GA4_SERVICE_ACCOUNT_JSON",
            ],
        )
    if provider == ConnectorKind.github:
        return has_secret(
            ["accessToken", "credentialsJson", "serviceAccountJson"],
            [
                "SEO_AD_BOT_GITHUB_ACCESS_TOKEN",
                "SEO_AD_BOT_GITHUB_CREDENTIALS_JSON",
                "SEO_AD_BOT_GITHUB_SERVICE_ACCOUNT_JSON",
            ],
        )
    if provider == ConnectorKind.cms:
        return bool(config.get("endpoint") or config.get("draftEndpoint")) and has_secret(
            ["authToken", "accessToken", "credentialsJson", "serviceAccountJson"],
            [
                "SEO_AD_BOT_CMS_ACCESS_TOKEN",
                "SEO_AD_BOT_CMS_CREDENTIALS_JSON",
                "SEO_AD_BOT_CMS_SERVICE_ACCOUNT_JSON",
            ],
        )
    if provider == ConnectorKind.script_api:
        return bool(config.get("endpoint")) and has_secret(
            ["authToken", "accessToken", "credentialsJson", "serviceAccountJson"],
            [
                "SEO_AD_BOT_SCRIPT_ACCESS_TOKEN",
                "SEO_AD_BOT_SCRIPT_CREDENTIALS_JSON",
                "SEO_AD_BOT_SCRIPT_SERVICE_ACCOUNT_JSON",
            ],
        )
    if provider == ConnectorKind.ad_network:
        return bool(config.get("endpoint")) and has_secret(
            ["authToken", "accessToken", "credentialsJson", "serviceAccountJson"],
            [
                "SEO_AD_BOT_AD_NETWORK_ACCESS_TOKEN",
                "SEO_AD_BOT_AD_NETWORK_CREDENTIALS_JSON",
                "SEO_AD_BOT_AD_NETWORK_SERVICE_ACCOUNT_JSON",
            ],
        )
    if provider == ConnectorKind.sitemap:
        if not str(config.get("providerUrl") or "").strip():
            return True
        return has_secret(
            ["accessToken", "authToken", "credentialsJson", "serviceAccountJson"],
            [
                "SEO_AD_BOT_SITEMAP_ACCESS_TOKEN",
                "SEO_AD_BOT_SITEMAP_CREDENTIALS_JSON",
                "SEO_AD_BOT_SITEMAP_SERVICE_ACCOUNT_JSON",
            ],
        )
    if provider == ConnectorKind.playwright:
        if str(config.get("providerUrl") or "").strip():
            return has_secret(
                ["accessToken", "authToken", "credentialsJson", "serviceAccountJson"],
                [
                    "SEO_AD_BOT_PLAYWRIGHT_ACCESS_TOKEN",
                    "SEO_AD_BOT_PLAYWRIGHT_CREDENTIALS_JSON",
                    "SEO_AD_BOT_PLAYWRIGHT_SERVICE_ACCOUNT_JSON",
                ],
            )
        return bool(config.get("enabled"))
    if provider in MARKET_EVIDENCE_CONNECTOR_KINDS:
        suffix = _market_provider_env_suffix(provider)
        if bool(config.get("providerUrl") or config.get("providerUrls")):
            return has_secret(
                ["accessToken", "authToken", "credentialsJson", "serviceAccountJson"],
                [
                    f"SEO_AD_BOT_{suffix}_PROVIDER_ACCESS_TOKEN",
                    f"SEO_AD_BOT_{suffix}_PROVIDER_CREDENTIALS_JSON",
                    f"SEO_AD_BOT_{suffix}_PROVIDER_SERVICE_ACCOUNT_JSON",
                    "SEO_AD_BOT_MARKET_PROVIDER_ACCESS_TOKEN",
                    "SEO_AD_BOT_MARKET_PROVIDER_CREDENTIALS_JSON",
                    "SEO_AD_BOT_MARKET_PROVIDER_SERVICE_ACCOUNT_JSON",
                ],
            )
        return has_secret(
            ["accessToken", "authToken", "credentialsJson", "serviceAccountJson"],
            [
                f"SEO_AD_BOT_{suffix}_PROVIDER_ACCESS_TOKEN",
                f"SEO_AD_BOT_{suffix}_PROVIDER_CREDENTIALS_JSON",
                f"SEO_AD_BOT_{suffix}_PROVIDER_SERVICE_ACCOUNT_JSON",
                "SEO_AD_BOT_MARKET_PROVIDER_ACCESS_TOKEN",
                "SEO_AD_BOT_MARKET_PROVIDER_CREDENTIALS_JSON",
                "SEO_AD_BOT_MARKET_PROVIDER_SERVICE_ACCOUNT_JSON",
            ],
        )
    return True


def build_default_connections(
    project_id: str,
    intake: SiteIntake,
    settings: Optional[Settings] = None,
) -> list[ProjectConnection]:
    settings = settings or get_settings()
    connections: list[ProjectConnection] = []
    providers = list(INGESTION_CONNECTOR_KINDS)
    providers.extend(provider for provider in MARKET_EVIDENCE_CONNECTOR_KINDS if _market_provider_configured(settings, intake, provider))
    for provider in providers:
        config = _connection_config(provider, intake, settings)
        status = ConnectorStatus.synthetic
        if provider == ConnectorKind.github and not intake.repo_url:
            status = ConnectorStatus.unavailable
        elif provider == ConnectorKind.cms and not intake.cms_name:
            status = ConnectorStatus.unavailable
        elif provider in {ConnectorKind.search_console, ConnectorKind.ga4} and not _has_access_credentials(provider, config):
            status = ConnectorStatus.missing_credentials
        elif provider == ConnectorKind.github and not _has_access_credentials(provider, config):
            status = ConnectorStatus.missing_credentials
        elif provider == ConnectorKind.cms and not _has_access_credentials(provider, config):
            status = ConnectorStatus.missing_credentials
        elif provider == ConnectorKind.script_api and not _has_access_credentials(provider, config):
            status = ConnectorStatus.missing_credentials
        elif provider == ConnectorKind.ad_network and not _has_access_credentials(provider, config):
            status = ConnectorStatus.missing_credentials
        elif provider == ConnectorKind.sitemap and not _has_access_credentials(provider, config):
            status = ConnectorStatus.missing_credentials
        elif provider == ConnectorKind.playwright and not _has_access_credentials(provider, config):
            status = ConnectorStatus.missing_credentials if config.get("providerUrl") else status
        connection = ProjectConnection(
            connection_id=new_id("conn"),
            provider=provider,
            label=_connection_label(provider),
            enabled=True,
            status=status,
            config=config,
            details={"summary": f"{_connection_label(provider)} initialized."},
            provenance=[f"project={project_id}", f"host={_site_host(intake)}"],
        )
        connections.append(connection)
    return connections


def _fetch_text(url: str, timeout: int = 6) -> str:
    request = Request(url, headers={"User-Agent": "SEO-AD-AutoPilot/1.0"})
    with urlopen(request, timeout=timeout) as response:  # nosec - controlled, read-only fetch
        body = response.read()
    return body.decode("utf-8", errors="replace")


def _extract_token_and_header(value: str) -> tuple[str, bool, str]:
    text = str(value or "").strip()
    if not text:
        return "", False, "Authorization"
    if text[:1] not in {"{", "["}:
        return text, False, "Authorization"
    try:
        parsed = json.loads(text)
    except Exception:
        return text, False, "Authorization"
    auth_header = "Authorization"
    candidates: list[Any] = []
    if isinstance(parsed, dict):
        auth_header = str(parsed.get("authHeader") or parsed.get("headerName") or auth_header).strip() or "Authorization"
        candidates.extend(
            [
                parsed.get("accessToken"),
                parsed.get("access_token"),
                parsed.get("token"),
                parsed.get("authToken"),
                parsed.get("privateKey"),
            ]
        )
        credentials = parsed.get("credentials")
        if isinstance(credentials, dict):
            candidates.extend(
                [
                    credentials.get("accessToken"),
                    credentials.get("access_token"),
                    credentials.get("token"),
                    credentials.get("authToken"),
                ]
            )
    for candidate in candidates:
        candidate_text = str(candidate or "").strip()
        if candidate_text:
            return candidate_text, True, auth_header
    return text, True, auth_header


def _resolve_credential_with_header(
    config: dict[str, Any],
    keys: list[str],
    env_keys: list[str],
) -> tuple[str, str, str]:
    for key in keys:
        value = str(config.get(key) or "").strip()
        if value:
            parsed_value, parsed, auth_header = _extract_token_and_header(value)
            return parsed_value, ("config:json" if parsed else "config"), auth_header
    for env_key in env_keys:
        value = str(os.getenv(env_key, "")).strip()
        if value:
            parsed_value, parsed, auth_header = _extract_token_and_header(value)
            return parsed_value, (f"env:{env_key}:json" if parsed else f"env:{env_key}"), auth_header
    return "", "none", "Authorization"


def _resolve_credential(config: dict[str, Any], keys: list[str], env_keys: list[str]) -> tuple[str, str]:
    token, source, _ = _resolve_credential_with_header(config, keys, env_keys)
    return token, source


def _http_json(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[dict[str, str]] = None,
    payload: Optional[dict[str, Any]] = None,
    timeout: int = 10,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"User-Agent": "SEO-AD-AutoPilot/1.0", "Accept": "application/json"}
    if payload is not None:
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = Request(url, data=data, headers=request_headers, method=method)
    with urlopen(request, timeout=timeout) as response:  # nosec - controlled provider call
        body = response.read().decode("utf-8", errors="replace")
        if not body:
            return {"status": response.status}
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"raw": body, "status": response.status}


def _extract_sitemap_locations(payload: Any) -> list[str]:
    def add_location(target: list[str], value: Any) -> None:
        if isinstance(value, str):
            text = value.strip()
            if text and text not in target:
                target.append(text)
        elif isinstance(value, dict):
            for key in ("loc", "url", "location", "href"):
                add_location(target, value.get(key))

    locations: list[str] = []
    if isinstance(payload, dict):
        for key in ("locations", "urls", "sitemapUrls", "sitemap_urls"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    add_location(locations, item)
            else:
                add_location(locations, value)
        sitemaps = payload.get("sitemaps")
        if isinstance(sitemaps, list):
            for item in sitemaps:
                add_location(locations, item)
        raw = payload.get("raw")
        if isinstance(raw, str):
            locations.extend(re.findall(r"<loc>([^<]+)</loc>", raw, flags=re.IGNORECASE))
    elif isinstance(payload, list):
        for item in payload:
            add_location(locations, item)
    elif isinstance(payload, str):
        locations.extend(re.findall(r"<loc>([^<]+)</loc>", payload, flags=re.IGNORECASE))
    deduped: list[str] = []
    for location in locations:
        location_text = str(location or "").strip()
        if location_text and location_text not in deduped:
            deduped.append(location_text)
    return deduped


def _page_snapshot_from_payload(payload: Any, fallback_url: str) -> Optional[PageSnapshot]:
    if not isinstance(payload, dict):
        return None
    snapshot = payload.get("snapshot")
    if isinstance(snapshot, dict):
        payload = snapshot
    if not isinstance(payload, dict):
        return None
    title = str(payload.get("title") or payload.get("pageTitle") or payload.get("name") or "").strip()
    description = str(payload.get("description") or payload.get("metaDescription") or payload.get("summary") or "").strip()
    if not title and not description:
        return None
    performance_budget = payload.get("performanceBudget") if isinstance(payload.get("performanceBudget"), dict) else {}
    snapshot_kwargs = {
        "url": str(payload.get("url") or payload.get("pageUrl") or fallback_url).strip() or fallback_url,
        "title": title or fallback_url,
        "description": description or "",
        "headings": [str(item).strip() for item in _coerce_list(payload.get("headings") or payload.get("headingTexts"))],
        "word_count": int(payload.get("wordCount") or payload.get("word_count") or 0),
        "internal_links": int(payload.get("internalLinks") or payload.get("internal_links") or 0),
        "external_links": int(payload.get("externalLinks") or payload.get("external_links") or 0),
        "images": int(payload.get("images") or payload.get("imageCount") or 0),
        "missing_alt_count": int(payload.get("missingAltCount") or payload.get("missing_alt_count") or 0),
        "structured_data": [str(item).strip() for item in _coerce_list(payload.get("structuredData") or payload.get("structured_data"))],
        "cta_count": int(payload.get("ctaCount") or payload.get("cta_count") or 0),
        "performance_budget": PagePerformanceBudget(
            lcp_ms=int(performance_budget.get("lcpMs") or performance_budget.get("lcp_ms") or payload.get("lcpMs") or payload.get("lcp_ms") or 0),
            cls=float(performance_budget.get("cls") or performance_budget.get("clsScore") or payload.get("cls") or 0.0),
            inp_ms=int(performance_budget.get("inpMs") or performance_budget.get("inp_ms") or payload.get("inpMs") or payload.get("inp_ms") or 0),
        ),
    }
    return PageSnapshot(**snapshot_kwargs)


def _http_failure_code(exc: HTTPError, provider: str) -> str:
    code = int(getattr(exc, "code", 0) or 0)
    if code == 401:
        return f"{provider}_AUTH_INVALID"
    if code == 403:
        return f"{provider}_PERMISSION_DENIED"
    if code == 404:
        return f"{provider}_ENDPOINT_NOT_FOUND"
    if code == 408:
        return f"{provider}_REQUEST_TIMEOUT"
    if code == 409:
        return f"{provider}_CONFLICT"
    if code == 422:
        return f"{provider}_VALIDATION_FAILED"
    if code == 429:
        return f"{provider}_RATE_LIMITED"
    if code >= 500:
        return f"{provider}_UNAVAILABLE"
    return f"{provider}_HTTP_ERROR"


def _exception_failure_code(exc: Exception, provider: str) -> str:
    message = str(exc).lower()
    if "timed out" in message or "timeout" in message:
        return f"{provider}_REQUEST_TIMEOUT"
    if "name or service not known" in message or "temporary failure in name resolution" in message:
        return f"{provider}_NETWORK_ERROR"
    if "connection refused" in message or "connection reset" in message:
        return f"{provider}_NETWORK_ERROR"
    return f"{provider}_REQUEST_FAILED"


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class BaseConnectorAdapter:
    kind: ConnectorKind
    label: str

    def probe(self, ctx: ConnectorContext) -> tuple[ProjectConnection, SourceEvidence]:
        raise NotImplementedError

    def _build_connection(
        self,
        ctx: ConnectorContext,
        *,
        status: ConnectorStatus,
        provenance: Iterable[str],
        details: dict[str, Any],
        fallback_reason: Optional[str] = None,
        failure_code: Optional[str] = None,
        retryable: bool = False,
        latency_ms: Optional[int] = None,
    ) -> ProjectConnection:
        connection = ctx.connection.model_copy()
        connection.status = status
        connection.last_checked_at = utcnow()
        connection.last_synced_at = utcnow()
        connection.next_sync_at = utcnow() + timedelta(minutes=max(15, int(ctx.connection.config.get("syncIntervalMinutes", 60))))
        connection.provenance = list(provenance)
        connection.details = details
        if fallback_reason:
            connection.details["fallbackReason"] = fallback_reason
        if failure_code:
            connection.details["errorCode"] = failure_code
        connection.details["retryable"] = retryable
        if latency_ms is not None:
            connection.details["latencyMs"] = latency_ms
        return connection


class SearchConsoleAdapter(BaseConnectorAdapter):
    kind = ConnectorKind.search_console
    label = "Search Console"

    def probe(self, ctx: ConnectorContext) -> tuple[ProjectConnection, SourceEvidence]:
        started = time.perf_counter()
        property_name = str(ctx.connection.config.get("property") or _site_host(ctx.intake))
        access_token, auth_source = _resolve_credential(
            ctx.connection.config,
            ["accessToken", "credentialsJson", "serviceAccountJson"],
            ["SEO_AD_BOT_SEARCH_CONSOLE_ACCESS_TOKEN"],
        )
        site_url = str(ctx.connection.config.get("siteUrl") or ctx.intake.url)
        fallback_reason = None
        failure_code = None
        retryable = False

        if not ctx.connection.enabled:
            fallback_reason = "connector disabled"
            status = ConnectorStatus.unavailable
            keywords = ctx.intake.keywords[:5] or [property_name]
            summary = "Search Console connector disabled; synthetic metrics retained."
            details = {
                "enabled": False,
                "property": property_name,
                "queryThemes": keywords,
                "clickTrend": ctx.connection.config.get("clickTrend", "stable"),
                "impressions": 1200 + len(keywords) * 80,
                "authSource": auth_source,
            }
        elif not access_token:
            fallback_reason = "missing accessToken"
            failure_code = "CONFIG_MISSING_ACCESS_TOKEN"
            status = ConnectorStatus.missing_credentials
            keywords = ctx.intake.keywords[:5] or [property_name]
            summary = f"Search Console property {property_name} is configured but lacks credentials."
            details = {
                "property": property_name,
                "queryThemes": keywords,
                "clickTrend": ctx.connection.config.get("clickTrend", "stable"),
                "impressions": 1200 + len(keywords) * 80,
                "authSource": auth_source,
            }
            retryable = True
        else:
            default_endpoint = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{site_url}/searchAnalytics/query"
            endpoints = _candidate_endpoints(
                ctx.connection.config,
                ["endpoints", "endpoint", "apiEndpoints", "apiEndpoint"],
                default_endpoint,
            )
            payload = {
                "startDate": ctx.connection.config.get("startDate")
                or (date.today() - timedelta(days=28)).isoformat(),
                "endDate": ctx.connection.config.get("endDate") or date.today().isoformat(),
                "dimensions": ["query"],
                "rowLimit": int(ctx.connection.config.get("rowLimit", 10)),
            }
            endpoint_attempts: list[dict[str, Any]] = []
            connected_details: Optional[dict[str, Any]] = None
            last_error_message = "search console request failed"
            for endpoint in endpoints:
                try:
                    response = _http_json(
                        endpoint,
                        method="POST",
                        headers={"Authorization": f"Bearer {access_token}"},
                        payload=payload,
                    )
                    if "raw" in response:
                        raise ValueError("SEARCH_CONSOLE_INVALID_PAYLOAD: non-json response")
                    rows = response.get("rows", [])
                    if not isinstance(rows, list):
                        raise ValueError("SEARCH_CONSOLE_INVALID_PAYLOAD: rows is not a list")
                    top_queries = [
                        " ".join(str(value) for value in row.get("keys", [])[:2]).strip() or "unknown"
                        for row in rows[:5]
                        if isinstance(row, dict)
                    ]
                    clicks = sum(int(row.get("clicks", 0)) for row in rows[:10] if isinstance(row, dict))
                    impressions = sum(int(row.get("impressions", 0)) for row in rows[:10] if isinstance(row, dict))
                    endpoint_attempts.append({"endpoint": endpoint, "status": "connected"})
                    connected_details = {
                        "property": property_name,
                        "endpoint": endpoint,
                        "endpointsConfigured": endpoints,
                        "endpointsTried": [item.get("endpoint") for item in endpoint_attempts],
                        "endpointAttempts": endpoint_attempts,
                        "queryThemes": top_queries or ctx.intake.keywords[:5] or [property_name],
                        "clicks": clicks,
                        "impressions": impressions,
                        "rowCount": len(rows),
                        "authSource": auth_source,
                    }
                    break
                except HTTPError as exc:
                    current_failure = _http_failure_code(exc, "SEARCH_CONSOLE")
                    endpoint_attempts.append(
                        {
                            "endpoint": endpoint,
                            "status": "error",
                            "failureCode": current_failure,
                            "message": str(exc),
                            "retryable": 500 <= getattr(exc, "code", 500) < 600,
                        }
                    )
                    retryable = bool(retryable or (500 <= getattr(exc, "code", 500) < 600))
                    failure_code = current_failure
                    last_error_message = str(exc)
                except Exception as exc:
                    message = str(exc)
                    if "SEARCH_CONSOLE_INVALID_PAYLOAD" in message:
                        current_failure = "SEARCH_CONSOLE_INVALID_PAYLOAD"
                        current_retryable = False
                    else:
                        current_failure = _exception_failure_code(exc, "SEARCH_CONSOLE")
                        current_retryable = True
                    endpoint_attempts.append(
                        {
                            "endpoint": endpoint,
                            "status": "error",
                            "failureCode": current_failure,
                            "message": message,
                            "retryable": current_retryable,
                        }
                    )
                    retryable = bool(retryable or current_retryable)
                    failure_code = current_failure
                    last_error_message = message
            if connected_details is not None:
                status = ConnectorStatus.connected
                summary = f"Search Console property {property_name} returned query rows."
                details = connected_details
            else:
                status = ConnectorStatus.error
                summary = "Search Console API request failed across all configured endpoints."
                fallback_reason = last_error_message
                details = {
                    "property": property_name,
                    "endpoint": endpoints[-1] if endpoints else default_endpoint,
                    "endpointsConfigured": endpoints,
                    "endpointsTried": [item.get("endpoint") for item in endpoint_attempts],
                    "endpointAttempts": endpoint_attempts,
                    "error": last_error_message,
                    "authSource": auth_source,
                }
        latency_ms = int((time.perf_counter() - started) * 1000)
        connection = self._build_connection(
            ctx,
            status=status,
            provenance=[f"property={property_name}", f"host={_site_host(ctx.intake)}"],
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
        )
        evidence = SourceEvidence(
            provider=self.kind,
            status=status,
            summary=summary,
            provenance=connection.provenance,
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
            auth_source=auth_source,
        )
        return connection, evidence


class Ga4Adapter(BaseConnectorAdapter):
    kind = ConnectorKind.ga4
    label = "GA4"

    def probe(self, ctx: ConnectorContext) -> tuple[ProjectConnection, SourceEvidence]:
        started = time.perf_counter()
        property_id = str(ctx.connection.config.get("propertyId") or ctx.connection.config.get("property") or "")
        access_token, auth_source = _resolve_credential(
            ctx.connection.config,
            ["accessToken", "credentialsJson", "serviceAccountJson"],
            ["SEO_AD_BOT_GA4_ACCESS_TOKEN"],
        )
        fallback_reason = None
        failure_code = None
        retryable = False
        if not ctx.connection.enabled:
            fallback_reason = "connector disabled"
            status = ConnectorStatus.unavailable
            summary = "GA4 connector disabled; synthetic traffic baseline retained."
            details = {
                "enabled": False,
                "property": property_id or _site_host(ctx.intake),
                "sessions": 3400 + len(ctx.intake.keywords) * 120,
                "conversions": 42 + len(ctx.intake.brand_whitelist),
                "engagementRate": 0.71,
                "authSource": auth_source,
            }
        elif not access_token:
            fallback_reason = "missing accessToken"
            failure_code = "CONFIG_MISSING_ACCESS_TOKEN"
            status = ConnectorStatus.missing_credentials
            summary = f"GA4 property {property_id or _site_host(ctx.intake)} is configured but lacks credentials."
            details = {
                "property": property_id or _site_host(ctx.intake),
                "sessions": 3400 + len(ctx.intake.keywords) * 120,
                "conversions": 42 + len(ctx.intake.brand_whitelist),
                "engagementRate": 0.71,
                "authSource": auth_source,
            }
            retryable = True
        else:
            default_endpoint = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
            endpoints = _candidate_endpoints(
                ctx.connection.config,
                ["endpoints", "endpoint", "apiEndpoints", "apiEndpoint"],
                default_endpoint,
            )
            payload = {
                "dateRanges": [
                    {
                        "startDate": ctx.connection.config.get("startDate")
                        or (date.today() - timedelta(days=28)).isoformat(),
                        "endDate": ctx.connection.config.get("endDate") or date.today().isoformat(),
                    }
                ],
                "metrics": [{"name": "sessions"}, {"name": "conversions"}, {"name": "engagementRate"}],
                "dimensions": [{"name": "sessionDefaultChannelGroup"}],
            }
            endpoint_attempts: list[dict[str, Any]] = []
            connected_details: Optional[dict[str, Any]] = None
            last_error_message = "ga4 request failed"
            for endpoint in endpoints:
                try:
                    response = _http_json(
                        endpoint,
                        method="POST",
                        headers={"Authorization": f"Bearer {access_token}"},
                        payload=payload,
                    )
                    if "raw" in response:
                        raise ValueError("GA4_INVALID_PAYLOAD: non-json response")
                    rows = response.get("rows", [])
                    if not isinstance(rows, list):
                        raise ValueError("GA4_INVALID_PAYLOAD: rows is not a list")
                    sessions = 0
                    conversions = 0
                    engagement_rate = 0.0
                    for row in rows[:5]:
                        if not isinstance(row, dict):
                            continue
                        metrics = row.get("metricValues", [])
                        if not isinstance(metrics, list):
                            raise ValueError("GA4_INVALID_PAYLOAD: metricValues is not a list")
                        if len(metrics) >= 1:
                            sessions += int(float(metrics[0].get("value", 0)))
                        if len(metrics) >= 2:
                            conversions += int(float(metrics[1].get("value", 0)))
                        if len(metrics) >= 3:
                            engagement_rate = max(engagement_rate, float(metrics[2].get("value", 0)))
                    endpoint_attempts.append({"endpoint": endpoint, "status": "connected"})
                    connected_details = {
                        "property": property_id or _site_host(ctx.intake),
                        "endpoint": endpoint,
                        "endpointsConfigured": endpoints,
                        "endpointsTried": [item.get("endpoint") for item in endpoint_attempts],
                        "endpointAttempts": endpoint_attempts,
                        "sessions": sessions or 3400 + len(ctx.intake.keywords) * 120,
                        "conversions": conversions or 42 + len(ctx.intake.brand_whitelist),
                        "engagementRate": round(engagement_rate or 0.71, 2),
                        "rowCount": len(rows),
                        "authSource": auth_source,
                    }
                    break
                except HTTPError as exc:
                    current_failure = _http_failure_code(exc, "GA4")
                    endpoint_attempts.append(
                        {
                            "endpoint": endpoint,
                            "status": "error",
                            "failureCode": current_failure,
                            "message": str(exc),
                            "retryable": 500 <= getattr(exc, "code", 500) < 600,
                        }
                    )
                    retryable = bool(retryable or (500 <= getattr(exc, "code", 500) < 600))
                    failure_code = current_failure
                    last_error_message = str(exc)
                except Exception as exc:
                    message = str(exc)
                    if "GA4_INVALID_PAYLOAD" in message:
                        current_failure = "GA4_INVALID_PAYLOAD"
                        current_retryable = False
                    else:
                        current_failure = _exception_failure_code(exc, "GA4")
                        current_retryable = True
                    endpoint_attempts.append(
                        {
                            "endpoint": endpoint,
                            "status": "error",
                            "failureCode": current_failure,
                            "message": message,
                            "retryable": current_retryable,
                        }
                    )
                    retryable = bool(retryable or current_retryable)
                    failure_code = current_failure
                    last_error_message = message
            if connected_details is not None:
                status = ConnectorStatus.connected
                summary = f"GA4 property {property_id or _site_host(ctx.intake)} returned baseline rows."
                details = connected_details
            else:
                status = ConnectorStatus.error
                summary = "GA4 API request failed across all configured endpoints."
                fallback_reason = last_error_message
                details = {
                    "property": property_id or _site_host(ctx.intake),
                    "endpoint": endpoints[-1] if endpoints else default_endpoint,
                    "endpointsConfigured": endpoints,
                    "endpointsTried": [item.get("endpoint") for item in endpoint_attempts],
                    "endpointAttempts": endpoint_attempts,
                    "error": last_error_message,
                    "authSource": auth_source,
                }
        latency_ms = int((time.perf_counter() - started) * 1000)
        connection = self._build_connection(
            ctx,
            status=status,
            provenance=[f"property={property_id or _site_host(ctx.intake)}", f"locale={ctx.intake.locale}"],
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
        )
        evidence = SourceEvidence(
            provider=self.kind,
            status=status,
            summary=summary,
            provenance=connection.provenance,
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
            auth_source=auth_source,
        )
        return connection, evidence


class GitHubAdapter(BaseConnectorAdapter):
    kind = ConnectorKind.github
    label = "GitHub"

    def probe(self, ctx: ConnectorContext) -> tuple[ProjectConnection, SourceEvidence]:
        started = time.perf_counter()
        repo_url = str(ctx.connection.config.get("repoUrl") or ctx.intake.repo_url or "")
        access_token, auth_source, auth_header = _resolve_credential_with_header(
            ctx.connection.config,
            ["accessToken", "credentialsJson", "serviceAccountJson"],
            [
                "SEO_AD_BOT_GITHUB_ACCESS_TOKEN",
                "SEO_AD_BOT_GITHUB_CREDENTIALS_JSON",
                "SEO_AD_BOT_GITHUB_SERVICE_ACCOUNT_JSON",
            ],
        )
        owner = str(ctx.connection.config.get("owner") or "")
        repo = str(ctx.connection.config.get("repo") or "")
        if repo_url and (not owner or not repo):
            path = urlparse(repo_url).path.strip("/")
            if "/" in path:
                owner, repo = path.split("/", 1)
        fallback_reason = None
        failure_code = None
        retryable = False
        default_endpoint = f"https://api.github.com/repos/{owner}/{repo}/pulls" if owner and repo else ""
        endpoints = _candidate_endpoints(ctx.connection.config, ["apiEndpoints", "apiEndpoint"], default_endpoint)
        details = {
            "repoUrl": repo_url,
            "branch": ctx.connection.config.get("branch", "main"),
            "authSource": auth_source,
            "authHeader": auth_header,
            "endpointsConfigured": endpoints,
            "endpointsTried": [],
        }
        if not ctx.connection.enabled:
            fallback_reason = "connector disabled"
            status = ConnectorStatus.unavailable
            summary = "Repository connector disabled; local release manifest retained."
        elif not repo_url or not access_token or not owner or not repo:
            fallback_reason = "missing repoUrl/accessToken/owner/repo"
            failure_code = "CONFIG_MISSING_GITHUB"
            status = ConnectorStatus.missing_credentials
            summary = "No repository credentials are complete enough to create a PR."
            retryable = True
        elif not ctx.connection.config.get("headBranch"):
            fallback_reason = "missing headBranch"
            failure_code = "CONFIG_MISSING_HEAD_BRANCH"
            status = ConnectorStatus.missing_credentials
            summary = "Repository connected, but no source branch was supplied for PR creation."
            retryable = True
        else:
            payload = {
                "title": ctx.connection.config.get("title")
                or f"SEO-AD AutoPilot release for {ctx.project_id}",
                "body": ctx.connection.config.get("body")
                or "Preview-first growth release generated by SEO-AD AutoPilot.",
                "head": str(ctx.connection.config.get("headBranch")),
                "base": str(ctx.connection.config.get("baseBranch") or "main"),
                "draft": bool(ctx.connection.config.get("draft", True)),
            }
            last_error: Optional[str] = None
            last_failure_code: Optional[str] = None
            for endpoint in endpoints:
                details["endpointsTried"].append(endpoint)
                try:
                    response = _http_json(
                        endpoint,
                        method="POST",
                        headers={str(auth_header or "Authorization"): f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
                        payload=payload,
                    )
                    if "raw" in response:
                        raise ValueError("GITHUB_INVALID_PAYLOAD: non-json response")
                    pr_url = str(response.get("html_url") or response.get("url") or "")
                    pr_number = response.get("number")
                    strict = bool(get_settings().strict_providers)
                    if pr_url:
                        status = ConnectorStatus.connected
                        summary = f"Created GitHub pull request {pr_number or ''} for {owner}/{repo}."
                        details = {
                            **details,
                            "endpoint": endpoint,
                            "owner": owner,
                            "repo": repo,
                            "branch": payload["head"],
                            "base": payload["base"],
                            "prUrl": pr_url,
                            "prNumber": pr_number,
                            "authSource": auth_source,
                            "authHeader": auth_header,
                        }
                        last_error = None
                        last_failure_code = None
                        break
                    status = ConnectorStatus.error if strict else ConnectorStatus.synthetic
                    fallback_reason = "GitHub API returned no PR URL."
                    failure_code = "GITHUB_INVALID_RESPONSE"
                    retryable = True
                    summary = "GitHub API accepted the request but returned no PR URL."
                    details = {
                        **details,
                        "endpoint": endpoint,
                        "owner": owner,
                        "repo": repo,
                        "authSource": auth_source,
                    }
                    last_error = fallback_reason
                    last_failure_code = failure_code
                except HTTPError as exc:
                    retryable = 500 <= getattr(exc, "code", 500) < 600
                    last_error = f"GitHub API error {getattr(exc, 'code', 'unknown')}"
                    last_failure_code = _http_failure_code(exc, "GITHUB")
                    details = {**details, "owner": owner, "repo": repo, "endpoint": endpoint, "error": str(exc), "authSource": auth_source}
                    continue
                except Exception as exc:
                    message = str(exc)
                    if "GITHUB_INVALID_PAYLOAD" in message:
                        retryable = False
                        last_failure_code = "GITHUB_INVALID_PAYLOAD"
                    else:
                        retryable = True
                        last_failure_code = _exception_failure_code(exc, "GITHUB")
                    last_error = message
                    details = {**details, "owner": owner, "repo": repo, "endpoint": endpoint, "error": str(exc), "authSource": auth_source}
                    continue
            else:
                status = ConnectorStatus.error
                summary = "GitHub API request failed across all configured endpoints."
            if status != ConnectorStatus.connected and last_error:
                fallback_reason = last_error
                failure_code = last_failure_code
        latency_ms = int((time.perf_counter() - started) * 1000)
        connection = self._build_connection(
            ctx,
            status=status,
            provenance=[f"repo={repo_url or 'unset'}"],
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
        )
        evidence = SourceEvidence(
            provider=self.kind,
            status=status,
            summary=summary,
            provenance=connection.provenance,
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
            auth_source=auth_source,
        )
        return connection, evidence


class CmsAdapter(BaseConnectorAdapter):
    kind = ConnectorKind.cms
    label = "CMS"

    def probe(self, ctx: ConnectorContext) -> tuple[ProjectConnection, SourceEvidence]:
        started = time.perf_counter()
        cms_name = str(ctx.connection.config.get("cmsName") or ctx.intake.cms_name or "")
        default_endpoint = str(ctx.connection.config.get("draftEndpoint") or ctx.connection.config.get("endpoint") or "")
        endpoints = _candidate_endpoints(ctx.connection.config, ["draftEndpoints", "draftEndpoint", "endpoints", "endpoint"], default_endpoint)
        access_token, auth_source, auth_header = _resolve_credential_with_header(
            ctx.connection.config,
            ["authToken", "accessToken", "credentialsJson", "serviceAccountJson"],
            [
                "SEO_AD_BOT_CMS_ACCESS_TOKEN",
                "SEO_AD_BOT_CMS_CREDENTIALS_JSON",
                "SEO_AD_BOT_CMS_SERVICE_ACCOUNT_JSON",
            ],
        )
        fallback_reason = None
        failure_code = None
        retryable = False
        details = {
            "cmsName": cms_name,
            "draftStatus": "ready" if cms_name else "unavailable",
            "authSource": auth_source,
            "authHeader": auth_header,
            "endpointsConfigured": endpoints,
            "endpointsTried": [],
        }
        if not ctx.connection.enabled:
            fallback_reason = "connector disabled"
            status = ConnectorStatus.unavailable
            summary = "CMS connector disabled; local drafts retained."
        elif not cms_name or not endpoints or not access_token:
            fallback_reason = "missing cmsName/endpoint/authToken"
            failure_code = "CONFIG_MISSING_CMS"
            status = ConnectorStatus.missing_credentials
            summary = "CMS draft publishing is not fully configured."
            retryable = True
        else:
            payload = {
                "projectId": ctx.project_id,
                "siteUrl": ctx.intake.url,
                "cmsName": cms_name,
                "mode": "draft",
                "source": "SEO-AD AutoPilot",
            }
            last_error: Optional[str] = None
            last_failure_code: Optional[str] = None
            for endpoint in endpoints:
                details["endpointsTried"].append(endpoint)
                try:
                    response = _http_json(
                        endpoint,
                        method="POST",
                        headers={str(auth_header or "Authorization"): f"Bearer {access_token}"},
                        payload=payload,
                    )
                    if "raw" in response:
                        raise ValueError("CMS_INVALID_PAYLOAD: non-json response")
                    draft_id = str(response.get("draftId") or response.get("id") or response.get("draft_id") or "")
                    strict = bool(get_settings().strict_providers)
                    if draft_id:
                        status = ConnectorStatus.connected
                        summary = f"CMS {cms_name} accepted a draft update."
                        details = {
                            **details,
                            "endpoint": endpoint,
                            "draftId": draft_id or endpoint,
                            "draftStatus": "ready",
                            "authSource": auth_source,
                            "authHeader": auth_header,
                        }
                        last_error = None
                        last_failure_code = None
                        break
                    status = ConnectorStatus.error if strict else ConnectorStatus.synthetic
                    fallback_reason = "CMS API returned no draft identifier."
                    failure_code = "CMS_INVALID_RESPONSE"
                    retryable = True
                    summary = "CMS API accepted the write but returned no draft identifier."
                    details = {**details, "endpoint": endpoint, "draftStatus": "ready", "authSource": auth_source}
                    last_error = fallback_reason
                    last_failure_code = failure_code
                except HTTPError as exc:
                    retryable = 500 <= getattr(exc, "code", 500) < 600
                    last_error = f"CMS API error {getattr(exc, 'code', 'unknown')}"
                    last_failure_code = _http_failure_code(exc, "CMS")
                    details = {**details, "endpoint": endpoint, "error": str(exc), "authSource": auth_source}
                except Exception as exc:
                    message = str(exc)
                    if "CMS_INVALID_PAYLOAD" in message:
                        retryable = False
                        last_failure_code = "CMS_INVALID_PAYLOAD"
                    else:
                        retryable = True
                        last_failure_code = _exception_failure_code(exc, "CMS")
                    last_error = message
                    details = {**details, "endpoint": endpoint, "error": str(exc), "authSource": auth_source}
            else:
                status = ConnectorStatus.error
                summary = "CMS draft write failed across all configured endpoints."
            if status != ConnectorStatus.connected and last_error:
                fallback_reason = last_error
                failure_code = last_failure_code
        latency_ms = int((time.perf_counter() - started) * 1000)
        connection = self._build_connection(
            ctx,
            status=status,
            provenance=[f"cms={cms_name or 'unset'}"],
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
        )
        evidence = SourceEvidence(
            provider=self.kind,
            status=status,
            summary=summary,
            provenance=connection.provenance,
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
            auth_source=auth_source,
        )
        return connection, evidence


class AdNetworkAdapter(BaseConnectorAdapter):
    kind = ConnectorKind.ad_network
    label = "Ad Network"

    @staticmethod
    def _normalize_provider_family(value: Any) -> str:
        normalized = str(value or "").strip().lower().replace("_", "-").replace(" ", "-")
        aliases = {
            "adsense": "adsense",
            "google-adsense": "adsense",
            "google-ad-manager": "gam",
            "admanager": "gam",
            "gam": "gam",
            "mediavine": "mediavine",
            "ezoic": "ezoic",
            "freestar": "freestar",
            "raptive": "raptive",
            "adthrive": "raptive",
            "monumetric": "monumetric",
            "pubmatic": "pubmatic",
            "seedtag": "seedtag",
            "gumgum": "gumgum",
            "sovrn": "sovrn",
            "sharethrough": "sharethrough",
            "revcontent": "revcontent",
            "outbrain": "outbrain",
            "taboola": "taboola",
            "yieldmo": "yieldmo",
            "teads": "teads",
            "magnite": "magnite",
            "triplelift": "triplelift",
            "indexexchange": "index_exchange",
            "indexexchangeplatform": "index_exchange",
            "adform": "adform",
            "criteo": "criteo",
            "undertone": "undertone",
            "generic": "generic",
        }
        return aliases.get(normalized, normalized or "generic")

    @staticmethod
    def _provider_display_name(family: str) -> str:
        labels = {
            "adsense": "Google AdSense",
            "gam": "Google Ad Manager",
            "mediavine": "Mediavine",
            "ezoic": "Ezoic",
            "freestar": "Freestar",
            "raptive": "Raptive",
            "monumetric": "Monumetric",
            "pubmatic": "PubMatic",
            "seedtag": "Seedtag",
            "gumgum": "GumGum",
            "sovrn": "Sovrn",
            "sharethrough": "Sharethrough",
            "revcontent": "RevContent",
            "outbrain": "Outbrain",
            "taboola": "Taboola",
            "yieldmo": "Yieldmo",
            "teads": "Teads",
            "magnite": "Magnite",
            "triplelift": "TripleLift",
            "index_exchange": "Index Exchange",
            "adform": "AdForm",
            "criteo": "Criteo",
            "undertone": "Undertone",
            "generic": "Ad Network",
        }
        return labels.get(family, family.replace("-", " ").title())

    @staticmethod
    def _provider_slots(family: str) -> list[str]:
        provider_slots = {
            "adsense": ["inline_after_intro", "sidebar", "in_article"],
            "gam": ["header_billboard", "sidebar", "inline_after_content"],
            "mediavine": ["in_content_auto", "sidebar_sticky", "video_anchor"],
            "ezoic": ["sidebar", "in_content", "footer_anchor"],
            "freestar": ["header", "sidebar", "inline_after_content"],
            "raptive": ["sidebar", "in_content", "adhesion_footer"],
            "monumetric": ["sidebar", "inline_after_content", "footer"],
            "pubmatic": ["header", "sidebar", "inline_after_content"],
            "seedtag": ["in_content", "sidebar", "footer_anchor"],
            "gumgum": ["header", "sidebar", "native_in_feed"],
            "sovrn": ["sidebar", "inline_after_content", "footer"],
            "sharethrough": ["in_feed", "inline_after_content", "sidebar"],
            "revcontent": ["inline_after_content", "sidebar", "footer"],
            "outbrain": ["in_feed", "inline_after_content", "sidebar"],
            "taboola": ["in_feed", "inline_after_content", "footer"],
            "yieldmo": ["sidebar", "sticky_footer", "native_in_feed"],
            "teads": ["in_feed", "inline_after_content", "video_anchor"],
            "magnite": ["header", "sidebar", "footer_anchor"],
            "triplelift": ["in_feed", "sidebar", "inline_after_content"],
            "index_exchange": ["header", "sidebar", "inline_after_content"],
            "adform": ["in_feed", "sidebar", "footer_anchor"],
            "criteo": ["native_in_feed", "sidebar", "inline_after_content"],
            "undertone": ["sidebar", "inline_after_content", "adhesion_footer"],
        }
        return provider_slots.get(family, ["sidebar", "inline_after_content"])

    def probe(self, ctx: ConnectorContext) -> tuple[ProjectConnection, SourceEvidence]:
        started = time.perf_counter()
        default_endpoint = str(ctx.connection.config.get("endpoint") or "")
        endpoints = _candidate_endpoints(ctx.connection.config, ["apiEndpoints", "apiEndpoint", "endpoints", "endpoint"], default_endpoint)
        timeout_ms = int(ctx.connection.config.get("timeoutMs") or get_settings().ad_network_provider_timeout_ms or 8000)
        timeout_seconds = max(1, int(timeout_ms / 1000))
        account_id = str(ctx.connection.config.get("accountId") or "")
        provider_family = self._normalize_provider_family(
            ctx.connection.config.get("providerFamily") or ctx.connection.config.get("network") or ctx.connection.config.get("provider")
        )
        provider_name = str(ctx.connection.config.get("providerName") or self._provider_display_name(provider_family))
        settlement_currency = str(ctx.connection.config.get("currency") or "USD").upper()
        policy_tier = str(ctx.connection.config.get("policyTier") or "standard")
        access_token, auth_source, auth_header = _resolve_credential_with_header(
            ctx.connection.config,
            ["authToken", "accessToken", "credentialsJson", "serviceAccountJson"],
            [
                "SEO_AD_BOT_AD_NETWORK_ACCESS_TOKEN",
                "SEO_AD_BOT_AD_NETWORK_CREDENTIALS_JSON",
                "SEO_AD_BOT_AD_NETWORK_SERVICE_ACCOUNT_JSON",
            ],
        )
        strict_mode = bool(get_settings().strict_providers)
        fallback_reason = None
        failure_code = None
        retryable = False
        details = {
            "provider": "ad_network",
            "providerFamily": provider_family,
            "providerName": provider_name,
            "accountId": account_id,
            "endpoint": default_endpoint,
            "endpointsConfigured": endpoints,
            "endpointsTried": [],
            "endpointAttempts": [],
            "timeoutMs": timeout_ms,
            "authSource": auth_source,
            "authHeader": auth_header,
            "settlementCurrency": settlement_currency,
            "policyTier": policy_tier,
            "payoutThreshold": 0.0,
            "geoCoverage": [],
            "providerProgram": "",
            "estimatedRevenueDaily": 0.0,
            "settledRevenueDaily": 0.0,
            "settlementWindow": "",
            "rpm": 0.0,
            "fillRate": 0.0,
            "impressions": 0,
            "clicks": 0,
            "ctr": 0.0,
        }
        if not ctx.connection.enabled:
            fallback_reason = "connector disabled"
            status = ConnectorStatus.unavailable
            summary = "Ad network connector disabled; ad provider checks skipped."
        elif not endpoints or not access_token or not account_id:
            fallback_reason = "missing endpoint/accessToken/accountId"
            failure_code = "CONFIG_MISSING_AD_NETWORK"
            status = ConnectorStatus.missing_credentials
            summary = "Ad network connector is configured but credentials are incomplete."
            retryable = True
            if not strict_mode:
                details = {
                    **details,
                    "estimatedRevenueDaily": 32.0,
                    "settledRevenueDaily": 28.4,
                    "settlementWindow": "T+7 estimated",
                    "rpm": 4.2,
                    "fillRate": 0.58,
                    "impressions": 7600,
                    "clicks": 82,
                    "ctr": 0.0108,
                    "providerRef": f"{provider_family}-synthetic",
                    "inventoryStatus": "synthetic-ready",
                    "recommendedSlots": self._provider_slots(provider_family),
                    "payoutThreshold": 100.0,
                    "geoCoverage": ["US", "CA", "GB"],
                    "providerProgram": "self-serve",
                    "mode": "synthetic-baseline",
                }
        else:
            payload = {"accountId": account_id, "siteUrl": ctx.intake.url, "mode": "validate_inventory"}
            last_error: Optional[str] = None
            last_failure_code: Optional[str] = None
            for endpoint in endpoints:
                details["endpointsTried"].append(endpoint)
                try:
                    response = _http_json(
                        endpoint,
                        method="POST",
                        headers={str(auth_header or "Authorization"): f"Bearer {access_token}"},
                        payload=payload,
                        timeout=timeout_seconds,
                    )
                    provider_account = str(response.get("accountId") or account_id)
                    inventory_status = str(response.get("inventoryStatus") or "ready")
                    response_family = self._normalize_provider_family(
                        response.get("providerFamily") or response.get("network") or response.get("provider")
                    )
                    if response_family != "generic" or provider_family == "generic":
                        provider_family = response_family
                    provider_name = str(response.get("providerName") or self._provider_display_name(provider_family))
                    slots = response.get("recommendedSlots") or self._provider_slots(provider_family)
                    impressions = int(
                        float(
                            response.get("impressions")
                            or response.get("dailyImpressions")
                            or response.get("adImpressions")
                            or response.get("pageviews")
                            or 0
                        )
                        or 0
                    )
                    clicks = int(float(response.get("clicks") or response.get("dailyClicks") or response.get("adClicks") or 0) or 0)
                    fill_rate = float(response.get("fillRate") or response.get("fill_rate") or response.get("matchedRate") or 0.0)
                    rpm = float(
                        response.get("rpm")
                        or response.get("eCPM")
                        or response.get("ecpm")
                        or response.get("pageRpm")
                        or response.get("sessionRpm")
                        or 0.0
                    )
                    estimated_daily = float(
                        response.get("estimatedRevenueDaily")
                        or response.get("dailyRevenue")
                        or response.get("grossRevenueDaily")
                        or response.get("estimatedEarnings")
                        or 0.0
                    )
                    settled_daily = float(
                        response.get("settledRevenueDaily")
                        or response.get("netRevenueDaily")
                        or response.get("settledDailyRevenue")
                        or response.get("earnings")
                        or response.get("publisherRevenueDaily")
                        or 0.0
                    )
                    settlement_window = str(response.get("settlementWindow") or response.get("settlementCadence") or "T+7 estimated")
                    settlement_currency = str(response.get("currency") or response.get("settlementCurrency") or settlement_currency).upper()
                    policy_tier = str(response.get("policyTier") or response.get("monetizationPolicy") or policy_tier)
                    payout_threshold = float(
                        response.get("payoutThreshold")
                        or response.get("minimumPayout")
                        or response.get("minPayout")
                        or 0.0
                    )
                    geo_coverage = _coerce_list(response.get("geoCoverage") or response.get("regions") or response.get("countries"))
                    provider_program = str(response.get("providerProgram") or response.get("program") or response.get("accountProgram") or "")
                    if not impressions:
                        impressions = 9400
                    if clicks <= 0:
                        clicks = max(1, int(impressions * 0.011))
                    if fill_rate <= 0:
                        fill_rate = 0.62
                    if rpm <= 0:
                        rpm = 4.8
                    if estimated_daily <= 0:
                        estimated_daily = round((impressions / 1000.0) * rpm * fill_rate, 2)
                    if settled_daily <= 0:
                        settled_daily = round(estimated_daily * 0.91, 2)
                    ctr = round(clicks / max(impressions, 1), 4)
                    status = ConnectorStatus.connected
                    summary = f"{provider_name} account {provider_account} is connected."
                    details = {
                        **details,
                        "endpoint": endpoint,
                        "endpointAttempts": [
                            *list(details.get("endpointAttempts") or []),
                            {"endpoint": endpoint, "status": "connected"},
                        ],
                        "providerFamily": provider_family,
                        "providerName": provider_name,
                        "accountId": provider_account,
                        "inventoryStatus": inventory_status,
                        "recommendedSlots": slots,
                        "providerRef": str(response.get("providerRef") or response.get("id") or provider_account),
                        "settlementCurrency": settlement_currency,
                        "policyTier": policy_tier,
                        "payoutThreshold": round(payout_threshold, 2),
                        "geoCoverage": geo_coverage,
                        "providerProgram": provider_program,
                        "impressions": impressions,
                        "clicks": clicks,
                        "ctr": ctr,
                        "fillRate": round(fill_rate, 4),
                        "rpm": round(rpm, 4),
                        "estimatedRevenueDaily": round(estimated_daily, 2),
                        "settledRevenueDaily": round(settled_daily, 2),
                        "settlementWindow": settlement_window,
                    }
                    last_error = None
                    last_failure_code = None
                    break
                except HTTPError as exc:
                    retryable = 500 <= getattr(exc, "code", 500) < 600
                    last_error = f"Ad network API error {getattr(exc, 'code', 'unknown')}"
                    last_failure_code = _http_failure_code(exc, "AD_NETWORK")
                    details = {
                        **details,
                        "endpoint": endpoint,
                        "error": str(exc),
                        "endpointAttempts": [
                            *list(details.get("endpointAttempts") or []),
                            {"endpoint": endpoint, "status": "error", "failureCode": last_failure_code, "retryable": retryable},
                        ],
                    }
                except Exception as exc:
                    retryable = True
                    last_error = str(exc)
                    last_failure_code = _exception_failure_code(exc, "AD_NETWORK")
                    details = {
                        **details,
                        "endpoint": endpoint,
                        "error": str(exc),
                        "endpointAttempts": [
                            *list(details.get("endpointAttempts") or []),
                            {"endpoint": endpoint, "status": "error", "failureCode": last_failure_code, "retryable": retryable},
                        ],
                    }
            else:
                status = ConnectorStatus.error
                summary = "Ad network API request failed across all configured endpoints."
            if status != ConnectorStatus.connected and last_error:
                fallback_reason = last_error
                failure_code = last_failure_code
                if not strict_mode:
                    details = {
                        **details,
                        "estimatedRevenueDaily": 24.0,
                        "settledRevenueDaily": 20.9,
                        "settlementWindow": "T+7 fallback",
                        "rpm": 3.6,
                        "fillRate": 0.47,
                        "impressions": 6800,
                        "clicks": 61,
                        "ctr": 0.009,
                        "mode": "synthetic-fallback",
                    }
        latency_ms = int((time.perf_counter() - started) * 1000)
        connection = self._build_connection(
            ctx,
            status=status,
            provenance=[f"account={account_id or 'unset'}", f"host={_site_host(ctx.intake)}"],
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
        )
        evidence = SourceEvidence(
            provider=self.kind,
            status=status,
            summary=summary,
            provenance=connection.provenance,
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
            auth_source=auth_source,
        )
        return connection, evidence


class ScriptApiAdapter(BaseConnectorAdapter):
    kind = ConnectorKind.script_api
    label = "Script API"

    def probe(self, ctx: ConnectorContext) -> tuple[ProjectConnection, SourceEvidence]:
        started = time.perf_counter()
        default_endpoint = str(ctx.connection.config.get("scriptEndpoint") or ctx.connection.config.get("endpoint") or "")
        endpoints = _candidate_endpoints(ctx.connection.config, ["scriptEndpoints", "scriptEndpoint", "endpoints", "endpoint"], default_endpoint)
        access_token, auth_source, auth_header = _resolve_credential_with_header(
            ctx.connection.config,
            ["authToken", "accessToken", "credentialsJson", "serviceAccountJson"],
            [
                "SEO_AD_BOT_SCRIPT_ACCESS_TOKEN",
                "SEO_AD_BOT_SCRIPT_CREDENTIALS_JSON",
                "SEO_AD_BOT_SCRIPT_SERVICE_ACCOUNT_JSON",
            ],
        )
        fallback_reason = None
        failure_code = None
        retryable = False
        details = {
            "endpoint": default_endpoint,
            "authSource": auth_source,
            "authHeader": auth_header,
            "endpointsConfigured": endpoints,
            "endpointsTried": [],
        }
        if not ctx.connection.enabled:
            fallback_reason = "connector disabled"
            status = ConnectorStatus.unavailable
            summary = "Script API connector disabled; script writeback checks skipped."
        elif not endpoints or not access_token:
            fallback_reason = "missing endpoint/accessToken"
            failure_code = "CONFIG_MISSING_SCRIPT"
            status = ConnectorStatus.missing_credentials
            summary = "Script API connector is configured but credentials are incomplete."
            retryable = True
        else:
            payload = {"siteUrl": ctx.intake.url, "mode": "health_probe"}
            last_error: Optional[str] = None
            last_failure_code: Optional[str] = None
            for endpoint in endpoints:
                details["endpointsTried"].append(endpoint)
                try:
                    response = _http_json(
                        endpoint,
                        method="POST",
                        headers={str(auth_header or "Authorization"): f"Bearer {access_token}"},
                        payload=payload,
                    )
                    if "raw" in response:
                        raise ValueError("SCRIPT_INVALID_PAYLOAD: non-json response")
                    provider_ref = str(
                        response.get("providerRef")
                        or response.get("id")
                        or response.get("artifactId")
                        or ""
                    ).strip()
                    strict = bool(get_settings().strict_providers)
                    if provider_ref:
                        status = ConnectorStatus.connected
                        summary = "Script API connector is connected."
                        details = {
                            **details,
                            "endpoint": endpoint,
                            "providerRef": provider_ref,
                            "health": str(response.get("health") or "ok"),
                        }
                        last_error = None
                        last_failure_code = None
                        break
                    status = ConnectorStatus.error if strict else ConnectorStatus.synthetic
                    summary = (
                        "Script API response is missing provider identifier in strict mode."
                        if strict
                        else "Script API response is missing provider identifier; fallback mode enabled."
                    )
                    last_error = "Script API returned no providerRef/id."
                    last_failure_code = "SCRIPT_INVALID_RESPONSE"
                    retryable = True
                    details = {
                        **details,
                        "endpoint": endpoint,
                        "health": str(response.get("health") or "unknown"),
                    }
                except HTTPError as exc:
                    retryable = 500 <= getattr(exc, "code", 500) < 600
                    last_error = f"Script API error {getattr(exc, 'code', 'unknown')}"
                    last_failure_code = _http_failure_code(exc, "SCRIPT")
                    details = {**details, "endpoint": endpoint, "error": str(exc)}
                except Exception as exc:
                    message = str(exc)
                    if "SCRIPT_INVALID_PAYLOAD" in message:
                        retryable = False
                        last_failure_code = "SCRIPT_INVALID_PAYLOAD"
                    else:
                        retryable = True
                        last_failure_code = _exception_failure_code(exc, "SCRIPT")
                    last_error = message
                    details = {**details, "endpoint": endpoint, "error": str(exc)}
            else:
                status = ConnectorStatus.error
                summary = "Script API request failed across all configured endpoints."
            if status != ConnectorStatus.connected and last_error:
                fallback_reason = last_error
                failure_code = last_failure_code
        latency_ms = int((time.perf_counter() - started) * 1000)
        connection = self._build_connection(
            ctx,
            status=status,
            provenance=[f"endpoint={default_endpoint or 'unset'}", f"host={_site_host(ctx.intake)}"],
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
        )
        evidence = SourceEvidence(
            provider=self.kind,
            status=status,
            summary=summary,
            provenance=connection.provenance,
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
            auth_source=auth_source,
        )
        return connection, evidence


class SitemapAdapter(BaseConnectorAdapter):
    kind = ConnectorKind.sitemap
    label = "Sitemap"

    def probe(self, ctx: ConnectorContext) -> tuple[ProjectConnection, SourceEvidence]:
        started = time.perf_counter()
        settings = get_settings()
        strict_mode = bool(settings.strict_providers)
        if not ctx.connection.enabled:
            latency_ms = int((time.perf_counter() - started) * 1000)
            details = {
                "enabled": False,
                "authSource": "missing",
                "sources": [],
                "discoveredUrls": [],
                "sourceCount": 0,
                "providerAttempts": [],
                "providerEndpoint": None,
                "providerEndpointConfigured": False,
            }
            connection = self._build_connection(
                ctx,
                status=ConnectorStatus.unavailable,
                provenance=["connector-disabled"],
                details=details,
                fallback_reason="connector disabled",
                retryable=False,
                latency_ms=latency_ms,
            )
            evidence = SourceEvidence(
                provider=self.kind,
                status=ConnectorStatus.unavailable,
                summary="Sitemap connector disabled by project policy.",
                provenance=connection.provenance,
                details=details,
                fallback_reason="connector disabled",
                retryable=False,
                auth_source="missing",
                latency_ms=latency_ms,
            )
            return connection, evidence

        explicit_config = bool(ctx.connection.config.get("explicitConfig"))
        sitemap_urls = _coerce_list(ctx.connection.config.get("urls")) or [ctx.intake.url.rstrip("/") + "/sitemap.xml"]
        provider_endpoint = str(ctx.connection.config.get("providerUrl") or settings.sitemap_provider_url or "").strip()
        provider_endpoints = _coerce_list(ctx.connection.config.get("providerUrls"))
        provider_timeout_ms = int(ctx.connection.config.get("providerTimeoutMs") or settings.sitemap_provider_timeout_ms)
        timeout_seconds = max(1, int(round(provider_timeout_ms / 1000)))
        provider_access_token, provider_auth_source, resolved_auth_header = _resolve_credential_with_header(
            ctx.connection.config,
            ["accessToken", "authToken", "credentialsJson", "serviceAccountJson"],
            [
                "SEO_AD_BOT_SITEMAP_ACCESS_TOKEN",
                "SEO_AD_BOT_SITEMAP_CREDENTIALS_JSON",
                "SEO_AD_BOT_SITEMAP_SERVICE_ACCOUNT_JSON",
            ],
        )
        configured_auth_header = str(ctx.connection.config.get("authHeader") or "").strip()
        provider_auth_header = configured_auth_header if configured_auth_header and configured_auth_header.lower() != "authorization" else str(
            resolved_auth_header or settings.sitemap_provider_auth_header or "Authorization"
        ).strip() or "Authorization"

        discovered: list[str] = []
        provider_attempts: list[dict[str, Any]] = []
        direct_attempts: list[dict[str, Any]] = []
        attempted_sources: list[str] = []
        provider_response_ref: Optional[str] = None
        provider_failure_code: Optional[str] = None
        provider_fallback_reason: Optional[str] = None
        provider_connected = False
        direct_connected = False
        provider_source_count = 0
        direct_source_count = 0

        provider_candidates = [endpoint for endpoint in [provider_endpoint, *provider_endpoints] if endpoint]
        for endpoint in provider_candidates[:3]:
            if endpoint in attempted_sources:
                continue
            attempted_sources.append(endpoint)
            provider_source_count += 1
            headers = {"Accept": "application/json, application/xml, text/xml;q=0.9,*/*;q=0.8"}
            if provider_access_token:
                headers[provider_auth_header] = provider_access_token
            payload = {
                "siteUrl": ctx.intake.url,
                "siteHost": _site_host(ctx.intake),
                "sitemapUrls": sitemap_urls,
                "requestedUrls": sitemap_urls,
            }
            try:
                response = _http_json(endpoint, method="POST", headers=headers, payload=payload, timeout=timeout_seconds)
                candidate_locations = _extract_sitemap_locations(response)
                provider_attempts.append(
                    {
                        "endpoint": endpoint,
                        "status": "connected" if candidate_locations else "failed",
                        "locationCount": len(candidate_locations),
                        "providerRef": str(response.get("providerRef") or response.get("artifactId") or response.get("id") or ""),
                        "authSource": provider_auth_source,
                        "authHeader": provider_auth_header if provider_access_token else None,
                        "latencyMs": int((time.perf_counter() - started) * 1000),
                    }
                )
                if candidate_locations:
                    discovered.extend(candidate_locations)
                    provider_connected = True
                    provider_response_ref = str(response.get("providerRef") or response.get("artifactId") or response.get("id") or endpoint)
                    break
                provider_failure_code = "SITEMAP_INVALID_PAYLOAD"
                provider_fallback_reason = "sitemap provider returned no locations"
            except HTTPError as exc:
                failure_code = _http_failure_code(exc, "SITEMAP")
                provider_attempts.append(
                    {
                        "endpoint": endpoint,
                        "status": "failed",
                        "failureCode": failure_code,
                        "authSource": provider_auth_source,
                        "authHeader": provider_auth_header if provider_access_token else None,
                        "latencyMs": int((time.perf_counter() - started) * 1000),
                    }
                )
                provider_failure_code = failure_code
                provider_fallback_reason = f"provider endpoint failed with {failure_code}"
            except Exception as exc:
                failure_code = _exception_failure_code(exc, "SITEMAP")
                provider_attempts.append(
                    {
                        "endpoint": endpoint,
                        "status": "failed",
                        "failureCode": failure_code,
                        "authSource": provider_auth_source,
                        "authHeader": provider_auth_header if provider_access_token else None,
                        "latencyMs": int((time.perf_counter() - started) * 1000),
                    }
                )
                provider_failure_code = failure_code
                provider_fallback_reason = f"provider endpoint failed with {failure_code}"

        if not discovered:
            for sitemap_url in sitemap_urls[:3]:
                absolute_url = sitemap_url if sitemap_url.startswith("http") else urljoin(ctx.intake.url.rstrip("/") + "/", sitemap_url.lstrip("/"))
                attempted_sources.append(absolute_url)
                direct_source_count += 1
                try:
                    text = _fetch_text(absolute_url)
                    parsed_locations = re.findall(r"<loc>([^<]+)</loc>", text, flags=re.IGNORECASE)
                    direct_attempts.append(
                        {
                            "endpoint": absolute_url,
                            "status": "connected" if parsed_locations else "failed",
                            "locationCount": len(parsed_locations),
                        }
                    )
                    if parsed_locations:
                        discovered.extend(parsed_locations)
                        direct_connected = True
                        break
                except Exception as exc:
                    direct_attempts.append(
                        {
                            "endpoint": absolute_url,
                            "status": "failed",
                            "failureCode": _exception_failure_code(exc, "SITEMAP"),
                        }
                    )

        if discovered:
            status = ConnectorStatus.connected
            if provider_connected:
                summary = f"Sitemap provider returned {len(discovered)} candidate URLs."
                auth_source = provider_auth_source
                fallback_reason = None
            else:
                summary = f"Sitemap discovery found {len(discovered)} candidate URLs."
                auth_source = "fallback"
                fallback_reason = provider_fallback_reason if provider_fallback_reason and attempted_sources else None
        else:
            status = ConnectorStatus.error if strict_mode else ConnectorStatus.synthetic
            if provider_endpoint or provider_endpoints:
                summary = (
                    "Sitemap provider and sitemap fetch both failed in strict mode; fallback is blocked."
                    if strict_mode
                    else "Sitemap provider and sitemap fetch fell back to deterministic sample URLs."
                )
            else:
                summary = (
                    "Sitemap fetch failed in strict mode; synthetic fallback is disabled."
                    if strict_mode
                    else "Sitemap fetch fell back to deterministic sample URLs."
                )
            fallback_reason = provider_fallback_reason or "sitemap fetch failed or returned no locations"
            auth_source = provider_auth_source if provider_connected else ("config" if explicit_config else "fallback")
            if not direct_connected and strict_mode:
                provider_failure_code = provider_failure_code or "SITEMAP_NO_LOCATIONS"
        if not discovered and not provider_connected and not direct_connected:
            discovered = [f"{ctx.intake.url.rstrip('/')}/page-{index}" for index in range(1, 4)] if not strict_mode else []

        details = {
            "sources": attempted_sources,
            "providerAttempts": provider_attempts,
            "directAttempts": direct_attempts,
            "providerEndpoint": provider_endpoint or None,
            "providerEndpoints": provider_endpoints,
            "providerEndpointConfigured": bool(provider_candidates),
            "providerResponseRef": provider_response_ref,
            "providerAuthSource": provider_auth_source,
            "providerAuthHeader": provider_auth_header,
            "providerConnected": provider_connected,
            "directConnected": direct_connected,
            "discoveredUrls": discovered[:25],
            "sourceCount": len(attempted_sources),
            "providerSourceCount": provider_source_count,
            "directSourceCount": direct_source_count,
            "authSource": auth_source,
            "explicitConfig": explicit_config,
            "strictMode": strict_mode,
        }
        latency_ms = int((time.perf_counter() - started) * 1000)
        failure_code = None if status == ConnectorStatus.connected else (provider_failure_code or "SITEMAP_NO_LOCATIONS")
        retryable = status != ConnectorStatus.connected and not strict_mode
        connection = self._build_connection(
            ctx,
            status=status,
            provenance=attempted_sources,
            details=details,
            fallback_reason=None if status == ConnectorStatus.connected else fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
        )
        evidence = SourceEvidence(
            provider=self.kind,
            status=status,
            summary=summary,
            provenance=connection.provenance,
            details=details,
            fallback_reason=None if status == ConnectorStatus.connected else fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            auth_source=auth_source,
            latency_ms=latency_ms,
        )
        return connection, evidence


class PlaywrightAdapter(BaseConnectorAdapter):
    kind = ConnectorKind.playwright
    label = "Playwright"

    def probe(self, ctx: ConnectorContext) -> tuple[ProjectConnection, SourceEvidence]:
        started = time.perf_counter()
        settings = get_settings()
        strict_mode = bool(settings.strict_providers)
        anti_bot_cooldown_base_minutes = max(0, int(settings.browser_crawl_antibot_cooldown_minutes))
        anti_bot_cooldown_max_minutes = max(
            anti_bot_cooldown_base_minutes,
            int(settings.browser_crawl_antibot_cooldown_max_minutes),
        )
        provider_endpoint = str(ctx.connection.config.get("providerUrl") or settings.playwright_provider_url or "").strip()
        provider_endpoints = _coerce_list(ctx.connection.config.get("providerUrls"))
        provider_timeout_ms = int(ctx.connection.config.get("providerTimeoutMs") or settings.playwright_provider_timeout_ms)
        provider_timeout_seconds = max(1, int(round(provider_timeout_ms / 1000)))
        provider_access_token, provider_auth_source, resolved_auth_header = _resolve_credential_with_header(
            ctx.connection.config,
            ["accessToken", "authToken", "credentialsJson", "serviceAccountJson"],
            [
                "SEO_AD_BOT_PLAYWRIGHT_ACCESS_TOKEN",
                "SEO_AD_BOT_PLAYWRIGHT_CREDENTIALS_JSON",
                "SEO_AD_BOT_PLAYWRIGHT_SERVICE_ACCOUNT_JSON",
            ],
        )
        configured_auth_header = str(ctx.connection.config.get("authHeader") or "").strip()
        provider_auth_header = configured_auth_header if configured_auth_header and configured_auth_header.lower() != "authorization" else str(
            resolved_auth_header or settings.playwright_auth_header or "Authorization"
        ).strip() or "Authorization"
        enabled = bool(ctx.connection.config.get("enabled"))
        live_crawl_enabled = bool(settings.enable_browser_crawl)
        auth_source = "config" if enabled else "missing"
        if enabled and not live_crawl_enabled and not provider_endpoint:
            status = ConnectorStatus.error if strict_mode else ConnectorStatus.synthetic
            summary = (
                "Playwright live crawl disabled by environment in strict mode; fallback is blocked."
                if strict_mode
                else "Playwright live crawl disabled by environment; synthetic fallback used."
            )
            failure_code = "PLAYWRIGHT_ENV_DISABLED"
            fallback_reason = "live browser crawl disabled by SEO_AD_BOT_ENABLE_BROWSER_CRAWL"
            details = {
                "enabled": True,
                "strictMode": strict_mode,
                "authSource": auth_source,
                "liveCrawlEnabled": live_crawl_enabled,
                "mode": "strict-error" if strict_mode else "synthetic",
                "failureCode": failure_code,
            }
            latency_ms = int((time.perf_counter() - started) * 1000)
            connection = self._build_connection(
                ctx,
                status=status,
                provenance=["browser-crawl-env-disabled"],
                details=details,
                fallback_reason=fallback_reason,
                failure_code=failure_code,
                retryable=False,
                latency_ms=latency_ms,
            )
            evidence = SourceEvidence(
                provider=self.kind,
                status=status,
                summary=summary,
                provenance=connection.provenance,
                details=details,
                fallback_reason=fallback_reason,
                failure_code=failure_code,
                retryable=False,
                auth_source=auth_source,
                latency_ms=latency_ms,
            )
            return connection, evidence
        if not enabled:
            status = ConnectorStatus.unavailable
            summary = "Browser crawl is disabled by configuration."
            details = {"enabled": False, "authSource": auth_source, "liveCrawlEnabled": live_crawl_enabled}
            latency_ms = int((time.perf_counter() - started) * 1000)
            connection = self._build_connection(
                ctx,
                status=status,
                provenance=["browser-crawl-disabled"],
                details=details,
                fallback_reason="browser crawl disabled",
                retryable=False,
                latency_ms=latency_ms,
            )
            evidence = SourceEvidence(
                provider=self.kind,
                status=status,
                summary=summary,
                provenance=connection.provenance,
                details=details,
                fallback_reason="browser crawl disabled",
                retryable=False,
                auth_source=auth_source,
                latency_ms=latency_ms,
            )
            return connection, evidence
        provider_attempts: list[dict[str, Any]] = []
        provider_response_ref: Optional[str] = None
        provider_failure_code: Optional[str] = None
        provider_fallback_reason: Optional[str] = None
        provider_connected = False
        provider_artifact_ref: Optional[str] = None
        provider_html_artifact_ref: Optional[str] = None
        provider_screenshot_artifact_ref: Optional[str] = None
        provider_candidates = [endpoint for endpoint in [provider_endpoint, *provider_endpoints] if endpoint]
        if provider_candidates:
            runtime_options: dict[str, Any] = {}
            for source_key, target_key in (
                ("timeoutMs", "timeoutMs"),
                ("retryCount", "retryCount"),
                ("userAgent", "userAgent"),
                ("userAgents", "userAgents"),
                ("jsEnabled", "jsEnabled"),
                ("backoffMs", "backoffMs"),
                ("jitterMs", "jitterMs"),
                ("antiBotEscalationThreshold", "antiBotEscalationThreshold"),
                ("proxyRotation", "proxyRotation"),
                ("proxy", "proxy"),
                ("proxies", "proxies"),
                ("extraHeaders", "extraHeaders"),
            ):
                if source_key in ctx.connection.config:
                    runtime_options[target_key] = ctx.connection.config.get(source_key)
            for endpoint in provider_candidates[:3]:
                headers = {"Accept": "application/json"}
                if provider_access_token:
                    headers[provider_auth_header] = provider_access_token
                payload = {
                    "pageUrl": ctx.intake.url,
                    "siteUrl": ctx.intake.url,
                    "siteHost": _site_host(ctx.intake),
                    "runtimeOptions": runtime_options,
                }
                try:
                    response = _http_json(endpoint, method="POST", headers=headers, payload=payload, timeout=provider_timeout_seconds)
                    provider_attempts.append(
                        {
                            "endpoint": endpoint,
                            "status": "connected",
                            "providerRef": str(response.get("providerRef") or response.get("artifactId") or response.get("id") or ""),
                            "authSource": provider_auth_source,
                            "authHeader": provider_auth_header if provider_access_token else None,
                            "latencyMs": int((time.perf_counter() - started) * 1000),
                        }
                    )
                    snapshot = _page_snapshot_from_payload(response, ctx.intake.url)
                    if snapshot is None:
                        provider_failure_code = "PLAYWRIGHT_PROVIDER_INVALID_PAYLOAD"
                        provider_fallback_reason = "browser farm provider returned no snapshot payload"
                        provider_attempts[-1]["status"] = "failed"
                        provider_attempts[-1]["failureCode"] = provider_failure_code
                        if strict_mode:
                            break
                        continue
                    provider_connected = True
                    provider_response_ref = str(response.get("providerRef") or response.get("artifactId") or response.get("id") or endpoint)
                    provider_artifact_ref = str(response.get("artifactRef") or response.get("artifactId") or response.get("providerRef") or provider_response_ref)
                    provider_html_artifact_ref = str(
                        response.get("htmlArtifactRef")
                        or response.get("_htmlArtifactRef")
                        or response.get("htmlRef")
                        or response.get("htmlArtifactId")
                        or ""
                    ) or None
                    provider_screenshot_artifact_ref = str(
                        response.get("screenshotArtifactRef")
                        or response.get("_screenshotArtifactRef")
                        or response.get("screenshotRef")
                        or response.get("screenshotArtifactId")
                        or ""
                    ) or None
                    if not provider_html_artifact_ref:
                        raw_html = str(response.get("htmlContent") or response.get("_htmlContent") or response.get("html") or "")
                        if raw_html:
                            try:
                                artifact_store = get_artifact_store()
                                html_artifact = artifact_store.write_text(
                                    f"crawler/{ctx.project_id}/{ctx.task_id or 'task_na'}/{new_id('crawl')}.html",
                                    raw_html,
                                )
                                provider_html_artifact_ref = html_artifact.artifact_ref
                            except Exception:
                                provider_html_artifact_ref = None
                    if not provider_screenshot_artifact_ref:
                        raw_screenshot_b64 = str(response.get("screenshotB64") or response.get("_screenshotB64") or response.get("screenshot") or "")
                        if raw_screenshot_b64:
                            try:
                                artifact_store = get_artifact_store()
                                screenshot_artifact = artifact_store.write_bytes(
                                    f"crawler/{ctx.project_id}/{ctx.task_id or 'task_na'}/{new_id('crawl')}.png",
                                    base64.b64decode(raw_screenshot_b64.encode("ascii")),
                                )
                                provider_screenshot_artifact_ref = screenshot_artifact.artifact_ref
                            except Exception:
                                provider_screenshot_artifact_ref = None
                    details = {
                        "pageUrl": snapshot.url,
                        "mode": "connected",
                        "strictMode": strict_mode,
                        "authSource": provider_auth_source,
                        "liveCrawlEnabled": live_crawl_enabled,
                        "providerEndpoint": endpoint,
                        "providerEndpointConfigured": True,
                        "providerAttempts": provider_attempts,
                        "providerResponseRef": provider_response_ref,
                        "providerArtifactRef": provider_artifact_ref,
                        "providerAuthSource": provider_auth_source,
                        "providerAuthHeader": provider_auth_header,
                        "providerConnected": True,
                        "title": snapshot.title,
                        "wordCount": snapshot.word_count,
                        "missingAltCount": snapshot.missing_alt_count,
                        "responseStatus": response.get("status"),
                        "runtimeOverrides": runtime_options,
                        "screenshotArtifactRef": provider_screenshot_artifact_ref,
                        "htmlArtifactRef": provider_html_artifact_ref,
                    }
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    connection = self._build_connection(
                        ctx,
                        status=ConnectorStatus.connected,
                        provenance=[endpoint],
                        details=details,
                        fallback_reason=None,
                        failure_code=None,
                        retryable=False,
                        latency_ms=latency_ms,
                    )
                    evidence = SourceEvidence(
                        provider=self.kind,
                        status=ConnectorStatus.connected,
                        summary=f"Playwright provider captured {snapshot.title!r} with {snapshot.word_count} words.",
                        provenance=connection.provenance,
                        details=details,
                        fallback_reason=None,
                        failure_code=None,
                        retryable=False,
                        auth_source=provider_auth_source,
                        latency_ms=latency_ms,
                    )
                    return connection, evidence
                except HTTPError as exc:
                    provider_failure_code = _http_failure_code(exc, "PLAYWRIGHT")
                    provider_attempts.append(
                        {
                            "endpoint": endpoint,
                            "status": "failed",
                            "failureCode": provider_failure_code,
                            "authSource": provider_auth_source,
                            "authHeader": provider_auth_header if provider_access_token else None,
                            "latencyMs": int((time.perf_counter() - started) * 1000),
                        }
                    )
                    provider_fallback_reason = f"browser farm provider failed with {provider_failure_code}"
                except Exception as exc:
                    provider_failure_code = _exception_failure_code(exc, "PLAYWRIGHT")
                    provider_attempts.append(
                        {
                            "endpoint": endpoint,
                            "status": "failed",
                            "failureCode": provider_failure_code,
                            "authSource": provider_auth_source,
                            "authHeader": provider_auth_header if provider_access_token else None,
                            "latencyMs": int((time.perf_counter() - started) * 1000),
                        }
                    )
                    provider_fallback_reason = f"browser farm provider failed with {provider_failure_code}"
            if strict_mode and provider_connected is False and provider_endpoint:
                latency_ms = int((time.perf_counter() - started) * 1000)
                details = {
                    "pageUrl": ctx.intake.url,
                    "mode": "strict-error",
                    "strictMode": strict_mode,
                    "authSource": provider_auth_source,
                    "liveCrawlEnabled": live_crawl_enabled,
                    "providerEndpoint": provider_endpoint,
                    "providerEndpoints": provider_endpoints,
                    "providerEndpointConfigured": True,
                    "providerAttempts": provider_attempts,
                    "providerResponseRef": provider_response_ref,
                    "providerArtifactRef": provider_artifact_ref,
                    "providerAuthSource": provider_auth_source,
                    "providerAuthHeader": provider_auth_header,
                    "providerConnected": False,
                    "failureCode": provider_failure_code or "PLAYWRIGHT_PROVIDER_UNAVAILABLE",
                }
                connection = self._build_connection(
                    ctx,
                    status=ConnectorStatus.error,
                    provenance=[provider_endpoint],
                    details=details,
                    fallback_reason=provider_fallback_reason or "browser farm provider unavailable",
                    failure_code=provider_failure_code or "PLAYWRIGHT_PROVIDER_UNAVAILABLE",
                    retryable=False,
                    latency_ms=latency_ms,
                )
                evidence = SourceEvidence(
                    provider=self.kind,
                    status=ConnectorStatus.error,
                    summary="Playwright browser farm provider failed in strict mode; fallback is blocked.",
                    provenance=connection.provenance,
                    details=details,
                    fallback_reason=provider_fallback_reason or "browser farm provider unavailable",
                    failure_code=provider_failure_code or "PLAYWRIGHT_PROVIDER_UNAVAILABLE",
                    retryable=False,
                    auth_source=provider_auth_source,
                    latency_ms=latency_ms,
                )
                return connection, evidence
        previous_details = ctx.connection.details if isinstance(ctx.connection.details, dict) else {}
        previous_manual_intervention = bool(previous_details.get("manualInterventionRequired")) or bool(
            previous_details.get("antiBotEscalated")
        )
        cooldown_until = _parse_iso_datetime(previous_details.get("antiBotCooldownUntil"))
        previous_cooldown_minutes = int(previous_details.get("antiBotCooldownMinutes") or anti_bot_cooldown_base_minutes)
        previous_cooldown_minutes = max(0, min(previous_cooldown_minutes, anti_bot_cooldown_max_minutes))
        if cooldown_until is None and ctx.connection.last_checked_at is not None and previous_cooldown_minutes > 0:
            checked_at = ctx.connection.last_checked_at
            if checked_at.tzinfo is None:
                checked_at = checked_at.replace(tzinfo=timezone.utc)
            cooldown_until = checked_at + timedelta(minutes=previous_cooldown_minutes)
        now = utcnow()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        if previous_manual_intervention and previous_cooldown_minutes > 0 and cooldown_until and cooldown_until > now:
            status = ConnectorStatus.error if strict_mode else ConnectorStatus.synthetic
            summary = (
                "Playwright anti-bot cooldown is active in strict mode; manual intervention still required."
                if strict_mode
                else "Playwright anti-bot cooldown active; synthetic fallback retained until manual intervention clears."
            )
            failure_code = "PLAYWRIGHT_ANTI_BOT_COOLDOWN"
            fallback_reason = f"anti-bot cooldown active until {cooldown_until.isoformat()}"
            details = {
                "pageUrl": ctx.intake.url,
                "mode": "strict-error" if strict_mode else "synthetic",
                "strictMode": strict_mode,
                "authSource": auth_source,
                "liveCrawlEnabled": live_crawl_enabled,
                "cooldownActive": True,
                "antiBotCooldownMinutes": previous_cooldown_minutes,
                "antiBotCooldownUntil": cooldown_until.isoformat(),
                "antiBotBlocked": bool(previous_details.get("antiBotBlocked")),
                "antiBotBlockCount": int(previous_details.get("antiBotBlockCount") or 0),
                "antiBotConsecutiveCount": int(previous_details.get("antiBotConsecutiveCount") or 0),
                "antiBotEscalated": bool(previous_details.get("antiBotEscalated") or previous_manual_intervention),
                "manualInterventionRequired": True,
                "remediationHint": "manual intervention required before next crawl attempt",
                "blockSignals": list(previous_details.get("blockSignals") or []),
                "configuredProxyCount": int(previous_details.get("configuredProxyCount") or 0),
                "configuredProxies": list(previous_details.get("configuredProxies") or []),
                "proxyRotationStrategy": previous_details.get("proxyRotationStrategy"),
                "selectedProxy": previous_details.get("selectedProxy"),
                "runtimeOverrides": previous_details.get("runtimeOverrides", {}),
                "screenshotArtifactRef": previous_details.get("screenshotArtifactRef"),
                "htmlArtifactRef": previous_details.get("htmlArtifactRef"),
            }
            latency_ms = int((time.perf_counter() - started) * 1000)
            connection = self._build_connection(
                ctx,
                status=status,
                provenance=["browser-crawl-antibot-cooldown", ctx.intake.url],
                details=details,
                fallback_reason=fallback_reason,
                failure_code=failure_code,
                retryable=False,
                latency_ms=latency_ms,
            )
            evidence = SourceEvidence(
                provider=self.kind,
                status=status,
                summary=summary,
                provenance=connection.provenance,
                details=details,
                fallback_reason=fallback_reason,
                failure_code=failure_code,
                retryable=False,
                auth_source=auth_source,
                latency_ms=latency_ms,
            )
            return connection, evidence

        runtime_options: dict[str, Any] = {}
        for source_key, target_key in (
            ("timeoutMs", "timeoutMs"),
            ("retryCount", "retryCount"),
            ("userAgent", "userAgent"),
            ("userAgents", "userAgents"),
            ("jsEnabled", "jsEnabled"),
            ("backoffMs", "backoffMs"),
            ("jitterMs", "jitterMs"),
            ("antiBotEscalationThreshold", "antiBotEscalationThreshold"),
            ("proxyRotation", "proxyRotation"),
            ("proxy", "proxy"),
            ("proxies", "proxies"),
            ("extraHeaders", "extraHeaders"),
        ):
            if source_key in ctx.connection.config:
                runtime_options[target_key] = ctx.connection.config.get(source_key)
        snapshot: Optional[PageSnapshot]
        diagnostics: dict[str, Any]
        snapshot, diagnostics = crawl_page_with_diagnostics(
            ctx.intake.url,
            fallback_title=ctx.intake.site_name or _site_host(ctx.intake).title(),
            fallback_description="Synthetic crawl fallback used for offline processing.",
            runtime_options=runtime_options if runtime_options else None,
        )
        raw_html = str(diagnostics.pop("_htmlContent", "") or "")
        raw_screenshot_b64 = str(diagnostics.pop("_screenshotB64", "") or "")
        screenshot_artifact_ref: Optional[str] = None
        html_artifact_ref: Optional[str] = None
        if raw_html or raw_screenshot_b64:
            try:
                artifact_store = get_artifact_store()
                artifact_prefix = f"crawler/{ctx.project_id}/{ctx.task_id or 'task_na'}/{new_id('crawl')}"
                if raw_html:
                    html_artifact = artifact_store.write_text(f"{artifact_prefix}.html", raw_html)
                    html_artifact_ref = html_artifact.artifact_ref
                if raw_screenshot_b64:
                    screenshot_artifact = artifact_store.write_bytes(
                        f"{artifact_prefix}.png",
                        base64.b64decode(raw_screenshot_b64.encode("ascii")),
                    )
                    screenshot_artifact_ref = screenshot_artifact.artifact_ref
            except Exception:
                screenshot_artifact_ref = None
                html_artifact_ref = None
        if snapshot is None:
            status = ConnectorStatus.error if strict_mode else ConnectorStatus.synthetic
            summary = (
                "Playwright crawl failed in strict mode; synthetic fallback is disabled."
                if strict_mode
                else "Playwright crawl fell back to a synthetic homepage snapshot."
            )
            failure_code = str(diagnostics.get("failureCode") or "PLAYWRIGHT_REQUEST_FAILED")
            anti_bot_blocked = failure_code == "PLAYWRIGHT_ANTI_BOT_BLOCKED" or bool(diagnostics.get("antiBotBlocked"))
            anti_bot_block_count = int(diagnostics.get("antiBotBlockCount") or (1 if anti_bot_blocked else 0))
            anti_bot_consecutive_count = int(diagnostics.get("antiBotConsecutiveCount") or anti_bot_block_count)
            anti_bot_escalated = bool(diagnostics.get("antiBotEscalated")) or (anti_bot_consecutive_count >= 2)
            manual_intervention_required = bool(diagnostics.get("manualInterventionRequired")) or anti_bot_escalated
            anti_bot_cooldown_minutes = min(
                anti_bot_cooldown_max_minutes,
                anti_bot_cooldown_base_minutes * max(1, anti_bot_consecutive_count),
            )
            anti_bot_cooldown_until: Optional[str] = None
            if manual_intervention_required and anti_bot_cooldown_minutes > 0:
                anti_bot_cooldown_until = (now + timedelta(minutes=anti_bot_cooldown_minutes)).isoformat()
            details = {
                "pageUrl": ctx.intake.url,
                "mode": "strict-error" if strict_mode else "synthetic",
                "strictMode": strict_mode,
                "authSource": auth_source,
                "liveCrawlEnabled": live_crawl_enabled,
                "crawlAttempts": diagnostics.get("attempts", []),
                "attemptCount": diagnostics.get("attemptCount", 0),
                "configuredRetryCount": diagnostics.get("configuredRetryCount", 0),
                "timeoutMs": diagnostics.get("timeoutMs"),
                "userAgent": diagnostics.get("userAgent"),
                "configuredUserAgents": diagnostics.get("configuredUserAgents", []),
                "configuredProxyCount": diagnostics.get("configuredProxyCount", 0),
                "configuredProxies": diagnostics.get("configuredProxies", []),
                "proxyRotationStrategy": diagnostics.get("proxyRotationStrategy"),
                "selectedProxy": diagnostics.get("selectedProxy"),
                "runtimeOverrides": diagnostics.get("runtimeOverrides", {}),
                "extraHeaders": diagnostics.get("extraHeaders", {}),
                "jitterMs": diagnostics.get("jitterMs"),
                "jsEnabled": diagnostics.get("jsEnabled"),
                "responseStatus": diagnostics.get("responseStatus"),
                "antiBotBlocked": anti_bot_blocked,
                "antiBotBlockCount": anti_bot_block_count,
                "antiBotConsecutiveCount": anti_bot_consecutive_count,
                "antiBotEscalated": anti_bot_escalated,
                "manualInterventionRequired": manual_intervention_required,
                "cooldownActive": bool(anti_bot_cooldown_until),
                "antiBotCooldownMinutes": anti_bot_cooldown_minutes,
                "antiBotCooldownUntil": anti_bot_cooldown_until,
                "remediationHint": str(diagnostics.get("remediationHint") or ("manual intervention required" if manual_intervention_required else "retry recommended")),
                "blockSignals": diagnostics.get("blockSignals", []),
                "screenshotArtifactRef": screenshot_artifact_ref,
                "htmlArtifactRef": html_artifact_ref,
            }
            fallback_reason = str(diagnostics.get("fallbackReason") or "crawl returned synthetic snapshot")
            retryable = (not anti_bot_blocked) and (not manual_intervention_required)
        else:
            status = ConnectorStatus.connected
            summary = f"Playwright captured {snapshot.title!r} with {snapshot.word_count} words."
            details = {
                "pageUrl": snapshot.url,
                "mode": "connected",
                "strictMode": strict_mode,
                "authSource": auth_source,
                "liveCrawlEnabled": live_crawl_enabled,
                "title": snapshot.title,
                "wordCount": snapshot.word_count,
                "missingAltCount": snapshot.missing_alt_count,
                "crawlAttempts": diagnostics.get("attempts", []),
                "attemptCount": diagnostics.get("attemptCount", 1),
                "configuredRetryCount": diagnostics.get("configuredRetryCount", 0),
                "timeoutMs": diagnostics.get("timeoutMs"),
                "userAgent": diagnostics.get("userAgent"),
                "configuredUserAgents": diagnostics.get("configuredUserAgents", []),
                "configuredProxyCount": diagnostics.get("configuredProxyCount", 0),
                "configuredProxies": diagnostics.get("configuredProxies", []),
                "proxyRotationStrategy": diagnostics.get("proxyRotationStrategy"),
                "selectedProxy": diagnostics.get("selectedProxy"),
                "runtimeOverrides": diagnostics.get("runtimeOverrides", {}),
                "extraHeaders": diagnostics.get("extraHeaders", {}),
                "jitterMs": diagnostics.get("jitterMs"),
                "jsEnabled": diagnostics.get("jsEnabled"),
                "responseStatus": diagnostics.get("responseStatus"),
                "antiBotBlocked": False,
                "antiBotBlockCount": 0,
                "antiBotConsecutiveCount": 0,
                "antiBotEscalated": False,
                "manualInterventionRequired": False,
                "cooldownActive": False,
                "antiBotCooldownMinutes": anti_bot_cooldown_base_minutes,
                "antiBotCooldownUntil": None,
                "remediationHint": "none",
                "blockSignals": [],
                "screenshotArtifactRef": screenshot_artifact_ref,
                "htmlArtifactRef": html_artifact_ref,
            }
            failure_code = None
            fallback_reason = None
            retryable = False
        latency_ms = int((time.perf_counter() - started) * 1000)
        connection = self._build_connection(
            ctx,
            status=status,
            provenance=[ctx.intake.url],
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
        )
        evidence = SourceEvidence(
            provider=self.kind,
            status=status,
            summary=summary,
            provenance=connection.provenance,
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            auth_source=auth_source,
            latency_ms=latency_ms,
        )
        return connection, evidence


class MarketEvidenceAdapter(BaseConnectorAdapter):
    def __init__(self, provider: ConnectorKind) -> None:
        if provider not in MARKET_EVIDENCE_CONNECTOR_KINDS:
            raise ValueError(f"Unsupported market evidence provider: {provider.value}")
        self.kind = provider
        self.label = _connection_label(provider)

    def probe(self, ctx: ConnectorContext) -> tuple[ProjectConnection, SourceEvidence]:
        started = time.perf_counter()
        provider_suffix = _market_provider_env_suffix(ctx.connection.provider)
        provider_url = str(ctx.connection.config.get("providerUrl") or "").strip()
        provider_urls = _coerce_list(ctx.connection.config.get("providerUrls"))
        endpoints = _candidate_endpoints(ctx.connection.config, _market_provider_endpoint_keys(), provider_url)
        access_token, auth_source, auth_header = _resolve_credential_with_header(
            ctx.connection.config,
            _market_provider_credential_keys(),
            [
                f"SEO_AD_BOT_{provider_suffix}_PROVIDER_ACCESS_TOKEN",
                f"SEO_AD_BOT_{provider_suffix}_PROVIDER_CREDENTIALS_JSON",
                f"SEO_AD_BOT_{provider_suffix}_PROVIDER_SERVICE_ACCOUNT_JSON",
                "SEO_AD_BOT_MARKET_PROVIDER_ACCESS_TOKEN",
                "SEO_AD_BOT_MARKET_PROVIDER_CREDENTIALS_JSON",
                "SEO_AD_BOT_MARKET_PROVIDER_SERVICE_ACCOUNT_JSON",
            ],
        )
        strict_mode = bool(get_settings().strict_providers)
        fallback_reason = None
        failure_code = None
        retryable = False
        details: dict[str, Any] = {
            "provider": ctx.connection.provider.value,
            "providerLabel": self.label,
            "providerUrl": provider_url,
            "providerUrls": provider_urls,
            "endpointsConfigured": endpoints,
            "endpointsTried": [],
            "authSource": auth_source,
            "authHeader": auth_header,
            "timeoutMs": int(ctx.connection.config.get("timeoutMs") or get_settings().market_provider_timeout_ms),
        }
        if not ctx.connection.enabled:
            status = ConnectorStatus.unavailable
            fallback_reason = "connector disabled"
            summary = f"{self.label} connector disabled; synthetic market evidence retained."
        elif not endpoints:
            status = ConnectorStatus.missing_credentials
            fallback_reason = "missing provider endpoint"
            failure_code = f"{ctx.connection.provider.value.upper()}_PROVIDER_MISSING"
            summary = f"{self.label} connector is configured without an endpoint."
            retryable = True
        elif not access_token:
            status = ConnectorStatus.missing_credentials
            fallback_reason = "missing accessToken"
            failure_code = f"{ctx.connection.provider.value.upper()}_PROVIDER_AUTH_MISSING"
            summary = f"{self.label} connector is configured without credentials."
            retryable = True
        else:
            payload = {
                "siteUrl": ctx.intake.url,
                "siteHost": _site_host(ctx.intake),
                "keywords": ctx.intake.keywords[:5],
                "mode": "market_evidence",
                "sourceType": ctx.connection.provider.value,
            }
            connected_payload: Optional[dict[str, Any]] = None
            last_error = "market evidence request failed"
            for endpoint in endpoints:
                attempt_started = time.perf_counter()
                try:
                    response = _http_json(
                        endpoint,
                        method="POST",
                        headers={str(auth_header or "Authorization"): f"Bearer {access_token}"},
                        payload=payload,
                        timeout=max(1, int(details["timeoutMs"]) // 1000),
                    )
                    if "raw" in response:
                        raise ValueError("MARKET_PROVIDER_INVALID_PAYLOAD: non-json response")
                    connected_payload = response if isinstance(response, dict) else {"raw": response}
                    details["endpointsTried"].append(
                        {
                            "endpoint": endpoint,
                            "status": "connected",
                            "latencyMs": int((time.perf_counter() - attempt_started) * 1000),
                        }
                    )
                    break
                except HTTPError as exc:
                    current_failure = _http_failure_code(exc, ctx.connection.provider.value.upper())
                    retryable = bool(retryable or 500 <= getattr(exc, "code", 500) < 600)
                    details["endpointsTried"].append(
                        {
                            "endpoint": endpoint,
                            "status": "error",
                            "failureCode": current_failure,
                            "message": str(exc),
                            "retryable": 500 <= getattr(exc, "code", 500) < 600,
                            "latencyMs": int((time.perf_counter() - attempt_started) * 1000),
                        }
                    )
                    failure_code = current_failure
                    last_error = str(exc)
                except Exception as exc:
                    current_failure = _exception_failure_code(exc, ctx.connection.provider.value.upper())
                    retryable = True
                    details["endpointsTried"].append(
                        {
                            "endpoint": endpoint,
                            "status": "error",
                            "failureCode": current_failure,
                            "message": str(exc),
                            "retryable": True,
                            "latencyMs": int((time.perf_counter() - attempt_started) * 1000),
                        }
                    )
                    failure_code = current_failure
                    last_error = str(exc)
            if connected_payload is not None:
                ref = str(connected_payload.get("id") or connected_payload.get("ref") or connected_payload.get("url") or endpoints[0])
                source_ref = f"{ctx.connection.provider.value}:{ref}"
                status = ConnectorStatus.connected
                summary = f"{self.label} provider returned live evidence from {endpoints[0]}."
                details = {
                    **details,
                    "mode": "connected",
                    "selectedEndpoint": endpoints[0],
                    "sample": connected_payload,
                    "sourceRef": source_ref,
                }
                latency_ms = int((time.perf_counter() - started) * 1000)
                connection = self._build_connection(
                    ctx,
                    status=status,
                    provenance=[f"endpoint={endpoints[0]}", f"source={ctx.connection.provider.value}"],
                    details=details,
                    fallback_reason=None,
                    failure_code=None,
                    retryable=False,
                    latency_ms=latency_ms,
                )
                evidence = SourceEvidence(
                    provider=ctx.connection.provider,
                    status=status,
                    summary=summary,
                    provenance=connection.provenance,
                    details=details,
                    source_type=ctx.connection.provider.value,  # type: ignore[arg-type]
                    source_ref=source_ref,
                    retryable=False,
                    auth_source=auth_source,
                    latency_ms=latency_ms,
                )
                return connection, evidence
            status = ConnectorStatus.error if strict_mode else ConnectorStatus.synthetic
            failure_code = failure_code or f"{ctx.connection.provider.value.upper()}_REQUEST_FAILED"
            fallback_reason = last_error
            summary = (
                f"{self.label} provider failed in strict mode; fallback is blocked."
                if strict_mode
                else f"{self.label} provider failed; synthetic market evidence retained."
            )
            details = {
                **details,
                "mode": "strict-error" if strict_mode else "synthetic",
                "failureCode": failure_code,
            }
        latency_ms = int((time.perf_counter() - started) * 1000)
        connection = self._build_connection(
            ctx,
            status=status,
            provenance=[f"source={ctx.connection.provider.value}"],
            details=details,
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            latency_ms=latency_ms,
        )
        evidence = SourceEvidence(
            provider=ctx.connection.provider,
            status=status,
            summary=summary,
            provenance=connection.provenance,
            details=details,
            source_type=ctx.connection.provider.value,  # type: ignore[arg-type]
            source_ref=(
                f"synthetic:{ctx.connection.provider.value}:{_site_host(ctx.intake)}"
                if status == ConnectorStatus.synthetic
                else None
            ),
            fallback_reason=fallback_reason,
            failure_code=failure_code,
            retryable=retryable,
            auth_source=auth_source,
            latency_ms=latency_ms,
        )
        return connection, evidence


class ConnectorGateway:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.adapters: dict[ConnectorKind, BaseConnectorAdapter] = {
            ConnectorKind.search_console: SearchConsoleAdapter(),
            ConnectorKind.ga4: Ga4Adapter(),
            ConnectorKind.github: GitHubAdapter(),
            ConnectorKind.cms: CmsAdapter(),
            ConnectorKind.script_api: ScriptApiAdapter(),
            ConnectorKind.ad_network: AdNetworkAdapter(),
            ConnectorKind.sitemap: SitemapAdapter(),
            ConnectorKind.playwright: PlaywrightAdapter(),
            ConnectorKind.trend: MarketEvidenceAdapter(ConnectorKind.trend),
            ConnectorKind.news: MarketEvidenceAdapter(ConnectorKind.news),
            ConnectorKind.qa: MarketEvidenceAdapter(ConnectorKind.qa),
        }

    def default_connections(self, project_id: str, intake: SiteIntake) -> list[ProjectConnection]:
        return build_default_connections(project_id, intake, self.settings)

    def collect(
        self,
        project_id: str,
        task_id: Optional[str],
        intake: SiteIntake,
        connections: Iterable[ProjectConnection],
    ) -> tuple[list[ProjectConnection], IngestionReport]:
        evidence: list[SourceEvidence] = []
        updated_connections: list[ProjectConnection] = []
        connector_status: dict[str, ConnectorStatus] = {}
        provenance: dict[str, list[str]] = {}
        notes: list[str] = []
        for connection in connections:
            adapter = self.adapters.get(connection.provider)
            if adapter is None:
                status = ConnectorStatus.unavailable
                updated = connection.model_copy()
                updated.status = status
                updated.last_checked_at = utcnow()
                updated.details = {"error": "No adapter registered."}
                updated_connections.append(updated)
                connector_status[connection.provider.value] = status
                provenance[connection.provider.value] = ["adapter-missing"]
                evidence.append(
                    SourceEvidence(
                        provider=connection.provider,
                        status=status,
                        summary="Adapter missing for connector.",
                        provenance=["adapter-missing"],
                        details={"provider": connection.provider.value},
                    )
                )
                continue
            ctx = ConnectorContext(project_id=project_id, task_id=task_id, intake=intake, connection=connection)
            updated, source = adapter.probe(ctx)
            updated_connections.append(updated)
            evidence.append(source)
            connector_status[connection.provider.value] = source.status
            provenance[connection.provider.value] = list(source.provenance)
            if source.fallback_reason:
                notes.append(f"{connection.label}: {source.fallback_reason}")
            elif source.status in {ConnectorStatus.missing_credentials, ConnectorStatus.unavailable}:
                notes.append(f"{connection.label} is using fallback evidence.")
        overall_status = self._aggregate_status(connector_status.values())
        report = IngestionReport(
            report_id=new_id("ingest"),
            project_id=project_id,
            task_id=task_id,
            status=overall_status,
            evidence=evidence,
            connector_status=connector_status,
            provenance=provenance,
            notes=notes,
        )
        return updated_connections, report

    def test(self, project_id: str, intake: SiteIntake, connections: Iterable[ProjectConnection]) -> tuple[list[ProjectConnection], list[str], ConnectionHealth]:
        updated, report = self.collect(project_id, None, intake, connections)
        issues = list(report.notes)
        health = self._health_from_connections(updated)
        return updated, issues, health

    def refresh_provider(
        self,
        project_id: str,
        task_id: Optional[str],
        intake: SiteIntake,
        connections: Iterable[ProjectConnection],
        provider: ConnectorKind,
    ) -> tuple[list[ProjectConnection], SourceEvidence]:
        existing = [connection.model_copy() for connection in connections]
        refreshed: Optional[ProjectConnection] = None
        source: Optional[SourceEvidence] = None
        for index, connection in enumerate(existing):
            if connection.provider != provider:
                continue
            adapter = self.adapters.get(provider)
            if adapter is None:
                updated = connection.model_copy()
                updated.status = ConnectorStatus.unavailable
                updated.last_checked_at = utcnow()
                updated.details = {"error": "No adapter registered for provider refresh."}
                refreshed = updated
                source = SourceEvidence(
                    provider=provider,
                    status=ConnectorStatus.unavailable,
                    summary="Provider refresh skipped because adapter is missing.",
                    provenance=["adapter-missing"],
                    details=updated.details,
                    fallback_reason="adapter missing",
                    retryable=False,
                )
            else:
                ctx = ConnectorContext(project_id=project_id, task_id=task_id, intake=intake, connection=connection)
                refreshed, source = adapter.probe(ctx)
            existing[index] = refreshed
            break
        if refreshed is None or source is None:
            raise ValueError(f"Provider {provider.value} not found in project connections")
        return existing, source

    def _aggregate_status(self, statuses: Iterable[ConnectorStatus]) -> ConnectorStatus:
        statuses = list(statuses)
        if any(status == ConnectorStatus.error for status in statuses):
            return ConnectorStatus.error
        if any(status == ConnectorStatus.connected for status in statuses):
            return ConnectorStatus.connected
        if any(status == ConnectorStatus.synthetic for status in statuses):
            return ConnectorStatus.synthetic
        if any(status == ConnectorStatus.missing_credentials for status in statuses):
            return ConnectorStatus.missing_credentials
        return ConnectorStatus.unavailable

    def _health_from_connections(self, connections: Iterable[ProjectConnection]) -> ConnectionHealth:
        statuses = [connection.status for connection in connections]
        if not statuses:
            return ConnectionHealth.unknown
        if all(status == ConnectorStatus.connected for status in statuses):
            return ConnectionHealth.healthy
        if any(status == ConnectorStatus.error for status in statuses):
            return ConnectionHealth.unavailable
        if any(status == ConnectorStatus.connected for status in statuses):
            return ConnectionHealth.degraded
        if any(status == ConnectorStatus.synthetic for status in statuses):
            return ConnectionHealth.degraded
        if any(status in {ConnectorStatus.missing_credentials, ConnectorStatus.unavailable} for status in statuses):
            return ConnectionHealth.unavailable
        return ConnectionHealth.unknown


class DeploymentGateway:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def build_deployment(
        self,
        task_id: str,
        plan: Plan,
        preview_ref: str,
        intake: SiteIntake,
        site_id: str,
        connections: Iterable[ProjectConnection],
    ) -> DeploymentRecord:
        (
            artifact_ref,
            release_notes,
            fallback_reason,
            failure_code,
            provider_artifact_id,
            provider_url,
            writeback_auth_source,
            writeback_attempts,
        ) = self._artifact_for_mode(
            plan.deployment_mode,
            preview_ref,
            intake,
            site_id,
            connections,
        )
        strict_mode = bool(self.settings.strict_providers)
        if plan.risk_score >= 80:
            status = "blocked"
        elif strict_mode and fallback_reason:
            status = "failed"
            release_notes = [
                *release_notes,
                f"Strict provider mode blocked deployment ({failure_code or 'unknown'}). Resolve connector settings and retry deployment.",
            ]
        elif fallback_reason and (strict_mode or plan.deployment_mode != DeploymentMode.static_export):
            status = "failed"
            release_notes = [*release_notes, f"Writeback is not complete ({failure_code or 'unknown'}). Resolve connector settings and retry deployment."]
        else:
            status = "scheduled"
        return DeploymentRecord(
            deployment_id=new_id("deploy"),
            task_id=task_id,
            mode=plan.deployment_mode,
            status=status,
            artifact_ref=artifact_ref,
            release_notes=[
                f"Deployment mode: {plan.deployment_mode.value}",
                f"Artifact reference: {artifact_ref}",
                *release_notes,
            ],
            rollback_ready=True,
            strict_mode=strict_mode,
            writeback_target=plan.deployment_mode.value,
            writeback_auth_source=writeback_auth_source,
            writeback_attempts=writeback_attempts,
            provider_artifact_id=provider_artifact_id,
            provider_url=provider_url,
            writeback_summary=self._writeback_summary(
                mode=plan.deployment_mode,
                status=status,
                provider_artifact_id=provider_artifact_id,
                provider_url=provider_url,
                writeback_auth_source=writeback_auth_source,
                writeback_attempts=writeback_attempts,
                fallback_reason=fallback_reason,
                failure_code=failure_code,
            ),
            fallback_reason=fallback_reason,
            failure_code=failure_code,
        )

    def _writeback_summary(
        self,
        *,
        mode: DeploymentMode,
        status: str,
        provider_artifact_id: Optional[str],
        provider_url: Optional[str],
        writeback_auth_source: Optional[str],
        writeback_attempts: list[dict[str, Any]],
        fallback_reason: Optional[str],
        failure_code: Optional[str],
    ) -> dict[str, Any]:
        success_count = sum(1 for item in writeback_attempts if str(item.get("status") or "") == "success")
        failed_count = sum(1 for item in writeback_attempts if str(item.get("status") or "") == "failed")
        skipped_count = sum(1 for item in writeback_attempts if str(item.get("status") or "") == "skipped")
        endpoints = [str(item.get("endpoint")) for item in writeback_attempts if item.get("endpoint")]
        successful_endpoints = [str(item.get("endpoint")) for item in writeback_attempts if str(item.get("status") or "") == "success" and item.get("endpoint")]
        failed_endpoints = [str(item.get("endpoint")) for item in writeback_attempts if str(item.get("status") or "") == "failed" and item.get("endpoint")]
        latency_values = [int(item.get("latencyMs")) for item in writeback_attempts if item.get("latencyMs") is not None]
        provider = {
            DeploymentMode.github_pr: "github",
            DeploymentMode.cms_draft: "cms",
            DeploymentMode.universal_script: "script_api",
            DeploymentMode.static_export: "static_export",
        }[mode]
        return {
            "provider": provider,
            "status": status,
            "successCount": success_count,
            "failedCount": failed_count,
            "skippedCount": skipped_count,
            "lastEndpoint": endpoints[-1] if endpoints else None,
            "successfulEndpoints": successful_endpoints,
            "failedEndpoints": failed_endpoints,
            "averageLatencyMs": int(sum(latency_values) / len(latency_values)) if latency_values else None,
            "providerArtifactId": provider_artifact_id,
            "providerUrl": provider_url,
            "authSource": writeback_auth_source,
            "fallbackReason": fallback_reason,
            "failureCode": failure_code,
        }

    def _artifact_for_mode(
        self,
        mode: DeploymentMode,
        preview_ref: str,
        intake: SiteIntake,
        site_id: str,
        connections: Iterable[ProjectConnection],
    ) -> tuple[str, list[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], list[dict[str, Any]]]:
        connection_map = {connection.provider.value: connection for connection in connections}
        if mode == DeploymentMode.github_pr:
            github_connection = connection_map.get("github")
            repo_url = intake.repo_url or (str(github_connection.config.get("repoUrl", "")) if github_connection else "")
            owner = str(github_connection.config.get("owner") or "") if github_connection else ""
            repo = str(github_connection.config.get("repo") or "") if github_connection else ""
            if repo_url and (not owner or not repo):
                path = urlparse(repo_url).path.strip("/")
                if "/" in path:
                    owner, repo = path.split("/", 1)
            access_token, auth_source, auth_header = _resolve_credential_with_header(
                github_connection.config if github_connection else {},
                ["accessToken", "credentialsJson", "serviceAccountJson"],
                [
                    "SEO_AD_BOT_GITHUB_ACCESS_TOKEN",
                    "SEO_AD_BOT_GITHUB_CREDENTIALS_JSON",
                    "SEO_AD_BOT_GITHUB_SERVICE_ACCOUNT_JSON",
                ],
            )
            head_branch = str(github_connection.config.get("headBranch") or "") if github_connection else ""
            base_branch = str(github_connection.config.get("baseBranch") or "main") if github_connection else "main"
            default_endpoint = f"https://api.github.com/repos/{owner}/{repo}/pulls" if owner and repo else ""
            github_config = github_connection.config if github_connection else {}
            github_endpoint_keys = ["apiEndpoints", "apiEndpoint"]
            github_fallback_endpoint = "" if _has_explicit_endpoint_config(github_config, github_endpoint_keys) else default_endpoint
            endpoints = _candidate_endpoints(github_config, github_endpoint_keys, github_fallback_endpoint)
            attempts: list[dict[str, Any]] = []
            if repo_url and owner and repo and access_token and head_branch:
                payload = {
                    "title": github_connection.config.get("title") or f"SEO-AD AutoPilot release for {site_id}",
                    "body": github_connection.config.get("body")
                    or f"Preview-first release bundle for {site_id} derived from {preview_ref}.",
                    "head": head_branch,
                    "base": base_branch,
                    "draft": bool(github_connection.config.get("draft", True)),
                }
                last_reason: Optional[str] = None
                last_code: Optional[str] = None
                for endpoint in endpoints:
                    attempt_started = time.perf_counter()
                    try:
                        response = _http_json(
                            endpoint,
                            method="POST",
                            headers={str(auth_header or "Authorization"): f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
                            payload=payload,
                        )
                        if "raw" in response:
                            last_reason = "GitHub writeback failed: non-json response"
                            last_code = "GITHUB_INVALID_PAYLOAD"
                            attempts.append(
                                {
                                    "endpoint": endpoint,
                                    "status": "failed",
                                    "failureCode": last_code,
                                    "message": last_reason,
                                    "latencyMs": int((time.perf_counter() - attempt_started) * 1000),
                                }
                            )
                            continue
                        pr_url = str(response.get("html_url") or response.get("url") or "")
                        if pr_url:
                            attempts.append({"endpoint": endpoint, "status": "success", "failureCode": None, "latencyMs": int((time.perf_counter() - attempt_started) * 1000)})
                            return (
                                pr_url,
                                ["GitHub PR created from the connected repository."],
                                None,
                                None,
                                str(response.get("number") or response.get("id") or ""),
                                pr_url,
                                auth_source,
                                attempts,
                            )
                        last_reason = "GitHub writeback failed: missing pull request URL in response"
                        last_code = "GITHUB_INVALID_RESPONSE"
                        attempts.append({"endpoint": endpoint, "status": "failed", "failureCode": last_code, "message": last_reason, "latencyMs": int((time.perf_counter() - attempt_started) * 1000)})
                    except HTTPError as exc:
                        last_reason = f"GitHub writeback failed: {exc}"
                        last_code = _http_failure_code(exc, "GITHUB")
                        attempts.append({"endpoint": endpoint, "status": "failed", "failureCode": last_code, "message": str(exc), "latencyMs": int((time.perf_counter() - attempt_started) * 1000)})
                    except Exception as exc:
                        last_reason = f"GitHub writeback failed: {exc}"
                        last_code = _exception_failure_code(exc, "GITHUB")
                        attempts.append({"endpoint": endpoint, "status": "failed", "failureCode": last_code, "message": str(exc), "latencyMs": int((time.perf_counter() - attempt_started) * 1000)})
                return (
                    f"local-pr://{site_id}/{preview_ref}",
                    ["Repository writeback failed; generated a local PR manifest instead."],
                    last_reason or "GitHub writeback failed",
                    last_code or "GITHUB_REQUEST_FAILED",
                    None,
                    None,
                    auth_source,
                    attempts,
                )
            fallback_reason = "missing GitHub repoUrl/accessToken/headBranch"
            return (
                f"local-pr://{site_id}/{preview_ref}",
                ["Repository unavailable; generated a local PR manifest instead."],
                fallback_reason,
                "CONFIG_MISSING_GITHUB",
                None,
                None,
                auth_source,
                [{"endpoint": endpoint, "status": "skipped", "failureCode": "CONFIG_MISSING_GITHUB", "latencyMs": 0} for endpoint in endpoints] if endpoints else [],
            )
        if mode == DeploymentMode.cms_draft:
            cms_connection = connection_map.get("cms")
            cms_name = intake.cms_name or (str(cms_connection.config.get("cmsName", "")) if cms_connection else "")
            cms_config = cms_connection.config if cms_connection else {}
            default_endpoint = str(cms_config.get("draftEndpoint") or cms_config.get("endpoint") or "")
            cms_endpoint_keys = ["draftEndpoints", "draftEndpoint", "endpoints", "endpoint"]
            cms_fallback_endpoint = "" if _has_explicit_endpoint_config(cms_config, cms_endpoint_keys) else default_endpoint
            endpoints = _candidate_endpoints(cms_config, cms_endpoint_keys, cms_fallback_endpoint)
            access_token, auth_source, auth_header = _resolve_credential_with_header(
                cms_connection.config if cms_connection else {},
                ["authToken", "accessToken", "credentialsJson", "serviceAccountJson"],
                [
                    "SEO_AD_BOT_CMS_ACCESS_TOKEN",
                    "SEO_AD_BOT_CMS_CREDENTIALS_JSON",
                    "SEO_AD_BOT_CMS_SERVICE_ACCOUNT_JSON",
                ],
            )
            attempts: list[dict[str, Any]] = []
            if cms_name and endpoints and access_token:
                payload = {
                    "projectId": site_id,
                    "previewRef": preview_ref,
                    "cmsName": cms_name,
                    "mode": "draft",
                }
                last_reason: Optional[str] = None
                last_code: Optional[str] = None
                for endpoint in endpoints:
                    attempt_started = time.perf_counter()
                    try:
                        response = _http_json(
                            endpoint,
                            method="POST",
                            headers={str(auth_header or "Authorization"): f"Bearer {access_token}"},
                            payload=payload,
                        )
                        if "raw" in response:
                            last_reason = "CMS writeback failed: non-json response"
                            last_code = "CMS_INVALID_PAYLOAD"
                            attempts.append(
                                {
                                    "endpoint": endpoint,
                                    "status": "failed",
                                    "failureCode": last_code,
                                    "message": last_reason,
                                    "latencyMs": int((time.perf_counter() - attempt_started) * 1000),
                                }
                            )
                            continue
                        draft_id = str(response.get("draftId") or response.get("id") or "")
                        if draft_id:
                            attempts.append({"endpoint": endpoint, "status": "success", "failureCode": None, "latencyMs": int((time.perf_counter() - attempt_started) * 1000)})
                            return (
                                f"cms://{cms_name}/draft/{draft_id}",
                                ["CMS draft prepared from the connected authoring system."],
                                None,
                                None,
                                draft_id,
                                endpoint,
                                auth_source,
                                attempts,
                            )
                        last_reason = "CMS writeback failed: missing draft id in response"
                        last_code = "CMS_INVALID_RESPONSE"
                        attempts.append({"endpoint": endpoint, "status": "failed", "failureCode": last_code, "message": last_reason, "latencyMs": int((time.perf_counter() - attempt_started) * 1000)})
                    except HTTPError as exc:
                        last_reason = f"CMS writeback failed: {exc}"
                        last_code = _http_failure_code(exc, "CMS")
                        attempts.append({"endpoint": endpoint, "status": "failed", "failureCode": last_code, "message": str(exc), "latencyMs": int((time.perf_counter() - attempt_started) * 1000)})
                    except Exception as exc:
                        last_reason = f"CMS writeback failed: {exc}"
                        last_code = _exception_failure_code(exc, "CMS")
                        attempts.append({"endpoint": endpoint, "status": "failed", "failureCode": last_code, "message": str(exc), "latencyMs": int((time.perf_counter() - attempt_started) * 1000)})
                return (
                    f"cms://{site_id}/draft/{preview_ref}",
                    ["CMS writeback failed; generated a local draft manifest."],
                    last_reason or "CMS writeback failed",
                    last_code or "CMS_REQUEST_FAILED",
                    None,
                    None,
                    auth_source,
                    attempts,
                )
            fallback_reason = "missing CMS endpoint/authToken"
            return (
                f"cms://{site_id}/draft/{preview_ref}",
                ["CMS unavailable; generated a local draft manifest."],
                fallback_reason,
                "CONFIG_MISSING_CMS",
                None,
                None,
                auth_source,
                [{"endpoint": endpoint, "status": "skipped", "failureCode": "CONFIG_MISSING_CMS", "latencyMs": 0} for endpoint in endpoints] if endpoints else [],
            )
        if mode == DeploymentMode.universal_script:
            script_connection = connection_map.get("script_api") or connection_map.get("cms") or connection_map.get("github")
            script_config = script_connection.config if script_connection else {}
            has_script_specific_endpoints = _has_explicit_endpoint_config(script_config, ["scriptEndpoints", "scriptEndpoint"])
            script_endpoint_keys = ["scriptEndpoints", "scriptEndpoint"] if has_script_specific_endpoints else ["scriptEndpoints", "scriptEndpoint", "endpoints", "endpoint"]
            default_endpoint = str(script_config.get("scriptEndpoint") or script_config.get("endpoint") or "")
            script_fallback_endpoint = "" if _has_explicit_endpoint_config(script_config, script_endpoint_keys) else default_endpoint
            endpoints = _candidate_endpoints(script_config, script_endpoint_keys, script_fallback_endpoint)
            access_token, auth_source, auth_header = _resolve_credential_with_header(
                script_connection.config if script_connection else {},
                ["accessToken", "authToken", "credentialsJson", "serviceAccountJson"],
                [
                    "SEO_AD_BOT_SCRIPT_ACCESS_TOKEN",
                    "SEO_AD_BOT_SCRIPT_CREDENTIALS_JSON",
                    "SEO_AD_BOT_SCRIPT_SERVICE_ACCOUNT_JSON",
                    "SEO_AD_BOT_CMS_ACCESS_TOKEN",
                    "SEO_AD_BOT_CMS_CREDENTIALS_JSON",
                    "SEO_AD_BOT_CMS_SERVICE_ACCOUNT_JSON",
                    "SEO_AD_BOT_GITHUB_ACCESS_TOKEN",
                    "SEO_AD_BOT_GITHUB_CREDENTIALS_JSON",
                    "SEO_AD_BOT_GITHUB_SERVICE_ACCOUNT_JSON",
                ],
            )
            attempts: list[dict[str, Any]] = []
            if endpoints and access_token:
                payload = {
                    "projectId": site_id,
                    "previewRef": preview_ref,
                    "script": f"window.__SEO_AD_AUTOPILOT__ = {{ previewRef: {preview_ref!r}, siteId: {site_id!r} }};",
                }
                last_reason: Optional[str] = None
                last_code: Optional[str] = None
                for endpoint in endpoints:
                    attempt_started = time.perf_counter()
                    try:
                        response = _http_json(
                            endpoint,
                            method="POST",
                            headers={str(auth_header or "Authorization"): f"Bearer {access_token}"},
                            payload=payload,
                        )
                        if "raw" in response:
                            last_reason = "Script writeback failed: non-json response"
                            last_code = "SCRIPT_INVALID_PAYLOAD"
                            attempts.append(
                                {
                                    "endpoint": endpoint,
                                    "status": "failed",
                                    "failureCode": last_code,
                                    "message": last_reason,
                                    "latencyMs": int((time.perf_counter() - attempt_started) * 1000),
                                }
                            )
                            continue
                        artifact_id = str(response.get("artifactId") or response.get("id") or "")
                        if artifact_id:
                            attempts.append({"endpoint": endpoint, "status": "success", "failureCode": None, "latencyMs": int((time.perf_counter() - attempt_started) * 1000)})
                            return (
                                f"script://{artifact_id}",
                                ["Universal script bundle prepared with rollback hooks."],
                                None,
                                None,
                                artifact_id,
                                endpoint,
                                auth_source,
                                attempts,
                            )
                        last_reason = "Script writeback failed: missing artifact id in response"
                        last_code = "SCRIPT_INVALID_RESPONSE"
                        attempts.append({"endpoint": endpoint, "status": "failed", "failureCode": last_code, "message": last_reason, "latencyMs": int((time.perf_counter() - attempt_started) * 1000)})
                    except HTTPError as exc:
                        last_reason = f"Script writeback failed: {exc}"
                        last_code = _http_failure_code(exc, "SCRIPT")
                        attempts.append({"endpoint": endpoint, "status": "failed", "failureCode": last_code, "message": str(exc), "latencyMs": int((time.perf_counter() - attempt_started) * 1000)})
                    except Exception as exc:
                        last_reason = f"Script writeback failed: {exc}"
                        last_code = _exception_failure_code(exc, "SCRIPT")
                        attempts.append({"endpoint": endpoint, "status": "failed", "failureCode": last_code, "message": str(exc), "latencyMs": int((time.perf_counter() - attempt_started) * 1000)})
                return (
                    f"script://{site_id}/{preview_ref}.js",
                    ["Universal script bundle prepared locally after writeback failure."],
                    last_reason or "Script writeback failed",
                    last_code or "SCRIPT_REQUEST_FAILED",
                    None,
                    None,
                    auth_source,
                    attempts,
                )
            fallback_reason = "missing script endpoint/token"
            return (
                f"script://{site_id}/{preview_ref}.js",
                ["Universal script endpoint unavailable; generated a local rollback-ready script manifest."],
                fallback_reason,
                "CONFIG_MISSING_SCRIPT",
                None,
                None,
                auth_source,
                [{"endpoint": endpoint, "status": "skipped", "failureCode": "CONFIG_MISSING_SCRIPT", "latencyMs": 0} for endpoint in endpoints] if endpoints else [],
            )
        static_connection = connection_map.get("script_api")
        static_config: dict[str, Any] = {}
        if static_connection is not None:
            static_config.update(static_connection.config)
        if intake.approval_rules:
            static_config.setdefault("staticEndpoint", intake.approval_rules.get("staticExportEndpoint"))
            static_config.setdefault("staticEndpoints", intake.approval_rules.get("staticExportEndpoints"))

        default_endpoint = str(static_config.get("staticEndpoint") or self.settings.static_export_provider_url or "").strip()
        configured_endpoint_hints = _coerce_list(static_config.get("staticEndpoints")) + _coerce_list(self.settings.static_export_provider_urls)
        explicit_provider_config = bool(default_endpoint or configured_endpoint_hints)
        if not explicit_provider_config:
            return (
                f"static://{site_id}/{preview_ref}",
                ["Static export bundle prepared with rollback snapshot."],
                None,
                None,
                preview_ref,
                None,
                "none",
                [],
            )
        endpoints = _candidate_endpoints(static_config, ["staticEndpoints", "staticEndpoint"], default_endpoint)
        for endpoint in _coerce_list(self.settings.static_export_provider_urls):
            if endpoint not in endpoints:
                endpoints.append(endpoint)
        access_token, auth_source, auth_header = _resolve_credential_with_header(
            static_config,
            [
                "staticAccessToken",
                "accessToken",
                "authToken",
                "staticCredentialsJson",
                "credentialsJson",
                "serviceAccountJson",
            ],
            [
                "SEO_AD_BOT_STATIC_EXPORT_ACCESS_TOKEN",
                "SEO_AD_BOT_STATIC_EXPORT_CREDENTIALS_JSON",
                "SEO_AD_BOT_STATIC_EXPORT_SERVICE_ACCOUNT_JSON",
                "SEO_AD_BOT_SCRIPT_ACCESS_TOKEN",
                "SEO_AD_BOT_SCRIPT_CREDENTIALS_JSON",
                "SEO_AD_BOT_SCRIPT_SERVICE_ACCOUNT_JSON",
            ],
        )
        attempts: list[dict[str, Any]] = []
        if endpoints and access_token:
            payload = {
                "projectId": site_id,
                "previewRef": preview_ref,
                "mode": "static_export",
                "rollbackReady": True,
            }
            last_reason: Optional[str] = None
            last_code: Optional[str] = None
            for endpoint in endpoints:
                attempt_started = time.perf_counter()
                try:
                    response = _http_json(
                        endpoint,
                        method="POST",
                        headers={str(auth_header or "Authorization"): f"Bearer {access_token}"},
                        payload=payload,
                    )
                    artifact_id = str(response.get("artifactId") or response.get("id") or "")
                    artifact_url = str(response.get("artifactUrl") or response.get("url") or "")
                    if artifact_id or artifact_url:
                        attempts.append(
                            {
                                "endpoint": endpoint,
                                "status": "success",
                                "failureCode": None,
                                "latencyMs": int((time.perf_counter() - attempt_started) * 1000),
                            }
                        )
                        return (
                            artifact_url or f"static://{site_id}/{artifact_id or preview_ref}",
                            ["Static export package pushed to the connected provider."],
                            None,
                            None,
                            artifact_id or preview_ref,
                            endpoint,
                            auth_source,
                            attempts,
                        )
                    last_reason = "Static export writeback failed: missing artifact id/url in response"
                    last_code = "STATIC_EXPORT_INVALID_RESPONSE"
                    attempts.append(
                        {
                            "endpoint": endpoint,
                            "status": "failed",
                            "failureCode": last_code,
                            "message": last_reason,
                            "latencyMs": int((time.perf_counter() - attempt_started) * 1000),
                        }
                    )
                except HTTPError as exc:
                    last_reason = f"Static export writeback failed: {exc}"
                    last_code = _http_failure_code(exc, "STATIC_EXPORT")
                    attempts.append(
                        {
                            "endpoint": endpoint,
                            "status": "failed",
                            "failureCode": last_code,
                            "message": str(exc),
                            "latencyMs": int((time.perf_counter() - attempt_started) * 1000),
                        }
                    )
                except Exception as exc:
                    last_reason = f"Static export writeback failed: {exc}"
                    last_code = _exception_failure_code(exc, "STATIC_EXPORT")
                    attempts.append(
                        {
                            "endpoint": endpoint,
                            "status": "failed",
                            "failureCode": last_code,
                            "message": str(exc),
                            "latencyMs": int((time.perf_counter() - attempt_started) * 1000),
                        }
                    )
            return (
                f"static://{site_id}/{preview_ref}",
                ["Static export writeback failed; generated a local rollback snapshot."],
                last_reason or "Static export writeback failed",
                last_code or "STATIC_EXPORT_REQUEST_FAILED",
                None,
                None,
                auth_source,
                attempts,
            )

        fallback_reason = "missing static export endpoint/token"
        return (
            f"static://{site_id}/{preview_ref}",
            ["Static export provider unavailable; generated a local rollback snapshot."],
            fallback_reason,
            "CONFIG_MISSING_STATIC_EXPORT",
            preview_ref,
            None,
            auth_source,
            [{"endpoint": endpoint, "status": "skipped", "failureCode": "CONFIG_MISSING_STATIC_EXPORT", "latencyMs": 0} for endpoint in endpoints] if endpoints else [],
        )
