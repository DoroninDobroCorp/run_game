#!/usr/bin/env python3
"""Validate and prepare privacy-sensitive resources for the founder iPhone app."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "research/r02/local/valparaiso_central"
DEFAULT_OUTPUT = ROOT / "ios/RunGameFounder/Resources/Local"

EXPECTED_M4A_FILE = "m01_solo_founder_30min.m4a"
EXPECTED_MANIFEST_FILE = "m01_solo_founder_30min.manifest.json"
EXPECTED_SCHEMA_VERSION = "0.1"
EXPECTED_CONCEPT_ID = "null_layer"
EXPECTED_MISSION_ID = "m01"
EXPECTED_BRANCH = "atlas_disclosure=concealed"
EXPECTED_DURATION_SEC = 1800.0
DURATION_TOLERANCE_SEC = 0.5
EXPECTED_NAV_EVENT_COUNT = 27
FINAL_NAV_MIN_SEC = 1790.0
FINAL_NAV_MAX_SEC = 1795.0

REQUIRED_ROUTE_ROLES = (
    "start_and_finish",
    "threshold",
    "witness",
    "triangulation",
)
REQUIRED_BINDING_SLOTS = ("threshold", "witness", "triangulation")
REQUIRED_FIELD_REVIEW_KEYS = (
    "measured_loop_length_meters",
    "measured_elevation_gain_meters",
    "poi_leg_distances_meters",
    "expected_poi_arrival_cue_sec",
    "route_surface_notes",
    "crossing_notes",
    "daylight_walkthrough_completed_at_local",
)
ROLES = (
    ("start_and_finish", "Старт и финиш"),
    ("threshold", "Порог"),
    ("witness", "Свидетель"),
    ("triangulation", "Триангуляция"),
    ("start_and_finish", "Финиш"),
)


def _json_constant_error(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value!r} is not allowed")


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r} is not allowed")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(
            handle,
            parse_constant=_json_constant_error,
            object_pairs_hook=_json_object_without_duplicates,
        )
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON value must be an object")
    return value


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def binding_contract_sha256(binding: dict[str, Any]) -> str:
    slots = binding.get("slots", {})
    payload = {
        "binding_id": binding.get("binding_id"),
        "route_id": binding.get("route_id"),
        "public_start": binding.get("public_start"),
        "slots": {
            slot_id: {
                key: slots.get(slot_id, {}).get(key)
                for key in (
                    "name",
                    "archetype",
                    "visible_attributes",
                    "source_refs",
                    "operator_trigger",
                )
            }
            for slot_id in REQUIRED_BINDING_SLOTS
        },
    }
    return canonical_json_sha256(payload)


def _parse_afinfo_duration(output: str) -> float:
    match = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", output)
    if match is None:
        raise ValueError("estimated duration field is missing")
    return float(match.group(1))


def probe_audio_duration(path: Path) -> float:
    """Return decoded container duration using ffprobe, with macOS afinfo fallback."""
    failures: list[str] = []
    commands: tuple[tuple[list[str], Callable[[str], float]], ...] = (
        (
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            lambda output: float(output.strip()),
        ),
        (
            ["afinfo", str(path)],
            _parse_afinfo_duration,
        ),
    )
    for command, parser in commands:
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=30
            )
        except FileNotFoundError:
            failures.append(f"{command[0]} not installed")
            continue
        except subprocess.TimeoutExpired:
            failures.append(f"{command[0]} timed out")
            continue
        except OSError as exc:
            failures.append(f"{command[0]} could not run: {exc}")
            continue
        if result.returncode != 0:
            failures.append(f"{command[0]} failed: {result.stderr.strip()}")
            continue
        try:
            duration = parser(result.stdout)
        except (AttributeError, TypeError, ValueError) as exc:
            failures.append(f"{command[0]} returned an unreadable duration: {exc}")
            continue
        if math.isfinite(duration) and duration > 0:
            return duration
        failures.append(f"{command[0]} returned invalid duration {duration!r}")
    raise RuntimeError("Could not probe audio duration: " + "; ".join(failures))


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _safe_slug(value: Any) -> str:
    raw = str(value or "").strip()
    normalized = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug[:80] or "r02-founder-fixture"


def _timeline() -> list[dict[str, Any]]:
    return [
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
    ]


def _validate_approval_flags(binding: dict[str, Any]) -> None:
    for field in (
        "public_start",
        "human_route_approved",
        "workout_approved",
        "human_approved",
    ):
        if not isinstance(binding.get(field), bool):
            raise ValueError(f"Binding field '{field}' must be boolean")


def complete_human_approval(binding: dict[str, Any]) -> bool:
    slots = binding.get("slots")
    metadata = binding.get("provisional_route_metadata")
    return (
        binding.get("public_start") is True
        and binding.get("human_route_approved") is True
        and binding.get("workout_approved") is True
        and binding.get("human_approved") is True
        and isinstance(slots, dict)
        and all(
            isinstance(slots.get(slot_id), dict)
            and slots[slot_id].get("human_approved") is True
            for slot_id in REQUIRED_BINDING_SLOTS
        )
        and _validate_field_review_metadata(metadata)
    )


def _validate_field_review_metadata(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False

    complete = all(
        metadata.get(field) is not None
        and metadata.get(field) != ""
        and metadata.get(field) != []
        for field in REQUIRED_FIELD_REVIEW_KEYS
    )

    loop_length = metadata.get("measured_loop_length_meters")
    if loop_length is not None and _number(loop_length, "measured_loop_length_meters") <= 0:
        raise ValueError("measured_loop_length_meters must be positive")
    elevation = metadata.get("measured_elevation_gain_meters")
    if elevation is not None and _number(elevation, "measured_elevation_gain_meters") < 0:
        raise ValueError("measured_elevation_gain_meters must be non-negative")

    legs = metadata.get("poi_leg_distances_meters")
    if legs is not None:
        if not isinstance(legs, list) or len(legs) != len(REQUIRED_ROUTE_ROLES):
            raise ValueError("poi_leg_distances_meters must contain exactly four legs")
        if any(_number(value, "poi_leg_distances_meters item") <= 0 for value in legs):
            raise ValueError("poi_leg_distances_meters items must be positive")

    arrivals = metadata.get("expected_poi_arrival_cue_sec")
    if arrivals is not None:
        expected_roles = set(REQUIRED_BINDING_SLOTS)
        if not isinstance(arrivals, dict) or set(arrivals) != expected_roles:
            raise ValueError(
                "expected_poi_arrival_cue_sec must contain threshold, witness, and triangulation"
            )
        values = [_number(arrivals[role], f"arrival {role}") for role in REQUIRED_BINDING_SLOTS]
        if any(value < 0 or value > EXPECTED_DURATION_SEC for value in values):
            raise ValueError("expected POI arrivals must be inside the mission duration")
        if values != sorted(values) or len(set(values)) != len(values):
            raise ValueError("expected POI arrivals must be strictly increasing")

    for field in ("route_surface_notes", "crossing_notes"):
        value = metadata.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{field} must be a non-empty string when recorded")

    completed_at = metadata.get("daylight_walkthrough_completed_at_local")
    if completed_at is not None:
        if not isinstance(completed_at, str) or not completed_at.strip():
            raise ValueError("daylight_walkthrough_completed_at_local must be a timestamp")
        try:
            parsed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("daylight walkthrough timestamp is not ISO-8601") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("daylight walkthrough timestamp must include a timezone")

    return complete


def _validate_binding_slots(
    binding: dict[str, Any], candidates: dict[str, Any], manifest: dict[str, Any]
) -> None:
    slots = binding.get("slots")
    if not isinstance(slots, dict):
        raise ValueError("Binding slots must be an object")
    missing = sorted(set(REQUIRED_BINDING_SLOTS) - set(slots))
    extra = sorted(set(slots) - set(REQUIRED_BINDING_SLOTS))
    if missing or extra:
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("unexpected=" + ",".join(extra))
        raise ValueError("Binding slot set mismatch: " + "; ".join(details))

    raw_text = "\n".join(
        str(cue.get("raw_text", ""))
        for cue in manifest.get("narrative_cues", [])
        if isinstance(cue, dict)
    )
    for role in REQUIRED_BINDING_SLOTS:
        slot = slots[role]
        if not isinstance(slot, dict):
            raise ValueError(f"Binding slot '{role}' must be an object")
        if not isinstance(slot.get("human_approved"), bool):
            raise ValueError(f"Binding slot '{role}' human_approved must be boolean")
        name = slot.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Binding slot '{role}' requires a non-empty name")
        refs = slot.get("source_refs")
        if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
            raise ValueError(f"Binding slot '{role}' source_refs must be a string array")
        expected_ref = candidates[role]["osm_url"]
        if expected_ref not in refs:
            raise ValueError(
                f"Binding slot '{role}' source_refs do not contain snapshot OSM URL {expected_ref}"
            )
        if name not in raw_text:
            raise ValueError(
                f"Audio manifest does not contain bound name {name!r} for slot '{role}'"
            )


def _validate_start_identity(binding: dict[str, Any], candidates: dict[str, Any]) -> None:
    metadata = binding.get("provisional_route_metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Binding provisional_route_metadata must be an object")
    start = candidates["start_and_finish"]
    if metadata.get("start_and_finish_name") != start["name"]:
        raise ValueError(
            "Binding start_and_finish_name does not match the snapshot start candidate"
        )
    if metadata.get("source_ref") != start["osm_url"]:
        raise ValueError(
            "Binding provisional route source_ref does not match the snapshot start OSM URL"
        )


def _validate_manifest_timing(
    manifest: dict[str, Any], actual_duration_sec: float
) -> None:
    cues = manifest.get("narrative_cues")
    if not isinstance(cues, list) or not cues:
        raise ValueError("Audio manifest narrative_cues must be a non-empty array")

    seen_ids: set[str] = set()
    previous_timestamp = -1.0
    previous_end = -1.0
    for index, cue in enumerate(cues):
        if not isinstance(cue, dict):
            raise ValueError(f"Audio manifest narrative_cues[{index}] must be an object")
        cue_id = cue.get("cue_id")
        node_id = cue.get("node_id")
        raw_text = cue.get("raw_text")
        if not isinstance(cue_id, str) or not cue_id.strip():
            raise ValueError(f"Audio manifest narrative_cues[{index}] requires cue_id")
        if cue_id in seen_ids:
            raise ValueError(f"Audio manifest contains duplicate cue_id {cue_id!r}")
        seen_ids.add(cue_id)
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError(f"Audio manifest cue {cue_id!r} requires node_id")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValueError(f"Audio manifest cue {cue_id!r} requires raw_text")

        timestamp = _number(
            cue.get("timestamp_sec"), f"Audio cue {cue_id!r} timestamp_sec"
        )
        duration = _number(
            cue.get("duration_sec"), f"Audio cue {cue_id!r} duration_sec"
        )
        if timestamp < 0 or duration <= 0:
            raise ValueError(f"Audio manifest cue {cue_id!r} has invalid timing")
        if timestamp <= previous_timestamp:
            raise ValueError("Audio manifest cue timestamps must be strictly increasing")
        if timestamp < previous_end - DURATION_TOLERANCE_SEC:
            raise ValueError(f"Audio manifest cue {cue_id!r} overlaps the previous cue")
        if timestamp + duration > actual_duration_sec + DURATION_TOLERANCE_SEC:
            raise ValueError(f"Audio manifest cue {cue_id!r} exceeds M4A duration")
        previous_timestamp = timestamp
        previous_end = timestamp + duration

    final_nav = _number(
        manifest.get("workout_final_nav_timestamp_sec"),
        "Audio manifest workout_final_nav_timestamp_sec",
    )
    if not FINAL_NAV_MIN_SEC <= final_nav <= FINAL_NAV_MAX_SEC:
        raise ValueError(
            "Audio manifest final NAV timestamp must be inside the 1790-1795s completion window"
        )
    if final_nav > actual_duration_sec:
        raise ValueError("Audio manifest final NAV timestamp is outside M4A duration")
    nav_count = manifest.get("workout_nav_events_count")
    if (
        isinstance(nav_count, bool)
        or not isinstance(nav_count, int)
        or nav_count != EXPECTED_NAV_EVENT_COUNT
    ):
        raise ValueError(
            f"Audio manifest workout_nav_events_count must equal {EXPECTED_NAV_EVENT_COUNT}"
        )


def _validate_candidate(role: str, candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise ValueError(f"Missing OSM candidate for required role '{role}'")
    latitude = _number(candidate.get("latitude"), f"Candidate '{role}' latitude")
    longitude = _number(candidate.get("longitude"), f"Candidate '{role}' longitude")
    if not -90 <= latitude <= 90:
        raise ValueError(f"Candidate '{role}' latitude is outside [-90, 90]")
    if not -180 <= longitude <= 180:
        raise ValueError(f"Candidate '{role}' longitude is outside [-180, 180]")

    name = candidate.get("name")
    osm_type = candidate.get("osm_type")
    osm_id = candidate.get("osm_id")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Candidate '{role}' requires a non-empty name")
    if osm_type not in {"node", "way", "relation"}:
        raise ValueError(f"Candidate '{role}' has invalid osm_type")
    if isinstance(osm_id, bool) or not isinstance(osm_id, int) or osm_id <= 0:
        raise ValueError(f"Candidate '{role}' has invalid osm_id")
    expected_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
    if candidate.get("osm_url") != expected_url:
        raise ValueError(
            f"Candidate '{role}' osm_url does not match its type/id ({expected_url})"
        )
    return {
        **candidate,
        "name": name.strip(),
        "latitude": latitude,
        "longitude": longitude,
        "osm_url": expected_url,
    }


def validate_fixture(fixture_dir: Path) -> dict[str, Any]:
    binding_path = fixture_dir / "current.binding.json"
    snapshot_path = fixture_dir / "osm_snapshot.json"
    audio_dir = fixture_dir / "audio"
    manifest_path = audio_dir / EXPECTED_MANIFEST_FILE

    required = [binding_path, snapshot_path, manifest_path]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing founder fixture files: " + ", ".join(missing))

    binding = load_json(binding_path)
    snapshot = load_json(snapshot_path)
    manifest = load_json(manifest_path)
    for label, document in (
        ("Binding", binding),
        ("Snapshot", snapshot),
        ("Audio manifest", manifest),
    ):
        if document.get("schema_version") != EXPECTED_SCHEMA_VERSION:
            raise ValueError(
                f"{label} schema_version must be {EXPECTED_SCHEMA_VERSION!r}"
            )
    if binding.get("research_mode") != "traveler_fixture":
        raise ValueError("Binding research_mode must be traveler_fixture")
    if binding.get("product_model") != "home_territory":
        raise ValueError("Binding product_model must be home_territory")
    _validate_approval_flags(binding)

    binding_id = binding.get("binding_id")
    if not isinstance(binding_id, str) or not binding_id.strip():
        raise ValueError("Binding requires a non-empty binding_id")
    if binding_id != binding_id.strip():
        raise ValueError("Binding binding_id must not contain surrounding whitespace")
    if manifest.get("concept_id") != EXPECTED_CONCEPT_ID:
        raise ValueError(
            f"Audio manifest concept_id must be {EXPECTED_CONCEPT_ID!r}, "
            f"got {manifest.get('concept_id')!r}"
        )
    if manifest.get("branch") != EXPECTED_BRANCH:
        raise ValueError(
            f"Audio manifest branch must be {EXPECTED_BRANCH!r}, "
            f"got {manifest.get('branch')!r}"
        )
    if manifest.get("mission_id") != EXPECTED_MISSION_ID:
        raise ValueError(
            f"Audio manifest mission_id must be {EXPECTED_MISSION_ID!r}, got {manifest.get('mission_id')!r}"
        )
    manifest_binding_id = manifest.get("binding_id")
    if manifest_binding_id is not None and manifest_binding_id != binding_id:
        raise ValueError("Audio manifest binding_id does not match current binding")

    m4a_name = manifest.get("m4a_file")
    if m4a_name != EXPECTED_M4A_FILE:
        raise ValueError(
            f"Audio manifest m4a_file must be {EXPECTED_M4A_FILE!r}; renamed assets are not supported"
        )
    m4a_path = audio_dir / m4a_name
    if not m4a_path.is_file():
        raise FileNotFoundError(f"Missing master audio: {m4a_path}")
    expected_audio_sha = manifest.get("m4a_sha256")
    if not isinstance(expected_audio_sha, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_audio_sha
    ):
        raise ValueError("Audio manifest m4a_sha256 must be a lowercase SHA-256")
    actual_audio_sha = compute_sha256(m4a_path)
    if actual_audio_sha != expected_audio_sha:
        raise ValueError(
            f"M4A SHA-256 mismatch: computed {actual_audio_sha}, manifest {expected_audio_sha}"
        )

    target_duration = _number(
        manifest.get("target_duration_sec"), "Audio manifest target_duration_sec"
    )
    actual_manifest_duration = _number(
        manifest.get("actual_duration_m4a_sec"),
        "Audio manifest actual_duration_m4a_sec",
    )
    probed_duration = probe_audio_duration(m4a_path)
    if target_duration <= 0 or actual_manifest_duration <= 0:
        raise ValueError("Audio durations must be positive")
    if abs(target_duration - EXPECTED_DURATION_SEC) > DURATION_TOLERANCE_SEC:
        raise ValueError(
            f"Audio target duration must match the M1 timeline ({EXPECTED_DURATION_SEC}s), "
            f"got {target_duration}s"
        )
    if abs(actual_manifest_duration - target_duration) > DURATION_TOLERANCE_SEC:
        raise ValueError(
            "Audio manifest actual/target duration mismatch: "
            f"actual={actual_manifest_duration}, target={target_duration}"
        )
    if abs(probed_duration - actual_manifest_duration) > DURATION_TOLERANCE_SEC:
        raise ValueError(
            "M4A probed/manifest duration mismatch: "
            f"probed={probed_duration}, manifest={actual_manifest_duration}"
        )
    if abs(probed_duration - target_duration) > DURATION_TOLERANCE_SEC:
        raise ValueError(
            "M4A probed/target duration mismatch: "
            f"probed={probed_duration}, target={target_duration}"
        )

    aiff_name = manifest.get("aiff_file")
    aiff_sha = manifest.get("aiff_sha256")
    if aiff_name is not None or aiff_sha is not None:
        if aiff_name != "m01_solo_founder_30min.aiff":
            raise ValueError("Audio manifest aiff_file must name the canonical R02 AIFF")
        if not isinstance(aiff_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", aiff_sha):
            raise ValueError("Audio manifest aiff_sha256 must be a lowercase SHA-256")
        aiff_path = audio_dir / aiff_name
        if not aiff_path.is_file():
            raise FileNotFoundError(f"Missing source AIFF: {aiff_path}")
        if compute_sha256(aiff_path) != aiff_sha:
            raise ValueError("AIFF SHA-256 mismatch against audio manifest")
        declared_aiff_duration = manifest.get("actual_duration_aiff_sec")
        if declared_aiff_duration is not None:
            actual_aiff_duration = probe_audio_duration(aiff_path)
            if abs(
                actual_aiff_duration
                - _number(declared_aiff_duration, "Audio manifest actual_duration_aiff_sec")
            ) > DURATION_TOLERANCE_SEC:
                raise ValueError("AIFF probed/manifest duration mismatch")
    _validate_manifest_timing(manifest, actual_manifest_duration)

    raw_candidates = snapshot.get("osm_candidates")
    if not isinstance(raw_candidates, dict):
        raise ValueError("Snapshot osm_candidates must be an object")
    candidates = {
        role: _validate_candidate(role, raw_candidates.get(role))
        for role in REQUIRED_ROUTE_ROLES
    }
    _validate_binding_slots(binding, candidates, manifest)
    _validate_start_identity(binding, candidates)
    _validate_field_review_metadata(binding.get("provisional_route_metadata"))

    metadata = snapshot.get("fixture_metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("Snapshot fixture_metadata must be an object when present")
    display_name = (
        metadata.get("display_name")
        or snapshot.get("city")
        or binding.get("city_alias")
        or fixture_dir.name
    )
    if not isinstance(display_name, str) or not display_name.strip():
        raise ValueError("Fixture requires a safe display name")
    gpx_prefix = _safe_slug(
        metadata.get("gpx_prefix")
        or binding.get("route_id")
        or binding_id
        or fixture_dir.name
    )

    route_points = []
    for index, (role, role_label) in enumerate(ROLES):
        candidate = candidates[role]
        localized_name = (
            binding["slots"][role]["name"]
            if role in REQUIRED_BINDING_SLOTS
            else candidate["name"]
        )
        route_points.append(
            {
                "id": f"{role}-{index}",
                "role": role,
                "roleLabel": role_label,
                "name": localized_name,
                "latitude": candidate["latitude"],
                "longitude": candidate["longitude"],
                "osmURL": candidate["osm_url"],
            }
        )

    timeline = _timeline()
    route_sha = canonical_json_sha256(route_points)
    timeline_sha = canonical_json_sha256(timeline)
    initial_human_approval = complete_human_approval(binding)
    mission = {
        "schemaVersion": EXPECTED_SCHEMA_VERSION,
        "missionID": EXPECTED_MISSION_ID,
        "title": "Линия, которой нет",
        "subtitle": "Нулевой слой · Миссия 1",
        "locationDisplayName": display_name.strip(),
        "bindingID": binding_id,
        "gpxPrefix": gpx_prefix,
        "audioFile": m4a_path.name,
        "audioSHA256": actual_audio_sha,
        "durationSeconds": target_duration,
        "routeInitiallyApproved": initial_human_approval,
        "workoutInitiallyApproved": initial_human_approval,
        "m1HumanApprovalComplete": initial_human_approval,
        "routeSHA256": route_sha,
        "timelineSHA256": timeline_sha,
        "bindingSHA256": compute_sha256(binding_path),
        "bindingContractSHA256": binding_contract_sha256(binding),
        "snapshotSHA256": compute_sha256(snapshot_path),
        "audioManifestSHA256": compute_sha256(manifest_path),
        "routePoints": route_points,
        "timeline": timeline,
        "evidenceNotice": "Маршрут и нагрузка становятся доступными для боевого запуска только после дневного обхода и домашней аудиопроверки.",
    }
    return {
        "binding": binding,
        "snapshot": snapshot,
        "manifest": manifest,
        "mission": mission,
        "m4a_path": m4a_path,
        "manifest_path": manifest_path,
        "probed_duration_sec": probed_duration,
    }


def _publish_validated_bundle(validated: dict[str, Any], output_dir: Path) -> None:
    m4a_path: Path = validated["m4a_path"]
    manifest_path: Path = validated["manifest_path"]
    expected_names = {"mission.json", m4a_path.name, manifest_path.name}

    if output_dir.is_symlink():
        raise ValueError(f"iOS output path must not be a symlink: {output_dir}")
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"iOS output path is not a directory: {output_dir}")
    if output_dir.is_dir():
        existing_names = {path.name for path in output_dir.iterdir()}
        stale = sorted(existing_names - expected_names)
        if stale:
            raise ValueError(
                "Refusing to publish over stale iOS resources: " + ", ".join(stale)
            )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".r02-ios-stage-", dir=output_dir.parent
    ) as temp_dir:
        stage = Path(temp_dir)
        staged_mission = stage / "mission.json"
        staged_mission.write_text(
            json.dumps(validated["mission"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        staged_audio = stage / m4a_path.name
        staged_manifest = stage / manifest_path.name
        shutil.copy2(m4a_path, staged_audio)
        shutil.copy2(manifest_path, staged_manifest)

        expected_audio_sha = validated["manifest"]["m4a_sha256"]
        if compute_sha256(staged_audio) != expected_audio_sha:
            raise RuntimeError("Staged iOS M4A failed post-copy SHA-256 verification")
        expected_manifest_sha = validated["mission"]["audioManifestSHA256"]
        if compute_sha256(staged_manifest) != expected_manifest_sha:
            raise RuntimeError("Staged iOS manifest failed post-copy SHA-256 verification")
        if load_json(staged_mission) != validated["mission"]:
            raise RuntimeError("Staged iOS mission changed during serialization")

        backup_dir: Path | None = None
        if output_dir.exists():
            backup_dir = Path(
                tempfile.mkdtemp(prefix=f".{output_dir.name}-previous-", dir=output_dir.parent)
            )
            backup_dir.rmdir()
            os.replace(output_dir, backup_dir)
        try:
            os.replace(stage, output_dir)
        except Exception:
            if backup_dir is not None and backup_dir.exists() and not output_dir.exists():
                os.replace(backup_dir, output_dir)
            raise
        if backup_dir is not None:
            shutil.rmtree(backup_dir)

    if {path.name for path in output_dir.iterdir()} != expected_names:
        raise RuntimeError("Published iOS resource inventory is not exact")
    if compute_sha256(output_dir / m4a_path.name) != validated["manifest"]["m4a_sha256"]:
        raise RuntimeError("Published iOS M4A failed post-copy SHA-256 verification")
    if (
        compute_sha256(output_dir / manifest_path.name)
        != validated["mission"]["audioManifestSHA256"]
    ):
        raise RuntimeError("Published iOS manifest failed post-copy SHA-256 verification")
    if load_json(output_dir / "mission.json") != validated["mission"]:
        raise RuntimeError("Published iOS mission does not match validated mission")


def prepare(fixture_dir: Path, output_dir: Path) -> dict[str, Any]:
    validated = validate_fixture(fixture_dir)
    _publish_validated_bundle(validated, output_dir)
    return validated["mission"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        mission = prepare(args.fixture_dir, args.output_dir)
        print(
            f"iOS founder resources prepared: {mission['title']} / "
            f"{len(mission['routePoints'])} route points / {mission['routeSHA256']}"
        )
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
