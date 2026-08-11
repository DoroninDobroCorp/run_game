import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
BEATS_PATH = ROOT / "research/r02/mission_01_beats.v0.1.json"
ACTIVE_FIXTURE_DIR = ROOT / "research/r02/local/valparaiso_central"
AUDIO_DIR = ACTIVE_FIXTURE_DIR / "audio"
MASTER_M4A = AUDIO_DIR / "m01_solo_founder_30min.m4a"
MANIFEST_PATH = AUDIO_DIR / "m01_solo_founder_30min.manifest.json"

from tools import r02_audio_qa

class TestR02AudioQA(unittest.TestCase):

    def test_probe_condition_a_master_if_present(self):
        if not MASTER_M4A.exists() or not MANIFEST_PATH.exists():
            self.skipTest("Local Condition A master audio or manifest not present")

        report = r02_audio_qa.probe_audio(
            m4a_path=MASTER_M4A,
            manifest_path=MANIFEST_PATH
        )

        self.assertEqual(report["tool"], "r02_audio_qa")
        self.assertEqual(report["schema_version"], "0.1")
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["checks"]["sha256_matches_manifest"])
        self.assertTrue(report["checks"]["sha256_matches_expected_master"])
        self.assertTrue(report["checks"]["duration_exact_1800s"])
        self.assertTrue(report["checks"]["format_aac_44100_mono"])
        self.assertTrue(report["checks"]["container_integrity_valid"])
        self.assertTrue(report["checks"]["zero_truncation"])
        self.assertFalse(report["checks"]["clipping_detected"])
        self.assertTrue(report["checks"]["peak_volume_matches_expected"])
        self.assertTrue(report["checks"]["ffmpeg_signal_probe_passed"])
        self.assertEqual(report["signal_analysis"]["max_volume_db"], -1.6)
        self.assertEqual(report["signal_analysis"]["peak_volume_db"], -1.6)
        self.assertFalse(report["human_audio_approved"])
        self.assertFalse(report["human_listening_performed"])

    def test_ffmpeg_missing_returns_not_run(self):
        with patch("tools.r02_audio_qa.probe_signal_volumedetect", return_value={
            "probe_tool": "ffmpeg_volumedetect",
            "status": "NOT_RUN",
            "error": "ffmpeg executable not found in PATH",
            "max_volume_db": None,
            "peak_volume_db": None,
            "mean_volume_db": None,
            "histogram_0db_count": 0,
            "clipping_detected": False,
        }):
            report = r02_audio_qa.probe_audio(
                m4a_path=MASTER_M4A if MASTER_M4A.exists() else Path(__file__),
                manifest_path=MANIFEST_PATH if MANIFEST_PATH.exists() else None,
            )
            if MASTER_M4A.exists() and MANIFEST_PATH.exists():
                self.assertEqual(report["status"], "NOT_RUN")
                self.assertFalse(report["checks"]["ffmpeg_signal_probe_passed"])
                self.assertEqual(report["signal_analysis"]["status"], "NOT_RUN")
            self.assertFalse(report["human_audio_approved"])

    def test_ffmpeg_error_returns_fail(self):
        with patch("tools.r02_audio_qa.probe_signal_volumedetect", return_value={
            "probe_tool": "ffmpeg_volumedetect",
            "status": "FAIL",
            "error": "ffmpeg volumedetect failed",
            "max_volume_db": None,
            "peak_volume_db": None,
            "mean_volume_db": None,
            "histogram_0db_count": 0,
            "clipping_detected": False,
        }):
            report = r02_audio_qa.probe_audio(
                m4a_path=MASTER_M4A if MASTER_M4A.exists() else Path(__file__),
                manifest_path=MANIFEST_PATH if MANIFEST_PATH.exists() else None,
            )
            if MASTER_M4A.exists() and MANIFEST_PATH.exists():
                self.assertEqual(report["status"], "FAIL")
                self.assertFalse(report["checks"]["ffmpeg_signal_probe_passed"])
                self.assertEqual(report["signal_analysis"]["status"], "FAIL")
            self.assertFalse(report["human_audio_approved"])

    def test_ffprobe_and_afinfo_missing_handled_gracefully(self):
        with patch("tools.r02_audio_qa.probe_audio_format", side_effect=r02_audio_qa.QAProbeError("All format probes failed")):
            report = r02_audio_qa.probe_audio(
                m4a_path=MASTER_M4A if MASTER_M4A.exists() else Path(__file__),
                manifest_path=MANIFEST_PATH if MANIFEST_PATH.exists() else None,
            )
            self.assertIn(report["status"], ("FAIL", "NOT_RUN"))
            self.assertFalse(report["human_audio_approved"])
            self.assertFalse(report["human_listening_performed"])
            self.assertIn("error", report)

    def test_missing_m4a_fails_closed(self):
        non_existent = ROOT / "research/r02/local/valparaiso_central/audio/non_existent.m4a"
        report = r02_audio_qa.probe_audio(
            m4a_path=non_existent,
            manifest_path=MANIFEST_PATH
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["human_audio_approved"])
        self.assertFalse(report["human_listening_performed"])
        self.assertIn("not found", report["error"])

    def test_missing_manifest_fails_closed(self):
        if not MASTER_M4A.exists():
            self.skipTest("Local Condition A master audio not present")

        non_existent_manifest = ROOT / "research/r02/local/valparaiso_central/audio/non_existent.manifest.json"
        report = r02_audio_qa.probe_audio(
            m4a_path=MASTER_M4A,
            manifest_path=non_existent_manifest
        )
        self.assertEqual(report["status"], "FAIL")
        self.assertFalse(report["checks"]["sha256_matches_manifest"])

    def test_corrupted_sha_fails_closed(self):
        if not MASTER_M4A.exists() or not MANIFEST_PATH.exists():
            self.skipTest("Local Condition A master audio or manifest not present")

        manifest_data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest_data["m4a_sha256"] = "0" * 64

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            json.dump(manifest_data, tmp)
            tmp_path = Path(tmp.name)

        try:
            report = r02_audio_qa.probe_audio(
                m4a_path=MASTER_M4A,
                manifest_path=tmp_path
            )
            self.assertEqual(report["status"], "FAIL")
            self.assertFalse(report["checks"]["sha256_matches_manifest"])
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_cli_output_json_only(self):
        if not MASTER_M4A.exists() or not MANIFEST_PATH.exists():
            self.skipTest("Local Condition A master audio or manifest not present")

        python_exec = os.environ.get("PYTHON") or sys.executable
        result = subprocess.run(
            [
                python_exec,
                str(ROOT / "tools/r02_audio_qa.py"),
                "--m4a",
                str(MASTER_M4A),
                "--manifest",
                str(MANIFEST_PATH),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "PASS")
        self.assertFalse(report["human_audio_approved"])

if __name__ == "__main__":
    unittest.main()
