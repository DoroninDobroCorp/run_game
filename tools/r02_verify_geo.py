#!/usr/bin/env python3
"""Verify the active R02 field fixture against the live OpenStreetMap API.

Candidate types, IDs, source names and junction memberships come from the local
snapshot. Translated display labels are not treated as OpenStreetMap names.
The command exits with status 1 on a missing role, malformed candidate, network
error, or live type/ID/name mismatch.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "research/r02/local/el_bolson/osm_snapshot.json"
REQUIRED_ROLES = ("start_and_finish", "threshold", "witness", "triangulation")


def fetch_osm_object(osm_type: str, osm_id: int) -> dict[str, Any]:
    url = f"https://api.openstreetmap.org/api/0.6/{osm_type}/{osm_id}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "RunGame-GeoVerifier/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)
    if not isinstance(data, dict) or not isinstance(data.get("elements"), list):
        raise ValueError(f"Malformed OSM response for {osm_type}/{osm_id}")
    matches = [element for element in data["elements"] if isinstance(element, dict)
               and element.get("type") == osm_type and element.get("id") == osm_id]
    if len(matches) != 1:
        raise ValueError(f"Missing or ambiguous type/ID for {osm_type}/{osm_id}")
    return matches[0]


def verify_osm_object(osm_type: str, osm_id: int, expected_name: str | None,
                      connected_way_ids: list[int] | None = None) -> bool:
    try:
        elem = fetch_osm_object(osm_type, osm_id)
        if expected_name is not None:
            if not isinstance(expected_name, str) or not expected_name.strip():
                raise ValueError("OSM source name must be nonempty")
            live_name = elem.get("tags", {}).get("name", "")
            if not isinstance(live_name, str) or expected_name.casefold() not in live_name.casefold():
                raise ValueError(f"Source name mismatch for {osm_type}/{osm_id}")
        else:
            # An unnamed junction is verified by its membership in two mapped
            # streets, never by accepting an empty name match.
            if (osm_type != "node" or not isinstance(connected_way_ids, list)
                    or len(connected_way_ids) < 2
                    or any(type(way_id) is not int or way_id <= 0 for way_id in connected_way_ids)
                    or len(set(connected_way_ids)) != len(connected_way_ids)):
                raise ValueError("Unnamed junction needs at least two distinct OSM way IDs")
            for way_id in connected_way_ids:
                way = fetch_osm_object("way", way_id)
                if osm_id not in way.get("nodes", []):
                    raise ValueError(f"Junction node/{osm_id} is no longer connected to way/{way_id}")
        print(f"OK: Verified {osm_type}/{osm_id}")
        return True
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(f"FAIL: Exception fetching {osm_type}/{osm_id}: {exc}", file=sys.stderr)
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    args = parser.parse_args(argv)

    if not args.snapshot.exists():
        print(f"FAIL: Snapshot file not found ({args.snapshot})", file=sys.stderr)
        return 1

    try:
        with args.snapshot.open("r", encoding="utf-8") as f:
            snapshot = json.load(f)
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("osm_candidates"), dict):
            raise ValueError("Snapshot must contain an osm_candidates object")
    except (OSError, ValueError) as exc:
        print(f"FAIL: Cannot read snapshot: {exc}", file=sys.stderr)
        return 1

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
        name = candidate.get("osm_name", candidate.get("name"))
        if (osm_type not in ("node", "way", "relation") or type(osm_id) is not int or osm_id <= 0
                or (name is not None and (not isinstance(name, str) or not name.strip()))):
            print(f"FAIL: Malformed OSM candidate for role '{role}'", file=sys.stderr)
            all_ok = False
            continue

        if not verify_osm_object(osm_type, osm_id, name, candidate.get("osm_way_ids")):
            all_ok = False

    city = snapshot.get("city", "Active fixture")
    if all_ok:
        print(f"{city} Geo Verification: ALL 4 OSM OBJECTS VERIFIED ONLINE (not field approval).")
        return 0

    print(f"{city} Geo Verification: FAILED!", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
