from __future__ import annotations

import secrets
import struct
import time
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse
import zlib

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings, SettingsConfigDict


class VisualFarmSettings(BaseSettings):
    """Runtime settings for the isolated browser process."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_key: str = Field(default="", alias="SEO_AD_BOT_VISUAL_FARM_API_KEY")
    artifact_dir: Path = Field(default=Path("var/visual-farm"), alias="SEO_AD_BOT_VISUAL_FARM_ARTIFACT_DIR")
    public_base_url: str = Field(default="", alias="SEO_AD_BOT_VISUAL_FARM_PUBLIC_BASE_URL")
    allowed_hosts: str = Field(default="", alias="SEO_AD_BOT_VISUAL_FARM_ALLOWED_HOSTS")
    timeout_ms: int = Field(default=30000, alias="SEO_AD_BOT_VISUAL_FARM_BROWSER_TIMEOUT_MS")
    readiness_cache_seconds: int = Field(default=30, alias="SEO_AD_BOT_VISUAL_FARM_READINESS_CACHE_SECONDS")
    smoke_url: str = Field(default="about:blank", alias="SEO_AD_BOT_VISUAL_FARM_SMOKE_URL")

    def host_is_allowed(self, target: str) -> bool:
        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        allowed = {value.strip().lower() for value in self.allowed_hosts.replace("\n", ",").split(",") if value.strip()}
        return parsed.hostname.lower() in allowed


class VisualComparisonRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    sample_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=300)
    page_url: str = ""
    baseline_url: str | None = None
    preview_url: str | None = None
    expected_max_diff_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    strict_mode: bool = False


def _presented_key(
    x_api_key: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def _require_api_key(
    settings: VisualFarmSettings,
    presented: Annotated[str | None, Depends(_presented_key)],
) -> None:
    if not settings.api_key or not presented or not secrets.compare_digest(settings.api_key, presented):
        raise HTTPException(status_code=401, detail="Visual farm API key is required")


def _validate_targets(payload: VisualComparisonRequest, settings: VisualFarmSettings) -> tuple[str, str]:
    baseline_url = str(payload.baseline_url or "").strip()
    preview_url = str(payload.preview_url or "").strip()
    if not baseline_url or not preview_url:
        raise HTTPException(status_code=422, detail="VISUAL_FARM_TARGETS_MISSING")
    if baseline_url == preview_url:
        raise HTTPException(status_code=422, detail="VISUAL_FARM_TARGETS_IDENTICAL")
    if not settings.host_is_allowed(baseline_url) or not settings.host_is_allowed(preview_url):
        raise HTTPException(status_code=422, detail="VISUAL_FARM_TARGET_NOT_ALLOWED")
    return baseline_url, preview_url


def _capture_pair(baseline_url: str, preview_url: str, settings: VisualFarmSettings) -> tuple[bytes, bytes]:
    from playwright.sync_api import sync_playwright

    timeout = max(1000, int(settings.timeout_ms))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 1024}, device_scale_factor=1)
            page.goto(baseline_url, wait_until="networkidle", timeout=timeout)
            baseline = page.screenshot(full_page=True, type="png")
            page.goto(preview_url, wait_until="networkidle", timeout=timeout)
            preview = page.screenshot(full_page=True, type="png")
            return baseline, preview
        finally:
            browser.close()


def _probe_browser_runtime(settings: VisualFarmSettings) -> dict[str, object]:
    from playwright.sync_api import sync_playwright

    smoke_url = str(settings.smoke_url or "about:blank").strip() or "about:blank"
    if smoke_url != "about:blank" and not settings.host_is_allowed(smoke_url):
        raise ValueError("VISUAL_FARM_SMOKE_TARGET_NOT_ALLOWED")
    timeout = max(1000, int(settings.timeout_ms))
    started = time.perf_counter()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 320, "height": 240}, device_scale_factor=1)
            page.goto(smoke_url, wait_until="load", timeout=timeout)
            screenshot = page.screenshot(type="png")
            if not screenshot.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("VISUAL_FARM_SMOKE_SCREENSHOT_INVALID")
            return {
                "status": "ready",
                "provider": "seo-ad-visual-farm",
                "chromiumReady": True,
                "browserVersion": browser.version,
                "smokeUrl": smoke_url,
                "screenshotBytes": len(screenshot),
                "latencyMs": int((time.perf_counter() - started) * 1000),
            }
        finally:
            browser.close()


def _decode_png(png: bytes) -> tuple[int, int, int, bytes]:
    """Decode the non-interlaced 8-bit RGB/RGBA PNGs emitted by Playwright."""
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Screenshot is not a PNG")
    offset = 8
    width = height = color_type = 0
    payload = bytearray()
    while offset + 12 <= len(png):
        length = struct.unpack(">I", png[offset : offset + 4])[0]
        chunk_type = png[offset + 4 : offset + 8]
        chunk = png[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", chunk)
            if bit_depth != 8 or color_type not in {2, 6} or compression != 0 or filter_method != 0 or interlace != 0:
                raise ValueError("Unsupported PNG format; expected non-interlaced 8-bit RGB/RGBA")
        elif chunk_type == b"IDAT":
            payload.extend(chunk)
        elif chunk_type == b"IEND":
            break
    if width <= 0 or height <= 0 or not payload:
        raise ValueError("PNG is missing image data")
    bytes_per_pixel = 4 if color_type == 6 else 3
    stride = width * bytes_per_pixel
    raw = zlib.decompress(bytes(payload))
    if len(raw) != (stride + 1) * height:
        raise ValueError("PNG scanline length is invalid")
    decoded = bytearray(height * stride)
    for row in range(height):
        source_offset = row * (stride + 1)
        filter_type = raw[source_offset]
        source = raw[source_offset + 1 : source_offset + 1 + stride]
        target_offset = row * stride
        for column, value in enumerate(source):
            left = decoded[target_offset + column - bytes_per_pixel] if column >= bytes_per_pixel else 0
            up = decoded[target_offset - stride + column] if row else 0
            upper_left = decoded[target_offset - stride + column - bytes_per_pixel] if row and column >= bytes_per_pixel else 0
            if filter_type == 0:
                decoded[target_offset + column] = value
            elif filter_type == 1:
                decoded[target_offset + column] = (value + left) & 0xFF
            elif filter_type == 2:
                decoded[target_offset + column] = (value + up) & 0xFF
            elif filter_type == 3:
                decoded[target_offset + column] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                pa = abs(up - upper_left)
                pb = abs(left - upper_left)
                pc = abs(left + up - 2 * upper_left)
                predictor = left if pa <= pb and pa <= pc else up if pb <= pc else upper_left
                decoded[target_offset + column] = (value + predictor) & 0xFF
            else:
                raise ValueError("PNG uses an unsupported filter")
    return width, height, bytes_per_pixel, bytes(decoded)


def _pixel_at(image: tuple[int, int, int, bytes], x: int, y: int) -> tuple[int, int, int, int]:
    width, height, bytes_per_pixel, data = image
    if x >= width or y >= height:
        return (255, 255, 255, 0)
    offset = (y * width + x) * bytes_per_pixel
    red, green, blue = data[offset : offset + 3]
    alpha = data[offset + 3] if bytes_per_pixel == 4 else 255
    return red, green, blue, alpha


def _compare_pngs(baseline: bytes, preview: bytes) -> dict[str, float | int]:
    baseline_image = _decode_png(baseline)
    preview_image = _decode_png(preview)
    width = max(baseline_image[0], preview_image[0])
    height = max(baseline_image[1], preview_image[1])
    threshold_delta = 16
    compared_pixels = 0
    mismatch_pixels = 0
    channel_delta_sum = 0
    max_channel_delta = 0
    for y in range(height):
        for x in range(width):
            baseline_pixel = _pixel_at(baseline_image, x, y)
            preview_pixel = _pixel_at(preview_image, x, y)
            channels = tuple(abs(left - right) for left, right in zip(baseline_pixel, preview_pixel))
            compared_pixels += 1
            max_delta = max(channels)
            mismatch_pixels += int(max_delta > threshold_delta)
            for channel in channels[:3]:
                channel_delta_sum += channel
                max_channel_delta = max(max_channel_delta, channel)
    mean_channel_delta = round(channel_delta_sum / max(1, compared_pixels * 3), 4)
    mismatch_ratio = round((mismatch_pixels / max(1, compared_pixels)) * 100, 4)
    return {
        "actualDiffPercent": mismatch_ratio,
        "mismatchPixels": mismatch_pixels,
        "comparedPixels": compared_pixels,
        "mismatchRatio": mismatch_ratio,
        "meanChannelDelta": mean_channel_delta,
        "maxChannelDelta": max_channel_delta,
        "thresholdDelta": threshold_delta,
        "thresholdExceededPixels": mismatch_pixels,
        "thresholdExceededRatio": mismatch_ratio,
    }


def create_app(settings: VisualFarmSettings | None = None) -> FastAPI:
    settings = settings or VisualFarmSettings()
    settings.artifact_dir.mkdir(parents=True, exist_ok=True)
    app = FastAPI(title="SEO-AD Visual Farm", version="1.0.0")
    readiness_cache: dict[str, object] = {"checkedAt": 0.0, "payload": None}

    def require_api_key(presented: Annotated[str | None, Depends(_presented_key)]) -> None:
        _require_api_key(settings, presented)

    def liveness_payload() -> dict[str, object]:
        return {
            "status": "ok",
            "provider": "seo-ad-visual-farm",
            "apiKeyConfigured": bool(settings.api_key),
            "readinessUrl": "/readyz",
        }

    @app.get("/")
    def health() -> dict[str, object]:
        return liveness_payload()

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return liveness_payload()

    @app.get("/readyz", dependencies=[Depends(require_api_key)])
    def readyz(force: bool = False) -> JSONResponse:
        now = time.monotonic()
        cached_payload = readiness_cache.get("payload")
        cache_seconds = max(0, int(settings.readiness_cache_seconds))
        if not force and isinstance(cached_payload, dict) and now - float(readiness_cache["checkedAt"]) < cache_seconds:
            return JSONResponse(status_code=200 if cached_payload.get("status") == "ready" else 503, content=cached_payload)
        try:
            payload = _probe_browser_runtime(settings)
        except Exception as exc:
            payload = {
                "status": "not_ready",
                "provider": "seo-ad-visual-farm",
                "chromiumReady": False,
                "failureCode": "VISUAL_FARM_CHROMIUM_UNAVAILABLE",
                "retryable": False,
                "message": str(exc),
            }
        readiness_cache.update({"checkedAt": now, "payload": payload})
        return JSONResponse(status_code=200 if payload.get("status") == "ready" else 503, content=payload)

    @app.post("/", dependencies=[Depends(require_api_key)])
    def compare(payload: VisualComparisonRequest, request: Request) -> dict[str, object]:
        baseline_url, preview_url = _validate_targets(payload, settings)
        started = time.perf_counter()
        try:
            baseline, preview = _capture_pair(baseline_url, preview_url, settings)
        except Exception as exc:
            return {
                "status": "failed",
                "provider": "seo-ad-visual-farm",
                "failureCode": "VISUAL_FARM_CAPTURE_FAILED",
                "fallbackReason": str(exc),
                "latencyMs": int((time.perf_counter() - started) * 1000),
            }

        run_id = f"visual-{secrets.token_urlsafe(12)}"
        baseline_name = f"{run_id}.baseline.png"
        preview_name = f"{run_id}.preview.png"
        (settings.artifact_dir / baseline_name).write_bytes(baseline)
        (settings.artifact_dir / preview_name).write_bytes(preview)
        comparison = _compare_pngs(baseline, preview)
        base_url = settings.public_base_url.rstrip("/") or str(request.base_url).rstrip("/")
        return {
            "status": "success",
            "provider": "seo-ad-visual-farm",
            "runId": run_id,
            "endpoint": base_url,
            "baselineScreenshotUrl": f"{base_url}/artifacts/{baseline_name}",
            "previewScreenshotUrl": f"{base_url}/artifacts/{preview_name}",
            "baselineArtifactRef": f"visual-farm://{baseline_name}",
            "previewArtifactRef": f"visual-farm://{preview_name}",
            "screenshotCount": 2,
            "latencyMs": int((time.perf_counter() - started) * 1000),
            **comparison,
        }

    @app.get("/artifacts/{artifact_name}", dependencies=[Depends(require_api_key)])
    def artifact(artifact_name: str) -> FileResponse:
        if Path(artifact_name).name != artifact_name or not artifact_name.endswith(".png"):
            raise HTTPException(status_code=404, detail="Artifact not found")
        artifact_path = settings.artifact_dir / artifact_name
        if not artifact_path.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found")
        return FileResponse(artifact_path, media_type="image/png")

    return app
