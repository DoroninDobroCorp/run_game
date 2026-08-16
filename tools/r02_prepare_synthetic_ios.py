#!/usr/bin/env python3
"""Create a privacy-safe iOS bundle for clean-clone build and automated tests.

The generated bundle is intentionally unsuitable for physical or field testing.
Production/device handoff must always use ``r02_prepare_ios.py`` with the private
Valparaíso fixture and accepted master-audio hash.
"""

from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import wave
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "ios/RunGameFounder/Resources/Local"
SYNTHETIC_AUDIO_DURATION_SECONDS = 30
r02_prepare_ios = importlib.import_module(
    "tools.r02_prepare_ios" if __package__ else "r02_prepare_ios"
)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _generate_silent_m4a(output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="r02-synthetic-audio-") as temp_dir:
        wav_path = Path(temp_dir) / "silence.wav"
        sample_rate = 8_000
        samples_remaining = sample_rate * SYNTHETIC_AUDIO_DURATION_SECONDS
        with wave.open(str(wav_path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            silent_chunk = b"\0\0" * sample_rate
            while samples_remaining > 0:
                count = min(samples_remaining, sample_rate)
                handle.writeframes(silent_chunk[: count * 2])
                samples_remaining -= count

        commands: list[list[str]] = []
        if shutil.which("afconvert"):
            commands.append(
                [
                    "afconvert",
                    str(wav_path),
                    str(output),
                    "-f",
                    "m4af",
                    "-d",
                    "aac",
                    "-b",
                    "16000",
                ]
            )
        if shutil.which("ffmpeg"):
            commands.append(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-y",
                    "-i",
                    str(wav_path),
                    "-c:a",
                    "aac",
                    "-b:a",
                    "16k",
                    str(output),
                ]
            )

        failures: list[str] = []
        for command in commands:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and output.is_file() and output.stat().st_size > 0:
                return
            failures.append(f"{command[0]}: {result.stderr.strip() or result.returncode}")
        raise RuntimeError(
            "Could not generate synthetic M4A; install ffmpeg or use macOS afconvert. "
            + "; ".join(failures)
        )


def prepare(output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="r02-synthetic-ios-") as temp_dir:
        stage = Path(temp_dir)
        audio_path = stage / r02_prepare_ios.EXPECTED_M4A_FILE
        manifest_path = stage / r02_prepare_ios.EXPECTED_MANIFEST_FILE
        _generate_silent_m4a(audio_path)

        audio_sha = r02_prepare_ios.compute_sha256(audio_path)
        manifest = {
            "schema_version": "0.1",
            "synthetic_test_only": True,
            "concept_id": "null_layer",
            "mission_id": "m01",
            "binding_id": "synthetic_ci_fixture_v1",
            "branch": "atlas_disclosure=concealed",
            "target_duration_sec": 1800.0,
            "actual_duration_m4a_sec": float(SYNTHETIC_AUDIO_DURATION_SECONDS),
            "workout_final_nav_timestamp_sec": 1792.0,
            "workout_nav_events_count": 27,
            "m4a_file": audio_path.name,
            "m4a_sha256": audio_sha,
            "narrative_cues": [
                {
                    "cue_id": "synthetic-warning",
                    "node_id": "synthetic_test_only",
                    "timestamp_sec": 0.0,
                    "duration_sec": 2.0,
                    "raw_text": "Synthetic automated-test audio. Not for field use.",
                }
            ],
        }
        _write_json(manifest_path, manifest)

        route_points = [
            {"id": "start_and_finish-0", "role": "start_and_finish", "roleLabel": "Старт", "name": "Synthetic Start", "latitude": 10.0, "longitude": 20.0, "osmURL": "https://www.openstreetmap.org/node/1"},
            {"id": "threshold-1", "role": "threshold", "roleLabel": "Порог", "name": "Synthetic Threshold", "latitude": 10.0001, "longitude": 20.0001, "osmURL": "https://www.openstreetmap.org/node/2"},
            {"id": "witness-2", "role": "witness", "roleLabel": "Свидетель", "name": "Synthetic Witness", "latitude": 10.0002, "longitude": 20.0001, "osmURL": "https://www.openstreetmap.org/node/3"},
            {"id": "triangulation-3", "role": "triangulation", "roleLabel": "Триангуляция", "name": "Synthetic Triangulation", "latitude": 10.0001, "longitude": 20.0002, "osmURL": "https://www.openstreetmap.org/node/4"},
            {"id": "start_and_finish-4", "role": "start_and_finish", "roleLabel": "Финиш", "name": "Synthetic Start", "latitude": 10.0, "longitude": 20.0, "osmURL": "https://www.openstreetmap.org/node/1"},
        ]
        timeline = r02_prepare_ios._timeline()
        synthetic_binding = {
            "binding_id": "synthetic_ci_fixture_v1",
            "route_id": "synthetic_ci_route_v1",
            "public_start": False,
            "slots": {},
        }
        mission = {
            "schemaVersion": "0.1",
            "missionID": "m01",
            "title": "Линия, которой нет",
            "subtitle": "Нулевой слой · Миссия 1",
            "locationDisplayName": "SYNTHETIC TEST BUNDLE — НЕ ДЛЯ МАРШРУТА",
            "bindingID": "synthetic_ci_fixture_v1",
            "bindingContractSHA256": r02_prepare_ios.binding_contract_sha256(synthetic_binding),
            "bindingSHA256": r02_prepare_ios.canonical_json_sha256(synthetic_binding),
            "snapshotSHA256": r02_prepare_ios.canonical_json_sha256({"synthetic": True}),
            "gpxPrefix": "synthetic-ci-route",
            "audioFile": audio_path.name,
            "audioSHA256": audio_sha,
            "audioManifestSHA256": r02_prepare_ios.compute_sha256(manifest_path),
            "durationSeconds": 1800.0,
            "routeInitiallyApproved": False,
            "workoutInitiallyApproved": False,
            "m1HumanApprovalComplete": False,
            "routePoints": route_points,
            "routeSHA256": r02_prepare_ios.canonical_json_sha256(route_points),
            "timeline": timeline,
            "timelineSHA256": r02_prepare_ios.canonical_json_sha256(timeline),
            "evidenceNotice": "SYNTHETIC TEST BUNDLE: запрещено использовать для device smoke, маршрута или founder evidence.",
        }

        validated = {
            "mission": mission,
            "manifest": manifest,
            "m4a_path": audio_path,
            "manifest_path": manifest_path,
        }
        r02_prepare_ios._publish_validated_bundle(validated, output_dir)
        return mission


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        mission = prepare(args.output_dir)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        "Synthetic iOS resources prepared for build/tests only: "
        f"{mission['bindingID']} -> {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
