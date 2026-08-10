#!/usr/bin/env python3
"""Unit tests for tools/r02_audit_privacy.py."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import r02_audit_privacy


class TestR02AuditPrivacy(unittest.TestCase):

    def test_audit_gitignore(self) -> None:
        report = r02_audit_privacy.audit_gitignore()
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["missing"]), 0)

    def test_audit_git_tracked_files(self) -> None:
        report = r02_audit_privacy.audit_git_tracked_files()
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["leaking_files"]), 0)

    def test_inspect_json_privacy_clean(self) -> None:
        clean_json = {
            "schema_version": "0.3",
            "record_status": "immediate_complete",
            "run_id": "run_123",
            "distance_m": 1250.0,
            "device": {"model": "iPhone 16 Pro"},
        }
        violations = r02_audit_privacy.inspect_json_privacy(clean_json)
        self.assertEqual(len(violations), 0)

    def test_inspect_json_privacy_leaks(self) -> None:
        leaky_json = {
            "schema_version": "0.3",
            "latitude": 37.7749,
            "longitude": -122.4194,
            "local_path": "/Users/john/secret/file.txt",
        }
        violations = r02_audit_privacy.inspect_json_privacy(leaky_json)
        self.assertTrue(len(violations) >= 3)
        self.assertTrue(any("latitude" in v for v in violations))
        self.assertTrue(any("longitude" in v for v in violations))
        self.assertTrue(any("absolute path" in v for v in violations))

    def test_audit_secrets_clean(self) -> None:
        report = r02_audit_privacy.audit_secrets()
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["findings"]), 0)

    def test_audit_all_clean(self) -> None:
        report = r02_audit_privacy.audit_all()
        self.assertTrue(report["ok"])
        self.assertEqual(report["status"], "PASS")

    def test_main_cli_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "privacy_out.json"
            exit_code = r02_audit_privacy.main(["--out", str(out_file)])
            self.assertEqual(exit_code, 0)
            self.assertTrue(out_file.is_file())
            data = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(data["tool"], "r02_audit_privacy")
            self.assertEqual(data["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
