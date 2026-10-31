"""Synthetic discovery tests: no emulator or ROM is launched."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.phase95_bridge import digest
from scripts.phase95_frontier_discover import register, run
from scripts.phase95_frontier_graph import FrontierGraph


EXIT_ID = "a" * 64


def observed(exit_id=EXIT_ID):
    return {"kind": "jfg-phase95-observed-world", "schema": 1,
            "acceptance": False, "level": 47,
            "exits": [{"id": exit_id, "source_level": 47,
                       "destination_level": 48, "position": [120, 0, 0]}],
            "coverage_denominator": "unknown"}


class FakeWorker:
    memories = [b"equal", b"equal"]

    def __init__(self, root, *_):
        self.root = root
        root.mkdir()
        self.number = int(root.name[-2:])

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def observe(self):
        return ({"sequence": 3, "frame": 100, "polls": 40, "player": 123},
                self.memories[self.number - 1])

    def import_checkpoint(self, path):
        assert path.exists()


class FrontierDiscoveryTests(unittest.TestCase):
    def test_two_matching_workers_register_uncovered_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text("synthetic sealed checkpoint")
            FakeWorker.memories = [b"equal", b"equal"]
            with patch("scripts.phase95_frontier_discover.preflight", return_value={}):
                result = run(checkpoint, root / "out", root / "emu.exe", root / "rom.z64",
                             root / "bridge.lua", "b" * 64, worker_type=FakeWorker,
                             inventory_reader=lambda *_: observed(),
                             position_reader=lambda *_: [0, 0, 0], private_root=root)
            self.assertTrue(result["deterministic"])
            self.assertFalse(result["coverage_claim"])
            self.assertEqual(len(result["registered_edges"]), 1)
            graph = FrontierGraph.load(root / "out" / "frontier-graph.json")
            edge_id = result["registered_edges"][0]
            self.assertEqual(graph.frontier("oracle-us", capabilities=("search-exit",)),
                             [edge_id])
            self.assertEqual(graph.status(edge_id, "oracle-us"), "unexplored")
            self.assertEqual(graph.edges[edge_id]["metadata"]["checkpoint_sha256"],
                             digest(checkpoint))
            self.assertEqual(graph.edges[edge_id]["priority"], 120)

    def test_independent_disagreement_does_not_publish_edges(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text("synthetic")
            FakeWorker.memories = [b"one", b"two"]
            with patch("scripts.phase95_frontier_discover.preflight", return_value={}):
                result = run(checkpoint, root / "out", root / "emu.exe", root / "rom.z64",
                             root / "bridge.lua", "b" * 64, worker_type=FakeWorker,
                             inventory_reader=lambda *_: observed(),
                             position_reader=lambda *_: [0, 0, 0], private_root=root)
            self.assertFalse(result["deterministic"])
            self.assertFalse((root / "out" / "frontier-graph.json").exists())
            self.assertTrue((root / "out" / "result.json").exists())

    def test_planner_source_change_does_not_publish_edges(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text("synthetic")
            FakeWorker.memories = [b"equal", b"equal"]
            pins = ({"sha256": "a" * 64, "files": {}},
                    {"sha256": "b" * 64, "files": {}})
            with patch("scripts.phase95_frontier_discover.preflight", return_value={}), \
                    patch("scripts.phase95_frontier_discover.source_pin", side_effect=pins):
                result = run(checkpoint, root / "out", root / "emu.exe",
                             root / "rom.z64", root / "bridge.lua", "b" * 64,
                             worker_type=FakeWorker,
                             inventory_reader=lambda *_: observed(),
                             position_reader=lambda *_: [0, 0, 0], private_root=root)
            self.assertFalse(result["deterministic"])
            self.assertFalse(result["planner_source_stable"])
            self.assertFalse((root / "out" / "frontier-graph.json").exists())

    def test_existing_graph_requires_reached_matching_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint = root / "checkpoint.json"
            checkpoint.write_text("synthetic")
            graph = FrontierGraph()
            graph.add_node("source", "checkpoint",
                           metadata={"checkpoint_sha256": digest(checkpoint)})
            graph_path = root / "graph.json"
            graph.save(graph_path)
            with patch("scripts.phase95_frontier_discover.preflight", return_value={}):
                with self.assertRaisesRegex(ValueError, "no reached matching"):
                    run(checkpoint, root / "out", root / "emu.exe", root / "rom.z64",
                        root / "bridge.lua", "b" * 64, graph_path=graph_path,
                        checkpoint_node="source", private_root=root)
            self.assertFalse((root / "out").exists())

    def test_registration_rejects_unsupported_source_and_exit_identity(self):
        graph = FrontierGraph()
        graph.add_node("source", "checkpoint", metadata={"checkpoint_sha256": "b" * 64})
        graph.add_entrypoint("oracle-us", "source")
        with self.assertRaisesRegex(ValueError, "sealed source"):
            register(graph, "source", "c" * 64, observed(), "result.json", [0, 0, 0])
        with self.assertRaisesRegex(ValueError, "identity"):
            register(graph, "source", "b" * 64, observed("bad"), "result.json", [0, 0, 0])


if __name__ == "__main__":
    unittest.main()
