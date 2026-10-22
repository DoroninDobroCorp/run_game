import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools import r02_analyze_gpx


def gpx_document_segments(segments):
    rendered_segments = []
    for points in segments:
        rendered = []
        for latitude, longitude, elevation, timestamp, accuracy in points:
            accuracy_xml = (
                ""
                if accuracy is None
                else f"<extensions><horizontalAccuracy>{accuracy}</horizontalAccuracy></extensions>"
            )
            rendered.append(
                f"""
                <trkpt lat="{latitude}" lon="{longitude}">
                  {'' if elevation is None else f'<ele>{elevation}</ele>'}
                  <time>{timestamp}</time>
                  {accuracy_xml}
                </trkpt>
                """
            )
        rendered_segments.append(f"<trkseg>{''.join(rendered)}</trkseg>")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
      <trk><name>Synthetic R02 Track</name>{''.join(rendered_segments)}</trk>
    </gpx>
    """


def gpx_document(points):
    return gpx_document_segments([points])


class R02AnalyzeGPXTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.gpx_path = self.root / "private-founder-track.gpx"
        self.mission_path = self.root / "mission.json"
        self.snapshot_path = self.root / "snapshot.json"
        self.manifest_path = self.root / "manifest.json"

        base = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

        def stamp(seconds):
            return (base + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")

        accepted_points = []
        for group_index, (longitude, group_start) in enumerate(
            ((0.0, 0), (0.001, 50), (0.002, 100), (0.003, 150), (0.0, 220))
        ):
            for repetition in range(5):
                accepted_index = group_index * 5 + repetition
                accepted_points.append(
                    (
                        0.0,
                        longitude,
                        10.0 + accepted_index * 0.5,
                        stamp(group_start + repetition * 10),
                        5,
                    )
                )
        self.points = accepted_points + [
            (0.0, 0.0015, 80.0, stamp(95), 80),
        ]
        self.points.sort(key=lambda point: point[3])
        self.gpx_path.write_text(gpx_document(self.points), encoding="utf-8")
        self.mission = {
            "schemaVersion": "0.1",
            "missionID": "m01",
            "routePoints": [
                {"id": "private-start", "role": "start_and_finish", "name": "Hidden", "latitude": 0.0, "longitude": 0.0},
                {"id": "secret-threshold", "role": "threshold", "name": "Hidden", "latitude": 0.0, "longitude": 0.001},
                {"id": "secret-witness", "role": "witness", "name": "Hidden", "latitude": 0.0, "longitude": 0.002},
                {"id": "secret-triangulation", "role": "triangulation", "name": "Hidden", "latitude": 0.0, "longitude": 0.003},
                {"id": "private-finish", "role": "start_and_finish", "name": "Hidden", "latitude": 0.0, "longitude": 0.0},
            ],
            "bindingID": "synthetic-binding",
            "bindingContractSHA256": "b" * 64,
            "audioSHA256": "a" * 64,
        }
        self.manifest = {
            "schema_version": "0.1",
            "mission_id": "m01",
            "target_duration_sec": 260,
            "m4a_sha256": "a" * 64,
            "narrative_cues": [
                {"cue_id": "c-threshold", "node_id": "m01_threshold", "timestamp_sec": 50},
                {"cue_id": "c-witness", "node_id": "m01_witness", "timestamp_sec": 100},
                {"cue_id": "c-triangulation", "node_id": "m01_triangulation", "timestamp_sec": 150},
            ],
        }
        self.write_manifest_and_sync_mission()

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_mission(self):
        route_payload = json.dumps(
            self.mission["routePoints"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
        self.mission["routeSHA256"] = hashlib.sha256(route_payload).hexdigest()
        self.mission_path.write_text(json.dumps(self.mission), encoding="utf-8")

    def write_manifest_and_sync_mission(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.mission["audioManifestSHA256"] = hashlib.sha256(
            self.manifest_path.read_bytes()
        ).hexdigest()
        self.write_mission()

    def analyze(self):
        return r02_analyze_gpx.analyze_files(
            gpx_path=self.gpx_path,
            mission_path=self.mission_path,
            manifest_path=self.manifest_path,
            max_horizontal_accuracy_m=50,
            arrival_radius_m=2,
        )

    def test_derives_distance_closure_arrivals_and_cue_deltas(self):
        report = self.analyze()

        summary = report["track_summary"]
        self.assertEqual(25, summary["accepted_points"])
        self.assertEqual(1, summary["rejected_points"])
        self.assertEqual(260.0, summary["duration_sec"])
        self.assertEqual(30.0, summary["maximum_sample_gap_sec"])
        self.assertAlmostEqual(667.17, summary["distance_m"], places=2)
        self.assertEqual(12.0, summary["elevation_gain_m"])
        self.assertEqual(0.0, summary["start_finish_closure_m"])
        self.assertEqual(4, len(report["route_leg_distances_m"]))
        self.assertEqual(
            report["route_leg_distances_m"],
            report["binding_field_values"]["poi_leg_distances_meters"],
        )
        self.assertEqual(
            summary["distance_m"],
            report["binding_field_values"]["measured_loop_length_meters"],
        )

        arrivals = {
            item["role"]: item["first_arrival_elapsed_sec"]
            for item in report["route_points"]
            if item["role"] in r02_analyze_gpx.REQUIRED_CUE_ROLES
        }
        self.assertEqual(
            {"threshold": 50.0, "witness": 100.0, "triangulation": 150.0},
            arrivals,
        )
        deltas = {item["role"]: item["cue_delta_sec"] for item in report["cue_deltas"]}
        self.assertEqual(
            {"threshold": 0.0, "witness": 0.0, "triangulation": 0.0},
            deltas,
        )
        self.assertEqual(220.0, report["route_points"][-1]["first_arrival_elapsed_sec"])

    def test_report_omits_coordinates_names_absolute_times_and_input_paths(self):
        secret_binding_id = "r02_m01_secret_valparaiso_location"
        self.mission["bindingID"] = secret_binding_id
        self.write_mission()
        serialized = json.dumps(self.analyze(), ensure_ascii=False, sort_keys=True)
        lowered = serialized.lower()

        for forbidden_key in ("latitude", "longitude", "started_at", "input_path", "gpx_path"):
            self.assertNotIn(forbidden_key, lowered)
        for forbidden_value in (
            str(self.gpx_path),
            str(self.mission_path),
            "private-founder-track.gpx",
            "private-start",
            "secret-threshold",
            "Hidden",
            "2026-01-01T10:00:00Z",
            secret_binding_id,
        ):
            self.assertNotIn(forbidden_value, serialized)
        self.assertIn("no safety or approval determination", serialized)
        provenance = self.analyze()["provenance"]
        self.assertEqual(
            hashlib.sha256(secret_binding_id.encode()).hexdigest(),
            provenance["binding_id_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(self.gpx_path.read_bytes()).hexdigest(),
            provenance["gpx_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(self.mission_path.read_bytes()).hexdigest(),
            provenance["route_source_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(self.manifest_path.read_bytes()).hexdigest(),
            provenance["manifest_sha256"],
        )

    def test_snapshot_route_input_is_supported(self):
        candidates = {}
        for role, longitude in (
            ("start_and_finish", 0.0),
            ("threshold", 0.001),
            ("witness", 0.002),
            ("triangulation", 0.003),
        ):
            candidates[role] = {
                "name": "Synthetic",
                "latitude": 0.0,
                "longitude": longitude,
            }
        self.snapshot_path.write_text(
            json.dumps({"osm_candidates": candidates}), encoding="utf-8"
        )

        report = r02_analyze_gpx.analyze_files(
            gpx_path=self.gpx_path,
            snapshot_path=self.snapshot_path,
            manifest_path=self.manifest_path,
            max_horizontal_accuracy_m=50,
            arrival_radius_m=2,
        )

        self.assertEqual(5, len(report["route_points"]))
        self.assertEqual(3, len(report["cue_deltas"]))

    def test_valid_cli_writes_only_the_derived_json_report(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = r02_analyze_gpx.main(
                [
                    "--gpx",
                    str(self.gpx_path),
                    "--mission",
                    str(self.mission_path),
                    "--manifest",
                    str(self.manifest_path),
                    "--arrival-radius-m",
                    "2",
                ]
            )

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr.getvalue())
        report = json.loads(stdout.getvalue())
        self.assertEqual("r02_gpx_cue_derived", report["report_type"])
        self.assertNotIn(str(self.gpx_path), stdout.getvalue())

    def test_unsorted_track_fails_closed(self):
        unsorted = list(self.points)
        unsorted[1], unsorted[2] = unsorted[2], unsorted[1]
        self.gpx_path.write_text(gpx_document(unsorted), encoding="utf-8")

        with self.assertRaisesRegex(
            r02_analyze_gpx.AnalysisError, "strictly chronological"
        ):
            self.analyze()

    def test_missing_accuracy_fails_closed(self):
        missing_accuracy = list(self.points)
        latitude, longitude, elevation, timestamp, _ = missing_accuracy[0]
        missing_accuracy[0] = (latitude, longitude, elevation, timestamp, None)
        self.gpx_path.write_text(gpx_document(missing_accuracy), encoding="utf-8")

        with self.assertRaisesRegex(
            r02_analyze_gpx.AnalysisError, "horizontalAccuracy"
        ):
            self.analyze()

    def test_missing_elevation_fails_closed(self):
        missing_elevation = list(self.points)
        latitude, longitude, _, timestamp, accuracy = missing_elevation[0]
        missing_elevation[0] = (latitude, longitude, None, timestamp, accuracy)
        self.gpx_path.write_text(gpx_document(missing_elevation), encoding="utf-8")

        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "elevation"):
            self.analyze()

    def test_too_few_accepted_points_fails_closed(self):
        poor = [
            (0.0, 0.0, 0.0, "2026-01-01T10:00:00Z", 4),
            (0.0, 0.0001, 0.0, "2026-01-01T10:00:10Z", 80),
        ]
        self.gpx_path.write_text(gpx_document(poor), encoding="utf-8")

        with self.assertRaisesRegex(
            r02_analyze_gpx.AnalysisError, "at least two accepted"
        ):
            self.analyze()

    def test_excessive_sample_gap_fails_closed(self):
        sparse = list(self.points)
        sparse[-1] = (0.0, 0.0, 14.0, "2026-01-01T10:10:00Z", 4)
        self.gpx_path.write_text(gpx_document(sparse), encoding="utf-8")

        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "sample gap"):
            self.analyze()

    def test_multiple_track_segments_cannot_hide_discontinuities(self):
        accepted = [point for point in self.points if point[4] <= 50]
        self.gpx_path.write_text(
            gpx_document_segments([accepted[:10], accepted[10:]]), encoding="utf-8"
        )

        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "exactly one"):
            self.analyze()

    def test_accuracy_override_cannot_weaken_device_evidence_gate(self):
        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "0-50m"):
            r02_analyze_gpx.analyze_files(
                gpx_path=self.gpx_path,
                mission_path=self.mission_path,
                manifest_path=self.manifest_path,
                max_horizontal_accuracy_m=50.001,
                arrival_radius_m=2,
            )

    def test_at_least_twenty_accepted_points_are_required(self):
        accepted = [point for point in self.points if point[4] <= 50]
        reduced = accepted[0:4] + accepted[5:9] + accepted[10:14] + accepted[15:19] + accepted[20:23]
        self.gpx_path.write_text(gpx_document(reduced), encoding="utf-8")

        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "at least 20"):
            self.analyze()

    def test_minimum_duration_is_enforced(self):
        base = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        compact = []
        for latitude, longitude, elevation, timestamp, accuracy in self.points:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            elapsed = (parsed - base).total_seconds()
            compact_timestamp = (
                base + timedelta(seconds=elapsed * 0.375)
            ).isoformat().replace("+00:00", "Z")
            compact.append(
                (latitude, longitude * 0.5, elevation, compact_timestamp, accuracy)
            )
        self.gpx_path.write_text(gpx_document(compact), encoding="utf-8")
        for point in self.mission["routePoints"]:
            point["longitude"] *= 0.5
        self.write_mission()

        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "at least 120s"):
            self.analyze()

    def test_minimum_distance_is_enforced(self):
        shortened = [
            (latitude, longitude * 0.2, elevation, timestamp, accuracy)
            for latitude, longitude, elevation, timestamp, accuracy in self.points
        ]
        self.gpx_path.write_text(gpx_document(shortened), encoding="utf-8")
        for point in self.mission["routePoints"]:
            point["longitude"] *= 0.2
        self.write_mission()

        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "at least 200m"):
            self.analyze()

    def test_three_ordered_samples_per_route_point_are_required(self):
        weakened = list(self.points)
        threshold_indices = [
            index
            for index, point in enumerate(weakened)
            if point[1] == 0.001 and point[4] <= 50
        ]
        for index in threshold_indices[2:]:
            latitude, _, elevation, timestamp, accuracy = weakened[index]
            weakened[index] = (latitude, 0.0015, elevation, timestamp, accuracy)
        self.gpx_path.write_text(gpx_document(weakened), encoding="utf-8")

        with self.assertRaisesRegex(
            r02_analyze_gpx.AnalysisError, "never enter the arrival radius"
        ):
            self.analyze()

    def test_first_and_last_points_must_be_near_public_start(self):
        displaced = []
        for point in self.points:
            latitude, longitude, elevation, timestamp, accuracy = point
            if longitude == 0.0:
                longitude = 0.001
            displaced.append((latitude, longitude, elevation, timestamp, accuracy))
        self.gpx_path.write_text(gpx_document(displaced), encoding="utf-8")

        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "first accepted"):
            self.analyze()

    def test_implausible_movement_speed_fails_closed(self):
        accelerated = list(self.points)
        threshold_index = next(
            index
            for index, point in enumerate(accelerated)
            if point[1] == 0.001 and point[4] <= 50
        )
        latitude, longitude, elevation, _, accuracy = accelerated[threshold_index]
        accelerated[threshold_index] = (
            latitude,
            longitude,
            elevation,
            "2026-01-01T10:00:41Z",
            accuracy,
        )
        accelerated.sort(key=lambda point: point[3])
        self.gpx_path.write_text(gpx_document(accelerated), encoding="utf-8")

        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "movement speed"):
            self.analyze()

    def test_prepared_mission_must_match_exact_manifest_and_audio(self):
        self.analyze()

        self.mission["audioManifestSHA256"] = "0" * 64
        self.write_mission()
        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "manifest SHA"):
            self.analyze()

        self.mission["audioManifestSHA256"] = hashlib.sha256(
            self.manifest_path.read_bytes()
        ).hexdigest()
        self.mission["audioSHA256"] = "b" * 64
        self.write_mission()
        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "audio SHA"):
            self.analyze()

    def test_prepared_mission_requires_complete_provenance_contract(self):
        baseline = json.loads(json.dumps(self.mission))
        for missing_key in (
            "audioManifestSHA256",
            "audioSHA256",
            "bindingContractSHA256",
            "routeSHA256",
        ):
            with self.subTest(missing_key=missing_key):
                incomplete = json.loads(json.dumps(baseline))
                incomplete.pop(missing_key)
                self.mission_path.write_text(json.dumps(incomplete), encoding="utf-8")
                with self.assertRaisesRegex(
                    r02_analyze_gpx.AnalysisError, "must declare"
                ):
                    self.analyze()

        for missing_key in ("missionID", "bindingID"):
            with self.subTest(missing_key=missing_key):
                incomplete = json.loads(json.dumps(baseline))
                incomplete.pop(missing_key)
                self.mission_path.write_text(json.dumps(incomplete), encoding="utf-8")
                with self.assertRaisesRegex(
                    r02_analyze_gpx.AnalysisError, "non-empty"
                ):
                    self.analyze()

    def test_prepared_mission_route_hash_must_match_exact_route_points(self):
        self.mission["routeSHA256"] = "0" * 64
        self.mission_path.write_text(json.dumps(self.mission), encoding="utf-8")

        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "route SHA"):
            self.analyze()

    def test_declared_manifest_binding_must_match_prepared_mission(self):
        self.mission["bindingID"] = "binding-a"
        self.manifest["binding_id"] = "binding-b"
        self.write_manifest_and_sync_mission()

        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "binding identifiers"):
            self.analyze()

    def test_missing_required_arrival_fails_closed(self):
        self.mission["routePoints"][3]["longitude"] = 0.01
        self.write_mission()

        with self.assertRaisesRegex(
            r02_analyze_gpx.AnalysisError, "never enter the arrival radius"
        ):
            self.analyze()

    def test_missing_required_cue_fails_closed_with_nonzero_cli(self):
        self.manifest["narrative_cues"] = self.manifest["narrative_cues"][:-1]
        self.write_manifest_and_sync_mission()
        stdout = io.StringIO()
        stderr = io.StringIO()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = r02_analyze_gpx.main(
                [
                    "--gpx",
                    str(self.gpx_path),
                    "--mission",
                    str(self.mission_path),
                    "--manifest",
                    str(self.manifest_path),
                ]
            )

        self.assertNotEqual(0, exit_code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("exactly one cue for role triangulation", stderr.getvalue())

    def test_json_inputs_reject_duplicate_keys_and_nonfinite_numbers(self):
        self.mission_path.write_text('{"routePoints": [], "routePoints": []}', encoding="utf-8")
        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "duplicate JSON key"):
            self.analyze()

        self.mission_path.write_text('{"routePoints": NaN}', encoding="utf-8")
        with self.assertRaisesRegex(r02_analyze_gpx.AnalysisError, "non-finite JSON number"):
            self.analyze()


if __name__ == "__main__":
    unittest.main()
