"""Attach independently replayed oracle checkpoint segments to a frontier cycle.

This imports spatial progression only. It never marks the selected exit covered.
"""

import argparse
import json
import math
from pathlib import Path

from scripts.phase95_bridge import digest, validate_checkpoint
from scripts.phase95_frontier_cycle import (MAX_SPATIAL_DEPTH, cycle_owner,
                                            graph_pointer, load_state,
                                            resolve_pointer, save_state)
from scripts.phase95_frontier_graph import FrontierGraph
from scripts.phase95_frontier_job import PRIVATE_ROOT, require_private


def _proof(path: Path, private_root: Path) -> dict:
    require_private(path, private_root, "node proof")
    proof = json.loads(path.read_text())
    tool = Path(__file__).with_name("phase95_frontier_verify_node.py")
    if (proof.get("kind") != "jfg-phase95-replayed-frontier-node" or
            proof.get("schema") != 1 or
            proof.get("verification_tool_sha256") != digest(tool) or
            type(proof.get("source_level")) is not int or
            not isinstance(proof.get("exit_id"), str) or
            len(proof["exit_id"]) != 64 or
            type(proof.get("selected_node")) is not int or
            proof["selected_node"] <= 0 or
            type(proof.get("selected_distance")) not in (int, float) or
            not math.isfinite(proof["selected_distance"]) or
            type(proof.get("controller_polls")) is not int or
            proof["controller_polls"] < 0 or
            not isinstance(proof.get("player_position"), list) or
            len(proof["player_position"]) != 3 or
            not all(type(value) in (int, float) and math.isfinite(value)
                    for value in proof["player_position"]) or
            not isinstance(proof.get("source_identity"), dict) or
            not isinstance(proof.get("checkpoint_pointers"), list) or
            len(proof["checkpoint_pointers"]) != 2 or
            not isinstance(proof.get("checkpoint_sha256"), list) or
            len(proof["checkpoint_sha256"]) != 2):
        raise ValueError("invalid independent node proof")
    for pointer, checksum in zip(proof["checkpoint_pointers"],
                                 proof["checkpoint_sha256"]):
        checkpoint = resolve_pointer(pointer, private_root, checksum)
        seal = validate_checkpoint(checkpoint, proof["source_identity"])
        if (seal.get("rdram_sha256") != proof.get("rdram_sha256") or
                seal.get("observation", {}).get("polls") !=
                proof.get("controller_polls")):
            raise ValueError("node proof checkpoint differs from selected state")
    source = resolve_pointer(proof.get("source_checkpoint_pointer"), private_root,
                             proof.get("source_checkpoint_sha256"))
    validate_checkpoint(source, proof["source_identity"])
    proof["source_checkpoint_sha256"] = digest(source)
    return proof


def import_chain(root: Path, output: Path, proofs: list[Path], *,
                 private_root: Path = PRIVATE_ROOT) -> dict:
    root, output, private_root = (Path(path).resolve() for path in
                                  (root, output, private_root))
    require_private(root, private_root, "cycle root")
    require_private(output, private_root, "chain import output")
    if output.parent != root or output.exists() or not proofs or len(proofs) > 4:
        raise ValueError("chain import needs a fresh direct child and 1-4 proofs")
    with cycle_owner(root, private_root):
        state = load_state(root / "state.json", private_root)
        if any(state.get(key) is not None for key in (
                "pending_node_verification", "pending_export",
                "pending_verification", "pending_discovery")):
            raise ValueError("cycle has pending maintenance")
        graph = FrontierGraph.load(resolve_pointer(state["graph"], private_root,
                                                   state["graph_sha256"]))
        paths = [Path(path).resolve() for path in proofs]
        chain = [_proof(path, private_root) for path in paths]
        first = chain[0]
        sources = [node for node in graph.nodes.values()
                   if node["kind"] == "checkpoint" and
                   node["metadata"].get("checkpoint_pointer") ==
                       first["source_checkpoint_pointer"] and
                   node["metadata"].get("checkpoint_sha256") ==
                       first["source_checkpoint_sha256"] and
                   node["metadata"].get("source_level") ==
                       first["source_level"]]
        if len(sources) != 1 or sources[0]["id"] not in graph.reached_nodes("oracle-us"):
            raise ValueError("chain source is not one reached graph checkpoint")
        parent = sources[0]["id"]
        base_edges = [edge for edge in graph.edges.values()
                      if edge["source"] == parent and
                      edge["metadata"].get("driver") == "search-exit" and
                      edge["metadata"].get("exit_id") == first["exit_id"] and
                      "retry_parent" not in edge["metadata"]]
        if len(base_edges) != 1:
            raise ValueError("chain source lacks one matching exit objective")
        base = base_edges[0]
        depth = sources[0]["metadata"].get("salvage_depth", 0)
        if type(depth) is not int or not 0 <= depth <= MAX_SPATIAL_DEPTH - len(chain):
            raise ValueError("chain exceeds spatial depth budget")
        for index, (proof, path) in enumerate(zip(chain, paths)):
            if (proof["source_level"] != first["source_level"] or
                    proof["exit_id"] != first["exit_id"] or
                    proof["source_identity"] != first["source_identity"]):
                raise ValueError("chain proof changed source level, exit, or emulator")
            if index and (proof["source_checkpoint_pointer"] !=
                          chain[index - 1]["checkpoint_pointers"][0] or
                          proof["source_checkpoint_sha256"] !=
                          chain[index - 1]["checkpoint_sha256"][0]):
                raise ValueError("chain checkpoint lineage is discontinuous")
        output.mkdir(parents=True, exist_ok=False)
        registered = []
        for index, (proof, path) in enumerate(zip(chain, paths)):
            checkpoint_sha = proof["checkpoint_sha256"][0]
            node_id = (f"us-level{proof['source_level']}-replayed-"
                       f"{checkpoint_sha[:16]}")
            proof_pointer = graph_pointer(path, private_root)
            graph.add_node(node_id, "checkpoint",
                           label=f"US level {proof['source_level']} replayed route scout",
                           metadata={"checkpoint_pointer": proof["checkpoint_pointers"][0],
                                     "checkpoint_sha256": checkpoint_sha,
                                     "source_level": proof["source_level"],
                                     "paired_node_result": proof_pointer,
                                     "salvage_depth": depth + index + 1,
                                     "distance_to_exit": proof["selected_distance"],
                                     "player_position": proof["player_position"],
                                     "selection": "coverage-import"})
            link = f"{node_id}:from:{parent}"
            graph.add_edge(link, parent, node_id, "progression", priority=0,
                           source_variant="us", source_pointer=proof_pointer,
                           metadata={"predicate": "independent selected-path replay; exit not reached"})
            graph.record(link + ":evidence", link, "oracle-us", "covered",
                         proof_pointer)
            registered.append(node_id)
            parent = node_id
        continuation = f"{parent}:exit-near:{first['exit_id']}"
        spec = {key: value for key, value in base["metadata"].items()
                if key not in ("retry_parent", "retry_tier")}
        spec.update(checkpoint_sha256=chain[-1]["checkpoint_sha256"][0],
                    max_nodes=128, max_expansions=40)
        graph.add_edge(continuation, parent, base["target"], "objective",
                       priority=50, source_variant="us",
                       source_pointer=graph_pointer(paths[-1], private_root),
                       required_capabilities=("search-exit",), metadata=spec)
        graph_path = output / "frontier-graph.json"
        graph.save(graph_path)
        result = {"kind": "jfg-phase95-frontier-imported-chain", "schema": 1,
                  "acceptance": False, "exit_covered": False,
                  "source_node": sources[0]["id"], "checkpoint_nodes": registered,
                  "continuation": continuation,
                  "proof_pointers": [graph_pointer(path, private_root)
                                     for path in paths],
                  "proof_sha256": [digest(path) for path in paths],
                  "graph_sha256": digest(graph_path)}
        result_path = output / "import-result.json"
        result_path.write_text(json.dumps(result, indent=2) + "\n")
        state.update(graph=graph_pointer(graph_path, private_root),
                     graph_sha256=digest(graph_path), status="active")
        state.setdefault("imports", []).append(graph_pointer(result_path, private_root))
        save_state(root / "state.json", state)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("proofs", type=Path, nargs="+")
    args = parser.parse_args()
    print(json.dumps(import_chain(args.root, args.output, args.proofs)))


if __name__ == "__main__":
    main()
