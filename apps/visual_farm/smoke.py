from __future__ import annotations

import argparse
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from apps.visual_farm.main import (
    VisualFarmSettings,
    _capture_pair,
    _compare_pngs,
    _decode_png,
    _probe_browser_runtime,
)


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def run_visual_farm_smoke(
    settings: VisualFarmSettings,
    *,
    baseline_url: str,
    preview_url: str,
    expected_max_diff_percent: float,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Run a deploy-time Chromium, screenshot, artifact, and diff acceptance check."""
    started = time.perf_counter()
    run_id = f"smoke-{secrets.token_urlsafe(10)}"
    run_dir = settings.artifact_dir / "smoke" / run_id
    report_path = report_path or run_dir / "report.json"
    report: dict[str, Any] = {
        "status": "failed",
        "provider": "seo-ad-visual-farm",
        "runId": run_id,
        "stage": "configuration",
        "baselineUrl": baseline_url,
        "previewUrl": preview_url,
        "expectedMaxDiffPercent": expected_max_diff_percent,
        "reportPath": str(report_path.resolve()),
    }

    try:
        if not baseline_url or not preview_url:
            raise ValueError("VISUAL_FARM_SMOKE_TARGETS_MISSING")
        if baseline_url == preview_url:
            raise ValueError("VISUAL_FARM_SMOKE_TARGETS_IDENTICAL")
        if not settings.host_is_allowed(baseline_url) or not settings.host_is_allowed(preview_url):
            raise ValueError("VISUAL_FARM_SMOKE_TARGET_NOT_ALLOWED")
        if not 0 <= expected_max_diff_percent <= 100:
            raise ValueError("VISUAL_FARM_SMOKE_DIFF_THRESHOLD_INVALID")

        report["stage"] = "readiness"
        readiness = _probe_browser_runtime(settings)
        report["readiness"] = readiness

        report["stage"] = "capture"
        baseline, preview = _capture_pair(baseline_url, preview_url, settings)

        report["stage"] = "artifact_validation"
        baseline_width, baseline_height, _, _ = _decode_png(baseline)
        preview_width, preview_height, _, _ = _decode_png(preview)
        run_dir.mkdir(parents=True, exist_ok=True)
        baseline_path = run_dir / "baseline.png"
        preview_path = run_dir / "preview.png"
        baseline_path.write_bytes(baseline)
        preview_path.write_bytes(preview)
        if baseline_path.read_bytes() != baseline or preview_path.read_bytes() != preview:
            raise RuntimeError("VISUAL_FARM_SMOKE_ARTIFACT_WRITE_INVALID")

        report["stage"] = "comparison"
        comparison = _compare_pngs(baseline, preview)
        actual_diff = float(comparison["actualDiffPercent"])
        report.update(
            {
                "baselineArtifactPath": str(baseline_path.resolve()),
                "previewArtifactPath": str(preview_path.resolve()),
                "baselineBytes": len(baseline),
                "previewBytes": len(preview),
                "baselineViewport": {"width": baseline_width, "height": baseline_height},
                "previewViewport": {"width": preview_width, "height": preview_height},
                **comparison,
            }
        )
        if actual_diff > expected_max_diff_percent:
            report.update(
                {
                    "failureCode": "VISUAL_FARM_DIFF_THRESHOLD_EXCEEDED",
                    "retryable": False,
                    "message": f"Actual diff {actual_diff}% exceeds {expected_max_diff_percent}%",
                }
            )
        else:
            report.update({"status": "success", "stage": "completed", "retryable": False})
    except Exception as exc:
        message = str(exc)
        stage = str(report.get("stage") or "configuration")
        failure_code = message if message.startswith("VISUAL_FARM_SMOKE_") else {
            "readiness": "VISUAL_FARM_CHROMIUM_UNAVAILABLE",
            "capture": "VISUAL_FARM_CAPTURE_FAILED",
            "artifact_validation": "VISUAL_FARM_ARTIFACT_INVALID",
            "comparison": "VISUAL_FARM_COMPARISON_FAILED",
        }.get(stage, "VISUAL_FARM_SMOKE_FAILED")
        report.update(
            {
                "failureCode": failure_code,
                "retryable": stage in {"readiness", "capture"},
                "message": message,
            }
        )
    finally:
        report["latencyMs"] = int((time.perf_counter() - started) * 1000)
        _write_report(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the production visual-farm screenshot acceptance check")
    parser.add_argument(
        "--baseline-url",
        default=os.getenv("SEO_AD_BOT_VISUAL_FARM_SMOKE_BASELINE_URL", ""),
        help="Deployed baseline URL (or SEO_AD_BOT_VISUAL_FARM_SMOKE_BASELINE_URL)",
    )
    parser.add_argument(
        "--preview-url",
        default=os.getenv("SEO_AD_BOT_VISUAL_FARM_SMOKE_PREVIEW_URL", ""),
        help="Preview URL (or SEO_AD_BOT_VISUAL_FARM_SMOKE_PREVIEW_URL)",
    )
    parser.add_argument(
        "--max-diff-percent",
        type=float,
        default=float(os.getenv("SEO_AD_BOT_VISUAL_FARM_SMOKE_MAX_DIFF_PERCENT", "0")),
        help="Maximum accepted pixel diff percentage",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path(os.environ["SEO_AD_BOT_VISUAL_FARM_SMOKE_REPORT_PATH"])
        if os.getenv("SEO_AD_BOT_VISUAL_FARM_SMOKE_REPORT_PATH")
        else None,
        help="Optional JSON report path",
    )
    args = parser.parse_args()
    report = run_visual_farm_smoke(
        VisualFarmSettings(),
        baseline_url=args.baseline_url.strip(),
        preview_url=args.preview_url.strip(),
        expected_max_diff_percent=args.max_diff_percent,
        report_path=args.report_path,
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
