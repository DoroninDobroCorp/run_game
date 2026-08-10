#!/usr/bin/env python3
"""Create a privacy-minimized R02 timing report from a local GPX track.

The analyzer is deliberately offline and uses only the Python standard library.
It reports derived distances and relative times; raw coordinates, absolute track
timestamps, place names, and input paths are never included in the JSON report.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Sequence
import xml.etree.ElementTree as ET

try:
    from tools.domain_thresholds import (
        MAX_EVIDENCE_ACCURACY_M,
        MAX_SAMPLE_GAP_SEC,
        MAX_START_FINISH_CLOSURE_M,
        MIN_EVIDENCE_DISTANCE_M,
        MIN_WALKTHROUGH_DURATION_SEC,
        MIN_EVIDENCE_SAMPLES,
        MIN_SAMPLES_PER_ROUTE_POINT,
        ROUTE_POINT_RADIUS_M,
    )
except ImportError:
    from domain_thresholds import (
        MAX_EVIDENCE_ACCURACY_M,
        MAX_SAMPLE_GAP_SEC,
        MAX_START_FINISH_CLOSURE_M,
        MIN_EVIDENCE_DISTANCE_M,
        MIN_WALKTHROUGH_DURATION_SEC,
        MIN_EVIDENCE_SAMPLES,
        MIN_SAMPLES_PER_ROUTE_POINT,
        ROUTE_POINT_RADIUS_M,
    )


EARTH_RADIUS_METERS = 6_371_008.8
MAX_EVIDENCE_SAMPLE_GAP_SEC = MAX_SAMPLE_GAP_SEC
MAX_EVIDENCE_SPEED_MPS = 15.0
MIN_ACCEPTED_POINTS = MIN_EVIDENCE_SAMPLES
MIN_EVIDENCE_DURATION_SEC = MIN_WALKTHROUGH_DURATION_SEC
MIN_EVIDENCE_DISTANCE_M = MIN_EVIDENCE_DISTANCE_M
MAX_START_FINISH_CLOSURE_M = MAX_START_FINISH_CLOSURE_M
MAX_ROUTE_POINT_RADIUS_M = ROUTE_POINT_RADIUS_M
MAX_HORIZONTAL_ACCURACY_M = MAX_EVIDENCE_ACCURACY_M
MIN_SAMPLES_PER_ROUTE_POINT = MIN_SAMPLES_PER_ROUTE_POINT
REQUIRED_CUE_ROLES = ("threshold", "witness", "triangulation")
ALLOWED_ROUTE_ROLES = ("start_and_finish", *REQUIRED_CUE_ROLES)
SNAPSHOT_ROUTE_ORDER = (
    "start_and_finish",
    "threshold",
    "witness",
    "triangulation",
)


class AnalysisError(ValueError):
    """Raised when an input is incomplete, malformed, or internally inconsistent."""


def _reject_json_constant(value: str) -> None:
    raise AnalysisError(f"non-finite JSON number {value!r} is not allowed")


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AnalysisError(f"duplicate JSON key {key!r} is not allowed")
        result[key] = value
    return result


@dataclass(frozen=True)
class TrackPoint:
    latitude: float
    longitude: float
    elevation_m: float
    timestamp: datetime
    horizontal_accuracy_m: float
    segment_index: int


@dataclass(frozen=True)
class RoutePoint:
    role: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Cue:
    role: str
    timestamp_sec: float


@dataclass(frozen=True)
class ParsedTrack:
    accepted: tuple[TrackPoint, ...]
    rejected_count: int
    segment_count: int


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnalysisError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise AnalysisError(f"{label} must be finite")
    return result


def _declared_sha256(
    document: dict[str, Any], key: str, label: str
) -> str | None:
    value = document.get(key)
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise AnalysisError(f"{label} {key} must be a lowercase SHA-256 hex digest")
    return value


def _required_sha256(document: dict[str, Any], key: str, label: str) -> str:
    value = _declared_sha256(document, key, label)
    if value is None:
        raise AnalysisError(f"{label} must declare {key}")
    return value


def _canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _identifier_sha256(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AnalysisError(f"{label} must be a non-empty string when present")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _coordinate(latitude: Any, longitude: Any, label: str) -> tuple[float, float]:
    lat = _finite_number(latitude, f"{label} latitude")
    lon = _finite_number(longitude, f"{label} longitude")
    if not -90.0 <= lat <= 90.0:
        raise AnalysisError(f"{label} latitude is out of range")
    if not -180.0 <= lon <= 180.0:
        raise AnalysisError(f"{label} longitude is out of range")
    return lat, lon


def _parse_timestamp(value: str) -> datetime:
    if not value:
        raise AnalysisError("every GPX track point must contain a timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise AnalysisError("GPX contains an invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AnalysisError("GPX timestamps must include a timezone")
    return parsed


def _child_text_by_local_name(element: ET.Element, name: str) -> str | None:
    for child in element.iter():
        if _local_name(child.tag) == name and child.text is not None:
            return child.text.strip()
    return None


def _read_input_bytes(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise AnalysisError(f"{label} input could not be read") from exc


def _parse_gpx_bytes(
    source: bytes, max_horizontal_accuracy_m: float
) -> ParsedTrack:
    """Parse and validate one GPX byte stream, rejecting low-accuracy samples."""

    if (
        not math.isfinite(max_horizontal_accuracy_m)
        or max_horizontal_accuracy_m <= 0
        or max_horizontal_accuracy_m > MAX_HORIZONTAL_ACCURACY_M
    ):
        raise AnalysisError(
            "maximum horizontal accuracy must be inside the positive 0-50m evidence bound"
        )
    try:
        root = ET.fromstring(source)
    except ET.ParseError as exc:
        raise AnalysisError("GPX input could not be read as valid XML") from exc
    if _local_name(root.tag) != "gpx":
        raise AnalysisError("input XML root must be gpx")

    tracks = [element for element in root.iter() if _local_name(element.tag) == "trk"]
    if len(tracks) != 1:
        raise AnalysisError("GPX must contain exactly one track")
    segments = [
        element for element in tracks[0] if _local_name(element.tag) == "trkseg"
    ]
    if len(segments) != 1:
        raise AnalysisError("GPX evidence must contain exactly one continuous track segment")

    accepted: list[TrackPoint] = []
    rejected_count = 0
    previous_timestamp: datetime | None = None
    total_points = 0
    for segment_index, segment in enumerate(segments):
        points = [element for element in segment if _local_name(element.tag) == "trkpt"]
        if not points:
            raise AnalysisError("GPX track segments must not be empty")
        for element in points:
            total_points += 1
            try:
                raw_latitude = float(element.attrib["lat"])
                raw_longitude = float(element.attrib["lon"])
            except (KeyError, TypeError, ValueError) as exc:
                raise AnalysisError("GPX contains a track point without numeric coordinates") from exc
            latitude, longitude = _coordinate(
                raw_latitude, raw_longitude, "GPX track point"
            )
            timestamp = _parse_timestamp(_child_text_by_local_name(element, "time") or "")
            if previous_timestamp is not None and timestamp <= previous_timestamp:
                raise AnalysisError("GPX track points must be strictly chronological")
            previous_timestamp = timestamp

            raw_accuracy = _child_text_by_local_name(element, "horizontalAccuracy")
            if raw_accuracy is None:
                raise AnalysisError(
                    "every GPX track point must contain horizontalAccuracy"
                )
            try:
                accuracy = float(raw_accuracy)
            except ValueError as exc:
                raise AnalysisError("GPX contains a non-numeric horizontalAccuracy") from exc
            if not math.isfinite(accuracy) or accuracy < 0:
                raise AnalysisError(
                    "GPX horizontalAccuracy must be a finite non-negative value"
                )
            raw_elevation = _child_text_by_local_name(element, "ele")
            if raw_elevation is None:
                raise AnalysisError("every GPX track point must contain elevation")
            try:
                elevation = float(raw_elevation)
            except ValueError as exc:
                raise AnalysisError("GPX contains a non-numeric elevation") from exc
            if not math.isfinite(elevation):
                raise AnalysisError("GPX elevation must be finite")
            if accuracy > max_horizontal_accuracy_m:
                rejected_count += 1
                continue
            accepted.append(
                TrackPoint(
                    latitude=latitude,
                    longitude=longitude,
                    elevation_m=elevation,
                    timestamp=timestamp,
                    horizontal_accuracy_m=accuracy,
                    segment_index=segment_index,
                )
            )

    if total_points == 0:
        raise AnalysisError("GPX track contains no points")
    if len(accepted) < 2:
        raise AnalysisError("GPX must contain at least two accepted track points")
    return ParsedTrack(
        accepted=tuple(accepted),
        rejected_count=rejected_count,
        segment_count=len(segments),
    )


def parse_gpx(gpx_path: Path, max_horizontal_accuracy_m: float) -> ParsedTrack:
    return _parse_gpx_bytes(
        _read_input_bytes(gpx_path, "GPX"), max_horizontal_accuracy_m
    )


def _json_from_bytes(source: bytes, label: str) -> dict[str, Any]:
    try:
        text = source.decode("utf-8")
        value = json.loads(
            text,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_json_object_without_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"{label} input could not be read as valid JSON") from exc
    if not isinstance(value, dict):
        raise AnalysisError(f"{label} input must be a JSON object")
    return value


def _read_json(path: Path, label: str) -> dict[str, Any]:
    return _json_from_bytes(_read_input_bytes(path, label), label)


def load_mission_route(mission_path: Path) -> tuple[list[RoutePoint], str | None]:
    mission = _read_json(mission_path, "mission")
    return _mission_route(mission)


def _mission_route(mission: dict[str, Any]) -> tuple[list[RoutePoint], str | None]:
    raw_points = mission.get("routePoints")
    if not isinstance(raw_points, list) or not raw_points:
        raise AnalysisError("mission must contain a non-empty routePoints array")
    route_points: list[RoutePoint] = []
    for index, raw_point in enumerate(raw_points):
        if not isinstance(raw_point, dict):
            raise AnalysisError("every mission route point must be an object")
        role = raw_point.get("role")
        if not isinstance(role, str) or not role.strip():
            raise AnalysisError("every mission route point must contain a role")
        role = role.strip()
        if role not in ALLOWED_ROUTE_ROLES:
            raise AnalysisError("mission contains an unsupported route role")
        latitude, longitude = _coordinate(
            raw_point.get("latitude"),
            raw_point.get("longitude"),
            f"mission route point {index}",
        )
        route_points.append(RoutePoint(role, latitude, longitude))
    expected_roles = (*SNAPSHOT_ROUTE_ORDER, "start_and_finish")
    if tuple(point.role for point in route_points) != expected_roles:
        raise AnalysisError(
            "mission route roles must be ordered start, threshold, witness, "
            "triangulation, finish"
        )
    mission_id = mission.get("missionID")
    if not isinstance(mission_id, str) or not mission_id.strip():
        raise AnalysisError("prepared mission must contain a non-empty missionID")
    return route_points, mission_id


def _snapshot_route(snapshot: dict[str, Any]) -> list[RoutePoint]:
    candidates = snapshot.get("osm_candidates")
    if not isinstance(candidates, dict):
        raise AnalysisError("snapshot must contain an osm_candidates object")
    route_points: list[RoutePoint] = []
    for role in SNAPSHOT_ROUTE_ORDER:
        candidate = candidates.get(role)
        if not isinstance(candidate, dict):
            raise AnalysisError(f"snapshot is missing required route role {role}")
        latitude, longitude = _coordinate(
            candidate.get("latitude"),
            candidate.get("longitude"),
            f"snapshot route role {role}",
        )
        route_points.append(RoutePoint(role, latitude, longitude))
    return route_points


def load_snapshot_route(snapshot_path: Path) -> list[RoutePoint]:
    return _snapshot_route(_read_json(snapshot_path, "snapshot"))


def load_manifest_cues(
    manifest_path: Path, expected_mission_id: str | None = None
) -> list[Cue]:
    manifest = _read_json(manifest_path, "manifest")
    return _manifest_cues(manifest, expected_mission_id)


def _manifest_cues(
    manifest: dict[str, Any], expected_mission_id: str | None = None
) -> list[Cue]:
    manifest_mission_id = manifest.get("mission_id")
    if manifest_mission_id is not None and (
        not isinstance(manifest_mission_id, str) or not manifest_mission_id.strip()
    ):
        raise AnalysisError("manifest mission_id must be a non-empty string")
    if expected_mission_id and manifest_mission_id != expected_mission_id:
        raise AnalysisError("mission and manifest mission identifiers do not match")
    raw_cues = manifest.get("narrative_cues")
    if not isinstance(raw_cues, list):
        raise AnalysisError("manifest must contain a narrative_cues array")
    duration = manifest.get("target_duration_sec")
    duration_sec = (
        _finite_number(duration, "manifest target_duration_sec")
        if duration is not None
        else None
    )
    if duration_sec is not None and duration_sec <= 0:
        raise AnalysisError("manifest target duration must be positive")

    cues: list[Cue] = []
    for role in REQUIRED_CUE_ROLES:
        matches = []
        for raw_cue in raw_cues:
            if not isinstance(raw_cue, dict):
                raise AnalysisError("every manifest narrative cue must be an object")
            node_id = raw_cue.get("node_id")
            if isinstance(node_id, str) and (
                node_id == role or node_id.endswith(f"_{role}")
            ):
                matches.append(raw_cue)
        if len(matches) != 1:
            raise AnalysisError(f"manifest must contain exactly one cue for role {role}")
        timestamp = _finite_number(
            matches[0].get("timestamp_sec"), f"manifest cue {role} timestamp_sec"
        )
        if timestamp < 0 or (duration_sec is not None and timestamp > duration_sec):
            raise AnalysisError(f"manifest cue {role} timestamp is outside the mission")
        cues.append(Cue(role=role, timestamp_sec=timestamp))
    return cues


def haversine_distance_m(
    latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float
) -> float:
    lat_a = math.radians(latitude_a)
    lat_b = math.radians(latitude_b)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(longitude_b - longitude_a)
    term = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_METERS * math.asin(min(1.0, math.sqrt(term)))


def _rounded(value: float) -> float:
    return round(value, 3)


def _route_analysis(
    track: Sequence[TrackPoint],
    route_points: Sequence[RoutePoint],
    arrival_radius_m: float,
) -> tuple[
    list[dict[str, Any]],
    dict[str, float | None],
    list[int | None],
]:
    route_report: list[dict[str, Any]] = []
    role_arrivals: dict[str, float | None] = {}
    arrival_indices: list[int | None] = []
    first_timestamp = track[0].timestamp
    ordered_search_start = 0
    for index, route_point in enumerate(route_points):
        distances = [
            haversine_distance_m(
                point.latitude,
                point.longitude,
                route_point.latitude,
                route_point.longitude,
            )
            for point in track
        ]
        closest = min(distances)
        nearby_indices: list[int] = []
        arrival_index = None
        reached_third_index = None
        for point_index in range(ordered_search_start, len(track)):
            if distances[point_index] <= arrival_radius_m:
                nearby_indices.append(point_index)
                if len(nearby_indices) >= MIN_SAMPLES_PER_ROUTE_POINT:
                    arrival_index = nearby_indices[0]
                    reached_third_index = point_index
                    break
        arrival_elapsed = None
        if arrival_index is not None and reached_third_index is not None:
            ordered_search_start = reached_third_index + 1
            arrival_elapsed = (
                track[arrival_index].timestamp - first_timestamp
            ).total_seconds()
        arrival_indices.append(arrival_index)
        route_report.append(
            {
                "route_point_index": index,
                "role": route_point.role,
                "closest_approach_m": _rounded(closest),
                "first_arrival_elapsed_sec": (
                    _rounded(arrival_elapsed) if arrival_elapsed is not None else None
                ),
            }
        )
        if route_point.role in REQUIRED_CUE_ROLES:
            if route_point.role in role_arrivals:
                raise AnalysisError(
                    f"route contains more than one point for cue role {route_point.role}"
                )
            role_arrivals[route_point.role] = arrival_elapsed

    missing_roles = [role for role in REQUIRED_CUE_ROLES if role not in role_arrivals]
    if missing_roles:
        raise AnalysisError(
            "route is missing required cue roles: " + ", ".join(missing_roles)
        )
    return route_report, role_arrivals, arrival_indices


def _distance_along_track(
    track: Sequence[TrackPoint], start_index: int, end_index: int
) -> float:
    if end_index <= start_index:
        raise AnalysisError("ordered route arrivals must use distinct track points")
    distance_m = 0.0
    for previous, current in zip(track[start_index:end_index], track[start_index + 1 : end_index + 1]):
        if previous.segment_index == current.segment_index:
            distance_m += haversine_distance_m(
                previous.latitude,
                previous.longitude,
                current.latitude,
                current.longitude,
            )
    if distance_m <= 0:
        raise AnalysisError("every derived route leg must have positive distance")
    return distance_m


def build_report(
    track: ParsedTrack,
    route_points: Sequence[RoutePoint],
    cues: Sequence[Cue],
    max_horizontal_accuracy_m: float,
    arrival_radius_m: float,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    if (
        not math.isfinite(arrival_radius_m)
        or arrival_radius_m <= 0
        or arrival_radius_m > MAX_ROUTE_POINT_RADIUS_M
    ):
        raise AnalysisError("arrival radius must be inside the positive 0-100m evidence bound")
    accepted = track.accepted
    if len(accepted) < MIN_ACCEPTED_POINTS:
        raise AnalysisError(
            f"GPX requires at least {MIN_ACCEPTED_POINTS} accepted track points"
        )
    distance_m = 0.0
    for previous, current in zip(accepted, accepted[1:]):
        if previous.segment_index == current.segment_index:
            segment_distance = haversine_distance_m(
                previous.latitude,
                previous.longitude,
                current.latitude,
                current.longitude,
            )
            elapsed = (current.timestamp - previous.timestamp).total_seconds()
            if segment_distance / elapsed > MAX_EVIDENCE_SPEED_MPS:
                raise AnalysisError("accepted GPX contains an implausible movement speed")
            distance_m += segment_distance
    elevation_gain_m = sum(
        max(0.0, current.elevation_m - previous.elevation_m)
        for previous, current in zip(accepted, accepted[1:])
        if previous.segment_index == current.segment_index
    )
    duration_sec = (accepted[-1].timestamp - accepted[0].timestamp).total_seconds()
    if duration_sec < MIN_EVIDENCE_DURATION_SEC:
        raise AnalysisError(
            f"accepted GPX duration must be at least {MIN_EVIDENCE_DURATION_SEC:g}s"
        )
    maximum_sample_gap_sec = max(
        (current.timestamp - previous.timestamp).total_seconds()
        for previous, current in zip(accepted, accepted[1:])
    )
    if maximum_sample_gap_sec > MAX_EVIDENCE_SAMPLE_GAP_SEC:
        raise AnalysisError(
            "accepted GPX contains a sample gap larger than the evidence limit"
        )
    closure_m = haversine_distance_m(
        accepted[0].latitude,
        accepted[0].longitude,
        accepted[-1].latitude,
        accepted[-1].longitude,
    )
    if distance_m < MIN_EVIDENCE_DISTANCE_M:
        raise AnalysisError(
            f"accepted GPX distance must be at least {MIN_EVIDENCE_DISTANCE_M:g}m"
        )
    if closure_m > MAX_START_FINISH_CLOSURE_M:
        raise AnalysisError(
            f"start-finish closure must be at most {MAX_START_FINISH_CLOSURE_M:g}m"
        )
    normalized_route_points = list(route_points)
    if tuple(point.role for point in normalized_route_points) == SNAPSHOT_ROUTE_ORDER:
        normalized_route_points.append(normalized_route_points[0])
    expected_roles = (*SNAPSHOT_ROUTE_ORDER, "start_and_finish")
    if tuple(point.role for point in normalized_route_points) != expected_roles:
        raise AnalysisError(
            "route roles must be ordered start, threshold, witness, triangulation, finish"
        )
    public_start = normalized_route_points[0]
    for label, point in (("first", accepted[0]), ("last", accepted[-1])):
        distance_to_start = haversine_distance_m(
            point.latitude,
            point.longitude,
            public_start.latitude,
            public_start.longitude,
        )
        if distance_to_start > MAX_ROUTE_POINT_RADIUS_M:
            raise AnalysisError(
                f"{label} accepted GPX point must be within {MAX_ROUTE_POINT_RADIUS_M:g}m of public start"
            )
    route_report, role_arrivals, arrival_indices = _route_analysis(
        accepted, normalized_route_points, arrival_radius_m
    )
    if any(index is None for index in arrival_indices):
        raise AnalysisError(
            "accepted GPX points never enter the arrival radius for every ordered route point"
        )
    ordered_indices = [index for index in arrival_indices if index is not None]
    leg_distances_m = [
        _distance_along_track(accepted, start, end)
        for start, end in zip(ordered_indices, ordered_indices[1:])
    ]
    missing_arrivals = [
        role for role in REQUIRED_CUE_ROLES if role_arrivals[role] is None
    ]
    if missing_arrivals:
        raise AnalysisError(
            "accepted GPX points never enter the arrival radius for required cue roles: "
            + ", ".join(missing_arrivals)
        )
    cue_report = []
    binding_arrivals: dict[str, float] = {}
    for cue in cues:
        arrival = role_arrivals[cue.role]
        if arrival is None:
            raise AnalysisError(f"route has no accepted arrival for cue role {cue.role}")
        binding_arrivals[cue.role] = _rounded(arrival)
        cue_report.append(
            {
                "role": cue.role,
                "cue_timestamp_sec": _rounded(cue.timestamp_sec),
                "first_arrival_elapsed_sec": (
                    _rounded(arrival) if arrival is not None else None
                ),
                "cue_delta_sec": (
                    _rounded(arrival - cue.timestamp_sec)
                    if arrival is not None
                    else None
                ),
            }
        )

    return {
        "schema_version": "0.2",
        "report_type": "r02_gpx_cue_derived",
        "provenance": provenance,
        "parameters": {
            "max_horizontal_accuracy_m": _rounded(max_horizontal_accuracy_m),
            "arrival_radius_m": _rounded(arrival_radius_m),
            "minimum_samples_per_route_point": MIN_SAMPLES_PER_ROUTE_POINT,
        },
        "track_summary": {
            "accepted_points": len(accepted),
            "rejected_points": track.rejected_count,
            "segment_count": track.segment_count,
            "duration_sec": _rounded(duration_sec),
            "maximum_sample_gap_sec": _rounded(maximum_sample_gap_sec),
            "distance_m": _rounded(distance_m),
            "elevation_gain_m": _rounded(elevation_gain_m),
            "start_finish_closure_m": _rounded(closure_m),
        },
        "route_points": route_report,
        "route_leg_distances_m": [_rounded(value) for value in leg_distances_m],
        "cue_deltas": cue_report,
        "binding_field_values": {
            "measured_loop_length_meters": _rounded(distance_m),
            "measured_elevation_gain_meters": _rounded(elevation_gain_m),
            "poi_leg_distances_meters": [
                _rounded(value) for value in leg_distances_m
            ],
            "expected_poi_arrival_cue_sec": {
                role: binding_arrivals[role] for role in REQUIRED_CUE_ROLES
            },
        },
        "limitations": [
            "Derived geometry and relative timing only; this report makes no safety or approval determination.",
            "Raw coordinates, place names, absolute timestamps, and input paths are intentionally omitted.",
            "Elevation gain is an unsmoothed sum of positive device-altitude deltas and requires human review.",
        ],
    }


def analyze_files(
    *,
    gpx_path: Path,
    manifest_path: Path,
    mission_path: Path | None = None,
    snapshot_path: Path | None = None,
    max_horizontal_accuracy_m: float = 50.0,
    arrival_radius_m: float = 100.0,
) -> dict[str, Any]:
    if (mission_path is None) == (snapshot_path is None):
        raise AnalysisError("provide exactly one of mission_path or snapshot_path")
    gpx_bytes = _read_input_bytes(gpx_path, "GPX")
    manifest_bytes = _read_input_bytes(manifest_path, "manifest")
    route_source_path = mission_path if mission_path is not None else snapshot_path
    assert route_source_path is not None
    route_source_bytes = _read_input_bytes(route_source_path, "route source")

    track = _parse_gpx_bytes(gpx_bytes, max_horizontal_accuracy_m)
    manifest_document = _json_from_bytes(manifest_bytes, "manifest")
    route_source_document = _json_from_bytes(route_source_bytes, "route source")
    if mission_path is not None:
        route_points, mission_id = _mission_route(route_source_document)
    else:
        route_points = _snapshot_route(route_source_document)
        mission_id = None
    cues = _manifest_cues(manifest_document, expected_mission_id=mission_id)

    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    mission_audio_sha: str | None
    manifest_audio_sha: str | None
    binding_contract_sha: str | None
    route_sha: str | None
    if mission_path is not None:
        mission_manifest_sha = _required_sha256(
            route_source_document, "audioManifestSHA256", "prepared mission"
        )
        mission_audio_sha = _required_sha256(
            route_source_document, "audioSHA256", "prepared mission"
        )
        manifest_audio_sha = _required_sha256(
            manifest_document, "m4a_sha256", "manifest"
        )
        binding_contract_sha = _required_sha256(
            route_source_document, "bindingContractSHA256", "prepared mission"
        )
        route_sha = _required_sha256(
            route_source_document, "routeSHA256", "prepared mission"
        )
        raw_route_points = route_source_document.get("routePoints")
        if route_sha != _canonical_json_sha256(raw_route_points):
            raise AnalysisError("prepared mission route SHA does not match routePoints")
        if mission_manifest_sha != manifest_sha:
            raise AnalysisError("mission audio manifest SHA does not match analyzed manifest")
        if mission_audio_sha != manifest_audio_sha:
            raise AnalysisError("mission and manifest audio SHA values do not match")
    else:
        mission_audio_sha = None
        manifest_audio_sha = _declared_sha256(
            manifest_document, "m4a_sha256", "manifest"
        )
        binding_contract_sha = None
        route_sha = None
    route_binding_id = route_source_document.get("bindingID")
    if mission_path is not None and (
        not isinstance(route_binding_id, str) or not route_binding_id.strip()
    ):
        raise AnalysisError("prepared mission must contain a non-empty bindingID")
    manifest_binding_id = manifest_document.get("binding_id")
    if manifest_binding_id is not None:
        if not isinstance(manifest_binding_id, str) or not manifest_binding_id.strip():
            raise AnalysisError("manifest binding_id must be a non-empty string")
        if route_binding_id != manifest_binding_id:
            raise AnalysisError("mission and manifest binding identifiers do not match")
    effective_audio_sha = mission_audio_sha or manifest_audio_sha
    provenance = {
        "gpx_sha256": hashlib.sha256(gpx_bytes).hexdigest(),
        "route_source_sha256": hashlib.sha256(route_source_bytes).hexdigest(),
        "manifest_sha256": manifest_sha,
        "route_source_kind": "prepared_mission" if mission_path is not None else "snapshot",
        "mission_id_sha256": _identifier_sha256(
            mission_id or manifest_document.get("mission_id"), "mission identifier"
        ),
        "binding_id_sha256": _identifier_sha256(
            route_binding_id or manifest_binding_id, "binding identifier"
        ),
        "binding_contract_sha256": binding_contract_sha,
        "route_sha256": route_sha,
        "audio_sha256": effective_audio_sha,
    }
    return build_report(
        track,
        route_points,
        cues,
        max_horizontal_accuracy_m=max_horizontal_accuracy_m,
        arrival_radius_m=arrival_radius_m,
        provenance=provenance,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpx", type=Path, required=True, help="Local GPX track")
    route_source = parser.add_mutually_exclusive_group(required=True)
    route_source.add_argument("--mission", type=Path, help="Prepared mission.json")
    route_source.add_argument("--snapshot", type=Path, help="Local OSM snapshot JSON")
    parser.add_argument("--manifest", type=Path, required=True, help="Master manifest JSON")
    parser.add_argument(
        "--max-horizontal-accuracy-m",
        type=float,
        default=50.0,
        help="Reject samples whose recorded horizontal accuracy exceeds this value",
    )
    parser.add_argument(
        "--arrival-radius-m",
        type=float,
        default=100.0,
        help="Radius used to derive first arrival at each route point",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = analyze_files(
            gpx_path=args.gpx,
            manifest_path=args.manifest,
            mission_path=args.mission,
            snapshot_path=args.snapshot,
            max_horizontal_accuracy_m=args.max_horizontal_accuracy_m,
            arrival_radius_m=args.arrival_radius_m,
        )
    except AnalysisError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
