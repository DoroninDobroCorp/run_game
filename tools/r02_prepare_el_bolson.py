#!/usr/bin/env python3
"""Prepare the El Bolsón test loop from a cached public OSM street network.

Start is the distance midpoint of Avenida Patagonia Argentina. The loop uses
connected OSM ways, never straight-line shortcuts or the nearby Ruta 40.
No human approvals, measured elevations, or field observations are invented.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import sys
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

geometry = importlib.import_module("tools.route_geometry" if __package__ else "route_geometry")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "research/r02/local/el_bolson"
AVENUE = 143070262
LOOP_WAYS = (AVENUE, 188346742, 250578255, 251613088, 188346745, AVENUE)
OSM = "https://www.openstreetmap.org"


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "RunGameFounder/1.0 (local route preparation)"})
    with urllib.request.urlopen(request, timeout=45) as response:
        result = json.load(response)
    if not isinstance(result, dict) or not isinstance(result.get("elements"), list):
        raise ValueError("OSM returned no elements")
    return result


def download_map() -> dict[str, Any]:
    avenue = fetch_json(f"https://api.openstreetmap.org/api/0.6/way/{AVENUE}/full.json")
    nodes = {x["id"]: x for x in avenue["elements"] if x["type"] == "node"}
    way = next(x for x in avenue["elements"] if x["type"] == "way" and x["id"] == AVENUE)
    points = [dict(latitude=nodes[n]["lat"], longitude=nodes[n]["lon"]) for n in way["nodes"]]
    midpoint = geometry.point_at(points, geometry.lengths(points)[-1] / 2)
    lat, lon = midpoint["latitude"], midpoint["longitude"]
    bbox = f"{lon - .018},{lat - .014},{lon + .018},{lat + .014}"
    return fetch_json(f"https://api.openstreetmap.org/api/0.6/map.json?bbox={bbox}")


def build_fixture(osm_map: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    nodes = {x["id"]: x for x in osm_map["elements"] if x["type"] == "node"}
    ways = {x["id"]: x for x in osm_map["elements"] if x["type"] == "way"}
    for way_id in set(LOOP_WAYS):
        way = ways.get(way_id)
        if way is None:
            raise ValueError(f"OSM snapshot is missing way {way_id}")
        tags = way.get("tags", {})
        if tags.get("highway") not in {"tertiary", "residential", "unclassified", "footway", "pedestrian", "path", "living_street"}:
            raise ValueError(f"Way {way_id} is not a supported walking street")
        if tags.get("foot") in {"no", "private"} or tags.get("access") in {"no", "private"} or tags.get("construction"):
            raise ValueError(f"Way {way_id} has access/construction restrictions")
        if any(node not in nodes for node in way["nodes"]):
            raise ValueError(f"Missing nodes for way {way_id}")
    if ways[AVENUE].get("tags", {}).get("name") != "Avenida Patagonia Argentina":
        raise ValueError("The starting avenue identity has changed; review the OSM source")

    def coord(node_id: int) -> dict[str, float]:
        node = nodes[node_id]
        return {"latitude": float(node["lat"]), "longitude": float(node["lon"])}

    def shared(a: int, b: int) -> int:
        matches = set(ways[a]["nodes"]) & set(ways[b]["nodes"])
        if len(matches) != 1:
            raise ValueError(f"Ways {a} and {b} need one unambiguous intersection")
        return matches.pop()

    avenue_nodes = ways[AVENUE]["nodes"]
    avenue_points = [coord(n) for n in avenue_nodes]
    cumulative = geometry.lengths(avenue_points)
    midpoint_distance = cumulative[-1] / 2
    start = geometry.point_at(avenue_points, midpoint_distance)
    split = next(i for i in range(1, len(cumulative)) if cumulative[i] >= midpoint_distance)
    junctions = [shared(a, b) for a, b in zip(LOOP_WAYS, LOOP_WAYS[1:])]
    first_index, last_index = avenue_nodes.index(junctions[0]), avenue_nodes.index(junctions[-1])
    if not last_index < split <= first_index:
        raise ValueError("The route no longer surrounds the avenue midpoint")
    route = [start] + [coord(n) for n in avenue_nodes[split:first_index + 1]]
    junction_indices = [len(route) - 1]
    for way_id, entrance, exit_node in zip(LOOP_WAYS[1:-1], junctions, junctions[1:]):
        sequence = ways[way_id]["nodes"]
        a, b = sequence.index(entrance), sequence.index(exit_node)
        segment = sequence[a:b + 1] if a <= b else list(reversed(sequence[b:a + 1]))
        route.extend(coord(n) for n in segment[1:])
        junction_indices.append(len(route) - 1)
    route.extend(coord(n) for n in avenue_nodes[last_index + 1:split])
    route.append(start.copy())
    # Landmark roles are actual junctions; no buildings or historical facts are invented.
    roles = ("start_and_finish", "threshold", "witness", "triangulation")
    names = (
        "Середина Avenida Patagonia Argentina",
        "поворот с Патагония Аргентина на Лос Гиндос",
        "перекрёсток Куйен и Лос Гиндос",
        "развилки Лос Гиндос и Пукара",
    )
    selected_indices = [0, junction_indices[0], junction_indices[2], junction_indices[3]]
    selected_ids = [AVENUE, junctions[0], junctions[2], junctions[3]]
    candidates: dict[str, Any] = {}
    for role, name, index, osm_id in zip(roles, names, selected_indices, selected_ids):
        osm_type = "way" if role == "start_and_finish" else "node"
        candidates[role] = {
            "name": name, "osm_type": osm_type, "osm_id": osm_id,
            "osm_url": f"{OSM}/{osm_type}/{osm_id}", **route[index],
        }
    offline_route = {
        "coordinates": route,
        "waypointIndices": selected_indices + [len(route) - 1],
        "source": f"{OSM}/way/{AVENUE}",
        "attribution": "© OpenStreetMap contributors · ODbL 1.0",
        "note": "Тестовый круг: Patagonia Argentina → Los Guindos → Cuyén → Los Guindos → Pucará → старт. Геометрия сохранена офлайн; покрытие и переходы ещё требуют дневного обхода.",
    }
    geometry.validate_route(offline_route, [candidates[r] for r in roles] + [candidates[roles[0]]])
    snapshot = {
        "schema_version": "0.1", "city": "El Bolsón, Río Negro, Argentina",
        "fixture_metadata": {"display_name": "Эль-Больсон · Патагония", "gpx_prefix": "el-bolson-patagonia-argentina"},
        "osm_candidates": candidates, "offline_route": offline_route,
        "source_way_ids": list(dict.fromkeys(LOOP_WAYS)),
        "start_method": "Half of the mapped avenue length, interpolated along its geometry",
        "avenue_length_meters": round(cumulative[-1], 2),
        "planned_loop_length_meters": round(geometry.lengths(route)[-1], 2),
        "field_verified": False,
    }
    binding = {
        "schema_version": "0.1", "binding_id": "el_bolson_patagonia_argentina_m01_v1",
        "research_mode": "traveler_fixture", "product_model": "home_territory",
        "city_alias": "el_bolson", "route_id": "el-bolson-patagonia-argentina",
        "public_start": False, "human_route_approved": False, "workout_approved": False, "human_approved": False,
        "slots": {
            role: {"name": candidates[role]["name"], "archetype": "path_transition" if role == "threshold" else "junction",
                   "visible_attributes": ["Street junction mapped by OpenStreetMap; not field-verified"],
                   "source_refs": [candidates[role]["osm_url"]],
                   "operator_trigger": "После безопасного прохода перекрёстка; не ускоряться ради аудиореплики.",
                   "human_approved": False}
            for role in roles[1:]
        },
        "provisional_route_metadata": {
            "start_and_finish_name": names[0], "source_ref": candidates[roles[0]]["osm_url"],
            "measured_loop_length_meters": None, "measured_elevation_gain_meters": None,
            "poi_leg_distances_meters": None, "expected_poi_arrival_cue_sec": None,
            "route_surface_notes": None, "crossing_notes": None,
            "daylight_walkthrough_completed_at_local": None,
        },
        "evidence_limits": ["Map-derived test route, not field approval.", "Fixed-time story cues require arrival-time review before a physical mission."],
    }
    return binding, snapshot


def planned_gpx(snapshot: dict[str, Any]) -> bytes:
    """Export a planned route (<rte>), never a recorded track (<trk>)."""
    namespace = "http://www.topografix.com/GPX/1/1"
    ET.register_namespace("", namespace)
    root = ET.Element(f"{{{namespace}}}gpx", version="1.1", creator="Run Game route planner")
    route = ET.SubElement(root, "rte")
    ET.SubElement(route, "name").text = "El Bolsón — Avenida Patagonia Argentina — planned test loop"
    ET.SubElement(route, "desc").text = "OSM-derived plan, not a recorded run or field approval. © OpenStreetMap contributors, ODbL 1.0."
    for point in snapshot["offline_route"]["coordinates"]:
        ET.SubElement(route, "rtept", lat=f"{point['latitude']:.7f}", lon=f"{point['longitude']:.7f}")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--osm-map", type=Path, help="Cached OSM /map.json export; avoids network requests")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        for name in ("current.binding.json", "osm_snapshot.json", "source.osm.json", "planned-route.gpx"):
            if (args.output_dir / name).exists():
                raise ValueError("Fixture already exists; use a new output directory to preserve reviews")
        osm_map = json.loads(args.osm_map.read_text()) if args.osm_map else download_map()
        binding, snapshot = build_fixture(osm_map)
        snapshot["prepared_at_utc"] = datetime.now(timezone.utc).isoformat()
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, value in (("current.binding.json", binding), ("osm_snapshot.json", snapshot), ("source.osm.json", osm_map)):
            (args.output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (args.output_dir / "planned-route.gpx").write_bytes(planned_gpx(snapshot))
        print(f"El Bolsón fixture prepared: {snapshot['planned_loop_length_meters']} m; start at avenue midpoint; human approvals remain false.")
        return 0
    except (OSError, ValueError, KeyError, StopIteration) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
