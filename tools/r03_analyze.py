#!/usr/bin/env python3
"""R03 Offline Analysis Harness & Synthetic A/B Dataset Evaluator.

Fulfills assertion VAL-R03-001.

Evaluates synthetic A/B datasets (Conditions A vs B), computing:
- Total and group denominators (assigned, completed, debriefed, recalled)
- Exclusion criteria (aborted, delayed debrief confound, early recall, incomplete)
- Primary outcomes and manipulation checks (mean, std, Cohen's d, t-statistic / difference)
- Fail-closed validation (rejects real participant data, leaks, duplicate IDs, invalid schemas)
- Supports generating synthetic randomized A/B datasets for offline simulation and power testing.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import random
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.domain_thresholds import SCHEMA_VERSION_DEBRIEF, SCHEMA_VERSION_RECALL  # noqa: E402

REAL_DATA_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # Email
    re.compile(r"\b(?:\+?1[-. ]?)?\(?([0-9]{3})\)?[-. ]?([0-9]{3})[-. ]?([0-9]{4})\b"),  # Phone
    re.compile(r"(\"latitude\"|\"longitude\"|\"coords\")", re.IGNORECASE),  # Raw coords
]


class R03AnalysisError(ValueError):
    """Exception raised for R03 data validation and analysis failures."""


def validate_binary_outcome(val: Any, participant_id: Optional[str] = None) -> int:
    """Validate that actual_next_workout_start is strictly boolean or exact integer 0/1.

    Returns 1 or 0. Rejects float (e.g. 2.0, NaN, 1.0, 0.0), string, -1, 2, None, etc.
    """
    if type(val) is bool:
        return 1 if val else 0
    if type(val) is int and val in (0, 1):
        return val
    pid_str = f" for participant {participant_id!r}" if participant_id else ""
    raise R03AnalysisError(
        f"actual_next_workout_start must be boolean or exact integer 0/1, got {val!r} (type {type(val).__name__}){pid_str}"
    )


def _reject_json_constant(value: str) -> None:
    raise R03AnalysisError(f"non-finite JSON constant {value!r} is forbidden")


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise R03AnalysisError(f"duplicate JSON key {key!r} is forbidden")
        result[key] = value
    return result


def load_strict_json(path: Path) -> Any:
    """Load JSON file strictly disallowing duplicate keys and non-finite floats."""
    if not path.is_file():
        raise R03AnalysisError(f"file not found: {path}")
    try:
        content = path.read_text(encoding="utf-8")
        return json.loads(
            content,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_json_object_without_duplicates,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise R03AnalysisError(f"invalid JSON structure: {exc}") from exc


def check_for_real_data_or_privacy_leaks(content_str: str) -> None:
    """Fail closed if real participant identifiers or raw GPS data appear in dataset."""
    for pat in REAL_DATA_PATTERNS:
        if pat.search(content_str):
            raise R03AnalysisError(f"forbidden real data or coordinate pattern detected in dataset: {pat.pattern}")


def compute_mean_and_std(values: List[float]) -> Tuple[float, float]:
    """Compute sample mean and sample standard deviation (unbiased, N-1)."""
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    mean = sum(values) / n
    if n == 1:
        return mean, 0.0
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return mean, math.sqrt(variance)


def compute_cohens_d(group_a: List[float], group_b: List[float]) -> float:
    """Compute Cohen's d effect size between group A and group B (pooled standard deviation)."""
    n_a = len(group_a)
    n_b = len(group_b)
    if n_a < 2 or n_b < 2:
        return 0.0

    mean_a, std_a = compute_mean_and_std(group_a)
    mean_b, std_b = compute_mean_and_std(group_b)

    # Pooled standard deviation
    s_pooled_sq = (((n_a - 1) * (std_a ** 2)) + ((n_b - 1) * (std_b ** 2))) / (n_a + n_b - 2)
    if s_pooled_sq <= 0:
        return 0.0
    s_pooled = math.sqrt(s_pooled_sq)
    return (mean_a - mean_b) / s_pooled


def compute_itt_risk_metrics(group_a: List[float], group_b: List[float]) -> Dict[str, Any]:
    """Compute Intention-To-Treat (ITT) risk difference, risk ratio, and 95% confidence intervals."""
    n_a = len(group_a)
    n_b = len(group_b)
    if n_a == 0 or n_b == 0:
        return {
            "n_assigned_A": n_a,
            "events_A": 0,
            "risk_A": 0.0,
            "n_assigned_B": n_b,
            "events_B": 0,
            "risk_B": 0.0,
            "risk_difference": 0.0,
            "risk_difference_se": 0.0,
            "risk_difference_ci_95": [0.0, 0.0],
            "risk_ratio": 1.0,
            "risk_ratio_ci_95": [1.0, 1.0],
        }

    k_a = sum(1 for x in group_a if x > 0.5)
    k_b = sum(1 for x in group_b if x > 0.5)

    p_a = k_a / n_a
    p_b = k_b / n_b

    # ITT Risk Difference
    rd = p_a - p_b
    se_rd = math.sqrt((p_a * (1.0 - p_a) / n_a) + (p_b * (1.0 - p_b) / n_b))
    z = 1.959963984540054  # 95% two-sided Z-critical value

    rd_ci_lower = max(-1.0, rd - z * se_rd)
    rd_ci_upper = min(1.0, rd + z * se_rd)

    # ITT Risk Ratio
    rr = p_a / p_b if p_b > 0 else (float("inf") if p_a > 0 else 1.0)

    # For RR 95% CI, use log transformation with Haldane-Anscombe continuity correction if zero/full events
    if k_a == 0 or k_b == 0 or k_a == n_a or k_b == n_b:
        a_c, n_ac = k_a + 0.5, n_a + 1.0
        b_c, n_bc = k_b + 0.5, n_b + 1.0
        p_ac, p_bc = a_c / n_ac, b_c / n_bc
        ln_rr = math.log(p_ac / p_bc)
        se_ln_rr = math.sqrt(((1.0 - p_ac) / a_c) + ((1.0 - p_bc) / b_c))
    else:
        ln_rr = math.log(p_a / p_b)
        se_ln_rr = math.sqrt(((1.0 - p_a) / k_a) + ((1.0 - p_b) / k_b))

    rr_ci_lower = math.exp(ln_rr - z * se_ln_rr)
    rr_ci_upper = math.exp(ln_rr + z * se_ln_rr)

    return {
        "n_assigned_A": n_a,
        "events_A": int(k_a),
        "risk_A": round(p_a, 4),
        "n_assigned_B": n_b,
        "events_B": int(k_b),
        "risk_B": round(p_b, 4),
        "risk_difference": round(rd, 4),
        "risk_difference_se": round(se_rd, 4),
        "risk_difference_ci_95": [round(rd_ci_lower, 4), round(rd_ci_upper, 4)],
        "risk_ratio": round(rr, 4) if not math.isinf(rr) else None,
        "risk_ratio_ci_95": [round(rr_ci_lower, 4), round(rr_ci_upper, 4)],
    }


def generate_synthetic_ab_dataset(
    n_total: int = 100,
    seed: int = 42,
    prob_abort: float = 0.05,
    prob_delayed_debrief: float = 0.08,
    prob_early_recall: float = 0.03,
    prob_missing_recall: float = 0.05,
    null_effect: bool = True,
    prob_workout_start_a: Optional[float] = None,
    prob_workout_start_b: Optional[float] = None,
) -> Dict[str, Any]:
    """Generate a synthetic, randomized A/B trial dataset adhering to preregistration schema.

    Defaults to neutral null effect (zero baked advantage for Condition A).
    """
    rng = random.Random(seed)

    if prob_workout_start_a is not None:
        p_start_a = prob_workout_start_a
    else:
        p_start_a = 0.50 if null_effect else 0.75

    if prob_workout_start_b is not None:
        p_start_b = prob_workout_start_b
    else:
        p_start_b = 0.50 if null_effect else 0.45

    participants = []
    for idx in range(n_total):
        participant_id = f"synth_user_{idx+1:03d}"
        condition = "A" if rng.random() < 0.5 else "B"
        is_aborted = rng.random() < prob_abort
        is_delayed_debrief = rng.random() < prob_delayed_debrief
        is_early_recall = rng.random() < prob_early_recall
        is_missing_recall = rng.random() < prob_missing_recall

        # Recording delay seconds
        if is_delayed_debrief:
            recording_delay_sec = float(rng.randint(3601, 7200))
        else:
            recording_delay_sec = float(rng.randint(10, 600))

        # Outcome values: neutral null effect by default (zero baked advantage for A)
        if condition == "A":
            base_workout_start = 1 if rng.random() < p_start_a else 0
            if null_effect and prob_workout_start_a is None:
                base_places = rng.gauss(2.5, 1.0)
                base_desire = rng.gauss(4.0, 1.0)
                base_necessity = rng.gauss(3.5, 1.0)
            else:
                base_places = rng.gauss(4.2, 1.1)
                base_desire = rng.gauss(5.5, 1.0)
                base_necessity = rng.gauss(5.2, 1.1)
        else:
            base_workout_start = 1 if rng.random() < p_start_b else 0
            base_places = rng.gauss(2.5, 1.0) if null_effect else rng.gauss(2.1, 1.0)
            base_desire = rng.gauss(4.0, 1.0) if null_effect else rng.gauss(3.8, 1.2)
            base_necessity = rng.gauss(3.5, 1.0) if null_effect else rng.gauss(2.5, 1.2)

        actual_next_workout_start = base_workout_start
        place_count = max(0, min(10, int(round(base_places))))
        desire_score = max(1, min(7, int(round(base_desire))))
        necessity_score = max(1, min(7, int(round(base_necessity))))

        record = {
            "participant_id": participant_id,
            "condition": condition,
            "synthetic": True,
            "session": {
                "run_id": f"run_synth_{idx+1:03d}",
                "aborted": is_aborted,
                "route_completed": not is_aborted,
                "audio_duration_seconds": 1800.0 if not is_aborted else float(rng.randint(300, 1200)),
            },
            "actual_next_workout_start": actual_next_workout_start,
            "immediate_debrief": {
                "schema_version": SCHEMA_VERSION_DEBRIEF,
                "completed": True,
                "recording_delay_seconds": recording_delay_sec,
                "confound_delayed_debrief": is_delayed_debrief,
                "place_necessity_1_to_7": necessity_score,
                "desire_for_m02_1_to_7": desire_score,
            },
        }

        if not is_aborted and not is_missing_recall:
            record["recall_24h"] = {
                "schema_version": SCHEMA_VERSION_RECALL,
                "completed": True,
                "due_at_delta_seconds": -300.0 if is_early_recall else float(rng.randint(0, 7200)),
                "is_early_recall": is_early_recall,
                "unaided_place_recall_count": place_count,
                "desire_for_m02_1_to_7": desire_score,
            }
        else:
            record["recall_24h"] = None

        participants.append(record)

    return {
        "schema_version": "0.1",
        "dataset_type": "synthetic_ab_trial",
        "synthetic": True,
        "seed": seed,
        "n_total": n_total,
        "participants": participants,
    }


def analyze_dataset(dataset: Dict[str, Any], prereg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Perform fail-closed analysis of an A/B dataset per preregistration specification."""
    if not isinstance(dataset, dict):
        raise R03AnalysisError("dataset must be a JSON object")

    if dataset.get("dataset_type") != "synthetic_ab_trial" and not dataset.get("synthetic"):
        # Real participant data is not permitted at this phase
        raise R03AnalysisError("R03 execution status is NOT_STARTED: real participant datasets are forbidden at this phase")

    # Serialize to check privacy and real data leaks
    serialized = json.dumps(dataset)
    check_for_real_data_or_privacy_leaks(serialized)

    participants = dataset.get("participants", [])
    if not isinstance(participants, list) or len(participants) == 0:
        raise R03AnalysisError("dataset contains no participants")

    # Check for duplicate participant IDs
    seen_pids = set()
    for p in participants:
        pid = p.get("participant_id")
        if not pid or pid in seen_pids:
            raise R03AnalysisError(f"missing or duplicate participant_id: {pid!r}")
        seen_pids.add(pid)

    # Denominators tracking
    denominators: dict[str, Any] = {
        "total_enrolled": len(participants),
        "by_condition": {"A": 0, "B": 0},
        "sessions_completed": {"A": 0, "B": 0},
        "sessions_aborted": {"A": 0, "B": 0},
        "debriefs_recorded": {"A": 0, "B": 0},
        "recalls_submitted": {"A": 0, "B": 0},
    }

    # Exclusions tracking
    exclusions: dict[str, Any] = {
        "total_excluded": 0,
        "by_reason": {
            "excl_aborted_run": 0,
            "excl_delayed_debrief": 0,
            "excl_early_recall": 0,
            "excl_missing_recall": 0,
        },
        "by_condition": {"A": 0, "B": 0},
    }

    # Clean per-protocol analysis groups
    clean_groups: dict[str, dict[str, list[Any]]] = {
        "A": {
            "pids": [],
            "next_workout_starts": [],
            "place_recall_counts": [],
            "desire_m02_scores": [],
            "place_necessity_scores": [],
        },
        "B": {
            "pids": [],
            "next_workout_starts": [],
            "place_recall_counts": [],
            "desire_m02_scores": [],
            "place_necessity_scores": [],
        },
    }

    for p in participants:
        pid = p.get("participant_id")
        cond = p.get("condition")
        if cond not in {"A", "B"}:
            raise R03AnalysisError(f"invalid condition {cond!r} for participant {pid}")

        if "actual_next_workout_start" not in p:
            raise R03AnalysisError(f"missing actual_next_workout_start for participant {pid}")
        workout_val = validate_binary_outcome(p["actual_next_workout_start"], participant_id=pid)

        denominators["by_condition"][cond] += 1
        session = p.get("session", {})
        is_aborted = session.get("aborted", False) or not session.get("route_completed", True)

        if is_aborted:
            denominators["sessions_aborted"][cond] += 1
        else:
            denominators["sessions_completed"][cond] += 1

        imm = p.get("immediate_debrief", {})
        if imm.get("completed", False):
            denominators["debriefs_recorded"][cond] += 1

        rec = p.get("recall_24h")
        if rec and rec.get("completed", False):
            denominators["recalls_submitted"][cond] += 1

        # Exclusion checks
        excluded = False
        if is_aborted:
            exclusions["by_reason"]["excl_aborted_run"] += 1
            excluded = True

        if imm.get("confound_delayed_debrief", False) or imm.get("recording_delay_seconds", 0) > 3600:
            exclusions["by_reason"]["excl_delayed_debrief"] += 1
            excluded = True

        if not rec or not rec.get("completed", False):
            if not is_aborted:
                exclusions["by_reason"]["excl_missing_recall"] += 1
            excluded = True
        else:
            if rec.get("is_early_recall", False) or rec.get("due_at_delta_seconds", 0) < 0:
                exclusions["by_reason"]["excl_early_recall"] += 1
                excluded = True

        if excluded:
            exclusions["total_excluded"] += 1
            exclusions["by_condition"][cond] += 1
        else:
            clean_groups[cond]["pids"].append(pid)
            clean_groups[cond]["next_workout_starts"].append(float(workout_val))
            clean_groups[cond]["place_recall_counts"].append(float(rec.get("unaided_place_recall_count", 0)))
            clean_groups[cond]["desire_m02_scores"].append(float(rec.get("desire_for_m02_1_to_7", 0)))
            clean_groups[cond]["place_necessity_scores"].append(float(imm.get("place_necessity_1_to_7", 0)))

    # Compute ITT metrics for primary outcome (actual_next_workout_start) across ALL assigned participants
    assigned_a_workout = [float(validate_binary_outcome(p.get("actual_next_workout_start"), participant_id=p.get("participant_id"))) for p in participants if p.get("condition") == "A"]
    assigned_b_workout = [float(validate_binary_outcome(p.get("actual_next_workout_start"), participant_id=p.get("participant_id"))) for p in participants if p.get("condition") == "B"]
    itt_workout_metrics = compute_itt_risk_metrics(assigned_a_workout, assigned_b_workout)

    # Compute outcomes and effect sizes
    group_a = clean_groups["A"]
    group_b = clean_groups["B"]

    n_clean_a = len(group_a["pids"])
    n_clean_b = len(group_b["pids"])

    mean_workout_a, std_workout_a = compute_mean_and_std(group_a["next_workout_starts"])
    mean_workout_b, std_workout_b = compute_mean_and_std(group_b["next_workout_starts"])

    mean_places_a, std_places_a = compute_mean_and_std(group_a["place_recall_counts"])
    mean_places_b, std_places_b = compute_mean_and_std(group_b["place_recall_counts"])
    cohen_places = compute_cohens_d(group_a["place_recall_counts"], group_b["place_recall_counts"])

    mean_desire_a, std_desire_a = compute_mean_and_std(group_a["desire_m02_scores"])
    mean_desire_b, std_desire_b = compute_mean_and_std(group_b["desire_m02_scores"])
    cohen_desire = compute_cohens_d(group_a["desire_m02_scores"], group_b["desire_m02_scores"])

    mean_nec_a, std_nec_a = compute_mean_and_std(group_a["place_necessity_scores"])
    mean_nec_b, std_nec_b = compute_mean_and_std(group_b["place_necessity_scores"])
    cohen_nec = compute_cohens_d(group_a["place_necessity_scores"], group_b["place_necessity_scores"])

    return {
        "status": "PASS",
        "tool": "r03_analyze",
        "execution_status_claim": "NOT_STARTED",
        "denominators": denominators,
        "exclusions": exclusions,
        "clean_sample_size": {
            "total": n_clean_a + n_clean_b,
            "condition_A": n_clean_a,
            "condition_B": n_clean_b,
        },
        "primary_outcomes": {
            "actual_next_workout_start": {
                "metric": "binary",
                "analysis_population": "intention_to_treat",
                "condition_A": {
                    "risk": itt_workout_metrics["risk_A"],
                    "events": itt_workout_metrics["events_A"],
                    "n_assigned": itt_workout_metrics["n_assigned_A"],
                    "mean": round(mean_workout_a, 2),
                    "std": round(std_workout_a, 2),
                    "n": n_clean_a,
                },
                "condition_B": {
                    "risk": itt_workout_metrics["risk_B"],
                    "events": itt_workout_metrics["events_B"],
                    "n_assigned": itt_workout_metrics["n_assigned_B"],
                    "mean": round(mean_workout_b, 2),
                    "std": round(std_workout_b, 2),
                    "n": n_clean_b,
                },
                "risk_difference": itt_workout_metrics["risk_difference"],
                "risk_difference_se": itt_workout_metrics["risk_difference_se"],
                "risk_difference_ci_95": itt_workout_metrics["risk_difference_ci_95"],
                "risk_ratio": itt_workout_metrics["risk_ratio"],
                "risk_ratio_ci_95": itt_workout_metrics["risk_ratio_ci_95"],
                "difference": round(mean_workout_a - mean_workout_b, 2),
            },
        },
        "manipulation_checks": {
            "place_necessity": {
                "condition_A": {"mean": round(mean_nec_a, 2), "std": round(std_nec_a, 2), "n": n_clean_a},
                "condition_B": {"mean": round(mean_nec_b, 2), "std": round(std_nec_b, 2), "n": n_clean_b},
                "difference": round(mean_nec_a - mean_nec_b, 2),
                "cohens_d": round(cohen_nec, 2),
            },
            "unaided_place_recall": {
                "condition_A": {"mean": round(mean_places_a, 2), "std": round(std_places_a, 2), "n": n_clean_a},
                "condition_B": {"mean": round(mean_places_b, 2), "std": round(std_places_b, 2), "n": n_clean_b},
                "difference": round(mean_places_a - mean_places_b, 2),
                "cohens_d": round(cohen_places, 2),
            },
            "desire_for_m02": {
                "condition_A": {"mean": round(mean_desire_a, 2), "std": round(std_desire_a, 2), "n": n_clean_a},
                "condition_B": {"mean": round(mean_desire_b, 2), "std": round(std_desire_b, 2), "n": n_clean_b},
                "difference": round(mean_desire_a - mean_desire_b, 2),
                "cohens_d": round(cohen_desire, 2),
            },
        },
        "interpretation_warning": "SYNTHETIC_DATASET_ONLY. R03 remains NOT_STARTED; no GO claims or real evidence established.",
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, help="Path to JSON dataset to analyze")
    parser.add_argument("--preregistration", type=Path, help="Path to preregistration.v0.1.json")
    parser.add_argument("--generate-synthetic", type=Path, help="Generate synthetic A/B dataset at target path")
    parser.add_argument("--n-samples", type=int, default=100, help="Number of synthetic samples to generate")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic seed for synthetic generator")
    parser.add_argument("--json", action="store_true", help="Output analysis report as clean JSON")

    args = parser.parse_args(argv)

    if args.generate_synthetic:
        data = generate_synthetic_ab_dataset(n_total=args.n_samples, seed=args.seed)
        args.generate_synthetic.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Generated synthetic A/B dataset with {args.n_samples} samples at {args.generate_synthetic}")
        return 0

    if not args.dataset:
        # Default behavior: generate synthetic in memory and analyze
        dataset = generate_synthetic_ab_dataset(n_total=args.n_samples, seed=args.seed)
    else:
        dataset = load_strict_json(args.dataset)

    prereg = None
    if args.preregistration:
        prereg = load_strict_json(args.preregistration)

    try:
        report = analyze_dataset(dataset, prereg)
        if args.json or True:  # Default to JSON output for tooling integration
            print(json.dumps(report, indent=2))
        return 0
    except R03AnalysisError as exc:
        err = {"status": "FAIL", "error": str(exc), "tool": "r03_analyze"}
        print(json.dumps(err, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
