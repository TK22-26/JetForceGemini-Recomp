"""Restartable, bounded US-oracle frontier and optional native diagnostic cycle.

Each state update is durable before the next worker starts; interrupted worker
directories remain as evidence on resume. Native verification does not claim
parity without aligned clocks and validated initial-save/Pak equivalence.
"""

import argparse
from contextlib import contextmanager
from functools import wraps
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import tempfile

from scripts.phase95_bridge import Worker, digest, validate_checkpoint
from scripts.phase95_frontier_discover import run as discover
from scripts.phase95_frontier_graph import FrontierGraph
from scripts.phase95_frontier_job import (PRIVATE_ROOT, add_incomplete_search_retry,
                                         colocated_search_siblings, require_private,
                                         run as search_job, select)
from scripts.phase95_frontier_salvage import salvage as salvage_search
from scripts.phase95_frontier_verify_node import (_nodes as saved_search_nodes,
                                                  verify as verify_search_node)
from scripts.phase95_export_inputs import export as export_inputs
from scripts.phase95_route_verifier import verify as verify_route


KIND = "jfg-phase95-frontier-cycle"
MAX_SPATIAL_DEPTH = 64


@contextmanager
def cycle_owner(root, private_root=PRIVATE_ROOT):
    """Serialize every writer of one cycle, including manual and ledger runs.

    Keep the lock file beside the cycle so a first writer can own it before
    creating the cycle directory. The OS releases the byte-range lock on exit
    or process death; the harmless file is deliberately not unlinked.
    """
    root = Path(root)
    require_private(root, private_root, "cycle output")
    lock = root.with_name(root.name + ".cycle.lock")
    require_private(lock, private_root, "cycle lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError("another writer owns this frontier cycle") from error
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError("another writer owns this frontier cycle") from error
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def owned_cycle(function):
    @wraps(function)
    def wrapped(root, *args, **kwargs):
        with cycle_owner(root, kwargs.get("private_root", PRIVATE_ROOT)):
            return function(root, *args, **kwargs)
    return wrapped


def resolve_pointer(pointer, private_root, expected_sha256=None):
    if not isinstance(pointer, str) or not pointer or \
            PureWindowsPath(pointer).drive or PurePosixPath(pointer).is_absolute() or \
            ".." in PurePosixPath(pointer).parts or "\\" in pointer:
        raise ValueError("invalid private checkpoint pointer")
    if expected_sha256 is not None and (not isinstance(expected_sha256, str) or
            len(expected_sha256) != 64 or any(
                char not in "0123456789abcdef" for char in expected_sha256)):
        raise ValueError("invalid pointer seal")
    path = private_root / pointer
    require_private(path, private_root, "checkpoint pointer")
    if expected_sha256 is not None and digest(path) != expected_sha256:
        raise ValueError("checkpoint pointer seal mismatch")
    return path


def graph_pointer(path, private_root):
    require_private(path, private_root, "graph")
    return path.resolve().relative_to(private_root.resolve()).as_posix()


def save_state(path, state):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_state(path, private_root):
    state = json.loads(path.read_text())
    if state.get("kind") != KIND or state.get("schema") != 1 or \
            type(state.get("next_index")) is not int or state["next_index"] < 0 or \
            type(state.get("attempt")) is not int or state["attempt"] < 0 or \
            not isinstance(state.get("jobs"), list) or \
            not isinstance(state.get("graph_sha256"), str):
        raise ValueError("invalid frontier cycle state")
    current = resolve_pointer(state.get("graph"), private_root,
                              state.get("graph_sha256"))
    FrontierGraph.load(current)
    return state


def requeue_legacy_incomplete(state, current_graph, root, private_root):
    """Migrate sealed bounded-search misses made before retry edges existed."""
    graph = FrontierGraph.load(current_graph)
    updates = {}
    for index, job in enumerate(state["jobs"]):
        if job.get("outcome") != "blocked" or "retry_edge" in job:
            continue
        result_path = resolve_pointer(job["result"], private_root)
        result = json.loads(result_path.read_text())
        if result.get("reason") != \
                "ObservationError: bounded exploration incomplete; not proof of unreachable exit":
            continue
        edge = graph.edges.get(job["edge"])
        if edge is None or edge["metadata"].get("driver") != "search-exit":
            continue
        retry = None
        world_path = result_path.parent / "attempt-01" / "world-inventory.json"
        if world_path.is_file():
            siblings = colocated_search_siblings(
                graph, edge, json.loads(world_path.read_text()))
            queued = [candidate for candidate, _ in siblings
                      if "retry_tier" in candidate["metadata"] and
                      graph.status(candidate["id"], "oracle-us") == "unexplored"]
            if queued:
                retry = min(queued, key=lambda candidate: (
                    candidate["priority"], candidate["id"]))["id"]
        own_retry = result.get("retry_edge_id")
        if retry is not None and own_retry is not None and own_retry != retry:
            if own_retry not in graph.edges or \
                    graph.edges[own_retry]["metadata"].get("retry_parent") != edge["id"]:
                raise ValueError("legacy own retry does not match blocked objective")
            graph.record(f"legacy-colocated-supersede-{index}", own_retry,
                         "oracle-us", "blocked", job["result"],
                         reason="co-located retry superseded by another queued search")
        if retry is None and own_retry is not None:
            if own_retry not in graph.edges or \
                    graph.edges[own_retry]["metadata"].get("retry_parent") != edge["id"]:
                raise ValueError("legacy own retry does not match blocked objective")
            retry = own_retry
        if retry is None:
            retry = add_incomplete_search_retry(graph, edge, result_path.parent)
        if retry is not None:
            updates[index] = retry
    if not updates:
        return False
    output = root / f"retry-legacy-{state['next_index']:04d}.json"
    if output.exists():
        if FrontierGraph.load(output).to_dict() != graph.to_dict():
            raise ValueError("legacy retry graph changed after interruption")
    else:
        graph.save(output)
    for index, retry in updates.items():
        state["jobs"][index]["retry_edge"] = retry
    state.update(graph=graph_pointer(output, private_root), graph_sha256=digest(output))
    save_state(root / "state.json", state)
    return True


def promote_paired_search(state, current_graph, root, private_root,
                          salvager=salvage_search):
    """Turn two agreeing incomplete searches into a new spatial frontier.

    This proves only that ordinary input reaches a reusable checkpoint closer
    to the observed exit. The original exit edges remain blocked/incomplete.
    """
    graph = FrontierGraph.load(current_graph)
    handled = {tuple(item["jobs"]) for item in state.setdefault("salvages", [])}
    for second in range(len(state["jobs"])):
        newer = state["jobs"][second]
        edge = graph.edges.get(newer["edge"])
        if newer.get("outcome") != "blocked" or edge is None or \
                edge["metadata"].get("driver") != "search-exit":
            continue
        spec = edge["metadata"]
        for first in range(second - 1, -1, -1):
            older = state["jobs"][first]
            parent = graph.edges.get(older["edge"])
            if (first, second) in handled or older.get("outcome") != "blocked" or \
                    parent is None or parent["metadata"].get("driver") != "search-exit" or \
                    parent["source"] != edge["source"] or \
                    parent["target"] != edge["target"] or \
                    parent["metadata"].get("exit_id") != spec["exit_id"] or \
                    parent["metadata"].get("checkpoint_sha256") != \
                    spec["checkpoint_sha256"]:
                continue
            first_root = resolve_pointer(older["result"], private_root).parent / "attempt-01"
            second_root = resolve_pointer(newer["result"], private_root).parent / "attempt-01"
            failures = [path / "search-failure.json" for path in
                        (first_root, second_root)]
            if not all(path.is_file() for path in failures):
                continue
            if any(json.loads(path.read_text()).get("reason") !=
                   "bounded search exhausted" for path in failures):
                continue
            state["attempt"] += 1
            save_state(root / "state.json", state)
            output = root / f"salvage-{first:04d}-{second:04d}-{state['attempt']:02d}"
            try:
                pair = salvager(first_root, second_root, spec["exit_id"], output,
                                private_root=private_root)
            except ValueError as error:
                if "no identical checkpoint with identical selected input path" not in str(error):
                    raise
                pair = None
            status = "no_pair" if pair is None else "no_progress"
            continuation = None
            if pair is not None:
                path = output / "salvage-result.json"
                if (not path.is_file() or json.loads(path.read_text()) != pair or
                        pair.get("kind") != "jfg-phase95-paired-exploration-checkpoint" or
                        pair.get("schema") != 1 or pair.get("paired") is not True or
                        pair.get("exit_id") != spec["exit_id"] or
                        pair.get("source_level") != graph.nodes[edge["source"]]["metadata"].get(
                            "source_level") or
                        pair.get("salvage_tool_sha256") != digest(
                            Path(__file__).with_name("phase95_frontier_salvage.py")) or
                        type(pair.get("horizontal_distance")) not in (int, float) or
                        type(pair.get("source_horizontal_distance")) not in (int, float) or
                        not math.isfinite(pair["horizontal_distance"]) or
                        not math.isfinite(pair["source_horizontal_distance"]) or
                        len(pair.get("checkpoint_pointers", ())) != 2 or
                        len(pair.get("checkpoint_sha256", ())) != 2):
                    raise ValueError("paired search artifact has invalid provenance")
                for pointer, checksum in zip(pair["checkpoint_pointers"],
                                             pair["checkpoint_sha256"]):
                    checkpoint = resolve_pointer(pointer, private_root, checksum)
                    seal = validate_checkpoint(checkpoint, pair["source_identity"])
                    if (seal["rdram_sha256"] != pair["rdram_sha256"] or
                            seal["observation"]["polls"] != pair["controller_polls"]):
                        raise ValueError("paired search checkpoint differs from artifact")
                depth = graph.nodes[edge["source"]]["metadata"].get("salvage_depth", 0)
                if type(depth) is not int or not 0 <= depth <= MAX_SPATIAL_DEPTH:
                    raise ValueError("invalid spatial frontier depth")
                if depth < MAX_SPATIAL_DEPTH and pair["horizontal_distance"] <= \
                        pair["source_horizontal_distance"] - 60:
                    checkpoint_sha = pair["checkpoint_sha256"][0]
                    node_id = (f"us-level{pair['source_level']}-paired-"
                               f"{checkpoint_sha[:16]}")
                    result_pointer = graph_pointer(path, private_root)
                    graph.add_node(node_id, "checkpoint",
                                   label=f"US level {pair['source_level']} paired spatial checkpoint",
                                   metadata={
                                       "checkpoint_sha256": checkpoint_sha,
                                       "checkpoint_pointer": pair["checkpoint_pointers"][0],
                                       "source_level": pair["source_level"],
                                       "paired_salvage_result": result_pointer,
                                       "salvage_depth": depth + 1,
                                       "horizontal_distance": pair["horizontal_distance"]})
                    link = f"{node_id}:from:{edge['source']}"
                    graph.add_edge(link, edge["source"], node_id, "progression",
                                   priority=0, source_variant="us",
                                   source_pointer=result_pointer,
                                   metadata={"predicate": "paired identical selected-input checkpoint; exit not reached"})
                    graph.record(link + ":evidence", link, "oracle-us", "covered",
                                 result_pointer)
                    continuation = f"{node_id}:exit-near:{spec['exit_id']}"
                    next_spec = {key: value for key, value in spec.items()
                                 if key not in ("retry_parent", "retry_tier")}
                    next_spec.update(checkpoint_sha256=checkpoint_sha,
                                     max_nodes=128, max_expansions=40)
                    graph.add_edge(continuation, node_id, edge["target"], "objective",
                                   priority=100, source_variant="us",
                                   source_pointer=result_pointer,
                                   required_capabilities=("search-exit",),
                                   metadata=next_spec)
                    new_graph = root / (f"salvage-graph-{first:04d}-{second:04d}-"
                                        f"{state['attempt']:02d}.json")
                    graph.save(new_graph)
                    state.update(graph=graph_pointer(new_graph, private_root),
                                 graph_sha256=digest(new_graph))
                    status = "promoted"
            state["salvages"].append({"jobs": [first, second], "status": status,
                                       "artifact": (graph_pointer(output / "salvage-result.json",
                                                                  private_root)
                                                    if pair is not None else None),
                                       "continuation": continuation})
            state["attempt"] = 0
            save_state(root / "state.json", state)
            return True
    return False


def queue_node_verification(state, current_graph, root, private_root):
    """Persist exit progress or a novel detour for independent replay."""
    graph = FrontierGraph.load(current_graph)
    paired_jobs = {index for item in state.get("salvages", [])
                   if item.get("status") == "promoted" for index in item["jobs"]}
    verified_positions = []
    for verified_job_index, job in enumerate(state["jobs"]):
        pointers = ([job["verified_node"]] if "verified_node" in job else [])
        pointers.extend(job.get("additional_verified_nodes", ()))
        for pointer in pointers:
            proof = json.loads(resolve_pointer(pointer, private_root).read_text())
            position = proof.get("player_position")
            if (proof.get("kind") != "jfg-phase95-replayed-frontier-node" or
                    type(proof.get("source_level")) is not int or
                    not isinstance(position, list) or len(position) != 3 or
                    not all(type(value) in (int, float) and math.isfinite(value)
                            for value in position)):
                raise ValueError("verified spatial node has invalid position")
            verified_positions.append((verified_job_index, proof["source_level"],
                                       position))
    observed_positions = []
    for observed_job_index, job in enumerate(state["jobs"]):
        if not job.get("result"):
            continue
        result_path = resolve_pointer(job["result"], private_root)
        worker = result_path.parent / "attempt-01"
        failure_path = worker / "search-failure.json"
        objective_path = worker / "search-objective.json"
        if not (failure_path.is_file() and objective_path.is_file() and
                (worker / "search-nodes.jsonl").is_file()):
            continue
        result = json.loads(result_path.read_text())
        failure = json.loads(failure_path.read_text())
        objective = json.loads(objective_path.read_text())
        identity = objective.get("exit_identity", {})
        if (result.get("planner_source_stable") is not True or
                failure.get("reason") != "bounded search exhausted" or
                type(identity.get("source_level")) is not int or
                not isinstance(identity.get("id"), str)):
            continue
        for node in saved_search_nodes(worker):
            observed_positions.append((observed_job_index,
                                       identity["source_level"], identity["id"],
                                       node["position"]))
    candidates = []
    for index, job in enumerate(state["jobs"]):
        if index in paired_jobs or job.get("outcome") != "blocked":
            continue
        own_positions = [(level, position) for owner, level, position
                         in verified_positions if owner == index]
        if len(own_positions) >= 2:
            continue
        if own_positions and not any(
                owner != index and level == own_positions[0][0] and
                math.hypot(position[0] - own_positions[0][1][0],
                           position[2] - own_positions[0][1][2]) < 180
                for owner, level, position in verified_positions):
            continue
        edge = graph.edges.get(job["edge"])
        if edge is None or edge["metadata"].get("driver") != "search-exit":
            continue
        depth = graph.nodes[edge["source"]]["metadata"].get("salvage_depth", 0)
        if type(depth) is not int or not 0 <= depth <= MAX_SPATIAL_DEPTH:
            raise ValueError("invalid spatial frontier depth")
        if depth == MAX_SPATIAL_DEPTH:
            continue
        result_path = resolve_pointer(job["result"], private_root)
        result = json.loads(result_path.read_text())
        worker = result_path.parent / "attempt-01"
        failure_path = worker / "search-failure.json"
        if (result.get("planner_source_stable") is not True or
                not failure_path.is_file() or
                json.loads(failure_path.read_text()).get("reason") !=
                "bounded search exhausted"):
            continue
        nodes = saved_search_nodes(worker)
        objective = json.loads((worker / "search-objective.json").read_text())
        source_level = objective.get("exit_identity", {}).get("source_level")
        exit_id = objective.get("exit_identity", {}).get("id")
        if type(source_level) is not int:
            raise ValueError("search lacks source level")
        def spatially_novel(node):
            return all(level != source_level or math.hypot(
                node["position"][0] - position[0],
                node["position"][2] - position[2]) >= 180
                for _, level, position in verified_positions) and all(
                owner == index or level != source_level or prior_exit != exit_id or
                math.hypot(node["position"][0] - position[0],
                           node["position"][2] - position[2]) >= 60
                for owner, level, prior_exit, position in observed_positions)
        available = [node for node in nodes[1:] if spatially_novel(node)]
        if not available:
            continue
        best = min(available, key=lambda node: (node["distance"], node["id"]))
        improvement = nodes[0]["distance"] - best["distance"]
        if improvement >= 60:
            candidates.append((0, -improvement, index, best["id"], worker,
                               "exit-progress"))
            continue
        if objective.get("search_mode") != "detour":
            continue
        source_position = nodes[0]["position"]
        def displacement(node):
            return math.hypot(node["position"][0] - source_position[0],
                              node["position"][2] - source_position[2])
        novel = [node for node in available if displacement(node) >= 240]
        if novel:
            chosen = min(novel, key=lambda node: (-displacement(node),
                                                  node["distance"], node["id"]))
            candidates.append((1, -displacement(chosen), index, chosen["id"],
                               worker, "spatial-detour"))
    if not candidates:
        return False
    _, _, index, node_id, worker, selection = min(candidates)
    prior_replays = sum(owner == index for owner, _, _ in verified_positions)
    state["pending_node_verification"] = {
        "job_index": index, "attempt": prior_replays, "node_id": node_id,
        "selection": selection,
        "worker_pointer": graph_pointer(worker, private_root)}
    save_state(root / "state.json", state)
    return True


def promote_replayed_node(state, current_graph, root, private_root,
                          emulator, rom, script, rom_sha256,
                          verifier=verify_search_node):
    """Finish a durable selected-node replay and expose its next search edge."""
    pending = state["pending_node_verification"]
    index = pending["job_index"]
    if type(index) is not int or not 0 <= index < len(state["jobs"]):
        raise ValueError("pending node verification has no source job")
    source = resolve_pointer(pending["worker_pointer"], private_root)
    graph = FrontierGraph.load(current_graph)
    job = state["jobs"][index]
    edge = graph.edges[job["edge"]]
    nodes = saved_search_nodes(source)
    if (type(pending.get("node_id")) is not int or
            not 0 < pending["node_id"] < len(nodes)):
        raise ValueError("pending node ID is invalid")
    source_position = nodes[0]["position"]
    selected = nodes[pending["node_id"]]
    displacement = math.hypot(selected["position"][0] - source_position[0],
                              selected["position"][2] - source_position[2])
    selection = pending.get("selection", "exit-progress")
    objective = json.loads((source / "search-objective.json").read_text())
    if selection == "exit-progress":
        valid_selection = nodes[0]["distance"] - selected["distance"] >= 60
    elif selection == "spatial-detour":
        valid_selection = (objective.get("search_mode") == "detour" and
                           displacement >= 240)
    else:
        valid_selection = False
    if not valid_selection:
        raise ValueError("pending spatial node does not meet selection rule")
    pending["attempt"] += 1
    save_state(root / "state.json", state)
    output = root / f"node-verify-{index:04d}-{pending['attempt']:02d}"
    proof = verifier(source, output, emulator, rom, script, rom_sha256,
                     node_id=pending["node_id"], private_root=private_root)
    path = output / "verification-result.json"
    if (not path.is_file() or json.loads(path.read_text()) != proof or
            proof.get("kind") != "jfg-phase95-replayed-frontier-node" or
            proof.get("schema") != 1 or proof.get("selected_node") != pending["node_id"] or
            proof.get("source_worker") != str(source) or
            proof.get("exit_id") != edge["metadata"]["exit_id"] or
            proof.get("source_level") != graph.nodes[edge["source"]]["metadata"].get(
                "source_level") or
            proof.get("verification_tool_sha256") != digest(
                Path(__file__).with_name("phase95_frontier_verify_node.py")) or
            type(proof.get("selected_distance")) not in (int, float) or
            type(proof.get("source_distance")) not in (int, float) or
            not math.isfinite(proof["selected_distance"]) or
            not math.isfinite(proof["source_distance"]) or
            proof["source_distance"] != nodes[0]["distance"] or
            proof["selected_distance"] != selected["distance"] or
            proof.get("player_position") != selected["position"] or
            len(proof.get("checkpoint_pointers", ())) != 2 or
            len(proof.get("checkpoint_sha256", ())) != 2):
        raise ValueError("independent node replay has invalid provenance")
    for pointer, checksum in zip(proof["checkpoint_pointers"],
                                 proof["checkpoint_sha256"]):
        checkpoint = resolve_pointer(pointer, private_root, checksum)
        seal = validate_checkpoint(checkpoint, proof["source_identity"])
        if (seal["rdram_sha256"] != proof["rdram_sha256"] or
                seal["observation"]["polls"] != proof["controller_polls"]):
            raise ValueError("independent node checkpoint differs from proof")
    depth = graph.nodes[edge["source"]]["metadata"].get("salvage_depth", 0)
    if type(depth) is not int or not 0 <= depth < MAX_SPATIAL_DEPTH:
        raise ValueError("invalid replayed spatial frontier depth")
    checkpoint_sha = proof["checkpoint_sha256"][0]
    node_id = f"us-level{proof['source_level']}-replayed-{checkpoint_sha[:16]}"
    pointer = graph_pointer(path, private_root)
    graph.add_node(node_id, "checkpoint",
                   label=f"US level {proof['source_level']} replayed spatial checkpoint",
                   metadata={"checkpoint_sha256": checkpoint_sha,
                             "checkpoint_pointer": proof["checkpoint_pointers"][0],
                             "source_level": proof["source_level"],
                             "paired_node_result": pointer,
                             "salvage_depth": depth + 1,
                             "distance_to_exit": proof["selected_distance"],
                             "player_position": proof["player_position"],
                             "horizontal_displacement": displacement,
                             "selection": selection})
    link = f"{node_id}:from:{edge['source']}"
    graph.add_edge(link, edge["source"], node_id, "progression", priority=0,
                   source_variant="us", source_pointer=pointer,
                   metadata={"predicate": "independent selected-path replay; exit not reached",
                             "selection": selection})
    graph.record(link + ":evidence", link, "oracle-us", "covered", pointer)
    continuation = f"{node_id}:exit-near:{proof['exit_id']}"
    next_spec = {key: value for key, value in edge["metadata"].items()
                 if key not in ("retry_parent", "retry_tier")}
    next_spec.update(checkpoint_sha256=checkpoint_sha,
                     max_nodes=128, max_expansions=40)
    graph.add_edge(continuation, node_id, edge["target"], "objective",
                   priority=(50 if "verified_node" in job else 100),
                   source_variant="us", source_pointer=pointer,
                   required_capabilities=("search-exit",), metadata=next_spec)
    new_graph = output / "frontier-graph.json"
    graph.save(new_graph)
    state.update(graph=graph_pointer(new_graph, private_root),
                 graph_sha256=digest(new_graph), pending_node_verification=None,
                 status="active")
    if "verified_node" in job:
        job.setdefault("additional_verified_nodes", []).append(pointer)
        job.setdefault("additional_continuations", []).append(continuation)
    else:
        job["verified_node"] = pointer
        job["continuation"] = continuation
    save_state(root / "state.json", state)


@owned_cycle
def run(root, emulator, rom, script, rom_sha256, *, graph_path=None,
        resume=False, max_jobs=1, private_root=PRIVATE_ROOT,
        job_runner=search_job, discoverer=discover, exporter=export_inputs,
        verifier=verify_route, salvager=salvage_search,
        node_verifier=verify_search_node,
        initial_flash=None, initial_pak=None,
        executable=None, verify_repeats=1, worker_type=Worker):
    require_private(root, private_root, "cycle output")
    if type(max_jobs) is not int or not 0 <= max_jobs <= 1000:
        raise ValueError("invalid cycle job budget")
    if type(verify_repeats) is not int or not 1 <= verify_repeats <= 10:
        raise ValueError("invalid oracle repeat count")
    state_path = root / "state.json"
    if resume:
        if graph_path is not None or not state_path.is_file() or any(
                value is not None for value in (initial_flash, initial_pak, executable)):
            raise ValueError("resume requires existing state without new graph or verification pins")
        state = load_state(state_path, private_root)
    else:
        if graph_path is None:
            raise ValueError("a graph is required for a new cycle")
        require_private(graph_path, private_root, "graph")
        FrontierGraph.load(graph_path)
        verification = None
        supplied = (initial_flash, initial_pak, executable)
        if any(value is not None for value in supplied):
            if any(value is None for value in supplied):
                raise ValueError("native diagnostics require flash, pak, and executable together")
            flash, pak, binary = (Path(value).resolve() for value in supplied)
            if not flash.is_file() or flash.stat().st_size != 0x20000 or \
                    not pak.is_file() or pak.stat().st_size != 32 or not binary.is_file():
                raise ValueError("invalid native diagnostic save/Pak or executable")
            verification = {"initial_flash": str(flash), "flash_sha256": digest(flash),
                            "initial_pak": str(pak), "pak_sha256": digest(pak),
                            "executable": str(binary), "executable_sha256": digest(binary),
                            "repeats": verify_repeats}
        root.mkdir(parents=True, exist_ok=False)
        state = {"kind": KIND, "schema": 1, "acceptance": False,
                 "graph": graph_pointer(graph_path, private_root),
                 "graph_sha256": digest(graph_path), "next_index": 0,
                 "attempt": 0, "pending_export": None, "pending_verification": None,
                 "pending_discovery": None, "pending_node_verification": None,
                 "jobs": [], "salvages": [],
                 "verification": verification, "status": "active"}
        save_state(state_path, state)
    executed = 0
    while True:
        current_graph = resolve_pointer(state["graph"], private_root,
                                        state["graph_sha256"])
        if state.get("pending_node_verification") is not None:
            promote_replayed_node(state, current_graph, root, private_root,
                                  emulator, rom, script, rom_sha256,
                                  verifier=node_verifier)
            continue
        pending_export = state.get("pending_export")
        if pending_export is not None:
            source = resolve_pointer(pending_export["worker_pointer"], private_root)
            if not source.is_dir() or pending_export["job_index"] >= len(state["jobs"]):
                raise ValueError("pending input export has no completed source job")
            pending_export["attempt"] += 1
            save_state(state_path, state)
            export_root = root / (f"export-{pending_export['job_index']:04d}-"
                                  f"{pending_export['attempt']:02d}")
            verification = state.get("verification")
            if verification is not None:
                flash = Path(verification["initial_flash"])
                pak = Path(verification["initial_pak"])
                if digest(flash) != verification["flash_sha256"] or \
                        digest(pak) != verification["pak_sha256"]:
                    raise ValueError("native diagnostic candidate save/Pak pin changed")
                manifest = exporter(source, export_root, initial_flash=flash,
                                    initial_pak=pak)
            else:
                manifest = exporter(source, export_root)
            saved_manifest = json.loads((export_root / "export-manifest.json").read_text())
            if manifest != saved_manifest or \
                    manifest.get("kind") != "jfg-phase95-selected-input-export" or \
                    manifest.get("input_sha256") != digest(export_root / "controller.input"):
                raise ValueError("selected input export did not seal controller input")
            if verification is not None:
                initial = manifest.get("initial_state") or {}
                if initial.get("flash_sha256") != verification["flash_sha256"] or \
                        initial.get("pak_sha256") != verification["pak_sha256"]:
                    raise ValueError("selected input export changed candidate save/Pak")
            state["jobs"][pending_export["job_index"]]["selected_input"] = graph_pointer(
                export_root / "export-manifest.json", private_root)
            if verification is not None:
                state["pending_verification"] = {
                    "job_index": pending_export["job_index"], "attempt": 0,
                    "source_pointer": graph_pointer(source, private_root),
                    "export_pointer": graph_pointer(export_root, private_root),
                    "input_sha256": manifest["input_sha256"]}
            state["pending_export"] = None
            save_state(state_path, state)
            continue
        pending_verify = state.get("pending_verification")
        if pending_verify is not None:
            verification = state.get("verification")
            if verification is None or pending_verify["job_index"] >= len(state["jobs"]):
                raise ValueError("pending native diagnostic lacks a covered source job")
            source = resolve_pointer(pending_verify["source_pointer"], private_root)
            exported = resolve_pointer(pending_verify["export_pointer"], private_root)
            if digest(exported / "controller.input") != pending_verify["input_sha256"] or \
                    digest(Path(verification["initial_flash"])) != verification["flash_sha256"] or \
                    digest(Path(verification["initial_pak"])) != verification["pak_sha256"] or \
                    digest(Path(verification["executable"])) != verification["executable_sha256"]:
                raise ValueError("native diagnostic source or toolchain pin changed")
            pending_verify["attempt"] += 1
            save_state(state_path, state)
            output = root / (f"verify-{pending_verify['job_index']:04d}-"
                             f"{pending_verify['attempt']:02d}")
            try:
                result = verifier(exported, source / "scenario-result.json", output,
                                  emulator, rom, rom_sha256,
                                  Path(verification["executable"]),
                                  repeats=verification["repeats"])
            except Exception:
                failure_path = output / "verification-failure.json"
                if not failure_path.is_file():
                    raise
                failure = json.loads(failure_path.read_text())
                if failure.get("completed") is not False or \
                        failure.get("rom_sha256") != rom_sha256 or \
                        failure.get("native_executable_sha256") != verification["executable_sha256"] or \
                        failure.get("contract", {}).get("input_sha256") != \
                        pending_verify["input_sha256"]:
                    raise ValueError("native diagnostic failure artifact has stale pins")
                state["jobs"][pending_verify["job_index"]]["verification_failure"] = \
                    graph_pointer(failure_path, private_root)
                state["pending_verification"] = None
                save_state(state_path, state)
                continue
            result_path = output / "verification-result.json"
            if result.get("completed") is not True or \
                    type(result.get("native_parity_verified")) is not bool or \
                    not result_path.is_file() or json.loads(result_path.read_text()) != result:
                raise ValueError("native diagnostic did not produce a bounded result")
            state["jobs"][pending_verify["job_index"]]["verification"] = graph_pointer(
                result_path, private_root)
            state["pending_verification"] = None
            save_state(state_path, state)
            continue
        pending = state["pending_discovery"]
        if pending is not None:
            checkpoint = resolve_pointer(pending["checkpoint_pointer"], private_root,
                                         pending["checkpoint_sha256"])
            graph = FrontierGraph.load(current_graph)
            node = graph.nodes.get(pending["checkpoint_node"])
            if node is None or node["metadata"].get("checkpoint_sha256") != \
                    pending["checkpoint_sha256"] or \
                    pending["checkpoint_node"] not in graph.reached_nodes("oracle-us"):
                raise ValueError("pending discovery checkpoint is not reached")
            state["attempt"] += 1
            save_state(state_path, state)
            output = root / f"discover-{pending['job_index']:04d}-{state['attempt']:02d}"
            result = discoverer(checkpoint, output, emulator, rom, script, rom_sha256,
                                graph_path=current_graph,
                                checkpoint_node=pending["checkpoint_node"],
                                worker_type=worker_type, private_root=private_root)
            if not result["deterministic"]:
                raise RuntimeError("independent frontier discovery disagreed; state is resumable")
            new_graph = output / "frontier-graph.json"
            state.update(graph=graph_pointer(new_graph, private_root),
                         graph_sha256=digest(new_graph), pending_discovery=None,
                         attempt=0)
            save_state(state_path, state)
            continue
        if requeue_legacy_incomplete(state, current_graph, root, private_root):
            continue
        if queue_node_verification(state, current_graph, root, private_root):
            continue
        if promote_paired_search(state, current_graph, root, private_root,
                                 salvager=salvager):
            continue
        if executed >= max_jobs:
            state["status"] = "budget_exhausted"
            save_state(state_path, state)
            return state
        graph = FrontierGraph.load(current_graph)
        try:
            edge = select(graph)
        except ValueError as error:
            if "no reachable uncovered" not in str(error):
                raise
            state["status"] = "frontier_exhausted"
            save_state(state_path, state)
            return state
        source = graph.nodes[edge["source"]]
        pointer = source["metadata"].get("checkpoint_pointer")
        checkpoint = resolve_pointer(pointer, private_root,
                                     edge["metadata"]["checkpoint_sha256"])
        state["attempt"] += 1
        save_state(state_path, state)
        index = state["next_index"]
        suffix = f"{index:04d}-{state['attempt']:02d}"
        output = root / f"job-{suffix}"
        label = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:8]
        result = job_runner(current_graph, output, checkpoint, emulator, rom,
                            script, rom_sha256, f"cycle-{label}-{suffix}",
                            worker_type=worker_type, private_root=private_root)
        new_graph = output / "frontier-evidence.json"
        pending = None
        if "next_checkpoint" in result:
            next_checkpoint = result["next_checkpoint"]
            pending = {"job_index": index,
                       "checkpoint_node": next_checkpoint["node"],
                       "checkpoint_pointer": graph_pointer(
                           output / next_checkpoint["pointer"], private_root),
                       "checkpoint_sha256": next_checkpoint["checkpoint_sha256"]}
        state.update(graph=graph_pointer(new_graph, private_root),
                     graph_sha256=digest(new_graph), next_index=index + 1,
                     attempt=0, pending_discovery=pending,
                     pending_export=({"job_index": index, "attempt": 0,
                                      "worker_pointer": graph_pointer(
                                          output / "attempt-01", private_root)}
                                     if result["outcome"] == "covered" else None),
                     status="active")
        state["jobs"].append({"index": index, "edge": result["edge_id"],
                              "outcome": result["outcome"],
                              "result": graph_pointer(output / "result.json", private_root)})
        save_state(state_path, state)
        executed += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-jobs", type=int, default=1)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--initial-flash", type=Path)
    parser.add_argument("--initial-pak", type=Path)
    parser.add_argument("--executable", type=Path)
    parser.add_argument("--verify-repeats", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.emulator, args.rom, args.script,
                         args.rom_sha256, graph_path=args.graph, resume=args.resume,
                         max_jobs=args.max_jobs, initial_flash=args.initial_flash,
                         initial_pak=args.initial_pak, executable=args.executable,
                         verify_repeats=args.verify_repeats), sort_keys=True))


if __name__ == "__main__":
    main()
