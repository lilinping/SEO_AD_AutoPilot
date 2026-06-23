from __future__ import annotations

import base64
import os
import random
import re
import time
from typing import Any, Optional
from urllib.parse import urlparse, urlsplit

from playwright.sync_api import sync_playwright

from .models import PagePerformanceBudget, PageSnapshot


def _browser_timeout_ms() -> int:
    value = os.getenv("SEO_AD_BOT_BROWSER_CRAWL_TIMEOUT_MS", "7000")
    try:
        return max(2000, int(value))
    except ValueError:
        return 7000


def _browser_retry_count() -> int:
    value = os.getenv("SEO_AD_BOT_BROWSER_CRAWL_RETRY_COUNT", "1")
    try:
        return max(0, int(value))
    except ValueError:
        return 1


def _browser_user_agent() -> str:
    return os.getenv("SEO_AD_BOT_BROWSER_CRAWL_USER_AGENT", "SEO-AD-AutoPilot/1.0")


def _browser_user_agents() -> list[str]:
    raw = str(os.getenv("SEO_AD_BOT_BROWSER_CRAWL_USER_AGENTS", "")).strip()
    candidates = [item.strip() for item in re.split(r"[\n,]", raw) if item.strip()]
    if candidates:
        return candidates
    return [_browser_user_agent()]


def _coerce_int(value: Any, fallback: int, minimum: Optional[int] = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(fallback)
    if minimum is not None:
        return max(int(minimum), parsed)
    return parsed


def _coerce_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(fallback)


def _browser_js_enabled() -> bool:
    return os.getenv("SEO_AD_BOT_BROWSER_CRAWL_JS_ENABLED", "true").lower() in {"1", "true", "yes"}


def _browser_backoff_ms() -> int:
    value = os.getenv("SEO_AD_BOT_BROWSER_CRAWL_BACKOFF_MS", "250")
    try:
        return max(50, int(value))
    except ValueError:
        return 250


def _browser_jitter_ms() -> int:
    value = os.getenv("SEO_AD_BOT_BROWSER_CRAWL_JITTER_MS", "120")
    try:
        return max(0, int(value))
    except ValueError:
        return 120


def _browser_anti_bot_escalation_threshold() -> int:
    value = os.getenv("SEO_AD_BOT_BROWSER_CRAWL_ANTI_BOT_ESCALATION_THRESHOLD", "2")
    try:
        return max(1, int(value))
    except ValueError:
        return 2


def _browser_proxy_rotation_strategy() -> str:
    value = str(os.getenv("SEO_AD_BOT_BROWSER_CRAWL_PROXY_ROTATION", "round_robin")).strip().lower()
    if value in {"random", "shuffle"}:
        return "random"
    return "round_robin"


def _split_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raw = str(value or "").strip()
    if not raw:
        return []
    return [item.strip() for item in re.split(r"[\n,]", raw) if item.strip()]


def _coerce_proxy_server(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if "://" not in value:
        return f"http://{value}"
    return value


def _parse_proxy_entry(raw: str) -> Optional[dict[str, str]]:
    proxy_server = _coerce_proxy_server(raw)
    if not proxy_server:
        return None
    parsed = urlsplit(proxy_server)
    if not parsed.hostname:
        return None
    scheme = parsed.scheme or "http"
    host = parsed.hostname
    port = parsed.port
    server = f"{scheme}://{host}:{port}" if port else f"{scheme}://{host}"
    result: dict[str, str] = {"server": server}
    if parsed.username:
        result["username"] = parsed.username
    if parsed.password:
        result["password"] = parsed.password
    return result


def _browser_proxies() -> list[dict[str, str]]:
    return _parse_proxy_pool(
        single_proxy=str(os.getenv("SEO_AD_BOT_BROWSER_CRAWL_PROXY", "")).strip(),
        multi_proxy=os.getenv("SEO_AD_BOT_BROWSER_CRAWL_PROXIES", ""),
    )


def _parse_proxy_pool(*, single_proxy: str, multi_proxy: Any) -> list[dict[str, str]]:
    entries: list[str] = []
    if single_proxy:
        entries.append(single_proxy)
    entries.extend(_split_values(multi_proxy))
    parsed: list[dict[str, str]] = []
    for entry in entries:
        proxy = _parse_proxy_entry(entry)
        if proxy is None:
            continue
        if proxy not in parsed:
            parsed.append(proxy)
    return parsed


def _resolve_runtime_proxies(options: Optional[dict[str, Any]]) -> list[dict[str, str]]:
    if not options:
        return _browser_proxies()
    single_proxy = str(options.get("proxy") or "").strip()
    multi_proxy = options.get("proxies")
    parsed = _parse_proxy_pool(single_proxy=single_proxy, multi_proxy=multi_proxy)
    if parsed:
        return parsed
    return _browser_proxies()


def _resolve_runtime_proxy_rotation(options: Optional[dict[str, Any]]) -> str:
    if not options:
        return _browser_proxy_rotation_strategy()
    raw = str(options.get("proxyRotation") or "").strip().lower()
    if raw in {"round_robin", "random", "shuffle"}:
        return "random" if raw in {"random", "shuffle"} else "round_robin"
    return _browser_proxy_rotation_strategy()


def _resolve_runtime_user_agents(options: Optional[dict[str, Any]]) -> list[str]:
    if not options:
        return _browser_user_agents()
    configured = _split_values(options.get("userAgents"))
    if configured:
        return configured
    single = str(options.get("userAgent") or "").strip()
    if single:
        return [single]
    return _browser_user_agents()


def _resolve_runtime_headers(options: Optional[dict[str, Any]]) -> dict[str, str]:
    headers = _browser_extra_headers()
    if not options:
        return headers
    extra = options.get("extraHeaders")
    if isinstance(extra, dict):
        for key, value in extra.items():
            header_key = str(key).strip()
            header_value = str(value).strip()
            if header_key and header_value:
                headers[header_key] = header_value
    return headers


def _resolve_runtime_timeout_ms(options: Optional[dict[str, Any]]) -> int:
    fallback = _browser_timeout_ms()
    if not options:
        return fallback
    return _coerce_int(options.get("timeoutMs"), fallback, minimum=2000)


def _resolve_runtime_retry_count(options: Optional[dict[str, Any]]) -> int:
    fallback = _browser_retry_count()
    if not options:
        return fallback
    return _coerce_int(options.get("retryCount"), fallback, minimum=0)


def _resolve_runtime_js_enabled(options: Optional[dict[str, Any]]) -> bool:
    fallback = _browser_js_enabled()
    if not options:
        return fallback
    return _coerce_bool(options.get("jsEnabled"), fallback)


def _resolve_runtime_backoff_ms(options: Optional[dict[str, Any]]) -> int:
    fallback = _browser_backoff_ms()
    if not options:
        return fallback
    return _coerce_int(options.get("backoffMs"), fallback, minimum=50)


def _resolve_runtime_jitter_ms(options: Optional[dict[str, Any]]) -> int:
    fallback = _browser_jitter_ms()
    if not options:
        return fallback
    return _coerce_int(options.get("jitterMs"), fallback, minimum=0)


def _resolve_runtime_antibot_escalation_threshold(options: Optional[dict[str, Any]]) -> int:
    fallback = _browser_anti_bot_escalation_threshold()
    if not options:
        return fallback
    return _coerce_int(options.get("antiBotEscalationThreshold"), fallback, minimum=1)


def _runtime_overrides_summary(options: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not options:
        return {}
    return {
        "timeoutMs": options.get("timeoutMs"),
        "retryCount": options.get("retryCount"),
        "userAgentsConfigured": len(_split_values(options.get("userAgents"))) > 0 or bool(str(options.get("userAgent") or "").strip()),
        "proxyConfigured": bool(str(options.get("proxy") or "").strip() or _split_values(options.get("proxies"))),
        "proxyRotation": str(options.get("proxyRotation") or "").strip() or None,
        "jsEnabled": options.get("jsEnabled"),
        "headersConfigured": isinstance(options.get("extraHeaders"), dict) and bool(options.get("extraHeaders")),
    }


def _sanitized_proxy(proxy: Optional[dict[str, str]]) -> Optional[dict[str, Any]]:
    if not proxy:
        return None
    return {
        "server": str(proxy.get("server") or ""),
        "hasAuth": bool(proxy.get("username")),
    }


def _select_proxy(proxies: list[dict[str, str]], attempt: int, strategy: str) -> Optional[dict[str, str]]:
    if not proxies:
        return None
    if strategy == "random":
        return random.choice(proxies)
    index = max(0, int(attempt)) % len(proxies)
    return proxies[index]


def _has_alternative_browser_fingerprint(
    *,
    selected_proxy: Optional[dict[str, str]],
    proxies: list[dict[str, str]],
    selected_user_agent: str,
    user_agents: list[str],
    attempt: int,
) -> bool:
    if attempt < 0:
        return False
    if len(user_agents) > 1:
        current_ua_index = user_agents.index(selected_user_agent) if selected_user_agent in user_agents else -1
        if current_ua_index < 0 or current_ua_index < len(user_agents) - 1:
            return True
    if len(proxies) > 1:
        current_proxy = _sanitized_proxy(selected_proxy)
        proxies_sanitized = [_sanitized_proxy(item) for item in proxies]
        if current_proxy in proxies_sanitized:
            current_proxy_index = proxies_sanitized.index(current_proxy)
        else:
            current_proxy_index = -1
        if current_proxy_index < 0 or current_proxy_index < len(proxies_sanitized) - 1:
            return True
    return False


def _browser_extra_headers() -> dict[str, str]:
    headers: dict[str, str] = {
        "Accept-Language": os.getenv("SEO_AD_BOT_BROWSER_CRAWL_ACCEPT_LANGUAGE", "en-US,en;q=0.9"),
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    }
    raw = os.getenv("SEO_AD_BOT_BROWSER_CRAWL_EXTRA_HEADERS", "").strip()
    if not raw:
        return headers
    for entry in raw.split(","):
        key, sep, value = entry.partition(":")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if key and value:
            headers[key] = value
    return headers


def _extract_block_signals_from_text(message: str) -> list[str]:
    text = str(message or "").lower()
    signal_patterns: list[tuple[str, str]] = [
        ("captcha", r"\bcaptcha\b"),
        ("turnstile", r"\bturnstile\b"),
        ("hcaptcha", r"\bhcaptcha\b"),
        ("recaptcha", r"re\\s*captcha|recaptcha"),
        ("challenge", r"\bchallenge\b"),
        ("access-denied", r"access denied"),
        ("forbidden", r"\bforbidden\b"),
        ("security-check", r"security check"),
        ("js-challenge", r"checking your browser|javascript challenge|js challenge"),
        ("verify-human", r"verify (that )?you are human"),
        ("cloudflare", r"cloudflare"),
        ("akamai", r"akamai"),
        ("datadome", r"datadome"),
        ("perimeterx", r"perimeterx|human security"),
        ("incapsula", r"incapsula|imperva"),
        ("ddos-guard", r"ddos-guard|ddos guard"),
        ("bot-detected", r"bot (detected|detection)"),
        ("enable-js-cookies", r"enable (javascript|js) and cookies"),
        ("human-verification", r"human verification|verify (you|that you) are (a )?human"),
        ("http-429", r"\b429\b|too many requests|rate limit"),
        ("http-403", r"\b403\b"),
    ]
    detected = [name for name, pattern in signal_patterns if re.search(pattern, text)]
    return list(dict.fromkeys(detected))


def _classify_crawl_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "anti-bot" in message or _extract_block_signals_from_text(message):
        return "PLAYWRIGHT_ANTI_BOT_BLOCKED"
    if "timed out" in message or "timeout" in message:
        return "PLAYWRIGHT_TIMEOUT"
    if "name or service not known" in message or "temporary failure in name resolution" in message:
        return "PLAYWRIGHT_NETWORK_ERROR"
    if "connection refused" in message or "connection reset" in message:
        return "PLAYWRIGHT_NETWORK_ERROR"
    if "navigation" in message:
        return "PLAYWRIGHT_NAVIGATION_ERROR"
    return "PLAYWRIGHT_REQUEST_FAILED"


def _anti_bot_attempt_stats(attempts: list[dict[str, Any]]) -> tuple[int, int]:
    anti_bot_count = 0
    for item in attempts:
        if str(item.get("failureCode") or "") == "PLAYWRIGHT_ANTI_BOT_BLOCKED":
            anti_bot_count += 1
    consecutive_count = 0
    for item in reversed(attempts):
        if str(item.get("failureCode") or "") == "PLAYWRIGHT_ANTI_BOT_BLOCKED":
            consecutive_count += 1
            continue
        break
    return anti_bot_count, consecutive_count


def crawl_page_with_diagnostics(
    url: str,
    fallback_title: str,
    fallback_description: str,
    runtime_options: Optional[dict[str, Any]] = None,
) -> tuple[Optional[PageSnapshot], dict[str, Any]]:
    timeout_ms = _resolve_runtime_timeout_ms(runtime_options)
    retry_count = _resolve_runtime_retry_count(runtime_options)
    user_agents = _resolve_runtime_user_agents(runtime_options)
    js_enabled = _resolve_runtime_js_enabled(runtime_options)
    backoff_ms = _resolve_runtime_backoff_ms(runtime_options)
    jitter_ms = _resolve_runtime_jitter_ms(runtime_options)
    anti_bot_escalation_threshold = _resolve_runtime_antibot_escalation_threshold(runtime_options)
    extra_headers = _resolve_runtime_headers(runtime_options)
    proxies = _resolve_runtime_proxies(runtime_options)
    proxy_rotation_strategy = _resolve_runtime_proxy_rotation(runtime_options)
    runtime_overrides = _runtime_overrides_summary(runtime_options)
    configured_proxy_servers = [str(item.get("server") or "") for item in proxies if str(item.get("server") or "").strip()]
    attempts: list[dict[str, Any]] = []
    detected_block_signals: list[str] = []
    try:
        with sync_playwright() as playwright:
            for attempt in range(retry_count + 1):
                browser = None
                context = None
                page = None
                selected_user_agent = random.choice(user_agents) if user_agents else _browser_user_agent()
                selected_proxy = _select_proxy(proxies, attempt, proxy_rotation_strategy)
                attempt_started = time.perf_counter()
                try:
                    launch_kwargs: dict[str, Any] = {"headless": True}
                    if selected_proxy is not None:
                        launch_kwargs["proxy"] = selected_proxy
                    browser = playwright.chromium.launch(**launch_kwargs)
                    context = browser.new_context(
                        viewport={"width": 1440, "height": 1600},
                        user_agent=selected_user_agent,
                        java_script_enabled=js_enabled,
                        ignore_https_errors=True,
                        extra_http_headers=extra_headers,
                    )
                    page = context.new_page()
                    page.set_default_navigation_timeout(timeout_ms)
                    page.set_default_timeout(timeout_ms)
                    response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    if jitter_ms > 0:
                        wait_ms = min(2500, max(50, int((timeout_ms // 6) + random.uniform(0, jitter_ms))))
                        page.wait_for_timeout(wait_ms)
                    else:
                        page.wait_for_timeout(min(1500, max(300, timeout_ms // 5)))
                    if js_enabled:
                        try:
                            page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5000))
                        except Exception:
                            pass
                    payload = page.evaluate(
                        """
                            () => {
                              const text = (value) => (value || '').trim();
                              const headings = Array.from(document.querySelectorAll('h1, h2, h3'))
                                .map((el) => text(el.textContent))
                                .filter(Boolean)
                                .slice(0, 8);
                              const anchors = Array.from(document.querySelectorAll('a[href]'));
                              const hrefs = anchors.map((el) => {
                                try {
                                  return new URL(el.href, window.location.href).href;
                                } catch (error) {
                                  return '';
                                }
                              }).filter(Boolean);
                              const images = Array.from(document.querySelectorAll('img'));
                              const bodyWords = text(document.body?.innerText || '').split(/\\s+/).filter(Boolean);
                              const ctaLabels = Array.from(document.querySelectorAll('a, button'))
                                .map((el) => text(el.textContent).toLowerCase())
                                .filter(Boolean);
                              const bodyText = text(document.body?.innerText || '').toLowerCase();
                              const structuredData = Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
                                .map((script) => text(script.textContent))
                                .filter(Boolean);
                              const blockSignals = [];
                              const blockPatterns = [
                                /captcha/i,
                                /turnstile/i,
                                /hcaptcha/i,
                                /recaptcha/i,
                                /access denied/i,
                                /verify you are human/i,
                                /security check/i,
                                /bot detection/i,
                                /cloudflare/i,
                                /attention required/i,
                                /checking your browser/i,
                                /javascript challenge/i
                              ];
                              for (const pattern of blockPatterns) {
                                if (pattern.test(document.title || '') || pattern.test(bodyText)) {
                                  blockSignals.push(pattern.source);
                                }
                              }
                              if (document.querySelector('iframe[src*=\"captcha\"], form[action*=\"captcha\"], #challenge-running, [data-cf-beacon], [id*=\"cf-challenge\"], iframe[src*=\"turnstile\"], div[class*=\"h-captcha\"], div[class*=\"g-recaptcha\"]')) {
                                blockSignals.push('challenge-dom');
                              }
                              return {
                                title: text(document.title),
                                description: text(document.querySelector('meta[name="description"]')?.content),
                                headings,
                                hrefs,
                                images: images.length,
                                missingAltCount: images.filter((img) => !text(img.getAttribute('alt'))).length,
                                wordCount: bodyWords.length,
                                ctaCount: ctaLabels.filter((label) => /buy|shop|start|get|learn|contact|subscribe|read|trial|demo|sign up|book/i.test(label)).length,
                                structuredData,
                                blockSignals: Array.from(new Set(blockSignals)).slice(0, 8),
                              };
                            }
                        """
                    )
                    page_html = page.content()
                    screenshot_bytes = page.screenshot(full_page=True)
                    response_status = int(response.status) if response is not None else 0
                    block_signals = [str(item) for item in payload.get("blockSignals", []) if str(item).strip()]
                    if response_status in {401, 403, 429, 503}:
                        block_signals.append(f"http-{response_status}")
                    if block_signals:
                        raise RuntimeError(f"anti-bot block detected: {', '.join(sorted(set(block_signals)))}")
                    host = urlparse(url).netloc.lower()
                    internal_links = len([href for href in payload["hrefs"] if host in href.lower()])
                    external_links = max(0, len(payload["hrefs"]) - internal_links)
                    word_count = int(payload["wordCount"])
                    images = int(payload["images"])
                    performance_budget = PagePerformanceBudget(
                        lcp_ms=1600 + min(1400, (word_count // 3) + images * 16),
                        cls=round(min(0.25, 0.02 + images * 0.003), 3),
                        inp_ms=110 + min(260, len(payload["headings"]) * 8 + internal_links * 2),
                    )
                    snapshot = PageSnapshot(
                        url=url,
                        title=payload["title"] or fallback_title,
                        description=payload["description"] or fallback_description,
                        headings=payload["headings"] or [fallback_title],
                        word_count=word_count,
                        internal_links=internal_links,
                        external_links=external_links,
                        images=images,
                        missing_alt_count=int(payload["missingAltCount"]),
                        structured_data=payload["structuredData"] or [],
                        cta_count=int(payload["ctaCount"]),
                        performance_budget=performance_budget,
                    )
                    attempts.append(
                        {
                            "attempt": attempt + 1,
                            "status": "connected",
                            "elapsedMs": int((time.perf_counter() - attempt_started) * 1000),
                            "waitedMs": 0,
                            "userAgent": selected_user_agent,
                            "proxy": _sanitized_proxy(selected_proxy),
                        }
                    )
                    anti_bot_block_count, anti_bot_consecutive_count = _anti_bot_attempt_stats(attempts)
                    return snapshot, {
                        "attempts": attempts,
                        "attemptCount": len(attempts),
                        "configuredRetryCount": retry_count,
                        "timeoutMs": timeout_ms,
                        "userAgent": selected_user_agent,
                        "configuredUserAgents": user_agents,
                        "configuredProxyCount": len(configured_proxy_servers),
                        "configuredProxies": configured_proxy_servers,
                        "proxyRotationStrategy": proxy_rotation_strategy,
                        "selectedProxy": _sanitized_proxy(selected_proxy),
                        "extraHeaders": extra_headers,
                        "jitterMs": jitter_ms,
                        "jsEnabled": js_enabled,
                        "responseStatus": response_status,
                        "antiBotBlocked": anti_bot_block_count > 0,
                        "antiBotBlockCount": anti_bot_block_count,
                        "antiBotConsecutiveCount": anti_bot_consecutive_count,
                        "antiBotEscalated": anti_bot_consecutive_count >= anti_bot_escalation_threshold,
                        "manualInterventionRequired": anti_bot_consecutive_count >= anti_bot_escalation_threshold,
                        "remediationHint": "none",
                        "blockSignals": detected_block_signals,
                        "_htmlContent": page_html,
                        "_screenshotB64": base64.b64encode(screenshot_bytes).decode("ascii"),
                        "failureCode": None,
                        "fallbackReason": None,
                        "runtimeOverrides": runtime_overrides,
                    }
                except Exception as exc:
                    failure_code = _classify_crawl_error(exc)
                    block_signals = _extract_block_signals_from_text(str(exc))
                    for signal in block_signals:
                        if signal not in detected_block_signals:
                            detected_block_signals.append(signal)
                    attempts.append(
                        {
                            "attempt": attempt + 1,
                            "status": "error",
                            "failureCode": failure_code,
                            "fallbackReason": str(exc),
                            "blockSignals": block_signals,
                            "rotationAvailable": _has_alternative_browser_fingerprint(
                                selected_proxy=selected_proxy,
                                proxies=proxies,
                                selected_user_agent=selected_user_agent,
                                user_agents=user_agents,
                                attempt=attempt,
                            ),
                            "elapsedMs": int((time.perf_counter() - attempt_started) * 1000),
                            "userAgent": selected_user_agent,
                            "proxy": _sanitized_proxy(selected_proxy),
                        }
                    )
                    if failure_code == "PLAYWRIGHT_ANTI_BOT_BLOCKED" and not attempts[-1]["rotationAvailable"]:
                        break
                    if attempt >= retry_count:
                        break
                    sleep_seconds = min(
                        2.0,
                        ((backoff_ms / 1000.0) * (2 ** attempt)) + (random.uniform(0, jitter_ms) / 1000.0 if jitter_ms > 0 else 0.0),
                    )
                    attempts[-1]["waitedMs"] = int(sleep_seconds * 1000)
                    time.sleep(sleep_seconds)
                finally:
                    try:
                        if page is not None:
                            page.close()
                    except Exception:
                        pass
                    try:
                        if context is not None:
                            context.close()
                    except Exception:
                        pass
                    try:
                        if browser is not None:
                            browser.close()
                    except Exception:
                        pass
        last = attempts[-1] if attempts else {}
        anti_bot_block_count, anti_bot_consecutive_count = _anti_bot_attempt_stats(attempts)
        anti_bot_escalated = anti_bot_consecutive_count >= anti_bot_escalation_threshold
        manual_intervention_required = anti_bot_escalated
        return None, {
            "attempts": attempts,
            "attemptCount": len(attempts),
            "configuredRetryCount": retry_count,
            "timeoutMs": timeout_ms,
            "userAgent": str((attempts[-1] if attempts else {}).get("userAgent") or (user_agents[0] if user_agents else _browser_user_agent())),
            "configuredUserAgents": user_agents,
            "configuredProxyCount": len(configured_proxy_servers),
            "configuredProxies": configured_proxy_servers,
            "proxyRotationStrategy": proxy_rotation_strategy,
            "selectedProxy": (last.get("proxy") if isinstance(last, dict) else None),
            "extraHeaders": extra_headers,
            "jitterMs": jitter_ms,
            "jsEnabled": js_enabled,
            "responseStatus": 0,
            "antiBotBlocked": str(last.get("failureCode")) == "PLAYWRIGHT_ANTI_BOT_BLOCKED",
            "antiBotBlockCount": anti_bot_block_count,
            "antiBotConsecutiveCount": anti_bot_consecutive_count,
            "antiBotEscalated": anti_bot_escalated,
            "manualInterventionRequired": manual_intervention_required,
            "remediationHint": (
                "anti-bot challenge persisted; rotate proxy/cookies and re-verify crawl permissions."
                if manual_intervention_required
                else "retry after short backoff"
            ),
            "blockSignals": detected_block_signals,
            "failureCode": str(last.get("failureCode") or "PLAYWRIGHT_REQUEST_FAILED"),
            "fallbackReason": str(last.get("fallbackReason") or "crawl returned no snapshot"),
            "runtimeOverrides": runtime_overrides,
        }
    except Exception as exc:
        failure_code = _classify_crawl_error(exc)
        anti_bot_block_count, anti_bot_consecutive_count = _anti_bot_attempt_stats(attempts)
        anti_bot_escalated = (
            anti_bot_consecutive_count >= _browser_anti_bot_escalation_threshold()
            or (failure_code == "PLAYWRIGHT_ANTI_BOT_BLOCKED" and anti_bot_block_count + 1 >= _browser_anti_bot_escalation_threshold())
        )
        manual_intervention_required = anti_bot_escalated
        return None, {
            "attempts": attempts,
            "attemptCount": len(attempts),
            "configuredRetryCount": retry_count,
            "timeoutMs": timeout_ms,
            "userAgent": str((attempts[-1] if attempts else {}).get("userAgent") or (user_agents[0] if user_agents else _browser_user_agent())),
            "configuredUserAgents": user_agents,
            "configuredProxyCount": len(configured_proxy_servers),
            "configuredProxies": configured_proxy_servers,
            "proxyRotationStrategy": proxy_rotation_strategy,
            "selectedProxy": None,
            "extraHeaders": extra_headers,
            "jitterMs": jitter_ms,
            "jsEnabled": js_enabled,
            "responseStatus": 0,
            "antiBotBlocked": failure_code == "PLAYWRIGHT_ANTI_BOT_BLOCKED",
            "antiBotBlockCount": anti_bot_block_count + (1 if failure_code == "PLAYWRIGHT_ANTI_BOT_BLOCKED" else 0),
            "antiBotConsecutiveCount": anti_bot_consecutive_count + (1 if failure_code == "PLAYWRIGHT_ANTI_BOT_BLOCKED" else 0),
            "antiBotEscalated": anti_bot_escalated,
            "manualInterventionRequired": manual_intervention_required,
            "remediationHint": (
                "anti-bot challenge persisted; rotate proxy/cookies and re-verify crawl permissions."
                if manual_intervention_required
                else "retry after short backoff"
            ),
            "blockSignals": detected_block_signals or _extract_block_signals_from_text(str(exc)),
            "failureCode": failure_code,
            "fallbackReason": str(exc),
            "runtimeOverrides": runtime_overrides,
        }


def crawl_page(url: str, fallback_title: str, fallback_description: str) -> Optional[PageSnapshot]:
    snapshot, _ = crawl_page_with_diagnostics(url, fallback_title, fallback_description)
    return snapshot
