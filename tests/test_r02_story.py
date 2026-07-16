import copy
import unittest

from tools import r02_story


class R02StoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = r02_story.load_json(r02_story.DEFAULT_GRAPH)
        cls.beats = r02_story.load_json(r02_story.DEFAULT_BEATS)
        cls.choices = r02_story.load_json(r02_story.DEFAULT_CHOICES)
        cls.binding = r02_story.load_json(r02_story.DEFAULT_BINDING)
        cls.scorecard = r02_story.load_json(r02_story.DEFAULT_SCORECARD)

    def assert_validation_mentions(self, value, phrase):
        with self.assertRaises(r02_story.ValidationError) as raised:
            r02_story.validate_graph(value)
        self.assertIn(phrase, str(raised.exception))

    def test_valid_artifacts_pass(self):
        graph_summary = r02_story.validate_graph(self.graph)
        beat_summary = r02_story.validate_beats(self.beats, self.graph)
        score_summary = r02_story.validate_scorecard(self.scorecard)
        self.assertEqual(8, graph_summary["paths"])
        self.assertEqual(1800, beat_summary["duration_sec"])
        self.assertEqual("null_layer", score_summary["winner"])

    def test_all_eight_braided_paths_are_reachable(self):
        paths = r02_story.enumerate_paths(self.graph)
        self.assertEqual(8, len(paths))
        decisions = {tuple(sorted(path["decisions"].items())) for path in paths}
        self.assertEqual(8, len(decisions))
        self.assertTrue(all(path["node_ids"][-1].startswith("m03_end_") for path in paths))

    def test_m1_choice_is_read_in_m2(self):
        concealed = dict(self.choices, atlas_disclosure="concealed")
        reported = dict(self.choices, atlas_disclosure="reported")
        concealed_nodes = {
            item["node_id"]
            for item in r02_story.linearize_graph(self.graph, concealed)["path"]
        }
        reported_nodes = {
            item["node_id"]
            for item in r02_story.linearize_graph(self.graph, reported)["path"]
        }
        self.assertIn("m02_after_concealed", concealed_nodes)
        self.assertNotIn("m02_after_reported", concealed_nodes)
        self.assertIn("m02_after_reported", reported_nodes)
        self.assertNotIn("m02_after_concealed", reported_nodes)

    def test_linearization_is_deterministic(self):
        first = r02_story.linearize_graph(self.graph, self.choices)
        second = r02_story.linearize_graph(self.graph, self.choices)
        self.assertEqual(first, second)
        self.assertEqual(first["checksum"], second["checksum"])

    def test_dangling_edge_is_rejected(self):
        broken = copy.deepcopy(self.graph)
        broken["edges"][0]["to"] = "missing_node"
        self.assert_validation_mentions(broken, "dangling to node")

    def test_cycle_is_rejected(self):
        broken = copy.deepcopy(self.graph)
        broken["edges"].append(
            {
                "id": "cycle_edge",
                "from": "m03_end_core",
                "to": "m01_start",
                "fallback": False,
                "requires": {},
                "effects": {},
                "because": "test",
            }
        )
        self.assert_validation_mentions(broken, "cycle detected")

    def test_choice_without_fallback_is_rejected(self):
        broken = copy.deepcopy(self.graph)
        broken["edges"] = [edge for edge in broken["edges"] if edge["id"] != "e007"]
        self.assert_validation_mentions(broken, "choice requires exactly one fallback")

    def test_undeclared_state_write_is_rejected(self):
        broken = copy.deepcopy(self.graph)
        broken["edges"][0]["effects"] = {"undeclared_state": "value"}
        self.assert_validation_mentions(broken, "undeclared state")

    def test_nonterminal_state_must_be_read_later(self):
        broken = copy.deepcopy(self.graph)
        for edge in broken["edges"]:
            edge.get("requires", {}).pop("atlas_disclosure", None)
        self.assert_validation_mentions(broken, "written but never read")

    def test_geo_scene_without_fallback_is_rejected(self):
        broken = copy.deepcopy(self.graph)
        node = next(node for node in broken["nodes"] if node["id"] == "m01_threshold")
        node["geo_slot"].pop("fallback_summary")
        self.assert_validation_mentions(broken, "geo_slot requires an authored fallback")

    def test_condition_b_contains_no_place_placeholders(self):
        rendered = r02_story.render_mission(
            self.graph, self.beats, self.choices, condition="B"
        )
        self.assertEqual([], rendered["unresolved_placeholders"])
        self.assertTrue(all("{" not in cue["text"] for cue in rendered["cues"]))

    def test_participant_export_requires_human_approval(self):
        with self.assertRaises(r02_story.ValidationError):
            r02_story.render_mission(
                self.graph,
                self.beats,
                self.choices,
                condition="A",
                binding=self.binding,
                participant=True,
            )

    def test_approved_binding_resolves_condition_a(self):
        approved = copy.deepcopy(self.binding)
        approved["human_route_approved"] = True
        approved["workout_approved"] = True
        approved["human_approved"] = True
        for index, slot in enumerate(approved["slots"].values(), start=1):
            slot["human_approved"] = True
            slot["name"] = f"Публичный ориентир {index}"
            slot["archetype"] = "verified_public_landmark"
            slot["operator_trigger"] = f"relative_progress_window_{index}"
            slot["visible_attributes"] = ["visually_distinct"]
            slot["source_refs"] = [f"manual_review_{index}"]
        rendered = r02_story.render_mission(
            self.graph,
            self.beats,
            self.choices,
            condition="A",
            binding=approved,
            participant=True,
        )
        self.assertEqual("participant_ready", rendered["status"])
        self.assertEqual([], rendered["unresolved_placeholders"])

    def test_approval_flags_do_not_accept_placeholder_binding(self):
        fake_approved = copy.deepcopy(self.binding)
        fake_approved["human_route_approved"] = True
        fake_approved["workout_approved"] = True
        fake_approved["human_approved"] = True
        for slot in fake_approved["slots"].values():
            slot["human_approved"] = True
        with self.assertRaises(r02_story.ValidationError) as raised:
            r02_story.validate_binding(fake_approved, participant=True)
        self.assertIn("requires a real name", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
