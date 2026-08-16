#!/usr/bin/env python3
"""Create or verify the private R02 tester handoff inventory.

The manifest contains hashes and relative names only. It never packages or
uploads private route/audio assets; transport encryption remains a human gate.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "research/r02/local/valparaiso_central"
EXPECTED_FILES = (
    "current.binding.json",
    "osm_snapshot.json",
    "audio/m01_solo_founder_30min.aiff",
    "audio/m01_solo_founder_30min.m4a",
    "audio/m01_solo_founder_30min.manifest.json",
)
r02_prepare_ios = importlib.import_module(
    "tools.r02_prepare_ios" if __package__ else "r02_prepare_ios"
)
r02_doctor = importlib.import_module(
    "tools.r02_doctor" if __package__ else "r02_doctor"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(64 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _release_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=10,
        check=True,
    )
    commit = result.stdout.strip()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("Could not resolve a full release commit SHA")
    return commit


def _ensure_clean_worktree() -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=10,
        check=True,
    )
    if result.stdout.strip():
        raise ValueError("Refusing to create a release manifest from a dirty Git worktree")


def inspect_fixture(fixture_dir: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for relative_name in EXPECTED_FILES:
        path = fixture_dir / relative_name
        if path.is_symlink():
            raise ValueError(f"Handoff file must not be a symlink: {relative_name}")
        if not path.is_file():
            raise FileNotFoundError(f"Missing handoff file: {relative_name}")
        files.append(
            {
                "path": relative_name,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    return files


def create_manifest(fixture_dir: Path, release_commit: str | None = None) -> dict[str, Any]:
    r02_prepare_ios.validate_fixture(fixture_dir)
    files = inspect_fixture(fixture_dir)
    m4a_entry = next(
        entry for entry in files if entry["path"] == "audio/m01_solo_founder_30min.m4a"
    )
    if m4a_entry["sha256"] != r02_doctor.EXPECTED_MASTER_SHA256:
        raise ValueError(
            "M4A does not match accepted release SHA-256: "
            f"{m4a_entry['sha256']} != {r02_doctor.EXPECTED_MASTER_SHA256}"
        )
    if release_commit is None:
        _ensure_clean_worktree()
    commit = release_commit or _release_commit()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("release_commit must be a full lowercase 40-character Git SHA")
    return {
        "schema_version": "0.1",
        "artifact": "r02-private-tester-handoff",
        "release_commit": commit,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "accepted_m4a_sha256": r02_doctor.EXPECTED_MASTER_SHA256,
        "transport_encryption_verified": False,
        "files": files,
    }


def write_manifest(manifest: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f".{output.name}.",
        dir=output.parent,
        delete=False,
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, output)


def verify_manifest(
    fixture_dir: Path,
    manifest_path: Path,
    expected_release_commit: str | None = None,
) -> dict[str, Any]:
    manifest = r02_prepare_ios.load_json(manifest_path)
    if manifest.get("schema_version") != "0.1" or manifest.get("artifact") != "r02-private-tester-handoff":
        raise ValueError("Unsupported handoff manifest schema/artifact")
    release_commit = manifest.get("release_commit")
    if not isinstance(release_commit, str) or re.fullmatch(r"[0-9a-f]{40}", release_commit) is None:
        raise ValueError("Handoff manifest release_commit is invalid")
    current_commit = expected_release_commit or _release_commit()
    if release_commit != current_commit:
        raise ValueError(
            "Handoff manifest release_commit does not match checked-out HEAD: "
            f"{release_commit} != {current_commit}"
        )
    expected_entries = manifest.get("files")
    if not isinstance(expected_entries, list):
        raise ValueError("Handoff manifest files must be an array")
    actual_entries = inspect_fixture(fixture_dir)
    if expected_entries != actual_entries:
        raise ValueError("Handoff asset inventory/hash mismatch")
    if manifest.get("accepted_m4a_sha256") != r02_doctor.EXPECTED_MASTER_SHA256:
        raise ValueError("Handoff manifest accepted M4A hash is stale")
    r02_prepare_ios.validate_fixture(fixture_dir)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE)
    create_parser.add_argument("--out", type=Path, required=True)
    create_parser.add_argument("--release-commit")
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE)
    verify_parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            manifest = create_manifest(args.fixture_dir, args.release_commit)
            write_manifest(manifest, args.out)
            print(f"R02 handoff manifest created: {args.out}")
        else:
            manifest = verify_manifest(args.fixture_dir, args.manifest)
            print(
                "R02 handoff manifest verified: "
                f"{manifest['release_commit']} / {len(manifest['files'])} private files"
            )
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
