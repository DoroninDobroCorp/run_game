import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BEATS_PATH = ROOT / "research/r02/mission_01_beats.v0.1.json"
ACTIVE_FIXTURE_DIR = ROOT / "research/r02/local/valparaiso_central"
AUDIO_DIR = ACTIVE_FIXTURE_DIR / "audio"
MASTER_M4A = AUDIO_DIR / "m01_solo_founder_30min.m4a"
MANIFEST_PATH = AUDIO_DIR / "m01_solo_founder_30min.manifest.json"
BINDING_PATH = ACTIVE_FIXTURE_DIR / "current.binding.json"
FIXTURE_BINDING_PATH = ROOT / "research/r02/fixtures/field_binding.example.json"
OSM_SNAPSHOT_PATH = ACTIVE_FIXTURE_DIR / "osm_snapshot.json"

RUN_INTERVALS = [
    (300, 360),
    (450, 510),
    (600, 660),
    (750, 810),
    (900, 960),
    (1050, 1110),
    (1200, 1260),
    (1350, 1410)
]

class TestR02MasterAudioSpecs(unittest.TestCase):

    def test_c010_contains_no_nav_completion_text(self):
        with BEATS_PATH.open("r", encoding="utf-8") as f:
            beats = json.load(f)

        c010 = next(cue for cue in beats["cues"] if cue["cue_id"] == "m01_c010")
        self.assertNotIn("NAV: Тренировка завершена", c010["condition_a_text"])
        self.assertNotIn("NAV: Тренировка завершена", c010["condition_b_text"])
        self.assertNotIn("NAV: Тренировка завершена", c010["fallback_text"])

    def test_c008_contains_original_strong_line(self):
        with BEATS_PATH.open("r", encoding="utf-8") as f:
            beats = json.load(f)

        c008 = next(cue for cue in beats["cues"] if cue["cue_id"] == "m01_c008")
        self.assertIn("Я появилась не там, где меня забыли, а там, где ты прошёл", c008["condition_a_text"])
        self.assertIn("Я появилась не там, где меня забыли, а там, где ты прошёл", c008["condition_b_text"])

    def test_unapproved_binding_and_provisional_route_fields(self):
        target_path = BINDING_PATH if BINDING_PATH.exists() else FIXTURE_BINDING_PATH
        with target_path.open("r", encoding="utf-8") as f:
            binding = json.load(f)

        self.assertFalse(binding.get("human_route_approved"))
        self.assertFalse(binding.get("workout_approved"))
        self.assertFalse(binding.get("human_approved"))
        for slot in binding.get("slots", {}).values():
            self.assertFalse(slot.get("human_approved"))

        meta = binding.get("provisional_route_metadata", {})
        self.assertIsNone(meta.get("measured_loop_length_meters"))
        self.assertIsNone(meta.get("measured_elevation_gain_meters"))
        self.assertIsNone(meta.get("poi_leg_distances_meters"))
        self.assertIsNone(meta.get("expected_poi_arrival_cue_sec"))

    def test_osm_snapshot_ids_and_names(self):
        if not OSM_SNAPSHOT_PATH.exists():
            self.skipTest("Local Valparaiso OSM snapshot not present (git-ignored)")
        with OSM_SNAPSHOT_PATH.open("r", encoding="utf-8") as f:
            snapshot = json.load(f)

        candidates = snapshot.get("osm_candidates", {})
        start = candidates.get("start_and_finish", {})
        threshold = candidates.get("threshold", {})
        witness = candidates.get("witness", {})
        triangulation = candidates.get("triangulation", {})

        self.assertEqual(start.get("osm_id"), 313292626)
        self.assertEqual(start.get("osm_type"), "way")
        self.assertEqual(start.get("name"), "Plaza de la Victoria")

        self.assertEqual(threshold.get("osm_id"), 479821102)
        self.assertEqual(threshold.get("osm_type"), "way")
        self.assertEqual(threshold.get("name"), "Arco Británico")

        self.assertEqual(witness.get("osm_id"), 313291642)
        self.assertEqual(witness.get("osm_type"), "way")
        self.assertEqual(witness.get("name"), "Parque Italia")

        self.assertEqual(triangulation.get("osm_id"), 313290496)
        self.assertEqual(triangulation.get("osm_type"), "way")
        self.assertEqual(triangulation.get("name"), "Plaza O'Higgins")

    def test_manifest_if_local_master_audio_present(self):
        if not MANIFEST_PATH.exists():
            self.skipTest("Local master audio manifest not present (git-ignored)")
        with MANIFEST_PATH.open("r", encoding="utf-8") as f:
            manifest = json.load(f)

        cues = manifest.get("narrative_cues", [])
        self.assertEqual(len(cues), 10, "Solo playlist must contain 10 cues")
        self.assertEqual(cues[0]["cue_id"], "m01_c001")
        self.assertEqual(cues[-1]["cue_id"], "m01_c010")

        final_nav = manifest.get("workout_final_nav_timestamp_sec", 0)
        self.assertGreaterEqual(final_nav, 1790.0)
        self.assertLessEqual(final_nav, 1795.0)

        for cue in cues:
            start = cue["timestamp_sec"]
            end = start + cue["duration_sec"]
            for run_start, run_end in RUN_INTERVALS:
                self.assertFalse(
                    run_start <= start < run_end or run_start < end <= run_end,
                    f"Cue {cue['cue_id']} ({start}s-{end}s) overlaps run interval ({run_start}s-{run_end}s)"
                )

if __name__ == "__main__":
    unittest.main()
