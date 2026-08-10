import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import r02_verify_field


class R02VerifyFieldTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.audio_dir = Path(self.temporary.name) / "audio"
        self.audio_dir.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def _hash(payload):
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _text_item(text):
        return {"raw_text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()}

    def _write_audio(self, condition):
        names = r02_verify_field._master_filenames(condition)
        aiff_payload = f"synthetic-{condition}-aiff".encode()
        m4a_payload = f"synthetic-{condition}-m4a".encode()
        (self.audio_dir / names["aiff"]).write_bytes(aiff_payload)
        (self.audio_dir / names["m4a"]).write_bytes(m4a_payload)
        return names, aiff_payload, m4a_payload

    def _strict_manifest(self, condition):
        names, aiff_payload, m4a_payload = self._write_audio(condition)
        workout_events = []
        for index, (timestamp, duration, text) in enumerate(
            ((0.0, 1.0, "Workout start"), (1792.0, 3.0, "Workout complete")),
            start=1,
        ):
            event = {
                "event_id": f"workout_nav_{index:03d}",
                "timestamp_sec": timestamp,
                "duration_sec": duration,
                "voice": "NAV",
                "synthesis_voice": "Synthetic NAV",
                "synthesis_rate": "100",
                **self._text_item(text),
            }
            workout_events.append(event)

        cue_timestamps = (8.0, 240.0, 365.0, 665.0, 815.0, 965.0, 1115.0, 1415.0, 1510.0, 1650.0)
        cues = []
        for index, ((cue_id, node_id), timestamp) in enumerate(
            zip(r02_verify_field.CANONICAL_CUE_SEQUENCE, cue_timestamps)
        ):
            text = f"Condition {condition} synthetic story {index + 1}"
            segment = {
                "role": "LEA",
                "text": text,
                "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "synthesis_voice": "Synthetic LEA",
                "synthesis_rate": "100",
            }
            cues.append(
                {
                    "cue_id": cue_id,
                    "node_id": node_id,
                    "timestamp_sec": timestamp,
                    "duration_sec": 2.0 + (1.0 if condition == "B" and index == 0 else 0.0),
                    "max_spoken_sec": 20.0,
                    "voice": "LEA",
                    "spoken_segments": [segment],
                    **self._text_item(text),
                }
            )

        schedule = [
            {
                "cue_id": cue["cue_id"],
                "node_id": cue["node_id"],
                "timestamp_sec": cue["timestamp_sec"],
                "voice": cue["voice"],
            }
            for cue in cues
        ]
        manifest = {
            "schema_version": "0.1",
            "tool_schema": r02_verify_field.STRICT_TOOL_SCHEMA,
            "mission_id": "m01",
            "concept_id": "null_layer",
            "condition": condition,
            "branch": "atlas_disclosure=concealed",
            "story_text_field": (
                "condition_a_text" if condition == "A" else "condition_b_text"
            ),
            "binding_id": "synthetic_binding_v1",
            "binding_sha256": "a" * 64,
            "beats_sha256": "b" * 64,
            "sample_rate_hz": 44100,
            "target_duration_sec": 1800.0,
            "actual_duration_aiff_sec": 1800.0,
            "actual_duration_m4a_sec": 1800.0,
            "aiff_file": names["aiff"],
            "m4a_file": names["m4a"],
            "aiff_sha256": self._hash(aiff_payload),
            "m4a_sha256": self._hash(m4a_payload),
            "workout_nav_events_count": len(workout_events),
            "workout_final_nav_timestamp_sec": 1792.0,
            "workout_nav_events": workout_events,
            "workout_nav_events_sha256": r02_verify_field.canonical_json_sha256(
                workout_events
            ),
            "narrative_cues": cues,
            "narrative_schedule_sha256": r02_verify_field.canonical_json_sha256(
                schedule
            ),
        }
        path = self.audio_dir / names["manifest"]
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path, manifest

    def _legacy_manifest(self):
        names, aiff_payload, m4a_payload = self._write_audio("A")
        manifest = {
            "schema_version": "0.1",
            "mission_id": "m01",
            "concept_id": "null_layer",
            "branch": "atlas_disclosure=concealed",
            "target_duration_sec": 1800.0,
            "actual_duration_aiff_sec": 1800.0,
            "actual_duration_m4a_sec": 1800.0,
            "aiff_file": names["aiff"],
            "m4a_file": names["m4a"],
            "aiff_sha256": self._hash(aiff_payload),
            "m4a_sha256": self._hash(m4a_payload),
            "workout_nav_events_count": 27,
            "workout_final_nav_timestamp_sec": 1792.0,
            "narrative_cues": [
                {
                    "cue_id": "cue_1",
                    "node_id": "node_1",
                    "timestamp_sec": 8.0,
                    "duration_sec": 2.0,
                    "voice": "LEA",
                    "raw_text": "Legacy story one",
                },
                {
                    "cue_id": "cue_2",
                    "node_id": "node_2",
                    "timestamp_sec": 10.0,
                    "duration_sec": 1.0,
                    "voice": "LEA",
                    "raw_text": "Legacy story two",
                },
            ],
        }
        path = self.audio_dir / names["manifest"]
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path, manifest

    def _rewrite(self, path, manifest):
        path.write_text(json.dumps(manifest), encoding="utf-8")

    @staticmethod
    def _probe(_path):
        return 1800.0

    def test_valid_legacy_manifest_and_unchanged_audio_dir_api(self):
        path, _ = self._legacy_manifest()
        result = r02_verify_field.verify_manifest(path, duration_probe=self._probe)
        self.assertFalse(result.strict)
        with mock.patch.object(
            r02_verify_field, "probe_audio_duration", side_effect=self._probe
        ):
            self.assertEqual(0, r02_verify_field.verify_audio_dir(self.audio_dir))

    def test_valid_strict_pair_allows_story_text_and_cue_duration_difference(self):
        path_a, _ = self._strict_manifest("A")
        path_b, _ = self._strict_manifest("B")
        verified_a = r02_verify_field.verify_manifest(
            path_a, require_strict=True, duration_probe=self._probe
        )
        verified_b = r02_verify_field.verify_manifest(
            path_b, require_strict=True, duration_probe=self._probe
        )
        r02_verify_field.verify_ab_parity(verified_a, verified_b)

    def test_new_manifest_cannot_downgrade_by_removing_tool_schema(self):
        path_a, manifest_a = self._strict_manifest("A")
        manifest_a.pop("tool_schema")
        self._rewrite(path_a, manifest_a)
        with self.assertRaisesRegex(
            r02_verify_field.VerificationError, "new-format manifest markers"
        ):
            r02_verify_field.verify_manifest(path_a, duration_probe=self._probe)

        path_a, manifest_a = self._strict_manifest("A")
        for field in r02_verify_field.STRICT_TOP_LEVEL_MARKERS | {"tool_schema"}:
            manifest_a.pop(field, None)
        for cue in manifest_a["narrative_cues"]:
            for field in r02_verify_field.STRICT_CUE_MARKERS:
                cue.pop(field, None)
            for segment in cue["spoken_segments"]:
                segment.pop("synthesis_voice", None)
                segment.pop("synthesis_rate", None)
        self._rewrite(path_a, manifest_a)
        with self.assertRaisesRegex(
            r02_verify_field.VerificationError, "new-format manifest markers"
        ):
            r02_verify_field.verify_manifest(path_a, duration_probe=self._probe)

        path_b, manifest_b = self._strict_manifest("B")
        for field in r02_verify_field.STRICT_TOP_LEVEL_MARKERS | {"tool_schema"}:
            manifest_b.pop(field, None)
        for cue in manifest_b["narrative_cues"]:
            for field in r02_verify_field.STRICT_CUE_MARKERS:
                cue.pop(field, None)
            cue.pop("spoken_segments", None)
        self._rewrite(path_b, manifest_b)
        with self.assertRaisesRegex(
            r02_verify_field.VerificationError, "new-format manifest markers"
        ):
            r02_verify_field.verify_manifest(path_b, duration_probe=self._probe)

    def test_strict_spoken_segments_must_match_raw_text(self):
        path, manifest = self._strict_manifest("A")
        segment = manifest["narrative_cues"][0]["spoken_segments"][0]
        segment["text"] = "Entirely unrelated synthesized text"
        segment["text_sha256"] = hashlib.sha256(segment["text"].encode()).hexdigest()
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(
            r02_verify_field.VerificationError,
            "spoken_segments do not match parsed raw_text",
        ):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

    def test_strict_parser_rejects_unlabeled_prefix_instead_of_dropping_it(self):
        path, manifest = self._strict_manifest("A")
        cue = manifest["narrative_cues"][0]
        cue["raw_text"] = "Unlabeled intro. ЛЕА: Spoken line."
        cue["text_sha256"] = hashlib.sha256(cue["raw_text"].encode()).hexdigest()
        segment = cue["spoken_segments"][0]
        segment["text"] = "Spoken line."
        segment["text_sha256"] = hashlib.sha256(segment["text"].encode()).hexdigest()
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "unlabeled text"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

    def test_cue_duration_parity_tolerance_boundary_passes_and_excess_fails(self):
        path_a, _ = self._strict_manifest("A")
        path_b, manifest_b = self._strict_manifest("B")
        manifest_b["narrative_cues"][0]["duration_sec"] = 12.0
        self._rewrite(path_b, manifest_b)
        verified_a = r02_verify_field.verify_manifest(path_a, duration_probe=self._probe)
        verified_b = r02_verify_field.verify_manifest(path_b, duration_probe=self._probe)
        r02_verify_field.verify_ab_parity(verified_a, verified_b)

        manifest_b["narrative_cues"][0]["duration_sec"] = 12.001
        self._rewrite(path_b, manifest_b)
        verified_b = r02_verify_field.verify_manifest(path_b, duration_probe=self._probe)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "more than 10.0s"):
            r02_verify_field.verify_ab_parity(verified_a, verified_b)

    def test_parity_requires_at_least_one_story_text_hash_difference(self):
        path_a, manifest_a = self._strict_manifest("A")
        path_b, manifest_b = self._strict_manifest("B")
        for cue_a, cue_b in zip(
            manifest_a["narrative_cues"], manifest_b["narrative_cues"]
        ):
            cue_b["raw_text"] = cue_a["raw_text"]
            cue_b["text_sha256"] = cue_a["text_sha256"]
            cue_b["spoken_segments"] = json.loads(
                json.dumps(cue_a["spoken_segments"])
            )
        self._rewrite(path_b, manifest_b)
        verified_a = r02_verify_field.verify_manifest(path_a, duration_probe=self._probe)
        verified_b = r02_verify_field.verify_manifest(path_b, duration_probe=self._probe)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "at least one cue"):
            r02_verify_field.verify_ab_parity(verified_a, verified_b)

    def test_parity_rejects_byte_identical_aiff_and_m4a_masters(self):
        path_a, manifest_a = self._strict_manifest("A")
        path_b, manifest_b = self._strict_manifest("B")
        aiff_a = self.audio_dir / manifest_a["aiff_file"]
        aiff_b = self.audio_dir / manifest_b["aiff_file"]
        aiff_b.write_bytes(aiff_a.read_bytes())
        manifest_b["aiff_sha256"] = self._hash(aiff_b.read_bytes())
        self._rewrite(path_b, manifest_b)
        verified_a = r02_verify_field.verify_manifest(path_a, duration_probe=self._probe)
        verified_b = r02_verify_field.verify_manifest(path_b, duration_probe=self._probe)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "AIFF masters are byte-identical"):
            r02_verify_field.verify_ab_parity(verified_a, verified_b)

        path_b, manifest_b = self._strict_manifest("B")
        m4a_a = self.audio_dir / manifest_a["m4a_file"]
        m4a_b = self.audio_dir / manifest_b["m4a_file"]
        m4a_b.write_bytes(m4a_a.read_bytes())
        manifest_b["m4a_sha256"] = self._hash(m4a_b.read_bytes())
        self._rewrite(path_b, manifest_b)
        verified_b = r02_verify_field.verify_manifest(path_b, duration_probe=self._probe)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "M4A masters are byte-identical"):
            r02_verify_field.verify_ab_parity(verified_a, verified_b)

    def test_compare_cli_is_clear_and_backward_compatible(self):
        path_a, _ = self._strict_manifest("A")
        path_b, _ = self._strict_manifest("B")
        with mock.patch.object(
            r02_verify_field, "probe_audio_duration", side_effect=self._probe
        ):
            return_code = r02_verify_field.main(
                ["--manifest", str(path_a), "--compare-manifest", str(path_b)]
            )
        self.assertEqual(0, return_code)

    def test_strict_text_hash_mismatch_is_rejected(self):
        path, manifest = self._strict_manifest("A")
        manifest["narrative_cues"][0]["text_sha256"] = "0" * 64
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "does not match raw_text"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

    def test_strict_manifest_requires_canonical_ten_cue_concealed_sequence(self):
        path, manifest = self._strict_manifest("A")
        manifest["narrative_cues"] = manifest["narrative_cues"][:-1]
        schedule = [
            {
                "cue_id": cue["cue_id"],
                "node_id": cue["node_id"],
                "timestamp_sec": cue["timestamp_sec"],
                "voice": cue["voice"],
            }
            for cue in manifest["narrative_cues"]
        ]
        manifest["narrative_schedule_sha256"] = (
            r02_verify_field.canonical_json_sha256(schedule)
        )
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "canonical ordered 10-cue"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

    def test_strict_cue_must_respect_authored_max_spoken_bound(self):
        path, manifest = self._strict_manifest("A")
        manifest["narrative_cues"][0]["max_spoken_sec"] = 1.0
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "max_spoken_sec"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

    def test_story_overlap_and_truncation_are_rejected(self):
        path, manifest = self._legacy_manifest()
        manifest["narrative_cues"][1]["timestamp_sec"] = 9.999
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "overlaps"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

        manifest["narrative_cues"][1]["timestamp_sec"] = 1799.0
        manifest["narrative_cues"][1]["duration_sec"] = 2.0
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "exceeds"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

    def test_strict_final_nav_audio_must_not_be_truncated(self):
        path, manifest = self._strict_manifest("A")
        manifest["workout_nav_events"][-1]["duration_sec"] = 9.0
        manifest["workout_nav_events_sha256"] = (
            r02_verify_field.canonical_json_sha256(manifest["workout_nav_events"])
        )
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "exceeds"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

    def test_strict_rejects_workout_and_story_audio_overlap(self):
        path, manifest = self._strict_manifest("A")
        manifest["workout_nav_events"][0]["duration_sec"] = 9.0
        manifest["workout_nav_events_sha256"] = (
            r02_verify_field.canonical_json_sha256(manifest["workout_nav_events"])
        )
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(
            r02_verify_field.VerificationError, "overlaps workout NAV"
        ):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

        manifest["workout_nav_events"][0]["duration_sec"] = 1793.0
        manifest["workout_nav_events_sha256"] = (
            r02_verify_field.canonical_json_sha256(manifest["workout_nav_events"])
        )
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(
            r02_verify_field.VerificationError, "overlaps the previous workout"
        ):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

    def test_bad_hash_duration_and_boolean_nav_count_are_rejected(self):
        path, manifest = self._legacy_manifest()
        manifest["m4a_sha256"] = "0" * 64
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "M4A SHA-256 mismatch"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

        manifest["m4a_sha256"] = self._hash((self.audio_dir / manifest["m4a_file"]).read_bytes())
        manifest["actual_duration_m4a_sec"] = 1790.0
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "duration"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

        manifest["actual_duration_m4a_sec"] = 1800.0
        manifest["workout_nav_events_count"] = True
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "positive integer"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

    def test_unknown_schema_nan_and_non_object_manifest_fail_closed(self):
        path, manifest = self._legacy_manifest()
        manifest["schema_version"] = "9.9"
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "schema_version"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

        path.write_text('{"schema_version":"0.1","x":NaN}', encoding="utf-8")
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "non-finite"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

        path.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "root must be an object"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

        path.write_text('{"schema_version":"0.1","schema_version":"0.1"}', encoding="utf-8")
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "duplicate JSON key"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

    def test_unsafe_filename_and_symlink_are_rejected(self):
        path, manifest = self._legacy_manifest()
        manifest["m4a_file"] = "../escape.m4a"
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "plain filename"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

        outside = Path(self.temporary.name) / "outside.m4a"
        outside.write_bytes(b"outside")
        link = self.audio_dir / "linked.m4a"
        link.symlink_to(outside)
        manifest["m4a_file"] = link.name
        self._rewrite(path, manifest)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "must not be a symlink"):
            r02_verify_field.verify_manifest(path, duration_probe=self._probe)

    def test_parity_rejects_metadata_and_cue_schedule_mismatch(self):
        path_a, _ = self._strict_manifest("A")
        path_b, _ = self._strict_manifest("B")
        verified_a = r02_verify_field.verify_manifest(path_a, duration_probe=self._probe)
        verified_b = r02_verify_field.verify_manifest(path_b, duration_probe=self._probe)
        verified_b.manifest["binding_sha256"] = "c" * 64
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "binding_sha256"):
            r02_verify_field.verify_ab_parity(verified_a, verified_b)

        verified_b.manifest["binding_sha256"] = "a" * 64
        verified_b.manifest["narrative_cues"][0]["timestamp_sec"] += 1.0
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "timestamp_sec"):
            r02_verify_field.verify_ab_parity(verified_a, verified_b)

    def test_parity_rejects_individually_valid_workout_difference(self):
        path_a, _ = self._strict_manifest("A")
        path_b, manifest_b = self._strict_manifest("B")
        event = manifest_b["workout_nav_events"][0]
        event["raw_text"] = "Different workout instruction"
        event["text_sha256"] = hashlib.sha256(
            event["raw_text"].encode()
        ).hexdigest()
        manifest_b["workout_nav_events_sha256"] = (
            r02_verify_field.canonical_json_sha256(
                manifest_b["workout_nav_events"]
            )
        )
        self._rewrite(path_b, manifest_b)
        verified_a = r02_verify_field.verify_manifest(path_a, duration_probe=self._probe)
        verified_b = r02_verify_field.verify_manifest(path_b, duration_probe=self._probe)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "workout_nav_events_sha256"):
            r02_verify_field.verify_ab_parity(verified_a, verified_b)

    def test_parity_requires_one_a_one_b_and_strict_manifests(self):
        path_a, _ = self._strict_manifest("A")
        verified_a = r02_verify_field.verify_manifest(path_a, duration_probe=self._probe)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "different manifest"):
            r02_verify_field.verify_ab_parity(verified_a, verified_a)

        legacy_path, _ = self._legacy_manifest()
        legacy = r02_verify_field.verify_manifest(legacy_path, duration_probe=self._probe)
        path_b, _ = self._strict_manifest("B")
        verified_b = r02_verify_field.verify_manifest(path_b, duration_probe=self._probe)
        with self.assertRaisesRegex(r02_verify_field.VerificationError, "provenance-strict"):
            r02_verify_field.verify_ab_parity(legacy, verified_b)

    def test_probe_falls_back_from_afinfo_to_ffprobe(self):
        fake_path = self.audio_dir / "fake.m4a"
        fake_path.write_bytes(b"fake")
        with mock.patch.object(
            r02_verify_field,
            "get_audio_duration_afinfo",
            side_effect=r02_verify_field.VerificationError("no afinfo"),
        ), mock.patch.object(
            r02_verify_field, "get_audio_duration_ffprobe", return_value=1800.0
        ):
            self.assertEqual(1800.0, r02_verify_field.probe_audio_duration(fake_path))


if __name__ == "__main__":
    unittest.main()
