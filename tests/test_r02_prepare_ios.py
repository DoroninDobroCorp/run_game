import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import r02_prepare_ios


class R02PrepareIOSTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = self.root / "fixture"
        self.output = self.root / "ios-local"
        self.audio = self.fixture / "audio"
        self.audio.mkdir(parents=True)
        self.m4a = self.audio / r02_prepare_ios.EXPECTED_M4A_FILE
        self.m4a.write_bytes(b"synthetic-m4a-for-unit-test")

        self.urls = {
            "start_and_finish": "https://www.openstreetmap.org/way/100",
            "threshold": "https://www.openstreetmap.org/way/101",
            "witness": "https://www.openstreetmap.org/way/102",
            "triangulation": "https://www.openstreetmap.org/way/103",
        }
        self.binding = {
            "schema_version": "0.1",
            "binding_id": "test_binding_v1",
            "route_id": "test_route_v1",
            "research_mode": "traveler_fixture",
            "product_model": "home_territory",
            "city_alias": "test_city",
            "public_start": True,
            "human_route_approved": False,
            "workout_approved": False,
            "human_approved": False,
            "slots": {
                "threshold": {
                    "name": "Порог-тест",
                    "archetype": "gate",
                    "visible_attributes": ["visible"],
                    "source_refs": [self.urls["threshold"]],
                    "operator_trigger": "after crossing",
                    "human_approved": False,
                },
                "witness": {
                    "name": "Свидетель-тест",
                    "archetype": "monument",
                    "visible_attributes": ["visible"],
                    "source_refs": [self.urls["witness"]],
                    "operator_trigger": "after passing",
                    "human_approved": False,
                },
                "triangulation": {
                    "name": "Площадь-тест",
                    "archetype": "open_square",
                    "visible_attributes": ["open"],
                    "source_refs": [self.urls["triangulation"]],
                    "operator_trigger": "on open segment",
                    "human_approved": False,
                },
            },
            "provisional_route_metadata": {
                "start_and_finish_name": "OSM start_and_finish",
                "source_ref": self.urls["start_and_finish"],
                "measured_loop_length_meters": None,
                "measured_elevation_gain_meters": None,
                "poi_leg_distances_meters": None,
                "expected_poi_arrival_cue_sec": None,
            },
        }
        self.snapshot = {
            "schema_version": "0.1",
            "city": "Test City, Test Country",
            "fixture_metadata": {
                "display_name": "Тестовый центр",
                "gpx_prefix": "Test Founder Route",
            },
            "osm_candidates": {
                role: {
                    "osm_type": "way",
                    "osm_id": 100 + index,
                    "name": f"OSM {role}",
                    "latitude": 10.0 + index / 100,
                    "longitude": 20.0 + index / 100,
                    "osm_url": self.urls[role],
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
                    "cue_id": "names",
                    "node_id": "m01_start",
                    "timestamp_sec": 8.0,
                    "duration_sec": 5.0,
                    "raw_text": " / ".join(
                        self.binding["slots"][slot]["name"]
                        for slot in r02_prepare_ios.REQUIRED_BINDING_SLOTS
                    ),
                }
            ],
        }
        self.write_fixture()
        self.duration_patch = mock.patch(
            "tools.r02_prepare_ios.probe_audio_duration", return_value=1800.0
        )
        self.duration_probe = self.duration_patch.start()

    def tearDown(self):
        self.duration_patch.stop()
        self.temp.cleanup()

    @staticmethod
    def write_json(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def write_fixture(self):
        self.write_json(self.fixture / "current.binding.json", self.binding)
        self.write_json(self.fixture / "osm_snapshot.json", self.snapshot)
        self.write_json(
            self.audio / r02_prepare_ios.EXPECTED_MANIFEST_FILE, self.manifest
        )

    def test_prepare_validates_and_publishes_exact_bundle(self):
        mission = r02_prepare_ios.prepare(self.fixture, self.output)

        self.assertEqual("Тестовый центр", mission["locationDisplayName"])
        self.assertEqual("test-founder-route", mission["gpxPrefix"])
        self.assertEqual("test_binding_v1", mission["bindingID"])
        self.assertEqual("Порог-тест", mission["routePoints"][1]["name"])
        self.assertEqual(5, len(mission["routePoints"]))
        self.assertRegex(mission["routeSHA256"], r"^[0-9a-f]{64}$")
        self.assertRegex(mission["timelineSHA256"], r"^[0-9a-f]{64}$")
        self.assertRegex(mission["bindingContractSHA256"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            {"mission.json", r02_prepare_ios.EXPECTED_M4A_FILE, r02_prepare_ios.EXPECTED_MANIFEST_FILE},
            {path.name for path in self.output.iterdir()},
        )
        self.assertEqual(
            self.manifest["m4a_sha256"],
            r02_prepare_ios.compute_sha256(self.output / r02_prepare_ios.EXPECTED_M4A_FILE),
        )

    def test_display_and_prefix_have_safe_fixture_fallbacks(self):
        self.snapshot.pop("fixture_metadata")
        self.write_fixture()
        mission = r02_prepare_ios.prepare(self.fixture, self.output)
        self.assertEqual("Test City, Test Country", mission["locationDisplayName"])
        self.assertEqual("test-route-v1", mission["gpxPrefix"])

    def test_initial_approval_requires_complete_human_evidence(self):
        self.binding.update(
            human_route_approved=True,
            workout_approved=True,
            human_approved=True,
        )
        for slot in self.binding["slots"].values():
            slot["human_approved"] = True
        self.binding["provisional_route_metadata"].update(
            measured_loop_length_meters=2500,
            measured_elevation_gain_meters=80,
            poi_leg_distances_meters=[500, 600, 700, 700],
            expected_poi_arrival_cue_sec={
                "threshold": 360,
                "witness": 660,
                "triangulation": 1110,
            },
            route_surface_notes="reviewed",
            crossing_notes="reviewed",
            daylight_walkthrough_completed_at_local="2026-08-11T10:00:00-03:00",
        )
        self.write_fixture()
        mission = r02_prepare_ios.prepare(self.fixture, self.output)
        self.assertTrue(mission["routeInitiallyApproved"])
        self.assertTrue(mission["workoutInitiallyApproved"])

        self.binding["slots"]["witness"]["human_approved"] = False
        self.write_fixture()
        mission = r02_prepare_ios.prepare(self.fixture, self.output)
        self.assertFalse(mission["routeInitiallyApproved"])
        self.assertFalse(mission["workoutInitiallyApproved"])

    def test_malformed_recorded_field_review_is_rejected(self):
        self.binding["provisional_route_metadata"]["poi_leg_distances_meters"] = [10, 20]
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "exactly four legs"):
            r02_prepare_ios.prepare(self.fixture, self.output)

    def test_json_loader_rejects_duplicate_keys_and_nonfinite_numbers(self):
        path = self.root / "malformed.json"
        path.write_text('{"value": 1, "value": 2}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            r02_prepare_ios.load_json(path)

        path.write_text('{"value": NaN}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "non-finite JSON number"):
            r02_prepare_ios.load_json(path)

    def test_sha_mismatch_is_rejected_before_output(self):
        self.manifest["m4a_sha256"] = "0" * 64
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "M4A SHA-256 mismatch"):
            r02_prepare_ios.prepare(self.fixture, self.output)
        self.assertFalse(self.output.exists())

    def test_duration_mismatch_is_rejected(self):
        self.manifest["actual_duration_m4a_sec"] = 1790.0
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "actual/target duration mismatch"):
            r02_prepare_ios.prepare(self.fixture, self.output)

    def test_probed_duration_mismatch_is_rejected(self):
        self.duration_probe.return_value = 1700.0
        with self.assertRaisesRegex(ValueError, "probed/manifest duration mismatch"):
            r02_prepare_ios.prepare(self.fixture, self.output)

    def test_target_duration_must_match_generated_timeline(self):
        self.manifest["target_duration_sec"] = 1200.0
        self.manifest["actual_duration_m4a_sec"] = 1200.0
        self.duration_probe.return_value = 1200.0
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "must match the M1 timeline"):
            r02_prepare_ios.prepare(self.fixture, self.output)

    def test_manifest_mission_id_is_fail_closed(self):
        self.manifest["mission_id"] = "m02"
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "mission_id must be 'm01'"):
            r02_prepare_ios.prepare(self.fixture, self.output)

    def test_manifest_binding_id_must_match_when_recorded(self):
        self.manifest["binding_id"] = "stale_binding"
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "binding_id does not match"):
            r02_prepare_ios.prepare(self.fixture, self.output)

    def test_start_name_and_source_must_match_snapshot(self):
        self.binding["provisional_route_metadata"]["start_and_finish_name"] = "Wrong"
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "start_and_finish_name"):
            r02_prepare_ios.prepare(self.fixture, self.output)

        self.binding["provisional_route_metadata"]["start_and_finish_name"] = (
            "OSM start_and_finish"
        )
        self.binding["provisional_route_metadata"]["source_ref"] = "manual"
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "source_ref"):
            r02_prepare_ios.prepare(self.fixture, self.output)

    def test_missing_route_role_and_invalid_coordinate_are_rejected(self):
        self.snapshot["osm_candidates"].pop("witness")
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "required role 'witness'"):
            r02_prepare_ios.prepare(self.fixture, self.output)

        self.snapshot = json.loads(
            (self.fixture / "osm_snapshot.json").read_text(encoding="utf-8")
        )
        # Restore from the original contract and make the coordinate invalid.
        self.snapshot["osm_candidates"]["witness"] = {
            "osm_type": "way",
            "osm_id": 102,
            "name": "OSM witness",
            "latitude": 91.0,
            "longitude": 20.02,
            "osm_url": self.urls["witness"],
        }
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "latitude is outside"):
            r02_prepare_ios.prepare(self.fixture, self.output)

    def test_snapshot_binding_source_ref_mismatch_is_rejected(self):
        self.binding["slots"]["threshold"]["source_refs"] = ["manual-review"]
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "source_refs do not contain snapshot OSM URL"):
            r02_prepare_ios.prepare(self.fixture, self.output)

    def test_manifest_must_contain_bound_names(self):
        self.manifest["narrative_cues"][0]["raw_text"] = "unrelated narration"
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "does not contain bound name"):
            r02_prepare_ios.prepare(self.fixture, self.output)

    def test_manifest_cue_timing_is_fail_closed(self):
        self.manifest["narrative_cues"][0]["timestamp_sec"] = 1799.0
        self.manifest["narrative_cues"][0]["duration_sec"] = 5.0
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "exceeds M4A duration"):
            r02_prepare_ios.prepare(self.fixture, self.output)

    def test_workout_nav_contract_is_exact(self):
        self.manifest["workout_nav_events_count"] = 1
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "must equal 27"):
            r02_prepare_ios.prepare(self.fixture, self.output)

        self.manifest["workout_nav_events_count"] = 27
        self.manifest["workout_final_nav_timestamp_sec"] = 0
        self.write_fixture()
        with self.assertRaisesRegex(ValueError, "1790-1795"):
            r02_prepare_ios.prepare(self.fixture, self.output)

    def test_stale_output_is_rejected_without_overwrite(self):
        self.output.mkdir()
        stale = self.output / "old-master.m4a"
        stale.write_bytes(b"keep-me")
        with self.assertRaisesRegex(ValueError, "stale iOS resources"):
            r02_prepare_ios.prepare(self.fixture, self.output)
        self.assertEqual(b"keep-me", stale.read_bytes())
        self.assertFalse((self.output / "mission.json").exists())

    def test_stage_failure_does_not_overwrite_existing_bundle(self):
        self.output.mkdir()
        old_files = {
            "mission.json": b"old mission",
            r02_prepare_ios.EXPECTED_M4A_FILE: b"old audio",
            r02_prepare_ios.EXPECTED_MANIFEST_FILE: b"old manifest",
        }
        for name, payload in old_files.items():
            (self.output / name).write_bytes(payload)

        original_copy = r02_prepare_ios.shutil.copy2
        copy_count = 0

        def fail_second_copy(source, destination):
            nonlocal copy_count
            copy_count += 1
            if copy_count == 2:
                raise OSError("synthetic staging failure")
            return original_copy(source, destination)

        with mock.patch("tools.r02_prepare_ios.shutil.copy2", side_effect=fail_second_copy):
            with self.assertRaisesRegex(OSError, "synthetic staging failure"):
                r02_prepare_ios.prepare(self.fixture, self.output)

        for name, payload in old_files.items():
            self.assertEqual(payload, (self.output / name).read_bytes())

    def test_directory_swap_failure_rolls_back_existing_bundle(self):
        self.output.mkdir()
        old_files = {
            "mission.json": b"old mission",
            r02_prepare_ios.EXPECTED_M4A_FILE: b"old audio",
            r02_prepare_ios.EXPECTED_MANIFEST_FILE: b"old manifest",
        }
        for name, payload in old_files.items():
            (self.output / name).write_bytes(payload)

        original_replace = r02_prepare_ios.os.replace
        replace_count = 0

        def fail_bundle_swap(source, destination):
            nonlocal replace_count
            replace_count += 1
            if replace_count == 2:
                raise OSError("synthetic directory swap failure")
            return original_replace(source, destination)

        with mock.patch("tools.r02_prepare_ios.os.replace", side_effect=fail_bundle_swap):
            with self.assertRaisesRegex(OSError, "synthetic directory swap failure"):
                r02_prepare_ios.prepare(self.fixture, self.output)

        for name, payload in old_files.items():
            self.assertEqual(payload, (self.output / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
