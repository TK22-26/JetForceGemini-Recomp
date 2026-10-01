"""Discover US exit objectives from an isolated oracle checkpoint.

This inventories only exits instantiated at this checkpoint. It does not claim
that an exit is reachable, that its gate is understood, or that its destination
has been entered. Two fresh workers must agree before edges become schedulable.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.phase95_bridge import Worker, digest
from scripts.phase95_frontier_graph import FrontierGraph
from scripts.phase95_frontier_job import LANE, PRIVATE_ROOT, preflight, require_private
from scripts.phase95_observation import decode
from scripts.phase95_planner_pin import source_pin
from scripts.phase95_world import inventory


def player_position(memory, metadata):
    state = decode(memory, sequence=metadata["sequence"],
                   player_pointer=metadata["player"])
    if state.player is None:
        raise ValueError("discovery checkpoint has no active player")
    return state.player.position


def register(graph, node_id, checkpoint_sha256, observed, pointer, player_position):
    """Add bounded exit-proximity candidates without treating them as coverage."""
    if graph.nodes[node_id]["kind"] != "checkpoint" or \
            graph.nodes[node_id]["metadata"].get("checkpoint_sha256") != checkpoint_sha256:
        raise ValueError("graph checkpoint node does not match sealed source")
    if node_id not in graph.reached_nodes(LANE):
        raise ValueError("graph checkpoint node is not reached in US oracle lane")
    if observed.get("kind") != "jfg-phase95-observed-world" or \
            observed.get("schema") != 1 or type(observed.get("level")) is not int or \
            not isinstance(observed.get("exits"), list):
        raise ValueError("invalid exit inventory")
    if not isinstance(player_position, (list, tuple)) or len(player_position) != 3 or \
            not all(type(value) in (int, float) and math.isfinite(value)
                    for value in player_position):
        raise ValueError("invalid observed player position")
    registered = []
    for item in observed["exits"]:
        exit_id = item.get("id") if isinstance(item, dict) else None
        if not isinstance(exit_id, str) or len(exit_id) != 64 or any(
                char not in "0123456789abcdef" for char in exit_id):
            raise ValueError("invalid observed exit identity")
        if item.get("source_level") != observed["level"] or \
                type(item.get("destination_level")) is not int:
            raise ValueError("invalid observed exit level")
        position = item.get("position")
        if not isinstance(position, (list, tuple)) or len(position) != 3 or \
                not all(type(value) in (int, float) and math.isfinite(value)
                        for value in position):
            raise ValueError("invalid observed exit position")
        horizontal_distance = math.hypot(player_position[0] - position[0],
                                         player_position[2] - position[2])
        if horizontal_distance > 1000000:
            raise ValueError("observed exit too far for bounded search")
        objective_id = f"{node_id}:exit-near:{exit_id}"
        graph.add_node(objective_id, "branch",
                       label=f"Level {observed['level']} exit {exit_id[:12]} proximity",
                       metadata={"predicate": "exit proximity only; crossing unverified",
                                 "source_level": observed["level"],
                                 "setup_destination_level": item["destination_level"]})
        graph.add_edge(objective_id, node_id, objective_id, "objective",
                       priority=round(horizontal_distance),
                       source_variant="us", source_pointer=pointer,
                       required_capabilities=("search-exit",),
                       metadata={"driver": "search-exit", "exit_id": exit_id,
                                 "max_nodes": 128, "max_expansions": 40, "radius": 25,
                                 "proximity": "horizontal", "max_vertical_gap": 100,
                                 "checkpoint_sha256": checkpoint_sha256})
        registered.append(objective_id)
    return registered


def run(checkpoint, output, emulator, rom, script, rom_sha256, *,
        graph_path=None, checkpoint_node=None, worker_type=Worker,
        inventory_reader=inventory, position_reader=player_position,
        private_root=PRIVATE_ROOT):
    for path, label in ((checkpoint, "checkpoint"), (output, "output")):
        require_private(path, private_root, label)
    if graph_path is not None:
        require_private(graph_path, private_root, "graph")
        if checkpoint_node is None:
            raise ValueError("existing graph requires an explicit checkpoint node")
        graph = FrontierGraph.load(graph_path)
    elif checkpoint_node is not None:
        raise ValueError("checkpoint node requires an existing graph")
    else:
        graph = FrontierGraph()
    checkpoint_sha256 = digest(checkpoint)
    identity = preflight({"metadata": {"checkpoint_sha256": checkpoint_sha256}},
                         checkpoint, emulator, rom, script, rom_sha256)
    if graph_path is not None:
        node = graph.nodes.get(checkpoint_node)
        if node is None or node["kind"] != "checkpoint" or \
                node["metadata"].get("checkpoint_sha256") != checkpoint_sha256 or \
                checkpoint_node not in graph.reached_nodes(LANE):
            raise ValueError("existing graph has no reached matching checkpoint node")
    planner_pin = source_pin()
    output.mkdir(parents=True, exist_ok=False)
    (output / "manifest.json").write_text(json.dumps({
        "kind": "jfg-phase95-frontier-discovery", "schema": 1, "acceptance": False,
        "lane": LANE, "checkpoint_sha256": checkpoint_sha256,
        "graph_sha256": digest(graph_path) if graph_path is not None else None,
        "planner_source_sha256": planner_pin["sha256"],
        "planner_sources": planner_pin["files"],
        "identity": identity, "repeat_count": 2,
        "scope": "currently instantiated exits only; reachability unknown"}, indent=2) + "\n")
    attempts = []
    failure = None
    for number in (1, 2):
        try:
            with worker_type(output / f"attempt-{number:02d}", emulator, rom, script,
                             rom_sha256) as worker:
                worker.observe()
                worker.import_checkpoint(checkpoint)
                metadata, memory = worker.observe()
                observed = inventory_reader(memory, metadata["sequence"])
                position = position_reader(memory, metadata)
                attempts.append({"attempt": number, "frame": metadata["frame"],
                                 "polls": metadata["polls"], "player": metadata["player"],
                                 "rdram_sha256": hashlib.sha256(memory).hexdigest(),
                                 "player_position": position,
                                 "inventory": observed})
                (worker.root / "world-inventory.json").write_text(
                    json.dumps(observed, indent=2) + "\n")
        except Exception as error:
            failure = f"{type(error).__name__}: {error}"
            break
    planner_stable = source_pin()["sha256"] == planner_pin["sha256"]
    deterministic = planner_stable and len(attempts) == 2 and all(
        attempts[0][key] == attempts[1][key] for key in
        ("frame", "polls", "player", "rdram_sha256", "player_position", "inventory"))
    registered = []
    if deterministic:
        observed = attempts[0]["inventory"]
        if graph_path is None:
            checkpoint_node = (f"us-level{observed['level']}-checkpoint-"
                               f"{checkpoint_sha256[:16]}")
            graph.add_node(checkpoint_node, "checkpoint",
                           label=f"US level {observed['level']} sealed checkpoint",
                           metadata={"checkpoint_sha256": checkpoint_sha256,
                                     "source_level": observed["level"],
                                     "checkpoint_pointer": checkpoint.resolve().relative_to(
                                         private_root.resolve()).as_posix()})
            graph.add_entrypoint(LANE, checkpoint_node)
        registered = register(graph, checkpoint_node, checkpoint_sha256,
                              observed, "result.json", attempts[0]["player_position"])
        graph.save(output / "frontier-graph.json")
    result = {"kind": "jfg-phase95-frontier-discovery-result", "schema": 1,
              "acceptance": False, "deterministic": deterministic,
              "planner_source_sha256": planner_pin["sha256"],
              "planner_source_stable": planner_stable,
              "checkpoint_node": checkpoint_node if deterministic else None,
              "registered_edges": registered, "attempts": attempts,
              "failure": ("planner source changed during frontier discovery"
                          if not planner_stable else failure if failure is not None else
                          None if deterministic else
                          "independent inventories or checkpoint states disagree"),
              "coverage_claim": False}
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--checkpoint-node")
    args = parser.parse_args()
    print(json.dumps(run(args.checkpoint, args.output, args.emulator, args.rom,
                         args.script, args.rom_sha256, graph_path=args.graph,
                         checkpoint_node=args.checkpoint_node), sort_keys=True))


if __name__ == "__main__":
    main()
