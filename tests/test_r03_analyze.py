"""Unit test suite for R03 Preregistration and Synthetic Analysis Harness (tools/r03_analyze.py).

Fulfills assertions VAL-R03-001 and VAL-R03-002.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools import r03_analyze

ROOT = Path(__file__).resolve().parents[1]


class TestR03PreregistrationAndAnalysis(unittest.TestCase):
    """Test cases for preregistration schema, synthetic A/B generation, and analysis harness."""

    def test_preregistration_schema_exists_and_is_valid(self):
        prereg_path = ROOT / "research" / "r03" / "preregistration.v0.1.json"
        self.assertTrue(prereg_path.is_file(), "research/r03/preregistration.v0.1.json must exist")
        data = r03_analyze.load_strict_json(prereg_path)
        self.assertEqual(data.get("schema_version"), "0.1")
        self.assertEqual(data.get("study_id"), "R03_SYNTHETIC_EVALUATION")
        self.assertIn("hypothesis", data)
        self.assertIn("conditions", data)
        self.assertIn("A", data["conditions"])
        self.assertIn("B", data["conditions"])

    def test_preregistration_defines_sole_primary_outcome_and_secondary_manipulation_checks(self):
        """Fulfills VAL-R03-002: preregistration.v0.1.json defines actual_next_workout_start as sole primary outcome."""
        prereg_path = ROOT / "research" / "r03" / "preregistration.v0.1.json"
        data = r03_analyze.load_strict_json(prereg_path)
        primary_outcomes = data.get("primary_outcomes", [])
        self.assertEqual(len(primary_outcomes), 1, "Must have exactly one primary outcome measure")
        self.assertEqual(primary_outcomes[0].get("id"), "actual_next_workout_start")
        self.assertEqual(primary_outcomes[0].get("metric"), "binary")

        manipulation_checks = data.get("manipulation_checks", [])
        mc_ids = {mc.get("id") for mc in manipulation_checks}
        self.assertIn("place_necessity_score", mc_ids)
        self.assertIn("retention_place_count", mc_ids)
        self.assertIn("desire_m02_score", mc_ids)

    def test_synthetic_generator_creates_valid_dataset(self):
        dataset = r03_analyze.generate_synthetic_ab_dataset(n_total=50, seed=123)
        self.assertEqual(dataset.get("dataset_type"), "synthetic_ab_trial")
        self.assertEqual(len(dataset.get("participants", [])), 50)

        report = r03_analyze.analyze_dataset(dataset)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["execution_status_claim"], "NOT_STARTED")
        self.assertEqual(report["denominators"]["total_enrolled"], 50)
        self.assertIn("primary_outcomes", report)
        self.assertIn("actual_next_workout_start", report["primary_outcomes"])
        self.assertIn("cohens_d", report["primary_outcomes"]["actual_next_workout_start"])
        self.assertIn("manipulation_checks", report)
        self.assertIn("place_necessity", report["manipulation_checks"])
        self.assertIn("unaided_place_recall", report["manipulation_checks"])
        self.assertIn("desire_for_m02", report["manipulation_checks"])

    def test_analysis_harness_evaluates_primary_binary_outcome_without_altering_not_started_status(self):
        """Fulfills VAL-R03-002: r03_analyze.py evaluates primary binary outcome without altering status."""
        dataset = r03_analyze.generate_synthetic_ab_dataset(n_total=20, seed=42)
        report = r03_analyze.analyze_dataset(dataset)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["execution_status_claim"], "NOT_STARTED")
        self.assertIn("actual_next_workout_start", report["primary_outcomes"])

    def test_analysis_harness_computes_exclusions_correctly(self):
        dataset = r03_analyze.generate_synthetic_ab_dataset(n_total=10, seed=99)
        # Force specific exclusion cases
        dataset["participants"][0]["session"]["aborted"] = True
        dataset["participants"][1]["immediate_debrief"]["confound_delayed_debrief"] = True
        dataset["participants"][2]["recall_24h"] = None

        report = r03_analyze.analyze_dataset(dataset)
        self.assertGreaterEqual(report["exclusions"]["total_excluded"], 3)
        self.assertGreaterEqual(report["exclusions"]["by_reason"]["excl_aborted_run"], 1)
        self.assertGreaterEqual(report["exclusions"]["by_reason"]["excl_delayed_debrief"], 1)

    def test_analysis_rejects_duplicate_json_keys(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write('{"dataset_type": "synthetic_ab_trial", "synthetic": true, "key": 1, "key": 2}')
            temp_path = Path(f.name)

        try:
            with self.assertRaises(r03_analyze.R03AnalysisError) as ctx:
                r03_analyze.load_strict_json(temp_path)
            self.assertIn("duplicate JSON key", str(ctx.exception))
        finally:
            temp_path.unlink(missing_ok=True)

    def test_analysis_rejects_non_finite_json_constants(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write('{"dataset_type": "synthetic_ab_trial", "synthetic": true, "val": NaN}')
            temp_path = Path(f.name)

        try:
            with self.assertRaises(r03_analyze.R03AnalysisError) as ctx:
                r03_analyze.load_strict_json(temp_path)
            self.assertTrue("non-finite JSON constant" in str(ctx.exception) or "invalid JSON structure" in str(ctx.exception))
        finally:
            temp_path.unlink(missing_ok=True)

    def test_analysis_rejects_real_data_leaks(self):
        dataset = r03_analyze.generate_synthetic_ab_dataset(n_total=5, seed=1)
        dataset["participants"][0]["leak"] = "testuser@example.com"
        with self.assertRaises(r03_analyze.R03AnalysisError) as ctx:
            r03_analyze.analyze_dataset(dataset)
        self.assertIn("forbidden real data", str(ctx.exception))

    def test_execution_status_remains_not_started(self):
        exec_status_path = ROOT / "docs" / "EXECUTION_STATUS.md"
        content = exec_status_path.read_text(encoding="utf-8")
        # Ensure R03 line in Stage Table still says NOT_STARTED
        r03_line = [line for line in content.splitlines() if "**R03**" in line or "| **R03** |" in line]
        self.assertTrue(len(r03_line) > 0, "R03 line must exist in EXECUTION_STATUS.md")
        self.assertIn("NOT_STARTED", r03_line[0])


if __name__ == "__main__":
    unittest.main()
