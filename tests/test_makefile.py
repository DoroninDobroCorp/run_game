#!/usr/bin/env python3
"""Unit tests for Makefile sanitizer targets and PYTHON executable consistency.

Fulfills assertion VAL-IOS-002 and VAL-CROSS-001 Makefile requirements.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE_PATH = ROOT / "Makefile"


class MakefileTargetsTests(unittest.TestCase):
    """Tests for Makefile targets, $(PYTHON) usage, and sanitizer configurations."""

    def setUp(self) -> None:
        self.assertTrue(MAKEFILE_PATH.is_file(), "Makefile must exist at repository root")
        self.content = MAKEFILE_PATH.read_text(encoding="utf-8")

    def test_python_variable_defined_at_top(self) -> None:
        """Verify PYTHON ?= python3 or PYTHON = ... is defined near top of Makefile."""
        match = re.search(r"^PYTHON\s*\??=\s*.+$", self.content, re.MULTILINE)
        self.assertIsNotNone(match, "Makefile must define PYTHON variable (e.g. PYTHON ?= python3)")

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

    def test_sanitizer_targets_handle_unsupported(self) -> None:
        """Verify test-asan and test-tsan contain UNSUPPORTED diagnostic status fallback."""
        # Find test-asan section
        asan_match = re.search(r"^test-asan\s*:.*?(?=\n[a-zA-Z0-9_\.-]+\s*:|\Z)", self.content, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(asan_match, "test-asan target block must be found")
        asan_block = asan_match.group(0)
        self.assertIn("enableAddressSanitizer", asan_block, "test-asan must use -enableAddressSanitizer YES")
        self.assertIn("UNSUPPORTED", asan_block, "test-asan must report UNSUPPORTED if unavailable")

        # Find test-tsan section
        tsan_match = re.search(r"^test-tsan\s*:.*?(?=\n[a-zA-Z0-9_\.-]+\s*:|\Z)", self.content, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(tsan_match, "test-tsan target block must be found")
        tsan_block = tsan_match.group(0)
        self.assertIn("enableThreadSanitizer", tsan_block, "test-tsan must use -enableThreadSanitizer YES")
        self.assertIn("UNSUPPORTED", tsan_block, "test-tsan must report UNSUPPORTED if unavailable")

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


if __name__ == "__main__":
    unittest.main()
