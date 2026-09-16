import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.visual_farm.main import VisualFarmSettings, create_app


def _png(red: int, green: int, blue: int) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"\x00" + bytes([red, green, blue]))) + chunk(b"IEND", b"")


class VisualFarmServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.settings = VisualFarmSettings(
            SEO_AD_BOT_VISUAL_FARM_API_KEY="test-visual-key",
            SEO_AD_BOT_VISUAL_FARM_ARTIFACT_DIR=Path(self.tempdir.name),
            SEO_AD_BOT_VISUAL_FARM_ALLOWED_HOSTS="owned.example",
            SEO_AD_BOT_VISUAL_FARM_PUBLIC_BASE_URL="http://visual-farm.test",
        )

    def test_health_is_public_but_comparison_and_artifacts_require_a_key(self) -> None:
        app = create_app(self.settings)
        with TestClient(app) as client:
            self.assertEqual(client.get("/").status_code, 200)
            self.assertEqual(client.get("/healthz").status_code, 200)
            self.assertEqual(client.get("/readyz").status_code, 401)
            self.assertEqual(
                client.post("/", json={"sampleId": "case", "name": "Case", "baselineUrl": "https://owned.example/old", "previewUrl": "https://owned.example/new"}).status_code,
                401,
            )

            headers = {"X-API-Key": "test-visual-key"}
            identical = client.post(
                "/",
                headers=headers,
                json={"sampleId": "case", "name": "Case", "baselineUrl": "https://owned.example/page", "previewUrl": "https://owned.example/page"},
            )
            self.assertEqual(identical.status_code, 422)
            self.assertEqual(identical.json()["detail"], "VISUAL_FARM_TARGETS_IDENTICAL")

            denied = client.post(
                "/",
                headers=headers,
                json={"sampleId": "case", "name": "Case", "baselineUrl": "https://unowned.example/old", "previewUrl": "https://owned.example/new"},
            )
            self.assertEqual(denied.status_code, 422)
            self.assertEqual(denied.json()["detail"], "VISUAL_FARM_TARGET_NOT_ALLOWED")

            with patch("apps.visual_farm.main._capture_pair", return_value=(_png(255, 255, 255), _png(0, 0, 0))):
                result = client.post(
                    "/",
                    headers=headers,
                    json={"sampleId": "case", "name": "Case", "baselineUrl": "https://owned.example/old", "previewUrl": "https://owned.example/new"},
                )
            self.assertEqual(result.status_code, 200)
            payload = result.json()
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["screenshotCount"], 2)
            self.assertEqual(payload["mismatchPixels"], 1)
            self.assertEqual(payload["actualDiffPercent"], 100.0)

            artifact_path = payload["baselineScreenshotUrl"].replace("http://visual-farm.test", "")
            self.assertEqual(client.get(artifact_path).status_code, 401)
            self.assertEqual(client.get(artifact_path, headers=headers).status_code, 200)

    def test_readiness_runs_chromium_smoke_and_caches_the_result(self) -> None:
        app = create_app(self.settings)
        headers = {"X-API-Key": "test-visual-key"}
        ready_payload = {
            "status": "ready",
            "provider": "seo-ad-visual-farm",
            "chromiumReady": True,
            "browserVersion": "Chromium test",
            "smokeUrl": "about:blank",
            "screenshotBytes": 128,
            "latencyMs": 12,
        }
        with TestClient(app) as client:
            with patch("apps.visual_farm.main._probe_browser_runtime", return_value=ready_payload) as probe:
                first = client.get("/readyz", headers=headers)
                second = client.get("/readyz", headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["chromiumReady"])
        self.assertEqual(second.status_code, 200)
        self.assertEqual(probe.call_count, 1)

    def test_readiness_returns_503_when_chromium_cannot_launch(self) -> None:
        app = create_app(self.settings)
        with TestClient(app) as client:
            with patch("apps.visual_farm.main._probe_browser_runtime", side_effect=RuntimeError("browser missing")):
                response = client.get("/readyz?force=true", headers={"X-API-Key": "test-visual-key"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["failureCode"], "VISUAL_FARM_CHROMIUM_UNAVAILABLE")
        self.assertFalse(response.json()["chromiumReady"])


if __name__ == "__main__":
    unittest.main()
