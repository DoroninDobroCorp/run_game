#!/usr/bin/env python3
"""Boot the selected iPhone Simulator, install the built app and show its dashboard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APP = ROOT / "ios/RunGameFounder/DerivedData/Build/Products/Debug-iphonesimulator/RunGameFounder.app"


def launch(destination: str, bundle_id: str, app: Path) -> None:
    match = re.search(r"(?:^|,)id=([A-Fa-f0-9-]{36})(?:,|$)", destination)
    if match is None:
        raise ValueError("Use a Simulator destination containing its id (UDID)")
    if not app.is_dir():
        raise ValueError("Built app is missing; run make el-bolson-build first")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]+", bundle_id) is None:
        raise ValueError("Invalid bundle identifier")
    udid = match.group(1)
    result = subprocess.run(["xcrun", "simctl", "list", "devices", "available", "--json"],
                            check=True, capture_output=True, text=True, timeout=30)
    devices = [device for group in json.loads(result.stdout)["devices"].values() for device in group]
    device = next((d for d in devices if d["udid"].lower() == udid.lower()), None)
    if device is None:
        raise ValueError("Requested Simulator is not installed or available")
    if device["state"] != "Booted":
        subprocess.run(["xcrun", "simctl", "boot", udid], check=True, timeout=60)
    subprocess.run(["xcrun", "simctl", "bootstatus", udid, "-b"], check=True, timeout=300)
    subprocess.run(["open", "-a", "Simulator", "--args", "-CurrentDeviceUDID", udid], check=True, timeout=30)
    subprocess.run(["xcrun", "simctl", "install", udid, str(app)], check=True, timeout=120)
    # A freshly booted runtime can still be preparing its launch services after
    # bootstatus finishes. Keep the visible device open while that request waits.
    subprocess.run(["xcrun", "simctl", "launch", udid, bundle_id], check=True, timeout=180)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--bundle-id", default="com.doronindobro.rungame.founder")
    parser.add_argument("--app", type=Path, default=DEFAULT_APP)
    args = parser.parse_args()
    try:
        launch(args.destination, args.bundle_id, args.app)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
