#!/usr/bin/env python3
"""Unit tests for Makefile sanitizer targets, PYTHON executable consistency, and documentation integrity.

Fulfills assertion VAL-IOS-002, VAL-CROSS-001, VAL-DOCS-001, and VAL-DOCS-002.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE_PATH = ROOT / "Makefile"
PROJECT_YML_PATH = ROOT / "ios" / "RunGameFounder" / "project.yml"


class MakefileTargetsTests(unittest.TestCase):
    """Tests for Makefile targets, $(PYTHON) usage, and sanitizer configurations."""

    def setUp(self) -> None:
        self.assertTrue(MAKEFILE_PATH.is_file(), "Makefile must exist at repository root")
        self.content = MAKEFILE_PATH.read_text(encoding="utf-8")

    def test_python_variable_defined_at_top(self) -> None:
        """Verify PYTHON ?= python3 or PYTHON = ... is defined near top of Makefile."""
        match = re.search(r"^PYTHON\s*\??=\s*.+$", self.content, re.MULTILINE)
        self.assertIsNotNone(match, "Makefile must define PYTHON variable (e.g. PYTHON ?= python3)")
        self.assertIn("/usr/bin/python3", match.group(0), "macOS release workflow must default to the pyexpat-capable system Python")

    def test_all_python_invocations_use_python_variable(self) -> None:
        """Verify python script and unittest invocations use $(PYTHON) instead of raw python3 or /usr/bin/python3."""
        lines = self.content.splitlines()
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Ignore comments, echo commands, or variable assignments (e.g. PYTHON ?= python3)
            if stripped.startswith("#") or "echo " in stripped or stripped.startswith("PYTHON"):
                continue
            # Raw python3 or /usr/bin/python3 should not be invoked directly in command lines
            self.assertNotRegex(
                stripped,
                r"(^|\s)(python3|/usr/bin/python3)(\s|$)",
                f"Line {i} in Makefile invokes python3 directly instead of $(PYTHON): {line}",
            )

    def test_sanitizer_targets_defined_in_phony_and_rules(self) -> None:
        """Verify test-asan and test-tsan targets are in .PHONY and defined as Makefile rules."""
        phony_match = re.search(r"^\.PHONY:.*$", self.content, re.MULTILINE)
        self.assertIsNotNone(phony_match, ".PHONY line must exist in Makefile")
        phony_line = phony_match.group(0)
        self.assertIn("test-asan", phony_line, ".PHONY must contain test-asan")
        self.assertIn("test-tsan", phony_line, ".PHONY must contain test-tsan")

        self.assertIsNotNone(re.search(r"^test-asan\s*:", self.content, re.MULTILINE), "Makefile must define test-asan target rule")
        self.assertIsNotNone(re.search(r"^test-tsan\s*:", self.content, re.MULTILINE), "Makefile must define test-tsan target rule")

    def test_sanitizer_targets_fail_closed_when_skipped(self) -> None:
        """Verify sanitizer targets report skipped runs and require an explicit opt-out."""
        # Find test-asan section
        asan_match = re.search(r"^test-asan\s*:.*?(?=\n[a-zA-Z0-9_\.-]+\s*:|\Z)", self.content, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(asan_match, "test-asan target block must be found")
        asan_block = asan_match.group(0)
        self.assertIn("enableAddressSanitizer", asan_block, "test-asan must use -enableAddressSanitizer YES")
        self.assertIn("SKIPPED", asan_block, "test-asan must report SKIPPED if unavailable")
        self.assertIn("ALLOW_UNSUPPORTED_SANITIZERS", asan_block)

        # Find test-tsan section
        tsan_match = re.search(r"^test-tsan\s*:.*?(?=\n[a-zA-Z0-9_\.-]+\s*:|\Z)", self.content, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(tsan_match, "test-tsan target block must be found")
        tsan_block = tsan_match.group(0)
        self.assertIn("enableThreadSanitizer", tsan_block, "test-tsan must use -enableThreadSanitizer YES")
        self.assertIn("SKIPPED", tsan_block, "test-tsan must report SKIPPED if unavailable")
        self.assertIn("ALLOW_UNSUPPORTED_SANITIZERS", tsan_block)

    def test_strict_ab_validate_target_executes_verify_field(self) -> None:
        """Verify strict-ab-validate target executes tools/r02_verify_field.py."""
        match = re.search(r"^strict-ab-validate\s*:.*?(?=\n[a-zA-Z0-9_\.-]+\s*:|\Z)", self.content, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(match, "strict-ab-validate target block must be found")
        block = match.group(0)
        self.assertIn("tools/r02_verify_field.py", block, "strict-ab-validate must execute tools/r02_verify_field.py")

    def test_verify_pretest_sequence(self) -> None:
        """Verify verify-pretest includes all required stages in sequence."""
        match = re.search(r"^verify-pretest\s*:\s*(.*)$", self.content, re.MULTILINE)
        self.assertIsNotNone(match, "verify-pretest target rule must exist")
        prereqs = match.group(1).split()
        expected_prereqs = [
            "r02-doctor",
            "r02-audit-privacy",
            "r02-preflight",
            "r02-audio-qa",
            "quality",
            "py-compile",
            "ast-cross-contract",
            "r02-story-validate",
            "strict-ab-validate",
            "r02-evidence-validate",
            "negative-smoke-test",
            "r03-synthetic-validate",
            "r04-unset-reject",
            "verify-synthetic",
            "ios-build",
            "ios-test",
            "test-asan",
            "test-tsan",
        ]
        for expected in expected_prereqs:
            self.assertIn(expected, prereqs, f"verify-pretest missing prerequisite target '{expected}'")

    def test_tester_package_target_avoids_developer_only_suites(self) -> None:
        match = re.search(r"^verify-tester-package\s*:\s*(.*)$", self.content, re.MULTILINE)
        self.assertIsNotNone(match, "verify-tester-package target rule must exist")
        prereqs = match.group(1).split()
        self.assertEqual(
            prereqs,
            ["r02-handoff-verify", "r02-doctor", "r02-audit-privacy", "r02-preflight", "r02-audio-qa", "ios-build"],
        )

    def test_clean_room_target_uses_synthetic_bundle(self) -> None:
        match = re.search(r"^verify-clean-room\s*:\s*(.*)$", self.content, re.MULTILINE)
        self.assertIsNotNone(match, "verify-clean-room target rule must exist")
        prereqs = match.group(1).split()
        self.assertIn("ios-synthetic-build-for-testing", prereqs)
        self.assertNotIn("r02-preflight", prereqs)

    def test_xcodegen_signing_and_bundle_id_are_parameterized(self) -> None:
        project_spec = PROJECT_YML_PATH.read_text(encoding="utf-8")
        self.assertIn("${RUN_GAME_BUNDLE_ID}", project_spec)
        self.assertIn("${RUN_GAME_DEVELOPMENT_TEAM}", project_spec)
        self.assertNotIn("DEVELOPMENT_TEAM: RYH84JAC66", project_spec)
        self.assertIn("IOS_BUNDLE_ID ?=", self.content)
        self.assertRegex(self.content, r"(?m)^IOS_DEVELOPMENT_TEAM \?=\s*$")


class DocumentationIntegrityTests(unittest.TestCase):
    """Tests for documentation integrity, machine report cleanup, and honest stage reporting.

    Fulfills assertions VAL-DOCS-001 and VAL-DOCS-002.
    """

    def test_machine_readiness_reports_removed_and_untracked(self) -> None:
        """Verify research/dependency_readiness_report.json and research/validation_readiness_report.json are untracked and do not exist."""
        dep_report = ROOT / "research" / "dependency_readiness_report.json"
        val_report = ROOT / "research" / "validation_readiness_report.json"
        self.assertFalse(dep_report.exists(), "dependency_readiness_report.json must be removed")
        self.assertFalse(val_report.exists(), "validation_readiness_report.json must be removed")

    def test_readme_purges_stale_metrics_and_reports_honest_status(self) -> None:
        """Verify README.md purges old $250 budget, 3% PDCR, outdated 156 test count, and reports R02 IN_PROGRESS / R03-R04 NOT_STARTED."""
        readme_path = ROOT / "README.md"
        self.assertTrue(readme_path.is_file(), "README.md must exist")
        content = readme_path.read_text(encoding="utf-8")

        self.assertNotIn("$250", content, "README.md must not contain stale $250 budget figure")
        self.assertNotIn("3.0%", content, "README.md must not contain stale 3.0% PDCR figure")
        self.assertNotIn("156 tests", content, "README.md must not contain outdated 156 test count")
        self.assertIn("245 tests", content, "README.md must reflect exact 245 Python test count")

        self.assertIn("R02", content, "README.md must mention Stage R02")
        self.assertIn("IN_PROGRESS", content, "README.md must report R02 as IN_PROGRESS")
        self.assertIn("NOT_STARTED", content, "README.md must report R03/R04 as NOT_STARTED")

    def test_execution_status_and_readiness_report_honest_counts_and_status(self) -> None:
        """Verify EXECUTION_STATUS.md and PRE_FIRST_TEST_READINESS.md report honest R02 IN_PROGRESS, R03/R04 NOT_STARTED, and exact test counts."""
        exec_status_path = ROOT / "docs" / "EXECUTION_STATUS.md"
        readiness_path = ROOT / "docs" / "PRE_FIRST_TEST_READINESS.md"

        self.assertTrue(exec_status_path.is_file(), "EXECUTION_STATUS.md must exist")
        self.assertTrue(readiness_path.is_file(), "PRE_FIRST_TEST_READINESS.md must exist")

        exec_content = exec_status_path.read_text(encoding="utf-8")
        read_content = readiness_path.read_text(encoding="utf-8")

        for name, doc_content in [("EXECUTION_STATUS.md", exec_content), ("PRE_FIRST_TEST_READINESS.md", read_content)]:
            self.assertIn("R02", doc_content, f"{name} must contain R02 stage")
            self.assertIn("IN_PROGRESS", doc_content, f"{name} must report IN_PROGRESS for R02")
            self.assertIn("NOT_STARTED", doc_content, f"{name} must report NOT_STARTED for R03/R04")
            self.assertIn("245", doc_content, f"{name} must report exact 245 Python test count")
            self.assertIn("76", doc_content, f"{name} must report the executed Swift unit test count")
            self.assertIn("5", doc_content, f"{name} must report the executed Swift UI test count")
            self.assertNotIn("runtime suite локально `NOT_RUN`", doc_content, f"{name} must not retain stale runtime status")


if __name__ == "__main__":
    unittest.main()
