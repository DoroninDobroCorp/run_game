#!/usr/bin/env python3
"""Verify the active R02 field fixture against the live OpenStreetMap API.

Candidate types, IDs, and names come from the local privacy-sensitive snapshot,
so switching the founder's city does not require another city-specific script.
The command exits with status 1 on a missing role, malformed candidate, network
error, or live type/ID/name mismatch.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "research/r02/local/valparaiso_central/osm_snapshot.json"
REQUIRED_ROLES = ("start_and_finish", "threshold", "witness", "triangulation")


def verify_osm_object(osm_type: str, osm_id: int, expected_name: str) -> bool:
    url = f"https://api.openstreetmap.org/api/0.6/{osm_type}/{osm_id}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "RunGame-GeoVerifier/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                print(f"FAIL: HTTP status {resp.status} for {osm_type}/{osm_id}", file=sys.stderr)
                return False
            data = json.loads(resp.read().decode("utf-8"))
            elements = data.get("elements", [])
            if not elements:
                print(f"FAIL: No elements returned for {osm_type}/{osm_id}", file=sys.stderr)
                return False
            elem = elements[0]
            if elem.get("type") != osm_type or elem.get("id") != osm_id:
                print(f"FAIL: Type/ID mismatch for {osm_type}/{osm_id}", file=sys.stderr)
                return False
            live_name = elem.get("tags", {}).get("name", "")
            if expected_name.casefold() not in live_name.casefold():
                print(
                    f"FAIL: Expected name '{expected_name}' in '{live_name}' "
                    f"for {osm_type}/{osm_id}",
                    file=sys.stderr,
                )
                return False
            print(f"OK: Verified {osm_type}/{osm_id} -> '{live_name}'")
            return True
    except Exception as exc:
        print(f"FAIL: Exception fetching {osm_type}/{osm_id}: {exc}", file=sys.stderr)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    args = parser.parse_args()

    if not args.snapshot.exists():
        print(f"FAIL: Snapshot file not found ({args.snapshot})", file=sys.stderr)
        return 1

    with args.snapshot.open("r", encoding="utf-8") as f:
        snapshot = json.load(f)

    candidates = snapshot.get("osm_candidates", {})
    all_ok = True
    for role in REQUIRED_ROLES:
        candidate = candidates.get(role)
        if not isinstance(candidate, dict):
            print(f"FAIL: Missing OSM candidate for role '{role}'", file=sys.stderr)
            all_ok = False
            continue

        osm_type = candidate.get("osm_type")
        osm_id = candidate.get("osm_id")
        name = candidate.get("name")
        if osm_type not in {"node", "way", "relation"} or not isinstance(osm_id, int) or not name:
            print(f"FAIL: Malformed OSM candidate for role '{role}'", file=sys.stderr)
            all_ok = False
            continue

        if not verify_osm_object(osm_type, osm_id, name):
            all_ok = False

    city = snapshot.get("city", "Active fixture")
    if all_ok:
        print(f"{city} Geo Verification: ALL 4 OSM OBJECTS VERIFIED ONLINE!")
        return 0

    print(f"{city} Geo Verification: FAILED!", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
