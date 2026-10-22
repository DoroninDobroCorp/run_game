#!/usr/bin/env python3
"""Build a non-authoritative R02 technical fixture from a retained app projection.

The original binding, OSM snapshot and AIFF were lost. This tool preserves the
accepted M4A and the installed app's route projection, reconstructs only the
minimum source JSON required for technical device QA, and decodes a replacement
AIFF from the accepted M4A. Every generated document explicitly remains
unapproved for field use; it must never be represented as the lost original
bundle or used to approve a participant/field run.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any

r02_prepare_ios = importlib.import_module(
    "tools.r02_prepare_ios" if __package__ else "r02_prepare_ios"
)
r02_story = importlib.import_module("tools.r02_story" if __package__ else "r02_story")
r02_doctor = importlib.import_module("tools.r02_doctor" if __package__ else "r02_doctor")

M4A_NAME = r02_prepare_ios.EXPECTED_M4A_FILE
MANIFEST_NAME = r02_prepare_ios.EXPECTED_MANIFEST_FILE
AIFF_NAME = "m01_solo_founder_30min.aiff"
RECONSTITUTION_STATUS = "RECONSTITUTED_TECHNICAL_FIXTURE_NOT_FIELD_APPROVED"
OSM_URL_PATTERN = re.compile(r"https://www\.openstreetmap\.org/(node|way|relation)/(\d+)\Z")
SLOT_ARCHETYPES = {
    "threshold": "passage",
    "witness": "distinct_structure",
    "triangulation": "open_square",
}


def load_json(path: Path) -> dict[str, Any]:
    return r02_prepare_ios.load_json(path)


def _required_string(document: dict[str, Any], key: str, label: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} requires a non-empty {key}")
    return value.strip()


def _route_candidates(mission: dict[str, Any]) -> dict[str, dict[str, Any]]:
    points = mission.get("routePoints")
    if not isinstance(points, list) or len(points) != len(r02_prepare_ios.ROLES):
        raise ValueError("Cached mission must contain the exact five R02 route points")

    candidates: dict[str, dict[str, Any]] = {}
    start_identity: tuple[Any, ...] | None = None
    for index, (expected_role, _) in enumerate(r02_prepare_ios.ROLES):
        point = points[index]
        if not isinstance(point, dict) or point.get("role") != expected_role:
            raise ValueError("Cached mission route-point role ordering is invalid")
        name = _required_string(point, "name", "Cached route point")
        osm_url = _required_string(point, "osmURL", "Cached route point")
        match = OSM_URL_PATTERN.fullmatch(osm_url)
        if match is None:
            raise ValueError("Cached route point does not have a canonical OSM URL")
        latitude = point.get("latitude")
        longitude = point.get("longitude")
        if isinstance(latitude, bool) or isinstance(longitude, bool):
            raise ValueError("Cached route point has invalid coordinates")
        if not isinstance(latitude, (int, float)) or not isinstance(longitude, (int, float)):
            raise ValueError("Cached route point lacks numeric coordinates")
        candidate = {
            "osm_type": match.group(1),
            "osm_id": int(match.group(2)),
            "name": name,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "osm_url": osm_url,
        }
        if expected_role == "start_and_finish":
            identity = (name, float(latitude), float(longitude), osm_url)
            if start_identity is None:
                start_identity = identity
            elif identity != start_identity:
                raise ValueError("Cached mission start and finish do not identify the same point")
        if expected_role in candidates and candidates[expected_role] != candidate:
            raise ValueError(f"Cached mission contains conflicting candidate for {expected_role}")
        candidates[expected_role] = candidate

    if set(candidates) != set(r02_prepare_ios.REQUIRED_ROUTE_ROLES):
        raise ValueError("Cached mission does not cover every required R02 route role")
    return candidates


def _build_binding(mission: dict[str, Any], candidates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source_binding_id = _required_string(mission, "bindingID", "Cached mission")
    slots: dict[str, dict[str, Any]] = {}
    for slot_id in r02_prepare_ios.REQUIRED_BINDING_SLOTS:
        candidate = candidates[slot_id]
        slots[slot_id] = {
            "name": candidate["name"],
            "archetype": SLOT_ARCHETYPES[slot_id],
            "visible_attributes": [],
            "source_refs": [candidate["osm_url"]],
            "operator_trigger": "Requires founder field review before use.",
            "human_approved": False,
        }
    return {
        "schema_version": "0.1",
        "binding_id": f"{source_binding_id}_reconstituted",
        "route_id": "r02_technical_reconstitution_2026_08",
        "research_mode": "traveler_fixture",
        "product_model": "home_territory",
        "city_alias": "reconstituted_r02_fixture",
        "public_start": False,
        "human_route_approved": False,
        "workout_approved": False,
        "human_approved": False,
        "slots": slots,
        "provisional_route_metadata": {
            "start_and_finish_name": candidates["start_and_finish"]["name"],
            "source_ref": candidates["start_and_finish"]["osm_url"],
            "measured_loop_length_meters": None,
            "measured_elevation_gain_meters": None,
            "poi_leg_distances_meters": None,
            "expected_poi_arrival_cue_sec": None,
            "route_surface_notes": None,
            "crossing_notes": None,
            "daylight_walkthrough_completed_at_local": None,
        },
        "fixture_provenance": {
            "status": RECONSTITUTION_STATUS,
            "source": "installed_app_mission_projection_plus_accepted_m4a",
            "lost_original_files": [
                "current.binding.json",
                "osm_snapshot.json",
                f"audio/{AIFF_NAME}",
            ],
            "field_approval_forbidden": True,
        },
    }


def _build_snapshot(mission: dict[str, Any], candidates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "city": _required_string(mission, "locationDisplayName", "Cached mission"),
        "fixture_metadata": {
            "display_name": _required_string(mission, "locationDisplayName", "Cached mission"),
            "gpx_prefix": _required_string(mission, "gpxPrefix", "Cached mission"),
            "provenance": RECONSTITUTION_STATUS,
        },
        "osm_candidates": candidates,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _decode_aiff(m4a_path: Path, aiff_path: Path) -> None:
    result = subprocess.run(
        ["afconvert", "-f", "AIFF", "-d", "BEI16@44100", "-c", "1", str(m4a_path), str(aiff_path)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"afconvert failed: {result.stderr.strip() or result.stdout.strip()}")
    if not aiff_path.is_file() or aiff_path.stat().st_size == 0:
        raise RuntimeError("afconvert did not produce a non-empty AIFF")


def reconstitute(
    mission_source: Path,
    audio_source: Path,
    manifest_source: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Create a new local fixture, fail-closed on ambiguous cached input."""
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite fixture directory: {output_dir}")
    if audio_source.name != M4A_NAME or manifest_source.name != MANIFEST_NAME:
        raise ValueError("Audio sources must use canonical R02 filenames")

    mission = load_json(mission_source)
    candidates = _route_candidates(mission)
    manifest = load_json(manifest_source)
    if r02_prepare_ios.compute_sha256(audio_source) != manifest.get("m4a_sha256"):
        raise ValueError("Recovered M4A does not match its source manifest")
    if r02_prepare_ios.compute_sha256(audio_source) != r02_doctor.EXPECTED_MASTER_SHA256:
        raise ValueError("Recovered M4A does not match the accepted production hash")

    raw_manifest = manifest_source.read_text(encoding="utf-8")
    for slot_id in r02_prepare_ios.REQUIRED_BINDING_SLOTS:
        if candidates[slot_id]["name"] not in raw_manifest:
            raise ValueError(f"Recovered manifest does not contain the {slot_id} candidate name")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{output_dir.name}.stage-", dir=output_dir.parent) as temp_dir:
        stage = Path(temp_dir)
        audio_dir = stage / "audio"
        audio_dir.mkdir()
        shutil.copy2(audio_source, audio_dir / M4A_NAME)
        _decode_aiff(audio_dir / M4A_NAME, audio_dir / AIFF_NAME)
        aiff_duration = r02_prepare_ios.probe_audio_duration(audio_dir / AIFF_NAME)

        rebuilt_manifest = deepcopy(manifest)
        rebuilt_manifest["aiff_file"] = AIFF_NAME
        rebuilt_manifest["aiff_sha256"] = r02_prepare_ios.compute_sha256(audio_dir / AIFF_NAME)
        rebuilt_manifest["actual_duration_aiff_sec"] = aiff_duration
        rebuilt_manifest["fixture_provenance"] = {
            "status": RECONSTITUTION_STATUS,
            "m4a": "accepted production M4A recovered from installed app",
            "aiff": "decoded replacement from recovered M4A; original AIFF is unavailable",
            "field_approval_forbidden": True,
        }
        _write_json(audio_dir / MANIFEST_NAME, rebuilt_manifest)
        _write_json(stage / "current.binding.json", _build_binding(mission, candidates))
        _write_json(stage / "osm_snapshot.json", _build_snapshot(mission, candidates))

        r02_prepare_ios.validate_fixture(stage)
        r02_story.validate_binding(load_json(stage / "current.binding.json"), participant=False)
        shutil.copytree(stage, output_dir)

    return {
        "status": RECONSTITUTION_STATUS,
        "fixture_dir": str(output_dir),
        "m4a_sha256": r02_prepare_ios.compute_sha256(output_dir / "audio" / M4A_NAME),
        "aiff_sha256": r02_prepare_ios.compute_sha256(output_dir / "audio" / AIFF_NAME),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mission-source", type=Path, required=True)
    parser.add_argument("--audio-source", type=Path, required=True)
    parser.add_argument("--manifest-source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = reconstitute(
        args.mission_source, args.audio_source, args.manifest_source, args.output_dir
    )
    print(
        f"{result['status']}: fixture created; "
        "human field approvals remain false and mandatory."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
