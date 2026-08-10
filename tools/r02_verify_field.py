#!/usr/bin/env python3
"""Verify legacy or provenance-strict R02 field master audio manifests.

The unchanged default verifies the legacy Condition A manifest under
``--audio-dir``. Pass ``--manifest`` to verify a specific new manifest, or
``--compare-manifest`` to strictly verify an A/B pair and their experimental
parity. This tool never grants route, workout, safety, or participant approval.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIO_DIR = ROOT / "research/r02/local/valparaiso_central/audio"

MANIFEST_SCHEMA_VERSION = "0.1"
STRICT_TOOL_SCHEMA = "r02_build_master_manifest/0.2"
MISSION_ID = "m01"
CONCEPT_ID = "null_layer"
BRANCH = "atlas_disclosure=concealed"
MASTER_STEM = "m01_solo_founder_30min"
CONDITION_B_SUFFIX = "_condition_b"
DEFAULT_MANIFEST_NAME = f"{MASTER_STEM}.manifest.json"

EXPECTED_DURATION_SEC = 1800.0
DURATION_TOLERANCE_SEC = 0.5
FINAL_NAV_MIN_SEC = 1790.0
FINAL_NAV_MAX_SEC = 1795.0
FLOAT_EPSILON = 1e-6
PROBE_TIMEOUT_SEC = 30
CUE_DURATION_PARITY_TOLERANCE_SEC = 10.0
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
STRICT_TOP_LEVEL_MARKERS = frozenset(
    {
        "condition",
        "story_text_field",
        "binding_id",
        "binding_sha256",
        "beats_sha256",
        "sample_rate_hz",
        "workout_nav_events",
        "workout_nav_events_sha256",
        "narrative_schedule_sha256",
    }
)
STRICT_CUE_MARKERS = frozenset({"text_sha256", "max_spoken_sec"})

CANONICAL_CUE_SEQUENCE = (
    ("m01_c001", "m01_start"),
    ("m01_c002", "m01_contact"),
    ("m01_c003", "m01_threshold"),
    ("m01_c004", "m01_witness"),
    ("m01_c005", "m01_choice_disclosure"),
    ("m01_c006a", "m01_response_concealed"),
    ("m01_c007", "m01_triangulation"),
    ("m01_c008", "m01_loop_close"),
    ("m01_c009", "m01_clue_fragments"),
    ("m01_c010", "m01_end"),
)


class VerificationError(ValueError):
    """An artifact is missing, unsafe, malformed, or inconsistent."""


@dataclass(frozen=True)
class VerifiedManifest:
    path: Path
    manifest: dict[str, Any]
    strict: bool
    aiff_path: Path
    m4a_path: Path
    aiff_duration_sec: float
    m4a_duration_sec: float
    aiff_sha256: str
    m4a_sha256: str


def _reject_json_constant(value: str) -> None:
    raise VerificationError(f"non-finite JSON number {value!r} is not allowed")


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError(f"duplicate JSON key {key!r} is not allowed")
        result[key] = value
    return result


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise VerificationError(f"field verification manifest not found ({path})")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
            object_pairs_hook=_json_object_without_duplicates,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"could not read manifest {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError("manifest JSON root must be an object")
    return value


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        while chunk := file_handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_dialogue_segments(text: str) -> list[tuple[str, str]]:
    """Mirror the builder's deterministic authored-text to TTS-segment contract."""
    clean_raw = re.sub(r"\[[^\]]+\]", "", text).strip()
    pattern = r"(NAV|АТЛАС|ЛЕА)(?:,\s*[^:]+)?:?"
    tokens = re.split(pattern, clean_raw)

    segments: list[tuple[str, str]] = []
    if len(tokens) == 1:
        text_clean = tokens[0].strip()
        if text_clean:
            segments.append(("LEA", text_clean))
        return segments

    if tokens[0].strip():
        raise VerificationError(
            "dialogue contains unlabeled text before the first speaker"
        )

    index = 1
    while index < len(tokens):
        speaker_raw = tokens[index].strip()
        speech = tokens[index + 1].strip() if index + 1 < len(tokens) else ""
        speech = re.sub(r"^\s*:\s*", "", speech).strip()
        if speech:
            role = (
                "NAV"
                if speaker_raw == "NAV"
                else "ATLAS" if speaker_raw == "АТЛАС" else "LEA"
            )
            segments.append((role, speech))
        index += 2
    return segments


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _duration_from_afinfo_output(stdout: str, name: str) -> float:
    match = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", stdout)
    if not match:
        raise VerificationError(f"could not parse duration from afinfo for {name}")
    return _finite_number(float(match.group(1)), f"afinfo duration for {name}")


def get_audio_duration_afinfo(path: Path) -> float:
    try:
        result = subprocess.run(
            ["afinfo", str(path)],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SEC,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VerificationError(f"afinfo unavailable for {path.name}: {exc}") from exc
    if result.returncode != 0:
        raise VerificationError(f"afinfo failed on {path.name}: {result.stderr.strip()}")
    duration = _duration_from_afinfo_output(result.stdout, path.name)
    if duration <= 0:
        raise VerificationError(f"afinfo duration for {path.name} must be positive")
    return duration


def get_audio_duration_ffprobe(path: Path) -> float:
    try:
        result = subprocess.run(
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
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SEC,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VerificationError(f"ffprobe unavailable for {path.name}: {exc}") from exc
    if result.returncode != 0:
        raise VerificationError(f"ffprobe failed on {path.name}: {result.stderr.strip()}")
    try:
        duration = _finite_number(float(result.stdout.strip()), f"ffprobe duration for {path.name}")
    except (TypeError, ValueError) as exc:
        raise VerificationError(f"could not parse duration from ffprobe for {path.name}") from exc
    if duration <= 0:
        raise VerificationError(f"ffprobe duration for {path.name} must be positive")
    return duration


def probe_audio_duration(path: Path) -> float:
    errors: list[str] = []
    for probe in (get_audio_duration_afinfo, get_audio_duration_ffprobe):
        try:
            return probe(path)
        except VerificationError as exc:
            errors.append(str(exc))
    raise VerificationError(
        f"no audio duration probe succeeded for {path.name}: " + " | ".join(errors)
    )


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VerificationError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise VerificationError(f"{label} must be a finite number")
    return number


def _positive_integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise VerificationError(f"{label} must be a positive integer")
    return value


def _required_string(value: Any, label: str, *, trimmed: bool = True) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VerificationError(f"{label} must be a non-empty string")
    if trimmed and value != value.strip():
        raise VerificationError(f"{label} must not contain surrounding whitespace")
    return value


def _sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise VerificationError(f"{label} must be a lowercase SHA-256")
    return value


def _master_filenames(condition: str) -> dict[str, str]:
    if condition not in {"A", "B"}:
        raise VerificationError("condition must be A or B")
    stem = MASTER_STEM if condition == "A" else MASTER_STEM + CONDITION_B_SUFFIX
    return {
        "aiff": f"{stem}.aiff",
        "m4a": f"{stem}.m4a",
        "manifest": f"{stem}.manifest.json",
    }


def _safe_artifact_path(directory: Path, filename: Any, label: str) -> Path:
    name = _required_string(filename, label)
    if name in {".", ".."} or Path(name).name != name or "/" in name or "\\" in name:
        raise VerificationError(f"{label} must be a plain filename")
    candidate = directory / name
    if candidate.is_symlink():
        raise VerificationError(f"{label} must not be a symlink")
    if not candidate.is_file():
        raise VerificationError(f"local master audio file is missing: {name}")
    try:
        resolved_directory = directory.resolve(strict=True)
        resolved_candidate = candidate.resolve(strict=True)
    except OSError as exc:
        raise VerificationError(f"could not resolve {label}: {exc}") from exc
    if resolved_candidate.parent != resolved_directory:
        raise VerificationError(f"{label} escapes its manifest directory")
    return candidate


def _validate_text_hash(item: dict[str, Any], label: str) -> str:
    declared_hash = _sha256(item.get("text_sha256"), f"{label} text_sha256")
    raw_text = _required_string(item.get("raw_text"), f"{label} raw_text", trimmed=False)
    actual_hash = text_sha256(raw_text)
    if declared_hash != actual_hash:
        raise VerificationError(f"{label} text_sha256 does not match raw_text")
    return declared_hash


def _validate_spoken_segments(
    cue: dict[str, Any], cue_id: str, raw_text: str
) -> None:
    segments = cue.get("spoken_segments")
    if not isinstance(segments, list) or not segments:
        raise VerificationError(f"cue {cue_id!r} spoken_segments must be a non-empty array")
    actual_dialogue: list[tuple[str, str]] = []
    for index, segment in enumerate(segments):
        label = f"cue {cue_id!r} spoken segment {index}"
        if not isinstance(segment, dict):
            raise VerificationError(f"{label} must be an object")
        role = _required_string(segment.get("role"), f"{label} role")
        segment_text = _required_string(
            segment.get("text"), f"{label} text", trimmed=False
        )
        declared_hash = _sha256(
            segment.get("text_sha256"), f"{label} text_sha256"
        )
        if declared_hash != text_sha256(segment_text):
            raise VerificationError(f"{label} text_sha256 does not match text")
        _required_string(segment.get("synthesis_voice"), f"{label} synthesis_voice")
        _required_string(segment.get("synthesis_rate"), f"{label} synthesis_rate")
        actual_dialogue.append((role, segment_text))
    expected_dialogue = parse_dialogue_segments(raw_text)
    if not expected_dialogue:
        raise VerificationError(f"cue {cue_id!r} raw_text has no speakable dialogue")
    if actual_dialogue != expected_dialogue:
        raise VerificationError(
            f"cue {cue_id!r} spoken_segments do not match parsed raw_text"
        )


def _has_strict_manifest_markers(manifest: dict[str, Any]) -> bool:
    if STRICT_TOP_LEVEL_MARKERS.intersection(manifest):
        return True
    cues = manifest.get("narrative_cues")
    if not isinstance(cues, list):
        return False
    for cue in cues:
        if not isinstance(cue, dict):
            continue
        if STRICT_CUE_MARKERS.intersection(cue):
            return True
        segments = cue.get("spoken_segments")
        if isinstance(segments, list) and any(
            isinstance(segment, dict)
            and (
                "text_sha256" in segment
                or "synthesis_voice" in segment
                or "synthesis_rate" in segment
            )
            for segment in segments
        ):
            return True
    return False


def _validate_narrative_cues(
    manifest: dict[str, Any], master_duration_sec: float, strict: bool
) -> list[dict[str, Any]]:
    cues = manifest.get("narrative_cues")
    if not isinstance(cues, list) or not cues:
        raise VerificationError("manifest narrative_cues must be a non-empty array")
    seen_ids: set[str] = set()
    previous_start = -1.0
    previous_end = -1.0
    schedule: list[dict[str, Any]] = []
    for index, cue in enumerate(cues):
        if not isinstance(cue, dict):
            raise VerificationError(f"narrative_cues[{index}] must be an object")
        cue_id = _required_string(cue.get("cue_id"), f"narrative_cues[{index}] cue_id")
        if cue_id in seen_ids:
            raise VerificationError(f"manifest contains duplicate cue_id {cue_id!r}")
        seen_ids.add(cue_id)
        node_id = _required_string(cue.get("node_id"), f"cue {cue_id!r} node_id")
        voice = _required_string(cue.get("voice"), f"cue {cue_id!r} voice")
        start = _finite_number(cue.get("timestamp_sec"), f"cue {cue_id!r} timestamp_sec")
        duration = _finite_number(cue.get("duration_sec"), f"cue {cue_id!r} duration_sec")
        if start < 0 or duration <= 0:
            raise VerificationError(f"cue {cue_id!r} has invalid timing")
        if start <= previous_start:
            raise VerificationError("narrative cue timestamps must be strictly increasing")
        if start < previous_end - FLOAT_EPSILON:
            raise VerificationError(f"cue {cue_id!r} overlaps the previous story cue")
        if start + duration > master_duration_sec + FLOAT_EPSILON:
            raise VerificationError(f"cue {cue_id!r} exceeds the master duration")
        previous_start = start
        previous_end = start + duration

        raw_text = cue.get("raw_text")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise VerificationError(f"cue {cue_id!r} raw_text must be non-empty")
        if strict:
            max_spoken_sec = _finite_number(
                cue.get("max_spoken_sec"), f"cue {cue_id!r} max_spoken_sec"
            )
            if max_spoken_sec <= 0 or duration > max_spoken_sec + FLOAT_EPSILON:
                raise VerificationError(
                    f"cue {cue_id!r} exceeds its positive max_spoken_sec bound"
                )
            _validate_text_hash(cue, f"cue {cue_id!r}")
            _validate_spoken_segments(cue, cue_id, raw_text)
        schedule.append(
            {
                "cue_id": cue_id,
                "node_id": node_id,
                "timestamp_sec": start,
                "voice": voice,
            }
        )
    if strict:
        declared_schedule_hash = _sha256(
            manifest.get("narrative_schedule_sha256"),
            "manifest narrative_schedule_sha256",
        )
        if declared_schedule_hash != canonical_json_sha256(schedule):
            raise VerificationError("narrative_schedule_sha256 does not match cue schedule")
        actual_sequence = tuple(
            (item["cue_id"], item["node_id"]) for item in schedule
        )
        if actual_sequence != CANONICAL_CUE_SEQUENCE:
            raise VerificationError(
                "strict manifest must contain the canonical ordered 10-cue "
                "concealed M1 sequence"
            )
    return schedule


def _validate_workout_events(
    manifest: dict[str, Any], master_duration_sec: float, nav_count: int, final_nav: float
) -> list[dict[str, Any]]:
    events = manifest.get("workout_nav_events")
    if not isinstance(events, list) or len(events) != nav_count:
        raise VerificationError("workout_nav_events length must match workout_nav_events_count")
    seen_ids: set[str] = set()
    previous_start = -1.0
    previous_end = -1.0
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise VerificationError(f"workout_nav_events[{index}] must be an object")
        label = f"workout NAV event {index}"
        event_id = _required_string(event.get("event_id"), f"{label} event_id")
        if event_id in seen_ids:
            raise VerificationError(f"duplicate workout event_id {event_id!r}")
        seen_ids.add(event_id)
        start = _finite_number(event.get("timestamp_sec"), f"{label} timestamp_sec")
        duration = _finite_number(event.get("duration_sec"), f"{label} duration_sec")
        if start < 0 or duration <= 0:
            raise VerificationError(f"{label} has invalid timing")
        if start <= previous_start:
            raise VerificationError("workout NAV timestamps must be strictly increasing")
        if start < previous_end - FLOAT_EPSILON:
            raise VerificationError(f"{label} overlaps the previous workout NAV event")
        if start + duration > master_duration_sec + FLOAT_EPSILON:
            raise VerificationError(f"{label} exceeds the master duration")
        previous_start = start
        previous_end = start + duration
        _required_string(event.get("voice"), f"{label} voice")
        _validate_text_hash(event, label)
        _required_string(event.get("synthesis_voice"), f"{label} synthesis_voice")
        _required_string(event.get("synthesis_rate"), f"{label} synthesis_rate")
    last_event = events[-1]
    if last_event.get("voice") != "NAV":
        raise VerificationError("final workout event must use the NAV voice")
    last_timestamp = _finite_number(
        last_event.get("timestamp_sec"), "final workout NAV timestamp"
    )
    if abs(last_timestamp - final_nav) > FLOAT_EPSILON:
        raise VerificationError("workout_final_nav_timestamp_sec does not match the final NAV event")
    declared_hash = _sha256(
        manifest.get("workout_nav_events_sha256"),
        "manifest workout_nav_events_sha256",
    )
    if declared_hash != canonical_json_sha256(events):
        raise VerificationError("workout_nav_events_sha256 does not match workout events")
    return events


def _validate_story_nav_nonoverlap(manifest: dict[str, Any]) -> None:
    cues = manifest["narrative_cues"]
    events = manifest["workout_nav_events"]
    for cue in cues:
        cue_id = cue["cue_id"]
        story_start = _finite_number(cue["timestamp_sec"], f"cue {cue_id!r} timestamp")
        story_end = story_start + _finite_number(
            cue["duration_sec"], f"cue {cue_id!r} duration"
        )
        for index, event in enumerate(events):
            nav_start = _finite_number(
                event["timestamp_sec"], f"workout NAV event {index} timestamp"
            )
            nav_end = nav_start + _finite_number(
                event["duration_sec"], f"workout NAV event {index} duration"
            )
            if (
                story_start < nav_end - FLOAT_EPSILON
                and nav_start < story_end - FLOAT_EPSILON
            ):
                raise VerificationError(
                    f"cue {cue_id!r} overlaps workout NAV event {index}"
                )


def _validate_strict_provenance(
    manifest_path: Path,
    manifest: dict[str, Any],
    master_duration_sec: float,
    nav_count: int,
    final_nav: float,
) -> None:
    condition = manifest.get("condition")
    if condition not in {"A", "B"}:
        raise VerificationError("strict manifest condition must be A or B")
    expected_names = _master_filenames(condition)
    if manifest_path.name != expected_names["manifest"]:
        raise VerificationError(
            f"Condition {condition} manifest filename must be {expected_names['manifest']!r}"
        )
    if manifest.get("aiff_file") != expected_names["aiff"]:
        raise VerificationError(
            f"Condition {condition} aiff_file must be {expected_names['aiff']!r}"
        )
    if manifest.get("m4a_file") != expected_names["m4a"]:
        raise VerificationError(
            f"Condition {condition} m4a_file must be {expected_names['m4a']!r}"
        )
    expected_text_field = "condition_a_text" if condition == "A" else "condition_b_text"
    if manifest.get("story_text_field") != expected_text_field:
        raise VerificationError(
            f"Condition {condition} story_text_field must be {expected_text_field!r}"
        )
    _required_string(manifest.get("binding_id"), "manifest binding_id")
    _sha256(manifest.get("binding_sha256"), "manifest binding_sha256")
    _sha256(manifest.get("beats_sha256"), "manifest beats_sha256")
    sample_rate = _positive_integer(manifest.get("sample_rate_hz"), "manifest sample_rate_hz")
    if sample_rate != 44100:
        raise VerificationError("manifest sample_rate_hz must be 44100")
    _validate_workout_events(manifest, master_duration_sec, nav_count, final_nav)
    _validate_story_nav_nonoverlap(manifest)


def verify_manifest(
    manifest_path: Path,
    *,
    require_strict: bool = False,
    duration_probe: Callable[[Path], float] | None = None,
) -> VerifiedManifest:
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    if duration_probe is None:
        duration_probe = probe_audio_duration
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise VerificationError(
            f"manifest schema_version must be {MANIFEST_SCHEMA_VERSION!r}"
        )
    tool_schema = manifest.get("tool_schema")
    if tool_schema is None:
        condition_b_manifest = _master_filenames("B")["manifest"]
        if (
            manifest_path.name == condition_b_manifest
            or _has_strict_manifest_markers(manifest)
        ):
            raise VerificationError(
                "new-format manifest markers require the provenance-strict tool_schema"
            )
        strict = False
    elif tool_schema == STRICT_TOOL_SCHEMA:
        strict = True
    else:
        raise VerificationError(f"unsupported tool_schema {tool_schema!r}")
    if require_strict and not strict:
        raise VerificationError("A/B parity requires provenance-strict manifests")

    if manifest.get("mission_id") != MISSION_ID:
        raise VerificationError(f"manifest mission_id must be {MISSION_ID!r}")
    if manifest.get("concept_id") != CONCEPT_ID:
        raise VerificationError(f"manifest concept_id must be {CONCEPT_ID!r}")
    if manifest.get("branch") != BRANCH:
        raise VerificationError(f"manifest branch must be {BRANCH!r}")

    target_duration = _finite_number(
        manifest.get("target_duration_sec"), "manifest target_duration_sec"
    )
    declared_aiff_duration = _finite_number(
        manifest.get("actual_duration_aiff_sec"), "manifest actual_duration_aiff_sec"
    )
    declared_m4a_duration = _finite_number(
        manifest.get("actual_duration_m4a_sec"), "manifest actual_duration_m4a_sec"
    )
    for label, duration in (
        ("target", target_duration),
        ("declared AIFF", declared_aiff_duration),
        ("declared M4A", declared_m4a_duration),
    ):
        if duration <= 0 or abs(duration - EXPECTED_DURATION_SEC) > DURATION_TOLERANCE_SEC:
            raise VerificationError(
                f"{label} duration {duration}s is not within {EXPECTED_DURATION_SEC}s bound"
            )

    manifest_directory = manifest_path.parent
    aiff_name = manifest.get("aiff_file", f"{MASTER_STEM}.aiff")
    m4a_name = manifest.get("m4a_file", f"{MASTER_STEM}.m4a")
    aiff_path = _safe_artifact_path(manifest_directory, aiff_name, "aiff_file")
    m4a_path = _safe_artifact_path(manifest_directory, m4a_name, "m4a_file")
    aiff_duration = duration_probe(aiff_path)
    m4a_duration = duration_probe(m4a_path)
    for label, probed, declared in (
        ("AIFF", aiff_duration, declared_aiff_duration),
        ("M4A", m4a_duration, declared_m4a_duration),
    ):
        probed = _finite_number(probed, f"probed {label} duration")
        if probed <= 0 or abs(probed - EXPECTED_DURATION_SEC) > DURATION_TOLERANCE_SEC:
            raise VerificationError(
                f"{label} duration {probed}s is not within {EXPECTED_DURATION_SEC}s bound"
            )
        if abs(probed - declared) > DURATION_TOLERANCE_SEC:
            raise VerificationError(
                f"{label} probed duration {probed}s does not match manifest {declared}s"
            )

    expected_aiff_sha = _sha256(manifest.get("aiff_sha256"), "manifest aiff_sha256")
    expected_m4a_sha = _sha256(manifest.get("m4a_sha256"), "manifest m4a_sha256")
    actual_aiff_sha = compute_sha256(aiff_path)
    actual_m4a_sha = compute_sha256(m4a_path)
    if actual_aiff_sha != expected_aiff_sha:
        raise VerificationError("AIFF SHA-256 mismatch")
    if actual_m4a_sha != expected_m4a_sha:
        raise VerificationError("M4A SHA-256 mismatch")

    final_nav = _finite_number(
        manifest.get("workout_final_nav_timestamp_sec"),
        "manifest workout_final_nav_timestamp_sec",
    )
    if not FINAL_NAV_MIN_SEC <= final_nav <= FINAL_NAV_MAX_SEC:
        raise VerificationError(
            f"final NAV timestamp {final_nav}s is not in safe "
            f"{FINAL_NAV_MIN_SEC:g}-{FINAL_NAV_MAX_SEC:g}s range"
        )
    master_duration = min(aiff_duration, m4a_duration)
    if final_nav >= master_duration:
        raise VerificationError("final NAV timestamp is outside the master duration")
    nav_count = _positive_integer(
        manifest.get("workout_nav_events_count"),
        "manifest workout_nav_events_count",
    )
    _validate_narrative_cues(manifest, master_duration, strict)
    if strict:
        _validate_strict_provenance(
            manifest_path,
            manifest,
            master_duration,
            nav_count,
            final_nav,
        )

    return VerifiedManifest(
        path=manifest_path,
        manifest=manifest,
        strict=strict,
        aiff_path=aiff_path,
        m4a_path=m4a_path,
        aiff_duration_sec=aiff_duration,
        m4a_duration_sec=m4a_duration,
        aiff_sha256=actual_aiff_sha,
        m4a_sha256=actual_m4a_sha,
    )


def verify_ab_parity(first: VerifiedManifest, second: VerifiedManifest) -> None:
    if first.path.resolve() == second.path.resolve():
        raise VerificationError("A/B parity requires two different manifest files")
    if not first.strict or not second.strict:
        raise VerificationError("A/B parity requires provenance-strict manifests")
    by_condition = {
        first.manifest.get("condition"): first,
        second.manifest.get("condition"): second,
    }
    if set(by_condition) != {"A", "B"} or len(by_condition) != 2:
        raise VerificationError("A/B parity requires exactly one Condition A and one Condition B")
    condition_a = by_condition["A"]
    condition_b = by_condition["B"]
    a = condition_a.manifest
    b = condition_b.manifest

    exact_fields = (
        "tool_schema",
        "mission_id",
        "concept_id",
        "branch",
        "binding_id",
        "binding_sha256",
        "beats_sha256",
        "sample_rate_hz",
        "workout_nav_events_count",
        "workout_nav_events_sha256",
        "narrative_schedule_sha256",
    )
    for field in exact_fields:
        if a.get(field) != b.get(field):
            raise VerificationError(f"A/B parity mismatch for {field}")
    for field in (
        "target_duration_sec",
        "actual_duration_aiff_sec",
        "actual_duration_m4a_sec",
        "workout_final_nav_timestamp_sec",
    ):
        if abs(_finite_number(a.get(field), field) - _finite_number(b.get(field), field)) > DURATION_TOLERANCE_SEC:
            raise VerificationError(f"A/B parity mismatch for {field}")
    if abs(condition_a.aiff_duration_sec - condition_b.aiff_duration_sec) > DURATION_TOLERANCE_SEC:
        raise VerificationError("A/B parity mismatch for probed AIFF duration")
    if abs(condition_a.m4a_duration_sec - condition_b.m4a_duration_sec) > DURATION_TOLERANCE_SEC:
        raise VerificationError("A/B parity mismatch for probed M4A duration")
    if a.get("workout_nav_events") != b.get("workout_nav_events"):
        raise VerificationError("A/B workout NAV events differ")
    if condition_a.aiff_sha256 == condition_b.aiff_sha256:
        raise VerificationError("Condition A/B AIFF masters are byte-identical")
    if condition_a.m4a_sha256 == condition_b.m4a_sha256:
        raise VerificationError("Condition A/B M4A masters are byte-identical")

    cues_a = a["narrative_cues"]
    cues_b = b["narrative_cues"]
    if len(cues_a) != len(cues_b):
        raise VerificationError("A/B narrative cue count differs")
    has_story_text_difference = False
    for index, (cue_a, cue_b) in enumerate(zip(cues_a, cues_b)):
        cue_id = cue_a.get("cue_id", index)
        for field in ("cue_id", "node_id", "voice", "max_spoken_sec"):
            if cue_a.get(field) != cue_b.get(field):
                raise VerificationError(
                    f"A/B cue {cue_id!r} parity mismatch for {field}"
                )
        timestamp_a = _finite_number(cue_a.get("timestamp_sec"), "A cue timestamp")
        timestamp_b = _finite_number(cue_b.get("timestamp_sec"), "B cue timestamp")
        if abs(timestamp_a - timestamp_b) > FLOAT_EPSILON:
            raise VerificationError(
                f"A/B cue {cue_id!r} parity mismatch for timestamp_sec"
            )
        duration_a = _finite_number(cue_a.get("duration_sec"), "A cue duration")
        duration_b = _finite_number(cue_b.get("duration_sec"), "B cue duration")
        if abs(duration_a - duration_b) > CUE_DURATION_PARITY_TOLERANCE_SEC:
            raise VerificationError(
                f"A/B cue {cue_id!r} duration differs by more than "
                f"{CUE_DURATION_PARITY_TOLERANCE_SEC:.1f}s"
            )
        if cue_a.get("text_sha256") != cue_b.get("text_sha256"):
            has_story_text_difference = True
        voice_signature_a = [
            (
                segment.get("role"),
                segment.get("synthesis_voice"),
                segment.get("synthesis_rate"),
            )
            for segment in cue_a["spoken_segments"]
        ]
        voice_signature_b = [
            (
                segment.get("role"),
                segment.get("synthesis_voice"),
                segment.get("synthesis_rate"),
            )
            for segment in cue_b["spoken_segments"]
        ]
        if voice_signature_a != voice_signature_b:
            raise VerificationError(
                f"A/B cue {cue_id!r} spoken voice/profile sequence differs"
            )
        # Story text, hashes, and bounded cue duration may differ by design.
    if not has_story_text_difference:
        raise VerificationError(
            "Condition A/B manifests must differ in at least one cue text_sha256"
        )


def _print_verified(result: VerifiedManifest) -> None:
    profile = result.manifest.get("condition", "legacy A")
    print(f"Field verification PASSED [{profile}]:")
    print(
        f"  AIFF File: {result.aiff_path.name} "
        f"({result.aiff_duration_sec:.2f}s, SHA: {result.aiff_sha256})"
    )
    print(
        f"  M4A File:  {result.m4a_path.name} "
        f"({result.m4a_duration_sec:.2f}s, SHA: {result.m4a_sha256})"
    )
    print(
        "  Final NAV Event: "
        f"{result.manifest['workout_final_nav_timestamp_sec']}s "
        "(completes before 1800.0s)"
    )


def verify_audio_dir(
    audio_dir: Path,
    *,
    manifest_path: Path | None = None,
    compare_manifest: Path | None = None,
) -> int:
    primary_path = manifest_path or Path(audio_dir) / DEFAULT_MANIFEST_NAME
    try:
        primary = verify_manifest(primary_path, require_strict=compare_manifest is not None)
        comparison: VerifiedManifest | None = None
        if compare_manifest is not None:
            comparison = verify_manifest(compare_manifest, require_strict=True)
            verify_ab_parity(primary, comparison)
        _print_verified(primary)
        if comparison is not None:
            _print_verified(comparison)
            print("A/B parity PASSED: workout and cue schedule are experimentally aligned.")
        return 0
    except (OSError, VerificationError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR)
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Specific legacy or strict manifest to verify (audio files resolve beside it).",
    )
    parser.add_argument(
        "--compare-manifest",
        type=Path,
        help="Strictly verify a second manifest and enforce Condition A/B parity.",
    )
    args = parser.parse_args(argv)
    return verify_audio_dir(
        args.audio_dir,
        manifest_path=args.manifest,
        compare_manifest=args.compare_manifest,
    )


if __name__ == "__main__":
    sys.exit(main())
