"""Run one bounded US-oracle checkpoint frontier objective, never a TAS replay.

The input graph is immutable. A fresh private output contains both independent
worker journals and a graph fragment with the resulting evidence. No ROM bytes,
checkpoint state, or RDRAM are copied into the graph fragment.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath

from scripts.phase95_bridge import Worker, digest, isolate_n64_bindings, runtime_digest, validate_checkpoint
from scripts.phase95_frontier_graph import FrontierGraph
from scripts.phase95_explore import search
from scripts.phase95_exit import load_search_source
from scripts.phase95_exit import cross
from scripts.phase95_export_inputs import selected_polls
from scripts.phase95_navigation import navigate
from scripts.phase95_planner_pin import source_pin
from scripts.phase95_world import inventory as world_inventory


LANE = "oracle-us"
TARGETS = frozenset(("longwoodbridge", "MrHints2", "exit", "surface-waypoint"))
PRIVATE_ROOT = Path(__file__).resolve().parents[1] / "tools" / "private"
PREDICATE = "player_within_observed_landmark_radius; no transition asserted"
SEARCH_PREDICATE = "player_within_selected_exit_proximity; no transition asserted"
CROSS_PREDICATE = "three_stable_playerBoy_observations_at_declared_destination"


def require_private(path, private_root, label):
    if not path.resolve().is_relative_to(private_root.resolve()):
        raise ValueError(f"{label} must be inside the approved private root")


def select(graph):
    """Select the first reachable, uncovered, supported US objective."""
    frontier = graph.frontier(LANE, capabilities=("navigate", "search-exit",
                                                   "cross-exit"))
    reached_levels = {graph.nodes[node]["metadata"].get("source_level")
                      for node in graph.reached_nodes(LANE)
                      if graph.nodes[node]["kind"] == "checkpoint"}
    attempted_exits = {edge["metadata"]["exit_id"]
                       for edge in graph.edges.values()
                       if edge["metadata"].get("driver") == "search-exit" and
                       graph.status(edge["id"], LANE) == "blocked"}
    fresh_distances = {}
    for edge_id in frontier:
        edge = graph.edges[edge_id]
        if edge["metadata"].get("driver") != "search-exit" or \
                edge["metadata"].get("retry_tier", 0) != 0:
            continue
        distance = graph.nodes[edge["source"]]["metadata"].get("distance_to_exit")
        if type(distance) in (int, float) and math.isfinite(distance) and distance >= 0:
            exit_id = edge["metadata"]["exit_id"]
            fresh_distances[exit_id] = min(distance,
                                           fresh_distances.get(exit_id, math.inf))

    def priority(edge_id):
        edge = graph.edges[edge_id]
        driver = edge["metadata"].get("driver")
        if driver == "cross-exit":
            destination = edge["metadata"].get("destination_level")
        elif driver == "search-exit":
            destination = graph.nodes[edge["target"]]["metadata"].get(
                "setup_destination_level")
        else:
            destination = None
        revisit = type(destination) is int and destination in reached_levels
        tier = edge["metadata"].get("retry_tier", 0)
        # Retry edges are persisted with a large deferral for compatibility;
        # score their distance plus a bounded retry cost so a far duplicate
        # checkpoint does not always outrank a nearby deeper attempt.
        effective_priority = edge["priority"] - 9500 * tier
        # A different checkpoint can reveal a new approach, so keep it in the
        # frontier. Try untouched semantic exits first once one approach has
        # already exhausted a bounded search.
        if driver == "search-exit" and tier == 0 and \
                edge["metadata"]["exit_id"] in attempted_exits:
            effective_priority += 1000
        source_metadata = graph.nodes[edge["source"]]["metadata"]
        if driver == "search-exit" and (
                source_metadata.get("paired_salvage_result") or
                source_metadata.get("paired_node_result")):
            # A paired input path already reached this closer checkpoint;
            # continue fresh spatial branches before enlarging a retry at a
            # paired checkpoint that may be another local cul-de-sac.
            effective_priority -= 2000
            effective_priority += 1000 * tier
            distance = source_metadata.get("distance_to_exit")
            if type(distance) in (int, float) and math.isfinite(distance) and distance >= 0:
                # A verified continuation that made substantial spatial
                # progress should not lose to an older, farther checkpoint
                # solely because it was the first promoted node in a job.
                effective_priority += min(1000, int(distance / 10))
                exit_id = edge["metadata"]["exit_id"]
                if tier == 1 and exit_id in fresh_distances and \
                        distance + 400 <= fresh_distances[exit_id]:
                    # One detour from a much closer verified checkpoint is
                    # worth testing before more distant first-pass branches.
                    effective_priority -= 2000
        return (int(revisit), effective_priority, edge_id)

    for edge_id in sorted(frontier, key=priority):
        edge = graph.edges[edge_id]
        if edge["kind"] not in ("objective", "transition") or \
                edge["source_variant"] != "us":
            continue
        if graph.nodes[edge["source"]]["kind"] != "checkpoint":
            continue
        spec = edge["metadata"]
        driver = spec.get("driver")
        if driver not in ("navigate", "search-exit", "cross-exit"):
            continue
        seal = spec.get("checkpoint_sha256")
        if not isinstance(seal, str) or len(seal) != 64 or any(c not in "0123456789abcdef" for c in seal):
            raise ValueError(f"invalid checkpoint seal {edge_id}")
        if driver == "cross-exit":
            if edge["kind"] != "transition" or set(spec) != {
                    "driver", "exit_id", "destination_level", "max_steps",
                    "checkpoint_sha256", "search_result_pointer"}:
                raise ValueError(f"unreviewed exit-crossing objective {edge_id}")
            pointer = spec["search_result_pointer"]
            if not isinstance(pointer, str) or not pointer or \
                    PureWindowsPath(pointer).drive or PurePosixPath(pointer).is_absolute() or \
                    ".." in PurePosixPath(pointer).parts or "\\" in pointer:
                raise ValueError(f"invalid exit-crossing source pointer {edge_id}")
            if not isinstance(spec["exit_id"], str) or len(spec["exit_id"]) != 64 or any(
                    c not in "0123456789abcdef" for c in spec["exit_id"]):
                raise ValueError(f"invalid exit-crossing identity {edge_id}")
            if type(spec["destination_level"]) is not int or not 0 <= spec["destination_level"] <= 999 or \
                    type(spec["max_steps"]) is not int or not 1 <= spec["max_steps"] <= 100:
                raise ValueError(f"invalid bounded exit-crossing objective {edge_id}")
            return edge
        if edge["kind"] != "objective":
            raise ValueError(f"invalid objective edge kind {edge_id}")
        if driver == "search-exit":
            base = {"driver", "exit_id", "max_nodes", "max_expansions",
                    "radius", "checkpoint_sha256"}
            proximity = {"proximity", "max_vertical_gap"}
            retry = {"retry_parent", "retry_tier"}
            jump = {"jump"}
            if set(spec) not in (base, base | proximity, base | retry,
                                 base | proximity | retry, base | retry | jump,
                                 base | proximity | retry | jump):
                raise ValueError(f"unreviewed exit-search objective {edge_id}")
            if not isinstance(spec["exit_id"], str) or len(spec["exit_id"]) != 64 or any(
                    c not in "0123456789abcdef" for c in spec["exit_id"]):
                raise ValueError(f"invalid exit identity {edge_id}")
            if type(spec["max_nodes"]) is not int or not 2 <= spec["max_nodes"] <= 256 or \
                    type(spec["max_expansions"]) is not int or not 1 <= spec["max_expansions"] <= 100:
                raise ValueError(f"invalid bounded exit-search objective {edge_id}")
            if type(spec["radius"]) not in (int, float) or not 1 <= spec["radius"] <= 100:
                raise ValueError(f"invalid exit-search radius {edge_id}")
            if "proximity" in spec and (spec["proximity"] != "horizontal" or
                    type(spec["max_vertical_gap"]) not in (int, float) or
                    not 1 <= spec["max_vertical_gap"] <= 100):
                raise ValueError(f"invalid exit-search proximity rule {edge_id}")
            if "jump" in spec and spec["jump"] is not True:
                raise ValueError(f"invalid jump-search objective {edge_id}")
            if "retry_tier" in spec and (type(spec["retry_tier"]) is not int or
                    not 1 <= spec["retry_tier"] <= 4 or
                    not isinstance(spec["retry_parent"], str) or
                    spec["retry_parent"] not in graph.edges or
                    graph.edges[spec["retry_parent"]]["source"] != edge["source"] or
                    graph.edges[spec["retry_parent"]]["target"] != edge["target"] or
                    graph.edges[spec["retry_parent"]]["metadata"].get("exit_id") !=
                    spec["exit_id"] or
                    graph.edges[spec["retry_parent"]]["metadata"].get("retry_tier", 0) !=
                    spec["retry_tier"] - 1 or
                    edge["priority"] != graph.edges[spec["retry_parent"]]["priority"] + 10000):
                raise ValueError(f"invalid exit-search retry lineage {edge_id}")
            return edge
        target = spec.get("target_name")
        steps = spec.get("max_steps")
        radius = spec.get("radius")
        if target not in TARGETS or type(steps) is not int or not 1 <= steps <= 3:
            raise ValueError(f"invalid bounded objective {edge_id}")
        if type(radius) not in (int, float) or not 1 <= radius <= 100:
            raise ValueError(f"invalid objective radius {edge_id}")
        allowed = {"driver", "target_name", "max_steps", "radius", "checkpoint_sha256",
                   "exit_id", "waypoint", "precision"}
        if set(spec) - allowed:
            raise ValueError(f"unreviewed objective options {edge_id}")
        if "precision" in spec and type(spec["precision"]) is not bool:
            raise ValueError("precision must be boolean")
        if target == "exit" and spec.get("exit_id") is None:
            raise ValueError("exit objective requires a reviewed exit ID")
        if target == "surface-waypoint":
            waypoint = spec.get("waypoint")
            if not isinstance(waypoint, list) or len(waypoint) != 3 or not all(
                    type(v) in (int, float) and abs(v) <= 100000 for v in waypoint):
                raise ValueError("invalid bounded waypoint")
        elif "waypoint" in spec:
            raise ValueError("waypoint only applies to surface-waypoint")
        return edge
    raise ValueError("no reachable uncovered US checkpoint navigation objective")


def preflight(edge, checkpoint, emulator, rom, script, rom_sha256):
    """Validate the exact Worker identity before launching or creating output."""
    if digest(checkpoint) != edge["metadata"]["checkpoint_sha256"]:
        raise ValueError("checkpoint seal does not match graph objective")
    if digest(rom) != rom_sha256:
        raise ValueError("ROM identity mismatch")
    source = emulator.parent
    config = json.loads((source / "config.ini").read_text(encoding="utf-8-sig"))
    for entry in config.get("PathEntries", {}).get("Paths", []):
        value = Path(entry.get("Path", ""))
        if value.is_absolute() or ".." in value.parts:
            raise ValueError("emulator path is not isolated")
    # Worker uses Path.write_text(newline=None): Windows translates LF to CRLF.
    encoded = (json.dumps(isolate_n64_bindings(config), indent=2) + "\n").replace(
        "\n", os.linesep).encode()
    identity = {"rom_sha256": rom_sha256,
                "runtime_sha256": runtime_digest(source),
                "config_sha256": hashlib.sha256(encoded).hexdigest(),
                "script_sha256": digest(script)}
    validate_checkpoint(checkpoint, identity)
    return identity


def verified_output_checkpoint(path, metadata, memory):
    """Never publish a route checkpoint pointer without its sealed state."""
    seal = json.loads(path.read_text())
    if seal.get("kind") != "jfg-phase95-checkpoint" or seal.get("schema") != 1 or \
            seal.get("rdram_sha256") != hashlib.sha256(memory).hexdigest() or any(
                seal.get("observation", {}).get(key) != metadata.get(key)
                for key in ("frame", "polls", "player")):
        raise ValueError("output checkpoint does not seal final observation")
    for suffix in ("State", "side"):
        if seal.get("digests", {}).get(suffix) != digest(path.with_suffix("." + suffix)):
            raise ValueError(f"output checkpoint {suffix} digest mismatch")


def add_incomplete_search_retry(graph, edge, output, job_id=None):
    """Escalate bounded search evidence without asserting an exit is unreachable."""
    spec = edge["metadata"]
    if spec["driver"] != "search-exit":
        return None
    failure_path = output / "attempt-01" / "search-failure.json"
    if not failure_path.is_file():
        return None
    failure = json.loads(failure_path.read_text())
    if failure.get("kind") != "jfg-phase95-search-incomplete" or \
            failure.get("reason") != "bounded search exhausted" or \
            failure.get("unreachable") is not False or \
            type(failure.get("nodes")) is not int or failure["nodes"] < 1:
        return None
    world_path = output / "attempt-01" / "world-inventory.json"
    if job_id is not None and world_path.is_file():
        for sibling, _ in colocated_search_siblings(
                graph, edge, json.loads(world_path.read_text())):
            if "retry_tier" in sibling["metadata"]:
                continue
            suffix = hashlib.sha256(sibling["id"].encode()).hexdigest()[:16]
            graph.record(job_id + "-colocated-miss-" + suffix, sibling["id"], LANE,
                         "blocked", "attempt-01/search-failure.json",
                         reason="co-located bounded search incomplete; not unreachable")
    nodes = min(256, max(128, spec["max_nodes"] * 2))
    expansions = min(100, max(40, spec["max_expansions"] * 2))
    jump = spec.get("jump", False)
    if nodes == spec["max_nodes"] and expansions == spec["max_expansions"]:
        if jump:
            return None
        jump = True
    tier = spec.get("retry_tier", 0) + 1
    if tier > 4:
        return None
    retry_id = f"{edge['id']}:retry-{tier}"
    graph.add_edge(retry_id, edge["source"], edge["target"], edge["kind"],
                   priority=edge["priority"] + 10000,
                   source_variant=edge["source_variant"],
                   source_pointer=edge["source_pointer"],
                   required_capabilities=edge["required_capabilities"],
                   metadata={**spec, "max_nodes": nodes,
                             "max_expansions": expansions,
                             "retry_parent": edge["id"], "retry_tier": tier,
                             **({"jump": True} if jump else {})})
    return retry_id


def block_auto_transition_source(graph, edge, output, job_id):
    """A checkpoint that auto-crosses cannot seed other ordinary exit searches."""
    path = output / "attempt-01" / "search-failure.json"
    if edge["metadata"].get("driver") != "search-exit" or not path.is_file():
        return []
    failure = json.loads(path.read_text())
    if (failure.get("kind") != "jfg-phase95-search-incomplete" or
            failure.get("source_auto_transition") is not True or
            failure.get("reason") !=
            "source checkpoint auto-transitions before explored move" or
            failure.get("nodes") != 1 or
            type(failure.get("trials")) is not int or failure["trials"] < 8 or
            not isinstance(failure.get("observed_levels"), list) or
            not failure["observed_levels"] or
            any(type(level) is not int for level in failure["observed_levels"]) or
            failure.get("unreachable") is not False):
        return []
    blocked = []
    for candidate in graph.edges.values():
        if (candidate["id"] == edge["id"] or
                candidate["source"] != edge["source"] or
                candidate["source_variant"] != "us" or
                candidate["metadata"].get("driver") != "search-exit" or
                graph.status(candidate["id"], LANE) != "unexplored"):
            continue
        suffix = hashlib.sha256(candidate["id"].encode()).hexdigest()[:16]
        graph.record(job_id + "-auto-transition-" + suffix, candidate["id"],
                     LANE, "blocked", "attempt-01/search-failure.json",
                     reason="source checkpoint crossed another exit under all bounded moves; use alternate source")
        blocked.append(candidate["id"])
    return blocked


def colocated_search_siblings(graph, edge, observed_world):
    """Find distinct exit objectives sharing an exact observed landmark/rule."""
    if not isinstance(observed_world, dict) or \
            observed_world.get("kind") != "jfg-phase95-observed-world" or \
            observed_world.get("schema") != 1 or not isinstance(
                observed_world.get("exits"), list) or any(
                    not isinstance(item, dict) or not isinstance(item.get("id"), str) or
                    not isinstance(item.get("position"), list)
                    for item in observed_world["exits"]):
        raise ValueError("invalid observed world for co-located exits")
    exits = {item["id"]: item for item in observed_world["exits"]}
    if len(exits) != len(observed_world["exits"]):
        raise ValueError("ambiguous observed exit identities")
    selected = exits.get(edge["metadata"]["exit_id"])
    if selected is None or observed_world.get("level") != selected.get("source_level"):
        raise ValueError("selected exit absent from observed world")
    spec = edge["metadata"]
    siblings = []
    for candidate in graph.edges.values():
        other = candidate["metadata"]
        if candidate["id"] == edge["id"] or \
                candidate["source"] != edge["source"] or \
                candidate["source_variant"] != "us" or \
                other.get("driver") != "search-exit" or \
                other.get("exit_id") == spec["exit_id"] or \
                any(other.get(key) != spec.get(key) for key in
                    ("radius", "proximity", "max_vertical_gap")) or \
                graph.status(candidate["id"], LANE) == "covered":
            continue
        identity = exits.get(other["exit_id"])
        if identity is not None and identity["position"] == selected["position"]:
            siblings.append((candidate, identity))
    return sorted(siblings, key=lambda pair: pair[0]["id"])


def promote_search_checkpoint(graph, edge, output, job_id, attempts,
                              private_root=PRIVATE_ROOT):
    """Reach the selected route checkpoint; do not assert an exit crossing."""
    pointer = attempts[0]["checkpoint"]
    checkpoint_path = output / pointer
    source_identity = load_search_source(checkpoint_path.parent / "search-result.json",
                                         checkpoint_path, edge["metadata"]["exit_id"])
    source_level = source_identity["source_level"]
    declared_level = graph.nodes[edge["source"]]["metadata"].get("source_level")
    if declared_level is not None and declared_level != source_level:
        raise ValueError("search source level disagrees with graph checkpoint")
    checkpoint_sha256 = digest(checkpoint_path)
    node_id = f"us-level{source_level}-checkpoint-{checkpoint_sha256[:16]}"
    graph.add_node(node_id, "checkpoint",
                   label=f"US level {source_level} exit-proximity checkpoint",
                   metadata={"checkpoint_sha256": checkpoint_sha256,
                             "source_level": source_level,
                             "checkpoint_pointer": checkpoint_path.resolve().relative_to(
                                 private_root.resolve()).as_posix()})
    link_id = f"{edge['id']}:checkpoint"
    graph.add_edge(link_id, edge["target"], node_id, "progression", priority=0,
                   source_variant="us", source_pointer=pointer,
                   metadata={"predicate": "sealed replay-equal route checkpoint; exit not crossed"})
    graph.record(job_id + "-checkpoint", link_id, LANE, "covered", "result.json")
    same_exit_covered = []
    for candidate in list(graph.edges.values()):
        other = candidate["metadata"]
        if candidate["id"] != edge["id"] and \
                candidate["source"] == edge["source"] and \
                candidate["target"] == edge["target"] and \
                other.get("driver") == "search-exit" and \
                other.get("exit_id") == source_identity["id"] and \
                all(other.get(key) == edge["metadata"].get(key) for key in
                    ("radius", "proximity", "max_vertical_gap")) and \
                graph.status(candidate["id"], LANE) != "covered":
            suffix = hashlib.sha256(candidate["id"].encode()).hexdigest()[:16]
            graph.record(job_id + "-same-exit-" + suffix, candidate["id"], LANE,
                         "covered", f"{checkpoint_path.parent.name}/search-result.json")
            same_exit_covered.append(candidate["id"])
    search_results = [(source_identity, checkpoint_path.parent / "search-result.json")]
    initial_world_path = checkpoint_path.parent / "world-inventory.json"
    if initial_world_path.is_file():
        siblings = colocated_search_siblings(graph, edge,
                                             json.loads(initial_world_path.read_text()))
        if siblings:
            checkpoint_seal = json.loads(checkpoint_path.read_text())
            memory = (checkpoint_path.parent / "observation.rdram").read_bytes()
            if hashlib.sha256(memory).hexdigest() != checkpoint_seal["rdram_sha256"]:
                raise ValueError("co-located exit final memory differs from checkpoint")
            final_world = world_inventory(memory,
                                          checkpoint_seal["observation"]["sequence"])
            if final_world["level"] != source_level:
                raise ValueError("co-located exit world changed level")
            final_exits = {item["id"]: item for item in final_world["exits"]}
            derived_results = {}
            for sibling, _ in siblings:
                identity = final_exits.get(sibling["metadata"]["exit_id"])
                if identity is None or identity["position"] != source_identity["position"]:
                    continue
                sibling_result = derived_results.get(identity["id"])
                if sibling_result is None:
                    sibling_result = checkpoint_path.parent / (
                        f"search-colocated-{identity['id'][:16]}.json")
                    sibling_result.write_text(json.dumps({
                        "kind": "jfg-phase95-checkpoint-search", "completed": True,
                        "replay_equal": True,
                        "final_rdram_sha256": checkpoint_seal["rdram_sha256"],
                        "exit_identity": identity,
                        "co_located_with": source_identity["id"],
                        "source_result_sha256": digest(search_results[0][1])}, indent=2) + "\n")
                    derived_results[identity["id"]] = sibling_result
                    search_results.append((identity, sibling_result))
                suffix = hashlib.sha256(sibling["id"].encode()).hexdigest()[:16]
                graph.record(job_id + "-colocated-" + suffix, sibling["id"], LANE,
                             "covered", f"{checkpoint_path.parent.name}/{sibling_result.name}")
    for identity, source_result in search_results:
        destination = identity.get("destination_level")
        if identity.get("world_gate") != -1 or \
                type(destination) is not int or destination == source_level:
            continue
        arrival_id = f"{node_id}:arrival:{destination}"
        if arrival_id in graph.edges and graph.edges[arrival_id]["metadata"].get("exit_id") != \
                identity["id"]:
            arrival_id += ":" + identity["id"][:16]
        search_pointer = source_result.resolve().relative_to(private_root.resolve()).as_posix()
        graph.add_node(arrival_id, "objective",
                       label=f"Stable playable arrival at level {destination}",
                       metadata={"predicate": "three playerBoy gameplay observations"})
        graph.add_edge(arrival_id, node_id, arrival_id, "transition", priority=0,
                       source_variant="us",
                       source_pointer=search_pointer,
                       required_capabilities=("cross-exit",),
                       metadata={"driver": "cross-exit",
                                 "exit_id": identity["id"],
                                 "destination_level": destination,
                                 "max_steps": 30,
                                 "checkpoint_sha256": checkpoint_sha256,
                                 "search_result_pointer": search_pointer})
    return {"node": node_id, "pointer": pointer,
            "checkpoint_sha256": checkpoint_sha256,
            "same_exit_covered_edges": same_exit_covered,
            "co_located_exit_ids": [item[0]["id"] for item in search_results[1:]]}


def promote_cross_checkpoint(graph, edge, output, job_id, attempts,
                             private_root=PRIVATE_ROOT):
    """Reach a new playable level only after two stable-arrival workers agree."""
    pointer = attempts[0]["checkpoint"]
    checkpoint_path = output / pointer
    crossing = json.loads((checkpoint_path.parent / "exit-result.json").read_text())
    destination = edge["metadata"]["destination_level"]
    last = crossing.get("final_observation", {})
    if crossing.get("completed") is not True or \
            crossing.get("destination_level") != destination or \
            last.get("level") != destination or last.get("player_name") != "playerBoy":
        raise ValueError("crossing result does not prove declared playable arrival")
    checkpoint_sha256 = digest(checkpoint_path)
    node_id = f"us-level{destination}-checkpoint-{checkpoint_sha256[:16]}"
    graph.add_node(node_id, "checkpoint",
                   label=f"US level {destination} stable arrival checkpoint",
                   metadata={"checkpoint_sha256": checkpoint_sha256,
                             "source_level": destination,
                             "checkpoint_pointer": checkpoint_path.resolve().relative_to(
                                 private_root.resolve()).as_posix()})
    link_id = f"{edge['id']}:checkpoint"
    graph.add_edge(link_id, edge["target"], node_id, "progression", priority=0,
                   source_variant="us", source_pointer=pointer,
                   metadata={"predicate": "sealed stable playable arrival checkpoint"})
    graph.record(job_id + "-checkpoint", link_id, LANE, "covered", "result.json")
    return {"node": node_id, "pointer": pointer,
            "checkpoint_sha256": checkpoint_sha256}


def search_mode(graph, edge):
    """Escalate a local exit retry into breadth-first topology scouting."""
    spec = edge["metadata"]
    if spec.get("driver") != "search-exit":
        return None
    tier = spec.get("retry_tier", 0)
    if tier >= 2:
        return "coverage"
    source = graph.nodes[edge["source"]]["metadata"]
    if tier >= 1 and (source.get("paired_salvage_result") or
                      source.get("paired_node_result")):
        return "detour"
    return "distance"


def run(graph_path, output, checkpoint, emulator, rom, script, rom_sha256, job_id,
        *, worker_type=Worker, navigator=navigate, searcher=search,
        crosser=cross, poll_selector=selected_polls,
        private_root=PRIVATE_ROOT):
    for path, label in ((graph_path, "graph"), (checkpoint, "checkpoint"),
                        (output, "output")):
        require_private(path, private_root, label)
    graph = FrontierGraph.load(graph_path)
    edge = select(graph)
    identity = preflight(edge, checkpoint, emulator, rom, script, rom_sha256)
    spec = edge["metadata"]
    mode = search_mode(graph, edge)
    source_identity = None
    if spec["driver"] == "cross-exit":
        source_result = private_root / spec["search_result_pointer"]
        require_private(source_result, private_root, "search result")
        source_identity = load_search_source(source_result, checkpoint, spec["exit_id"])
        if source_identity["destination_level"] != spec["destination_level"]:
            raise ValueError("crossing destination differs from sealed search result")
    if not job_id or job_id != job_id.strip() or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in job_id):
        raise ValueError("job ID must use lowercase letters, digits, hyphen, underscore")
    planner_pin = source_pin()
    output.mkdir(parents=True, exist_ok=False)
    predicate = {"search-exit": SEARCH_PREDICATE, "cross-exit": CROSS_PREDICATE,
                 "navigate": PREDICATE}[spec["driver"]]
    manifest = {"kind": "jfg-phase95-frontier-job", "schema": 1, "acceptance": False,
                "job_id": job_id, "lane": LANE, "edge_id": edge["id"],
                "graph_sha256": digest(graph_path), "checkpoint_sha256": digest(checkpoint),
                "identity": identity, "objective": spec, "predicate": predicate,
                "planner_source_sha256": planner_pin["sha256"],
                "planner_sources": planner_pin["files"],
                "effective_search_mode": mode,
                "repeat_count": 2}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    attempts = []
    failure = None
    for number in (1, 2):
        try:
            with worker_type(output / f"attempt-{number:02d}", emulator, rom, script,
                             rom_sha256) as worker:
                worker.observe()
                worker.import_checkpoint(checkpoint)
                if spec["driver"] == "cross-exit":
                    result = crosser(worker, exit_id=spec["exit_id"],
                                     max_steps=spec["max_steps"],
                                     source_identity=source_identity)
                    steps = result["final_observation"]["step"] + 1
                elif spec["driver"] == "search-exit":
                    result = searcher(worker, spec["exit_id"],
                                      max_nodes=spec["max_nodes"],
                                      max_expansions=spec["max_expansions"],
                                      radius=spec["radius"],
                                      **({"mode": mode} if mode != "distance" else {}),
                                      **({"jump": True} if spec.get("jump") else {}),
                                      **({"proximity": spec["proximity"],
                                          "max_vertical_gap": spec["max_vertical_gap"]}
                                         if "proximity" in spec else {}))
                    steps = result["route_steps"]
                else:
                    result = navigator(worker, spec["target_name"], max_steps=spec["max_steps"],
                                       radius=spec["radius"], exit_id=spec.get("exit_id"),
                                       waypoint=spec.get("waypoint"),
                                       precision=spec.get("precision", False))
                    steps = result["steps"]
                metadata, memory = worker.observe()
                checkpoint_pointer = None
                if spec["driver"] in ("search-exit", "cross-exit") and result["completed"]:
                    slot = "c1" if spec["driver"] == "search-exit" else "e1"
                    checkpoint_path = worker.root / f"checkpoint-{slot}.json"
                    verified_output_checkpoint(checkpoint_path, metadata, memory)
                    checkpoint_pointer = f"attempt-{number:02d}/checkpoint-{slot}.json"
                attempt = {"attempt": number, "completed": result["completed"],
                           "steps": steps, "frame": metadata["frame"],
                           "polls": metadata["polls"], "player": metadata["player"],
                           "rdram_sha256": hashlib.sha256(memory).hexdigest(),
                           "journal": f"attempt-{number:02d}",
                           "checkpoint": checkpoint_pointer}
            samples, _ = poll_selector(output / f"attempt-{number:02d}")
            if len(samples) != attempt["polls"]:
                raise ValueError("selected controller path does not match final poll count")
            attempt["selected_input_sha256"] = hashlib.sha256(json.dumps(
                samples, separators=(",", ":")).encode()).hexdigest()
            if attempt["completed"]:
                scenario = {"kind": "jfg-phase95-frontier-scenario-result", "schema": 1,
                            "completed": True, "edge_id": edge["id"],
                            "final_frame": attempt["frame"],
                            "final_rdram_sha256": attempt["rdram_sha256"],
                            "controller_polls": attempt["polls"],
                            "planner_source_sha256": planner_pin["sha256"],
                            "selected_input_sha256": attempt["selected_input_sha256"]}
                (output / f"attempt-{number:02d}" / "scenario-result.json").write_text(
                    json.dumps(scenario, indent=2) + "\n")
            attempts.append(attempt)
        except Exception as error:
            failure = f"{type(error).__name__}: {error}"
            break
    planner_stable = source_pin()["sha256"] == planner_pin["sha256"]
    signatures = [tuple(item[key] for key in ("completed", "steps", "frame", "polls",
                                                   "player", "rdram_sha256", "selected_input_sha256"))
                  for item in attempts]
    deterministic = len(signatures) == 2 and signatures[0] == signatures[1]
    covered = planner_stable and deterministic and all(item["completed"] for item in attempts)
    reason = None if covered else ("planner source changed during frontier job"
                                   if not planner_stable else failure or
                                   "independent attempts disagree or objective unfinished")
    next_checkpoint = None
    if covered and spec["driver"] in ("search-exit", "cross-exit"):
        try:
            promotion = (promote_search_checkpoint if spec["driver"] == "search-exit"
                         else promote_cross_checkpoint)
            next_checkpoint = promotion(graph, edge, output, job_id, attempts,
                                        private_root=private_root)
        except Exception as error:
            graph = FrontierGraph.load(graph_path)
            covered = False
            reason = f"checkpoint promotion failed: {type(error).__name__}: {error}"
    result = {"kind": "jfg-phase95-frontier-result", "schema": 1, "acceptance": False,
              "job_id": job_id, "edge_id": edge["id"], "lane": LANE,
              "predicate": predicate,
              "outcome": "covered" if covered else "blocked", "deterministic": deterministic,
              "planner_source_sha256": planner_pin["sha256"],
              "planner_source_stable": planner_stable,
              "attempts": attempts, "reason": reason}
    if next_checkpoint is not None:
        result["next_checkpoint"] = next_checkpoint
    graph.record(job_id, edge["id"], LANE, result["outcome"], "result.json", reason=reason)
    if not covered and planner_stable:
        source_blocked = block_auto_transition_source(graph, edge, output, job_id)
        if source_blocked:
            result["source_blocked_edges"] = source_blocked
        retry = add_incomplete_search_retry(graph, edge, output, job_id=job_id)
        if retry is not None:
            result["retry_edge_id"] = retry
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    graph.save(output / "frontier-evidence.json")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    result = run(args.graph, args.output, args.checkpoint, args.emulator, args.rom,
                 args.script, args.rom_sha256, args.job_id)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
