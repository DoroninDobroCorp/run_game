"""Offline walking geometry shared by fixture preparation and simulated runs.

Coordinates belong in ignored local fixtures, never in generated public reports.
"""

from __future__ import annotations

import math
from typing import Any


def distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1, lat2 = math.radians(a["latitude"]), math.radians(b["latitude"])
    dlat = lat2 - lat1
    dlon = math.radians(b["longitude"] - a["longitude"])
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6_371_000 * 2 * math.asin(math.sqrt(min(1, max(0, hav))))


def lengths(points: list[dict[str, Any]]) -> list[float]:
    result = [0.0]
    for a, b in zip(points, points[1:]):
        result.append(result[-1] + distance(a, b))
    return result


def point_at(points: list[dict[str, Any]], meters: float) -> dict[str, float]:
    cumulative = lengths(points)
    if not points or not math.isfinite(meters) or meters < 0 or meters > cumulative[-1] + 0.001:
        raise ValueError("Distance must lie on a non-empty geometry")
    for i in range(1, len(points)):
        if cumulative[i] >= meters and cumulative[i] > cumulative[i - 1]:
            fraction = (meters - cumulative[i - 1]) / (cumulative[i] - cumulative[i - 1])
            return {
                key: round(points[i - 1][key] + fraction * (points[i][key] - points[i - 1][key]), 7)
                for key in ("latitude", "longitude")
            }
    return {key: points[-1][key] for key in ("latitude", "longitude")}


def validate_route(route: Any, waypoints: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(route, dict):
        raise ValueError("offline_route must be an object")
    if set(route) != {"coordinates", "waypointIndices", "source", "attribution", "note"}:
        raise ValueError("offline_route has missing or unknown fields")
    for key in ("source", "attribution", "note"):
        if not isinstance(route[key], str) or not route[key].strip():
            raise ValueError(f"offline_route.{key} must be non-empty text")
    points = route["coordinates"]
    if not isinstance(points, list) or not 5 <= len(points) <= 10_000:
        raise ValueError("offline_route needs 5–10000 coordinates")
    for point in points:
        if not isinstance(point, dict) or set(point) != {"latitude", "longitude"}:
            raise ValueError("offline_route coordinate must contain latitude and longitude")
        for key, bound in (("latitude", 90), ("longitude", 180)):
            value = point[key]
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or abs(value) > bound:
                raise ValueError(f"offline_route contains invalid {key}")
    indices = route["waypointIndices"]
    if not isinstance(indices, list) or len(waypoints) < 2 or len(indices) != len(waypoints):
        raise ValueError("offline_route requires one geometry index per waypoint")
    if any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(points) for i in indices):
        raise ValueError("offline_route waypoint index is invalid")
    if indices[0] != 0 or indices[-1] != len(points) - 1 or any(a >= b for a, b in zip(indices, indices[1:])):
        raise ValueError("offline_route waypoint indices must increase from start to finish")
    if any(distance(points[i], waypoint) > 10 for i, waypoint in zip(indices, waypoints)):
        raise ValueError("offline_route geometry does not visit each waypoint in order")
    if distance(points[0], points[-1]) > 25:
        raise ValueError("offline_route must return to its start")
    if any(distance(a, b) > 500 for a, b in zip(points, points[1:])):
        raise ValueError("offline_route contains a gap longer than 500 m")
    if not 200 <= lengths(points)[-1] <= 20_000:
        raise ValueError("offline_route length must be between 200 m and 20 km")
    return route
