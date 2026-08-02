#!/usr/bin/env python3
"""Opt-in field verification tool for local R02 master audio assets.

This tool validates local master audio files (m01_solo_founder_30min.m4a/.aiff)
against their manifest, checking duration via afinfo/ffprobe, verifying SHA-256
checksums, and ensuring final NAV completion occurs before 1800.0s.

MUST return exit code 1 if manifest or master audio files are missing or invalid.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIO_DIR = ROOT / "research/r02/local/santiago_cumming/audio"


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
        raise RuntimeError(f"afinfo failed on {path.name}: {res.stderr}")
    match = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", res.stdout)
    if match:
        return float(match.group(1))
    raise RuntimeError(f"Could not parse duration from afinfo for {path.name}")


def verify_audio_dir(audio_dir: Path) -> int:
    manifest_path = audio_dir / "m01_solo_founder_30min.manifest.json"

    if not manifest_path.exists():
        print(f"ERROR: Field verification manifest not found ({manifest_path})", file=sys.stderr)
        return 1

    with manifest_path.open("r", encoding="utf-8") as f:
        manifest = json.load(f)

    aiff_file = audio_dir / manifest.get("aiff_file", "m01_solo_founder_30min.aiff")
    m4a_file = audio_dir / manifest.get("m4a_file", "m01_solo_founder_30min.m4a")

    if not aiff_file.exists() or not m4a_file.exists():
        print(f"ERROR: Local master audio files missing in {audio_dir}", file=sys.stderr)
        return 1

    # 1. Duration check
    dur_aiff = get_audio_duration_afinfo(aiff_file)
    dur_m4a = get_audio_duration_afinfo(m4a_file)

    if not (1799.5 <= dur_aiff <= 1800.5):
        print(f"ERROR: AIFF duration {dur_aiff}s is not within 1800.0s bound", file=sys.stderr)
        return 1

    if not (1799.5 <= dur_m4a <= 1800.5):
        print(f"ERROR: M4A duration {dur_m4a}s is not within 1800.0s bound", file=sys.stderr)
        return 1

    # 2. SHA-256 Hash check
    sha_aiff = compute_sha256(aiff_file)
    sha_m4a = compute_sha256(m4a_file)

    if sha_aiff != manifest.get("aiff_sha256"):
        print(f"ERROR: AIFF SHA-256 mismatch!\nComputed: {sha_aiff}\nManifest: {manifest.get('aiff_sha256')}", file=sys.stderr)
        return 1

    if sha_m4a != manifest.get("m4a_sha256"):
        print(f"ERROR: M4A SHA-256 mismatch!\nComputed: {sha_m4a}\nManifest: {manifest.get('m4a_sha256')}", file=sys.stderr)
        return 1

    # 3. Final NAV timestamp check
    final_nav = manifest.get("workout_final_nav_timestamp_sec", 0)
    if not (1790.0 <= final_nav <= 1795.0):
        print(f"ERROR: Final NAV timestamp {final_nav}s is not in safe 1790-1795s range", file=sys.stderr)
        return 1

    print("Field verification PASSED:")
    print(f"  AIFF File: {aiff_file.name} ({dur_aiff:.2f}s, SHA: {sha_aiff})")
    print(f"  M4A File:  {m4a_file.name} ({dur_m4a:.2f}s, SHA: {sha_m4a})")
    print(f"  Final NAV Event: {final_nav}s (completes before 1800.0s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR)
    args = parser.parse_args()
    return verify_audio_dir(args.audio_dir)


if __name__ == "__main__":
    sys.exit(main())
