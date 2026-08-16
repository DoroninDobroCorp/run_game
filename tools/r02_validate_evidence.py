#!/usr/bin/env python3
"""Fail-closed validator for schema 0.4 immediate debrief and 0.3 24h recall JSON evidence files.

Fulfills assertions VAL-VALIDATOR-001 and VAL-VALIDATOR-002.

Validates:
- Duplicate JSON keys rejection
- Non-finite numbers (NaN/Infinity) rejection
- Schema 0.4 for immediate debrief records (recordStatus == "immediate_complete" or "draft_incomplete")
- Schema 0.3 for recall records (recordStatus == "recall_24h_complete" or "recall_24h_draft")
- SHA256 hex string format enforcement (64 hex characters)
- Likert score range enforcement (1..7) for integer scores
- Timestamp ordering and delay calculations (recordingDelaySeconds, completedAtLocal >= dueAtLocal)
- Detection and flagging of delayed debriefs (> 3600 seconds) as confounds
- Raw coordinate / location leakage checks
- Pair mode (--immediate and --recall): exact identity equality (run_id, binding_id, mission_id, condition),
  timestamp sequence ordering (recall.completedAtLocal >= immediate.recordedAtLocal),
  dueAt calculation verification (dueAtLocal == run_ended_at_local + 86400s within 1s tolerance),
  and flagging of delayed debriefs (> 3600 seconds) as confounds.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.domain_thresholds import SCHEMA_VERSION_DEBRIEF, SCHEMA_VERSION_RECALL  # noqa: E402

SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
LAT_LON_KEY_RE = re.compile(r"^(latitude|longitude|lat|lon|lats|lons|coord|coordinates|track_points|points)$", re.IGNORECASE)
DEBRIEF_DELAY_CONFOUND_THRESHOLD_SEC = 3600.0


class ValidationError(ValueError):
    """Validation failure exception with detailed reasons."""


def _reject_json_constant(value: str) -> None:
    raise ValidationError(f"non-finite JSON constant {value!r} is forbidden")


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON key {key!r} is forbidden")
        result[key] = value
    return result


def load_json_strict(path: Path) -> Any:
    """Load JSON file disallowing duplicate keys and NaN/Infinity constants."""
    if not path.is_file():
        raise ValidationError(f"file not found: {path}")
    try:
        content = path.read_text(encoding="utf-8")
        return json.loads(
            content,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_json_object_without_duplicates,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid JSON structure: {exc}") from exc


def _check_no_raw_coordinate_leakage(obj: Any, path: str = "$") -> None:
    """Recursively inspect JSON object for key names or structures leaking raw GPS coordinates."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            current_path = f"{path}.{key}"
            if LAT_LON_KEY_RE.match(key):
                # Allow 'track' summary if present in debrief, but check its internal structure
                if key in {"track", "track_summary"} and isinstance(val, dict):
                    pass
                else:
                    raise ValidationError(f"forbidden raw coordinate key detected: {current_path}")
            _check_no_raw_coordinate_leakage(val, current_path)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _check_no_raw_coordinate_leakage(item, f"{path}[{idx}]")
    elif isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValidationError(f"non-finite float detected at {path}: {obj}")


def _validate_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.match(value):
        raise ValidationError(f"invalid SHA-256 format for {label}: {value!r}")
    return value.lower()


def _validate_likert_score(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"Likert score for {label} must be an integer: {value!r}")
    if not (1 <= value <= 7):
        raise ValidationError(f"Likert score for {label} out of range (1..7): {value}")
    return value


def _parse_iso_timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"missing or empty timestamp for {label}")
    from datetime import datetime
    iso_str = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            raise ValidationError(f"naive timestamp lacking timezone offset or Z for {label}: {value!r}")
        return value
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"invalid ISO-8601 timestamp for {label}: {value!r} ({exc})") from exc


def _timestamp_to_seconds(value: str) -> float:
    from datetime import datetime
    iso_str = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(iso_str)
    return dt.timestamp()


def validate_immediate_debrief(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a schema 0.4 immediate debrief JSON structure."""
    if not isinstance(data, dict):
        raise ValidationError("root payload must be a JSON object")

    _check_no_raw_coordinate_leakage(data)

    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION_DEBRIEF:
        raise ValidationError(f"expected schema_version {SCHEMA_VERSION_DEBRIEF!r}, got {schema_version!r}")

    record_status = data.get("record_status")
    allowed_statuses = {"immediate_complete", "draft_incomplete"}
    if record_status not in allowed_statuses:
        raise ValidationError(f"invalid record_status {record_status!r}; expected one of {allowed_statuses}")

    # Check required top-level string fields
    for field in ["participant_id", "run_id", "binding_id", "mission_id", "condition", "participant_role", "route_workout_fingerprint"]:
        val = data.get(field)
        if not isinstance(val, str) or not val.strip():
            raise ValidationError(f"missing or empty required field {field!r}")

    _validate_sha256(data.get("audio_sha256"), "audio_sha256")

    # Timestamps
    started_at = _parse_iso_timestamp(data.get("started_at_local"), "started_at_local")
    ended_at = _parse_iso_timestamp(data.get("ended_at_local"), "ended_at_local")
    recorded_at = _parse_iso_timestamp(data.get("recorded_at_local"), "recorded_at_local")
    precommitted_at = _parse_iso_timestamp(data.get("precommitted_next_workout_at_local"), "precommitted_next_workout_at_local")

    t_started = _timestamp_to_seconds(started_at)
    t_ended = _timestamp_to_seconds(ended_at)
    t_recorded = _timestamp_to_seconds(recorded_at)
    t_precommitted = _timestamp_to_seconds(precommitted_at)

    if t_ended < t_started:
        raise ValidationError(f"ended_at_local ({ended_at}) is before started_at_local ({started_at})")

    if t_recorded < t_ended:
        raise ValidationError(f"recorded_at_local ({recorded_at}) is before ended_at_local ({ended_at})")

    if t_precommitted < t_ended:
        raise ValidationError(f"precommitted_next_workout_at_local ({precommitted_at}) is before ended_at_local ({ended_at})")

    # Recording delay seconds verification
    rec_delay = data.get("recording_delay_seconds")
    if not isinstance(rec_delay, (int, float)) or not math.isfinite(rec_delay):
        raise ValidationError(f"recording_delay_seconds must be a finite number: {rec_delay!r}")

    if rec_delay < 0:
        raise ValidationError(f"recording_delay_seconds cannot be negative: {rec_delay}")

    expected_delay = t_recorded - t_ended
    if abs(rec_delay - expected_delay) > 1.0:
        raise ValidationError(f"recording_delay_seconds mismatch: recorded {rec_delay}, expected {expected_delay:.2f}")

    # Immediate debrief evidence
    imm = data.get("immediate_debrief_before_edits")
    if not isinstance(imm, dict):
        raise ValidationError("missing or invalid immediate_debrief_before_edits object")

    if record_status == "immediate_complete":
        for field in [
            "mission_goal_in_one_sentence",
            "moment_companion_became_important",
            "unaided_memorable_scene",
            "attention_drop_moment",
            "what_physical_movement_changed",
            "predicted_next_twist",
        ]:
            val = imm.get(field)
            if not isinstance(val, str) or not val.strip():
                raise ValidationError(f"missing or empty immediate debrief field {field!r}")

        _validate_likert_score(imm.get("desire_for_m02_1_to_7"), "desire_for_m02_1_to_7")
        _validate_likert_score(imm.get("place_necessity_1_to_7"), "place_necessity_1_to_7")

        if not isinstance(imm.get("next_workout_still_scheduled"), bool):
            raise ValidationError("next_workout_still_scheduled must be a boolean")

    # Safety & Runtime consistency
    safety = data.get("safety")
    if not isinstance(safety, dict):
        raise ValidationError("missing or invalid safety object")
    if not isinstance(safety.get("route_manually_checked"), bool):
        raise ValidationError("safety.route_manually_checked must be a boolean")
    safety_abort = safety.get("abort")
    if not isinstance(safety_abort, bool):
        raise ValidationError("safety.abort must be a boolean")

    abort_reason = safety.get("abort_reason")
    if abort_reason is not None and not isinstance(abort_reason, str):
        raise ValidationError("safety.abort_reason must be a string")

    runtime = data.get("runtime")
    if not isinstance(runtime, dict):
        raise ValidationError("missing or invalid runtime object")
    runtime_completed = runtime.get("completed")
    if not isinstance(runtime_completed, bool):
        raise ValidationError("runtime.completed must be a boolean")

    if safety_abort and runtime_completed:
        raise ValidationError("run cannot be both aborted (safety.abort=True) and completed (runtime.completed=True)")

    if record_status == "immediate_complete":
        if safety_abort:
            if runtime_completed:
                raise ValidationError("aborted run must have runtime.completed set to False")
            if not isinstance(abort_reason, str) or not abort_reason.strip():
                raise ValidationError("aborted immediate debrief requires non-empty safety.abort_reason")
        else:
            if not runtime_completed:
                raise ValidationError("non-aborted immediate_complete record requires runtime.completed to be True")

    # Device
    device = data.get("device")
    if not isinstance(device, dict):
        raise ValidationError("missing or invalid device object")
    if record_status == "immediate_complete":
        for field in ["model", "system_name", "system_version", "headphones"]:
            value = device.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"missing or empty device field {field!r}")
        if not isinstance(device.get("lock_screen_used"), bool):
            raise ValidationError("device.lock_screen_used must be a boolean")
        if not isinstance(device.get("lock_screen_answer_recorded"), bool):
            raise ValidationError("device.lock_screen_answer_recorded must be a boolean")

    # Track Summary check
    track = data.get("track")
    if runtime_completed:
        if track is None or not isinstance(track, dict):
            raise ValidationError("completed record requires a valid track summary object")

    if track is not None:
        if not isinstance(track, dict):
            raise ValidationError("track must be an object if present")
        _validate_sha256(track.get("file_sha256"), "track.file_sha256")
        file_name = track.get("file_name")
        if not isinstance(file_name, str) or not file_name.strip():
            raise ValidationError("missing or empty track.file_name")
        sample_count = track.get("sample_count")
        if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count <= 0:
            raise ValidationError(f"track.sample_count must be a positive integer: {sample_count!r}")
        for num_field in ["duration_seconds", "distance_meters", "mean_horizontal_accuracy_meters", "maximum_sample_gap_seconds"]:
            val = track.get(num_field)
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0:
                raise ValidationError(f"track.{num_field} must be a non-negative number: {val!r}")
        if "started_at" in track:
            _parse_iso_timestamp(track["started_at"], "track.started_at")
        if "ended_at" in track:
            _parse_iso_timestamp(track["ended_at"], "track.ended_at")

    # Check delayed debrief confound
    confound_flagged = rec_delay > DEBRIEF_DELAY_CONFOUND_THRESHOLD_SEC

    return {
        "valid": True,
        "type": "immediate_debrief",
        "schema_version": schema_version,
        "record_status": record_status,
        "run_id": data.get("run_id"),
        "recording_delay_seconds": rec_delay,
        "confound_delayed_debrief": confound_flagged,
        "raw_data": data,
    }


def validate_recall_record(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a schema 0.3 24h recall JSON structure."""
    if not isinstance(data, dict):
        raise ValidationError("root payload must be a JSON object")

    _check_no_raw_coordinate_leakage(data)

    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION_RECALL:
        raise ValidationError(f"expected schema_version {SCHEMA_VERSION_RECALL!r}, got {schema_version!r}")

    record_status = data.get("record_status")
    allowed_statuses = {"recall_24h_complete", "recall_24h_draft"}
    if record_status not in allowed_statuses:
        raise ValidationError(f"invalid record_status {record_status!r}; expected one of {allowed_statuses}")

    for field in ["participant_id", "run_id", "binding_id", "mission_id", "condition", "route_workout_fingerprint"]:
        val = data.get(field)
        if not isinstance(val, str) or not val.strip():
            raise ValidationError(f"missing or empty required field {field!r}")

    _validate_sha256(data.get("audio_sha256"), "audio_sha256")

    run_ended_at = _parse_iso_timestamp(data.get("run_ended_at_local"), "run_ended_at_local")
    due_at = _parse_iso_timestamp(data.get("due_at_local"), "due_at_local")
    completed_at = _parse_iso_timestamp(data.get("completed_at_local"), "completed_at_local")

    t_ended = _timestamp_to_seconds(run_ended_at)
    t_due = _timestamp_to_seconds(due_at)
    t_completed = _timestamp_to_seconds(completed_at)

    if t_due < t_ended:
        raise ValidationError(f"due_at_local ({due_at}) is before run_ended_at_local ({run_ended_at})")

    if t_completed < t_ended:
        raise ValidationError(f"completed_at_local ({completed_at}) is before run_ended_at_local ({run_ended_at})")

    # Reject recall completed before dueAt
    if record_status == "recall_24h_complete":
        if t_completed < t_due - 1.0:
            raise ValidationError(
                f"recall completed before dueAt: completedAtLocal ({completed_at}) < dueAtLocal ({due_at})"
            )

        story_recall = data.get("unaided_story_recall")
        if not isinstance(story_recall, str) or not story_recall.strip():
            raise ValidationError("missing or empty unaided_story_recall")

        place_recall = data.get("unaided_place_recall")
        if not isinstance(place_recall, list) or len(place_recall) == 0:
            raise ValidationError("unaided_place_recall must be a non-empty array of place strings")
        for idx, item in enumerate(place_recall):
            if not isinstance(item, str) or not item.strip():
                raise ValidationError(f"invalid place item at index {idx}: {item!r}")

        _validate_likert_score(data.get("desire_for_m02_1_to_7"), "desire_for_m02_1_to_7")

    return {
        "valid": True,
        "type": "recall_24h",
        "schema_version": schema_version,
        "record_status": record_status,
        "run_id": data.get("run_id"),
        "due_at_local": due_at,
        "completed_at_local": completed_at,
        "raw_data": data,
    }


def validate_evidence_file(path: Path) -> dict[str, Any]:
    """Validate evidence JSON file (immediate debrief or 24h recall)."""
    data = load_json_strict(path)
    _check_no_raw_coordinate_leakage(data)

    if not isinstance(data, dict):
        raise ValidationError("root JSON payload must be an object")

    schema_version = data.get("schema_version")
    record_status = str(data.get("record_status", ""))

    if schema_version == SCHEMA_VERSION_DEBRIEF or "immediate" in record_status or "draft_incomplete" in record_status:
        return validate_immediate_debrief(data)
    elif schema_version == SCHEMA_VERSION_RECALL or "recall" in record_status:
        return validate_recall_record(data)
    else:
        raise ValidationError(f"unrecognized evidence schemaVersion {schema_version!r} and recordStatus {record_status!r}")


def validate_evidence_pair(immediate_path: Path, recall_path: Path) -> dict[str, Any]:
    """Validate paired immediate debrief and 24h recall evidence files (VAL-VALIDATOR-002)."""
    imm_res = validate_evidence_file(immediate_path)
    if imm_res["type"] != "immediate_debrief":
        raise ValidationError(f"immediate evidence file {immediate_path.name} is not an immediate debrief (got {imm_res['type']})")

    rec_res = validate_evidence_file(recall_path)
    if rec_res["type"] != "recall_24h":
        raise ValidationError(f"recall evidence file {recall_path.name} is not a 24h recall record (got {rec_res['type']})")

    if imm_res["record_status"] != "immediate_complete" or rec_res["record_status"] != "recall_24h_complete":
        raise ValidationError(
            f"pair mode requires complete records, got immediate record_status={imm_res['record_status']!r} and recall record_status={rec_res['record_status']!r}"
        )

    imm_data = imm_res["raw_data"]
    rec_data = rec_res["raw_data"]

    # 1. Identity equality checks
    for key in ["participant_id", "run_id", "binding_id", "mission_id", "condition"]:
        imm_val = imm_data.get(key)
        rec_val = rec_data.get(key)
        if imm_val != rec_val:
            raise ValidationError(f"pair identity mismatch for {key}: immediate={imm_val!r}, recall={rec_val!r}")

    # Audio SHA256 & Fingerprint equality
    if imm_data.get("audio_sha256", "").lower() != rec_data.get("audio_sha256", "").lower():
        raise ValidationError(
            f"pair identity mismatch for audio_sha256: immediate={imm_data.get('audio_sha256')!r}, recall={rec_data.get('audio_sha256')!r}"
        )
    if imm_data.get("route_workout_fingerprint") != rec_data.get("route_workout_fingerprint"):
        raise ValidationError(
            f"pair identity mismatch for route_workout_fingerprint: immediate={imm_data.get('route_workout_fingerprint')!r}, recall={rec_data.get('route_workout_fingerprint')!r}"
        )

    # 2. Timestamp ordering checks
    imm_ended = _timestamp_to_seconds(imm_data["ended_at_local"])
    imm_recorded = _timestamp_to_seconds(imm_data["recorded_at_local"])
    rec_ended = _timestamp_to_seconds(rec_data["run_ended_at_local"])
    rec_due = _timestamp_to_seconds(rec_data["due_at_local"])
    rec_completed = _timestamp_to_seconds(rec_data["completed_at_local"])

    # Verify run_ended_at matching between immediate and recall
    if abs(imm_ended - rec_ended) > 1.0:
        raise ValidationError(
            f"timestamp mismatch for run ended time: immediate ended_at_local={imm_data['ended_at_local']}, recall run_ended_at_local={rec_data['run_ended_at_local']}"
        )

    # Sequence ordering: recall.completedAtLocal >= immediate.recordedAtLocal
    if rec_completed < imm_recorded:
        raise ValidationError(
            f"timestamp sequence violation: recall completedAtLocal ({rec_data['completed_at_local']}) is before immediate recordedAtLocal ({imm_data['recorded_at_local']})"
        )

    # 3. dueAt 24h calculation verification: dueAtLocal == run_ended_at_local + 86400s (within 1s tolerance)
    expected_due = imm_ended + 86400.0
    if abs(rec_due - expected_due) > 1.0:
        raise ValidationError(
            f"dueAt 24h calculation error: due_at_local={rec_data['due_at_local']} (diff from endedAt + 24h is {rec_due - expected_due:.2f}s)"
        )

    # 4. Delayed debrief confound check
    rec_delay = imm_res["recording_delay_seconds"]
    confound_flagged = rec_res.get("confound_delayed_debrief", False) or imm_res.get("confound_delayed_debrief", False)

    return {
        "valid": True,
        "type": "evidence_pair",
        "run_id": imm_data["run_id"],
        "immediate_file": str(immediate_path),
        "recall_file": str(recall_path),
        "recording_delay_seconds": rec_delay,
        "confound_delayed_debrief": confound_flagged,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path, help="Evidence JSON files to validate")
    parser.add_argument("--immediate", type=Path, help="Immediate debrief JSON file for pair validation")
    parser.add_argument("--recall", type=Path, help="24h recall JSON file for pair validation")
    args = parser.parse_args(argv)

    if (args.immediate is not None) != (args.recall is not None):
        parser.error("pair mode requires BOTH --immediate and --recall flags")

    failures = 0
    if args.immediate and args.recall:
        try:
            res = validate_evidence_pair(args.immediate, args.recall)
            print(f"[PASS] Pair mode: {args.immediate.name} + {args.recall.name} (run_id={res['run_id']})")
            if res.get("confound_delayed_debrief"):
                print(f"       WARNING: Debrief delayed > 1 hour ({res['recording_delay_seconds']:.1f}s); flagged as confound.")
        except ValidationError as exc:
            failures += 1
            print(f"[FAIL] Pair mode ({args.immediate.name} + {args.recall.name}): {exc}", file=sys.stderr)
    elif args.files:
        for file_path in args.files:
            try:
                res = validate_evidence_file(file_path)
                print(f"[PASS] {file_path.name}: {res['type']} ({res['record_status']})")
                if res.get("confound_delayed_debrief"):
                    print(f"       WARNING: Debrief delayed > 1 hour ({res['recording_delay_seconds']:.1f}s); flagged as confound.")
            except ValidationError as exc:
                failures += 1
                print(f"[FAIL] {file_path.name}: {exc}", file=sys.stderr)
    else:
        parser.print_help()
        return 2

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
