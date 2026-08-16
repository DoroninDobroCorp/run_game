#!/usr/bin/env python3
"""R04 Fail-Closed Decision Template Validator.

Fulfills assertions VAL-R04-002, VAL-R04-004, and VAL-R04-005.

Evaluates research/r04/decision_template.json and fails closed with non-zero exit code
if any founder parameter or observed metric value is "UNSET", unpopulated, missing,
out of range, or physically impossible.
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
    """Raised when R04 decision template fails validation or contains UNSET / invalid parameters."""


def evaluate_r04_decision_template(template_data: Dict[str, Any]) -> str:
    """Evaluates R04 decision parameters.

    Fails closed (raises R04DecisionValidationError) if any founder parameter
    or observed metric value is UNSET, unpopulated, out of range, or physically impossible.
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
    for req_param in ("go_threshold_pdcr_percent", "conditional_pivot_min_pdcr_percent", "no_go_threshold_pdcr_percent"):
        if req_param not in params:
            raise R04DecisionValidationError(f"Missing required founder parameter: {req_param}")

    for req_metric in ("qualified_visitor_count", "completed_refundable_deposits_count", "pdcr_actual_percent", "total_ad_spend_usd"):
        if req_metric not in observed:
            raise R04DecisionValidationError(f"Missing required observed metric: {req_metric}")

    try:
        go_thresh = float(params["go_threshold_pdcr_percent"])
        pivot_thresh = float(params["conditional_pivot_min_pdcr_percent"])
        no_go_thresh = float(params["no_go_threshold_pdcr_percent"])
        visitor_count = float(observed["qualified_visitor_count"])
        deposit_count = float(observed["completed_refundable_deposits_count"])
        pdcr_actual = float(observed["pdcr_actual_percent"])
        ad_spend = float(observed["total_ad_spend_usd"])
    except (ValueError, TypeError) as exc:
        raise R04DecisionValidationError(f"Invalid numeric value in decision parameters or metrics: {exc}") from exc

    # Range validation for thresholds (0..100)
    if not (0.0 <= go_thresh <= 100.0):
        raise R04DecisionValidationError(f"go_threshold_pdcr_percent must be in range [0, 100], got {go_thresh}")
    if not (0.0 <= pivot_thresh <= 100.0):
        raise R04DecisionValidationError(f"conditional_pivot_min_pdcr_percent must be in range [0, 100], got {pivot_thresh}")
    if not (0.0 <= no_go_thresh <= 100.0):
        raise R04DecisionValidationError(f"no_go_threshold_pdcr_percent must be in range [0, 100], got {no_go_thresh}")

    # Threshold ordering and non-overlapping decision bands validation
    if no_go_thresh > pivot_thresh:
        raise R04DecisionValidationError(
            f"Invalid threshold ordering: no_go_threshold_pdcr_percent ({no_go_thresh}) "
            f"exceeds conditional_pivot_min_pdcr_percent ({pivot_thresh})"
        )
    if pivot_thresh > go_thresh:
        raise R04DecisionValidationError(
            f"Invalid threshold ordering: conditional_pivot_min_pdcr_percent ({pivot_thresh}) "
            f"exceeds go_threshold_pdcr_percent ({go_thresh})"
        )

    # Physically impossible metrics checks
    if visitor_count < 0:
        raise R04DecisionValidationError(f"qualified_visitor_count must be non-negative (>= 0), got {visitor_count}")
    if visitor_count == 0:
        raise R04DecisionValidationError("qualified_visitor_count must be > 0 for decision evaluation")

    if deposit_count < 0:
        raise R04DecisionValidationError(f"completed_refundable_deposits_count must be non-negative (>= 0), got {deposit_count}")

    if deposit_count > visitor_count:
        raise R04DecisionValidationError(
            f"completed_refundable_deposits_count ({deposit_count}) cannot exceed qualified_visitor_count ({visitor_count})"
        )

    if ad_spend < 0:
        raise R04DecisionValidationError(f"total_ad_spend_usd must be non-negative (>= 0), got {ad_spend}")

    if not (0.0 <= pdcr_actual <= 100.0):
        raise R04DecisionValidationError(f"pdcr_actual_percent must be in range [0, 100], got {pdcr_actual}")

    # Recalculate and verify supplied pdcr_actual_percent matches deposits / visitors * 100
    recomputed_pdcr = (deposit_count / visitor_count) * 100.0
    if abs(pdcr_actual - recomputed_pdcr) > 1e-4:
        raise R04DecisionValidationError(
            f"Supplied pdcr_actual_percent ({pdcr_actual}) does not match recomputed PDCR ({recomputed_pdcr:.4f}%) "
            f"from deposits ({deposit_count}) / visitors ({visitor_count}) * 100"
        )

    if pdcr_actual >= go_thresh:
        return "GO"
    elif pdcr_actual >= pivot_thresh:
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
