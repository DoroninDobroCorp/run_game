#!/usr/bin/env python3
"""Unit tests for tools/r02_validate_evidence.py evidence validator script.

Fulfills assertions VAL-VALIDATOR-001 and VAL-VALIDATOR-002.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.r02_validate_evidence import (
    ValidationError,
    load_json_strict,
    validate_evidence_file,
    validate_evidence_pair,
    validate_immediate_debrief,
    validate_recall_record,
)


class TestR02ValidateEvidence(unittest.TestCase):
    """Test suite for schema 0.4 immediate and 0.3 recall evidence validation."""

    def setUp(self) -> None:
        self.valid_immediate_dict = {
            "schema_version": "0.4",
            "record_status": "immediate_complete",
            "participant_id": "participant_founder_001",
            "run_id": "run-12345",
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
                "file_name": "run-12345.gpx",
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
            "schema_version": "0.3",
            "record_status": "recall_24h_complete",
            "participant_id": "participant_founder_001",
            "run_id": "run-12345",
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

    def test_valid_immediate_debrief_passes(self) -> None:
        res = validate_immediate_debrief(self.valid_immediate_dict)
        self.assertTrue(res["valid"])
        self.assertEqual(res["type"], "immediate_debrief")
        self.assertFalse(res["confound_delayed_debrief"])

    def test_valid_aborted_immediate_debrief_passes(self) -> None:
        """VAL-VALIDATOR-005: Aborted completed immediate debrief with abort=True and runtime.completed=False passes."""
        aborted_data = json.loads(json.dumps(self.valid_immediate_dict))
        aborted_data["safety"]["abort"] = True
        aborted_data["safety"]["abort_reason"] = "Hardware malfunction required safety halt"
        aborted_data["runtime"]["completed"] = False
        aborted_data["track"] = None

        res = validate_immediate_debrief(aborted_data)
        self.assertTrue(res["valid"])
        self.assertEqual(res["type"], "immediate_debrief")
        self.assertEqual(res["record_status"], "immediate_complete")

    def test_valid_aborted_immediate_debrief_with_partial_track_passes(self) -> None:
        """VAL-VALIDATOR-005: Aborted completed immediate debrief with partial GPX summary passes."""
        aborted_data = json.loads(json.dumps(self.valid_immediate_dict))
        aborted_data["safety"]["abort"] = True
        aborted_data["safety"]["abort_reason"] = "User aborted after 10 minutes"
        aborted_data["runtime"]["completed"] = False

        res = validate_immediate_debrief(aborted_data)
        self.assertTrue(res["valid"])

    def test_aborted_immediate_debrief_rejects_empty_abort_reason(self) -> None:
        """VAL-VALIDATOR-005: Aborted immediate debrief without non-empty abort_reason is rejected."""
        aborted_data = json.loads(json.dumps(self.valid_immediate_dict))
        aborted_data["safety"]["abort"] = True
        aborted_data["safety"]["abort_reason"] = "   "
        aborted_data["runtime"]["completed"] = False

        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(aborted_data)
        self.assertIn("aborted immediate debrief requires non-empty safety.abort_reason", str(ctx.exception))

    def test_aborted_immediate_debrief_rejects_runtime_completed_true(self) -> None:
        """VAL-VALIDATOR-005: Aborted immediate debrief with runtime.completed=True is rejected."""
        aborted_data = json.loads(json.dumps(self.valid_immediate_dict))
        aborted_data["safety"]["abort"] = True
        aborted_data["safety"]["abort_reason"] = "Aborted run"
        aborted_data["runtime"]["completed"] = True

        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(aborted_data)
        self.assertIn("run cannot be both aborted", str(ctx.exception))

    def test_valid_recall_record_passes(self) -> None:
        res = validate_recall_record(self.valid_recall_dict)
        self.assertTrue(res["valid"])
        self.assertEqual(res["type"], "recall_24h")

    def test_reject_missing_participant_id_in_immediate(self) -> None:
        data = dict(self.valid_immediate_dict)
        data.pop("participant_id")
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("missing or empty required field 'participant_id'", str(ctx.exception))

        data["participant_id"] = "   "
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("missing or empty required field 'participant_id'", str(ctx.exception))

    def test_reject_missing_participant_id_in_recall(self) -> None:
        data = dict(self.valid_recall_dict)
        data.pop("participant_id")
        with self.assertRaises(ValidationError) as ctx:
            validate_recall_record(data)
        self.assertIn("missing or empty required field 'participant_id'", str(ctx.exception))

        data["participant_id"] = ""
        with self.assertRaises(ValidationError) as ctx:
            validate_recall_record(data)
        self.assertIn("missing or empty required field 'participant_id'", str(ctx.exception))

    def test_reject_duplicate_keys(self) -> None:
        json_str = '{"schema_version": "0.4", "schema_version": "0.4", "run_id": "123"}'
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            f.write(json_str)
            f_path = Path(f.name)

        try:
            with self.assertRaises(ValidationError) as ctx:
                load_json_strict(f_path)
            self.assertIn("duplicate JSON key", str(ctx.exception))
        finally:
            f_path.unlink()

    def test_reject_nan_infinity(self) -> None:
        for val in ["NaN", "Infinity", "-Infinity"]:
            json_str = f'{{"schema_version": "0.4", "recording_delay_seconds": {val}}}'
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
                f.write(json_str)
                f_path = Path(f.name)

            try:
                with self.assertRaises(ValidationError) as ctx:
                    load_json_strict(f_path)
                self.assertIn("non-finite JSON constant", str(ctx.exception))
            finally:
                f_path.unlink()

    def test_reject_invalid_sha_format(self) -> None:
        data = dict(self.valid_immediate_dict)
        data["audio_sha256"] = "invalid-sha-12345"
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("invalid SHA-256 format", str(ctx.exception))

    def test_reject_out_of_range_likert_scores(self) -> None:
        data = dict(self.valid_immediate_dict)
        data["immediate_debrief_before_edits"] = dict(self.valid_immediate_dict["immediate_debrief_before_edits"])

        # Test 0
        data["immediate_debrief_before_edits"]["desire_for_m02_1_to_7"] = 0
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("out of range", str(ctx.exception))

        # Test 8
        data["immediate_debrief_before_edits"]["desire_for_m02_1_to_7"] = 8
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("out of range", str(ctx.exception))

        # Test float Likert score
        data["immediate_debrief_before_edits"]["desire_for_m02_1_to_7"] = 5.5
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("must be an integer", str(ctx.exception))

    def test_flag_delayed_debrief_as_confound(self) -> None:
        data = dict(self.valid_immediate_dict)
        # ended at 10:30, recorded at 12:30 -> 7200 seconds delay (> 3600s)
        data["ended_at_local"] = "2026-08-11T10:30:00Z"
        data["recorded_at_local"] = "2026-08-11T12:30:00Z"
        data["recording_delay_seconds"] = 7200.0

        res = validate_immediate_debrief(data)
        self.assertTrue(res["valid"])
        self.assertTrue(res["confound_delayed_debrief"])

    def test_reject_recall_completed_before_due_at(self) -> None:
        data = dict(self.valid_recall_dict)
        # due at 10:30 on 2026-08-12, but completed at 10:00
        data["due_at_local"] = "2026-08-12T10:30:00Z"
        data["completed_at_local"] = "2026-08-12T10:00:00Z"

        with self.assertRaises(ValidationError) as ctx:
            validate_recall_record(data)
        self.assertIn("recall completed before dueAt", str(ctx.exception))

    def test_reject_raw_coordinate_leakage(self) -> None:
        data = dict(self.valid_immediate_dict)
        data["coordinates"] = [{"latitude": -33.045, "longitude": -71.62}]

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f_path = Path(f.name)

        try:
            with self.assertRaises(ValidationError) as ctx:
                validate_evidence_file(f_path)
            self.assertIn("forbidden raw coordinate key detected", str(ctx.exception))
        finally:
            f_path.unlink()

    def test_validate_evidence_file_end_to_end(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(self.valid_immediate_dict, f)
            f_path = Path(f.name)

        try:
            res = validate_evidence_file(f_path)
            self.assertTrue(res["valid"])
            self.assertEqual(res["type"], "immediate_debrief")
        finally:
            f_path.unlink()

    def test_pair_mode_success(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_imm, \
             tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_rec:
            json.dump(self.valid_immediate_dict, f_imm)
            json.dump(self.valid_recall_dict, f_rec)
            path_imm = Path(f_imm.name)
            path_rec = Path(f_rec.name)

        try:
            res = validate_evidence_pair(path_imm, path_rec)
            self.assertTrue(res["valid"])
            self.assertEqual(res["type"], "evidence_pair")
            self.assertEqual(res["run_id"], "run-12345")
            self.assertFalse(res["confound_delayed_debrief"])
        finally:
            path_imm.unlink()
            path_rec.unlink()

    def test_pair_mode_rejects_participant_id_mismatch(self) -> None:
        rec_data = dict(self.valid_recall_dict)
        rec_data["participant_id"] = "participant_other_002"

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_imm, \
             tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_rec:
            json.dump(self.valid_immediate_dict, f_imm)
            json.dump(rec_data, f_rec)
            path_imm = Path(f_imm.name)
            path_rec = Path(f_rec.name)

        try:
            with self.assertRaises(ValidationError) as ctx:
                validate_evidence_pair(path_imm, path_rec)
            self.assertIn("pair identity mismatch for participant_id", str(ctx.exception))
        finally:
            path_imm.unlink()
            path_rec.unlink()

    def test_validate_example_fixtures_single_and_pair(self) -> None:
        root_dir = Path(__file__).resolve().parents[1]
        run_fixture = root_dir / "research/r02/fixtures/field_run.example.json"
        recall_fixture = root_dir / "research/r02/fixtures/field_recall.example.json"

        imm_res = validate_evidence_file(run_fixture)
        self.assertTrue(imm_res["valid"])
        self.assertEqual(imm_res["type"], "immediate_debrief")

        rec_res = validate_evidence_file(recall_fixture)
        self.assertTrue(rec_res["valid"])
        self.assertEqual(rec_res["type"], "recall_24h")

        pair_res = validate_evidence_pair(run_fixture, recall_fixture)
        self.assertTrue(pair_res["valid"])
        self.assertEqual(pair_res["type"], "evidence_pair")
        self.assertEqual(pair_res["run_id"], "run_example_001")

    def test_pair_mode_rejects_identity_mismatch(self) -> None:
        rec_data = dict(self.valid_recall_dict)
        rec_data["run_id"] = "run-different"

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_imm, \
             tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_rec:
            json.dump(self.valid_immediate_dict, f_imm)
            json.dump(rec_data, f_rec)
            path_imm = Path(f_imm.name)
            path_rec = Path(f_rec.name)

        try:
            with self.assertRaises(ValidationError) as ctx:
                validate_evidence_pair(path_imm, path_rec)
            self.assertIn("pair identity mismatch for run_id", str(ctx.exception))
        finally:
            path_imm.unlink()
            path_rec.unlink()

    def test_pair_mode_rejects_timestamp_sequence_ordering_violation(self) -> None:
        imm_data = dict(self.valid_immediate_dict)
        # Immediate ended at 2026-08-11T10:30:00Z, but recorded late at 2026-08-12T12:00:00Z
        imm_data["recorded_at_local"] = "2026-08-12T12:00:00Z"
        imm_data["recording_delay_seconds"] = 91800.0

        rec_data = dict(self.valid_recall_dict)
        # Recall due at 2026-08-12T10:30:00Z and completed at 2026-08-12T11:00:00Z (before immediate recorded_at_local)
        rec_data["due_at_local"] = "2026-08-12T10:30:00Z"
        rec_data["completed_at_local"] = "2026-08-12T11:00:00Z"

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_imm, \
             tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_rec:
            json.dump(imm_data, f_imm)
            json.dump(rec_data, f_rec)
            path_imm = Path(f_imm.name)
            path_rec = Path(f_rec.name)

        try:
            with self.assertRaises(ValidationError) as ctx:
                validate_evidence_pair(path_imm, path_rec)
            self.assertIn("timestamp sequence violation", str(ctx.exception))
        finally:
            path_imm.unlink()
            path_rec.unlink()

    def test_pair_mode_rejects_due_at_24h_calculation_mismatch(self) -> None:
        rec_data = dict(self.valid_recall_dict)
        # ended at 10:30, expected dueAt is 10:30 next day (86400s later). Set dueAt to 15:00 next day.
        rec_data["due_at_local"] = "2026-08-12T15:00:00Z"
        rec_data["completed_at_local"] = "2026-08-12T16:00:00Z"

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_imm, \
             tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_rec:
            json.dump(self.valid_immediate_dict, f_imm)
            json.dump(rec_data, f_rec)
            path_imm = Path(f_imm.name)
            path_rec = Path(f_rec.name)

        try:
            with self.assertRaises(ValidationError) as ctx:
                validate_evidence_pair(path_imm, path_rec)
            self.assertIn("dueAt 24h calculation error", str(ctx.exception))
        finally:
            path_imm.unlink()
            path_rec.unlink()

    def test_pair_mode_flags_delayed_debrief_confound(self) -> None:
        imm_data = dict(self.valid_immediate_dict)
        imm_data["ended_at_local"] = "2026-08-11T10:30:00Z"
        imm_data["recorded_at_local"] = "2026-08-11T12:00:00Z"
        imm_data["recording_delay_seconds"] = 5400.0

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_imm, \
             tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_rec:
            json.dump(imm_data, f_imm)
            json.dump(self.valid_recall_dict, f_rec)
            path_imm = Path(f_imm.name)
            path_rec = Path(f_rec.name)

        try:
            res = validate_evidence_pair(path_imm, path_rec)
            self.assertTrue(res["valid"])
            self.assertTrue(res["confound_delayed_debrief"])
        finally:
            path_imm.unlink()
            path_rec.unlink()

    def test_pair_mode_rejects_draft_combinations(self) -> None:
        draft_imm = dict(self.valid_immediate_dict)
        draft_imm["record_status"] = "draft_incomplete"

        draft_rec = dict(self.valid_recall_dict)
        draft_rec["record_status"] = "recall_24h_draft"

        complete_imm = dict(self.valid_immediate_dict)
        complete_rec = dict(self.valid_recall_dict)

        combinations = [
            (draft_imm, draft_rec),
            (complete_imm, draft_rec),
            (draft_imm, complete_rec),
        ]

        for imm_data, rec_data in combinations:
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_imm, \
                 tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_rec:
                json.dump(imm_data, f_imm)
                json.dump(rec_data, f_rec)
                path_imm = Path(f_imm.name)
                path_rec = Path(f_rec.name)

            try:
                with self.assertRaises(ValidationError) as ctx:
                    validate_evidence_pair(path_imm, path_rec)
                self.assertIn("pair mode requires complete records", str(ctx.exception))
            finally:
                path_imm.unlink()
                path_rec.unlink()

    def test_reject_negative_recording_delay(self) -> None:
        data = dict(self.valid_immediate_dict)
        data["recording_delay_seconds"] = -10.0
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("recording_delay_seconds cannot be negative", str(ctx.exception))

    def test_reject_recorded_before_ended(self) -> None:
        data = dict(self.valid_immediate_dict)
        data["ended_at_local"] = "2026-08-11T10:30:00Z"
        data["recorded_at_local"] = "2026-08-11T10:25:00Z"
        data["recording_delay_seconds"] = -300.0
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("recorded_at_local", str(ctx.exception))

    def test_reject_naive_timestamp_lacking_timezone_or_z(self) -> None:
        data = dict(self.valid_immediate_dict)
        data["started_at_local"] = "2026-08-11T10:00:00"
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("naive timestamp lacking timezone offset or Z", str(ctx.exception))

        rec_data = dict(self.valid_recall_dict)
        rec_data["due_at_local"] = "2026-08-12T10:30:00"
        with self.assertRaises(ValidationError) as ctx:
            validate_recall_record(rec_data)
        self.assertIn("naive timestamp lacking timezone offset or Z", str(ctx.exception))

    def test_validate_precommitted_next_workout_at_local_format_and_ordering(self) -> None:
        # Invalid format (naive)
        data = dict(self.valid_immediate_dict)
        data["precommitted_next_workout_at_local"] = "2026-08-12T10:30:00"
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("naive timestamp lacking timezone offset or Z", str(ctx.exception))

        # Ordering violation (before ended_at_local)
        data["precommitted_next_workout_at_local"] = "2026-08-11T09:00:00Z"
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("precommitted_next_workout_at_local", str(ctx.exception))

    def test_reject_completed_record_lacking_track_summary(self) -> None:
        data = dict(self.valid_immediate_dict)
        data["track"] = None
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("completed record requires a valid track summary object", str(ctx.exception))

    def test_reject_completed_record_marked_as_aborted(self) -> None:
        data = dict(self.valid_immediate_dict)
        data["safety"] = dict(self.valid_immediate_dict["safety"])
        data["safety"]["abort"] = True
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(data)
        self.assertIn("run cannot be both aborted", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
