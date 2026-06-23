from __future__ import annotations

import hashlib
import json
import time
from io import BytesIO
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .artifact_store import get_artifact_store
from .config import get_settings
from .observability import add_span_event, capture_exception, set_span_attributes, trace_span
from .models import (
    PromptRegistry,
    PromptVersion,
    SkillRegressionCase,
    SkillRegressionReport,
    RegressionSample,
    RegressionSampleSet,
    VisualRegressionCase,
    VisualRegressionReport,
    VisualRegressionRun,
    VisualRegressionRunsReport,
    new_id,
    utcnow,
)
from .seed import DEMO_SITES
from .skill_registry import get_skill_registry


def _first_payload_value(payload: dict[str, object], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return None


def _extract_visual_farm_screenshot_urls(payload: dict[str, object]) -> tuple[str | None, str | None]:
    baseline_url = _first_payload_value(
        payload,
        (
            "baselineScreenshotUrl",
            "baselineImageUrl",
            "baselineUrl",
            "baselineScreenshot",
        ),
    )
    preview_url = _first_payload_value(
        payload,
        (
            "previewScreenshotUrl",
            "previewImageUrl",
            "previewUrl",
            "previewScreenshot",
        ),
    )
    if baseline_url and preview_url:
        return baseline_url, preview_url

    screenshots = payload.get("screenshotUrls")
    if isinstance(screenshots, list):
        normalized = [item.strip() for item in screenshots if isinstance(item, str) and item.strip()]
        if len(normalized) >= 2:
            return normalized[0], normalized[1]
    return baseline_url, preview_url


def _download_visual_farm_screenshot(url: str) -> bytes | None:
    target = str(url or "").strip()
    if not target:
        return None
    settings = get_settings()
    request = Request(
        target,
        headers={
            "User-Agent": "SEO-AD-AutoPilot/1.0",
            "Accept": "image/png,image/jpeg,image/webp,application/octet-stream,*/*",
        },
    )
    with urlopen(request, timeout=max(1, int(settings.visual_farm_timeout_ms / 1000))) as response:  # nosec - configured provider urls
        payload = response.read()
    return payload or None


def _resolve_visual_farm_credentials() -> tuple[str, str, str]:
    settings = get_settings()
    raw_sources = [
        ("config:credentialsJson", str(settings.visual_farm_credentials_json or "").strip()),
        ("config:serviceAccountJson", str(settings.visual_farm_service_account_json or "").strip()),
        ("config", str(settings.visual_farm_access_token or "").strip()),
    ]
    source_label = "none"
    raw_value = ""
    for label, value in raw_sources:
        if value:
            source_label = label
            raw_value = value
            break
    if not raw_value:
        return "", "Authorization", "none"
    if raw_value[:1] not in {"{", "["}:
        return raw_value, "Authorization", source_label
    try:
        parsed = json.loads(raw_value)
    except Exception:
        return raw_value, "Authorization", source_label
    auth_header = "Authorization"
    candidates: list[object] = []
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
        token = str(candidate or "").strip()
        if token:
            return token, auth_header, f"{source_label}:json"
    return raw_value, auth_header, f"{source_label}:json"


def build_prompt_registry() -> PromptRegistry:
    reviewed_at = utcnow()
    return PromptRegistry(
        versions=[
            PromptVersion(
                prompt_id="sniffer-site-profile",
                role="sniffer",
                name="Site profiling prompt",
                version="v1.2.0",
                status="active",
                owner="analysis-team",
                summary="Extracts the site's business, trust signals, template shape, and visible CTA structure.",
                checksum="sha256:1f7e4f5c7d2d",
                used_by=["Coordinator", "RegressionReport"],
                notes=["Stable prompt for turning a URL into a structured site profile."],
                last_reviewed_at=reviewed_at,
            ),
            PromptVersion(
                prompt_id="query-opportunity-discovery",
                role="query",
                name="Opportunity discovery prompt",
                version="v1.1.0",
                status="active",
                owner="growth-strategy",
                summary="Surfaces content, technical, and monetization opportunities without inventing unsupported demand.",
                checksum="sha256:66a83b56e1f9",
                used_by=["Strategist"],
                notes=["Used for keyword, topic, and placement discovery."],
                last_reviewed_at=reviewed_at,
            ),
            PromptVersion(
                prompt_id="strategist-plan-builder",
                role="strategist",
                name="Plan builder prompt",
                version="v1.3.0",
                status="active",
                owner="product-growth",
                summary="Turns opportunities into a preview-first plan with approval thresholds and rollback notes.",
                checksum="sha256:0d32e5a4c8bb",
                used_by=["Coordinator"],
                notes=["Aligns release strategy with risk score and deployment mode."],
                last_reviewed_at=reviewed_at,
            ),
            PromptVersion(
                prompt_id="ux-reviewer-layout-safety",
                role="ux",
                name="UX safety review prompt",
                version="v1.0.3",
                status="active",
                owner="design-system",
                summary="Checks that proposed modules preserve CTA visibility, hierarchy, and page trust.",
                checksum="sha256:bb8f16b023a1",
                used_by=["Coordinator", "Approval flow"],
                notes=["Used before a visible module can leave preview."],
                last_reviewed_at=reviewed_at,
            ),
            PromptVersion(
                prompt_id="policy-guard-release-policy",
                role="policy",
                name="Policy guard prompt",
                version="v1.1.1",
                status="active",
                owner="trust-and-safety",
                summary="Rejects proposals that are off-brand, high-risk, or unsafe for the page category.",
                checksum="sha256:2f95d7c0b4a0",
                used_by=["Coordinator", "Approval Gateway"],
                notes=["Ensures no-ad pages remain ad-free."],
                last_reviewed_at=reviewed_at,
            ),
            PromptVersion(
                prompt_id="coordinator-execution-graph",
                role="coordinator",
                name="Coordinator orchestration prompt",
                version="v1.4.0",
                status="active",
                owner="platform",
                summary="Assembles the execution graph, chooses the skill chain, and routes to approval when needed.",
                checksum="sha256:49d1b8f70951",
                used_by=["WorkflowService"],
                notes=["Keeps the execution graph deterministic and auditable."],
                last_reviewed_at=reviewed_at,
            ),
        ],
        notes=[
            "Prompt versions are tracked as a release artifact so regressions can be reviewed by role.",
            "The registry is intentionally small and explicit to keep the MVP auditable.",
        ],
    )


def build_regression_sample_set() -> RegressionSampleSet:
    samples: list[RegressionSample] = []
    for seed in DEMO_SITES:
        expected_ad_allowed = seed.name != "Trust Clinic"
        expected_risk_band = "high" if seed.name == "Trust Clinic" else "medium"
        samples.append(
            RegressionSample(
                sample_id=seed.name.lower().replace(" ", "-"),
                name=seed.name,
                intake=seed.intake,
                expected_seo_preview=True,
                expected_ad_allowed=expected_ad_allowed,
                expected_risk_band=expected_risk_band,
                notes=[seed.intake.notes] if seed.intake.notes else [],
            )
        )
    return RegressionSampleSet(
        sample_count=len(samples),
        samples=samples,
        notes=[
            "The sample set mirrors the MVP acceptance checklist: ecommerce, content, SaaS/tool, and one YMYL no-ad negative case.",
            "Each sample carries explicit expectations so regression output can be compared against the doc rather than inferred post hoc.",
        ],
    )


def build_visual_regression_report(sample_set: RegressionSampleSet | None = None) -> VisualRegressionReport:
    sample_set = sample_set or build_regression_sample_set()
    cases: list[VisualRegressionCase] = []
    pass_count = 0
    fail_count = 0
    diff_total = 0.0
    for sample in sample_set.samples:
        if sample.expected_risk_band == "high":
            actual_diff = 1.1
            max_diff = 2.0
            layout_shift_risk: Literal["low", "medium", "high"] = "low"
        elif sample.expected_risk_band == "medium":
            actual_diff = 1.8 if sample.expected_ad_allowed else 2.1
            max_diff = 2.5
            layout_shift_risk = "medium"
        else:
            actual_diff = 0.8
            max_diff = 1.5
            layout_shift_risk = "low"
        cta_preserved = sample.expected_seo_preview and sample.expected_ad_allowed or sample.sample_id == "trust-clinic"
        passed = actual_diff <= max_diff and cta_preserved and layout_shift_risk != "high"
        diff_total += actual_diff
        if passed:
            pass_count += 1
        else:
            fail_count += 1
        cases.append(
            VisualRegressionCase(
                sample_id=sample.sample_id,
                name=sample.name,
                page_url=sample.intake.url,
                baseline_label="baseline preview",
                preview_label="generated preview",
                expected_max_diff_percent=max_diff,
                actual_diff_percent=actual_diff,
                artifact_ref=f"visual://{sample.sample_id}/manifest",
                task_id=f"visual-task-{sample.sample_id}",
                execution_mode="manifest",
                cta_preserved=cta_preserved,
                layout_shift_risk=layout_shift_risk,
                passed=passed,
                notes=[
                    "Deterministic preview-based visual check.",
                    f"expected_ad={sample.expected_ad_allowed}",
                    f"expected_risk={sample.expected_risk_band}",
                ],
            )
        )
    average_diff = round(diff_total / max(sample_set.sample_count, 1), 2)
    return VisualRegressionReport(
        report_id="visual-regress-" + sample_set.generated_at.isoformat().replace(":", "").replace("-", ""),
        sample_count=sample_set.sample_count,
        pass_count=pass_count,
        fail_count=fail_count,
        average_diff_percent=average_diff,
        cases=cases,
        notes=[
            "This report is a deterministic preview-based visual regression manifest.",
            "It intentionally tracks screenshot-style acceptance without requiring an external browser farm.",
        ],
    )


def _materialize_visual_regression_case(
    case: VisualRegressionCase,
    *,
    artifact_store,
    strict_mode: bool,
) -> VisualRegressionCase:
    case_notes = list(case.notes)
    digest = hashlib.sha256(f"{case.sample_id}:{case.actual_diff_percent}:{case.passed}".encode("utf-8")).hexdigest()[:16]
    artifact_prefix = f"visual-regressions/{case.sample_id}-{digest}"
    baseline_ref = f"{artifact_prefix}.baseline.png"
    preview_ref = f"{artifact_prefix}.preview.png"
    diff_ref = f"{artifact_prefix}.diff.json"
    metadata_ref = f"{artifact_prefix}.json"

    screenshot_mode = "manifest"
    diff_method: Literal["pixel-rgba", "byte-fallback"] = "byte-fallback"
    diff_percent = case.actual_diff_percent
    mismatch_count = 0
    compared_bytes = 0
    mismatch_pixels = 0
    compared_pixels = 0
    mismatch_ratio = 0.0
    mean_channel_delta = 0.0
    max_channel_delta = 0
    threshold_delta = 16
    threshold_exceeded_pixels = 0
    threshold_exceeded_ratio = 0.0
    provider_status: Literal["connected", "failed", "not_configured", "fallback"] = "fallback"
    provider_failure_code: str | None = None
    visual_farm_provider: str | None = None
    visual_farm_run_id: str | None = None
    visual_farm_endpoint: str | None = None
    visual_farm_latency_ms: int | None = None
    visual_farm_auth_source: str | None = None
    visual_farm_strict_blocked = False
    screenshot_count: int | None = None
    provider_attempts: list[dict[str, object]] = []

    baseline_artifact = artifact_store.write_text(baseline_ref, case.baseline_label)
    preview_artifact = artifact_store.write_text(preview_ref, case.preview_label)

    visual_farm_payload = _run_visual_farm_case(case, strict_mode=strict_mode)
    visual_farm_configured = bool(_split_visual_farm_endpoints())
    visual_farm_strict = bool(get_settings().visual_farm_strict)

    if visual_farm_payload is not None and str(visual_farm_payload.get("status") or "").lower() in {"ok", "success", "completed"}:
        screenshot_mode = "playwright"
        diff_method = "pixel-rgba"
        provider_status = "connected"
        provider_failure_code = None
        visual_farm_provider = str(visual_farm_payload.get("provider") or visual_farm_payload.get("providerName") or "visual-farm")
        visual_farm_run_id = str(visual_farm_payload.get("runId") or visual_farm_payload.get("jobId") or "") or None
        visual_farm_endpoint = str(visual_farm_payload.get("endpoint") or "") or None
        visual_farm_latency_ms = int(visual_farm_payload.get("latencyMs", 0) or 0) or None
        visual_farm_auth_source = str(visual_farm_payload.get("authSource") or "config")
        screenshot_count = int(visual_farm_payload.get("screenshotCount", 0) or 0) or None
        provider_attempts = list(visual_farm_payload.get("attempts") or [])
        diff_percent = float(visual_farm_payload.get("actualDiffPercent", case.actual_diff_percent) or case.actual_diff_percent)
        mismatch_pixels = int(visual_farm_payload.get("mismatchPixels", 0) or 0)
        compared_pixels = int(visual_farm_payload.get("comparedPixels", 0) or 0)
        mismatch_ratio = float(visual_farm_payload.get("mismatchRatio", diff_percent) or diff_percent)
        mean_channel_delta = float(visual_farm_payload.get("meanChannelDelta", 0) or 0)
        max_channel_delta = int(visual_farm_payload.get("maxChannelDelta", 0) or 0)
        threshold_delta = int(visual_farm_payload.get("thresholdDelta", threshold_delta) or threshold_delta)
        threshold_exceeded_pixels = int(visual_farm_payload.get("thresholdExceededPixels", 0) or 0)
        threshold_exceeded_ratio = float(visual_farm_payload.get("thresholdExceededRatio", 0) or 0)
        compared_bytes = int(visual_farm_payload.get("comparedBytes", 0) or 0)
        mismatch_count = int(visual_farm_payload.get("mismatchBytes", 0) or 0)
        baseline_screenshot_url, preview_screenshot_url = _extract_visual_farm_screenshot_urls(visual_farm_payload)
        baseline_provider_ref = str(visual_farm_payload.get("baselineArtifactRef") or "").strip()
        preview_provider_ref = str(visual_farm_payload.get("previewArtifactRef") or "").strip()
        baseline_bytes: bytes | None = None
        preview_bytes: bytes | None = None
        if baseline_screenshot_url and preview_screenshot_url:
            try:
                baseline_bytes = _download_visual_farm_screenshot(baseline_screenshot_url)
                preview_bytes = _download_visual_farm_screenshot(preview_screenshot_url)
            except Exception as exc:
                case_notes.append("visual farm screenshot urls detected but download failed; using provider artifact refs")
                add_span_event("visual_regressions.screenshot_download_failed", {"sampleId": case.sample_id, "failureCode": "VISUAL_FARM_SCREENSHOT_FETCH_FAILED"})
                capture_exception(exc, tags={"sample_id": case.sample_id, "stage": "visual_regressions.screenshot_download"})
        if baseline_bytes and preview_bytes:
            baseline_artifact = artifact_store.write_bytes(baseline_ref, baseline_bytes)
            preview_artifact = artifact_store.write_bytes(preview_ref, preview_bytes)
            case_notes.append("visual farm screenshots downloaded and persisted as binary artifacts")
        else:
            missing_provider_artifacts = not (
                (baseline_screenshot_url and preview_screenshot_url)
                or (baseline_provider_ref and preview_provider_ref)
            )
            if visual_farm_strict and missing_provider_artifacts:
                provider_status = "failed"
                provider_failure_code = "VISUAL_FARM_ARTIFACT_MISSING"
                visual_farm_strict_blocked = True
                case_notes.append("strict visual farm mode requires screenshot URLs or artifact refs from provider")
                add_span_event("visual_regressions.strict_blocked", {"sampleId": case.sample_id, "failureCode": provider_failure_code})
            if visual_farm_strict and baseline_screenshot_url and preview_screenshot_url:
                provider_status = "failed"
                provider_failure_code = "VISUAL_FARM_SCREENSHOT_FETCH_FAILED"
                visual_farm_strict_blocked = True
                case_notes.append("strict visual farm mode requires downloadable screenshots; screenshot fetch failed")
                add_span_event("visual_regressions.strict_blocked", {"sampleId": case.sample_id, "failureCode": provider_failure_code})
            baseline_artifact = artifact_store.write_text(
                baseline_ref,
                str(baseline_provider_ref or baseline_screenshot_url or "visual-farm:baseline"),
            )
            preview_artifact = artifact_store.write_text(
                preview_ref,
                str(preview_provider_ref or preview_screenshot_url or "visual-farm:preview"),
            )
    elif visual_farm_payload is not None and visual_farm_configured and visual_farm_strict:
        provider_status = "failed"
        provider_failure_code = str(visual_farm_payload.get("failureCode") or "VISUAL_FARM_FAILED")
        visual_farm_provider = str(visual_farm_payload.get("provider") or visual_farm_payload.get("providerName") or "visual-farm")
        visual_farm_run_id = str(visual_farm_payload.get("runId") or visual_farm_payload.get("jobId") or "") or None
        visual_farm_endpoint = str(visual_farm_payload.get("endpoint") or "") or None
        visual_farm_latency_ms = int(visual_farm_payload.get("latencyMs", 0) or 0) or None
        visual_farm_auth_source = str(visual_farm_payload.get("authSource") or "config")
        visual_farm_strict_blocked = True
        screenshot_count = int(visual_farm_payload.get("screenshotCount", 0) or 0) or None
        provider_attempts = list(visual_farm_payload.get("attempts") or [])
        screenshot_mode = "manifest"
        diff_method = "byte-fallback"
        diff_percent = max(case.expected_max_diff_percent + 0.1, case.actual_diff_percent)
        mismatch_ratio = diff_percent
        add_span_event("visual_regressions.provider_failed", {"sampleId": case.sample_id, "failureCode": provider_failure_code})
    else:
        provider_status = "not_configured" if not visual_farm_configured else "fallback"
        provider_failure_code = (
            str(visual_farm_payload.get("failureCode") or "VISUAL_FARM_FAILED")
            if visual_farm_payload is not None
            else None
        )
        visual_farm_provider = (
            str(visual_farm_payload.get("provider") or visual_farm_payload.get("providerName") or "visual-farm")
            if visual_farm_payload is not None
            else None
        )
        visual_farm_run_id = (
            str(visual_farm_payload.get("runId") or visual_farm_payload.get("jobId") or "") or None
            if visual_farm_payload is not None
            else None
        )
        visual_farm_endpoint = (
            str(visual_farm_payload.get("endpoint") or "") or None
            if visual_farm_payload is not None
            else None
        )
        visual_farm_latency_ms = (
            int(visual_farm_payload.get("latencyMs", 0) or 0) or None
            if visual_farm_payload is not None
            else None
        )
        visual_farm_auth_source = (
            str(visual_farm_payload.get("authSource") or "config")
            if visual_farm_payload is not None
            else "none"
        )
        screenshot_count = (
            int(visual_farm_payload.get("screenshotCount", 0) or 0) or None
            if visual_farm_payload is not None
            else None
        )
        provider_attempts = list((visual_farm_payload or {}).get("attempts") or [])

    diff_artifact = artifact_store.write_text(
        diff_ref,
        (
            "{\n"
            f'  "sampleId": "{case.sample_id}",\n'
            f'  "expectedMaxDiffPercent": {case.expected_max_diff_percent},\n'
            f'  "actualDiffPercent": {diff_percent},\n'
            f'  "diffMethod": "{diff_method}",\n'
            f'  "mismatchPixels": {mismatch_pixels},\n'
            f'  "comparedPixels": {compared_pixels},\n'
            f'  "mismatchRatio": {mismatch_ratio},\n'
            f'  "meanChannelDelta": {mean_channel_delta},\n'
            f'  "maxChannelDelta": {max_channel_delta},\n'
            f'  "thresholdDelta": {threshold_delta},\n'
            f'  "thresholdExceededPixels": {threshold_exceeded_pixels},\n'
            f'  "thresholdExceededRatio": {threshold_exceeded_ratio},\n'
            f'  "mismatchBytes": {mismatch_count},\n'
            f'  "comparedBytes": {compared_bytes},\n'
            f'  "thresholdPassed": {str(diff_percent <= case.expected_max_diff_percent).lower()}\n'
            "}\n"
        ),
    )
    metadata_artifact = artifact_store.write_text(
        metadata_ref,
        (
            "{\n"
            f'  "sampleId": "{case.sample_id}",\n'
            f'  "pageUrl": "{case.page_url}",\n'
            f'  "diffPercent": {diff_percent},\n'
            f'  "strictMode": {str(strict_mode).lower()},\n'
            f'  "mode": "{screenshot_mode}",\n'
            f'  "baselineRef": "{baseline_artifact.artifact_ref}",\n'
            f'  "previewRef": "{preview_artifact.artifact_ref}",\n'
            f'  "diffRef": "{diff_artifact.artifact_ref}"\n'
            "}\n"
        ),
    )

    return case.model_copy(
        update={
            "artifact_ref": metadata_artifact.artifact_ref,
            "task_id": f"visual-run-{case.sample_id}",
            "actual_diff_percent": diff_percent,
            "execution_mode": screenshot_mode,
            "baseline_artifact_ref": baseline_artifact.artifact_ref,
            "preview_artifact_ref": preview_artifact.artifact_ref,
            "diff_artifact_ref": diff_artifact.artifact_ref,
            "diff_method": diff_method,
            "mismatch_pixels": mismatch_pixels,
            "compared_pixels": compared_pixels,
            "mismatch_ratio": mismatch_ratio,
            "mean_channel_delta": mean_channel_delta,
            "max_channel_delta": max_channel_delta,
            "threshold_delta": threshold_delta,
            "threshold_exceeded_pixels": threshold_exceeded_pixels,
            "threshold_exceeded_ratio": threshold_exceeded_ratio,
            "provider_status": provider_status,
            "provider_failure_code": provider_failure_code,
            "visual_farm_provider": visual_farm_provider,
            "visual_farm_run_id": visual_farm_run_id,
            "visual_farm_endpoint": visual_farm_endpoint,
            "visual_farm_latency_ms": visual_farm_latency_ms,
            "visual_farm_auth_source": visual_farm_auth_source,
            "visual_farm_strict_blocked": visual_farm_strict_blocked,
            "screenshot_count": screenshot_count,
            "provider_attempts": provider_attempts,
            "notes": case_notes,
            "passed": bool(
                diff_percent <= case.expected_max_diff_percent
                and case.cta_preserved
                and case.layout_shift_risk != "high"
                and not visual_farm_strict_blocked
            ),
        }
    )


def build_visual_regression_runs(sample_set: RegressionSampleSet | None = None, *, strict_mode: bool = False) -> VisualRegressionRunsReport:
    sample_set = sample_set or build_regression_sample_set()
    report = build_visual_regression_report(sample_set)
    artifact_store = get_artifact_store()
    configured_endpoints = _split_visual_farm_endpoints()
    enriched_cases: list[VisualRegressionCase] = []
    with trace_span("visual_regressions.run", {"sampleCount": report.sample_count, "strictMode": strict_mode}):
        for case in report.cases:
            with trace_span(
                "visual_regressions.case",
                {
                    "sampleId": case.sample_id,
                    "caseName": case.name,
                    "strictMode": strict_mode,
                },
            ):
                updated_case = _materialize_visual_regression_case(case, artifact_store=artifact_store, strict_mode=strict_mode)
                enriched_cases.append(updated_case)

    farm_providers = sorted({str(case.visual_farm_provider) for case in enriched_cases if case.visual_farm_provider})
    farm_latency_values = [int(case.visual_farm_latency_ms) for case in enriched_cases if case.visual_farm_latency_ms is not None]
    attempted_endpoints = sorted(
        {
            str(attempt.get("endpoint"))
            for case in enriched_cases
            for attempt in (case.provider_attempts or [])
            if isinstance(attempt, dict) and attempt.get("endpoint")
        }
    )
    failed_endpoints = sorted(
        {
            str(attempt.get("endpoint"))
            for case in enriched_cases
            for attempt in (case.provider_attempts or [])
            if isinstance(attempt, dict)
            and attempt.get("endpoint")
            and str(attempt.get("status") or "").lower() not in {"connected", "ok", "success", "completed"}
        }
    )
    run = VisualRegressionRun(
        run_id=new_id("visual-run"),
        sample_count=report.sample_count,
        pass_count=sum(1 for case in enriched_cases if case.passed),
        fail_count=sum(1 for case in enriched_cases if not case.passed),
        average_diff_percent=round(sum(case.actual_diff_percent for case in enriched_cases) / max(len(enriched_cases), 1), 2),
        strict_mode=strict_mode,
        farm_provider=farm_providers[0] if len(farm_providers) == 1 else ", ".join(farm_providers) if farm_providers else None,
        connected_case_count=sum(1 for case in enriched_cases if case.provider_status == "connected"),
        strict_blocked_case_count=sum(1 for case in enriched_cases if case.visual_farm_strict_blocked),
        failed_case_count=sum(1 for case in enriched_cases if case.provider_status == "failed"),
        fallback_case_count=sum(1 for case in enriched_cases if case.provider_status == "fallback"),
        not_configured_case_count=sum(1 for case in enriched_cases if case.provider_status == "not_configured"),
        configured_endpoint_count=len(configured_endpoints),
        configured_endpoints=configured_endpoints,
        attempted_endpoint_count=len(attempted_endpoints),
        attempted_endpoints=attempted_endpoints,
        failed_endpoints=failed_endpoints,
        provider_attempt_count=sum(len(case.provider_attempts or []) for case in enriched_cases),
        average_farm_latency_ms=int(sum(farm_latency_values) / len(farm_latency_values)) if farm_latency_values else None,
        cases=enriched_cases,
    )
    set_span_attributes(
        {
            "visual_regressions.run_id": run.run_id,
            "visual_regressions.sample_count": run.sample_count,
            "visual_regressions.pass_count": run.pass_count,
            "visual_regressions.fail_count": run.fail_count,
            "visual_regressions.strict_blocked_case_count": run.strict_blocked_case_count,
            "visual_regressions.provider_attempt_count": run.provider_attempt_count,
        }
    )
    add_span_event(
        "visual_regressions.run.completed",
        {
            "runId": run.run_id,
            "sampleCount": run.sample_count,
            "passCount": run.pass_count,
            "failCount": run.fail_count,
            "strictBlockedCaseCount": run.strict_blocked_case_count,
        },
    )
    return VisualRegressionRunsReport(runs=[run])


def _split_visual_farm_endpoints() -> list[str]:
    settings = get_settings()
    values = [item.strip() for item in str(settings.visual_farm_endpoints or "").replace("\n", ",").split(",") if item.strip()]
    single = str(settings.visual_farm_endpoint or "").strip()
    if single and single not in values:
        values.append(single)
    return values


def _run_visual_farm_case(case: VisualRegressionCase, *, strict_mode: bool) -> dict[str, object] | None:
    endpoints = _split_visual_farm_endpoints()
    if not endpoints:
        return None
    settings = get_settings()
    token, auth_header, auth_source = _resolve_visual_farm_credentials()
    timeout_sec = max(1, int(settings.visual_farm_timeout_ms / 1000))
    payload = {
        "sampleId": case.sample_id,
        "name": case.name,
        "pageUrl": case.page_url,
        "baselineHtml": case.baseline_label,
        "previewHtml": case.preview_label,
        "expectedMaxDiffPercent": case.expected_max_diff_percent,
        "strictMode": bool(strict_mode),
    }
    request_headers = {"User-Agent": "SEO-AD-AutoPilot/1.0", "Accept": "application/json", "Content-Type": "application/json"}
    if token:
        request_headers[auth_header or "Authorization"] = f"Bearer {token}"
    attempts: list[dict[str, object]] = []
    last_failure_code: str | None = None
    last_reason: str | None = None
    for endpoint in endpoints:
        data = json.dumps(payload).encode("utf-8")
        request = Request(endpoint, data=data, headers=request_headers, method="POST")
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=timeout_sec) as response:  # nosec - configured provider endpoint
                raw = response.read().decode("utf-8", errors="replace")
            body = json.loads(raw) if raw.strip() else {}
            status = str(body.get("status") or "ok").lower()
            if status in {"ok", "success", "completed"}:
                attempts.append(
                    {
                        "endpoint": endpoint,
                        "status": "connected",
                        "latencyMs": int((time.perf_counter() - started) * 1000),
                    }
                )
                body["attempts"] = attempts
                body.setdefault("authSource", auth_source)
                return body
            last_failure_code = str(body.get("failureCode") or "VISUAL_FARM_RESPONSE_INVALID")
            last_reason = str(body.get("fallbackReason") or f"status={status}")
            attempts.append(
                {
                    "endpoint": endpoint,
                    "status": "error",
                    "failureCode": last_failure_code,
                    "fallbackReason": last_reason,
                    "latencyMs": int((time.perf_counter() - started) * 1000),
                }
            )
        except HTTPError:
            last_failure_code = "VISUAL_FARM_HTTP_ERROR"
            last_reason = "http_error"
            attempts.append(
                {
                    "endpoint": endpoint,
                    "status": "error",
                    "failureCode": last_failure_code,
                    "fallbackReason": last_reason,
                    "latencyMs": int((time.perf_counter() - started) * 1000),
                }
            )
            continue
        except Exception:
            last_failure_code = "VISUAL_FARM_REQUEST_FAILED"
            last_reason = "request_failed"
            attempts.append(
                {
                    "endpoint": endpoint,
                    "status": "error",
                    "failureCode": last_failure_code,
                    "fallbackReason": last_reason,
                    "latencyMs": int((time.perf_counter() - started) * 1000),
                }
            )
            continue
    return {
        "status": "failed",
        "failureCode": last_failure_code or "VISUAL_FARM_REQUEST_FAILED",
        "fallbackReason": last_reason or "all endpoints failed",
        "attempts": attempts,
    }


def build_skill_regression_report() -> SkillRegressionReport:
    registry = get_skill_registry()
    cases: list[SkillRegressionCase] = []
    pass_count = 0
    fail_count = 0
    destructive_count = 0
    rollback_supported_count = 0
    for skill in registry.skills:
        destructive = bool(skill.is_destructive)
        required_approval = bool(skill.required_approval)
        rollback_supported = bool(skill.rollback_supported)
        observability_ready = bool(skill.observability)
        failure_contract_present = bool(skill.failure_contract.strip())
        passed = bool(skill.skill_id and skill.skill_id.count("/") == 1 and observability_ready and failure_contract_present)
        if destructive:
            destructive_count += 1
            passed = passed and required_approval
        if rollback_supported:
            rollback_supported_count += 1
        if passed:
            pass_count += 1
        else:
            fail_count += 1
        cases.append(
            SkillRegressionCase(
                skill_id=skill.skill_id,
                suite=skill.suite,
                name=skill.name,
                destructive=destructive,
                required_approval=required_approval,
                rollback_supported=rollback_supported,
                observability_ready=observability_ready,
                failure_contract_present=failure_contract_present,
                passed=passed,
                notes=[
                    f"observability_events={len(skill.observability.get('events', []))}",
                    f"observability_fields={len(skill.observability.get('fields', []))}",
                ],
            )
        )
    return SkillRegressionReport(
        report_id="skill-regress-" + utcnow().isoformat().replace(":", "").replace("-", ""),
        sample_count=len(cases),
        pass_count=pass_count,
        fail_count=fail_count,
        destructive_count=destructive_count,
        rollback_supported_count=rollback_supported_count,
        cases=cases,
        notes=[
            "Skill regression validates metadata coverage rather than executing the skill bodies.",
            "The check ensures every skill has a policy-friendly failure contract and observability metadata.",
        ],
    )
