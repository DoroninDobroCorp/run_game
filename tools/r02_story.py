#!/usr/bin/env python3
"""Validate and linearize the R02 authored narrative graph.

This is intentionally a standard-library research tool, not a production story
runtime. It proves that the braided authoring graph is coherent and can be
compiled into one deterministic Wizard-of-Oz path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPH = ROOT / "research/r02/narrative_graph.v0.1.json"
DEFAULT_BEATS = ROOT / "research/r02/mission_01_beats.v0.1.json"
DEFAULT_CHOICES = ROOT / "research/r02/fixtures/choices.example.json"
DEFAULT_BINDING = ROOT / "research/r02/fixtures/field_binding.example.json"
DEFAULT_SCORECARD = ROOT / "research/r02/tournament/scorecard.json"

TERMINAL_KINDS = {"ending"}
PRIVATE_FIELD_NAMES = {
    "lat",
    "latitude",
    "lon",
    "lng",
    "longitude",
    "coordinates",
    "exact_start",
    "exact_end",
    "raw_trace",
    "gpx",
}


class ValidationError(ValueError):
    """Raised when one or more authored-contract checks fail."""

    def __init__(self, errors: Iterable[str]):
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


def _json_constant_error(value: str) -> None:
    raise ValidationError([f"non-finite JSON number {value!r} is not allowed"])


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError([f"duplicate JSON key {key!r} is not allowed"])
        result[key] = value
    return result


def load_json(path: Path | str) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(
            handle,
            parse_constant=_json_constant_error,
            object_pairs_hook=_json_object_without_duplicates,
        )
    if not isinstance(value, dict):
        raise ValidationError([f"{path}: top-level JSON value must be an object"])
    return value


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def checksum(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _duplicates(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def _node_maps(graph: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    nodes = {node["id"]: node for node in graph.get("nodes", []) if "id" in node}
    outgoing: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in nodes}
    for edge in graph.get("edges", []):
        if edge.get("from") in outgoing:
            outgoing[edge["from"]].append(edge)
    return nodes, outgoing


def _validate_state_value(
    state_schema: dict[str, Any], state_id: str, value: Any, context: str, errors: list[str]
) -> None:
    definition = state_schema.get(state_id)
    if definition is None:
        errors.append(f"{context}: undeclared state '{state_id}'")
        return
    if definition.get("type") == "enum" and value not in definition.get("values", []):
        errors.append(
            f"{context}: value {value!r} is not allowed for state '{state_id}'"
        )


def validate_graph(graph: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    required = {
        "schema_version",
        "concept_id",
        "title",
        "product_scope",
        "runner_contract",
        "companion",
        "state_schema",
        "missions",
        "central_reveal",
        "nodes",
        "edges",
    }
    missing = sorted(required - graph.keys())
    if missing:
        errors.append(f"graph: missing required fields: {', '.join(missing)}")

    node_list = graph.get("nodes", [])
    edge_list = graph.get("edges", [])
    mission_list = graph.get("missions", [])
    state_schema = graph.get("state_schema", {})

    if len(state_schema) > 5:
        errors.append("graph: R02 graph may declare at most five state variables")

    for collection_name, values in (
        ("node", [item.get("id") for item in node_list]),
        ("edge", [item.get("id") for item in edge_list]),
        ("mission", [item.get("id") for item in mission_list]),
    ):
        if any(value is None for value in values):
            errors.append(f"graph: every {collection_name} requires an id")
        duplicates = _duplicates(value for value in values if value is not None)
        if duplicates:
            errors.append(
                f"graph: duplicate {collection_name} ids: {', '.join(sorted(duplicates))}"
            )

    nodes, outgoing = _node_maps(graph)
    mission_ids = {mission.get("id") for mission in mission_list}

    for state_id, definition in state_schema.items():
        if definition.get("type") != "enum":
            errors.append(f"state '{state_id}': only enum is supported in R02 v0.1")
            continue
        values = definition.get("values", [])
        if not values or len(values) != len(set(values)):
            errors.append(f"state '{state_id}': values must be non-empty and unique")
        if definition.get("initial") not in values:
            errors.append(f"state '{state_id}': initial value is not declared")

    for node in node_list:
        node_id = node.get("id", "<missing>")
        kind = node.get("kind")
        if node.get("mission_id") not in mission_ids:
            errors.append(f"node '{node_id}': unknown mission_id")
        if kind not in {"scene", "choice", "gate", "mission_end", "ending"}:
            errors.append(f"node '{node_id}': unsupported kind {kind!r}")
        if not node.get("dramatic_function"):
            errors.append(f"node '{node_id}': missing dramatic_function")
        if not node.get("relationship_change"):
            errors.append(f"node '{node_id}': missing relationship_change")
        runner_action = node.get("runner_action", {})
        if "causally_required" not in runner_action:
            errors.append(f"node '{node_id}': runner_action must declare causally_required")
        if "failure_fallback_preserves_canon" not in runner_action:
            errors.append(
                f"node '{node_id}': runner_action must declare failure fallback behavior"
            )
        if node.get("geo_slot") and not node["geo_slot"].get("fallback_summary"):
            errors.append(f"node '{node_id}': geo_slot requires an authored fallback")

        edges = outgoing.get(node_id, [])
        if kind in TERMINAL_KINDS:
            if edges:
                errors.append(f"node '{node_id}': ending must not have outgoing edges")
        elif not edges:
            errors.append(f"node '{node_id}': non-terminal node has no outgoing edge")

        if kind == "choice":
            choice_id = node.get("choice_id")
            raw_options = node.get("options", [])
            if not isinstance(raw_options, list) or any(
                not isinstance(option, str) for option in raw_options
            ):
                errors.append(f"node '{node_id}': options must be an array of strings")
                options: list[str] = []
            else:
                options = raw_options
            if choice_id not in state_schema:
                errors.append(f"node '{node_id}': choice_id is not declared state")
            explicit = [edge for edge in edges if not edge.get("fallback")]
            fallback = [edge for edge in edges if edge.get("fallback")]
            if len(fallback) != 1:
                errors.append(f"node '{node_id}': choice requires exactly one fallback edge")
            edge_options: list[str] = []
            for edge in explicit:
                option = edge.get("option")
                if not isinstance(option, str):
                    errors.append(
                        f"edge '{edge.get('id')}': explicit choice option must be a string"
                    )
                else:
                    edge_options.append(option)
            if sorted(edge_options) != sorted(options):
                errors.append(
                    f"node '{node_id}': explicit edge options do not match authored options"
                )
            if node.get("authored_fallback") not in options:
                errors.append(f"node '{node_id}': authored_fallback must be an option")
            for edge in edges:
                if edge.get("choice_id") != choice_id:
                    errors.append(f"edge '{edge.get('id')}': wrong choice_id")
        elif kind == "gate":
            if any(not edge.get("requires") for edge in edges):
                errors.append(f"node '{node_id}': every gate edge requires state predicates")
        elif kind not in TERMINAL_KINDS and len(edges) != 1:
            errors.append(
                f"node '{node_id}': deterministic scene/end requires exactly one outgoing edge"
            )

    for edge in edge_list:
        edge_id = edge.get("id", "<missing>")
        if edge.get("from") not in nodes:
            errors.append(f"edge '{edge_id}': dangling from node {edge.get('from')!r}")
        if edge.get("to") not in nodes:
            errors.append(f"edge '{edge_id}': dangling to node {edge.get('to')!r}")
        for state_id, value in edge.get("requires", {}).items():
            _validate_state_value(state_schema, state_id, value, f"edge '{edge_id}' requires", errors)
        for state_id, value in edge.get("effects", {}).items():
            _validate_state_value(state_schema, state_id, value, f"edge '{edge_id}' effects", errors)

    for state_id in state_schema:
        writers = [edge for edge in edge_list if state_id in edge.get("effects", {})]
        readers = [edge for edge in edge_list if state_id in edge.get("requires", {})]
        if not writers:
            errors.append(f"state '{state_id}': never written")
            continue
        writes_only_to_endings = all(
            nodes.get(edge.get("to"), {}).get("kind") == "ending" for edge in writers
        )
        if not readers and not writes_only_to_endings:
            errors.append(
                f"state '{state_id}': written but never read by a later authored gate"
            )

    if mission_list:
        start = mission_list[0].get("entry_node")
        if start not in nodes:
            errors.append("graph: first mission entry node does not exist")
        else:
            reachable: set[str] = set()
            stack = [start]
            while stack:
                current = stack.pop()
                if current in reachable:
                    continue
                reachable.add(current)
                stack.extend(
                    edge["to"]
                    for edge in outgoing.get(current, [])
                    if edge.get("to") in nodes
                )
            unreachable = sorted(set(nodes) - reachable)
            if unreachable:
                errors.append(f"graph: unreachable nodes: {', '.join(unreachable)}")

            visiting: set[str] = set()
            visited: set[str] = set()
            reported_cycle_nodes: set[str] = set()

            def visit(node_id: str) -> None:
                if node_id in visiting:
                    if node_id not in reported_cycle_nodes:
                        errors.append(f"graph: cycle detected at node '{node_id}'")
                        reported_cycle_nodes.add(node_id)
                    return
                if node_id in visited:
                    return
                visiting.add(node_id)
                for edge in outgoing.get(node_id, []):
                    if edge.get("to") in nodes:
                        visit(edge["to"])
                visiting.remove(node_id)
                visited.add(node_id)

            visit(start)

    for mission in mission_list:
        mission_id = mission.get("id")
        if mission.get("entry_node") not in nodes:
            errors.append(f"mission '{mission_id}': entry node does not exist")
        for end_node in mission.get("end_nodes", []):
            if end_node not in nodes:
                errors.append(f"mission '{mission_id}': end node '{end_node}' does not exist")
        mission_nodes = [node for node in node_list if node.get("mission_id") == mission_id]
        if not any(
            node.get("runner_action", {}).get("causally_required") for node in mission_nodes
        ):
            errors.append(f"mission '{mission_id}': no runner-causal action")
        if not any(
            node.get("relationship_change") not in {None, "", "нет"}
            for node in mission_nodes
        ):
            errors.append(f"mission '{mission_id}': no relationship change")

    reveal = graph.get("central_reveal", {})
    setup_ids = reveal.get("setup_ids", [])
    if len(setup_ids) < 2:
        errors.append("central_reveal: at least two independent setup clues are required")
    setup_locations: dict[str, str] = {}
    payoff_locations: dict[str, str] = {}
    for node in node_list:
        for setup_id in node.get("setup_ids", []):
            setup_locations[setup_id] = node["id"]
        for payoff_id in node.get("payoff_ids", []):
            payoff_locations[payoff_id] = node["id"]
    for setup_id in setup_ids:
        if setup_id not in setup_locations:
            errors.append(f"central_reveal: setup '{setup_id}' has no authored node")
        if setup_id not in payoff_locations:
            errors.append(f"central_reveal: setup '{setup_id}' has no payoff")
    if reveal.get("payoff_node") not in nodes:
        errors.append("central_reveal: payoff node does not exist")
    else:
        mission_order = {
            mission.get("id"): index for index, mission in enumerate(mission_list)
        }
        payoff_mission = mission_order.get(nodes[reveal["payoff_node"]].get("mission_id"), -1)
        for setup_id, setup_node_id in setup_locations.items():
            if setup_id not in setup_ids:
                continue
            setup_mission = mission_order.get(nodes[setup_node_id].get("mission_id"), -1)
            if setup_mission >= payoff_mission:
                errors.append(
                    f"central_reveal: setup '{setup_id}' must precede payoff mission"
                )

    canonical_text = json.dumps(graph, ensure_ascii=False).lower()
    forbidden_city_patterns = [
        r"\bбар\b",
        r"сантьяго",
        r"valpara[ií]so",
        r"вальпараисо",
        r"черногори",
        r"montenegro",
    ]
    for pattern in forbidden_city_patterns:
        if re.search(pattern, canonical_text):
            errors.append(f"graph: canonical story contains research-city token {pattern!r}")

    if not errors:
        try:
            path_count = len(enumerate_paths(graph))
            if path_count > 8:
                errors.append(f"graph: branch explosion ({path_count} paths; maximum is 8)")
        except ValidationError as exc:
            errors.extend(exc.errors)

    if errors:
        raise ValidationError(errors)
    return {
        "nodes": len(node_list),
        "edges": len(edge_list),
        "missions": len(mission_list),
        "states": len(state_schema),
        "paths": len(enumerate_paths(graph)),
    }


def _initial_state(graph: dict[str, Any]) -> dict[str, Any]:
    return {
        state_id: definition["initial"]
        for state_id, definition in graph["state_schema"].items()
    }


def _matching_gate_edges(
    edges: list[dict[str, Any]], state: dict[str, Any]
) -> list[dict[str, Any]]:
    return [
        edge
        for edge in edges
        if all(state.get(key) == value for key, value in edge.get("requires", {}).items())
    ]


def _apply_effects(state: dict[str, Any], edge: dict[str, Any]) -> dict[str, Any]:
    updated = dict(state)
    updated.update(edge.get("effects", {}))
    return updated


def enumerate_paths(graph: dict[str, Any]) -> list[dict[str, Any]]:
    nodes, outgoing = _node_maps(graph)
    start = graph["missions"][0]["entry_node"]
    results: list[dict[str, Any]] = []

    def walk(
        node_id: str,
        state: dict[str, Any],
        decisions: dict[str, str],
        path: list[str],
    ) -> None:
        if len(path) > len(nodes) + 1:
            raise ValidationError(["graph: traversal exceeded node bound (possible cycle)"])
        node = nodes[node_id]
        next_path = path + [node_id]
        if node["kind"] in TERMINAL_KINDS:
            results.append(
                {"decisions": decisions, "final_state": state, "node_ids": next_path}
            )
            return
        edges = outgoing[node_id]
        if node["kind"] == "choice":
            explicit = [edge for edge in edges if not edge.get("fallback")]
            for edge in explicit:
                next_decisions = dict(decisions)
                next_decisions[node["choice_id"]] = edge["option"]
                walk(
                    edge["to"],
                    _apply_effects(state, edge),
                    next_decisions,
                    next_path,
                )
            return
        if node["kind"] == "gate":
            matches = _matching_gate_edges(edges, state)
            if len(matches) != 1:
                raise ValidationError(
                    [f"node '{node_id}': expected one gate transition, got {len(matches)}"]
                )
            edge = matches[0]
        else:
            if len(edges) != 1:
                raise ValidationError(
                    [f"node '{node_id}': expected one deterministic transition"]
                )
            edge = edges[0]
        walk(edge["to"], _apply_effects(state, edge), decisions, next_path)

    walk(start, _initial_state(graph), {}, [])
    return results


def linearize_graph(
    graph: dict[str, Any],
    decisions: dict[str, str],
    stop_mission: str | None = None,
) -> dict[str, Any]:
    validate_decisions(graph, decisions)
    nodes, outgoing = _node_maps(graph)
    node_id = graph["missions"][0]["entry_node"]
    state = _initial_state(graph)
    path: list[dict[str, Any]] = []

    for _ in range(len(nodes) + 1):
        node = nodes[node_id]
        path.append(
            {
                "node_id": node_id,
                "mission_id": node["mission_id"],
                "kind": node["kind"],
                "dramatic_function": node["dramatic_function"],
                "state_before": dict(state),
            }
        )
        if node["kind"] in TERMINAL_KINDS:
            break
        if stop_mission and node["kind"] == "mission_end" and node["mission_id"] == stop_mission:
            break

        edges = outgoing[node_id]
        if node["kind"] == "choice":
            selected = decisions.get(node["choice_id"])
            matching = [
                edge
                for edge in edges
                if not edge.get("fallback") and edge.get("option") == selected
            ]
            if not matching:
                matching = [edge for edge in edges if edge.get("fallback")]
            if len(matching) != 1:
                raise ValidationError(
                    [f"node '{node_id}': cannot resolve choice {selected!r}"]
                )
            edge = matching[0]
            path[-1]["selected_option"] = edge.get("option", node.get("authored_fallback"))
        elif node["kind"] == "gate":
            matching = _matching_gate_edges(edges, state)
            if len(matching) != 1:
                raise ValidationError(
                    [f"node '{node_id}': expected one gate transition, got {len(matching)}"]
                )
            edge = matching[0]
        else:
            if len(edges) != 1:
                raise ValidationError([f"node '{node_id}': nondeterministic transition"])
            edge = edges[0]
        state = _apply_effects(state, edge)
        path[-1]["edge_id"] = edge["id"]
        path[-1]["state_after"] = dict(state)
        node_id = edge["to"]
    else:
        raise ValidationError(["linearize: traversal exceeded graph bound"])

    result = {
        "schema_version": "0.1",
        "concept_id": graph["concept_id"],
        "decisions": decisions,
        "final_state": state,
        "path": path,
    }
    result["checksum"] = checksum(result)
    return result


def validate_decisions(
    graph: dict[str, Any], decisions: dict[str, Any]
) -> dict[str, str]:
    """Validate an explicit authored path selection.

    Choice fallbacks model missing participant input at runtime. Tooling callers
    provide an explicit choices object, so typos and omissions must fail instead
    of silently compiling the fallback branch.
    """
    if not isinstance(decisions, dict):
        raise ValidationError(["choices: top-level value must be an object"])

    choice_nodes = [
        node for node in graph.get("nodes", []) if node.get("kind") == "choice"
    ]
    expected = {node.get("choice_id") for node in choice_nodes if node.get("choice_id")}
    actual = set(decisions)
    errors: list[str] = []

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        errors.append("choices: missing required choices: " + ", ".join(missing))
    if extra:
        errors.append("choices: unknown choices: " + ", ".join(extra))

    nodes_by_choice = {
        node["choice_id"]: node for node in choice_nodes if node.get("choice_id")
    }
    for choice_id in sorted(expected & actual):
        value = decisions[choice_id]
        options = nodes_by_choice[choice_id].get("options", [])
        if value not in options:
            errors.append(
                f"choices: value {value!r} is not allowed for '{choice_id}'"
            )

    if errors:
        raise ValidationError(errors)
    return {key: decisions[key] for key in sorted(expected)}


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\wЁёА-Яа-я-]+\b", text, flags=re.UNICODE))


def validate_beats(beats: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    nodes, _ = _node_maps(graph)
    cues = beats.get("cues", [])
    cue_ids = [cue.get("cue_id") for cue in cues]
    duplicates = _duplicates(value for value in cue_ids if value)
    if duplicates:
        errors.append(f"beats: duplicate cue ids: {', '.join(sorted(duplicates))}")
    if beats.get("concept_id") != graph.get("concept_id"):
        errors.append("beats: concept_id does not match graph")

    workout = beats.get("workout_contract", {})
    pattern = workout.get("interval_pattern", {})
    total = (
        workout.get("warmup_walk_sec", 0)
        + pattern.get("repetitions", 0)
        * (pattern.get("run_sec", 0) + pattern.get("walk_sec", 0))
        + workout.get("cooldown_walk_sec", 0)
    )
    if total != beats.get("target_duration_sec"):
        errors.append(f"beats: workout duration {total}s != target duration")

    beat_nodes: set[str] = set()
    for cue in cues:
        cue_id = cue.get("cue_id", "<missing>")
        node_id = cue.get("node_id")
        if node_id not in nodes:
            errors.append(f"cue '{cue_id}': unknown graph node '{node_id}'")
            continue
        beat_nodes.add(node_id)
        node = nodes[node_id]
        if node.get("mission_id") != beats.get("mission_id"):
            errors.append(f"cue '{cue_id}': node belongs to another mission")
        for field in ("condition_a_text", "condition_b_text", "fallback_text"):
            if not cue.get(field):
                errors.append(f"cue '{cue_id}': missing {field}")
        if "{" in cue.get("condition_b_text", ""):
            errors.append(f"cue '{cue_id}': condition B contains a place placeholder")
        if cue.get("max_spoken_sec", 0) > node.get("workout_fit", {}).get(
            "max_spoken_seconds", 0
        ):
            errors.append(f"cue '{cue_id}': exceeds node spoken-time limit")

        trigger_slot = cue.get("trigger", {}).get("geo_slot_id")
        node_slot = node.get("geo_slot", {}).get("slot_id")
        if trigger_slot != node_slot:
            if trigger_slot or node_slot:
                errors.append(f"cue '{cue_id}': geo slot does not match graph node")
        if node_slot:
            placeholder = "{" + node_slot + ".name}"
            if placeholder not in cue.get("condition_a_text", ""):
                errors.append(
                    f"cue '{cue_id}': condition A must causally bind {placeholder}"
                )
            if not cue.get("fallback_text"):
                errors.append(f"cue '{cue_id}': geo scene has no authored fallback")

        count_a = _word_count(cue.get("condition_a_text", ""))
        count_b = _word_count(cue.get("condition_b_text", ""))
        tolerance = max(12, int(max(count_a, count_b) * 0.40))
        if abs(count_a - count_b) > tolerance:
            errors.append(
                f"cue '{cue_id}': A/B word-count parity failed ({count_a} vs {count_b})"
            )

    expected_nodes = {
        node["id"]
        for node in graph.get("nodes", [])
        if node.get("mission_id") == beats.get("mission_id") and node.get("kind") != "gate"
    }
    missing_nodes = sorted(expected_nodes - beat_nodes)
    if missing_nodes:
        errors.append(f"beats: missing cue cards for nodes: {', '.join(missing_nodes)}")

    if errors:
        raise ValidationError(errors)
    return {"cues": len(cues), "duration_sec": total, "mission_id": beats["mission_id"]}


def validate_scorecard(scorecard: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    weights = scorecard.get("weights", {})
    if sum(weights.values()) != 100:
        errors.append(f"scorecard: weights sum to {sum(weights.values())}, expected 100")
    totals: dict[str, int] = {}
    for candidate in scorecard.get("candidates", []):
        scores = candidate.get("scores", {})
        unknown = set(scores) - set(weights)
        missing = set(weights) - set(scores)
        if unknown or missing:
            errors.append(f"scorecard: category mismatch for {candidate.get('concept_id')}")
        for category, value in scores.items():
            if value < 0 or value > weights.get(category, 0):
                errors.append(
                    f"scorecard: invalid score {value} for {candidate.get('concept_id')}/{category}"
                )
        total = sum(scores.values())
        totals[candidate.get("concept_id")] = total
        if total != candidate.get("total"):
            errors.append(
                f"scorecard: stored total for {candidate.get('concept_id')} is {candidate.get('total')}, computed {total}"
            )
    if totals:
        actual_winner = max(totals, key=lambda concept_id: totals[concept_id])
        if scorecard.get("winner") != actual_winner:
            errors.append(
                f"scorecard: declared winner {scorecard.get('winner')!r} != {actual_winner!r}"
            )
    if errors:
        raise ValidationError(errors)
    return {"candidates": len(totals), "winner": scorecard.get("winner"), "totals": totals}


def _find_private_fields(value: Any, path: str = "binding") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in PRIVATE_FIELD_NAMES:
                findings.append(f"{path}.{key}")
            findings.extend(_find_private_fields(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_find_private_fields(child, f"{path}[{index}]"))
    return findings


def _m1_geo_slot_contract(graph: dict[str, Any]) -> dict[str, set[str]]:
    errors: list[str] = []
    contract: dict[str, set[str]] = {}
    for node in graph.get("nodes", []):
        if node.get("mission_id") != "m01":
            continue
        geo_slot = node.get("geo_slot")
        if not geo_slot:
            continue
        slot_id = geo_slot.get("slot_id")
        allowed = geo_slot.get("allowed_archetypes")
        if (
            not isinstance(slot_id, str)
            or not slot_id
            or not isinstance(allowed, list)
            or not allowed
            or any(not isinstance(value, str) or not value for value in allowed)
            or len(allowed) != len(set(allowed))
        ):
            errors.append(
                f"graph: M1 geo node '{node.get('id', '<missing>')}' has an invalid slot contract"
            )
            continue
        if slot_id in contract:
            errors.append(f"graph: duplicate M1 geo slot '{slot_id}'")
            continue
        contract[slot_id] = set(allowed)
    if errors:
        raise ValidationError(errors)
    return contract


def validate_binding(
    binding: dict[str, Any],
    participant: bool = False,
    graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    active_graph = graph if graph is not None else load_json(DEFAULT_GRAPH)
    slot_contract = _m1_geo_slot_contract(active_graph)
    if binding.get("research_mode") != "traveler_fixture":
        errors.append("binding: research_mode must be traveler_fixture")
    if binding.get("product_model") != "home_territory":
        errors.append("binding: product_model must remain home_territory")
    private_fields = _find_private_fields(binding)
    if private_fields:
        errors.append(
            "binding: committed fixture contains private coordinate/trace fields: "
            + ", ".join(private_fields)
        )

    slots = binding.get("slots")
    if not isinstance(slots, dict):
        errors.append("binding: slots must be an object")
        slots = {}
    expected_slots = set(slot_contract)
    actual_slots = set(slots)
    missing_slots = sorted(expected_slots - actual_slots)
    extra_slots = sorted(actual_slots - expected_slots)
    if missing_slots:
        errors.append("binding: missing required M1 slots: " + ", ".join(missing_slots))
    if extra_slots:
        errors.append("binding: unexpected M1 slots: " + ", ".join(extra_slots))

    for slot_id in sorted(expected_slots & actual_slots):
        slot = slots[slot_id]
        if not isinstance(slot, dict):
            errors.append(f"binding: slot '{slot_id}' must be an object")
            continue
        archetype = slot.get("archetype")
        if not isinstance(archetype, str) or archetype not in slot_contract[slot_id]:
            allowed = ", ".join(sorted(slot_contract[slot_id]))
            errors.append(
                f"binding: slot '{slot_id}' archetype {archetype!r} is not allowed; "
                f"expected one of: {allowed}"
            )

    if participant:
        if binding.get("public_start") is not True:
            errors.append("binding: participant export requires public_start=true")
        for field in ("human_route_approved", "workout_approved", "human_approved"):
            if binding.get(field) is not True:
                errors.append(f"binding: participant export requires {field}=true")
        for slot_id in sorted(expected_slots & actual_slots):
            slot = slots[slot_id]
            if not isinstance(slot, dict):
                continue
            if slot.get("human_approved") is not True:
                errors.append(
                    f"binding: participant export requires slot '{slot_id}' approval"
                )
            for field in ("name", "archetype", "operator_trigger"):
                value = slot.get(field)
                if not value or "REPLACE" in str(value).upper():
                    errors.append(
                        f"binding: slot '{slot_id}' requires a real {field} before participant export"
                    )
            if not slot.get("visible_attributes"):
                errors.append(
                    f"binding: slot '{slot_id}' requires verified visible_attributes"
                )
            if not slot.get("source_refs"):
                errors.append(f"binding: slot '{slot_id}' requires source_refs")
    if errors:
        raise ValidationError(errors)
    return {"slots": len(slots), "participant_ready": participant}


PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\.name\}")


def _bind_text(text: str, binding: dict[str, Any] | None) -> str:
    if binding is None:
        return text

    def replace(match: re.Match[str]) -> str:
        slot_id = match.group(1)
        slot = binding.get("slots", {}).get(slot_id)
        return slot.get("name", match.group(0)) if slot else match.group(0)

    return PLACEHOLDER_RE.sub(replace, text)


def render_mission(
    graph: dict[str, Any],
    beats: dict[str, Any],
    decisions: dict[str, str],
    condition: str,
    binding: dict[str, Any] | None = None,
    participant: bool = False,
) -> dict[str, Any]:
    if condition not in {"A", "B"}:
        raise ValidationError(["render: condition must be A or B"])
    validate_graph(graph)
    validate_beats(beats, graph)
    if participant:
        if binding is None:
            raise ValidationError(["render: participant export requires field binding"])
        validate_binding(binding, participant=True, graph=graph)
    elif binding is not None:
        validate_binding(binding, participant=False, graph=graph)

    linear = linearize_graph(graph, decisions, stop_mission=beats["mission_id"])
    cue_by_node = {cue["node_id"]: cue for cue in beats["cues"]}
    rendered_cues: list[dict[str, Any]] = []
    for path_item in linear["path"]:
        cue = cue_by_node.get(path_item["node_id"])
        if cue is None:
            continue
        text_field = "condition_a_text" if condition == "A" else "condition_b_text"
        rendered_cues.append(
            {
                "cue_id": cue["cue_id"],
                "node_id": cue["node_id"],
                "voice": cue["voice"],
                "trigger": cue["trigger"],
                "max_spoken_sec": cue["max_spoken_sec"],
                "text": _bind_text(cue[text_field], binding),
                "fallback_text": cue["fallback_text"],
            }
        )

    unresolved = sorted(
        {match.group(0) for cue in rendered_cues for match in PLACEHOLDER_RE.finditer(cue["text"])}
    )
    if participant and unresolved:
        raise ValidationError(
            ["render: unresolved participant placeholders: " + ", ".join(unresolved)]
        )
    result = {
        "schema_version": "0.1",
        "status": "participant_ready" if participant else "draft_not_for_participants",
        "concept_id": graph["concept_id"],
        "mission_id": beats["mission_id"],
        "condition": condition,
        "binding_id": binding.get("binding_id") if binding else None,
        "decisions": decisions,
        "final_state": linear["final_state"],
        "unresolved_placeholders": unresolved,
        "cues": rendered_cues,
    }
    result["checksum"] = checksum(result)
    return result


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def command_validate(args: argparse.Namespace) -> int:
    graph = load_json(args.graph)
    beats = load_json(args.beats)
    scorecard = load_json(args.scorecard)
    binding = load_json(args.binding)
    result = {
        "graph": validate_graph(graph),
        "beats": validate_beats(beats, graph),
        "scorecard": validate_scorecard(scorecard),
        "binding_draft": validate_binding(binding, participant=False, graph=graph),
    }
    _print_json(result)
    return 0


def command_paths(args: argparse.Namespace) -> int:
    graph = load_json(args.graph)
    validate_graph(graph)
    paths = enumerate_paths(graph)
    for path in paths:
        path["checksum"] = checksum(path)
    _print_json({"path_count": len(paths), "paths": paths})
    return 0


def command_linearize(args: argparse.Namespace) -> int:
    graph = load_json(args.graph)
    beats = load_json(args.beats)
    decisions = load_json(args.choices)
    binding = load_json(args.binding) if args.binding else None
    result = render_mission(
        graph,
        beats,
        decisions,
        condition=args.condition,
        binding=binding,
        participant=args.participant,
    )
    _print_json(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate all committed R02A artifacts")
    validate.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    validate.add_argument("--beats", type=Path, default=DEFAULT_BEATS)
    validate.add_argument("--scorecard", type=Path, default=DEFAULT_SCORECARD)
    validate.add_argument("--binding", type=Path, default=DEFAULT_BINDING)
    validate.set_defaults(func=command_validate)

    paths = subparsers.add_parser("paths", help="enumerate every explicit braided path")
    paths.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    paths.set_defaults(func=command_paths)

    linearize = subparsers.add_parser(
        "linearize", help="compile one deterministic mission path and A/B cue sheet"
    )
    linearize.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    linearize.add_argument("--beats", type=Path, default=DEFAULT_BEATS)
    linearize.add_argument("--choices", type=Path, default=DEFAULT_CHOICES)
    linearize.add_argument("--binding", type=Path)
    linearize.add_argument("--mission", default="m01", choices=["m01"])
    linearize.add_argument("--condition", default="B", choices=["A", "B"])
    linearize.add_argument("--participant", action="store_true")
    linearize.set_defaults(func=command_linearize)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValidationError, json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
