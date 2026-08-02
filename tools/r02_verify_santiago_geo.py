#!/usr/bin/env python3
"""Santiago OSM Geo Verification Script.

Queries the live OpenStreetMap API to verify that all candidate OSM IDs, types,
and names in the Santiago snapshot exist and match expected metadata.

Exits with return code 1 on any error or mismatch.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "research/r02/local/santiago_cumming/osm_snapshot.json"

EXPECTED_CANDIDATES = {
    "start_and_finish": {
        "osm_type": "node",
        "osm_id": 253281419,
        "name_substr": "Cumming"
    },
    "threshold": {
        "osm_type": "way",
        "osm_id": 592372641,
        "name_substr": "Palacio Álamos"
    },
    "witness": {
        "osm_type": "way",
        "osm_id": 180191510,
        "name_substr": "Basílica del Salvador"
    },
    "triangulation": {
        "osm_type": "way",
        "osm_id": 23389924,
        "name_substr": "Plaza Brasil"
    }
}


def verify_osm_object(osm_type: str, osm_id: int, expected_name_substr: str) -> bool:
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
            tags = elem.get("tags", {})
            name = tags.get("name", "")
            if expected_name_substr.lower() not in name.lower():
                print(f"FAIL: Expected name substring '{expected_name_substr}' in '{name}' for {osm_type}/{osm_id}", file=sys.stderr)
                return False
            print(f"OK: Verified {osm_type}/{osm_id} -> '{name}'")
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

    for role, spec in EXPECTED_CANDIDATES.items():
        cand = candidates.get(role, {})
        snap_type = cand.get("osm_type")
        snap_id = cand.get("osm_id")
        snap_name = cand.get("name", "")

        if snap_type != spec["osm_type"] or snap_id != spec["osm_id"]:
            print(f"FAIL: Snapshot mismatch for {role}: got {snap_type}/{snap_id}, expected {spec['osm_type']}/{spec['osm_id']}", file=sys.stderr)
            all_ok = False
            continue

        if spec["name_substr"].lower() not in snap_name.lower():
            print(f"FAIL: Snapshot name '{snap_name}' missing expected '{spec['name_substr']}'", file=sys.stderr)
            all_ok = False
            continue

        # Live OSM API query check
        if not verify_osm_object(spec["osm_type"], spec["osm_id"], spec["name_substr"]):
            all_ok = False

    if all_ok:
        print("Santiago Geo Verification: ALL 4 OSM OBJECTS VERIFIED ONLINE!")
        return 0
    else:
        print("Santiago Geo Verification: FAILED!", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
