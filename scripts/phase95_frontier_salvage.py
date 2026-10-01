"""Pair a reusable near-exit checkpoint from two incomplete oracle searches.

The proof is exploratory checkpoint evidence, not exit coverage or native parity.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.phase95_bridge import digest, validate_checkpoint
from scripts.phase95_export_inputs import selected_polls
from scripts.phase95_frontier_job import PRIVATE_ROOT, require_private


IDENTITY_KEYS = ("rom_sha256", "emulator_sha256", "runtime_sha256",
                 "config_sha256", "script_sha256")


def _read(path):
    return json.loads(path.read_text())


def _worker(root, exit_id):
    manifest = _read(root / "manifest.json")
    world = _read(root / "world-inventory.json")
    failure = _read(root / "search-failure.json")
    if world.get("kind") != "jfg-phase95-observed-world" or \
            type(world.get("level")) is not int or \
            failure.get("kind") != "jfg-phase95-search-incomplete" or \
            failure.get("unreachable") is not False:
        raise ValueError("source is not an incomplete observed search")
    exits = [item for item in world.get("exits", ()) if item.get("id") == exit_id]
    if len(exits) != 1 or exits[0].get("source_level") != world["level"]:
        raise ValueError("selected exit identity absent or ambiguous")
    nodes = [json.loads(line) for line in (root / "search-nodes.jsonl").read_text().splitlines()]
    if not nodes:
        raise ValueError("incomplete search has no saved nodes")
    lineage_path = root / "import-lineage.json"
    lineage = _read(lineage_path) if lineage_path.is_file() else None
    return manifest, world, exits[0], nodes, lineage


def salvage(first, second, exit_id, output, *, private_root=PRIVATE_ROOT):
    first, second, output = (Path(value).resolve() for value in (first, second, output))
    for path, label in ((first, "first worker"), (second, "second worker"),
                        (output, "salvage output")):
        require_private(path, private_root, label)
    if first == second or not first.is_dir() or not second.is_dir() or \
            output.exists() or output.is_relative_to(first) or \
            output.is_relative_to(second) or \
            not isinstance(exit_id, str) or len(exit_id) != 64 or any(
                char not in "0123456789abcdef" for char in exit_id):
        raise ValueError("salvage needs two distinct workers and a reviewed exit ID")
    left, right = _worker(first, exit_id), _worker(second, exit_id)
    left_manifest, left_world, left_exit, left_nodes, left_lineage = left
    right_manifest, right_world, right_exit, right_nodes, right_lineage = right
    if any(left_manifest.get(key) != right_manifest.get(key) or
           not left_manifest.get(key) for key in IDENTITY_KEYS) or \
            left_world["level"] != right_world["level"] or \
            left_exit["position"] != right_exit["position"] or \
            (left_lineage is None) != (right_lineage is None) or \
            (left_lineage is not None and
             left_lineage.get("source_manifest_sha256") !=
             right_lineage.get("source_manifest_sha256")):
        raise ValueError("incomplete workers do not share a source identity")
    target = left_exit["position"]
    if len(target) != 3 or not all(math.isfinite(value) for value in target):
        raise ValueError("invalid observed exit position")
    source = left_nodes[0]
    peer_source = right_nodes[0]
    if (source.get("id") != 0 or peer_source.get("id") != 0 or
            any(source.get(key) != peer_source.get(key)
                for key in ("sha256", "position", "counters")) or
            not isinstance(source.get("position"), list) or
            len(source["position"]) != 3 or
            not all(math.isfinite(value) for value in source["position"])):
        raise ValueError("incomplete workers do not share a source checkpoint state")
    source_distance = math.hypot(source["position"][0] - target[0],
                                 source["position"][2] - target[2])
    lookup = {}
    for node in right_nodes:
        counters = node.get("counters", {})
        key = (node.get("sha256"), counters.get("frame"),
               counters.get("polls"), counters.get("player"))
        lookup.setdefault(key, []).append(node)
    ordered = sorted(left_nodes, key=lambda node: (
        math.hypot(node["position"][0] - target[0],
                   node["position"][2] - target[2]), node["id"]))
    for node in ordered:
        counters = node["counters"]
        key = (node["sha256"], counters["frame"], counters["polls"],
               counters["player"])
        for peer in lookup.get(key, ()):
            if node["position"] != peer["position"]:
                continue
            paths = (first / f"checkpoint-{node['slot']}.json",
                     second / f"checkpoint-{peer['slot']}.json")
            for path, manifest, candidate in zip(paths,
                                                  (left_manifest, right_manifest),
                                                  (node, peer)):
                seal = validate_checkpoint(path, manifest)
                if seal.get("rdram_sha256") != candidate["sha256"] or any(
                        seal.get("observation", {}).get(name) != candidate["counters"][name]
                        for name in ("frame", "polls", "player")):
                    raise ValueError("saved search node differs from checkpoint seal")
            samples, _ = selected_polls(first, stop_slot=node["slot"])
            other_samples, _ = selected_polls(second, stop_slot=peer["slot"])
            if samples != other_samples or len(samples) != counters["polls"]:
                continue
            result = {"kind": "jfg-phase95-paired-exploration-checkpoint",
                      "schema": 1, "acceptance": False, "paired": True,
                      "exit_id": exit_id, "source_level": left_world["level"],
                      "exit_position": target, "player_position": node["position"],
                      "source_player_position": source["position"],
                      "source_horizontal_distance": source_distance,
                      "horizontal_distance": math.hypot(
                          node["position"][0] - target[0],
                          node["position"][2] - target[2]),
                      "rdram_sha256": node["sha256"],
                      "frame": counters["frame"], "controller_polls": counters["polls"],
                      "selected_input_sha256": hashlib.sha256(json.dumps(
                          samples, separators=(",", ":")).encode()).hexdigest(),
                      "source_identity": {key: left_manifest[key]
                                          for key in IDENTITY_KEYS},
                      "checkpoint_pointers": [path.relative_to(
                          private_root.resolve()).as_posix() for path in paths],
                      "checkpoint_sha256": [digest(path) for path in paths],
                      "salvage_tool_sha256": digest(Path(__file__)),
                      "source_workers": [str(first), str(second)],
                      "native_parity_verified": False,
                      "limitation": "paired oracle checkpoint only; exit not reached or crossed"}
            output.mkdir(parents=True, exist_ok=False)
            (output / "salvage-result.json").write_text(
                json.dumps(result, indent=2) + "\n")
            return result
    raise ValueError("no identical checkpoint with identical selected input path")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--exit-id", required=True)
    args = parser.parse_args()
    print(json.dumps(salvage(args.first, args.second, args.exit_id, args.output)))


if __name__ == "__main__":
    main()
