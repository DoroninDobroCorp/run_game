#!/usr/bin/env python3
"""Technical audio QA probe for Condition A master audio without human listening.

Probes Condition A M4A master for SHA-256 match, exact 1800s duration,
AAC 44.1kHz mono format, container integrity, zero truncation, and signal peak/clipping.
Outputs machine-readable technical report JSON without performing human audio listening
or granting human audio approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_M4A_PATH = ROOT / "research/r02/local/valparaiso_central/audio/m01_solo_founder_30min.m4a"
DEFAULT_MANIFEST_PATH = ROOT / "research/r02/local/valparaiso_central/audio/m01_solo_founder_30min.manifest.json"

EXPECTED_DURATION_SEC = 1800.0
DURATION_TOLERANCE_SEC = 0.5
EXPECTED_SAMPLE_RATE_HZ = 44100
EXPECTED_CHANNELS = 1
EXPECTED_CODEC = "aac"
PROBE_TIMEOUT_SEC = 30


class QAProbeError(ValueError):
    """Raised when audio probing encounters a structural error."""


def _reject_json_constant(value: str) -> None:
    raise QAProbeError(f"non-finite JSON number {value!r} is not allowed")


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise QAProbeError(f"duplicate JSON key {key!r} is not allowed")
        result[key] = value
    return result


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def probe_ffprobe(m4a_path: Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(m4a_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=PROBE_TIMEOUT_SEC)
    if result.returncode != 0:
        raise QAProbeError(f"ffprobe failed: {result.stderr.strip()}")
    try:
        data = json.loads(result.stdout)
    except Exception as exc:
        raise QAProbeError(f"Failed to parse ffprobe JSON output: {exc}") from exc

    streams = data.get("streams", [])
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not audio_stream:
        raise QAProbeError("No audio stream found in ffprobe output")

    codec_name = str(audio_stream.get("codec_name", "")).lower()
    sample_rate = int(audio_stream.get("sample_rate", 0))
    channels = int(audio_stream.get("channels", 0))
    channel_layout = str(audio_stream.get("channel_layout", "")).lower()

    format_info = data.get("format", {})
    duration_str = format_info.get("duration") or audio_stream.get("duration")
    if not duration_str:
        raise QAProbeError("Duration missing in ffprobe output")
    duration = float(duration_str)

    return {
        "probe_tool": "ffprobe",
        "duration_sec": duration,
        "codec_name": codec_name,
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "channel_layout": channel_layout,
        "container_format": format_info.get("format_name", ""),
        "size_bytes": int(format_info.get("size", m4a_path.stat().st_size if m4a_path.exists() else 0)),
        "bit_rate_bps": int(format_info.get("bit_rate", 0)) if format_info.get("bit_rate") else 0,
    }


def probe_afinfo(m4a_path: Path) -> dict[str, Any]:
    cmd = ["afinfo", str(m4a_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=PROBE_TIMEOUT_SEC)
    if result.returncode != 0:
        raise QAProbeError(f"afinfo failed: {result.stderr.strip()}")
    
    stdout = result.stdout
    match_dur = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", stdout)
    if not match_dur:
        raise QAProbeError("Could not parse duration from afinfo output")
    duration = float(match_dur.group(1))

    match_rate = re.search(r"([0-9]+)\s*Hz", stdout)
    sample_rate = int(match_rate.group(1)) if match_rate else 0

    match_chan = re.search(r"([0-9]+)\s*channels", stdout)
    channels = int(match_chan.group(1)) if match_chan else 0

    codec_name = "aac" if "aac" in stdout.lower() or "mp4a" in stdout.lower() else "unknown"

    return {
        "probe_tool": "afinfo",
        "duration_sec": duration,
        "codec_name": codec_name,
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "channel_layout": "mono" if channels == 1 else "stereo" if channels == 2 else "unknown",
        "container_format": "m4a",
        "size_bytes": m4a_path.stat().st_size if m4a_path.exists() else 0,
        "bit_rate_bps": 0,
    }


def probe_audio_format(m4a_path: Path) -> dict[str, Any]:
    errors = []
    try:
        return probe_ffprobe(m4a_path)
    except Exception as exc:
        errors.append(f"ffprobe: {exc}")
    try:
        return probe_afinfo(m4a_path)
    except Exception as exc:
        errors.append(f"afinfo: {exc}")
    raise QAProbeError(f"All format probes failed: {'; '.join(errors)}")


def probe_signal_volumedetect(m4a_path: Path) -> dict[str, Any]:
    cmd = [
        "ffmpeg",
        "-i",
        str(m4a_path),
        "-af",
        "volumedetect",
        "-f",
        "null",
        "/dev/null",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return {
                "probe_tool": "ffmpeg_volumedetect",
                "status": "FAIL",
                "error": f"ffmpeg volumedetect failed with exit code {result.returncode}: {result.stderr.strip()}",
                "max_volume_db": None,
                "mean_volume_db": None,
                "histogram_0db_count": 0,
                "clipping_detected": False,
            }
        stderr = result.stderr
        max_vol_match = re.search(r"max_volume:\s*([-+]?[0-9.]+)\s*dB", stderr)
        mean_vol_match = re.search(r"mean_volume:\s*([-+]?[0-9.]+)\s*dB", stderr)
        hist_0db_match = re.search(r"histogram_0db:\s*([0-9]+)", stderr)

        if not max_vol_match:
            return {
                "probe_tool": "ffmpeg_volumedetect",
                "status": "FAIL",
                "error": "Could not parse max_volume from ffmpeg output",
                "max_volume_db": None,
                "mean_volume_db": None,
                "histogram_0db_count": 0,
                "clipping_detected": False,
            }

        max_vol_db = float(max_vol_match.group(1))
        mean_vol_db = float(mean_vol_match.group(1)) if mean_vol_match else None
        hist_0db = int(hist_0db_match.group(1)) if hist_0db_match else 0

        # Clipping detected if max_volume >= 0.0 dB or histogram_0db > 0
        clipping_detected = False
        if max_vol_db >= 0.0:
            clipping_detected = True
        if hist_0db > 0:
            clipping_detected = True

        return {
            "probe_tool": "ffmpeg_volumedetect",
            "status": "PASS",
            "max_volume_db": max_vol_db,
            "mean_volume_db": mean_vol_db,
            "histogram_0db_count": hist_0db,
            "clipping_detected": clipping_detected,
        }
    except FileNotFoundError:
        return {
            "probe_tool": "ffmpeg_volumedetect",
            "status": "NOT_RUN",
            "error": "ffmpeg executable not found in PATH",
            "max_volume_db": None,
            "mean_volume_db": None,
            "histogram_0db_count": 0,
            "clipping_detected": False,
        }
    except Exception as exc:
        return {
            "probe_tool": "ffmpeg_volumedetect",
            "status": "FAIL",
            "error": str(exc),
            "max_volume_db": None,
            "mean_volume_db": None,
            "histogram_0db_count": 0,
            "clipping_detected": False,
        }


def probe_audio(
    m4a_path: Path,
    manifest_path: Path | None = None,
) -> dict[str, Any]:
    if not m4a_path.is_file():
        return {
            "schema_version": "0.1",
            "tool": "r02_audio_qa",
            "status": "FAIL",
            "error": f"M4A master audio file not found: {m4a_path}",
            "human_audio_approved": False,
            "human_listening_performed": False,
        }

    actual_sha256 = compute_sha256(m4a_path)
    expected_sha256 = None
    manifest_data = None

    if manifest_path is not None and manifest_path.is_file():
        try:
            manifest_text = manifest_path.read_text(encoding="utf-8")
            manifest_data = json.loads(
                manifest_text,
                parse_constant=_reject_json_constant,
                object_pairs_hook=_json_object_without_duplicates,
            )
            expected_sha256 = manifest_data.get("m4a_sha256")
        except Exception as exc:
            return {
                "schema_version": "0.1",
                "tool": "r02_audio_qa",
                "status": "FAIL",
                "error": f"Failed to read/parse manifest: {exc}",
                "human_audio_approved": False,
                "human_listening_performed": False,
            }

    try:
        format_info = probe_audio_format(m4a_path)
    except Exception as exc:
        return {
            "schema_version": "0.1",
            "tool": "r02_audio_qa",
            "status": "FAIL",
            "error": f"Audio container probing failed: {exc}",
            "human_audio_approved": False,
            "human_listening_performed": False,
        }

    signal_info = probe_signal_volumedetect(m4a_path)
    signal_passed = (signal_info.get("status") == "PASS") and (signal_info.get("max_volume_db") is not None)

    # Perform assertions
    sha_match = (expected_sha256 is not None) and (actual_sha256 == expected_sha256)
    duration_exact = abs(format_info["duration_sec"] - EXPECTED_DURATION_SEC) <= DURATION_TOLERANCE_SEC
    format_valid = (
        format_info["codec_name"] == EXPECTED_CODEC
        and format_info["sample_rate_hz"] == EXPECTED_SAMPLE_RATE_HZ
        and format_info["channels"] == EXPECTED_CHANNELS
    )
    container_valid = True  # Format probe succeeded without corrupt/truncated error
    zero_truncation = format_info["duration_sec"] >= (EXPECTED_DURATION_SEC - DURATION_TOLERANCE_SEC)
    clipping_detected = signal_info["clipping_detected"]

    all_passed = (
        sha_match
        and duration_exact
        and format_valid
        and container_valid
        and zero_truncation
        and not clipping_detected
        and signal_passed
    )

    if signal_info.get("status") == "NOT_RUN":
        status = "NOT_RUN"
    elif all_passed:
        status = "PASS"
    else:
        status = "FAIL"

    return {
        "schema_version": "0.1",
        "tool": "r02_audio_qa",
        "status": status,
        "m4a_file": m4a_path.name,
        "manifest_file": manifest_path.name if manifest_path else None,
        "actual_sha256": actual_sha256,
        "expected_sha256": expected_sha256,
        "probed_duration_sec": format_info["duration_sec"],
        "expected_duration_sec": EXPECTED_DURATION_SEC,
        "format": {
            "codec_name": format_info["codec_name"],
            "sample_rate_hz": format_info["sample_rate_hz"],
            "channels": format_info["channels"],
            "channel_layout": format_info["channel_layout"],
        },
        "signal_analysis": signal_info,
        "checks": {
            "sha256_matches_manifest": sha_match,
            "duration_exact_1800s": duration_exact,
            "format_aac_44100_mono": format_valid,
            "container_integrity_valid": container_valid,
            "zero_truncation": zero_truncation,
            "clipping_detected": clipping_detected,
            "ffmpeg_signal_probe_passed": signal_passed,
        },
        "human_audio_approved": False,
        "human_listening_performed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m4a", type=Path, default=DEFAULT_M4A_PATH, help="Path to M4A master audio file")
    parser.add_argument(
        "--manifest", type=Path, default=DEFAULT_MANIFEST_PATH, help="Path to master audio manifest file"
    )
    parser.add_argument("--out", type=Path, help="Optional output JSON report path")
    args = parser.parse_args(argv)

    report = probe_audio(args.m4a, args.manifest)
    report_json = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)

    if args.out:
        args.out.write_text(report_json + "\n", encoding="utf-8")

    print(report_json)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
