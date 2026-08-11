"""Unit test suite for R04 Decision Template and Guardrails Verification.

Fulfills assertion VAL-R04-001.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestR04DecisionTemplate(unittest.TestCase):
    """Verifies that research/r04/decision_template.md meets all VAL-R04-001 requirements."""

    def setUp(self):
        self.r04_dir = ROOT / "research" / "r04"
        self.template_path = self.r04_dir / "decision_template.md"

    def test_r04_directory_and_template_exist(self):
        self.assertTrue(self.r04_dir.is_dir(), "research/r04/ directory must exist")
        self.assertTrue(self.template_path.is_file(), "research/r04/decision_template.md must exist")

    def test_template_contains_required_founder_parameters(self):
        content = self.template_path.read_text(encoding="utf-8")
        
        # Check required parameter fields / sections
        required_fields = [
            "Target Audience & Scope",
            "Price Offer & Deposit Rules",
            "Refund & Cancellation Policy",
            "Qualified Visitor Definition",
            "Ad Spend Stop-Loss Limit",
            "Primary Conversion Metric",
            "GO / NO-GO Decision Rules",
        ]
        for field in required_fields:
            self.assertIn(field, content, f"decision_template.md must contain section/parameter: '{field}'")

    def test_template_enforces_pre_landing_publication_guardrails(self):
        content = self.template_path.read_text(encoding="utf-8")

        # Must explicitly state landing pages cannot be published without filled template
        self.assertIn("explicit founder choices", content.lower())
        self.assertIn("prior to landing publication", content.lower())
        self.assertIn("no landing page published", content.lower())
        self.assertIn("no payments accepted", content.lower())

    def test_execution_status_unaltered(self):
        """Verifies R04 status remains NOT_STARTED in docs/EXECUTION_STATUS.md."""
        exec_status_path = ROOT / "docs" / "EXECUTION_STATUS.md"
        self.assertTrue(exec_status_path.is_file(), "docs/EXECUTION_STATUS.md must exist")
        content = exec_status_path.read_text(encoding="utf-8")

        r04_lines = [line for line in content.splitlines() if "| **R04** |" in line or "**R04**" in line]
        self.assertTrue(len(r04_lines) > 0, "R04 entry must exist in docs/EXECUTION_STATUS.md")
        self.assertIn("NOT_STARTED", r04_lines[0], "R04 status must remain NOT_STARTED in EXECUTION_STATUS.md")


if __name__ == "__main__":
    unittest.main()
