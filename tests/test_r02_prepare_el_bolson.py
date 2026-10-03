import copy
import errno
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from tools import r02_prepare_el_bolson as bolson
from tools import r02_story


def synthetic_map():
    # Anonymous geometry with the same street topology; no real start or trace.
    nodes = [
        {"type": "node", "id": i + 1, "lat": 10.0001 + i * .001, "lon": 20.0001}
        for i in range(9)
    ]
    nodes.extend([
        {"type": "node", "id": 20, "lat": 10.0061, "lon": 20.0011},
        {"type": "node", "id": 21, "lat": 10.0051, "lon": 20.0021},
        {"type": "node", "id": 22, "lat": 10.0031, "lon": 20.0011},
    ])
    ids = bolson.LOOP_WAYS[:-1]
    sequences = [list(range(1, 10)), [7, 20], [20, 21], [21, 22], [22, 4]]
    ways = [
        {"type": "way", "id": way_id, "nodes": sequence,
         "tags": {"highway": "residential", "name": "Avenida Patagonia Argentina" if way_id == bolson.AVENUE else "Test street"}}
        for way_id, sequence in zip(ids, sequences)
    ]
    return {"elements": nodes + ways}


class ElBolsonFixtureTests(unittest.TestCase):
    def test_route_starts_at_distance_midpoint_and_closes_on_mapped_ways(self):
        binding, snapshot = bolson.build_fixture(synthetic_map())
        r02_story.validate_binding(binding, participant=False, graph=r02_story.load_json(r02_story.DEFAULT_GRAPH))
        route = snapshot["offline_route"]
        self.assertEqual(route["coordinates"][0], route["coordinates"][-1])
        self.assertAlmostEqual(route["coordinates"][0]["latitude"], 10.0041, places=6)
        self.assertEqual(route["waypointIndices"][0], 0)
        self.assertEqual(route["waypointIndices"][-1], len(route["coordinates"]) - 1)
        self.assertEqual(len(route["waypointIndices"]), 5)
        self.assertGreater(snapshot["planned_loop_length_meters"], 200)
        for key in ("public_start", "human_route_approved", "workout_approved", "human_approved"):
            self.assertIs(binding[key], False)
        self.assertIs(snapshot["field_verified"], False)
        self.assertIsNone(binding["provisional_route_metadata"]["measured_elevation_gain_meters"])

    def test_missing_or_disconnected_streets_are_rejected(self):
        original = synthetic_map()
        missing = copy.deepcopy(original)
        missing["elements"].pop()
        with self.assertRaisesRegex(ValueError, "missing way"):
            bolson.build_fixture(missing)
        disconnected = copy.deepcopy(original)
        # The last connection must lie south of the midpoint; flip to north.
        disconnected["elements"][-1]["nodes"] = [22, 8]
        with self.assertRaisesRegex(ValueError, "midpoint"):
            bolson.build_fixture(disconnected)

    def test_private_motorway_and_construction_segments_are_rejected(self):
        for tags in ({"access": "private"}, {"foot": "no"}, {"highway": "trunk"}, {"construction": "yes"}):
            source = synthetic_map()
            source["elements"][-1]["tags"].update(tags)
            with self.subTest(tags=tags), self.assertRaises(ValueError):
                bolson.build_fixture(source)

    def test_wrong_avenue_name_and_missing_coordinates_are_rejected(self):
        source = synthetic_map()
        next(x for x in source["elements"] if x["type"] == "way")["tags"]["name"] = "Different road"
        with self.assertRaisesRegex(ValueError, "identity"):
            bolson.build_fixture(source)
        source = synthetic_map()
        source["elements"].pop(0)
        with self.assertRaisesRegex(ValueError, "Missing nodes"):
            bolson.build_fixture(source)

    def test_gpx_export_is_a_plan_not_recorded_evidence(self):
        _, snapshot = bolson.build_fixture(synthetic_map())
        root = ET.fromstring(bolson.planned_gpx(snapshot))
        ns = {"g": "http://www.topografix.com/GPX/1/1"}
        self.assertEqual(len(root.findall(".//g:rtept", ns)), len(snapshot["offline_route"]["coordinates"]))
        self.assertEqual(root.findall(".//g:trkpt", ns), [])
        self.assertEqual(root.findall(".//g:time", ns), [])

    def test_failed_final_write_leaves_no_partial_fixture_and_retry_succeeds(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            root = Path(temp)
            source = root / "map.json"
            source.write_text(json.dumps(synthetic_map()))
            output = root / "fixture"
            args = ["--osm-map", str(source), "--output-dir", str(output)]
            with patch.object(Path, "write_bytes", side_effect=OSError(errno.ENOSPC, "No space left")):
                self.assertEqual(bolson.main(args), 1)
            self.assertFalse(output.exists())
            self.assertEqual(list(root.iterdir()), [source])
            self.assertEqual(bolson.main(args), 0)
            self.assertEqual({file.name for file in output.iterdir()}, {
                "current.binding.json", "osm_snapshot.json", "source.osm.json", "planned-route.gpx",
            })

    def test_existing_reviews_are_preserved_and_empty_destination_is_supported(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            root = Path(temp)
            source = root / "map.json"
            source.write_text(json.dumps(synthetic_map()))
            output = root / "fixture"
            output.mkdir()
            args = ["--osm-map", str(source), "--output-dir", str(output)]
            self.assertEqual(bolson.main(args), 0)
            original = {file.name: file.read_bytes() for file in output.iterdir()}
            self.assertEqual(bolson.main(args), 1)
            self.assertEqual({file.name: file.read_bytes() for file in output.iterdir()}, original)

    def test_publication_failure_preserves_files_created_during_preparation(self):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            root = Path(temp)
            source = root / "map.json"
            source.write_text(json.dumps(synthetic_map()))
            output = root / "fixture"
            rename = bolson.os.rename

            def concurrent_review(stage, destination):
                destination.mkdir()
                (destination / "review.txt").write_text("keep this review")
                rename(stage, destination)

            with patch.object(bolson.os, "rename", side_effect=concurrent_review):
                self.assertEqual(bolson.main(["--osm-map", str(source), "--output-dir", str(output)]), 1)
            self.assertEqual({file.name for file in output.iterdir()}, {"review.txt"})
            self.assertEqual((output / "review.txt").read_text(), "keep this review")
            self.assertEqual({file.name for file in root.iterdir()}, {"map.json", "fixture"})


if __name__ == "__main__":
    unittest.main()
