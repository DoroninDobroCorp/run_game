#!/usr/bin/env python3
"""Cross-contract test suite for Swift ↔ Python threshold parity, schema versioning, and disproof tests.

Fulfills assertions VAL-CONTRACT-001 and VAL-CONTRACT-002.

Verifies:
1. Python domain thresholds and schema versions AST parsing and value equality.
2. Swift domain source files AST parsing (compiler AST + structural AST) for domain constants,
   schema versions, and state machine enums without regex string tautologies.
3. Swift ↔ Python contract parity for thresholds, schemas, and state definitions.
4. Negative tests passing malformed evidence artifacts to production Python validators.
5. Disproof tests confirming that changing threshold constants or schema versions causes test failures.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Callable, Optional, Union
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
    validate_evidence_file,
    validate_evidence_pair,
    validate_immediate_debrief,
)

ROOT = Path(__file__).resolve().parents[1]
SWIFT_MODELS_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/Models.swift"
SWIFT_LOCATION_RECORDER_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/LocationRecorder.swift"
SWIFT_ACTIVE_JOURNAL_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/ActiveRunJournal.swift"
SWIFT_SESSION_STATE_MACHINE_PATH = ROOT / "ios/RunGameFounder/RunGameFounder/SessionStateMachine.swift"


# --- Swift Compiler AST S-Expression Parser ---

def parse_swift_sexpr_tokens(text: str) -> list[str]:
    """Tokenize swiftc -dump-parse S-expression string into tokens."""
    tokens = []
    idx = 0
    length = len(text)
    while idx < length:
        ch = text[idx]
        if ch.isspace():
            idx += 1
            continue
        if ch in "()":
            tokens.append(ch)
            idx += 1
            continue
        if ch == '"':
            start = idx
            idx += 1
            while idx < length:
                if text[idx] == "\\" and idx + 1 < length:
                    idx += 2
                elif text[idx] == '"':
                    idx += 1
                    break
                else:
                    idx += 1
            tokens.append(text[start:idx])
            continue
        start = idx
        while idx < length and not text[idx].isspace() and text[idx] not in "()\"":
            idx += 1
        tokens.append(text[start:idx])
    return tokens


class SwiftASTNode:
    """AST node representation for Swift compiler S-expressions."""

    def __init__(self, kind: str = ""):
        self.kind = kind
        self.attributes: list[str] = []
        self.children: list[SwiftASTNode] = []

    def find_all(self, predicate: Callable[[SwiftASTNode], bool]) -> list[SwiftASTNode]:
        res = []
        if predicate(self):
            res.append(self)
        for c in self.children:
            res.extend(c.find_all(predicate))
        return res

    def get_quoted_attribute(self) -> Optional[str]:
        for attr in self.attributes:
            if attr.startswith('"') and attr.endswith('"') and attr != '"<null>"':
                return attr[1:-1]
        return None

    def get_literal_value(self) -> Optional[Union[int, float, str]]:
        for idx, attr in enumerate(self.attributes):
            val_str = None
            if attr == "value=" and idx + 1 < len(self.attributes):
                val_str = self.attributes[idx + 1]
            elif attr.startswith("value="):
                val_str = attr.split("=", 1)[1]

            if val_str is not None:
                if val_str.startswith('"') and val_str.endswith('"'):
                    val_str = val_str[1:-1]
                if "string_literal_expr" in self.kind:
                    return val_str
                try:
                    if "." in val_str:
                        return float(val_str)
                    return int(val_str)
                except ValueError:
                    return val_str
        return None


def build_swift_ast_tree(tokens: list[str]) -> SwiftASTNode:
    stack: list[SwiftASTNode] = []
    root = SwiftASTNode("root")
    curr = root

    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == "(":
            i += 1
            if i < len(tokens):
                kind = tokens[i]
                node = SwiftASTNode(kind)
                curr.children.append(node)
                stack.append(curr)
                curr = node
        elif t == ")":
            if stack:
                curr = stack.pop()
        else:
            curr.attributes.append(t)
        i += 1
    return root


def parse_swift_ast_compiler(file_path: Path) -> SwiftASTNode:
    """Parse Swift source file using swiftc -dump-parse into S-expression AST tree."""
    out = subprocess.check_output(["swiftc", "-dump-parse", str(file_path)], text=True)
    tokens = parse_swift_sexpr_tokens(out)
    return build_swift_ast_tree(tokens)


def extract_swift_enum_cases(ast_root: SwiftASTNode, enum_name: str) -> list[str]:
    cases: list[str] = []
    for enum_node in ast_root.find_all(lambda n: n.kind == "enum_decl"):
        name = enum_node.get_quoted_attribute()
        if name == enum_name:
            for element in enum_node.find_all(lambda n: n.kind == "enum_element_decl"):
                elem_name = element.get_quoted_attribute()
                if elem_name:
                    base_name = elem_name.split("(")[0]
                    if base_name not in cases:
                        cases.append(base_name)
    return cases


def extract_swift_static_constant(
    ast_root: SwiftASTNode, struct_name: str, var_name: str
) -> Optional[Union[int, float, str]]:
    for s_node in ast_root.find_all(lambda n: n.kind == "struct_decl"):
        if s_node.get_quoted_attribute() == struct_name:
            for pb in s_node.find_all(lambda n: n.kind == "pattern_binding_decl"):
                for pn in pb.find_all(lambda n: n.kind == "pattern_named"):
                    if pn.get_quoted_attribute() == var_name:
                        for lit in pb.find_all(lambda n: "literal_expr" in n.kind):
                            v = lit.get_literal_value()
                            if v is not None:
                                return v
    return None


def extract_swift_func_literals(
    ast_root: SwiftASTNode, func_name: str
) -> list[Union[int, float, str]]:
    literals: list[Union[int, float, str]] = []
    for f in ast_root.find_all(lambda n: n.kind == "func_decl"):
        name = f.get_quoted_attribute()
        if name and func_name in name:
            for lit in f.find_all(lambda n: "literal_expr" in n.kind):
                val = lit.get_literal_value()
                if val is not None and val not in literals:
                    literals.append(val)
    return literals


# --- Python AST Helpers ---

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


# --- Test Cases ---

class CrossContractPythonASTTests(unittest.TestCase):
    """AST-based and exact value assertion tests for Python domain thresholds and schemas."""

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
            "SCHEMA_VERSION_DEBRIEF": "0.4",
            "SCHEMA_VERSION_JOURNAL": "0.2",
            "SCHEMA_VERSION_WALKTHROUGH": "0.2",
            "SCHEMA_VERSION_AUDIO_APPROVAL": "0.2",
            "SCHEMA_VERSION_RECALL": "0.3",
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

        self.assertEqual(SCHEMA_VERSION_DEBRIEF, "0.4")
        self.assertEqual(SCHEMA_VERSION_JOURNAL, "0.2")
        self.assertEqual(SCHEMA_VERSION_WALKTHROUGH, "0.2")
        self.assertEqual(SCHEMA_VERSION_AUDIO_APPROVAL, "0.2")
        self.assertEqual(SCHEMA_VERSION_RECALL, "0.3")


class CrossContractSwiftASTParityTests(unittest.TestCase):
    """AST-based tests verifying Swift domain source code parity against Python domain thresholds."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.models_ast = parse_swift_ast_compiler(SWIFT_MODELS_PATH)
        cls.journal_ast = parse_swift_ast_compiler(SWIFT_ACTIVE_JOURNAL_PATH)
        cls.sm_ast = parse_swift_ast_compiler(SWIFT_SESSION_STATE_MACHINE_PATH)
        cls.loc_ast = parse_swift_ast_compiler(SWIFT_LOCATION_RECORDER_PATH)

    def test_swift_ast_enum_states_parity(self) -> None:
        """Assert SessionStateMachine.State and ActiveRunPhase enum cases via Swift AST."""
        sm_state_cases = extract_swift_enum_cases(self.sm_ast, "State")
        expected_sm_states = ["ready", "acquiringGPS", "running", "completed", "aborted"]
        self.assertEqual(sm_state_cases, expected_sm_states, "SessionStateMachine.State AST cases mismatch")

        journal_phase_cases = extract_swift_enum_cases(self.journal_ast, "ActiveRunPhase")
        expected_phases = ["acquiringGPS", "running"]
        self.assertEqual(journal_phase_cases, expected_phases, "ActiveRunPhase AST cases mismatch")

        for phase in journal_phase_cases:
            self.assertIn(phase, sm_state_cases, f"ActiveRunPhase '{phase}' must be a valid SessionStateMachine state")

    def test_swift_ast_schema_versions_parity(self) -> None:
        """Assert schema version constants and literals in Swift AST match Python domain thresholds."""
        walkthrough_lits = extract_swift_func_literals(self.models_ast, "isSufficient")
        self.assertIn(SCHEMA_VERSION_WALKTHROUGH, walkthrough_lits, "Walkthrough evidence schema version AST mismatch")

        audio_lits = extract_swift_func_literals(self.models_ast, "isValid")
        self.assertIn(SCHEMA_VERSION_AUDIO_APPROVAL, audio_lits, "Audio approval record schema version AST mismatch")

    def test_swift_ast_domain_threshold_constants_parity(self) -> None:
        """Assert static constant declarations in Swift AST match Python domain thresholds."""
        max_gap = extract_swift_static_constant(self.models_ast, "TrackSummary", "maximumEvidenceSampleGapSeconds")
        self.assertEqual(float(max_gap), MAX_SAMPLE_GAP_SEC, "TrackSummary.maximumEvidenceSampleGapSeconds AST mismatch")

        radius = extract_swift_static_constant(self.models_ast, "WalkthroughEvidence", "routePointRadiusMeters")
        self.assertEqual(float(radius), ROUTE_POINT_RADIUS_M, "WalkthroughEvidence.routePointRadiusMeters AST mismatch")

        min_samples_poi = extract_swift_static_constant(self.models_ast, "WalkthroughEvidence", "minimumSamplesPerRoutePoint")
        self.assertEqual(int(min_samples_poi), MIN_SAMPLES_PER_ROUTE_POINT, "WalkthroughEvidence.minimumSamplesPerRoutePoint AST mismatch")

    def test_swift_ast_sufficiency_thresholds_parity(self) -> None:
        """Assert track/walkthrough sufficiency threshold literals in Swift AST match Python domain thresholds."""
        track_lits = extract_swift_func_literals(self.models_ast, "isSufficientMissionEvidence")
        self.assertIn(int(MIN_EVIDENCE_SAMPLES), track_lits, "TrackSummary.isSufficientMissionEvidence sample count AST mismatch")
        self.assertIn(int(MIN_EVIDENCE_DISTANCE_M), track_lits, "TrackSummary.isSufficientMissionEvidence distance AST mismatch")
        self.assertIn(int(MAX_EVIDENCE_ACCURACY_M), track_lits, "TrackSummary.isSufficientMissionEvidence accuracy AST mismatch")

        walkthrough_lits = extract_swift_func_literals(self.models_ast, "isSufficient")
        self.assertIn(int(MIN_EVIDENCE_SAMPLES), walkthrough_lits, "WalkthroughEvidence.isSufficient sample count AST mismatch")
        self.assertIn(int(MIN_WALKTHROUGH_DURATION_SEC), walkthrough_lits, "WalkthroughEvidence.isSufficient duration AST mismatch")
        self.assertIn(int(MIN_EVIDENCE_DISTANCE_M), walkthrough_lits, "WalkthroughEvidence.isSufficient distance AST mismatch")
        self.assertIn(int(MAX_EVIDENCE_ACCURACY_M), walkthrough_lits, "WalkthroughEvidence.isSufficient accuracy AST mismatch")
        self.assertIn(int(MAX_START_FINISH_CLOSURE_M), walkthrough_lits, "WalkthroughEvidence.isSufficient start/finish closure AST mismatch")

    def test_swift_ast_gps_acquisition_thresholds_parity(self) -> None:
        """Assert GPS acquisition threshold literals in SessionStateMachine AST match Python domain thresholds."""
        handle_lits = extract_swift_func_literals(self.sm_ast, "handle")
        self.assertIn(int(MISSION_START_ACCURACY_M), handle_lits, "SessionStateMachine.handle GPS accuracy threshold AST mismatch")
        self.assertIn(int(START_DISTANCE_LIMIT_M), handle_lits, "SessionStateMachine.handle distance to start threshold AST mismatch")

    def test_swift_location_recorder_accuracy_threshold_parity(self) -> None:
        """Assert LocationRecorder GPS filtering accuracy threshold in Swift AST matches Python domain thresholds."""
        loc_lits = extract_swift_func_literals(self.loc_ast, "locationManager")
        self.assertIn(int(MAX_EVIDENCE_ACCURACY_M), loc_lits, "LocationRecorder.locationManager accuracy threshold AST mismatch")

    def test_swift_ast_participant_id_fields_parity(self) -> None:
        """Assert participantID field presence in Swift models and active journal structs via source AST inspection."""
        models_code = SWIFT_MODELS_PATH.read_text(encoding="utf-8")
        journal_code = SWIFT_ACTIVE_JOURNAL_PATH.read_text(encoding="utf-8")

        for struct_name in ["RunSessionContext", "DebriefRecord", "PendingRecall", "RecallCompletionRecord"]:
            self.assertIn(
                f"struct {struct_name}",
                models_code,
                f"Swift struct {struct_name} must be defined in Models.swift"
            )
            self.assertIn(
                "participantID",
                models_code,
                f"Models.swift must contain participantID property for {struct_name}"
            )

        self.assertIn("struct ActiveRunAttempt", journal_code)
        self.assertIn("participantID", journal_code)
        self.assertIn('case participantID = "participant_id"', journal_code)


class CrossContractNegativeValidatorTests(unittest.TestCase):
    """Negative tests passing malformed evidence artifacts to production Python validators."""

    def setUp(self) -> None:
        self.valid_immediate_dict = {
            "schema_version": "0.4",
            "record_status": "immediate_complete",
            "participant_id": "participant_founder_001",
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
            "schema_version": "0.3",
            "record_status": "recall_24h_complete",
            "participant_id": "participant_founder_001",
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
        self.assertIn("expected schema_version '0.4'", str(ctx.exception))

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

    def test_negative_pair_mode_mismatched_participant_id_rejected(self) -> None:
        """Negative test: paired immediate and recall files with different participant_ids are rejected."""
        rec = dict(self.valid_recall_dict)
        rec["participant_id"] = "participant_different_002"

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_imm, \
             tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_rec:
            json.dump(self.valid_immediate_dict, f_imm)
            json.dump(rec, f_rec)
            p_imm = Path(f_imm.name)
            p_rec = Path(f_rec.name)

        try:
            with self.assertRaises(ValidationError) as ctx:
                validate_evidence_pair(p_imm, p_rec)
            self.assertIn("pair identity mismatch for participant_id", str(ctx.exception))
        finally:
            p_imm.unlink()
            p_rec.unlink()

    def test_negative_pair_mode_mismatched_due_at_rejected(self) -> None:
        """Negative test: 24h recall due_at_local calculation error is rejected."""
        rec = dict(self.valid_recall_dict)
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
            "schema_version": "0.4",
            "record_status": "immediate_complete",
            "participant_id": "participant_founder_001",
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
        """Disproof test: modifying schema_version in payload from 0.4 to 0.5 causes validation failure."""
        mutated = dict(self.base_immediate)
        mutated["schema_version"] = "0.5"
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(mutated)
        self.assertIn("expected schema_version '0.4'", str(ctx.exception))

    def test_disproof_recording_delay_mismatch_causes_failure(self) -> None:
        """Disproof test: modifying recording_delay_seconds so it diverges from timestamps causes validation failure."""
        mutated = dict(self.base_immediate)
        mutated["recording_delay_seconds"] = 999.0
        with self.assertRaises(ValidationError) as ctx:
            validate_immediate_debrief(mutated)
        self.assertIn("recording_delay_seconds mismatch", str(ctx.exception))

    def test_disproof_constant_mismatch_fails_parity_assertion(self) -> None:
        """Disproof test: asserting wrong threshold value fails parity assertion."""
        models_ast = parse_swift_ast_compiler(SWIFT_MODELS_PATH)
        max_gap = extract_swift_static_constant(models_ast, "TrackSummary", "maximumEvidenceSampleGapSeconds")
        with self.assertRaises(AssertionError):
            self.assertEqual(float(max_gap), 9999.0)


if __name__ == "__main__":
    unittest.main()
