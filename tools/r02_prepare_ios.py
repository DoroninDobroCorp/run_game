#!/usr/bin/env python3
"""Prepare the local, privacy-sensitive resources for the founder iPhone app."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "research/r02/local/valparaiso_central"
DEFAULT_OUTPUT = ROOT / "ios/RunGameFounder/Resources/Local"

ROLES = (
    ("start_and_finish", "Старт и финиш"),
    ("threshold", "Порог"),
    ("witness", "Свидетель"),
    ("triangulation", "Триангуляция"),
    ("start_and_finish", "Финиш"),
)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def prepare(fixture_dir: Path, output_dir: Path) -> dict:
    binding_path = fixture_dir / "current.binding.json"
    snapshot_path = fixture_dir / "osm_snapshot.json"
    audio_dir = fixture_dir / "audio"
    manifest_path = audio_dir / "m01_solo_founder_30min.manifest.json"

    required = [binding_path, snapshot_path, manifest_path]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing founder fixture files: " + ", ".join(missing))

    binding = load_json(binding_path)
    snapshot = load_json(snapshot_path)
    manifest = load_json(manifest_path)
    m4a_path = audio_dir / manifest["m4a_file"]
    if not m4a_path.exists():
        raise FileNotFoundError(f"Missing master audio: {m4a_path}")

    candidates = snapshot.get("osm_candidates", {})
    route_points = []
    for index, (role, role_label) in enumerate(ROLES):
        candidate = candidates.get(role, {})
        latitude = candidate.get("latitude")
        longitude = candidate.get("longitude")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise ValueError(f"Candidate '{role}' has no numeric latitude/longitude")
        route_points.append({
            "id": f"{role}-{index}",
            "role": role,
            "roleLabel": role_label,
            "name": candidate["name"],
            "latitude": latitude,
            "longitude": longitude,
            "osmURL": candidate["osm_url"],
        })

    mission = {
        "schemaVersion": "0.1",
        "missionID": "m01",
        "title": "Линия, которой нет",
        "subtitle": "Нулевой слой · Миссия 1",
        "locationDisplayName": "Центральный Вальпараисо",
        "bindingID": binding["binding_id"],
        "audioFile": m4a_path.name,
        "audioSHA256": manifest["m4a_sha256"],
        "durationSeconds": manifest["target_duration_sec"],
        "routeInitiallyApproved": bool(binding.get("human_route_approved", False)),
        "workoutInitiallyApproved": bool(binding.get("workout_approved", False)),
        "routePoints": route_points,
        "timeline": [
            {"start": 0, "end": 300, "label": "Разминка · ходьба", "kind": "walk"},
            *[
                item
                for repetition in range(8)
                for item in (
                    {
                        "start": 300 + repetition * 150,
                        "end": 360 + repetition * 150,
                        "label": f"Бег {repetition + 1} из 8",
                        "kind": "run",
                    },
                    {
                        "start": 360 + repetition * 150,
                        "end": 450 + repetition * 150,
                        "label": "Восстановление · ходьба",
                        "kind": "walk",
                    },
                )
            ],
            {"start": 1500, "end": 1800, "label": "Заминка · ходьба", "kind": "cooldown"},
        ],
        "evidenceNotice": "Маршрут и нагрузка становятся доступными для боевого запуска только после дневного обхода и домашней аудиопроверки.",
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    mission_path = output_dir / "mission.json"
    mission_path.write_text(json.dumps(mission, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(m4a_path, output_dir / m4a_path.name)
    shutil.copy2(manifest_path, output_dir / manifest_path.name)
    return mission


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        mission = prepare(args.fixture_dir, args.output_dir)
        print(
            f"iOS founder resources prepared: {mission['title']} / "
            f"{len(mission['routePoints'])} route points"
        )
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
