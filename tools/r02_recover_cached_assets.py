#!/usr/bin/env python3
"""Preserve a verified *partial* private R02 asset recovery from an app bundle.

This tool is deliberately conservative. It can recover only an M4A and its
audio manifest when they already exist in a local installed app, and records
that the binding, OSM snapshot and AIFF still require the authoritative private
bundle. It never creates or substitutes those three files.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

r02_doctor = importlib.import_module("tools.r02_doctor" if __package__ else "r02_doctor")


M4A_NAME = "m01_solo_founder_30min.m4a"
MANIFEST_NAME = "m01_solo_founder_30min.manifest.json"
STATUS_NAME = "RECOVERY_STATUS.json"
UNRECOVERED_AUTHORITATIVE_FILES = (
    "current.binding.json",
    "osm_snapshot.json",
    "audio/m01_solo_founder_30min.aiff",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, dict):
        raise ValueError("Cached audio manifest must be a JSON object")
    if payload.get("schema_version") != "0.1":
        raise ValueError("Cached audio manifest has unsupported schema_version")
    if payload.get("m4a_file") != M4A_NAME:
        raise ValueError("Cached audio manifest names an unexpected M4A")
    if payload.get("m4a_sha256") != r02_doctor.EXPECTED_MASTER_SHA256:
        raise ValueError("Cached audio manifest does not declare the accepted M4A hash")
    return payload


def recover(audio_source: Path, manifest_source: Path, output_dir: Path) -> dict[str, Any]:
    """Copy the two verified cached files into a new, explicitly partial bundle."""
    if output_dir.exists():
        raise FileExistsError(
            f"Refusing to overwrite recovery directory: {output_dir}. Choose a new empty path."
        )
    if audio_source.name != M4A_NAME or manifest_source.name != MANIFEST_NAME:
        raise ValueError("Source filenames must retain the canonical R02 M4A and manifest names")
    if not audio_source.is_file() or not manifest_source.is_file():
        raise FileNotFoundError("Both cached M4A and cached manifest must be regular files")

    actual_sha = sha256(audio_source)
    if actual_sha != r02_doctor.EXPECTED_MASTER_SHA256:
        raise ValueError("Cached M4A hash does not match the accepted production hash")
    manifest = load_manifest(manifest_source)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.stage-", dir=output_dir.parent))
    try:
        shutil.copy2(audio_source, stage / M4A_NAME)
        shutil.copy2(manifest_source, stage / MANIFEST_NAME)
        status = {
            "artifact": "r02-cached-asset-recovery",
            "schema_version": "0.1",
            "status": "UNVERIFIED_PARTIAL_RECOVERY",
            "recovered_files": [M4A_NAME, MANIFEST_NAME],
            "m4a_sha256": actual_sha,
            "manifest_m4a_sha256": manifest["m4a_sha256"],
            "authoritative_files_still_required": list(UNRECOVERED_AUTHORITATIVE_FILES),
            "safe_next_step": "Obtain the original private bundle; do not use this directory as a release fixture.",
        }
        (stage / STATUS_NAME).write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(stage, output_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-source", type=Path, required=True)
    parser.add_argument("--manifest-source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    status = recover(args.audio_source, args.manifest_source, args.output_dir)
    print(
        "Recovered verified M4A + manifest as UNVERIFIED_PARTIAL_RECOVERY; "
        f"still missing {len(status['authoritative_files_still_required'])} authoritative files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
