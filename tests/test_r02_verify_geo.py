import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_r02_prepare_el_bolson import synthetic_map
from tools import r02_prepare_el_bolson as bolson
from tools import r02_verify_geo as geo


class GeoVerificationTests(unittest.TestCase):
    def setUp(self):
        self.source = synthetic_map()
        _, self.snapshot = bolson.build_fixture(self.source)

    def fetch(self, osm_type, osm_id):
        return next(element for element in self.source["elements"]
                    if element["type"] == osm_type and element["id"] == osm_id)

    def verify(self, snapshot):
        with tempfile.TemporaryDirectory() as temp, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            path = Path(temp) / "snapshot.json"
            path.write_text(json.dumps(snapshot))
            return geo.main(["--snapshot", str(path)])

    def test_translated_start_and_unnamed_junctions_verify_against_osm_identity(self):
        with patch.object(geo, "fetch_osm_object", side_effect=self.fetch):
            self.assertEqual(self.verify(self.snapshot), 0)

    def test_renamed_avenue_or_disconnected_junction_fails(self):
        with patch.object(geo, "fetch_osm_object", side_effect=self.fetch):
            self.fetch("way", bolson.AVENUE)["tags"]["name"] = "Different road"
            self.assertEqual(self.verify(self.snapshot), 1)
            self.fetch("way", bolson.AVENUE)["tags"]["name"] = "Avenida Patagonia Argentina"
            self.source["elements"][-1]["nodes"] = [4]
            self.assertEqual(self.verify(self.snapshot), 1)

    def test_empty_names_cannot_bypass_junction_verification(self):
        for way_ids in [None, [], [1], [1, 1], [True, 2], [1, "2"], [-1, 2]]:
            snapshot = copy.deepcopy(self.snapshot)
            snapshot["osm_candidates"]["threshold"]["osm_way_ids"] = way_ids
            with self.subTest(way_ids=way_ids), patch.object(geo, "fetch_osm_object", side_effect=self.fetch):
                self.assertEqual(self.verify(snapshot), 1)

    def test_legacy_named_candidate_and_network_errors(self):
        snapshot = copy.deepcopy(self.snapshot)
        start = snapshot["osm_candidates"]["start_and_finish"]
        start["name"] = start.pop("osm_name")
        with patch.object(geo, "fetch_osm_object", side_effect=self.fetch):
            self.assertEqual(self.verify(snapshot), 0)
        with patch.object(geo, "fetch_osm_object", side_effect=OSError("offline")):
            self.assertEqual(self.verify(snapshot), 1)

    def test_malformed_snapshots_fail_without_traceback(self):
        for snapshot in [[], {}, {"osm_candidates": []}, {"osm_candidates": {"threshold": {"osm_type": []}}}]:
            with self.subTest(snapshot=snapshot):
                self.assertEqual(self.verify(snapshot), 1)

    def test_wrong_api_identity_is_rejected(self):
        for elements in [[], [{"type": "node", "id": 99}], [None], [{"type": "way", "id": 1}] * 2]:
            with self.subTest(elements=elements), patch.object(geo.urllib.request, "urlopen") as request:
                request.return_value.__enter__.return_value = io.StringIO(json.dumps({"elements": elements}))
                with self.assertRaises(ValueError):
                    geo.fetch_osm_object("way", 1)


if __name__ == "__main__":
    unittest.main()
