#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from tools import r02_prepare_synthetic_ios


class R02PrepareSyntheticIOSTests(unittest.TestCase):
    def test_prepare_publishes_marked_fail_closed_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "Local"

            def fake_audio(path: Path) -> None:
                path.write_bytes(b"synthetic-audio-test")

            with patch.object(r02_prepare_synthetic_ios, "_generate_silent_m4a", side_effect=fake_audio):
                mission = r02_prepare_synthetic_ios.prepare(output)

            self.assertEqual(
                {path.name for path in output.iterdir()},
                {"mission.json", "m01_solo_founder_30min.m4a", "m01_solo_founder_30min.manifest.json"},
            )
            self.assertIn("SYNTHETIC TEST BUNDLE", mission["locationDisplayName"])
            self.assertFalse(mission["routeInitiallyApproved"])
            self.assertFalse(mission["workoutInitiallyApproved"])
            self.assertFalse(mission["m1HumanApprovalComplete"])
            audio = output / "m01_solo_founder_30min.m4a"
            self.assertEqual(mission["audioSHA256"], hashlib.sha256(audio.read_bytes()).hexdigest())
            manifest = json.loads((output / "m01_solo_founder_30min.manifest.json").read_text(encoding="utf-8"))
            self.assertIs(manifest["synthetic_test_only"], True)

    def test_main_fails_closed_when_audio_generation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, patch.object(
            r02_prepare_synthetic_ios,
            "_generate_silent_m4a",
            side_effect=RuntimeError("encoder unavailable"),
        ):
            with redirect_stderr(io.StringIO()):
                self.assertEqual(
                    r02_prepare_synthetic_ios.main(["--output-dir", temp_dir]),
                    1,
                )
