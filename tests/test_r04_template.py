"""Unit test suite for R04 Decision Template and Guardrails Verification.

Fulfills assertions VAL-R04-001, VAL-R04-002, and VAL-R04-003.
"""

import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from tools.r04_validate_decision import (
    R04DecisionValidationError,
    evaluate_r04_decision_template,
    load_decision_template,
    main as r04_validator_main,
)


class TestR04DecisionTemplate(unittest.TestCase):
    """Verifies that research/r04/decision_template.md and decision_template.json meet VAL-R04-001, VAL-R04-002, and VAL-R04-003 requirements."""

    def setUp(self):
        self.r04_dir = ROOT / "research" / "r04"
        self.template_path = self.r04_dir / "decision_template.md"
        self.json_template_path = self.r04_dir / "decision_template.json"
        self.validator_path = ROOT / "tools" / "r04_validate_decision.py"

    def test_r04_directory_and_template_exist(self):
        self.assertTrue(self.r04_dir.is_dir(), "research/r04/ directory must exist")
        self.assertTrue(self.template_path.is_file(), "research/r04/decision_template.md must exist")
        self.assertTrue(self.json_template_path.is_file(), "research/r04/decision_template.json must exist")
        self.assertTrue(self.validator_path.is_file(), "tools/r04_validate_decision.py must exist")

    def test_template_contains_required_founder_parameters(self):
        content = self.template_path.read_text(encoding="utf-8")

        required_fields = [
            "Target Audience & Scope",
            "Price Offer & Deposit Rules",
            "Refund & Cancellation Policy",
            "Qualified Visitor Definition",
            "Ad Spend Stop-Loss Limit",
            "Primary Conversion Metric",
            "Observed Operational Metrics",
            "GO / NO-GO Decision Rules",
        ]
        for field in required_fields:
            self.assertIn(field, content, f"decision_template.md must contain section/parameter: '{field}'")

    def test_template_enforces_pre_landing_publication_guardrails(self):
        content = self.template_path.read_text(encoding="utf-8")

        self.assertIn("explicit founder choices", content.lower())
        self.assertIn("prior to landing publication", content.lower())
        self.assertIn("no landing page published", content.lower())
        self.assertIn("no payments accepted", content.lower())

    def test_json_template_initializes_all_parameters_to_unset(self):
        """VAL-R04-001: Verifies decision_template.json separates founder_parameters and observed_metrics with all values set to UNSET."""
        with open(self.json_template_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        params = data.get("founder_parameters", {})
        self.assertTrue(len(params) > 0, "founder_parameters dict must not be empty")
        for key, value in params.items():
            self.assertEqual(value, "UNSET", f"Founder parameter '{key}' must be initialized to 'UNSET'")

        observed = data.get("observed_metrics", {})
        self.assertTrue(len(observed) > 0, "observed_metrics dict must not be empty")
        for key, value in observed.items():
            self.assertEqual(value, "UNSET", f"Observed metric '{key}' must be initialized to 'UNSET'")

    def test_evaluation_fails_closed_when_unpopulated(self):
        """VAL-R04-002: Verifies unpopulated/UNSET evaluations fail closed with R04DecisionValidationError."""
        with open(self.json_template_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        with self.assertRaises(R04DecisionValidationError) as ctx:
            evaluate_r04_decision_template(data)

        self.assertIn("UNSET", str(ctx.exception))

    def test_production_validator_cli_fails_closed_on_unpopulated_template(self):
        """VAL-R04-002: Verifies tools/r04_validate_decision.py fails closed with exit code 1 on unpopulated template."""
        exit_code = r04_validator_main(["--template", str(self.json_template_path)])
        self.assertEqual(exit_code, 1, "Validator must return non-zero exit code on UNSET template")

    def test_missing_observation_rejection_and_cli_exit_code_1(self):
        """VAL-R04-002: Verifies populating founder parameters without observed PDCR fails closed with exit code 1."""
        with open(self.json_template_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Populate founder parameters but leave observed_metrics UNSET
        data["founder_parameters"] = {key: 1 for key in data["founder_parameters"]}

        with self.assertRaises(R04DecisionValidationError) as ctx:
            evaluate_r04_decision_template(data)
        self.assertIn("UNSET", str(ctx.exception))

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            json.dump(data, tmp)

        try:
            exit_code = r04_validator_main(["--template", str(tmp_path)])
            self.assertEqual(exit_code, 1, "Validator must return exit code 1 when observed_metrics are UNSET")
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_zero_default_fallbacks_rejects_missing_thresholds_or_metrics(self):
        """VAL-R04-002: Verifies zero default fallbacks exist and missing required keys fail closed."""
        with open(self.json_template_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["founder_parameters"] = {key: "1.0" for key in data["founder_parameters"]}
        data["observed_metrics"] = {key: "1.0" for key in data["observed_metrics"]}

        # Remove go_threshold_pdcr_percent
        bad_params = dict(data["founder_parameters"])
        del bad_params["go_threshold_pdcr_percent"]
        data_missing_thresh = dict(data, founder_parameters=bad_params)

        with self.assertRaises(R04DecisionValidationError) as ctx:
            evaluate_r04_decision_template(data_missing_thresh)
        self.assertIn("go_threshold_pdcr_percent", str(ctx.exception))

        # Remove pdcr_actual_percent
        bad_observed = dict(data["observed_metrics"])
        del bad_observed["pdcr_actual_percent"]
        data_missing_pdcr = dict(data, observed_metrics=bad_observed)

        with self.assertRaises(R04DecisionValidationError) as ctx:
            evaluate_r04_decision_template(data_missing_pdcr)
        self.assertIn("pdcr_actual_percent", str(ctx.exception))

    def test_evaluation_succeeds_when_fully_populated(self):
        """Verifies evaluation succeeds with valid outcome when all parameters and metrics are populated."""
        with open(self.json_template_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["founder_parameters"] = {key: "configured_val" for key in data["founder_parameters"]}
        data["founder_parameters"]["go_threshold_pdcr_percent"] = 3.0
        data["founder_parameters"]["conditional_pivot_min_pdcr_percent"] = 1.5
        data["founder_parameters"]["no_go_threshold_pdcr_percent"] = 1.5

        data["observed_metrics"] = {key: "100" for key in data["observed_metrics"]}
        data["observed_metrics"]["pdcr_actual_percent"] = 3.5

        result = evaluate_r04_decision_template(data)
        self.assertEqual(result, "GO")

    def test_production_validator_cli_succeeds_on_populated_template(self):
        """Verifies tools/r04_validate_decision.py returns exit code 0 when template is fully populated."""
        with open(self.json_template_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["founder_parameters"] = {key: "configured_val" for key in data["founder_parameters"]}
        data["founder_parameters"]["go_threshold_pdcr_percent"] = 3.0
        data["founder_parameters"]["conditional_pivot_min_pdcr_percent"] = 1.5
        data["founder_parameters"]["no_go_threshold_pdcr_percent"] = 1.5

        data["observed_metrics"] = {key: "100" for key in data["observed_metrics"]}
        data["observed_metrics"]["pdcr_actual_percent"] = 4.0

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            json.dump(data, tmp)

        try:
            exit_code = r04_validator_main(["--template", str(tmp_path)])
            self.assertEqual(exit_code, 0, "Validator must return exit code 0 on valid populated template")
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

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
