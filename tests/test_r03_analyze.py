"""Unit test suite for R03 Preregistration and Synthetic Analysis Harness (tools/r03_analyze.py).

Fulfills assertions VAL-R03-001, VAL-R03-002, and VAL-R03-003.
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

    def test_preregistration_marks_unknown_sample_sizes_and_windows_as_unset(self):
        """Fulfills VAL-R03-001: preregistration.v0.1.json marks unknown sample sizes/windows as UNSET/TBD."""
        prereg_path = ROOT / "research" / "r03" / "preregistration.v0.1.json"
        data = r03_analyze.load_strict_json(prereg_path)

        sample_size = data.get("sample_size", {})
        self.assertIn(sample_size.get("min_n_per_condition"), ["UNSET", "TBD"])
        self.assertIn(sample_size.get("target_n"), ["UNSET", "TBD"])

        eval_windows = data.get("evaluation_windows", {})
        self.assertTrue(len(eval_windows) > 0, "evaluation_windows must be present")
        self.assertIn(eval_windows.get("recruitment_window"), ["UNSET", "TBD"])
        self.assertIn(eval_windows.get("data_collection_window"), ["UNSET", "TBD"])

    def test_preregistration_defines_condition_b_as_component_test(self):
        """Fulfills VAL-R03-001 and VAL-R03-006: Condition B is defined as a component test preserving narrative structure while altering place dramatic function."""
        prereg_path = ROOT / "research" / "r03" / "preregistration.v0.1.json"
        data = r03_analyze.load_strict_json(prereg_path)
        cond_b = data.get("conditions", {}).get("B", {})
        description = cond_b.get("description", "").lower()
        self.assertIn("component test", description)
        self.assertIn("preserving narrative structure while altering place dramatic function", description)

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
        self.assertNotIn("cohens_d", report["primary_outcomes"]["actual_next_workout_start"])
        self.assertIn("risk_difference", report["primary_outcomes"]["actual_next_workout_start"])
        self.assertIn("manipulation_checks", report)
        self.assertIn("place_necessity", report["manipulation_checks"])
        self.assertIn("unaided_place_recall", report["manipulation_checks"])
        self.assertIn("desire_for_m02", report["manipulation_checks"])

    def test_neutral_null_synthetic_generator_default(self):
        """Fulfills VAL-R03-002: synthetic generator defaults to neutral null effect (zero baked advantage for A)."""
        # Generate large sample to verify null effect convergence
        dataset = r03_analyze.generate_synthetic_ab_dataset(n_total=2000, seed=42)
        report = r03_analyze.analyze_dataset(dataset)

        outcome = report["primary_outcomes"]["actual_next_workout_start"]
        risk_diff = outcome["risk_difference"]
        risk_ratio = outcome["risk_ratio"]

        # Null effect means risk difference is close to 0.0 and risk ratio close to 1.0
        self.assertAlmostEqual(risk_diff, 0.0, delta=0.06, msg=f"Risk difference should be near 0.0 under null, got {risk_diff}")
        self.assertAlmostEqual(risk_ratio, 1.0, delta=0.15, msg=f"Risk ratio should be near 1.0 under null, got {risk_ratio}")

    def test_synthetic_generator_randomization_and_reproducibility(self):
        """Fulfills VAL-R03-002: verifies 1:1 allocation ratio and deterministic seed reproducibility."""
        ds1 = r03_analyze.generate_synthetic_ab_dataset(n_total=100, seed=777)
        ds2 = r03_analyze.generate_synthetic_ab_dataset(n_total=100, seed=777)
        self.assertEqual(ds1, ds2, "Identical seed must produce identical synthetic dataset")

        n_a = sum(1 for p in ds1["participants"] if p["condition"] == "A")
        n_b = sum(1 for p in ds1["participants"] if p["condition"] == "B")
        self.assertEqual(n_a + n_b, 100)
        # Randomization should produce approx balanced groups
        self.assertGreater(n_a, 35)
        self.assertGreater(n_b, 35)

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

    def test_itt_missingness_handling_and_tracking(self):
        """Fulfills VAL-R03-002: verifies missing recall and aborted records are properly tracked and included in ITT."""
        dataset = r03_analyze.generate_synthetic_ab_dataset(n_total=30, seed=101, prob_abort=0.0)
        # Mark 4 participants as having missing recall and 2 as aborted
        dataset["participants"][0]["recall_24h"] = None
        dataset["participants"][1]["recall_24h"] = None
        dataset["participants"][2]["recall_24h"] = None
        dataset["participants"][3]["recall_24h"] = None
        dataset["participants"][4]["session"]["aborted"] = True
        dataset["participants"][5]["session"]["aborted"] = True

        report = r03_analyze.analyze_dataset(dataset)
        denoms = report["denominators"]
        self.assertEqual(denoms["total_enrolled"], 30)
        self.assertEqual(denoms["sessions_aborted"]["A"] + denoms["sessions_aborted"]["B"], 2)

        outcome = report["primary_outcomes"]["actual_next_workout_start"]
        self.assertEqual(
            outcome["condition_A"]["n_assigned"] + outcome["condition_B"]["n_assigned"],
            30,
            "All 30 assigned participants must be in ITT denominator despite missing recall / aborts",
        )

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

    def test_itt_risk_metrics_computation(self):
        """Fulfills VAL-R03-002: verifies ITT risk difference and ratio with confidence intervals."""
        group_a = [1.0] * 35 + [0.0] * 15  # Risk A = 0.70 (35/50)
        group_b = [1.0] * 20 + [0.0] * 30  # Risk B = 0.40 (20/50)

        res = r03_analyze.compute_itt_risk_metrics(group_a, group_b)
        self.assertEqual(res["n_assigned_A"], 50)
        self.assertEqual(res["events_A"], 35)
        self.assertEqual(res["risk_A"], 0.7)
        self.assertEqual(res["n_assigned_B"], 50)
        self.assertEqual(res["events_B"], 20)
        self.assertEqual(res["risk_B"], 0.4)
        self.assertEqual(res["risk_difference"], 0.3)
        self.assertAlmostEqual(res["risk_difference_se"], 0.0949, places=3)
        self.assertEqual(len(res["risk_difference_ci_95"]), 2)
        self.assertLess(res["risk_difference_ci_95"][0], 0.3)
        self.assertGreater(res["risk_difference_ci_95"][1], 0.3)
        self.assertEqual(res["risk_ratio"], 1.75)
        self.assertEqual(len(res["risk_ratio_ci_95"]), 2)
        self.assertLess(res["risk_ratio_ci_95"][0], 1.75)
        self.assertGreater(res["risk_ratio_ci_95"][1], 1.75)

    def test_itt_analysis_includes_all_assigned_participants(self):
        """Fulfills VAL-R03-002: analyze_dataset computes ITT metrics over all assigned participants."""
        dataset = r03_analyze.generate_synthetic_ab_dataset(n_total=40, seed=42)
        # Mark 5 participants as aborted (excluded from per-protocol)
        for i in range(5):
            dataset["participants"][i]["session"]["aborted"] = True

        report = r03_analyze.analyze_dataset(dataset)
        outcome = report["primary_outcomes"]["actual_next_workout_start"]
        self.assertEqual(outcome["analysis_population"], "intention_to_treat")
        self.assertEqual(
            outcome["condition_A"]["n_assigned"] + outcome["condition_B"]["n_assigned"],
            40,
            "ITT denominator must include all assigned participants (40), even aborted ones",
        )
        self.assertIn("risk_difference", outcome)
        self.assertIn("risk_difference_ci_95", outcome)
        self.assertIn("risk_ratio", outcome)
        self.assertIn("risk_ratio_ci_95", outcome)

    def test_preregistration_specifies_itt_analysis_plan(self):
        """Fulfills VAL-R03-001 and VAL-R03-002: preregistration specifies ITT risk difference/ratio analysis."""
        prereg_path = ROOT / "research" / "r03" / "preregistration.v0.1.json"
        data = r03_analyze.load_strict_json(prereg_path)
        plan = data.get("analysis_plan", {})
        self.assertEqual(plan.get("analysis_population"), "intention_to_treat")
        self.assertEqual(plan.get("primary_outcome_analysis"), "itt_risk_difference_and_ratio")
        self.assertEqual(plan.get("confidence_interval"), 0.95)

    def test_complete_r03_scaffolding_artifacts_exist_and_validate(self):
        """Fulfills VAL-R03-003: all R03 scaffolding artifacts exist and validate cleanly."""
        r03_dir = ROOT / "research" / "r03"

        # 1. anonymized_event_schema.json
        schema_path = r03_dir / "anonymized_event_schema.json"
        self.assertTrue(schema_path.is_file(), "anonymized_event_schema.json must exist")
        schema = r03_analyze.load_strict_json(schema_path)
        self.assertEqual(schema.get("title"), "R03AnonymizedEventSchema")
        self.assertIn("participant_id", schema.get("properties", {}))
        self.assertIn("actual_next_workout_start", schema.get("properties", {}))

        # 2. synthetic_fixture.json
        fixture_path = r03_dir / "synthetic_fixture.json"
        self.assertTrue(fixture_path.is_file(), "synthetic_fixture.json must exist")
        fixture = r03_analyze.load_strict_json(fixture_path)
        self.assertEqual(fixture.get("dataset_type"), "synthetic_ab_trial")
        self.assertTrue(fixture.get("synthetic"))
        self.assertGreater(len(fixture.get("participants", [])), 0)
        # Verify it analyzes cleanly
        report = r03_analyze.analyze_dataset(fixture)
        self.assertEqual(report["status"], "PASS")

        # 3. blank_analysis_report.json
        report_path = r03_dir / "blank_analysis_report.json"
        self.assertTrue(report_path.is_file(), "blank_analysis_report.json must exist")
        blank_report = r03_analyze.load_strict_json(report_path)
        self.assertEqual(blank_report.get("status"), "UNEXECUTED")
        self.assertEqual(blank_report.get("execution_status_claim"), "NOT_STARTED")
        self.assertIn("denominators", blank_report)
        self.assertIn("primary_outcomes", blank_report)

        # 4. consent_privacy_checklist.md
        checklist_path = r03_dir / "consent_privacy_checklist.md"
        self.assertTrue(checklist_path.is_file(), "consent_privacy_checklist.md must exist")
        content = checklist_path.read_text(encoding="utf-8")
        self.assertIn("R03 Consent & Privacy Verification Checklist", content)
        self.assertIn("Informed Consent", content)
        self.assertIn("Pseudonymization", content)
        self.assertIn("NOT_STARTED", content)

    def test_analyze_dataset_strictly_validates_binary_outcome(self):
        """Fulfills VAL-R03-004: analyze_dataset rejects non-binary values (2, NaN, string, -1) with R03AnalysisError."""
        dataset = r03_analyze.generate_synthetic_ab_dataset(n_total=10, seed=42)

        # Valid binary integer 0/1 and boolean True/False
        dataset["participants"][0]["actual_next_workout_start"] = 1
        dataset["participants"][1]["actual_next_workout_start"] = 0
        dataset["participants"][2]["actual_next_workout_start"] = True
        dataset["participants"][3]["actual_next_workout_start"] = False
        report = r03_analyze.analyze_dataset(dataset)
        self.assertEqual(report["status"], "PASS")

        # Invalid: integer 2
        dataset["participants"][0]["actual_next_workout_start"] = 2
        with self.assertRaises(r03_analyze.R03AnalysisError) as ctx:
            r03_analyze.analyze_dataset(dataset)
        self.assertIn("must be boolean or exact integer 0/1", str(ctx.exception))

        # Invalid: integer -1
        dataset["participants"][0]["actual_next_workout_start"] = -1
        with self.assertRaises(r03_analyze.R03AnalysisError) as ctx:
            r03_analyze.analyze_dataset(dataset)
        self.assertIn("must be boolean or exact integer 0/1", str(ctx.exception))

        # Invalid: string "1"
        dataset["participants"][0]["actual_next_workout_start"] = "1"
        with self.assertRaises(r03_analyze.R03AnalysisError) as ctx:
            r03_analyze.analyze_dataset(dataset)
        self.assertIn("must be boolean or exact integer 0/1", str(ctx.exception))

        # Invalid: float 2.0
        dataset["participants"][0]["actual_next_workout_start"] = 2.0
        with self.assertRaises(r03_analyze.R03AnalysisError) as ctx:
            r03_analyze.analyze_dataset(dataset)
        self.assertIn("must be boolean or exact integer 0/1", str(ctx.exception))

        # Invalid: float 1.0
        dataset["participants"][0]["actual_next_workout_start"] = 1.0
        with self.assertRaises(r03_analyze.R03AnalysisError) as ctx:
            r03_analyze.analyze_dataset(dataset)
        self.assertIn("must be boolean or exact integer 0/1", str(ctx.exception))

        # Invalid: float NaN
        dataset["participants"][0]["actual_next_workout_start"] = float("nan")
        with self.assertRaises(r03_analyze.R03AnalysisError) as ctx:
            r03_analyze.analyze_dataset(dataset)
        self.assertIn("must be boolean or exact integer 0/1", str(ctx.exception))

    def test_randomizer_tool_reproducibility_and_balance(self):
        """Fulfills VAL-R03-005: r03_randomizer.py implements deterministic 1:1 blocked allocation generator with reproducibility tests."""
        from tools import r03_randomizer

        # Deterministic reproducibility
        alloc1 = r03_randomizer.generate_blocked_allocation(n_participants=100, seed=123, block_size=4)
        alloc2 = r03_randomizer.generate_blocked_allocation(n_participants=100, seed=123, block_size=4)
        self.assertEqual(alloc1, alloc2, "Identical seed must produce identical allocation schedule")

        # Different seeds produce different allocations
        alloc3 = r03_randomizer.generate_blocked_allocation(n_participants=100, seed=999, block_size=4)
        self.assertNotEqual(alloc1["allocations"], alloc3["allocations"])

        # Balance check
        self.assertEqual(alloc1["summary"]["condition_A_count"], 50)
        self.assertEqual(alloc1["summary"]["condition_B_count"], 50)
        self.assertTrue(alloc1["summary"]["is_balanced"])

        # Odd N balance check
        alloc_odd = r03_randomizer.generate_blocked_allocation(n_participants=101, seed=42, block_size=4)
        self.assertEqual(alloc_odd["n_participants"], 101)
        self.assertEqual(alloc_odd["summary"]["condition_A_count"] + alloc_odd["summary"]["condition_B_count"], 101)
        self.assertTrue(alloc_odd["summary"]["is_balanced"])

        # Error cases
        with self.assertRaises(r03_randomizer.R03RandomizerError):
            r03_randomizer.generate_blocked_allocation(n_participants=0)

        with self.assertRaises(r03_randomizer.R03RandomizerError):
            r03_randomizer.generate_blocked_allocation(n_participants=10, block_size=3)

        with self.assertRaises(r03_randomizer.R03RandomizerError):
            r03_randomizer.generate_blocked_allocation(n_participants=10, block_size=0)

    def test_preregistration_hygiene_72h_replacement_and_primary_outcome(self):
        """Fulfills VAL-R03-006: preregistration.v0.1.json replaces 72h references with TBD and removes Cohen's d from primary outcome."""
        prereg_path = ROOT / "research" / "r03" / "preregistration.v0.1.json"
        data = r03_analyze.load_strict_json(prereg_path)

        # 72h references replaced with TBD
        hypothesis = data.get("hypothesis", "")
        self.assertNotIn("72 hours", hypothesis.lower())
        self.assertIn("within tbd", hypothesis.lower())

        primary_outcome = data.get("primary_outcomes", [])[0]
        name = primary_outcome.get("name", "")
        self.assertNotIn("72 hours", name.lower())
        self.assertIn("within tbd", name.lower())

        # Primary outcome block does not reference cohens_d
        primary_str = json.dumps(primary_outcome)
        self.assertNotIn("cohens_d", primary_str)


if __name__ == "__main__":
    unittest.main()
