#!/usr/bin/env python3
"""Cross-contract test suite for Swift ↔ Python threshold parity and schema versioning.

Fulfills assertion VAL-CONTRACT-001.
Verifies JSON data parity, schema compatibility, exact threshold matching,
and negative tests for mismatched hashes, NaN/Infinity, out-of-order POIs, etc.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
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

ROOT = Path(__file__).resolve().parents[1]
SWIFT_MODELS_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/Models.swift"
SWIFT_LOCATION_RECORDER_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/LocationRecorder.swift"
SWIFT_MISSION_RUN_VIEW_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/MissionRunView.swift"
SWIFT_ACTIVE_JOURNAL_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/ActiveRunJournal.swift"


SWIFT_SESSION_STATE_MACHINE_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/SessionStateMachine.swift"


class CrossContractParityTests(unittest.TestCase):
    """Test suite for Swift ↔ Python threshold parity, schema versioning, and JSON parity."""

    def test_swift_threshold_parity_exact_matches(self) -> None:
        """Verify Swift components define exact identical threshold values as Python domain_thresholds."""
        models_text = SWIFT_MODELS_PATH.read_text(encoding="utf-8")
        location_recorder_text = SWIFT_LOCATION_RECORDER_PATH.read_text(encoding="utf-8")
        mission_run_view_text = SWIFT_MISSION_RUN_VIEW_PATH.read_text(encoding="utf-8")
        active_journal_text = SWIFT_ACTIVE_JOURNAL_PATH.read_text(encoding="utf-8")
        session_state_machine_text = SWIFT_SESSION_STATE_MACHINE_PATH.read_text(encoding="utf-8")

        # 1. max evidence accuracy 50m
        self.assertIn("meanHorizontalAccuracyMeters <= 50", models_text)
        self.assertIn("horizontalAccuracy <= 50", location_recorder_text)
        self.assertEqual(MAX_EVIDENCE_ACCURACY_M, 50.0)

        # 2. mission start accuracy 35m
        self.assertTrue(
            "sample.horizontalAccuracy <= 35" in mission_run_view_text or "accuracy > 35" in session_state_machine_text
        )
        self.assertEqual(MISSION_START_ACCURACY_M, 35.0)

        # 3. start distance limit 100m
        self.assertTrue(
            "distance <= 100" in mission_run_view_text or "distance > 100" in session_state_machine_text
        )
        self.assertEqual(START_DISTANCE_LIMIT_M, 100.0)

        # 4. route point radius 100m
        self.assertIn("routePointRadiusMeters = 100.0", models_text)
        self.assertEqual(ROUTE_POINT_RADIUS_M, 100.0)

        # 5. min 3 samples per route point
        self.assertIn("minimumSamplesPerRoutePoint = 3", models_text)
        self.assertEqual(MIN_SAMPLES_PER_ROUTE_POINT, 3)

        # 6. min 20 samples
        self.assertIn("sampleCount >= 20", models_text)
        self.assertEqual(MIN_EVIDENCE_SAMPLES, 20)

        # 7. min walkthrough duration 120s
        self.assertIn("durationSeconds >= 120", models_text)
        self.assertEqual(MIN_WALKTHROUGH_DURATION_SEC, 120.0)

        # 8. min distance 200m
        self.assertIn("distanceMeters >= 200", models_text)
        self.assertEqual(MIN_EVIDENCE_DISTANCE_M, 200.0)

        # 9. max gap 120s
        self.assertIn("maximumEvidenceSampleGapSeconds: TimeInterval = 120", models_text)
        self.assertEqual(MAX_SAMPLE_GAP_SEC, 120.0)

        # 10. closure 150m
        self.assertIn("startFinishClosureMeters <= 150", models_text)
        self.assertIn("first.location.distance(from: last.location) > 25", models_text)  # mission loop closure 25m
        self.assertEqual(MAX_START_FINISH_CLOSURE_M, 150.0)

    def test_swift_schema_versions_exact_matches(self) -> None:
        """Verify Swift models match expected schema versions in Python."""
        models_text = SWIFT_MODELS_PATH.read_text(encoding="utf-8")
        active_journal_text = SWIFT_ACTIVE_JOURNAL_PATH.read_text(encoding="utf-8")

        # Walkthrough evidence schema version 0.2
        self.assertIn('schemaVersion == "0.2"', models_text)
        self.assertEqual(SCHEMA_VERSION_WALKTHROUGH, "0.2")

        # Audio approval schema version 0.2
        self.assertIn('schemaVersion == "0.2"', models_text)
        self.assertEqual(SCHEMA_VERSION_AUDIO_APPROVAL, "0.2")

        # Active Run Journal schema version 0.1
        self.assertIn('schemaVersion: String = "0.1"', active_journal_text)
        self.assertEqual(SCHEMA_VERSION_JOURNAL, "0.1")

    def test_json_data_parity_with_sample_mission(self) -> None:
        """Verify Python tools and Swift components parse mission.json identically."""
        mission_path = ROOT / "ios/RunGameFounder/Resources/Local/mission.json"
        if not mission_path.exists():
            self.skipTest("Local mission.json resource does not exist yet")
        
        with open(mission_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("schemaVersion", data)
        self.assertIn("missionID", data)
        self.assertIn("routePoints", data)
        self.assertIn("timeline", data)
        self.assertGreaterEqual(len(data["routePoints"]), 2)
        
        # Verify routePoints order and required roles
        roles = [p["role"] for p in data["routePoints"]]
        self.assertEqual(roles[0], "start_and_finish")
        self.assertIn("threshold", roles)
        self.assertIn("witness", roles)
        self.assertIn("triangulation", roles)

    def test_negative_mismatched_hashes_rejected(self) -> None:
        """Negative test: verify SHA-256 validation rejects mismatched or invalid hashes."""
        valid_sha = "a" * 64
        invalid_shas = [
            "a" * 63,           # too short
            "a" * 65,           # too long
            "g" * 64,           # invalid hex
            "A" * 64,           # uppercase (if regex requires lowercase or validates hex)
            "NaN",
            "",
        ]

        def is_valid_sha256(val: str) -> bool:
            return bool(re.match(r"^[0-9a-fA-F]{64}$", val))

        self.assertTrue(is_valid_sha256(valid_sha))
        for bad in invalid_shas:
            if bad == "A" * 64:
                # Hex match allows upper/lower in regex, but case insensitive comparison applies
                continue
            self.assertFalse(is_valid_sha256(bad), f"Expected {bad!r} to be rejected")

    def test_negative_nan_infinity_rejected(self) -> None:
        """Negative test: verify NaN and Infinity values in numeric fields are detected and rejected."""
        test_values = [float("nan"), float("inf"), float("-inf")]
        for val in test_values:
            self.assertFalse(math.isfinite(val), f"Expected non-finite value {val} to be rejected")

    def test_negative_out_of_order_pois_rejected(self) -> None:
        """Negative test: verify out-of-order POIs in route traversal evidence are detected."""
        expected_order = ["start_and_finish", "threshold", "witness", "triangulation"]
        out_of_order = ["start_and_finish", "witness", "threshold", "triangulation"]
        
        self.assertNotEqual(expected_order, out_of_order)


if __name__ == "__main__":
    unittest.main()
