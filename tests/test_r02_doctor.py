#!/usr/bin/env python3
"""Unit tests for tools/r02_doctor.py."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from tools import r02_doctor


class TestR02Doctor(unittest.TestCase):

    def test_inspect_python(self) -> None:
        result = r02_doctor.inspect_python()
        self.assertIn(result["status"], ("PASS", "WARN", "BLOCKED"))
        self.assertIn("version", result)
        self.assertIn("executable", result)

    def test_inspect_platform(self) -> None:
        result = r02_doctor.inspect_platform()
        self.assertIn(result["status"], ("PASS", "WARN"))
        self.assertIn("system", result)

    def test_inspect_git(self) -> None:
        result = r02_doctor.inspect_git()
        self.assertIn(result["status"], ("PASS", "WARN"))
        self.assertIn("branch", result)

    def test_inspect_local_fixtures_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            result = r02_doctor.inspect_local_fixtures(
                tmp_path / "nonexistent_fixture",
                tmp_path / "nonexistent_ios",
            )
            self.assertEqual(result["status"], "WARN")
            self.assertFalse(result["fixture_dir_exists"])
            self.assertFalse(result["ios_resources_dir_exists"])

    def test_inspect_local_fixtures_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            fixture_dir = tmp_path / "fixture"
            ios_dir = tmp_path / "ios"
            fixture_dir.mkdir()
            ios_dir.mkdir()
            (ios_dir / "m01_solo_founder_30min.m4a").write_bytes(b"dummy")
            (ios_dir / "m01_solo_founder_30min.manifest.json").write_text("{}", encoding="utf-8")
            (ios_dir / "mission.json").write_text("{}", encoding="utf-8")

            result = r02_doctor.inspect_local_fixtures(fixture_dir, ios_dir)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["fixture_dir_exists"])
            self.assertTrue(result["ios_resources_dir_exists"])
            self.assertTrue(result["m4a_exists"])
            self.assertTrue(result["manifest_exists"])
            self.assertTrue(result["mission_exists"])

    def test_diagnose_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            report = r02_doctor.diagnose(tmp_path, tmp_path)
            self.assertEqual(report["schema_version"], "0.1")
            self.assertEqual(report["tool"], "r02_doctor")
            self.assertIn(report["status"], ("PASS", "WARN", "BLOCKED"))
            self.assertIn("inspections", report)
            for name in ("python", "platform", "git", "local_fixtures", "privacy", "audio_probes", "xcode", "xcodegen", "simulators"):
                self.assertIn(name, report["inspections"])

    def test_main_cli_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "doctor_out.json"
            exit_code = r02_doctor.main(["--out", str(out_file)])
            self.assertIn(exit_code, (0, 1))
            self.assertTrue(out_file.is_file())
            data = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(data["tool"], "r02_doctor")


if __name__ == "__main__":
    unittest.main()
