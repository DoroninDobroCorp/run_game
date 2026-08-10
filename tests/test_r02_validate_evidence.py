#!/usr/bin/env python3
"""Unit tests for tools/r02_validate_evidence.py evidence validator script.

Fulfills assertion VAL-VALIDATOR-001.
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
    validate_immediate_debrief,
    validate_recall_record,
)


class TestR02ValidateEvidence(unittest.TestCase):
    """Test suite for schema 0.3 immediate and recall evidence validation."""

    def setUp(self) -> None:
        self.valid_immediate_dict = {
            "schema_version": "0.3",
            "record_status": "immediate_complete",
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
            "schema_version": "0.2",
            "record_status": "recall_24h_complete",
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

    def test_valid_recall_record_passes(self) -> None:
        res = validate_recall_record(self.valid_recall_dict)
        self.assertTrue(res["valid"])
        self.assertEqual(res["type"], "recall_24h")

    def test_reject_duplicate_keys(self) -> None:
        json_str = '{"schema_version": "0.3", "schema_version": "0.3", "run_id": "123"}'
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
            json_str = f'{{"schema_version": "0.3", "recording_delay_seconds": {val}}}'
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


if __name__ == "__main__":
    unittest.main()
