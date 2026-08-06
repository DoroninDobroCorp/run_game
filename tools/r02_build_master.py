#!/usr/bin/env python3
"""Build a 30-minute master audio file for Solo Founder Narrative Run.

This script synthesizes clean spoken audio (stripping speaker prefixes and
stage directions in brackets) using distinct voice profiles for NAV, ATLAS,
and LEA. It builds a single 1800.0s timeline with exact PCM sample placement
and generates the audio manifest with SHA-256 checksums.
"""

from __future__ import annotations

import argparse
from array import array
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BEATS = ROOT / "research/r02/mission_01_beats.v0.1.json"
DEFAULT_LOCAL_DIR = ROOT / "research/r02/local/valparaiso_central"
DEFAULT_BINDING = DEFAULT_LOCAL_DIR / "current.binding.json"
DEFAULT_FIXTURE_BINDING = ROOT / "research/r02/fixtures/field_binding.example.json"
DEFAULT_OUTPUT_DIR = DEFAULT_LOCAL_DIR / "audio"

SAMPLE_RATE = 44100
TARGET_DURATION_SEC = 1800.0
TOTAL_SAMPLES = int(TARGET_DURATION_SEC * SAMPLE_RATE)

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
    (1792.0, "NAV", "Тренировка завершена. Продолжайте спокойную ходьбу, если это необходимо.")
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
    "m01_c010": 1650.0
}

# Voice configurations for macOS say
VOICE_SPECS = {
    "NAV": {"voice": "Milena", "rate": "185"},
    "ATLAS": {"voice": "Yuri", "fallback_voice": "Milena", "rate": "150"},
    "LEA": {"voice": "Milena", "rate": "170"}
}


def load_json(p: Path) -> dict:
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def bind_text(text: str, binding: dict) -> str:
    slots = binding.get("slots", {})
    for slot_id, slot in slots.items():
        text = text.replace("{" + slot_id + ".name}", slot.get("name", f"[{slot_id}]"))
    return text


def parse_dialogue_segments(text: str) -> list[tuple[str, str]]:
    """Parse dialogue text into (voice_role, cleaned_spoken_text) segments.

    Strips bracketed stage directions like [короткая помеха] and speaker prefixes.
    """
    # Remove stage directions inside brackets
    clean_raw = re.sub(r"\[[^\]]+\]", "", text).strip()

    # Split by speaker labels like NAV:, ЛЕА:, АТЛАС:, ЛЕА, почти неслышно:
    pattern = r"(NAV|АТЛАС|ЛЕА)(?:,\s*[^:]+)?:?"
    tokens = re.split(pattern, clean_raw)

    segments = []
    if len(tokens) == 1:
        text_clean = tokens[0].strip()
        if text_clean:
            segments.append(("LEA", text_clean))
        return segments

    idx = 1
    while idx < len(tokens):
        speaker_raw = tokens[idx].strip()
        speech = tokens[idx + 1].strip() if (idx + 1) < len(tokens) else ""
        speech = re.sub(r"^\s*:\s*", "", speech).strip()
        if speech:
            role = "NAV" if speaker_raw == "NAV" else ("ATLAS" if speaker_raw == "АТЛАС" else "LEA")
            segments.append((role, speech))
        idx += 2

    return segments


def tts_segment_to_wav(text: str, voice_role: str, out_wav_path: Path):
    spec = VOICE_SPECS.get(voice_role, VOICE_SPECS["LEA"])
    voice_name = spec.get("voice", "Milena")
    rate = spec.get("rate", "175")

    temp_aiff = out_wav_path.with_suffix(".aiff")
    cmd_say = ["say", "-v", voice_name, "-r", rate, "-o", str(temp_aiff), text]
    res = subprocess.run(cmd_say, capture_output=True, text=True)
    if res.returncode != 0 and "fallback_voice" in spec:
        voice_name = spec["fallback_voice"]
        cmd_say = ["say", "-v", voice_name, "-r", rate, "-o", str(temp_aiff), text]
        res = subprocess.run(cmd_say, capture_output=True, text=True)

    if res.returncode != 0:
        raise RuntimeError(f"say failed for role {voice_role} ({text!r}): {res.stderr}")

    cmd_conv = [
        "afconvert", "-f", "WAVE", "-c", "1", "-d", "LEI16@44100", str(temp_aiff), str(out_wav_path)
    ]
    res_conv = subprocess.run(cmd_conv, capture_output=True, text=True)
    if temp_aiff.exists():
        temp_aiff.unlink()
    if res_conv.returncode != 0:
        raise RuntimeError(f"afconvert failed: {res_conv.stderr}")


def read_wav_pcm(path: Path) -> list[int]:
    with wave.open(str(path), "rb") as wf:
        n_frames = wf.getnframes()
        data = wf.readframes(n_frames)
        return list(struct.unpack(f"<{n_frames}h", data))


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_audio_duration_afinfo(path: Path) -> float:
    cmd = ["afinfo", str(path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"afinfo failed: {res.stderr}")
    match = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", res.stdout)
    if match:
        return float(match.group(1))
    raise RuntimeError(f"Could not parse duration from afinfo output:\n{res.stdout}")


def build_master_audio(beats_path: Path, binding_path: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    beats = load_json(beats_path)
    binding = load_json(binding_path)

    master_aiff = output_dir / "m01_solo_founder_30min.aiff"
    master_m4a = output_dir / "m01_solo_founder_30min.m4a"
    manifest_path = output_dir / "m01_solo_founder_30min.manifest.json"

    # A Python list of 79M integer objects consumes multiple gigabytes. A signed
    # 16-bit array matches the output format and keeps the 30-minute buffer near
    # its actual PCM size (~159 MB).
    pcm_buffer = array("h", [0]) * TOTAL_SAMPLES
    cues_manifest = []

    # 1. Workout NAV Events
    for start_sec, role, text in WORKOUT_NAV_EVENTS:
        temp_wav = output_dir / f"_temp_nav_{int(start_sec)}.wav"
        tts_segment_to_wav(text, role, temp_wav)
        samples = read_wav_pcm(temp_wav)
        temp_wav.unlink()

        start_sample = int(start_sec * SAMPLE_RATE)
        for i, s in enumerate(samples):
            idx = start_sample + i
            if idx < TOTAL_SAMPLES:
                pcm_buffer[idx] = max(-32768, min(32767, pcm_buffer[idx] + s))

    # 2. Story Cues
    story_cues = {cue["cue_id"]: cue for cue in beats.get("cues", [])}
    for cue_id, start_sec in STORY_CUE_TIMESTAMPS.items():
        cue = story_cues.get(cue_id)
        if not cue:
            raise RuntimeError(f"Missing cue card for {cue_id}")

        bound_text = bind_text(cue["condition_a_text"], binding)
        segments = parse_dialogue_segments(bound_text)

        cue_samples: list[int] = []
        for seg_role, seg_text in segments:
            temp_wav = output_dir / f"_temp_{cue_id}_{seg_role}.wav"
            tts_segment_to_wav(seg_text, seg_role, temp_wav)
            seg_samples = read_wav_pcm(temp_wav)
            temp_wav.unlink()
            cue_samples.extend(seg_samples)

        duration_sec = round(len(cue_samples) / SAMPLE_RATE, 2)
        start_sample = int(start_sec * SAMPLE_RATE)

        for i, s in enumerate(cue_samples):
            idx = start_sample + i
            if idx < TOTAL_SAMPLES:
                pcm_buffer[idx] = max(-32768, min(32767, pcm_buffer[idx] + s))

        cues_manifest.append({
            "cue_id": cue_id,
            "node_id": cue["node_id"],
            "timestamp_sec": start_sec,
            "duration_sec": duration_sec,
            "voice": cue["voice"],
            "raw_text": bound_text,
            "spoken_segments": [{"role": r, "text": t} for r, t in segments]
        })

    # 3. Export Master WAV file
    master_wav = output_dir / "m01_solo_founder_30min.wav"
    with wave.open(str(master_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        if sys.byteorder != "little":
            pcm_buffer.byteswap()
        wf.writeframes(pcm_buffer.tobytes())

    # 4. Convert master WAV to AIFF and M4A
    cmd_aiff = ["afconvert", "-f", "AIFF", "-c", "1", "-d", "BEI16@44100", str(master_wav), str(master_aiff)]
    subprocess.run(cmd_aiff, check=True, capture_output=True)

    cmd_m4a = ["ffmpeg", "-y", "-i", str(master_wav), "-c:a", "aac", "-b:a", "192k", str(master_m4a)]
    subprocess.run(cmd_m4a, check=True, capture_output=True)

    if master_wav.exists():
        master_wav.unlink()

    # 5. Validation
    dur_aiff = get_audio_duration_afinfo(master_aiff)
    dur_m4a = get_audio_duration_afinfo(master_m4a)

    if not (1799.5 <= dur_aiff <= 1800.5) or not (1799.5 <= dur_m4a <= 1800.5):
        raise RuntimeError(f"Duration validation failed: AIFF={dur_aiff}s, M4A={dur_m4a}s")

    # 6. Manifest
    manifest = {
        "schema_version": "0.1",
        "mission_id": "m01",
        "title": "Solo Founder Narrative Run 30-Minute Master Audio",
        "concept_id": "null_layer",
        "branch": "atlas_disclosure=concealed",
        "target_duration_sec": 1800.0,
        "actual_duration_aiff_sec": dur_aiff,
        "actual_duration_m4a_sec": dur_m4a,
        "aiff_sha256": compute_sha256(master_aiff),
        "m4a_sha256": compute_sha256(master_m4a),
        "aiff_file": master_aiff.name,
        "m4a_file": master_m4a.name,
        "workout_nav_events_count": len(WORKOUT_NAV_EVENTS),
        "workout_final_nav_timestamp_sec": 1792.0,
        "narrative_cues": cues_manifest
    }

    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beats", type=Path, default=DEFAULT_BEATS)
    parser.add_argument(
        "--binding",
        type=Path,
        default=DEFAULT_BINDING if DEFAULT_BINDING.exists() else DEFAULT_FIXTURE_BINDING,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    try:
        manifest = build_master_audio(args.beats, args.binding, args.output_dir)
        print(f"Master audio build SUCCESS: {manifest['m4a_file']} ({manifest['actual_duration_m4a_sec']}s)")
        print(f"AIFF SHA-256: {manifest['aiff_sha256']}")
        print(f"M4A SHA-256:  {manifest['m4a_sha256']}")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
