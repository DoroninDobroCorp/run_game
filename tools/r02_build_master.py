#!/usr/bin/env python3
"""Build a fixed 30-minute R02 master for experimental Condition A or B.

Condition A remains the default and retains the legacy master filenames.
Condition B uses the authored ``condition_b_text`` and publishes a separate
``*_condition_b`` master trio. All synthesis and validation happens in a
staging directory; the prior published trio is restored if publication fails.
"""

from __future__ import annotations

import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from typing import Any
import unicodedata
import wave

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BEATS = ROOT / "research/r02/mission_01_beats.v0.1.json"
DEFAULT_LOCAL_DIR = ROOT / "research/r02/local/valparaiso_central"
DEFAULT_BINDING = DEFAULT_LOCAL_DIR / "current.binding.json"
DEFAULT_FIXTURE_BINDING = ROOT / "research/r02/fixtures/field_binding.example.json"
DEFAULT_OUTPUT_DIR = DEFAULT_LOCAL_DIR / "audio"

MANIFEST_SCHEMA_VERSION = "0.1"  # Kept for r02_prepare_ios compatibility.
TOOL_SCHEMA = "r02_build_master_manifest/0.2"
MISSION_ID = "m01"
CONCEPT_ID = "null_layer"
BRANCH = "atlas_disclosure=concealed"
MASTER_STEM = "m01_solo_founder_30min"
CONDITION_B_SUFFIX = "_condition_b"

SAMPLE_RATE = 44100
TARGET_DURATION_SEC = 1800.0
TOTAL_SAMPLES = int(TARGET_DURATION_SEC * SAMPLE_RATE)
DURATION_TOLERANCE_SEC = 0.5
FINAL_NAV_MIN_SEC = 1790.0
FINAL_NAV_MAX_SEC = 1795.0
FLOAT_EPSILON = 1e-9
TTS_TIMEOUT_SEC = 120
CONVERSION_TIMEOUT_SEC = 1200

WORKOUT_NAV_EVENTS = [
    (0.0, "NAV", "Тренировка запущена. Пять минут ходьбы."),
    (270.0, "NAV", "Внимание. Первый беговой интервал через тридцать секунд."),
    (300.0, "NAV", "Бег один. Бег шестьдесят секунд."),
    (360.0, "NAV", "Переход на ходьбу. Ходьба девяносто секунд."),
    (420.0, "NAV", "Внимание. Бег два через тридцать секунд."),
    (450.0, "NAV", "Бег два. Бег шестьдесят секунд."),
    (510.0, "NAV", "Переход на ходьбу. Ходьба девяносто секунд."),
    (570.0, "NAV", "Внимание. Бег три через тридцать секунд."),
    (600.0, "NAV", "Бег три. Бег шестьдесят секунд."),
    (660.0, "NAV", "Переход на ходьбу. Ходьба девяносто секунд."),
    (720.0, "NAV", "Внимание. Бег четыре через тридцать секунд."),
    (750.0, "NAV", "Бег четыре. Бег шестьдесят секунд."),
    (810.0, "NAV", "Переход на ходьбу. Ходьба девяносто секунд."),
    (870.0, "NAV", "Внимание. Бег пять через тридцать секунд."),
    (900.0, "NAV", "Бег пять. Бег шестьдесят секунд."),
    (960.0, "NAV", "Переход на ходьбу. Ходьба девяносто секунд."),
    (1020.0, "NAV", "Внимание. Бег шесть через тридцать секунд."),
    (1050.0, "NAV", "Бег шесть. Бег шестьдесят секунд."),
    (1110.0, "NAV", "Переход на ходьбу. Ходьба девяносто секунд."),
    (1170.0, "NAV", "Внимание. Бег семь через тридцать секунд."),
    (1200.0, "NAV", "Бег семь. Бег шестьдесят секунд."),
    (1260.0, "NAV", "Переход на ходьбу. Ходьба девяносто секунд."),
    (1320.0, "NAV", "Внимание. Бег восемь через тридцать секунд."),
    (1350.0, "NAV", "Бег восемь. Бег шестьдесят секунд."),
    (1410.0, "NAV", "Переход на ходьбу. Ходьба девяносто секунд."),
    (1500.0, "NAV", "Заминка. Спокойная ходьба пять минут."),
    (1792.0, "NAV", "Тренировка завершена. Продолжайте спокойную ходьбу, если это необходимо."),
]

STORY_CUE_TIMESTAMPS = {
    "m01_c001": 8.0,
    "m01_c002": 240.0,
    "m01_c003": 365.0,
    "m01_c004": 665.0,
    "m01_c005": 815.0,
    "m01_c006a": 965.0,
    "m01_c007": 1115.0,
    "m01_c008": 1415.0,
    "m01_c009": 1510.0,
    "m01_c010": 1650.0,
}

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

# Voice configurations for macOS say.
VOICE_SPECS = {
    "NAV": {"voice": "Milena", "rate": "185"},
    "ATLAS": {"voice": "Yuri", "fallback_voice": "Milena", "rate": "150"},
    "LEA": {"voice": "Milena", "rate": "170"},
}

PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\.name\}")


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
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_json_constant_error,
        object_pairs_hook=_json_object_without_duplicates,
    )
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def load_json_with_sha256(path: Path) -> tuple[dict[str, Any], str]:
    payload = path.read_bytes()
    value = json.loads(
        payload.decode("utf-8"),
        parse_constant=_json_constant_error,
        object_pairs_hook=_json_object_without_duplicates,
    )
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value, hashlib.sha256(payload).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def master_filenames(condition: str) -> dict[str, str]:
    if condition not in {"A", "B"}:
        raise ValueError("condition must be A or B")
    stem = MASTER_STEM if condition == "A" else MASTER_STEM + CONDITION_B_SUFFIX
    return {
        "aiff": f"{stem}.aiff",
        "m4a": f"{stem}.m4a",
        "manifest": f"{stem}.manifest.json",
    }


def bind_text(text: str, binding: dict[str, Any]) -> str:
    slots = binding.get("slots", {})

    def replace(match: re.Match[str]) -> str:
        slot = slots.get(match.group(1)) if isinstance(slots, dict) else None
        name = slot.get("name") if isinstance(slot, dict) else None
        return name if isinstance(name, str) and name.strip() else match.group(0)

    return PLACEHOLDER_RE.sub(replace, text)


def binding_slot_names(binding: dict[str, Any]) -> list[str]:
    slots = binding.get("slots", {})
    if not isinstance(slots, dict):
        raise ValueError("binding slots must be an object")
    names: list[str] = []
    for slot in slots.values():
        if not isinstance(slot, dict):
            continue
        name = slot.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def normalized_casefold(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def parse_dialogue_segments(text: str) -> list[tuple[str, str]]:
    """Parse authored dialogue into voice-role and spoken-text segments."""
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
        raise ValueError("dialogue contains unlabeled text before the first speaker")

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


def tts_segment_to_wav(
    text: str, voice_role: str, out_wav_path: Path
) -> dict[str, str]:
    """Synthesize one segment and return the voice profile actually requested."""
    spec = VOICE_SPECS.get(voice_role, VOICE_SPECS["LEA"])
    voice_name = spec.get("voice", "Milena")
    rate = spec.get("rate", "175")
    temp_aiff = out_wav_path.with_suffix(".aiff")

    try:
        command = ["say", "-v", voice_name, "-r", rate, "-o", str(temp_aiff), text]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=TTS_TIMEOUT_SEC,
        )
        if result.returncode != 0 and "fallback_voice" in spec:
            voice_name = spec["fallback_voice"]
            command = [
                "say",
                "-v",
                voice_name,
                "-r",
                rate,
                "-o",
                str(temp_aiff),
                text,
            ]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=TTS_TIMEOUT_SEC,
            )
        if result.returncode != 0:
            raise RuntimeError(
                f"say failed for role {voice_role} ({text!r}): {result.stderr}"
            )

        conversion = subprocess.run(
            [
                "afconvert",
                "-f",
                "WAVE",
                "-c",
                "1",
                "-d",
                f"LEI16@{SAMPLE_RATE}",
                str(temp_aiff),
                str(out_wav_path),
            ],
            capture_output=True,
            text=True,
            timeout=TTS_TIMEOUT_SEC,
        )
        if conversion.returncode != 0:
            raise RuntimeError(f"afconvert failed: {conversion.stderr}")
    finally:
        temp_aiff.unlink(missing_ok=True)

    return {"voice": voice_name, "rate": rate}


def read_wav_pcm(path: Path) -> list[int]:
    with wave.open(str(path), "rb") as wav_file:
        if wav_file.getnchannels() != 1:
            raise RuntimeError(f"Synthesized WAV must be mono: {path.name}")
        if wav_file.getsampwidth() != 2:
            raise RuntimeError(f"Synthesized WAV must be signed 16-bit PCM: {path.name}")
        if wav_file.getframerate() != SAMPLE_RATE:
            raise RuntimeError(
                f"Synthesized WAV sample rate is {wav_file.getframerate()}, expected {SAMPLE_RATE}"
            )
        if wav_file.getcomptype() != "NONE":
            raise RuntimeError(f"Synthesized WAV must be uncompressed PCM: {path.name}")
        frame_count = wav_file.getnframes()
        data = wav_file.readframes(frame_count)
    if len(data) != frame_count * 2:
        raise RuntimeError(f"Synthesized WAV is truncated: {path.name}")
    return list(struct.unpack(f"<{frame_count}h", data))


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        while chunk := file_handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def get_audio_duration_afinfo(path: Path) -> float:
    result = subprocess.run(
        ["afinfo", str(path)],
        capture_output=True,
        text=True,
        timeout=TTS_TIMEOUT_SEC,
    )
    if result.returncode != 0:
        raise RuntimeError(f"afinfo failed: {result.stderr}")
    match = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", result.stdout)
    if not match:
        raise RuntimeError(f"Could not parse duration from afinfo output:\n{result.stdout}")
    duration = float(match.group(1))
    if not math.isfinite(duration) or duration <= 0:
        raise RuntimeError(f"afinfo reported an invalid duration for {path.name}")
    return duration


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def prepare_build_plan(
    beats: dict[str, Any], binding: dict[str, Any], condition: str
) -> list[dict[str, Any]]:
    """Validate authored sources and return the selected, bound story plan."""
    if condition not in {"A", "B"}:
        raise ValueError("condition must be A or B")
    if beats.get("mission_id") != MISSION_ID:
        raise ValueError(f"beats mission_id must be {MISSION_ID!r}")
    if beats.get("concept_id") != CONCEPT_ID:
        raise ValueError(f"beats concept_id must be {CONCEPT_ID!r}")
    beats_duration = _number(beats.get("target_duration_sec"), "beats target_duration_sec")
    if abs(beats_duration - TARGET_DURATION_SEC) > FLOAT_EPSILON:
        raise ValueError(
            f"beats target duration {beats_duration}s does not match {TARGET_DURATION_SEC}s"
        )
    operator_rules = beats.get("operator_rules")
    if not isinstance(operator_rules, list) or not any(
        isinstance(rule, str) and BRANCH in rule for rule in operator_rules
    ):
        raise ValueError(f"beats do not declare the fixed branch {BRANCH!r}")

    binding_id = binding.get("binding_id")
    if (
        not isinstance(binding_id, str)
        or not binding_id.strip()
        or binding_id != binding_id.strip()
    ):
        raise ValueError("binding_id must be a non-empty trimmed string")

    raw_cues = beats.get("cues")
    if not isinstance(raw_cues, list):
        raise ValueError("beats cues must be an array")
    cue_by_id: dict[str, dict[str, Any]] = {}
    for index, cue in enumerate(raw_cues):
        if not isinstance(cue, dict):
            raise ValueError(f"beats cues[{index}] must be an object")
        cue_id = cue.get("cue_id")
        if not isinstance(cue_id, str) or not cue_id.strip():
            raise ValueError(f"beats cues[{index}] requires cue_id")
        if cue_id in cue_by_id:
            raise ValueError(f"duplicate cue_id {cue_id!r} in beats")
        cue_by_id[cue_id] = cue

    canonical_ids = tuple(cue_id for cue_id, _ in CANONICAL_CUE_SEQUENCE)
    if tuple(STORY_CUE_TIMESTAMPS) != canonical_ids:
        raise RuntimeError("builder cue timestamps do not match the canonical M1 branch")
    expected_node_by_cue = dict(CANONICAL_CUE_SEQUENCE)

    text_field = "condition_a_text" if condition == "A" else "condition_b_text"
    condition_b_forbidden_names = binding_slot_names(binding) if condition == "B" else []
    plan: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    previous_timestamp = -1.0
    for cue_id, timestamp in STORY_CUE_TIMESTAMPS.items():
        cue = cue_by_id.get(cue_id)
        if cue is None:
            raise ValueError(f"missing cue card for {cue_id}")
        node_id = cue.get("node_id")
        voice = cue.get("voice")
        source_text = cue.get(text_field)
        if not isinstance(node_id, str) or not node_id.strip():
            raise ValueError(f"cue {cue_id!r} requires node_id")
        if node_id != expected_node_by_cue[cue_id]:
            raise ValueError(
                f"cue {cue_id!r} node_id must be {expected_node_by_cue[cue_id]!r} "
                "for the concealed M1 branch"
            )
        if node_id in seen_nodes:
            raise ValueError(f"duplicate selected node_id {node_id!r}")
        seen_nodes.add(node_id)
        if not isinstance(voice, str) or not voice.strip():
            raise ValueError(f"cue {cue_id!r} requires voice")
        if not isinstance(source_text, str) or not source_text.strip():
            raise ValueError(f"cue {cue_id!r} requires non-empty {text_field}")
        max_spoken_sec = _number(
            cue.get("max_spoken_sec"), f"cue {cue_id!r} max_spoken_sec"
        )
        if max_spoken_sec <= 0:
            raise ValueError(f"cue {cue_id!r} max_spoken_sec must be positive")

        start = _number(timestamp, f"cue {cue_id!r} timestamp")
        if start < 0 or start >= TARGET_DURATION_SEC or start <= previous_timestamp:
            raise ValueError(f"cue {cue_id!r} has an invalid or unordered timestamp")
        previous_timestamp = start
        trigger = cue.get("trigger")
        window = trigger.get("window_sec") if isinstance(trigger, dict) else None
        if (
            not isinstance(window, list)
            or len(window) != 2
            or start < _number(window[0], f"cue {cue_id!r} window start")
            or start > _number(window[1], f"cue {cue_id!r} window end")
        ):
            raise ValueError(f"cue {cue_id!r} timestamp is outside its authored window")

        if condition == "B" and PLACEHOLDER_RE.search(source_text):
            raise ValueError(f"cue {cue_id!r} Condition B text contains a place placeholder")
        if condition == "B":
            folded_text = normalized_casefold(source_text)
            literal_place_names = [
                name
                for name in condition_b_forbidden_names
                if normalized_casefold(name) in folded_text
            ]
            if literal_place_names:
                raise ValueError(
                    f"cue {cue_id!r} Condition B text contains a bound place name"
                )
        selected_text = bind_text(source_text, binding) if condition == "A" else source_text
        unresolved = sorted(set(match.group(0) for match in PLACEHOLDER_RE.finditer(selected_text)))
        if unresolved:
            raise ValueError(
                f"cue {cue_id!r} has unresolved placeholders: {', '.join(unresolved)}"
            )
        segments = parse_dialogue_segments(selected_text)
        if not segments or any(not role or not text.strip() for role, text in segments):
            raise ValueError(f"cue {cue_id!r} has no speakable dialogue")
        plan.append(
            {
                "cue_id": cue_id,
                "node_id": node_id,
                "timestamp_sec": start,
                "voice": voice,
                "max_spoken_sec": max_spoken_sec,
                "raw_text": selected_text,
                "text_sha256": text_sha256(selected_text),
                "segments": segments,
            }
        )
    return plan


def _configured_profile(role: str) -> dict[str, str]:
    spec = VOICE_SPECS.get(role, VOICE_SPECS["LEA"])
    return {"voice": spec.get("voice", "Milena"), "rate": spec.get("rate", "175")}


def _synthesize_samples(
    text: str, role: str, temp_wav: Path
) -> tuple[list[int], dict[str, str]]:
    try:
        profile = tts_segment_to_wav(text, role, temp_wav)
        samples = read_wav_pcm(temp_wav)
    finally:
        temp_wav.unlink(missing_ok=True)
    if not samples:
        raise RuntimeError(f"TTS produced an empty segment for role {role}")
    if not any(samples):
        raise RuntimeError(f"TTS produced an all-silent segment for role {role}")
    if not isinstance(profile, dict):
        profile = _configured_profile(role)
    voice = profile.get("voice")
    rate = profile.get("rate")
    if not isinstance(voice, str) or not voice or not isinstance(rate, str) or not rate:
        raise RuntimeError(f"TTS returned invalid provenance for role {role}")
    return samples, {"voice": voice, "rate": rate}


def _mix_samples(pcm_buffer: array, start_sec: float, samples: list[int], label: str) -> None:
    if not samples:
        raise RuntimeError(f"{label} has zero duration")
    start_sample = int(start_sec * SAMPLE_RATE)
    end_sample = start_sample + len(samples)
    if start_sample < 0 or end_sample > TOTAL_SAMPLES:
        raise RuntimeError(
            f"{label} would be truncated ({start_sec:.3f}s + "
            f"{len(samples) / SAMPLE_RATE:.3f}s > {TARGET_DURATION_SEC:.3f}s)"
        )
    for offset, sample in enumerate(samples):
        index = start_sample + offset
        pcm_buffer[index] = max(-32768, min(32767, pcm_buffer[index] + sample))


def validate_rendered_timeline(
    workout_events: list[dict[str, Any]],
    narrative_cues: list[dict[str, Any]],
    target_duration_sec: float,
) -> None:
    """Fail closed on bounds, zero duration, story overlap, and final NAV."""
    target = _number(target_duration_sec, "target duration")
    if target <= 0:
        raise ValueError("target duration must be positive")
    if not workout_events:
        raise ValueError("workout NAV event list must not be empty")
    if not narrative_cues:
        raise ValueError("narrative cue list must not be empty")

    def timing(item: dict[str, Any], label: str) -> tuple[float, float]:
        start = _number(item.get("timestamp_sec"), f"{label} timestamp")
        duration = _number(item.get("duration_sec"), f"{label} duration")
        if start < 0 or duration <= 0:
            raise ValueError(f"{label} has invalid timing")
        if start + duration > target + FLOAT_EPSILON:
            raise ValueError(f"{label} would be truncated by the master duration")
        return start, duration

    previous_nav = -1.0
    previous_nav_end = -1.0
    nav_intervals: list[tuple[float, float, int]] = []
    for index, event in enumerate(workout_events):
        start, duration = timing(event, f"workout NAV event {index}")
        if start <= previous_nav:
            raise ValueError("workout NAV timestamps must be strictly increasing")
        if start < previous_nav_end - FLOAT_EPSILON:
            raise ValueError(f"workout NAV event {index} overlaps the previous workout NAV")
        previous_nav = start
        previous_nav_end = start + duration
        nav_intervals.append((start, previous_nav_end, index))
    final_nav = workout_events[-1]
    if final_nav.get("voice") != "NAV":
        raise ValueError("final workout event must use the NAV voice")
    final_nav_timestamp = _number(
        final_nav.get("timestamp_sec"), "final workout NAV timestamp"
    )
    if not FINAL_NAV_MIN_SEC <= final_nav_timestamp <= FINAL_NAV_MAX_SEC:
        raise ValueError(
            f"final workout NAV timestamp {final_nav_timestamp}s is outside the safe "
            f"{FINAL_NAV_MIN_SEC:g}-{FINAL_NAV_MAX_SEC:g}s range"
        )

    previous_story_start = -1.0
    previous_story_end = -1.0
    story_intervals: list[tuple[float, float, Any]] = []
    for index, cue in enumerate(narrative_cues):
        cue_id = cue.get("cue_id", index)
        start, duration = timing(cue, f"story cue {cue_id!r}")
        if start <= previous_story_start:
            raise ValueError("story cue timestamps must be strictly increasing")
        if start < previous_story_end - FLOAT_EPSILON:
            raise ValueError(f"story cue {cue_id!r} overlaps the previous story cue")
        previous_story_start = start
        previous_story_end = start + duration
        story_intervals.append((start, previous_story_end, cue_id))

    for story_start, story_end, cue_id in story_intervals:
        for nav_start, nav_end, nav_index in nav_intervals:
            if (
                story_start < nav_end - FLOAT_EPSILON
                and nav_start < story_end - FLOAT_EPSILON
            ):
                raise ValueError(
                    f"story cue {cue_id!r} overlaps workout NAV event {nav_index}"
                )


def convert_master_formats(master_wav: Path, master_aiff: Path, master_m4a: Path) -> None:
    subprocess.run(
        [
            "afconvert",
            "-f",
            "AIFF",
            "-c",
            "1",
            "-d",
            f"BEI16@{SAMPLE_RATE}",
            str(master_wav),
            str(master_aiff),
        ],
        check=True,
        capture_output=True,
        timeout=CONVERSION_TIMEOUT_SEC,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(master_wav),
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(master_m4a),
        ],
        check=True,
        capture_output=True,
        timeout=CONVERSION_TIMEOUT_SEC,
    )
    if not master_aiff.is_file() or not master_m4a.is_file():
        raise RuntimeError("audio conversion did not produce both master files")


def publish_staged_files(
    staging_dir: Path, output_dir: Path, filenames: list[str]
) -> None:
    """Publish a file set with per-file atomic replace and transaction rollback."""
    if output_dir.is_symlink():
        raise ValueError(f"output directory must not be a symlink: {output_dir}")
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"output path is not a directory: {output_dir}")
    for name in filenames:
        if Path(name).name != name or name in {"", ".", ".."}:
            raise ValueError(f"unsafe publish filename: {name!r}")
        source = staging_dir / name
        if not source.is_file() or source.is_symlink():
            raise RuntimeError(f"staged artifact missing or unsafe: {name}")

    output_existed = output_dir.exists()
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in filenames:
        destination = output_dir / name
        if destination.exists() and (not destination.is_file() or destination.is_symlink()):
            raise RuntimeError(f"existing publish target is not a regular file: {destination}")

    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}.r02-backup-", dir=output_dir.parent
    ) as backup_name:
        backup_dir = Path(backup_name)
        backed_up: list[str] = []
        published: list[str] = []
        try:
            for name in filenames:
                destination = output_dir / name
                if destination.exists():
                    os.replace(destination, backup_dir / name)
                    backed_up.append(name)
            for name in filenames:
                os.replace(staging_dir / name, output_dir / name)
                published.append(name)
        except Exception as publish_error:
            rollback_errors: list[str] = []
            for name in reversed(published):
                try:
                    (output_dir / name).unlink(missing_ok=True)
                except OSError as error:
                    rollback_errors.append(f"remove {name}: {error}")
            for name in reversed(backed_up):
                try:
                    os.replace(backup_dir / name, output_dir / name)
                except OSError as error:
                    rollback_errors.append(f"restore {name}: {error}")
            if not output_existed:
                try:
                    output_dir.rmdir()
                except OSError:
                    pass
            if rollback_errors:
                raise RuntimeError(
                    "publish failed and rollback was incomplete: "
                    + "; ".join(rollback_errors)
                ) from publish_error
            raise RuntimeError("atomic master publish failed; previous trio restored") from publish_error


def build_master_audio(
    beats_path: Path,
    binding_path: Path,
    output_dir: Path,
    condition: str = "A",
) -> dict[str, Any]:
    filenames = master_filenames(condition)
    beats, beats_hash = load_json_with_sha256(beats_path)
    binding, binding_hash = load_json_with_sha256(binding_path)
    story_plan = prepare_build_plan(beats, binding, condition)
    binding_id = binding["binding_id"]

    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"output path is not a directory: {output_dir}")

    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}.r02-stage-", dir=output_dir.parent
    ) as staging_name:
        staging_dir = Path(staging_name)
        master_wav = staging_dir / f"{MASTER_STEM}.working.wav"
        master_aiff = staging_dir / filenames["aiff"]
        master_m4a = staging_dir / filenames["m4a"]
        manifest_path = staging_dir / filenames["manifest"]

        pcm_buffer = array("h", [0]) * TOTAL_SAMPLES
        workout_manifest: list[dict[str, Any]] = []
        for index, (start_sec, role, text) in enumerate(WORKOUT_NAV_EVENTS, start=1):
            start = _number(start_sec, f"workout NAV event {index} timestamp")
            if role != "NAV" or not isinstance(text, str) or not text.strip():
                raise ValueError(f"workout NAV event {index} has invalid role or text")
            temp_wav = staging_dir / f"_temp_nav_{index:03d}.wav"
            samples, profile = _synthesize_samples(text, role, temp_wav)
            _mix_samples(pcm_buffer, start, samples, f"workout NAV event {index}")
            workout_manifest.append(
                {
                    "event_id": f"workout_nav_{index:03d}",
                    "timestamp_sec": start,
                    "duration_sec": round(len(samples) / SAMPLE_RATE, 6),
                    "voice": role,
                    "raw_text": text,
                    "text_sha256": text_sha256(text),
                    "synthesis_voice": profile["voice"],
                    "synthesis_rate": profile["rate"],
                }
            )

        cues_manifest: list[dict[str, Any]] = []
        for cue in story_plan:
            cue_samples: list[int] = []
            spoken_segments: list[dict[str, Any]] = []
            for segment_index, (segment_role, segment_text) in enumerate(
                cue["segments"], start=1
            ):
                temp_wav = staging_dir / (
                    f"_temp_{cue['cue_id']}_{segment_index:02d}_{segment_role}.wav"
                )
                segment_samples, profile = _synthesize_samples(
                    segment_text, segment_role, temp_wav
                )
                cue_samples.extend(segment_samples)
                spoken_segments.append(
                    {
                        "role": segment_role,
                        "text": segment_text,
                        "text_sha256": text_sha256(segment_text),
                        "synthesis_voice": profile["voice"],
                        "synthesis_rate": profile["rate"],
                    }
                )
            cue_duration_sec = len(cue_samples) / SAMPLE_RATE
            if cue_duration_sec > cue["max_spoken_sec"] + FLOAT_EPSILON:
                raise RuntimeError(
                    f"story cue {cue['cue_id']} duration {cue_duration_sec:.3f}s "
                    f"exceeds authored max_spoken_sec {cue['max_spoken_sec']:.3f}s"
                )
            _mix_samples(
                pcm_buffer,
                cue["timestamp_sec"],
                cue_samples,
                f"story cue {cue['cue_id']}",
            )
            cues_manifest.append(
                {
                    "cue_id": cue["cue_id"],
                    "node_id": cue["node_id"],
                    "timestamp_sec": cue["timestamp_sec"],
                    "duration_sec": round(cue_duration_sec, 6),
                    "max_spoken_sec": cue["max_spoken_sec"],
                    "voice": cue["voice"],
                    "text_sha256": cue["text_sha256"],
                    "raw_text": cue["raw_text"],
                    "spoken_segments": spoken_segments,
                }
            )

        validate_rendered_timeline(
            workout_manifest,
            cues_manifest,
            TARGET_DURATION_SEC,
        )

        with wave.open(str(master_wav), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(SAMPLE_RATE)
            if sys.byteorder != "little":
                pcm_buffer.byteswap()
            wav_file.writeframes(pcm_buffer.tobytes())

        convert_master_formats(master_wav, master_aiff, master_m4a)
        master_wav.unlink(missing_ok=True)

        duration_aiff = get_audio_duration_afinfo(master_aiff)
        duration_m4a = get_audio_duration_afinfo(master_m4a)
        for label, duration in (("AIFF", duration_aiff), ("M4A", duration_m4a)):
            if abs(duration - TARGET_DURATION_SEC) > DURATION_TOLERANCE_SEC:
                raise RuntimeError(
                    f"{label} duration validation failed: {duration}s, "
                    f"expected {TARGET_DURATION_SEC}s"
                )

        narrative_schedule = [
            {
                "cue_id": cue["cue_id"],
                "node_id": cue["node_id"],
                "timestamp_sec": cue["timestamp_sec"],
                "voice": cue["voice"],
            }
            for cue in cues_manifest
        ]
        manifest: dict[str, Any] = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "tool_schema": TOOL_SCHEMA,
            "mission_id": MISSION_ID,
            "title": "Solo Founder Narrative Run 30-Minute Master Audio",
            "concept_id": CONCEPT_ID,
            "condition": condition,
            "branch": BRANCH,
            "story_text_field": (
                "condition_a_text" if condition == "A" else "condition_b_text"
            ),
            "binding_id": binding_id,
            "binding_sha256": binding_hash,
            "beats_sha256": beats_hash,
            "sample_rate_hz": SAMPLE_RATE,
            "target_duration_sec": TARGET_DURATION_SEC,
            "actual_duration_aiff_sec": duration_aiff,
            "actual_duration_m4a_sec": duration_m4a,
            "aiff_sha256": compute_sha256(master_aiff),
            "m4a_sha256": compute_sha256(master_m4a),
            "aiff_file": master_aiff.name,
            "m4a_file": master_m4a.name,
            "workout_nav_events_count": len(workout_manifest),
            "workout_final_nav_timestamp_sec": workout_manifest[-1]["timestamp_sec"],
            "workout_nav_events_sha256": canonical_json_sha256(workout_manifest),
            "workout_nav_events": workout_manifest,
            "narrative_schedule_sha256": canonical_json_sha256(narrative_schedule),
            "narrative_cues": cues_manifest,
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False),
            encoding="utf-8",
        )

        publish_staged_files(
            staging_dir,
            output_dir,
            [filenames["aiff"], filenames["m4a"], filenames["manifest"]],
        )
        return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beats", type=Path, default=DEFAULT_BEATS)
    parser.add_argument(
        "--binding",
        type=Path,
        default=DEFAULT_BINDING if DEFAULT_BINDING.exists() else DEFAULT_FIXTURE_BINDING,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--condition", choices=["A", "B"], default="A")
    args = parser.parse_args(argv)

    try:
        manifest = build_master_audio(
            args.beats,
            args.binding,
            args.output_dir,
            condition=args.condition,
        )
        print(
            f"Master audio build SUCCESS [{manifest['condition']}]: "
            f"{manifest['m4a_file']} ({manifest['actual_duration_m4a_sec']}s)"
        )
        print(f"AIFF SHA-256: {manifest['aiff_sha256']}")
        print(f"M4A SHA-256:  {manifest['m4a_sha256']}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
