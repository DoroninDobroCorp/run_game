#!/usr/bin/env python3
"""R04 Fail-Closed Decision Template Validator.

Fulfills assertion VAL-R04-002.

Evaluates research/r04/decision_template.json and fails closed with non-zero exit code
if any founder parameter or observed metric value is "UNSET", unpopulated, or missing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE_PATH = ROOT / "research" / "r04" / "decision_template.json"


class R04DecisionValidationError(ValueError):
    """Raised when R04 decision template fails validation or contains UNSET parameters."""


def evaluate_r04_decision_template(template_data: Dict[str, Any]) -> str:
    """Evaluates R04 decision parameters.

    Fails closed (raises R04DecisionValidationError) if any founder parameter
    or observed metric value is UNSET or unpopulated.
    Returns decision outcome string ("GO", "CONDITIONAL_PIVOT", or "NO_GO") if fully populated and valid.
    """
    if not isinstance(template_data, dict):
        raise R04DecisionValidationError("Decision template must be a JSON object")

    params = template_data.get("founder_parameters")
    if not isinstance(params, dict) or len(params) == 0:
        raise R04DecisionValidationError("Missing or empty founder_parameters in decision template")

    unpopulated_founder = []
    for key, val in params.items():
        if val == "UNSET" or val is None or (isinstance(val, str) and len(val.strip()) == 0):
            unpopulated_founder.append(key)

    if unpopulated_founder:
        raise R04DecisionValidationError(
            f"Cannot evaluate R04 decision template: founder parameter(s) unpopulated/UNSET: {unpopulated_founder}"
        )

    observed = template_data.get("observed_metrics")
    if not isinstance(observed, dict) or len(observed) == 0:
        raise R04DecisionValidationError("Missing or empty observed_metrics in decision template")

    unpopulated_observed = []
    for key, val in observed.items():
        if val == "UNSET" or val is None or (isinstance(val, str) and len(val.strip()) == 0):
            unpopulated_observed.append(key)

    if unpopulated_observed:
        raise R04DecisionValidationError(
            f"Cannot evaluate R04 decision template: observed metric(s) unpopulated/UNSET: {unpopulated_observed}"
        )

    # Strict check for required decision fields without default fallbacks
    if "go_threshold_pdcr_percent" not in params:
        raise R04DecisionValidationError("Missing required founder parameter: go_threshold_pdcr_percent")
    if "conditional_pivot_min_pdcr_percent" not in params:
        raise R04DecisionValidationError("Missing required founder parameter: conditional_pivot_min_pdcr_percent")
    if "pdcr_actual_percent" not in observed:
        raise R04DecisionValidationError("Missing required observed metric: pdcr_actual_percent")

    try:
        go_thresh = float(params["go_threshold_pdcr_percent"])
        pivot_thresh = float(params["conditional_pivot_min_pdcr_percent"])
        pdcr = float(observed["pdcr_actual_percent"])
    except (ValueError, TypeError) as exc:
        raise R04DecisionValidationError(f"Invalid numeric value in decision parameters or metrics: {exc}") from exc

    if pdcr >= go_thresh:
        return "GO"
    elif pdcr >= pivot_thresh:
        return "CONDITIONAL_PIVOT"
    else:
        return "NO_GO"


def load_decision_template(path: Path) -> Dict[str, Any]:
    """Loads JSON decision template file."""
    if not path.is_file():
        raise R04DecisionValidationError(f"File not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise R04DecisionValidationError(f"Failed to parse JSON decision template: {exc}") from exc


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE_PATH,
        help="Path to decision_template.json (defaults to research/r04/decision_template.json)",
    )
    args = parser.parse_args(argv)

    try:
        data = load_decision_template(args.template)
        outcome = evaluate_r04_decision_template(data)
        report = {
            "status": "PASS",
            "tool": "r04_validate_decision",
            "outcome": outcome,
            "template": str(args.template),
        }
        print(json.dumps(report, indent=2))
        return 0
    except R04DecisionValidationError as exc:
        err = {
            "status": "FAIL",
            "tool": "r04_validate_decision",
            "error": str(exc),
            "template": str(args.template),
        }
        print(json.dumps(err, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
