#!/usr/bin/env python3
"""Offline integrity preflight for the active R02 founder device-smoke bundle.

The highest status this command can emit is READY_FOR_DEVICE_SMOKE. It never
approves route safety, workout suitability, participant export, or an M1-A run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import r02_prepare_ios, r02_story  # noqa: E402

DEFAULT_FIXTURE = r02_prepare_ios.DEFAULT_FIXTURE
DEFAULT_IOS_RESOURCES = r02_prepare_ios.DEFAULT_OUTPUT

FIELD_BLOCKERS = r02_prepare_ios.REQUIRED_FIELD_REVIEW_KEYS


def _check(checks: list[dict[str, Any]], check_id: str, ok: bool, detail: str) -> None:
    checks.append({"id": check_id, "ok": bool(ok), "detail": detail})


def _path_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return f"<external>/{path.name}"


def _redact_paths(value: str, fixture_dir: Path, ios_resources_dir: Path) -> str:
    replacements = (
        (str(fixture_dir.resolve()), "<fixture>"),
        (str(ios_resources_dir.resolve()), "<ios_resources>"),
        (str(ROOT.resolve()), "<repo>"),
    )
    result = value
    for source, replacement in sorted(replacements, key=lambda item: -len(item[0])):
        result = result.replace(source, replacement)
    return result


def _human_blockers(
    binding: dict[str, Any] | None
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    if binding is None:
        return [
            {
                "code": "binding_unavailable",
                "path": "current.binding.json",
                "message": "A human-review binding is unavailable.",
            }
        ]

    for field in ("human_route_approved", "workout_approved", "human_approved"):
        if binding.get(field) is not True:
            blockers.append(
                {
                    "code": "human_approval_missing",
                    "path": f"binding.{field}",
                    "message": f"{field}=true requires a real human walk-through/review.",
                }
            )
    if binding.get("public_start") is not True:
        blockers.append(
            {
                "code": "public_start_missing",
                "path": "binding.public_start",
                "message": "M1-A requires a manually confirmed public start.",
            }
        )

    slots = binding.get("slots", {})
    if isinstance(slots, dict):
        for slot_id in r02_prepare_ios.REQUIRED_BINDING_SLOTS:
            slot = slots.get(slot_id)
            if not isinstance(slot, dict) or slot.get("human_approved") is not True:
                blockers.append(
                    {
                        "code": "slot_approval_missing",
                        "path": f"binding.slots.{slot_id}.human_approved",
                        "message": f"Geo slot '{slot_id}' still needs human approval.",
                    }
                )

    metadata = binding.get("provisional_route_metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    for field in FIELD_BLOCKERS:
        value = metadata.get(field)
        if value is None or value == "" or value == []:
            blockers.append(
                {
                    "code": "field_measurement_missing",
                    "path": f"binding.provisional_route_metadata.{field}",
                    "message": f"Field measurement/review '{field}' is still missing.",
                }
            )
    return blockers


def preflight(fixture_dir: Path, ios_resources_dir: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    hashes: dict[str, str] = {}
    binding: dict[str, Any] | None = None
    graph: dict[str, Any] | None = None
    validated: dict[str, Any] | None = None

    try:
        graph = r02_story.load_json(r02_story.DEFAULT_GRAPH)
        graph_summary = r02_story.validate_graph(graph)
        _check(
            checks,
            "canonical_graph_valid",
            True,
            f"{_path_label(r02_story.DEFAULT_GRAPH)} / {graph_summary['nodes']} nodes",
        )
    except Exception as exc:
        errors.append(f"canonical_graph: {exc}")
        _check(checks, "canonical_graph_valid", False, str(exc))
        graph = None

    binding_path = fixture_dir / "current.binding.json"
    try:
        binding = r02_prepare_ios.load_json(binding_path)
    except Exception as exc:
        errors.append(f"binding: {exc}")

    if binding is not None and graph is not None:
        try:
            r02_story.validate_binding(binding, participant=False, graph=graph)
            _check(
                checks,
                "binding_graph_contract",
                True,
                "binding has the exact M1 slot/archetype contract",
            )
        except r02_story.ValidationError as exc:
            errors.extend(f"binding_contract: {message}" for message in exc.errors)
            _check(checks, "binding_graph_contract", False, "; ".join(exc.errors))

    try:
        validated = r02_prepare_ios.validate_fixture(fixture_dir)
        mission = validated["mission"]
        binding = validated["binding"]
        _check(
            checks,
            "fixture_integrity",
            True,
            "binding/snapshot/source refs/audio SHA/duration are internally consistent",
        )
        hashes.update(
            {
                "audio_sha256": mission["audioSHA256"],
                "binding_sha256": mission["bindingSHA256"],
                "binding_contract_sha256": mission["bindingContractSHA256"],
                "snapshot_sha256": mission["snapshotSHA256"],
                "audio_manifest_sha256": mission["audioManifestSHA256"],
                "route_sha256": mission["routeSHA256"],
                "timeline_sha256": mission["timelineSHA256"],
            }
        )
    except Exception as exc:
        errors.append(f"fixture_integrity: {exc}")
        _check(checks, "fixture_integrity", False, str(exc))

    if validated is not None:
        expected_mission = validated["mission"]
        if graph is not None:
            try:
                choices = r02_story.load_json(r02_story.DEFAULT_CHOICES)
                linearized = r02_story.linearize_graph(
                    graph, choices, stop_mission=r02_prepare_ios.EXPECTED_MISSION_ID
                )
                expected_nodes = [item["node_id"] for item in linearized["path"]]
                actual_nodes = [
                    cue.get("node_id")
                    for cue in validated["manifest"]["narrative_cues"]
                ]
                expected_branch = f"atlas_disclosure={choices['atlas_disclosure']}"
                provenance_ok = (
                    actual_nodes == expected_nodes
                    and validated["manifest"].get("branch") == expected_branch
                )
                _check(
                    checks,
                    "audio_story_provenance",
                    provenance_ok,
                    "manifest cue nodes and branch match the canonical M1 linearization",
                )
                if not provenance_ok:
                    errors.append("audio_manifest: story branch/cue provenance mismatch")
            except Exception as exc:
                errors.append(f"audio_manifest_provenance: {exc}")
                _check(checks, "audio_story_provenance", False, str(exc))

        expected_names = {
            "mission.json",
            r02_prepare_ios.EXPECTED_M4A_FILE,
            r02_prepare_ios.EXPECTED_MANIFEST_FILE,
        }
        if not ios_resources_dir.is_dir():
            errors.append(f"ios_resources: directory not found ({ios_resources_dir})")
            _check(checks, "ios_resource_inventory", False, "directory missing")
        else:
            actual_names = {path.name for path in ios_resources_dir.iterdir()}
            inventory_ok = actual_names == expected_names
            _check(
                checks,
                "ios_resource_inventory",
                inventory_ok,
                f"expected={sorted(expected_names)}, actual={sorted(actual_names)}",
            )
            if not inventory_ok:
                errors.append("ios_resources: resource inventory is missing or stale")

            mission_path = ios_resources_dir / "mission.json"
            ios_audio_path = ios_resources_dir / r02_prepare_ios.EXPECTED_M4A_FILE
            ios_manifest_path = (
                ios_resources_dir / r02_prepare_ios.EXPECTED_MANIFEST_FILE
            )
            try:
                actual_mission = r02_prepare_ios.load_json(mission_path)
                mission_match = actual_mission == expected_mission
                _check(
                    checks,
                    "ios_mission_matches_fixture",
                    mission_match,
                    "prepared mission equals the currently validated fixture projection",
                )
                if not mission_match:
                    errors.append("ios_mission: prepared mission.json is stale")

                route_hash = r02_prepare_ios.canonical_json_sha256(
                    actual_mission.get("routePoints")
                )
                timeline_hash = r02_prepare_ios.canonical_json_sha256(
                    actual_mission.get("timeline")
                )
                route_hash_ok = (
                    actual_mission.get("routeSHA256") == route_hash
                    and route_hash == expected_mission["routeSHA256"]
                )
                timeline_hash_ok = (
                    actual_mission.get("timelineSHA256") == timeline_hash
                    and timeline_hash == expected_mission["timelineSHA256"]
                )
                expected_initial_approval = r02_prepare_ios.complete_human_approval(
                    validated["binding"]
                )
                approvals_ok = (
                    actual_mission.get("routeInitiallyApproved")
                    is expected_initial_approval
                    and actual_mission.get("workoutInitiallyApproved")
                    is expected_initial_approval
                    and actual_mission.get("m1HumanApprovalComplete")
                    is expected_initial_approval
                )
                _check(checks, "route_hash", route_hash_ok, route_hash)
                _check(checks, "timeline_hash", timeline_hash_ok, timeline_hash)
                _check(
                    checks,
                    "recorded_approval_projection",
                    approvals_ok,
                    "initial approval requires every human flag, slot approval, and field review; preflight grants none",
                )
                if not route_hash_ok:
                    errors.append("ios_mission: route hash mismatch")
                if not timeline_hash_ok:
                    errors.append("ios_mission: timeline hash mismatch")
                if not approvals_ok:
                    errors.append("ios_mission: approval projection mismatch")
            except Exception as exc:
                errors.append(f"ios_mission: {exc}")
                _check(checks, "ios_mission_matches_fixture", False, str(exc))

            try:
                audio_sha = r02_prepare_ios.compute_sha256(ios_audio_path)
                audio_ok = audio_sha == expected_mission["audioSHA256"]
                _check(checks, "ios_audio_sha256", audio_ok, audio_sha)
                if not audio_ok:
                    errors.append("ios_audio: SHA-256 mismatch")
            except Exception as exc:
                errors.append(f"ios_audio: {exc}")
                _check(checks, "ios_audio_sha256", False, str(exc))

            try:
                manifest_sha = r02_prepare_ios.compute_sha256(ios_manifest_path)
                manifest_ok = manifest_sha == expected_mission["audioManifestSHA256"]
                _check(checks, "ios_audio_manifest_sha256", manifest_ok, manifest_sha)
                if not manifest_ok:
                    errors.append("ios_audio_manifest: SHA-256 mismatch")
            except Exception as exc:
                errors.append(f"ios_audio_manifest: {exc}")
                _check(checks, "ios_audio_manifest_sha256", False, str(exc))

    blockers = _human_blockers(binding)
    status = "READY_FOR_DEVICE_SMOKE" if not errors else "NOT_READY_FOR_DEVICE_SMOKE"
    sanitized_checks = [
        {
            **check,
            "detail": _redact_paths(str(check["detail"]), fixture_dir, ios_resources_dir),
        }
        for check in checks
    ]
    sanitized_errors = [
        _redact_paths(error, fixture_dir, ios_resources_dir) for error in errors
    ]
    return {
        "schema_version": "0.1",
        "tool": "r02_preflight",
        "mode": "offline_no_network",
        "status": status,
        "scope": {
            "device_smoke_only": True,
            "preflight_grants_route_safety_approval": False,
            "preflight_grants_workout_approval": False,
            "preflight_grants_m1_a_approval": False,
        },
        "fixture_dir": _path_label(fixture_dir),
        "ios_resources_dir": _path_label(ios_resources_dir),
        "checks": sanitized_checks,
        "errors": sanitized_errors,
        "artifact_hashes": hashes,
        "human_blockers_to_m1_a": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument(
        "--ios-resources-dir", type=Path, default=DEFAULT_IOS_RESOURCES
    )
    args = parser.parse_args(argv)
    result = preflight(args.fixture_dir, args.ios_resources_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "READY_FOR_DEVICE_SMOKE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
