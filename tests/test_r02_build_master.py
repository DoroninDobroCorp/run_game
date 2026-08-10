import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import wave

from tools import r02_build_master


class R02BuildMasterTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.beats_path = self.root / "beats.json"
        self.binding_path = self.root / "binding.json"
        self.output_dir = self.root / "audio"
        self.beats = {
            "schema_version": "0.1",
            "concept_id": "null_layer",
            "mission_id": "m01",
            "target_duration_sec": 10.0,
            "operator_rules": [
                "Synthetic fixture keeps atlas_disclosure=concealed fixed."
            ],
            "cues": [
                {
                    "cue_id": "cue_1",
                    "node_id": "node_1",
                    "voice": "LEA",
                    "max_spoken_sec": 5.0,
                    "trigger": {"window_sec": [0.0, 2.0]},
                    "condition_a_text": "ЛЕА: У {threshold.name} внешний сигнал.",
                    "condition_b_text": "ЛЕА: Первый внутренний сигнал.",
                },
                {
                    "cue_id": "cue_2",
                    "node_id": "node_2",
                    "voice": "ATLAS+LEA",
                    "max_spoken_sec": 5.0,
                    "trigger": {"window_sec": [4.0, 6.0]},
                    "condition_a_text": "АТЛАС: Проверка. ЛЕА: Второй сигнал.",
                    "condition_b_text": "АТЛАС: Проверка. ЛЕА: Другой второй сигнал.",
                },
            ],
        }
        self.binding = {
            "schema_version": "0.1",
            "binding_id": "synthetic_binding_v1",
            "slots": {"threshold": {"name": "Синтетический порог"}},
        }
        self._write_sources()

    def tearDown(self):
        self.temporary.cleanup()

    def _write_sources(self):
        self.beats_path.write_text(
            json.dumps(self.beats, ensure_ascii=False), encoding="utf-8"
        )
        self.binding_path.write_text(
            json.dumps(self.binding, ensure_ascii=False), encoding="utf-8"
        )

    def _patch_small_timeline(self):
        return mock.patch.multiple(
            r02_build_master,
            SAMPLE_RATE=10,
            TARGET_DURATION_SEC=10.0,
            TOTAL_SAMPLES=100,
            FINAL_NAV_MIN_SEC=9.0,
            FINAL_NAV_MAX_SEC=9.5,
            WORKOUT_NAV_EVENTS=[
                (0.0, "NAV", "Synthetic workout start."),
                (9.0, "NAV", "Synthetic workout complete."),
            ],
            STORY_CUE_TIMESTAMPS={"cue_1": 1.0, "cue_2": 5.0},
            CANONICAL_CUE_SEQUENCE=(("cue_1", "node_1"), ("cue_2", "node_2")),
        )

    @staticmethod
    def _fake_tts(_text, role, output_path):
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(10)
            wav_file.writeframes((100).to_bytes(2, "little", signed=True) * 2)
        return {"voice": f"synthetic-{role}", "rate": "100"}

    @staticmethod
    def _fake_conversion(master_wav, master_aiff, master_m4a):
        payload = master_wav.read_bytes()
        master_aiff.write_bytes(payload + b"-aiff")
        master_m4a.write_bytes(payload + b"-m4a")

    def test_default_a_and_condition_b_filenames_are_backward_compatible(self):
        self.assertEqual(
            "m01_solo_founder_30min.m4a",
            r02_build_master.master_filenames("A")["m4a"],
        )
        self.assertEqual(
            "m01_solo_founder_30min_condition_b.m4a",
            r02_build_master.master_filenames("B")["m4a"],
        )
        with self.assertRaisesRegex(ValueError, "condition must be A or B"):
            r02_build_master.master_filenames("b")

    def test_build_plan_selects_and_binds_the_requested_condition(self):
        with self._patch_small_timeline():
            plan_a = r02_build_master.prepare_build_plan(
                self.beats, self.binding, "A"
            )
            plan_b = r02_build_master.prepare_build_plan(
                self.beats, self.binding, "B"
            )

        self.assertIn("Синтетический порог", plan_a[0]["raw_text"])
        self.assertNotIn("Синтетический порог", plan_b[0]["raw_text"])
        self.assertEqual(
            "ЛЕА: Первый внутренний сигнал.", plan_b[0]["raw_text"]
        )
        self.assertEqual(
            hashlib.sha256(plan_b[0]["raw_text"].encode("utf-8")).hexdigest(),
            plan_b[0]["text_sha256"],
        )

    def test_condition_b_place_placeholder_fails_before_tts(self):
        self.beats["cues"][0]["condition_b_text"] = (
            "ЛЕА: Нельзя использовать {threshold.name}."
        )
        self._write_sources()
        with self._patch_small_timeline(), mock.patch.object(
            r02_build_master, "tts_segment_to_wav"
        ) as synthesize:
            with self.assertRaisesRegex(ValueError, "Condition B text contains"):
                r02_build_master.build_master_audio(
                    self.beats_path,
                    self.binding_path,
                    self.output_dir,
                    condition="B",
                )
        synthesize.assert_not_called()
        self.assertFalse(self.output_dir.exists())

    def test_condition_b_literal_bound_place_name_fails_before_tts(self):
        self.beats["cues"][0]["condition_b_text"] = (
            "ЛЕА: Видишь СИНТЕТИЧЕСКИЙ ПОРОГ перед собой."
        )
        self._write_sources()
        with self._patch_small_timeline(), mock.patch.object(
            r02_build_master, "tts_segment_to_wav"
        ) as synthesize:
            with self.assertRaisesRegex(ValueError, "contains a bound place name"):
                r02_build_master.build_master_audio(
                    self.beats_path,
                    self.binding_path,
                    self.output_dir,
                    condition="B",
                )
        synthesize.assert_not_called()
        self.assertFalse(self.output_dir.exists())

    def test_condition_b_literal_name_guard_normalizes_unicode(self):
        self.binding["slots"]["threshold"]["name"] = "Café"
        self.beats["cues"][0]["condition_b_text"] = "ЛЕА: Вижу Cafe\u0301."
        self._write_sources()
        with self._patch_small_timeline(), mock.patch.object(
            r02_build_master, "tts_segment_to_wav"
        ) as synthesize:
            with self.assertRaisesRegex(ValueError, "contains a bound place name"):
                r02_build_master.build_master_audio(
                    self.beats_path,
                    self.binding_path,
                    self.output_dir,
                    condition="B",
                )
        synthesize.assert_not_called()
        self.assertFalse(self.output_dir.exists())

    def test_dialogue_parser_rejects_unlabeled_prefix_instead_of_dropping_it(self):
        with self.assertRaisesRegex(ValueError, "unlabeled text"):
            r02_build_master.parse_dialogue_segments("Intro. ЛЕА: Spoken line.")

    @mock.patch.object(r02_build_master, "FINAL_NAV_MIN_SEC", 9.0)
    @mock.patch.object(r02_build_master, "FINAL_NAV_MAX_SEC", 9.5)
    def test_timeline_rejects_zero_duration_overlap_and_truncation(self):
        workout = [
            {
                "timestamp_sec": 0.0,
                "duration_sec": 1.0,
                "voice": "NAV",
            },
            {
                "timestamp_sec": 9.0,
                "duration_sec": 0.5,
                "voice": "NAV",
            },
        ]
        stories = [
            {"cue_id": "one", "timestamp_sec": 1.0, "duration_sec": 2.0},
            {"cue_id": "two", "timestamp_sec": 3.0, "duration_sec": 1.0},
        ]
        r02_build_master.validate_rendered_timeline(workout, stories, 10.0)

        workout[1]["timestamp_sec"] = 8.999
        with self.assertRaisesRegex(ValueError, "outside the safe"):
            r02_build_master.validate_rendered_timeline(workout, stories, 10.0)
        workout[1]["timestamp_sec"] = 9.0

        workout[1]["timestamp_sec"] = 0.999
        with self.assertRaisesRegex(ValueError, "overlaps the previous workout"):
            r02_build_master.validate_rendered_timeline(workout, stories, 10.0)
        workout[1]["timestamp_sec"] = 9.0

        stories[0]["timestamp_sec"] = 0.999
        with self.assertRaisesRegex(ValueError, "overlaps workout NAV"):
            r02_build_master.validate_rendered_timeline(workout, stories, 10.0)
        stories[0]["timestamp_sec"] = 1.0

        stories[1]["timestamp_sec"] = 2.999
        with self.assertRaisesRegex(ValueError, "overlaps"):
            r02_build_master.validate_rendered_timeline(workout, stories, 10.0)
        stories[1]["timestamp_sec"] = 3.0
        stories[1]["duration_sec"] = 0.0
        with self.assertRaisesRegex(ValueError, "invalid timing"):
            r02_build_master.validate_rendered_timeline(workout, stories, 10.0)
        stories[1]["duration_sec"] = 8.0
        with self.assertRaisesRegex(ValueError, "truncated"):
            r02_build_master.validate_rendered_timeline(workout, stories, 10.0)

    def test_synthetic_condition_b_build_has_strict_provenance(self):
        with self._patch_small_timeline(), mock.patch.object(
            r02_build_master,
            "tts_segment_to_wav",
            side_effect=self._fake_tts,
        ), mock.patch.object(
            r02_build_master,
            "convert_master_formats",
            side_effect=self._fake_conversion,
        ), mock.patch.object(
            r02_build_master,
            "get_audio_duration_afinfo",
            return_value=10.0,
        ):
            manifest = r02_build_master.build_master_audio(
                self.beats_path,
                self.binding_path,
                self.output_dir,
                condition="B",
            )

        expected_names = {
            "m01_solo_founder_30min_condition_b.aiff",
            "m01_solo_founder_30min_condition_b.m4a",
            "m01_solo_founder_30min_condition_b.manifest.json",
        }
        self.assertEqual(expected_names, {path.name for path in self.output_dir.iterdir()})
        self.assertEqual("0.1", manifest["schema_version"])
        self.assertEqual(r02_build_master.TOOL_SCHEMA, manifest["tool_schema"])
        self.assertEqual("B", manifest["condition"])
        self.assertEqual("condition_b_text", manifest["story_text_field"])
        self.assertEqual("synthetic_binding_v1", manifest["binding_id"])
        self.assertEqual(
            hashlib.sha256(self.binding_path.read_bytes()).hexdigest(),
            manifest["binding_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(self.beats_path.read_bytes()).hexdigest(),
            manifest["beats_sha256"],
        )
        self.assertEqual("cue_1", manifest["narrative_cues"][0]["cue_id"])
        self.assertEqual("node_1", manifest["narrative_cues"][0]["node_id"])
        self.assertEqual(1.0, manifest["narrative_cues"][0]["timestamp_sec"])
        self.assertEqual(
            "ЛЕА: Первый внутренний сигнал.",
            manifest["narrative_cues"][0]["raw_text"],
        )
        self.assertEqual(9.0, manifest["workout_final_nav_timestamp_sec"])

    def test_failed_staged_build_preserves_previous_master_trio(self):
        names = r02_build_master.master_filenames("B")
        self.output_dir.mkdir()
        old_payloads = {}
        for name in names.values():
            payload = f"old-{name}".encode()
            old_payloads[name] = payload
            (self.output_dir / name).write_bytes(payload)

        with self._patch_small_timeline(), mock.patch.object(
            r02_build_master,
            "tts_segment_to_wav",
            side_effect=self._fake_tts,
        ), mock.patch.object(
            r02_build_master,
            "convert_master_formats",
            side_effect=RuntimeError("synthetic conversion failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic conversion failure"):
                r02_build_master.build_master_audio(
                    self.beats_path,
                    self.binding_path,
                    self.output_dir,
                    condition="B",
                )

        for name, payload in old_payloads.items():
            self.assertEqual(payload, (self.output_dir / name).read_bytes())

    def test_all_silent_synthetic_segment_fails_before_publish(self):
        def silent_tts(_text, role, output_path):
            with wave.open(str(output_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(10)
                wav_file.writeframes(b"\x00\x00" * 2)
            return {"voice": f"synthetic-{role}", "rate": "100"}

        with self._patch_small_timeline(), mock.patch.object(
            r02_build_master,
            "tts_segment_to_wav",
            side_effect=silent_tts,
        ), mock.patch.object(r02_build_master, "convert_master_formats") as convert:
            with self.assertRaisesRegex(RuntimeError, "all-silent"):
                r02_build_master.build_master_audio(
                    self.beats_path,
                    self.binding_path,
                    self.output_dir,
                    condition="B",
                )
        convert.assert_not_called()
        self.assertFalse(self.output_dir.exists())

    def test_publish_failure_rolls_back_every_previous_file(self):
        stage = self.root / "stage"
        output = self.root / "published"
        stage.mkdir()
        output.mkdir()
        names = ["one", "two", "three"]
        for name in names:
            (stage / name).write_bytes(f"new-{name}".encode())
            (output / name).write_bytes(f"old-{name}".encode())

        real_replace = os.replace

        def flaky_replace(source, destination):
            source_path = Path(source)
            if source_path.parent == stage and source_path.name == "two":
                raise OSError("synthetic publish failure")
            return real_replace(source, destination)

        with mock.patch.object(r02_build_master.os, "replace", side_effect=flaky_replace):
            with self.assertRaisesRegex(RuntimeError, "previous trio restored"):
                r02_build_master.publish_staged_files(stage, output, names)

        for name in names:
            self.assertEqual(f"old-{name}".encode(), (output / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
