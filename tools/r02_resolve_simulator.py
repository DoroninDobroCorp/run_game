#!/usr/bin/env python3
"""Resolve an available iPhone simulator destination for xcodebuild."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any

FALLBACK_DESTINATION = "platform=iOS Simulator,name=iPhone 16 Pro,OS=latest"


def _runtime_version(runtime: str) -> tuple[int, ...]:
    match = re.search(r"iOS[-.]([0-9.-]+)$", runtime)
    if match is None:
        return ()
    return tuple(int(part) for part in re.findall(r"\d+", match.group(1)))


def resolve_from_simctl(payload: dict[str, Any]) -> str | None:
    candidates: list[tuple[bool, tuple[int, ...], bool, str]] = []
    devices = payload.get("devices")
    if not isinstance(devices, dict):
        return None
    for runtime, runtime_devices in devices.items():
        if "iOS" not in runtime or not isinstance(runtime_devices, list):
            continue
        for device in runtime_devices:
            if not isinstance(device, dict) or device.get("isAvailable") is not True:
                continue
            name = device.get("name")
            udid = device.get("udid")
            if not isinstance(name, str) or not name.startswith("iPhone") or not isinstance(udid, str):
                continue
            candidates.append(
                (
                    device.get("state") == "Booted",
                    _runtime_version(runtime),
                    name == "iPhone 16 Pro",
                    udid,
                )
            )
    if not candidates:
        return None
    _, _, _, udid = max(candidates)
    return f"platform=iOS Simulator,id={udid}"


def resolve() -> str:
    try:
        result = subprocess.run(
            ["xcrun", "simctl", "list", "devices", "available", "--json"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode == 0:
            destination = resolve_from_simctl(json.loads(result.stdout))
            if destination is not None:
                return destination
    except (FileNotFoundError, json.JSONDecodeError, OSError, subprocess.TimeoutExpired):
        pass
    return FALLBACK_DESTINATION


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
