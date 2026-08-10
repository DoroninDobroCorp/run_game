from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import r02_preflight, r02_prepare_ios


class R02PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = self.root / "fixture"
        self.output = self.root / "ios-local"
        audio_dir = self.fixture / "audio"
        audio_dir.mkdir(parents=True)
        self.m4a = audio_dir / r02_prepare_ios.EXPECTED_M4A_FILE
        self.m4a.write_bytes(b"preflight-synthetic-audio")

        urls = {
            role: f"https://www.openstreetmap.org/way/{200 + index}"
            for index, role in enumerate(r02_prepare_ios.REQUIRED_ROUTE_ROLES)
        }
        self.binding = {
            "schema_version": "0.1",
            "binding_id": "preflight_binding_v1",
            "route_id": "preflight_route_v1",
            "research_mode": "traveler_fixture",
            "product_model": "home_territory",
            "city_alias": "preflight_city",
            "public_start": True,
            "human_route_approved": False,
            "workout_approved": False,
            "human_approved": False,
            "slots": {
                "threshold": {
                    "name": "Threshold Bound Name",
                    "archetype": "gate",
                    "visible_attributes": ["visible"],
                    "source_refs": [urls["threshold"]],
                    "operator_trigger": "after boundary",
                    "human_approved": False,
                },
                "witness": {
                    "name": "Witness Bound Name",
                    "archetype": "monument",
                    "visible_attributes": ["visible"],
                    "source_refs": [urls["witness"]],
                    "operator_trigger": "after landmark",
                    "human_approved": False,
                },
                "triangulation": {
                    "name": "Triangulation Bound Name",
                    "archetype": "open_square",
                    "visible_attributes": ["open"],
                    "source_refs": [urls["triangulation"]],
                    "operator_trigger": "on open segment",
                    "human_approved": False,
                },
            },
            "provisional_route_metadata": {
                **{field: None for field in r02_preflight.FIELD_BLOCKERS},
                "start_and_finish_name": "OSM start_and_finish",
                "source_ref": urls["start_and_finish"],
            },
        }
        self.snapshot = {
            "schema_version": "0.1",
            "city": "Preflight Test City",
            "fixture_metadata": {
                "display_name": "Preflight Test Center",
                "gpx_prefix": "Preflight Route",
            },
            "osm_candidates": {
                role: {
                    "osm_type": "way",
                    "osm_id": 200 + index,
                    "name": f"OSM {role}",
                    "latitude": 40.0 + index / 100,
                    "longitude": -70.0 - index / 100,
                    "osm_url": urls[role],
                }
                for index, role in enumerate(r02_prepare_ios.REQUIRED_ROUTE_ROLES)
            },
        }
        self.manifest = {
            "schema_version": "0.1",
            "concept_id": "null_layer",
            "mission_id": "m01",
            "branch": "atlas_disclosure=concealed",
            "target_duration_sec": 1800.0,
            "actual_duration_m4a_sec": 1800.0,
            "workout_final_nav_timestamp_sec": 1792.0,
            "workout_nav_events_count": 27,
            "m4a_file": r02_prepare_ios.EXPECTED_M4A_FILE,
            "m4a_sha256": hashlib.sha256(self.m4a.read_bytes()).hexdigest(),
            "narrative_cues": [
                {
                    "cue_id": f"cue-{index}",
                    "node_id": node_id,
                    "timestamp_sec": 8.0 + index * 150.0,
                    "duration_sec": 5.0,
                    "raw_text": " ".join(
                        self.binding["slots"][slot]["name"]
                        for slot in r02_prepare_ios.REQUIRED_BINDING_SLOTS
                    )
                    if index == 0
                    else f"Narrative cue {index}",
                }
                for index, node_id in enumerate(
                    (
                        "m01_start",
                        "m01_contact",
                        "m01_threshold",
                        "m01_witness",
                        "m01_choice_disclosure",
                        "m01_response_concealed",
                        "m01_triangulation",
                        "m01_loop_close",
                        "m01_clue_fragments",
                        "m01_end",
                    )
                )
            ],
        }
        self.write_json(self.fixture / "current.binding.json", self.binding)
        self.write_json(self.fixture / "osm_snapshot.json", self.snapshot)
        self.write_json(
            audio_dir / r02_prepare_ios.EXPECTED_MANIFEST_FILE, self.manifest
        )
        self.duration_patch = mock.patch(
            "tools.r02_prepare_ios.probe_audio_duration", return_value=1800.0
        )
        self.duration_patch.start()
        r02_prepare_ios.prepare(self.fixture, self.output)

    def tearDown(self):
        self.duration_patch.stop()
        self.temp.cleanup()

    @staticmethod
    def write_json(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def test_ready_for_device_smoke_does_not_claim_safety(self):
        result = r02_preflight.preflight(self.fixture, self.output)
        self.assertEqual("READY_FOR_DEVICE_SMOKE", result["status"])
        self.assertEqual([], result["errors"])
        self.assertTrue(result["scope"]["device_smoke_only"])
        self.assertFalse(result["scope"]["preflight_grants_route_safety_approval"])
        self.assertFalse(result["scope"]["preflight_grants_workout_approval"])
        self.assertFalse(result["scope"]["preflight_grants_m1_a_approval"])
        self.assertGreater(len(result["human_blockers_to_m1_a"]), 0)

    def test_missing_field_measurements_are_blockers_not_device_errors(self):
        result = r02_preflight.preflight(self.fixture, self.output)
        missing = {
            blocker["path"]
            for blocker in result["human_blockers_to_m1_a"]
            if blocker["code"] == "field_measurement_missing"
        }
        self.assertEqual(
            {
                f"binding.provisional_route_metadata.{field}"
                for field in r02_preflight.FIELD_BLOCKERS
            },
            missing,
        )
        self.assertEqual("READY_FOR_DEVICE_SMOKE", result["status"])

    def test_invalid_binding_graph_contract_blocks_device_smoke(self):
        self.binding["slots"]["threshold"]["archetype"] = "gate_or_path_transition"
        self.write_json(self.fixture / "current.binding.json", self.binding)
        result = r02_preflight.preflight(self.fixture, self.output)
        self.assertEqual("NOT_READY_FOR_DEVICE_SMOKE", result["status"])
        self.assertTrue(
            any(error.startswith("binding_contract:") for error in result["errors"])
        )

    def test_tampered_ios_audio_blocks_device_smoke(self):
        (self.output / r02_prepare_ios.EXPECTED_M4A_FILE).write_bytes(b"tampered")
        result = r02_preflight.preflight(self.fixture, self.output)
        self.assertEqual("NOT_READY_FOR_DEVICE_SMOKE", result["status"])
        self.assertIn("ios_audio: SHA-256 mismatch", result["errors"])

    def test_tampered_route_hash_and_approval_projection_are_rejected(self):
        mission_path = self.output / "mission.json"
        mission = json.loads(mission_path.read_text(encoding="utf-8"))
        mission["routePoints"][0]["latitude"] += 0.01
        mission["routeInitiallyApproved"] = True
        self.write_json(mission_path, mission)

        result = r02_preflight.preflight(self.fixture, self.output)
        self.assertEqual("NOT_READY_FOR_DEVICE_SMOKE", result["status"])
        self.assertIn("ios_mission: prepared mission.json is stale", result["errors"])
        self.assertIn("ios_mission: route hash mismatch", result["errors"])
        self.assertIn("ios_mission: approval projection mismatch", result["errors"])

    def test_tampered_m1_human_projection_is_rejected(self):
        mission_path = self.output / "mission.json"
        mission = json.loads(mission_path.read_text(encoding="utf-8"))
        mission["m1HumanApprovalComplete"] = True
        self.write_json(mission_path, mission)

        result = r02_preflight.preflight(self.fixture, self.output)
        self.assertEqual("NOT_READY_FOR_DEVICE_SMOKE", result["status"])
        self.assertIn("ios_mission: approval projection mismatch", result["errors"])

    def test_cli_emits_json_only(self):
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = r02_preflight.main(
                [
                    "--fixture-dir",
                    str(self.fixture),
                    "--ios-resources-dir",
                    str(self.output),
                ]
            )
        parsed = json.loads(output.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("READY_FOR_DEVICE_SMOKE", parsed["status"])
        self.assertEqual("offline_no_network", parsed["mode"])
        self.assertNotIn(str(self.root), output.getvalue())


if __name__ == "__main__":
    unittest.main()
