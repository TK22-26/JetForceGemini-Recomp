"""Independently replay one saved incomplete-search path into a new checkpoint.

This proves a reachable spatial state and identical selected controller input,
not exit coverage or native parity. All input and checkpoint data stay private.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.phase95_bridge import Action, Worker, digest, validate_checkpoint
from scripts.phase95_export_inputs import selected_polls
from scripts.phase95_frontier_job import PRIVATE_ROOT, require_private


def _nodes(root):
    nodes = [json.loads(line) for line in
             (root / "search-nodes.jsonl").read_text().splitlines()]
    if not nodes or len(nodes) > 256:
        raise ValueError("invalid saved search node count")
    for index, node in enumerate(nodes):
        parent = node.get("parent")
        if (node.get("id") != index or node.get("slot") != f"a{index:04x}" or
                (parent is not None and
                 (type(parent) is not int or not 0 <= parent < index)) or
                (index == 0) != (parent is None) or
                type(node.get("depth")) is not int or
                node["depth"] != (0 if parent is None else nodes[parent]["depth"] + 1) or
                not isinstance(node.get("sha256"), str) or
                len(node["sha256"]) != 64 or
                not isinstance(node.get("position"), list) or
                len(node["position"]) != 3 or
                not all(type(value) in (int, float) and math.isfinite(value)
                        for value in node["position"]) or
                type(node.get("distance")) not in (int, float) or
                not math.isfinite(node["distance"])):
            raise ValueError("invalid saved search node")
        counters = node.get("counters")
        if not isinstance(counters, dict) or any(
                type(counters.get(key)) is not int or counters[key] < 0
                for key in ("frame", "polls", "player")):
            raise ValueError("invalid saved search node counters")
        if index:
            raw_actions = node.get("actions") or [node.get("action")]
            if not isinstance(raw_actions, list) or not 1 <= len(raw_actions) <= 3:
                raise ValueError("invalid saved node actions")
            for raw in raw_actions:
                if not isinstance(raw, dict) or set(raw) != {
                        "frames", "buttons", "x", "y"}:
                    raise ValueError("invalid saved node action")
                Action(**raw).validate()
    return nodes


def _path(nodes, node_id):
    if type(node_id) is not int or not 0 <= node_id < len(nodes):
        raise ValueError("invalid saved search node ID")
    route = []
    current = node_id
    while current:
        route.append(nodes[current])
        current = nodes[current]["parent"]
    route.reverse()
    if len(route) > 100:
        raise ValueError("selected search path exceeds bounded replay depth")
    return route


def _same_observation(metadata, memory, node):
    return (hashlib.sha256(memory).hexdigest() == node["sha256"] and
            all(metadata.get(key) == node["counters"][key]
                for key in ("frame", "polls", "player")))


def verify(source_worker, output, emulator, rom, script, rom_sha256,
           *, node_id=None, worker_type=Worker, private_root=PRIVATE_ROOT):
    source_worker, output = Path(source_worker).resolve(), Path(output).resolve()
    require_private(source_worker, private_root, "source search")
    require_private(output, private_root, "replayed node")
    if output.exists() or not source_worker.is_dir():
        raise ValueError("node replay needs a fresh output and existing source")
    if (source_worker / "bridge-result.txt").read_text() != "stopped\n":
        raise ValueError("source search worker did not stop cleanly")
    failure = json.loads((source_worker / "search-failure.json").read_text())
    if failure.get("kind") != "jfg-phase95-search-incomplete" or \
            failure.get("reason") != "bounded search exhausted" or \
            failure.get("unreachable") is not False:
        raise ValueError("source is not a bounded incomplete search")
    source_manifest = json.loads((source_worker / "manifest.json").read_text())
    lineage = json.loads((source_worker / "import-lineage.json").read_text())
    source_checkpoint = Path(lineage["source_manifest"]).resolve()
    require_private(source_checkpoint, private_root, "source checkpoint")
    if digest(source_checkpoint) != lineage["source_manifest_sha256"]:
        raise ValueError("source checkpoint lineage changed")
    validate_checkpoint(source_checkpoint, source_manifest)
    nodes = _nodes(source_worker)
    objective = json.loads((source_worker / "search-objective.json").read_text())
    exit_identity = objective.get("exit_identity", {})
    target = exit_identity.get("position")
    if (objective.get("kind") != "jfg-phase95-checkpoint-search" or
            type(exit_identity.get("source_level")) is not int or
            not isinstance(exit_identity.get("id"), str) or
            len(exit_identity["id"]) != 64 or
            not isinstance(target, list) or len(target) != 3 or
            not all(type(value) in (int, float) and math.isfinite(value)
                    for value in target) or
            objective.get("proximity") not in ("3d", "horizontal")):
        raise ValueError("invalid saved exit-search objective")
    for node in nodes:
        measured = (math.hypot(node["position"][0] - target[0],
                               node["position"][2] - target[2])
                    if objective["proximity"] == "horizontal" else
                    math.dist(node["position"], target))
        if abs(measured - node["distance"]) > 0.001:
            raise ValueError("saved node distance differs from observed exit")
    if node_id is not None and (type(node_id) is not int or
                                not 0 <= node_id < len(nodes)):
        raise ValueError("invalid saved search node ID")
    chosen = min(nodes, key=lambda node: (node["distance"], node["id"])) \
        if node_id is None else nodes[node_id]
    route = _path(nodes, chosen["id"])
    selected_checkpoint = source_worker / f"checkpoint-{chosen['slot']}.json"
    seal = validate_checkpoint(selected_checkpoint, source_manifest)
    if (seal.get("rdram_sha256") != chosen["sha256"] or
            any(seal.get("observation", {}).get(key) != chosen["counters"][key]
                for key in ("frame", "polls", "player"))):
        raise ValueError("saved search node differs from its checkpoint")
    original_samples, _ = selected_polls(source_worker, stop_slot=chosen["slot"])
    if len(original_samples) != chosen["counters"]["polls"]:
        raise ValueError("selected saved-node input has wrong poll count")
    output.mkdir(parents=True, exist_ok=False)
    replay_root = output / "worker"
    with worker_type(replay_root, emulator, rom, script, rom_sha256) as worker:
        worker.observe()
        for key in ("rom_sha256", "emulator_sha256", "runtime_sha256",
                    "config_sha256", "script_sha256"):
            if worker.identity.get(key) != source_manifest.get(key):
                raise ValueError(f"independent worker changed {key}")
        worker.import_checkpoint(source_checkpoint)
        metadata, memory = worker.observe()
        if not _same_observation(metadata, memory, nodes[0]):
            raise ValueError("independent search source differs from saved root")
        for node in route:
            for raw in node.get("actions") or [node["action"]]:
                worker.act(Action(**raw))
                metadata, memory = worker.observe()
            if not _same_observation(metadata, memory, node):
                raise ValueError(f"independent search node differs at {node['id']}")
            print(json.dumps({"replayed_node": node["id"],
                              "depth": node["depth"],
                              "distance": node["distance"]}), flush=True)
        worker.checkpoint("save", "c1")
        final_metadata, final_memory = worker.observe()
        if not _same_observation(final_metadata, final_memory, chosen):
            raise ValueError("saving independent checkpoint changed selected state")
    replay_checkpoint = replay_root / "checkpoint-c1.json"
    validate_checkpoint(replay_checkpoint, worker.identity)
    replay_samples, _ = selected_polls(replay_root, stop_slot="c1")
    if replay_samples != original_samples:
        raise ValueError("independent selected controller path differs")
    sample_sha = hashlib.sha256(json.dumps(
        original_samples, separators=(",", ":")).encode()).hexdigest()
    result = {"kind": "jfg-phase95-replayed-frontier-node", "schema": 1,
              "acceptance": False, "native_parity_verified": False,
              "source_worker": str(source_worker),
              "source_manifest_sha256": digest(source_worker / "manifest.json"),
              "source_checkpoint_pointer": source_checkpoint.relative_to(
                  private_root.resolve()).as_posix(),
              "exit_id": exit_identity["id"],
              "source_level": exit_identity["source_level"],
              "exit_position": target,
              "source_identity": {key: source_manifest[key] for key in
                                  ("rom_sha256", "emulator_sha256", "runtime_sha256",
                                   "config_sha256", "script_sha256")},
              "selected_node": chosen["id"], "depth": chosen["depth"],
              "source_distance": nodes[0]["distance"],
              "selected_distance": chosen["distance"],
              "player_position": chosen["position"],
              "rdram_sha256": chosen["sha256"],
              "frame": chosen["counters"]["frame"],
              "controller_polls": len(original_samples),
              "selected_input_sha256": sample_sha,
              "checkpoint_pointers": [selected_checkpoint.relative_to(
                  private_root.resolve()).as_posix(),
                  replay_checkpoint.relative_to(private_root.resolve()).as_posix()],
              "checkpoint_sha256": [digest(selected_checkpoint),
                                    digest(replay_checkpoint)],
              "verification_tool_sha256": digest(Path(__file__)),
              "limitation": "paired oracle spatial checkpoint only; exit not reached"}
    (output / "verification-result.json").write_text(
        json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_worker", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--node-id", type=int)
    args = parser.parse_args()
    print(json.dumps(verify(args.source_worker, args.output, args.emulator,
                            args.rom, args.script, args.rom_sha256,
                            node_id=args.node_id), sort_keys=True))


if __name__ == "__main__":
    main()
