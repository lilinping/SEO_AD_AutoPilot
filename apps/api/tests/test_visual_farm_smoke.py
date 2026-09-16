import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

from apps.visual_farm.main import VisualFarmSettings
from apps.visual_farm.smoke import run_visual_farm_smoke


def _png(red: int, green: int, blue: int) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        checksum = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"\x00" + bytes([red, green, blue])))
        + chunk(b"IEND", b"")
    )


class VisualFarmSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.artifact_dir = Path(self.tempdir.name) / "artifacts"
        self.report_path = Path(self.tempdir.name) / "reports" / "visual-smoke.json"
        self.settings = VisualFarmSettings(
            SEO_AD_BOT_VISUAL_FARM_ARTIFACT_DIR=self.artifact_dir,
            SEO_AD_BOT_VISUAL_FARM_ALLOWED_HOSTS="baseline.example,preview.example",
        )

    def run_smoke(self, *, max_diff: float = 0.0) -> dict[str, object]:
        return run_visual_farm_smoke(
            self.settings,
            baseline_url="https://baseline.example/page",
            preview_url="https://preview.example/page",
            expected_max_diff_percent=max_diff,
            report_path=self.report_path,
        )

    @patch("apps.visual_farm.smoke._probe_browser_runtime")
    @patch("apps.visual_farm.smoke._capture_pair")
    def test_success_writes_validated_artifacts_and_report(self, capture_pair, probe_browser) -> None:
        probe_browser.return_value = {"status": "ready", "chromiumReady": True}
        capture_pair.return_value = (_png(255, 255, 255), _png(255, 255, 255))

        report = self.run_smoke()

        self.assertEqual(report["status"], "success")
        self.assertEqual(report["actualDiffPercent"], 0.0)
        self.assertTrue(Path(str(report["baselineArtifactPath"])).is_file())
        self.assertTrue(Path(str(report["previewArtifactPath"])).is_file())
        persisted = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["runId"], report["runId"])
        self.assertEqual(persisted["stage"], "completed")

    @patch("apps.visual_farm.smoke._probe_browser_runtime")
    @patch("apps.visual_farm.smoke._capture_pair")
    def test_diff_threshold_failure_keeps_artifacts_and_blocks_acceptance(self, capture_pair, probe_browser) -> None:
        probe_browser.return_value = {"status": "ready", "chromiumReady": True}
        capture_pair.return_value = (_png(255, 255, 255), _png(0, 0, 0))

        report = self.run_smoke(max_diff=5.0)

        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["failureCode"], "VISUAL_FARM_DIFF_THRESHOLD_EXCEEDED")
        self.assertEqual(report["actualDiffPercent"], 100.0)
        self.assertTrue(Path(str(report["baselineArtifactPath"])).is_file())

    def test_missing_targets_fail_before_browser_launch(self) -> None:
        with patch("apps.visual_farm.smoke._probe_browser_runtime") as probe_browser:
            report = run_visual_farm_smoke(
                self.settings,
                baseline_url="",
                preview_url="",
                expected_max_diff_percent=0,
                report_path=self.report_path,
            )

        self.assertEqual(report["failureCode"], "VISUAL_FARM_SMOKE_TARGETS_MISSING")
        self.assertEqual(report["stage"], "configuration")
        probe_browser.assert_not_called()

    @patch("apps.visual_farm.smoke._probe_browser_runtime", side_effect=RuntimeError("browser missing"))
    def test_missing_browser_is_a_retryable_readiness_failure(self, _probe_browser) -> None:
        report = self.run_smoke()

        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["failureCode"], "VISUAL_FARM_CHROMIUM_UNAVAILABLE")
        self.assertTrue(report["retryable"])
        self.assertEqual(json.loads(self.report_path.read_text(encoding="utf-8"))["message"], "browser missing")


if __name__ == "__main__":
    unittest.main()
