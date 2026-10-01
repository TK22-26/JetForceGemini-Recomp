"""Synthetic cycle tests; no BizHawk worker is launched."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.phase95_bridge import digest
from scripts.phase95_frontier_cycle import (queue_node_verification,
                                            promote_replayed_node,
                                            requeue_legacy_incomplete,
                                            resolve_pointer, run)
from scripts.phase95_frontier_graph import FrontierGraph
from scripts.phase95_frontier_job import select


def seed(root):
    checkpoint = root / "seed-checkpoint.json"
    checkpoint.write_text("synthetic checkpoint")
    graph = FrontierGraph()
    graph.add_node("seed", "checkpoint", metadata={
        "checkpoint_sha256": digest(checkpoint),
        "checkpoint_pointer": checkpoint.name})
    graph.add_node("near", "objective")
    graph.add_edge("near", "seed", "near", "objective", source_variant="us",
                   required_capabilities=("navigate",),
                   metadata={"driver": "navigate", "target_name": "longwoodbridge",
                             "max_steps": 1, "radius": 60,
                             "checkpoint_sha256": digest(checkpoint)})
    graph.add_entrypoint("oracle-us", "seed")
    graph_path = root / "seed-graph.json"
    graph.save(graph_path)
    return graph_path, checkpoint


class SyntheticJob:
    def __init__(self, private_root):
        self.private_root = private_root
        self.calls = []

    def __call__(self, graph_path, output, checkpoint, *_args, **_kwargs):
        self.calls.append(checkpoint)
        output.mkdir()
        (output / "attempt-01").mkdir()
        (output / "attempt-01" / "scenario-result.json").write_text(
            json.dumps({"completed": True}))
        graph = FrontierGraph.load(graph_path)
        graph.record(f"job-{len(self.calls)}", "near", "oracle-us", "covered", "result.json")
        next_checkpoint = output / "checkpoint-c1.json"
        next_checkpoint.write_text("synthetic next checkpoint")
        graph.add_node("next", "checkpoint", metadata={
            "checkpoint_sha256": digest(next_checkpoint),
            "checkpoint_pointer": next_checkpoint.relative_to(self.private_root).as_posix()})
        graph.add_edge("checkpoint-link", "near", "next", "progression",
                       source_variant="us")
        graph.record("checkpoint-result", "checkpoint-link", "oracle-us", "covered",
                     "result.json")
        graph.save(output / "frontier-evidence.json")
        result = {"edge_id": "near", "outcome": "covered",
                  "next_checkpoint": {"node": "next", "pointer": "checkpoint-c1.json",
                                      "checkpoint_sha256": digest(next_checkpoint)}}
        (output / "result.json").write_text(json.dumps(result))
        return result


class SyntheticDiscover:
    def __init__(self):
        self.calls = 0
        self.fail_once = False

    def __call__(self, checkpoint, output, *_args, graph_path, checkpoint_node,
                 **_kwargs):
        self.calls += 1
        if self.fail_once and self.calls == 1:
            output.mkdir()
            raise RuntimeError("synthetic interruption")
        output.mkdir()
        self_checkpoint = FrontierGraph.load(graph_path)
        assert checkpoint_node == "next"
        assert digest(checkpoint) == self_checkpoint.nodes["next"]["metadata"]["checkpoint_sha256"]
        self_checkpoint.add_node("new-exit", "branch")
        self_checkpoint.add_edge("new-exit", "next", "new-exit", "objective",
                                 source_variant="us", required_capabilities=("search-exit",))
        self_checkpoint.save(output / "frontier-graph.json")
        return {"deterministic": True}


class SyntheticExport:
    def __init__(self):
        self.calls = 0
        self.fail_once = False

    def __call__(self, source, output, *, initial_flash=None, initial_pak=None):
        self.calls += 1
        assert source.name.startswith("attempt-") or source.parent.name.startswith("job-")
        output.mkdir()
        if self.fail_once and self.calls == 1:
            raise RuntimeError("synthetic export interruption")
        (output / "controller.input").write_text("synthetic selected input")
        result = {"kind": "jfg-phase95-selected-input-export",
                  "input_sha256": digest(output / "controller.input")}
        if initial_flash is not None:
            (output / "initial.flash").write_bytes(initial_flash.read_bytes())
            (output / "initial.pak").write_bytes(initial_pak.read_bytes())
            result["initial_state"] = {"flash_sha256": digest(output / "initial.flash"),
                                       "pak_sha256": digest(output / "initial.pak")}
        (output / "export-manifest.json").write_text(json.dumps(result))
        return result


class SyntheticVerifier:
    def __init__(self):
        self.calls = 0
        self.fail_once = False
        self.report_failure = False

    def __call__(self, source, scenario_result, output, _emulator, _rom,
                 rom_sha256, executable, *, repeats):
        self.calls += 1
        assert (source / "controller.input").is_file()
        assert scenario_result.name == "scenario-result.json"
        assert repeats == 1
        output.mkdir()
        if self.fail_once and self.calls == 1:
            raise RuntimeError("synthetic verification interruption")
        if self.report_failure:
            failure = {"completed": False, "rom_sha256": rom_sha256,
                       "native_executable_sha256": digest(executable),
                       "contract": {"input_sha256": digest(source / "controller.input")}}
            (output / "verification-failure.json").write_text(json.dumps(failure))
            raise ValueError("synthetic reported route mismatch")
        result = {"completed": True, "native_parity_verified": False}
        (output / "verification-result.json").write_text(json.dumps(result))
        return result


class FrontierCycleTests(unittest.TestCase):
    def test_does_not_promote_position_seen_in_earlier_search(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cycle = root / "cycle"
            cycle.mkdir()
            graph = FrontierGraph()
            graph.add_node("start", "checkpoint", metadata={"source_level": 21})
            graph.add_node("exit", "objective")
            graph.add_edge("search", "start", "exit", "objective",
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata={"driver": "search-exit", "exit_id": "b" * 64})
            graph_path = cycle / "graph.json"
            graph.save(graph_path)
            jobs = []
            for index, x in enumerate((200.0, 200.7)):
                worker = cycle / f"job-{index:04d}-01" / "attempt-01"
                worker.mkdir(parents=True)
                (worker / "search-failure.json").write_text(json.dumps({
                    "reason": "bounded search exhausted"}))
                (worker / "search-objective.json").write_text(json.dumps({
                    "search_mode": "distance", "exit_identity": {
                        "source_level": 21, "id": "b" * 64}}))
                nodes = []
                for number, position in enumerate(([0.0, 0.0, 0.0],
                                                    [x, 0.0, 0.0])):
                    nodes.append({"id": number, "slot": f"a{number:04x}",
                                  "parent": None if number == 0 else 0,
                                  "depth": number, "position": position,
                                  "yaw": 0, "distance": 300.0 - 200.0 * number,
                                  "sha256": "c" * 64,
                                  "counters": {"frame": 20, "polls": 10,
                                               "player": 42},
                                  "action": None if number == 0 else {
                                      "frames": 60, "buttons": 0,
                                      "x": 60, "y": 0}})
                (worker / "search-nodes.jsonl").write_text(
                    "\n".join(json.dumps(node) for node in nodes) + "\n")
                result = worker.parent / "result.json"
                result.write_text(json.dumps({"planner_source_stable": True}))
                jobs.append({"edge": "search", "outcome": (
                    "covered" if index == 0 else "blocked"),
                    "result": result.relative_to(root).as_posix()})
            self.assertFalse(queue_node_verification(
                {"jobs": jobs}, graph_path, cycle, root))

    def test_detour_preserves_farther_spatial_frontier_for_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cycle = root / "cycle"
            cycle.mkdir()
            graph = FrontierGraph()
            graph.add_node("start", "checkpoint", metadata={"source_level": 21})
            graph.add_node("exit", "objective")
            graph.add_edge("search", "start", "exit", "objective",
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata={"driver": "search-exit", "exit_id": "b" * 64})
            graph_path = cycle / "graph.json"
            graph.save(graph_path)
            worker = cycle / "job-0000-01" / "attempt-01"
            worker.mkdir(parents=True)
            (worker / "search-failure.json").write_text(json.dumps({
                "reason": "bounded search exhausted"}))
            (worker / "search-objective.json").write_text(json.dumps({
                "search_mode": "detour", "exit_identity": {"source_level": 21}}))
            (worker / "search-nodes.jsonl").write_text("\n".join(json.dumps({
                "id": number, "slot": f"a{number:04x}",
                "parent": None if number == 0 else number - 1,
                "depth": number,
                "position": ([0.0, 0.0, 260.0] if number == 3 else
                             [float(150 * number), 0.0, 0.0]),
                "yaw": 0, "distance": float(100 + 50 * number),
                "sha256": "c" * 64,
                "counters": {"frame": 20, "polls": 10, "player": 42},
                "action": None if number == 0 else
                          {"frames": 60, "buttons": 0, "x": 60, "y": 0}})
                for number in range(4)) + "\n")
            result_path = worker.parent / "result.json"
            result_path.write_text(json.dumps({"planner_source_stable": True}))
            state = {"jobs": [{"index": 0, "edge": "search", "outcome": "blocked",
                               "result": result_path.relative_to(root).as_posix()}]}
            self.assertTrue(queue_node_verification(state, graph_path, cycle, root))
            self.assertEqual(state["pending_node_verification"]["node_id"], 2)
            self.assertEqual(state["pending_node_verification"]["selection"],
                             "spatial-detour")
            prior = cycle / "prior-proof.json"
            prior.write_text(json.dumps({
                "kind": "jfg-phase95-replayed-frontier-node",
                "source_level": 21, "player_position": [300.0, 0.0, 0.0]}))
            state["jobs"].append({"verified_node": prior.relative_to(root).as_posix()})
            state["pending_node_verification"] = None
            self.assertTrue(queue_node_verification(state, graph_path, cycle, root))
            self.assertEqual(state["pending_node_verification"]["node_id"], 3)
            nodes_path = worker / "search-nodes.jsonl"
            records = [json.loads(line) for line in nodes_path.read_text().splitlines()]
            for record, measured in zip(records, (500.0, 100.0, 200.0, 300.0)):
                record["distance"] = measured
            nodes_path.write_text("\n".join(json.dumps(item) for item in records) + "\n")
            (worker / "search-objective.json").write_text(json.dumps({
                "search_mode": "distance", "exit_identity": {"source_level": 21}}))
            state["pending_node_verification"] = None
            self.assertTrue(queue_node_verification(state, graph_path, cycle, root))
            self.assertEqual(state["pending_node_verification"]["node_id"], 3)
            self.assertEqual(state["pending_node_verification"]["selection"],
                             "exit-progress")
            state["jobs"][0]["verified_node"] = prior.relative_to(root).as_posix()
            state["pending_node_verification"] = None
            self.assertTrue(queue_node_verification(state, graph_path, cycle, root))
            self.assertEqual(state["pending_node_verification"]["node_id"], 3)
            self.assertEqual(state["pending_node_verification"]["attempt"], 1)

    def test_replayed_detour_promotes_checkpoint_without_claiming_exit_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cycle = root / "cycle"
            cycle.mkdir()
            graph = FrontierGraph()
            graph.add_node("start", "checkpoint", metadata={"source_level": 21})
            graph.add_node("exit", "objective")
            graph.add_edge("search", "start", "exit", "objective",
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata={"driver": "search-exit", "exit_id": "b" * 64,
                                     "checkpoint_sha256": "a" * 64})
            graph_path = cycle / "graph.json"
            graph.save(graph_path)
            worker = cycle / "job-0000-01" / "attempt-01"
            worker.mkdir(parents=True)
            (worker / "search-objective.json").write_text(json.dumps({
                "search_mode": "detour"}))
            (worker / "search-nodes.jsonl").write_text("\n".join(json.dumps({
                "id": number, "slot": f"a{number:04x}",
                "parent": None if number == 0 else 0,
                "depth": number, "position": [float(300 * number), 0.0, 0.0],
                "yaw": 0, "distance": float(100 + 100 * number),
                "sha256": "c" * 64,
                "counters": {"frame": 20, "polls": 10, "player": 42},
                "action": None if number == 0 else
                          {"frames": 60, "buttons": 0, "x": 60, "y": 0}})
                for number in range(2)) + "\n")
            state = {"jobs": [{"edge": "search", "outcome": "blocked"}],
                     "pending_node_verification": {
                         "job_index": 0, "attempt": 0, "node_id": 1,
                         "selection": "spatial-detour",
                         "worker_pointer": worker.relative_to(root).as_posix()}}

            def fake_verify(source, output, *_args, **_kwargs):
                output.mkdir()
                checkpoints = [worker / "checkpoint-a0001.json",
                               output / "checkpoint-c1.json"]
                for path in checkpoints:
                    path.write_text("synthetic checkpoint")
                proof = {"kind": "jfg-phase95-replayed-frontier-node", "schema": 1,
                         "selected_node": 1, "source_worker": str(source),
                         "exit_id": "b" * 64, "source_level": 21,
                         "source_distance": 100.0, "selected_distance": 200.0,
                         "player_position": [300.0, 0.0, 0.0],
                         "rdram_sha256": "c" * 64, "controller_polls": 10,
                         "source_identity": {},
                         "checkpoint_pointers": [path.relative_to(root).as_posix()
                                                 for path in checkpoints],
                         "checkpoint_sha256": [digest(path) for path in checkpoints],
                         "verification_tool_sha256": digest(
                             Path(__file__).resolve().parents[1] / "scripts" /
                             "phase95_frontier_verify_node.py")}
                (output / "verification-result.json").write_text(json.dumps(proof))
                return proof

            with patch("scripts.phase95_frontier_cycle.validate_checkpoint",
                       return_value={"rdram_sha256": "c" * 64,
                                     "observation": {"polls": 10}}):
                promote_replayed_node(state, graph_path, cycle, root,
                                      root / "emu.exe", root / "rom.z64",
                                      root / "bridge.lua", "a" * 64,
                                      verifier=fake_verify)
            promoted = FrontierGraph.load(root / state["graph"])
            continuation = state["jobs"][0]["continuation"]
            node = promoted.nodes[promoted.edges[continuation]["source"]]
            self.assertEqual(node["metadata"]["selection"], "spatial-detour")
            self.assertEqual(node["metadata"]["distance_to_exit"], 200.0)
            self.assertEqual(node["metadata"]["horizontal_displacement"], 300.0)
            self.assertEqual(promoted.status(continuation, "oracle-us"), "unexplored")

    def test_incomplete_search_node_replays_as_durable_spatial_continuation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cycle = root / "cycle"
            cycle.mkdir()
            graph = FrontierGraph()
            graph.add_node("start", "checkpoint", metadata={
                "source_level": 21, "checkpoint_sha256": "a" * 64})
            graph.add_node("exit", "objective", metadata={
                "setup_destination_level": 16})
            graph.add_edge("search", "start", "exit", "objective",
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata={"driver": "search-exit", "exit_id": "b" * 64,
                                     "max_nodes": 128, "max_expansions": 40,
                                     "radius": 25, "checkpoint_sha256": "a" * 64})
            graph.add_entrypoint("oracle-us", "start")
            graph.record("miss", "search", "oracle-us", "blocked", "miss.json",
                         reason="bounded search incomplete")
            graph_path = cycle / "graph.json"
            graph.save(graph_path)
            worker = cycle / "job-0000-01" / "attempt-01"
            worker.mkdir(parents=True)
            (worker / "search-failure.json").write_text(json.dumps({
                "reason": "bounded search exhausted"}))
            (worker / "search-objective.json").write_text(json.dumps({
                "search_mode": "distance", "exit_identity": {"source_level": 21}}))
            (worker / "search-nodes.jsonl").write_text("\n".join(json.dumps({
                "id": number, "slot": f"a{number:04x}",
                "parent": None if number == 0 else 0,
                "depth": number, "position": [float(number), 0.0, 0.0],
                "yaw": 0, "distance": 500.0 - 200 * number,
                "sha256": "c" * 64,
                "counters": {"frame": 20, "polls": 10, "player": 42},
                "action": None if number == 0 else
                          {"frames": 60, "buttons": 0, "x": 60, "y": 0}})
                for number in (0, 1)) + "\n")
            result_path = worker.parent / "result.json"
            result_path.write_text(json.dumps({"planner_source_stable": True}))
            (cycle / "state.json").write_text(json.dumps({
                "kind": "jfg-phase95-frontier-cycle", "schema": 1,
                "graph": graph_path.relative_to(root).as_posix(),
                "graph_sha256": digest(graph_path), "next_index": 1,
                "attempt": 0, "jobs": [{"index": 0, "edge": "search",
                                        "outcome": "blocked", "retry_edge": "none",
                                        "result": result_path.relative_to(root).as_posix()}],
                "pending_export": None, "pending_verification": None,
                "pending_discovery": None, "verification": None,
                "status": "active"}))
            calls = []

            def fake_verify(source, output, *_args, node_id, private_root):
                calls.append((source, node_id))
                output.mkdir()
                identity = {key: key + "-synthetic" for key in (
                    "rom_sha256", "runtime_sha256", "config_sha256",
                    "script_sha256")}
                checkpoints = [source / "checkpoint-a0001.json",
                               output / "checkpoint-c1.json"]
                for path in checkpoints:
                    state_file = path.with_suffix(".State")
                    side_file = path.with_suffix(".side")
                    state_file.write_bytes(b"synthetic checkpoint")
                    side_file.write_text("synthetic 10 20\n")
                    path.write_text(json.dumps({
                        "kind": "jfg-phase95-checkpoint", "schema": 1,
                        "identity": identity,
                        "observation": {"frame": 20, "polls": 10, "player": 42},
                        "rdram_sha256": "c" * 64,
                        "digests": {"State": digest(state_file),
                                    "side": digest(side_file)}}))
                proof = {"kind": "jfg-phase95-replayed-frontier-node",
                         "schema": 1, "selected_node": node_id,
                         "source_worker": str(source), "exit_id": "b" * 64,
                         "source_level": 21, "source_distance": 500.0,
                         "selected_distance": 300.0,
                         "player_position": [1.0, 0.0, 0.0],
                         "rdram_sha256": "c" * 64, "controller_polls": 10,
                         "source_identity": identity,
                         "checkpoint_pointers": [
                             path.relative_to(root).as_posix() for path in checkpoints],
                         "checkpoint_sha256": [digest(path) for path in checkpoints],
                         "verification_tool_sha256": digest(
                             Path(__file__).resolve().parents[1] / "scripts" /
                             "phase95_frontier_verify_node.py")}
                (output / "verification-result.json").write_text(json.dumps(proof))
                return proof

            state = run(cycle, root / "emu.exe", root / "rom.z64",
                        root / "bridge.lua", "a" * 64, resume=True,
                        max_jobs=0, private_root=root, node_verifier=fake_verify)
            self.assertEqual(calls, [(worker, 1)])
            self.assertIsNone(state["pending_node_verification"])
            self.assertIn("verified_node", state["jobs"][0])
            promoted = FrontierGraph.load(root / state["graph"])
            continuation = state["jobs"][0]["continuation"]
            self.assertEqual(promoted.status("search", "oracle-us"), "blocked")
            self.assertEqual(promoted.status(continuation, "oracle-us"), "unexplored")
            self.assertEqual(select(promoted)["id"], continuation)
            repeated = run(cycle, root / "emu.exe", root / "rom.z64",
                           root / "bridge.lua", "a" * 64, resume=True,
                           max_jobs=0, private_root=root, node_verifier=fake_verify)
            self.assertEqual(len(calls), 1)
            self.assertEqual(repeated["graph_sha256"], state["graph_sha256"])

    def test_paired_incomplete_search_becomes_closer_checkpoint_not_exit_coverage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cycle = root / "cycle"
            cycle.mkdir()
            seed_checkpoint = root / "seed.json"
            seed_checkpoint.write_text("synthetic source")
            graph = FrontierGraph()
            graph.add_node("start", "checkpoint", metadata={
                "checkpoint_pointer": "seed.json", "checkpoint_sha256": digest(seed_checkpoint),
                "source_level": 21})
            graph.add_node("exit", "objective", metadata={"setup_destination_level": 16})
            base = {"driver": "search-exit", "exit_id": "a" * 64,
                    "max_nodes": 128, "max_expansions": 40, "radius": 25,
                    "checkpoint_sha256": digest(seed_checkpoint)}
            graph.add_edge("search", "start", "exit", "objective",
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata=base)
            graph.add_edge("retry", "start", "exit", "objective", priority=10100,
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata={**base, "max_nodes": 256, "max_expansions": 80,
                                     "retry_parent": "search", "retry_tier": 1})
            graph.add_entrypoint("oracle-us", "start")
            for number, edge_id in enumerate(("search", "retry")):
                graph.record(f"blocked-{number}", edge_id, "oracle-us", "blocked",
                             f"job-{number:04d}-01/result.json",
                             reason="bounded search incomplete")
            graph_path = cycle / "graph.json"
            graph.save(graph_path)
            jobs = []
            for number, edge_id in enumerate(("search", "retry")):
                directory = cycle / f"job-{number:04d}-01"
                worker = directory / "attempt-01"
                worker.mkdir(parents=True)
                (worker / "search-failure.json").write_text(json.dumps({
                    "reason": "bounded search exhausted"}))
                result = directory / "result.json"
                result.write_text("{}")
                jobs.append({"index": number, "edge": edge_id,
                             "outcome": "blocked", "retry_edge": "retry",
                             "result": result.relative_to(root).as_posix()})
            (cycle / "state.json").write_text(json.dumps({
                "kind": "jfg-phase95-frontier-cycle", "schema": 1,
                "graph": graph_path.relative_to(root).as_posix(),
                "graph_sha256": digest(graph_path), "next_index": 2,
                "attempt": 0, "jobs": jobs, "pending_export": None,
                "pending_verification": None, "pending_discovery": None,
                "verification": None, "status": "active"}))
            calls = []

            def fake_salvage(first, second, exit_id, output, *, private_root):
                calls.append((first, second, exit_id))
                output.mkdir()
                identity = {key: key + "-synthetic" for key in (
                    "rom_sha256", "runtime_sha256", "config_sha256",
                    "script_sha256")}
                checkpoint = first / "checkpoint-a0001.json"
                state_file = checkpoint.with_suffix(".State")
                side_file = checkpoint.with_suffix(".side")
                state_file.write_bytes(b"synthetic checkpoint")
                side_file.write_text("synthetic 10 20\n")
                checkpoint.write_text(json.dumps({
                    "kind": "jfg-phase95-checkpoint", "schema": 1,
                    "identity": identity,
                    "observation": {"frame": 20, "polls": 10, "player": 42},
                    "rdram_sha256": "c" * 64,
                    "digests": {"State": digest(state_file), "side": digest(side_file)}}))
                artifact = {"kind": "jfg-phase95-paired-exploration-checkpoint",
                            "schema": 1, "paired": True, "exit_id": exit_id,
                            "source_level": 21, "source_horizontal_distance": 500.0,
                            "horizontal_distance": 300.0,
                            "rdram_sha256": "c" * 64, "controller_polls": 10,
                            "source_identity": identity,
                            "checkpoint_pointers": [checkpoint.relative_to(root).as_posix(),
                                                    checkpoint.relative_to(root).as_posix()],
                            "checkpoint_sha256": [digest(checkpoint), digest(checkpoint)],
                            "salvage_tool_sha256": digest(Path(__file__).resolve().parents[1] /
                                "scripts" / "phase95_frontier_salvage.py")}
                (output / "salvage-result.json").write_text(json.dumps(artifact))
                return artifact

            state = run(cycle, root / "emu.exe", root / "rom.z64",
                        root / "bridge.lua", "a" * 64, resume=True,
                        max_jobs=0, private_root=root, salvager=fake_salvage)
            self.assertEqual(len(calls), 1)
            self.assertEqual(state["salvages"][0]["status"], "promoted")
            self.assertEqual(state["jobs"][0]["outcome"], "blocked")
            self.assertEqual(state["jobs"][1]["outcome"], "blocked")
            promoted = FrontierGraph.load(root / state["graph"])
            continuation = state["salvages"][0]["continuation"]
            self.assertEqual(promoted.status(continuation, "oracle-us"), "unexplored")
            self.assertEqual(select(promoted)["id"], continuation)
            self.assertEqual(promoted.nodes[promoted.edges[continuation]["source"]][
                "metadata"]["salvage_depth"], 1)
            repeated = run(cycle, root / "emu.exe", root / "rom.z64",
                           root / "bridge.lua", "a" * 64, resume=True,
                           max_jobs=0, private_root=root, salvager=fake_salvage)
            self.assertEqual(len(calls), 1)
            self.assertEqual(repeated["graph_sha256"], state["graph_sha256"])

    def test_cycle_writer_lock_rejects_overlap_and_releases_after_process_death(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            graph, _ = seed(root)
            cycle = root / "cycle"
            code = (
                "from pathlib import Path\n"
                "import sys\n"
                "from scripts.phase95_frontier_cycle import cycle_owner\n"
                "with cycle_owner(Path(sys.argv[1]), Path(sys.argv[2])):\n"
                "    print('owned', flush=True)\n"
                "    sys.stdin.read()\n"
            )
            child = subprocess.Popen(
                [sys.executable, "-u", "-c", code, str(cycle), str(root)],
                cwd=Path(__file__).resolve().parents[1],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(child.stdout.readline().strip(), "owned")
                with self.assertRaisesRegex(RuntimeError, "another writer owns"):
                    run(cycle, root / "emu.exe", root / "rom.z64",
                        root / "script.lua", "a" * 64, graph_path=graph,
                        max_jobs=0, private_root=root)
                self.assertFalse(cycle.exists())
            finally:
                child.kill()
                child.communicate(timeout=10)
            state = run(cycle, root / "emu.exe", root / "rom.z64",
                        root / "script.lua", "a" * 64, graph_path=graph,
                        max_jobs=0, private_root=root)
            self.assertEqual(state["status"], "budget_exhausted")

    def test_legacy_bounded_miss_is_requeued_from_sealed_job_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cycle = root / "cycle"
            cycle.mkdir()
            graph = FrontierGraph()
            graph.add_node("start", "checkpoint")
            graph.add_node("near", "objective")
            graph.add_node("near-sibling", "objective")
            graph.add_edge("near", "start", "near", "objective",
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata={"driver": "search-exit", "exit_id": "a" * 64,
                                     "max_nodes": 128, "max_expansions": 40,
                                     "radius": 25, "checkpoint_sha256": "b" * 64})
            graph.add_edge("near-sibling", "start", "near-sibling", "objective",
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata={"driver": "search-exit", "exit_id": "c" * 64,
                                     "max_nodes": 128, "max_expansions": 40,
                                     "radius": 25, "checkpoint_sha256": "b" * 64})
            graph.add_entrypoint("oracle-us", "start")
            graph.record("miss", "near", "oracle-us", "blocked", "result.json",
                         reason="bounded exploration incomplete")
            graph_path = root / "graph.json"
            graph.save(graph_path)
            job_dir = cycle / "job-0000-01"
            (job_dir / "attempt-01").mkdir(parents=True)
            (job_dir / "attempt-01" / "search-failure.json").write_text(json.dumps({
                "kind": "jfg-phase95-search-incomplete", "nodes": 110,
                "reason": "bounded search exhausted", "unreachable": False}))
            (job_dir / "result.json").write_text(json.dumps({
                "reason": "ObservationError: bounded exploration incomplete; not proof of unreachable exit"}))
            state = {"jobs": [{"outcome": "blocked", "edge": "near",
                               "result": "cycle/job-0000-01/result.json"}],
                     "next_index": 1, "graph": "graph.json",
                     "graph_sha256": digest(graph_path)}
            self.assertTrue(requeue_legacy_incomplete(state, graph_path, cycle, root))
            self.assertEqual(state["jobs"][0]["retry_edge"], "near:retry-1")
            snapshot = FrontierGraph.load(root / state["graph"])
            self.assertEqual(snapshot.status("near", "oracle-us"), "blocked")
            self.assertEqual(snapshot.status("near:retry-1", "oracle-us"), "unexplored")
            self.assertFalse(requeue_legacy_incomplete(state, root / state["graph"],
                                                       cycle, root))
            sibling_dir = cycle / "job-0001-01"
            (sibling_dir / "attempt-01").mkdir(parents=True)
            (sibling_dir / "attempt-01" / "search-failure.json").write_text(json.dumps({
                "kind": "jfg-phase95-search-incomplete", "nodes": 110,
                "reason": "bounded search exhausted", "unreachable": False}))
            (sibling_dir / "attempt-01" / "world-inventory.json").write_text(
                json.dumps({"kind": "jfg-phase95-observed-world", "schema": 1,
                            "level": 21,
                            "exits": [{"id": "a" * 64, "source_level": 21,
                                       "position": [46, 64, -2090]},
                                      {"id": "c" * 64, "source_level": 21,
                                       "position": [46, 64, -2090]}]}))
            (sibling_dir / "result.json").write_text(json.dumps({
                "reason": "ObservationError: bounded exploration incomplete; not proof of unreachable exit",
                "retry_edge_id": "near-sibling:retry-1"}))
            duplicate = FrontierGraph.load(root / state["graph"])
            sibling_spec = duplicate.edges["near-sibling"]["metadata"]
            duplicate.add_edge("near-sibling:retry-1", "start", "near-sibling",
                               "objective", priority=10100, source_variant="us",
                               required_capabilities=("search-exit",),
                               metadata={**sibling_spec, "max_nodes": 256,
                                         "max_expansions": 80,
                                         "retry_parent": "near-sibling",
                                         "retry_tier": 1})
            duplicate_path = root / "with-duplicate.json"
            duplicate.save(duplicate_path)
            state["graph"] = duplicate_path.name
            state["graph_sha256"] = digest(duplicate_path)
            state["jobs"].append({"outcome": "blocked", "edge": "near-sibling",
                                  "result": "cycle/job-0001-01/result.json"})
            state["next_index"] = 2
            self.assertTrue(requeue_legacy_incomplete(state, root / state["graph"],
                                                      cycle, root))
            self.assertEqual(state["jobs"][1]["retry_edge"], "near:retry-1")
            shared = FrontierGraph.load(root / state["graph"])
            self.assertEqual(shared.status("near-sibling:retry-1", "oracle-us"),
                             "blocked")

    def test_cycle_promotes_and_discovers_without_manual_checkpoint_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            graph, checkpoint = seed(root)
            job = SyntheticJob(root)
            discover = SyntheticDiscover()
            exporter = SyntheticExport()
            state = run(root / "cycle", root / "emu.exe", root / "rom.z64",
                        root / "script.lua", "a" * 64, graph_path=graph,
                        max_jobs=1, private_root=root,
                        job_runner=job, discoverer=discover, exporter=exporter)
            self.assertEqual(state["status"], "budget_exhausted")
            self.assertEqual(job.calls, [checkpoint])
            self.assertEqual(discover.calls, 1)
            self.assertEqual(exporter.calls, 1)
            self.assertTrue((root / "cycle" / "export-0000-01" /
                             "controller.input").exists())
            self.assertIsNone(state["pending_discovery"])
            final = FrontierGraph.load(root / state["graph"])
            self.assertIn("new-exit", final.frontier("oracle-us",
                                                    capabilities=("search-exit",)))

    def test_interrupted_discovery_resumes_without_repeating_completed_job(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            graph, checkpoint = seed(root)
            job = SyntheticJob(root)
            discover = SyntheticDiscover()
            exporter = SyntheticExport()
            discover.fail_once = True
            with self.assertRaisesRegex(RuntimeError, "synthetic interruption"):
                run(root / "cycle", root / "emu.exe", root / "rom.z64",
                    root / "script.lua", "a" * 64, graph_path=graph,
                    max_jobs=1, private_root=root,
                    job_runner=job, discoverer=discover, exporter=exporter)
            preserved = json.loads((root / "cycle" / "state.json").read_text())
            self.assertIsNotNone(preserved["pending_discovery"])
            resumed = run(root / "cycle", root / "emu.exe", root / "rom.z64",
                          root / "script.lua", "a" * 64, resume=True,
                          max_jobs=0, private_root=root,
                          job_runner=job, discoverer=discover, exporter=exporter)
            self.assertEqual(discover.calls, 2)
            self.assertEqual(exporter.calls, 1)
            self.assertEqual(job.calls, [checkpoint])
            self.assertEqual(resumed["status"], "budget_exhausted")
            self.assertTrue((root / "cycle" / "discover-0000-02" /
                             "frontier-graph.json").exists())

    def test_interrupted_export_resumes_before_discovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            graph, checkpoint = seed(root)
            job = SyntheticJob(root)
            discover = SyntheticDiscover()
            exporter = SyntheticExport()
            exporter.fail_once = True
            with self.assertRaisesRegex(RuntimeError, "export interruption"):
                run(root / "cycle", root / "emu.exe", root / "rom.z64",
                    root / "script.lua", "a" * 64, graph_path=graph,
                    max_jobs=1, private_root=root, job_runner=job,
                    discoverer=discover, exporter=exporter)
            preserved = json.loads((root / "cycle" / "state.json").read_text())
            self.assertIsNotNone(preserved["pending_export"])
            self.assertEqual(discover.calls, 0)
            resumed = run(root / "cycle", root / "emu.exe", root / "rom.z64",
                          root / "script.lua", "a" * 64, resume=True,
                          max_jobs=0, private_root=root, job_runner=job,
                          discoverer=discover, exporter=exporter)
            self.assertEqual(job.calls, [checkpoint])
            self.assertEqual(exporter.calls, 2)
            self.assertEqual(discover.calls, 1)
            self.assertIsNone(resumed["pending_export"])
            self.assertTrue((root / "cycle" / "export-0000-02" /
                             "controller.input").exists())

    def test_native_diagnostic_is_durable_and_resumes_before_discovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            graph, checkpoint = seed(root)
            flash, pak, executable = (root / name for name in
                                      ("initial.flash", "initial.pak", "native.exe"))
            flash.write_bytes(bytes(0x20000))
            pak.write_bytes(bytes(32))
            executable.write_bytes(b"synthetic native binary")
            job = SyntheticJob(root)
            discover = SyntheticDiscover()
            exporter = SyntheticExport()
            verifier = SyntheticVerifier()
            verifier.fail_once = True
            with self.assertRaisesRegex(RuntimeError, "verification interruption"):
                run(root / "cycle", root / "emu.exe", root / "rom.z64",
                    root / "script.lua", "a" * 64, graph_path=graph,
                    max_jobs=1, private_root=root, job_runner=job,
                    discoverer=discover, exporter=exporter, verifier=verifier,
                    initial_flash=flash, initial_pak=pak, executable=executable)
            preserved = json.loads((root / "cycle" / "state.json").read_text())
            self.assertIsNone(preserved["pending_export"])
            self.assertIsNotNone(preserved["pending_verification"])
            self.assertEqual(discover.calls, 0)
            resumed = run(root / "cycle", root / "emu.exe", root / "rom.z64",
                          root / "script.lua", "a" * 64, resume=True,
                          max_jobs=0, private_root=root, job_runner=job,
                          discoverer=discover, exporter=exporter, verifier=verifier)
            self.assertEqual(job.calls, [checkpoint])
            self.assertEqual(exporter.calls, 1)
            self.assertEqual(verifier.calls, 2)
            self.assertEqual(discover.calls, 1)
            self.assertIsNone(resumed["pending_verification"])
            self.assertIn("verification", resumed["jobs"][0])

    def test_native_diagnostic_requires_complete_pin_set(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            graph, _ = seed(root)
            with self.assertRaisesRegex(ValueError, "flash, pak, and executable"):
                run(root / "cycle", root / "emu.exe", root / "rom.z64",
                    root / "script.lua", "a" * 64, graph_path=graph,
                    private_root=root, initial_flash=root / "initial.flash")
            self.assertFalse((root / "cycle").exists())

    def test_reported_native_diagnostic_failure_is_preserved_and_discovery_continues(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            graph, _ = seed(root)
            flash, pak, executable = (root / name for name in
                                      ("initial.flash", "initial.pak", "native.exe"))
            flash.write_bytes(bytes(0x20000))
            pak.write_bytes(bytes(32))
            executable.write_bytes(b"synthetic native binary")
            verifier = SyntheticVerifier()
            verifier.report_failure = True
            discover = SyntheticDiscover()
            state = run(root / "cycle", root / "emu.exe", root / "rom.z64",
                        root / "script.lua", "a" * 64, graph_path=graph,
                        max_jobs=1, private_root=root, job_runner=SyntheticJob(root),
                        discoverer=discover, exporter=SyntheticExport(), verifier=verifier,
                        initial_flash=flash, initial_pak=pak, executable=executable)
            self.assertEqual(discover.calls, 1)
            self.assertIsNone(state["pending_verification"])
            self.assertIn("verification_failure", state["jobs"][0])
            self.assertNotIn("verification", state["jobs"][0])

    def test_pointer_escape_and_seal_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = root / "checkpoint.json"
            path.write_text("state")
            for pointer in ("../outside", "C:/outside", "\\\\host\\share", "bad\\name"):
                with self.assertRaisesRegex(ValueError, "pointer"):
                    resolve_pointer(pointer, root)
            with self.assertRaisesRegex(ValueError, "seal mismatch"):
                resolve_pointer(path.name, root, hashlib.sha256(b"wrong").hexdigest())


if __name__ == "__main__":
    unittest.main()
