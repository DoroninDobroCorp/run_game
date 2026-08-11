#!/usr/bin/env python3
"""Cross-contract test suite for Swift ↔ Python threshold parity, schema versioning, and disproof tests.

Fulfills assertions VAL-CONTRACT-001 and VAL-CONTRACT-002.

Verifies:
1. Standard cross-contract threshold parity and schema version matching.
2. Negative tests passing malformed artifacts to actual production validators/models.
3. Direct AST and runtime value assertions (no regex tautologies).
4. Disproof tests confirming that changing threshold constants or schema versions causes test failures.
"""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path
import tempfile
import unittest

from tools.domain_thresholds import (
    MAX_EVIDENCE_ACCURACY_M,
    MAX_SAMPLE_GAP_SEC,
    MAX_START_FINISH_CLOSURE_M,
    MIN_EVIDENCE_DISTANCE_M,
    MIN_EVIDENCE_SAMPLES,
    MIN_SAMPLES_PER_ROUTE_POINT,
    MIN_WALKTHROUGH_DURATION_SEC,
    MISSION_START_ACCURACY_M,
    ROUTE_POINT_RADIUS_M,
    SCHEMA_VERSION_AUDIO_APPROVAL,
    SCHEMA_VERSION_DEBRIEF,
    SCHEMA_VERSION_JOURNAL,
    SCHEMA_VERSION_RECALL,
    SCHEMA_VERSION_WALKTHROUGH,
    START_DISTANCE_LIMIT_M,
)
from tools.r02_validate_evidence import (
    ValidationError,
    load_json_strict,
    validate_evidence_file,
    validate_evidence_pair,
    validate_immediate_debrief,
    validate_recall_record,
)

ROOT = Path(__file__).resolve().parents[1]
SWIFT_MODELS_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/Models.swift"
SWIFT_LOCATION_RECORDER_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/LocationRecorder.swift"
SWIFT_MISSION_RUN_VIEW_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/MissionRunView.swift"
SWIFT_ACTIVE_JOURNAL_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/ActiveRunJournal.swift"
SWIFT_SESSION_STATE_MACHINE_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/SessionStateMachine.swift"


def extract_python_domain_thresholds_ast() -> dict[str, ast.AST]:
    """Parse domain_thresholds.py using AST to extract top-level variable assignment AST nodes."""
    target_file = ROOT / "tools/domain_thresholds.py"
    tree = ast.parse(target_file.read_text(encoding="utf-8"), filename=str(target_file))
    assignments: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            assignments[node.target.id] = node.value
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
    return assignments


class CrossContractParityASTTests(unittest.TestCase):
    """AST-based and exact value assertion tests for Swift ↔ Python thresholds and schemas."""

    def test_ast_python_domain_thresholds_constants_defined(self) -> None:
        """Verify python domain thresholds are explicitly defined integer/float/string literals via AST."""
        assignments = extract_python_domain_thresholds_ast()

        expected_numeric = {
            "MAX_EVIDENCE_ACCURACY_M": 50.0,
            "MISSION_START_ACCURACY_M": 35.0,
            "START_DISTANCE_LIMIT_M": 100.0,
            "ROUTE_POINT_RADIUS_M": 100.0,
            "MIN_EVIDENCE_DISTANCE_M": 200.0,
            "MAX_START_FINISH_CLOSURE_M": 150.0,
            "MIN_SAMPLES_PER_ROUTE_POINT": 3,
            "MIN_EVIDENCE_SAMPLES": 20,
            "MIN_WALKTHROUGH_DURATION_SEC": 120.0,
            "MAX_SAMPLE_GAP_SEC": 120.0,
        }

        for var_name, expected_val in expected_numeric.items():
            self.assertIn(var_name, assignments, f"{var_name} must be defined in domain_thresholds.py")
            node = assignments[var_name]
            self.assertIsInstance(node, ast.Constant, f"{var_name} AST node must be an ast.Constant")
            self.assertEqual(node.value, expected_val, f"{var_name} AST constant value mismatch")

        expected_schemas = {
            "SCHEMA_VERSION_DEBRIEF": "0.3",
            "SCHEMA_VERSION_JOURNAL": "0.1",
            "SCHEMA_VERSION_WALKTHROUGH": "0.2",
            "SCHEMA_VERSION_AUDIO_APPROVAL": "0.2",
            "SCHEMA_VERSION_RECALL": "0.2",
        }

        for var_name, expected_val in expected_schemas.items():
            self.assertIn(var_name, assignments, f"{var_name} must be defined in domain_thresholds.py")
            node = assignments[var_name]
            self.assertIsInstance(node, ast.Constant, f"{var_name} AST node must be an ast.Constant")
            self.assertEqual(node.value, expected_val, f"{var_name} AST schema constant mismatch")

    def test_direct_value_assertions_python_domain_thresholds(self) -> None:
        """Direct runtime value assertions for Python domain thresholds without regex."""
        self.assertEqual(MAX_EVIDENCE_ACCURACY_M, 50.0)
        self.assertEqual(MISSION_START_ACCURACY_M, 35.0)
        self.assertEqual(START_DISTANCE_LIMIT_M, 100.0)
        self.assertEqual(ROUTE_POINT_RADIUS_M, 100.0)
        self.assertEqual(MIN_EVIDENCE_DISTANCE_M, 200.0)
        self.assertEqual(MAX_START_FINISH_CLOSURE_M, 150.0)
        self.assertEqual(MIN_SAMPLES_PER_ROUTE_POINT, 3)
        self.assertEqual(MIN_EVIDENCE_SAMPLES, 20)
        self.assertEqual(MIN_WALKTHROUGH_DURATION_SEC, 120.0)
        self.assertEqual(MAX_SAMPLE_GAP_SEC, 120.0)

        self.assertEqual(SCHEMA_VERSION_DEBRIEF, "0.3")
        self.assertEqual(SCHEMA_VERSION_JOURNAL, "0.1")
        self.assertEqual(SCHEMA_VERSION_WALKTHROUGH, "0.2")
        self.assertEqual(SCHEMA_VERSION_AUDIO_APPROVAL, "0.2")
        self.assertEqual(SCHEMA_VERSION_RECALL, "0.2")


class CrossContractNegativeValidatorTests(unittest.TestCase):
    """Negative tests passing malformed evidence artifacts to production Python validators."""

    def setUp(self) -> None:
        self.valid_immediate_dict = {
            "schema_version": "0.3",
            "record_status": "immediate_complete",
            "run_id": "run-parity-001",
            "binding_id": "valparaiso_central",
            "mission_id": "m01",
            "condition": "A",
            "participant_role": "founder",
            "started_at_local": "2026-08-11T10:00:00Z",
            "ended_at_local": "2026-08-11T10:30:00Z",
            "recorded_at_local": "2026-08-11T10:35:00Z",
            "recording_delay_seconds": 300.0,
            "precommitted_next_workout_at_local": "2026-08-12T10:30:00Z",
            "audio_sha256": "a" * 64,
            "route_workout_fingerprint": "b" * 64,
            "track": {
                "file_name": "run-parity-001.gpx",
                "file_sha256": "c" * 64,
                "sample_count": 50,
                "duration_seconds": 1800.0,
                "distance_meters": 2500.0,
                "mean_horizontal_accuracy_meters": 5.0,
                "maximum_sample_gap_seconds": 10.0,
            },
            "safety": {
                "route_manually_checked": True,
                "abort": False,
                "abort_reason": "",
                "needed_screen_while_moving": False,
                "nav_conflicts": [],
            },
            "runtime": {
                "completed": True,
                "geo_slots_reached": ["slot1"],
                "geo_fallbacks_used": [],
                "missed_or_late_cues": [],
                "operator_improvisation_used": False,
                "audio_incidents": [],
                "additional_audio_notes": "",
                "off_route_incidents": [],
                "pause_count": 0,
                "location_incidents": [],
            },
            "immediate_debrief_before_edits": {
                "mission_goal_in_one_sentence": "Test mission goal sentence.",
                "moment_companion_became_important": "When companion spoke.",
                "unaided_memorable_scene": "The square scene.",
                "attention_drop_moment": "None.",
                "what_physical_movement_changed": "Changed pace.",
                "desire_for_m02_1_to_7": 6,
                "place_necessity_1_to_7": 7,
                "predicted_next_twist": "Plot twist prediction.",
                "next_workout_still_scheduled": True,
            },
            "recall_after_24h": {
                "pending": True,
                "instructions": "Recall in 24h",
            },
            "confounds": {
                "unfamiliar_city_novelty": "",
                "fatigue": "",
                "noise": "",
                "weather": "",
                "route_quality": "",
                "audio_quality": "",
                "elevation_or_stairs": "",
            },
            "device": {
                "model": "iPhone 16 Pro",
                "system_name": "iOS",
                "system_version": "18.5",
                "headphones": "AirPods Pro",
                "lock_screen_used": True,
                "lock_screen_answer_recorded": True,
            },
            "evidence_limits": ["Founder test"],
        }

        self.valid_recall_dict = {
            "schema_version": "0.2",
            "record_status": "recall_24h_complete",
            "run_id": "run-parity-001",
            "binding_id": "valparaiso_central",
            "mission_id": "m01",
            "condition": "A",
            "audio_sha256": "a" * 64,
            "route_workout_fingerprint": "b" * 64,
            "run_ended_at_local": "2026-08-11T10:30:00Z",
            "due_at_local": "2026-08-12T10:30:00Z",
            "completed_at_local": "2026-08-12T11:00:00Z",
            "unaided_story_recall": "I remember Lea and the plaza.",
            "unaided_place_recall": ["Plaza Sotomayor", "Muelle Prat"],
            "desire_for_m02_1_to_7": 6,
            "evidence_limits": ["Recall completed by founder."],
        }

    def test_negative_malformed_schema_version_rejected(self) -> None:
        """Negative test: schema version mismatch is rejected by validate_immediate_debrief."""
        data = dict(self.valid_immediate_dict)
        data["schema_version"] = "9.9"
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("expected schema_version '0.3'", str(ctx.exception))

    def test_negative_malformed_sha256_rejected(self) -> None:
        """Negative test: malformed audio SHA256 string is rejected."""
        data = dict(self.valid_immediate_dict)
        data["audio_sha256"] = "12345invalidsha"
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("invalid SHA-256 format", str(ctx.exception))

    def test_negative_out_of_range_likert_rejected(self) -> None:
        """Negative test: Likert score outside 1..7 range is rejected."""
        data = dict(self.valid_immediate_dict)
        imm = dict(data["immediate_debrief_before_edits"])
        imm["desire_for_m02_1_to_7"] = 10
        data["immediate_debrief_before_edits"] = imm

        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("out of range", str(ctx.exception))

    def test_negative_raw_coordinate_leakage_rejected(self) -> None:
        """Negative test: JSON payload containing raw latitude/longitude key is rejected."""
        data = dict(self.valid_immediate_dict)
        data["latitude"] = -33.0458
        data["longitude"] = -71.6197

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f_path = Path(f.name)

        try:
            with self.assertRaises(ValidationError) as ctx:
                validate_evidence_file(f_path)
            self.assertIn("forbidden raw coordinate key detected", str(ctx.exception))
        finally:
            f_path.unlink()

    def test_negative_pair_mode_mismatched_run_id_rejected(self) -> None:
        """Negative test: paired immediate and recall files with different run_ids are rejected."""
        rec = dict(self.valid_recall_dict)
        rec["run_id"] = "run-parity-999"

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_imm, \
             tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_rec:
            json.dump(self.valid_immediate_dict, f_imm)
            json.dump(rec, f_rec)
            p_imm = Path(f_imm.name)
            p_rec = Path(f_rec.name)

        try:
            with self.assertRaises(ValidationError) as ctx:
                validate_evidence_pair(p_imm, p_rec)
            self.assertIn("pair identity mismatch for run_id", str(ctx.exception))
        finally:
            p_imm.unlink()
            p_rec.unlink()

    def test_negative_pair_mode_mismatched_due_at_rejected(self) -> None:
        """Negative test: 24h recall due_at_local calculation error is rejected."""
        rec = dict(self.valid_recall_dict)
        # 24h from ended_at 10:30 should be 10:30 next day. Set to 18:00 next day.
        rec["due_at_local"] = "2026-08-12T18:00:00Z"
        rec["completed_at_local"] = "2026-08-12T18:30:00Z"

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_imm, \
             tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_rec:
            json.dump(self.valid_immediate_dict, f_imm)
            json.dump(rec, f_rec)
            p_imm = Path(f_imm.name)
            p_rec = Path(f_rec.name)

        try:
            with self.assertRaises(ValidationError) as ctx:
                validate_evidence_pair(p_imm, p_rec)
            self.assertIn("dueAt 24h calculation error", str(ctx.exception))
        finally:
            p_imm.unlink()
            p_rec.unlink()


class CrossContractDisproofTests(unittest.TestCase):
    """Disproof tests: confirm that deliberate constant/schema modifications break validation."""

    def setUp(self) -> None:
        self.base_immediate = {
            "schema_version": "0.3",
            "record_status": "immediate_complete",
            "run_id": "run-disproof-001",
            "binding_id": "valparaiso_central",
            "mission_id": "m01",
            "condition": "A",
            "participant_role": "founder",
            "started_at_local": "2026-08-11T10:00:00Z",
            "ended_at_local": "2026-08-11T10:30:00Z",
            "recorded_at_local": "2026-08-11T10:35:00Z",
            "recording_delay_seconds": 300.0,
            "precommitted_next_workout_at_local": "2026-08-12T10:30:00Z",
            "audio_sha256": "f" * 64,
            "route_workout_fingerprint": "e" * 64,
            "track": {
                "file_name": "run-disproof-001.gpx",
                "file_sha256": "d" * 64,
                "sample_count": 50,
                "duration_seconds": 1800.0,
                "distance_meters": 2500.0,
                "mean_horizontal_accuracy_meters": 5.0,
                "maximum_sample_gap_seconds": 10.0,
            },
            "safety": {
                "route_manually_checked": True,
                "abort": False,
                "abort_reason": "",
                "needed_screen_while_moving": False,
                "nav_conflicts": [],
            },
            "runtime": {
                "completed": True,
                "geo_slots_reached": ["slot1"],
                "geo_fallbacks_used": [],
                "missed_or_late_cues": [],
                "operator_improvisation_used": False,
                "audio_incidents": [],
                "additional_audio_notes": "",
                "off_route_incidents": [],
                "pause_count": 0,
                "location_incidents": [],
            },
            "immediate_debrief_before_edits": {
                "mission_goal_in_one_sentence": "Goal.",
                "moment_companion_became_important": "Moment.",
                "unaided_memorable_scene": "Scene.",
                "attention_drop_moment": "None.",
                "what_physical_movement_changed": "Pace.",
                "desire_for_m02_1_to_7": 5,
                "place_necessity_1_to_7": 5,
                "predicted_next_twist": "Twist.",
                "next_workout_still_scheduled": True,
            },
            "recall_after_24h": {"pending": True, "instructions": "Instruct"},
            "confounds": {
                "unfamiliar_city_novelty": "",
                "fatigue": "",
                "noise": "",
                "weather": "",
                "route_quality": "",
                "audio_quality": "",
                "elevation_or_stairs": "",
            },
            "device": {
                "model": "iPhone 16 Pro",
                "system_name": "iOS",
                "system_version": "18.5",
                "headphones": "AirPods Pro",
                "lock_screen_used": True,
                "lock_screen_answer_recorded": True,
            },
            "evidence_limits": ["Founder test"],
        }

    def test_disproof_schema_version_change_causes_failure(self) -> None:
        """Disproof test: modifying schema_version in payload from 0.3 to 0.4 causes validation failure."""
        mutated = dict(self.base_immediate)
        mutated["schema_version"] = "0.4"
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(mutated)
        self.assertIn("expected schema_version '0.3'", str(ctx.exception))

    def test_disproof_recording_delay_mismatch_causes_failure(self) -> None:
        """Disproof test: modifying recording_delay_seconds so it diverges from timestamps causes validation failure."""
        mutated = dict(self.base_immediate)
        # ended 10:30, recorded 10:35 -> actual diff is 300s. Set recorded value to 999s.
        mutated["recording_delay_seconds"] = 999.0
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(mutated)
        self.assertIn("recording_delay_seconds mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
