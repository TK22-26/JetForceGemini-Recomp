"""Synthetic tests only: no emulator or private game data is launched."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.phase95_frontier_graph import FrontierGraph
from scripts.phase95_bridge import digest, isolate_n64_bindings, runtime_digest
from scripts.phase95_frontier_job import (preflight, promote_search_checkpoint,
                                          run, search_mode, select)
from scripts.phase95_observation import ObservationError


def fake_polls(_root):
    return [(0, 0, 0)] * 5, []


def fixture_graph(checkpoint_sha):
    graph = FrontierGraph()
    graph.add_node("start", "checkpoint")
    graph.add_node("landmark", "objective")
    graph.add_node("elsewhere", "objective")
    graph.add_edge("wrong-lane", "start", "elsewhere", "objective", priority=0,
                   source_variant="jp", metadata={"driver": "navigate"})
    graph.add_edge("landmark", "start", "landmark", "objective", priority=1,
                   source_variant="us", required_capabilities=("navigate",),
                   metadata={"driver": "navigate", "target_name": "longwoodbridge",
                             "max_steps": 1, "radius": 65,
                             "checkpoint_sha256": checkpoint_sha})
    graph.add_entrypoint("oracle-us", "start")
    return graph


class FakeWorker:
    observations = []

    def __init__(self, root, *_):
        self.root = root
        root.mkdir()
        self.number = int(root.name[-2:])

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def observe(self):
        return ({"frame": 10, "polls": 5, "player": 123},
                self.observations[self.number - 1])

    def import_checkpoint(self, path):
        assert path.exists()


class FrontierJobTests(unittest.TestCase):
    def test_second_exit_retry_scouts_topology_in_breadth(self):
        graph = FrontierGraph()
        graph.add_node("start", "checkpoint")
        graph.add_node("exit", "objective")
        graph.add_edge("retry", "start", "exit", "objective",
                       metadata={"driver": "search-exit", "retry_tier": 2})
        self.assertEqual(search_mode(graph, graph.edges["retry"]), "coverage")

    def test_select_reachable_uncovered_us_objective(self):
        graph = fixture_graph("a" * 64)
        self.assertEqual(select(graph)["id"], "landmark")
        graph.record("done", "landmark", "oracle-us", "covered", "result.json")
        with self.assertRaisesRegex(ValueError, "no reachable"):
            select(graph)

    def test_select_prefers_unreached_destination_over_short_return_exit(self):
        graph = FrontierGraph()
        graph.add_node("start", "checkpoint", metadata={"source_level": 47})
        graph.add_node("return", "branch",
                       metadata={"setup_destination_level": 47})
        graph.add_node("new", "branch",
                       metadata={"setup_destination_level": 48})
        for name, priority, exit_id in (("return", 1, "a" * 64),
                                        ("new", 100, "b" * 64)):
            graph.add_edge(name, "start", name, "objective", priority=priority,
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata={"driver": "search-exit", "exit_id": exit_id,
                                     "max_nodes": 128, "max_expansions": 40,
                                     "radius": 25, "checkpoint_sha256": "c" * 64})
        graph.add_entrypoint("oracle-us", "start")
        self.assertEqual(select(graph)["id"], "new")
        graph.add_node("reached-48", "checkpoint", metadata={"source_level": 48})
        graph.add_entrypoint("oracle-us", "reached-48")
        self.assertEqual(select(graph)["id"], "return")

    def test_select_nearby_retry_before_far_duplicate_exit(self):
        graph = FrontierGraph()
        graph.add_node("start", "checkpoint", metadata={"source_level": 47})
        graph.add_node("near", "branch",
                       metadata={"setup_destination_level": 199})
        graph.add_node("far", "branch",
                       metadata={"setup_destination_level": 199})
        spec = {"driver": "search-exit", "exit_id": "b" * 64,
                "max_nodes": 128, "max_expansions": 40, "radius": 25,
                "checkpoint_sha256": "c" * 64}
        graph.add_edge("near", "start", "near", "objective", priority=128,
                       source_variant="us", required_capabilities=("search-exit",),
                       metadata=spec)
        graph.record("miss", "near", "oracle-us", "blocked", "miss.json",
                     reason="bounded search incomplete")
        graph.add_edge("near:retry-1", "start", "near", "objective",
                       priority=10128, source_variant="us",
                       required_capabilities=("search-exit",),
                       metadata={**spec, "max_nodes": 256, "max_expansions": 80,
                                 "retry_parent": "near", "retry_tier": 1})
        graph.add_edge("far", "start", "far", "objective", priority=1851,
                       source_variant="us", required_capabilities=("search-exit",),
                       metadata=spec)
        graph.add_entrypoint("oracle-us", "start")
        self.assertEqual(select(graph)["id"], "near:retry-1")

    def test_select_fresh_paired_source_before_paired_retry(self):
        graph = FrontierGraph()
        for source in ("paired-a", "paired-b"):
            graph.add_node(source, "checkpoint", metadata={
                "source_level": 21, "paired_salvage_result": source + ".json"})
            graph.add_entrypoint("oracle-us", source)
        graph.add_node("exit", "objective", metadata={"setup_destination_level": 16})
        spec = {"driver": "search-exit", "exit_id": "a" * 64,
                "max_nodes": 128, "max_expansions": 40, "radius": 25,
                "checkpoint_sha256": "b" * 64}
        graph.add_edge("first", "paired-a", "exit", "objective", priority=100,
                       source_variant="us", required_capabilities=("search-exit",),
                       metadata=spec)
        graph.record("first-miss", "first", "oracle-us", "blocked", "miss.json",
                     reason="bounded search incomplete")
        graph.add_edge("first:retry-1", "paired-a", "exit", "objective",
                       priority=10100, source_variant="us",
                       required_capabilities=("search-exit",),
                       metadata={**spec, "max_nodes": 256, "max_expansions": 80,
                                 "retry_parent": "first", "retry_tier": 1})
        graph.add_edge("second", "paired-b", "exit", "objective", priority=100,
                       source_variant="us", required_capabilities=("search-exit",),
                       metadata=spec)
        self.assertEqual(select(graph)["id"], "second")
        graph.record("second-miss", "second", "oracle-us", "blocked", "miss2.json",
                     reason="bounded search incomplete")
        self.assertEqual(select(graph)["id"], "first:retry-1")

    def test_select_verified_closer_source_over_older_priority(self):
        graph = FrontierGraph()
        for name, distance in (("closer", 1116.57), ("older", 1694.45)):
            graph.add_node(name, "checkpoint", metadata={
                "source_level": 21, "paired_node_result": name + ".json",
                "distance_to_exit": distance})
            graph.add_entrypoint("oracle-us", name)
        graph.add_node("exit", "objective", metadata={
            "setup_destination_level": 16})
        spec = {"driver": "search-exit", "exit_id": "a" * 64,
                "max_nodes": 128, "max_expansions": 40, "radius": 25,
                "checkpoint_sha256": "b" * 64}
        graph.add_edge("closer", "closer", "exit", "objective", priority=100,
                       source_variant="us", required_capabilities=("search-exit",),
                       metadata=spec)
        graph.add_edge("older", "older", "exit", "objective", priority=50,
                       source_variant="us", required_capabilities=("search-exit",),
                       metadata=spec)
        self.assertEqual(select(graph)["id"], "closer")

    def test_select_close_detour_before_far_fresh_source(self):
        graph = FrontierGraph()
        for name, distance in (("near", 1116.57), ("far", 1673.95)):
            graph.add_node(name, "checkpoint", metadata={
                "source_level": 21, "paired_node_result": name + ".json",
                "distance_to_exit": distance})
            graph.add_entrypoint("oracle-us", name)
        graph.add_node("exit", "objective", metadata={
            "setup_destination_level": 16})
        spec = {"driver": "search-exit", "exit_id": "a" * 64,
                "max_nodes": 128, "max_expansions": 40, "radius": 25,
                "checkpoint_sha256": "b" * 64}
        graph.add_edge("near", "near", "exit", "objective", priority=100,
                       source_variant="us", required_capabilities=("search-exit",),
                       metadata=spec)
        graph.record("miss", "near", "oracle-us", "blocked", "miss.json",
                     reason="bounded search incomplete")
        graph.add_edge("near:retry-1", "near", "exit", "objective",
                       priority=10100, source_variant="us",
                       required_capabilities=("search-exit",),
                       metadata={**spec, "retry_parent": "near", "retry_tier": 1})
        graph.add_edge("far", "far", "exit", "objective", priority=50,
                       source_variant="us", required_capabilities=("search-exit",),
                       metadata=spec)
        self.assertEqual(select(graph)["id"], "near:retry-1")

    def test_paired_retry_uses_detour_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text("synthetic")
            graph = FrontierGraph()
            graph.add_node("paired", "checkpoint", metadata={
                "paired_salvage_result": "paired-result.json", "source_level": 21})
            graph.add_node("exit", "objective", metadata={
                "setup_destination_level": 16})
            spec = {"driver": "search-exit", "exit_id": "a" * 64,
                    "max_nodes": 128, "max_expansions": 40, "radius": 25,
                    "checkpoint_sha256": digest(checkpoint)}
            graph.add_edge("base", "paired", "exit", "objective", priority=100,
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata=spec)
            graph.record("miss", "base", "oracle-us", "blocked", "miss.json",
                         reason="bounded search incomplete")
            graph.add_edge("retry", "paired", "exit", "objective", priority=10100,
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata={**spec, "max_nodes": 256, "max_expansions": 80,
                                     "retry_parent": "base", "retry_tier": 1})
            graph.add_entrypoint("oracle-us", "paired")
            graph_path = root / "graph.json"
            graph.save(graph_path)
            FakeWorker.observations = [b"same", b"same"]
            calls = []

            def incomplete(_worker, _exit_id, **kwargs):
                calls.append(kwargs)
                return {"completed": False, "route_steps": 0}

            with patch("scripts.phase95_frontier_job.preflight", return_value={}):
                result = run(graph_path, root / "out", checkpoint, root / "emu.exe",
                             root / "rom.z64", root / "bridge.lua", "b" * 64,
                             "paired-detour", worker_type=FakeWorker,
                             searcher=incomplete, poll_selector=fake_polls,
                             private_root=root)
            self.assertEqual(result["outcome"], "blocked")
            self.assertEqual([call["mode"] for call in calls], ["detour", "detour"])
            manifest = json.loads((root / "out" / "manifest.json").read_text())
            self.assertEqual(manifest["effective_search_mode"], "detour")

    def test_selects_unattempted_semantic_exit_before_far_repeat(self):
        graph = FrontierGraph()
        graph.add_node("first", "checkpoint")
        graph.add_node("second", "checkpoint")
        graph.add_node("repeat-target", "objective")
        graph.add_node("novel-target", "objective")
        graph.add_entrypoint("oracle-us", "first")
        graph.add_entrypoint("oracle-us", "second")
        common = {"driver": "search-exit", "max_nodes": 128,
                  "max_expansions": 40, "radius": 25,
                  "checkpoint_sha256": "a" * 64}
        graph.add_edge("attempted", "first", "repeat-target", "objective",
                       priority=50, source_variant="us",
                       required_capabilities=("search-exit",),
                       metadata={**common, "exit_id": "b" * 64})
        graph.record("miss", "attempted", "oracle-us", "blocked", "miss.json",
                     reason="bounded search incomplete")
        graph.add_edge("repeat", "second", "repeat-target", "objective",
                       priority=100, source_variant="us",
                       required_capabilities=("search-exit",),
                       metadata={**common, "exit_id": "b" * 64})
        graph.add_edge("novel", "second", "novel-target", "objective",
                       priority=200, source_variant="us",
                       required_capabilities=("search-exit",),
                       metadata={**common, "exit_id": "c" * 64})
        self.assertEqual(select(graph)["id"], "novel")
        graph.record("novel-miss", "novel", "oracle-us", "blocked", "miss2.json",
                     reason="bounded search incomplete")
        self.assertEqual(select(graph)["id"], "repeat")

    def test_reject_unbounded_objective(self):
        graph = fixture_graph("a" * 64)
        graph.edges["landmark"]["metadata"]["max_steps"] = 500
        with self.assertRaisesRegex(ValueError, "bounded"):
            select(graph)

    def test_select_observed_exit_search(self):
        graph = fixture_graph("a" * 64)
        graph.record("done", "landmark", "oracle-us", "covered", "result.json")
        graph.add_node("exit-near", "branch")
        graph.add_edge("exit-near", "start", "exit-near", "objective",
                       source_variant="us", required_capabilities=("search-exit",),
                       metadata={"driver": "search-exit", "exit_id": "b" * 64,
                                 "max_nodes": 128, "max_expansions": 40,
                                 "radius": 65, "checkpoint_sha256": "a" * 64})
        self.assertEqual(select(graph)["id"], "exit-near")
        graph.edges["exit-near"]["metadata"]["max_nodes"] = 999
        with self.assertRaisesRegex(ValueError, "bounded"):
            select(graph)

    def test_preflight_fails_closed_before_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = root / "state.json"
            checkpoint.write_text("{}")
            edge = fixture_graph("a" * 64).edges["landmark"]
            with self.assertRaisesRegex(ValueError, "seal"):
                preflight(edge, checkpoint, root / "emu.exe", root / "rom.z64",
                          root / "bridge.lua", "b" * 64)

    def test_preflight_matches_worker_native_line_endings(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            emulator = root / "emu.exe"
            emulator.write_bytes(b"synthetic runtime")
            rom = root / "rom.z64"
            rom.write_bytes(b"synthetic ROM identity only")
            script = root / "bridge.lua"
            script.write_bytes(b"synthetic script")
            settings = {"AllTrollers": {"Nintendo 64 Controller": {"P1 A": "X"}}}
            (root / "config.ini").write_text(json.dumps(settings))
            canonical = (json.dumps(isolate_n64_bindings(settings), indent=2) + "\n")
            expected_config = hashlib.sha256(canonical.replace("\n", os.linesep).encode()).hexdigest()
            checkpoint = root / "checkpoint.json"
            checkpoint.with_suffix(".State").write_bytes(b"synthetic state")
            checkpoint.with_suffix(".side").write_bytes(b"synthetic side")
            identity = {"rom_sha256": digest(rom), "runtime_sha256": runtime_digest(root),
                        "config_sha256": expected_config, "script_sha256": digest(script)}
            checkpoint.write_text(json.dumps({"kind": "jfg-phase95-checkpoint", "schema": 1,
                                              "identity": identity,
                                              "digests": {"State": digest(checkpoint.with_suffix(".State")),
                                                          "side": digest(checkpoint.with_suffix(".side"))}}))
            self.assertEqual(preflight({"metadata": {"checkpoint_sha256": digest(checkpoint)}},
                                       checkpoint, emulator, rom, script, digest(rom)), identity)

    def test_two_independent_equal_runs_cover_and_preserve_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text("synthetic")
            graph = fixture_graph(hashlib.sha256(b"synthetic").hexdigest())
            graph_path = root / "graph.json"
            graph.save(graph_path)
            before = graph_path.read_bytes()
            FakeWorker.observations = [b"same", b"same"]
            with patch("scripts.phase95_frontier_job.preflight", return_value={"synthetic": True}):
                result = run(graph_path, root / "out", checkpoint, root / "emu.exe",
                             root / "rom.z64", root / "bridge.lua", "b" * 64,
                             "job-1", worker_type=FakeWorker,
                             navigator=lambda *_args, **_kwargs: {"completed": True, "steps": 1},
                             poll_selector=fake_polls,
                             private_root=root)
            self.assertEqual(result["outcome"], "covered")
            self.assertIn("no transition asserted", result["predicate"])
            self.assertTrue(result["deterministic"])
            manifest = json.loads((root / "out" / "manifest.json").read_text())
            self.assertEqual(result["planner_source_sha256"],
                             manifest["planner_source_sha256"])
            self.assertTrue(result["planner_source_stable"])
            scenario = json.loads((root / "out" / "attempt-01" /
                                   "scenario-result.json").read_text())
            self.assertEqual(scenario["final_rdram_sha256"],
                             result["attempts"][0]["rdram_sha256"])
            self.assertEqual(scenario["controller_polls"], 5)
            self.assertEqual(scenario["planner_source_sha256"],
                             manifest["planner_source_sha256"])
            self.assertEqual(graph_path.read_bytes(), before)
            snapshot = FrontierGraph.load(root / "out" / "frontier-evidence.json")
            self.assertEqual(snapshot.status("landmark", "oracle-us"), "covered")
            self.assertEqual(snapshot.evidence["job-1"]["pointer"], "result.json")

    def test_disagreement_blocks_and_preserves_both_attempts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text("synthetic")
            graph_path = root / "graph.json"
            fixture_graph(hashlib.sha256(b"synthetic").hexdigest()).save(graph_path)
            FakeWorker.observations = [b"one", b"two"]
            with patch("scripts.phase95_frontier_job.preflight", return_value={}):
                result = run(graph_path, root / "out", checkpoint, root / "emu.exe",
                             root / "rom.z64", root / "bridge.lua", "b" * 64,
                             "job-2", worker_type=FakeWorker,
                             navigator=lambda *_args, **_kwargs: {"completed": True, "steps": 1},
                             poll_selector=fake_polls,
                             private_root=root)
            self.assertEqual(result["outcome"], "blocked")
            self.assertFalse(result["deterministic"])
            self.assertEqual(len(result["attempts"]), 2)
            self.assertTrue((root / "out" / "attempt-01").is_dir())
            self.assertTrue((root / "out" / "attempt-02").is_dir())

    def test_equal_final_state_but_different_input_paths_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text("synthetic")
            graph_path = root / "graph.json"
            fixture_graph(hashlib.sha256(b"synthetic").hexdigest()).save(graph_path)
            FakeWorker.observations = [b"same", b"same"]

            def different_polls(worker_root):
                button = 1 if worker_root.name == "attempt-02" else 0
                return [(button, 0, 0)] * 5, []

            with patch("scripts.phase95_frontier_job.preflight", return_value={}):
                result = run(graph_path, root / "out", checkpoint, root / "emu.exe",
                             root / "rom.z64", root / "bridge.lua", "b" * 64,
                             "job-input-disagree", worker_type=FakeWorker,
                             navigator=lambda *_args, **_kwargs: {"completed": True, "steps": 1},
                             poll_selector=different_polls, private_root=root)
            self.assertEqual(result["outcome"], "blocked")
            self.assertFalse(result["deterministic"])
            self.assertNotEqual(result["attempts"][0]["selected_input_sha256"],
                                result["attempts"][1]["selected_input_sha256"])

    def test_planner_source_change_during_job_blocks_promotion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text("synthetic")
            graph_path = root / "graph.json"
            fixture_graph(hashlib.sha256(b"synthetic").hexdigest()).save(graph_path)
            FakeWorker.observations = [b"same", b"same"]
            pins = ({"sha256": "a" * 64, "files": {}},
                    {"sha256": "b" * 64, "files": {}})
            with patch("scripts.phase95_frontier_job.preflight", return_value={}), \
                    patch("scripts.phase95_frontier_job.source_pin", side_effect=pins):
                result = run(graph_path, root / "out", checkpoint, root / "emu.exe",
                             root / "rom.z64", root / "bridge.lua", "b" * 64,
                             "job-planner-change", worker_type=FakeWorker,
                             navigator=lambda *_args, **_kwargs: {"completed": True, "steps": 1},
                             poll_selector=fake_polls, private_root=root)
            self.assertEqual(result["outcome"], "blocked")
            self.assertFalse(result["planner_source_stable"])
            self.assertEqual(result["reason"], "planner source changed during frontier job")

    def test_exit_search_uses_bounded_search_and_exports_checkpoint_pointer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text("synthetic")
            graph = FrontierGraph()
            graph.add_node("start", "checkpoint")
            graph.add_node("near", "branch")
            graph.add_node("near-sibling", "branch")
            graph.add_edge("near", "start", "near", "objective", source_variant="us",
                           required_capabilities=("search-exit",),
                           metadata={"driver": "search-exit", "exit_id": "b" * 64,
                                     "max_nodes": 16, "max_expansions": 4, "radius": 60,
                                     "checkpoint_sha256": digest(checkpoint)})
            graph.add_edge("near-sibling", "start", "near-sibling", "objective",
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata={"driver": "search-exit", "exit_id": "c" * 64,
                                     "max_nodes": 16, "max_expansions": 4, "radius": 60,
                                     "checkpoint_sha256": digest(checkpoint)})
            graph.add_entrypoint("oracle-us", "start")
            graph_path = root / "graph.json"
            graph.save(graph_path)
            FakeWorker.observations = [b"same", b"same"]
            calls = []
            selected_identity = {"id": "b" * 64, "source_level": 21,
                                 "position": [46, 64, -2090],
                                 "destination_level": 47, "world_gate": -1}
            sibling_identity = {"id": "c" * 64, "source_level": 21,
                                "position": [46, 64, -2090],
                                "destination_level": 48, "world_gate": -1}
            observed_world = {"kind": "jfg-phase95-observed-world", "schema": 1,
                              "level": 21, "exits": [selected_identity, sibling_identity]}

            def fake_search(worker, exit_id, **bounds):
                calls.append((exit_id, bounds))
                checkpoint_path = worker.root / "checkpoint-c1.json"
                checkpoint_path.with_suffix(".State").write_bytes(b"state")
                checkpoint_path.with_suffix(".side").write_bytes(b"side")
                (worker.root / "observation.rdram").write_bytes(b"same")
                (worker.root / "world-inventory.json").write_text(
                    json.dumps(observed_world))
                checkpoint_path.write_text(json.dumps({
                    "kind": "jfg-phase95-checkpoint", "schema": 1,
                    "rdram_sha256": hashlib.sha256(b"same").hexdigest(),
                    "observation": {"sequence": 1, "frame": 10,
                                    "polls": 5, "player": 123},
                    "digests": {"State": digest(checkpoint_path.with_suffix(".State")),
                                "side": digest(checkpoint_path.with_suffix(".side"))}}))
                (worker.root / "search-result.json").write_text(json.dumps({
                    "kind": "jfg-phase95-checkpoint-search", "completed": True,
                    "replay_equal": True,
                    "final_rdram_sha256": hashlib.sha256(b"same").hexdigest(),
                    "exit_identity": selected_identity}))
                return {"completed": True, "route_steps": 2}

            with patch("scripts.phase95_frontier_job.preflight", return_value={}), \
                    patch("scripts.phase95_frontier_job.world_inventory",
                          return_value=observed_world):
                result = run(graph_path, root / "out", checkpoint, root / "emu.exe",
                             root / "rom.z64", root / "bridge.lua", "b" * 64,
                             "job-search", worker_type=FakeWorker,
                             searcher=fake_search, poll_selector=fake_polls,
                             private_root=root)
            self.assertEqual(result["outcome"], "covered")
            self.assertIn("exit_proximity", result["predicate"])
            self.assertEqual(calls, [("b" * 64, {"max_nodes": 16,
                                                "max_expansions": 4, "radius": 60})] * 2)
            self.assertEqual(result["attempts"][0]["checkpoint"],
                             "attempt-01/checkpoint-c1.json")
            snapshot = FrontierGraph.load(root / "out" / "frontier-evidence.json")
            self.assertIn(result["next_checkpoint"]["node"],
                          snapshot.reached_nodes("oracle-us"))
            self.assertEqual(snapshot.nodes[result["next_checkpoint"]["node"]]["kind"],
                             "checkpoint")
            self.assertEqual(result["next_checkpoint"]["co_located_exit_ids"],
                             [sibling_identity["id"]])
            self.assertEqual(snapshot.status("near-sibling", "oracle-us"), "covered")
            self.assertEqual(len([item for item in snapshot.edges.values()
                                  if item["metadata"].get("driver") == "cross-exit"]), 2)
            self.assertEqual(select(snapshot)["metadata"]["driver"], "cross-exit")

    def test_exit_crossing_requires_sealed_source_and_promotes_arrival(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = root / "checkpoint-c1.json"
            checkpoint.write_text(json.dumps({"kind": "jfg-phase95-checkpoint",
                                              "rdram_sha256": "a" * 64}))
            search_result = root / "search-result.json"
            search_result.write_text(json.dumps({
                "kind": "jfg-phase95-checkpoint-search", "completed": True,
                "replay_equal": True, "final_rdram_sha256": "a" * 64,
                "exit_identity": {"id": "b" * 64, "source_level": 21,
                                  "destination_level": 47, "world_gate": -1}}))
            graph = FrontierGraph()
            graph.add_node("near-checkpoint", "checkpoint",
                           metadata={"source_level": 21,
                                     "checkpoint_sha256": digest(checkpoint)})
            graph.add_node("arrival", "objective")
            graph.add_edge("arrival", "near-checkpoint", "arrival", "transition",
                           source_variant="us", required_capabilities=("cross-exit",),
                           metadata={"driver": "cross-exit", "exit_id": "b" * 64,
                                     "destination_level": 47, "max_steps": 15,
                                     "checkpoint_sha256": digest(checkpoint),
                                     "search_result_pointer": search_result.name})
            graph.add_entrypoint("oracle-us", "near-checkpoint")
            graph_path = root / "graph.json"
            graph.save(graph_path)
            FakeWorker.observations = [b"same", b"same"]

            def fake_cross(worker, **kwargs):
                self.assertEqual(kwargs["source_identity"]["id"], "b" * 64)
                path = worker.root / "checkpoint-e1.json"
                path.with_suffix(".State").write_bytes(b"state")
                path.with_suffix(".side").write_bytes(b"side")
                path.write_text(json.dumps({
                    "kind": "jfg-phase95-checkpoint", "schema": 1,
                    "rdram_sha256": hashlib.sha256(b"same").hexdigest(),
                    "observation": {"frame": 10, "polls": 5, "player": 123},
                    "digests": {"State": digest(path.with_suffix(".State")),
                                "side": digest(path.with_suffix(".side"))}}))
                (worker.root / "exit-result.json").write_text(json.dumps({
                    "completed": True, "destination_level": 47,
                    "final_observation": {"step": 3, "level": 47,
                                          "player_name": "playerBoy"}}))
                return {"completed": True, "final_observation": {"step": 3}}

            with patch("scripts.phase95_frontier_job.preflight", return_value={}):
                result = run(graph_path, root / "out", checkpoint, root / "emu.exe",
                             root / "rom.z64", root / "bridge.lua", "c" * 64,
                             "job-cross", worker_type=FakeWorker,
                             crosser=fake_cross, poll_selector=fake_polls,
                             private_root=root)
            self.assertEqual(result["outcome"], "covered")
            self.assertEqual(result["attempts"][0]["checkpoint"],
                             "attempt-01/checkpoint-e1.json")
            snapshot = FrontierGraph.load(root / "out" / "frontier-evidence.json")
            self.assertIn(result["next_checkpoint"]["node"],
                          snapshot.reached_nodes("oracle-us"))
            self.assertEqual(snapshot.nodes[result["next_checkpoint"]["node"]][
                "metadata"]["source_level"], 47)

    def test_bounded_search_incomplete_schedules_larger_reviewable_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text("synthetic")
            graph = FrontierGraph()
            graph.add_node("start", "checkpoint")
            graph.add_node("near", "objective")
            graph.add_node("near-sibling", "objective")
            graph.add_edge("near", "start", "near", "objective", priority=4,
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata={"driver": "search-exit", "exit_id": "b" * 64,
                                     "max_nodes": 128, "max_expansions": 40,
                                     "radius": 25,
                                     "checkpoint_sha256": digest(checkpoint)})
            graph.add_edge("near-sibling", "start", "near-sibling", "objective",
                           priority=5, source_variant="us",
                           required_capabilities=("search-exit",),
                           metadata={"driver": "search-exit", "exit_id": "c" * 64,
                                     "max_nodes": 128, "max_expansions": 40,
                                     "radius": 25,
                                     "checkpoint_sha256": digest(checkpoint)})
            graph.add_entrypoint("oracle-us", "start")
            graph_path = root / "graph.json"
            graph.save(graph_path)
            FakeWorker.observations = [b"same"]

            def incomplete(worker, *_args, **_kwargs):
                (worker.root / "search-failure.json").write_text(json.dumps({
                    "kind": "jfg-phase95-search-incomplete", "nodes": 110,
                    "reason": "bounded search exhausted", "unreachable": False}))
                (worker.root / "world-inventory.json").write_text(json.dumps({
                    "kind": "jfg-phase95-observed-world", "schema": 1,
                    "level": 21,
                    "exits": [{"id": "b" * 64, "source_level": 21,
                               "position": [46, 64, -2090]},
                              {"id": "c" * 64, "source_level": 21,
                               "position": [46, 64, -2090]}]}))
                raise ObservationError("bounded exploration incomplete")

            with patch("scripts.phase95_frontier_job.preflight", return_value={}):
                result = run(graph_path, root / "out", checkpoint, root / "emu.exe",
                             root / "rom.z64", root / "bridge.lua", "c" * 64,
                             "job-search-incomplete", worker_type=FakeWorker,
                             searcher=incomplete, private_root=root)
            self.assertEqual(result["outcome"], "blocked")
            self.assertEqual(result["retry_edge_id"], "near:retry-1")
            snapshot = FrontierGraph.load(root / "out" / "frontier-evidence.json")
            self.assertEqual(snapshot.status("near", "oracle-us"), "blocked")
            self.assertEqual(snapshot.status("near-sibling", "oracle-us"), "blocked")
            retry = select(snapshot)
            self.assertEqual(retry["id"], "near:retry-1")
            self.assertEqual(retry["metadata"]["max_nodes"], 256)
            self.assertEqual(retry["metadata"]["max_expansions"], 80)
            self.assertEqual(retry["metadata"]["retry_tier"], 1)

    def test_maxed_ordinary_search_schedules_jump_retry_once(self):
        from scripts.phase95_frontier_job import add_incomplete_search_retry

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            worker = root / "attempt-01"
            worker.mkdir()
            (worker / "search-failure.json").write_text(json.dumps({
                "kind": "jfg-phase95-search-incomplete", "nodes": 193,
                "reason": "bounded search exhausted", "unreachable": False}))
            graph = FrontierGraph()
            graph.add_node("start", "checkpoint")
            graph.add_node("near", "objective")
            graph.add_edge("near", "start", "near", "objective", priority=4,
                           source_variant="us", required_capabilities=("search-exit",),
                           metadata={"driver": "search-exit", "exit_id": "b" * 64,
                                     "max_nodes": 256, "max_expansions": 100,
                                     "radius": 25, "checkpoint_sha256": "a" * 64,
                                     "retry_parent": "older", "retry_tier": 2})
            retry_id = add_incomplete_search_retry(graph, graph.edges["near"], root)
            self.assertEqual(retry_id, "near:retry-3")
            retry = graph.edges[retry_id]
            self.assertTrue(retry["metadata"]["jump"])
            self.assertEqual(retry["metadata"]["max_nodes"], 256)
            self.assertEqual(retry["metadata"]["max_expansions"], 100)
            self.assertIsNone(add_incomplete_search_retry(graph, retry, root))

    def test_auto_transition_blocks_same_source_searches_without_retry(self):
        from scripts.phase95_frontier_job import (
            add_incomplete_search_retry, block_auto_transition_source)

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            worker = root / "attempt-01"
            worker.mkdir()
            (worker / "search-failure.json").write_text(json.dumps({
                "kind": "jfg-phase95-search-incomplete", "nodes": 1,
                "reason": "source checkpoint auto-transitions before explored move",
                "source_auto_transition": True, "observed_levels": [48],
                "trials": 8, "unreachable": False}))
            graph = FrontierGraph()
            for node in ("source", "other", "selected", "sibling", "remote"):
                graph.add_node(node, "checkpoint" if node in ("source", "other")
                               else "objective")
            common = {"driver": "search-exit", "exit_id": "a" * 64}
            for edge_id, source, target in (
                    ("selected", "source", "selected"),
                    ("sibling", "source", "sibling"),
                    ("remote", "other", "remote")):
                graph.add_edge(edge_id, source, target, "objective",
                               source_variant="us", metadata=common)
            blocked = block_auto_transition_source(
                graph, graph.edges["selected"], root, "job")
            self.assertEqual(blocked, ["sibling"])
            self.assertEqual(graph.status("sibling", "oracle-us"), "blocked")
            self.assertEqual(graph.status("remote", "oracle-us"), "unexplored")
            self.assertIsNone(add_incomplete_search_retry(
                graph, graph.edges["selected"], root))

    def test_successful_retry_covers_its_same_exit_ancestor(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "job"
            worker = output / "attempt-01"
            worker.mkdir(parents=True)
            checkpoint = worker / "checkpoint-c1.json"
            memory_sha = hashlib.sha256(b"same").hexdigest()
            checkpoint.write_text(json.dumps({"kind": "jfg-phase95-checkpoint",
                                              "rdram_sha256": memory_sha}))
            (worker / "search-result.json").write_text(json.dumps({
                "kind": "jfg-phase95-checkpoint-search", "completed": True,
                "replay_equal": True, "final_rdram_sha256": memory_sha,
                "exit_identity": {"id": "b" * 64, "source_level": 21,
                                  "destination_level": 47, "world_gate": -1}}))
            graph = FrontierGraph()
            graph.add_node("start", "checkpoint", metadata={"source_level": 21})
            graph.add_node("near", "objective")
            spec = {"driver": "search-exit", "exit_id": "b" * 64,
                    "max_nodes": 128, "max_expansions": 40, "radius": 25,
                    "checkpoint_sha256": "a" * 64}
            graph.add_edge("near", "start", "near", "objective",
                           source_variant="us", metadata=spec)
            graph.record("miss", "near", "oracle-us", "blocked", "miss.json",
                         reason="bounded search incomplete")
            graph.add_edge("near:retry-1", "start", "near", "objective",
                           source_variant="us", metadata={
                               **spec, "max_nodes": 256, "max_expansions": 80,
                               "retry_parent": "near", "retry_tier": 1})
            promotion = promote_search_checkpoint(
                graph, graph.edges["near:retry-1"], output, "retry-job",
                [{"checkpoint": "attempt-01/checkpoint-c1.json"}],
                private_root=root)
            self.assertEqual(promotion["same_exit_covered_edges"], ["near"])
            self.assertEqual(graph.status("near", "oracle-us"), "covered")

    def test_rejects_public_output_before_preflight_or_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            private = root / "private"
            private.mkdir()
            checkpoint = private / "checkpoint.json"
            checkpoint.write_text("synthetic")
            graph_path = private / "graph.json"
            fixture_graph(hashlib.sha256(b"synthetic").hexdigest()).save(graph_path)
            public_output = root / "public-output"
            with patch("scripts.phase95_frontier_job.preflight") as check:
                with self.assertRaisesRegex(ValueError, "output must be inside"):
                    run(graph_path, public_output, checkpoint, root / "emu.exe",
                        root / "rom.z64", root / "bridge.lua", "b" * 64,
                        "job-3", private_root=private)
            check.assert_not_called()
            self.assertFalse(public_output.exists())


if __name__ == "__main__":
    unittest.main()
