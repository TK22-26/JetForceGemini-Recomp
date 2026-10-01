import json
from pathlib import Path
import tempfile
import unittest

from scripts.phase95_bridge import digest
from scripts.phase95_frontier_cycle import MAX_SPATIAL_DEPTH, graph_pointer
from scripts.phase95_frontier_graph import FrontierGraph
from scripts.phase95_frontier_import_chain import import_chain


class ImportChainTests(unittest.TestCase):
    def fixture(self, root):
        identity = {key: "a" * 64 for key in (
            "rom_sha256", "runtime_sha256", "config_sha256", "script_sha256")}

        def checkpoint(name, rdram):
            path = root / f"{name}.json"
            state = path.with_suffix(".State")
            side = path.with_suffix(".side")
            state.write_bytes(name.encode())
            side.write_text("abc 10 42\n")
            path.write_text(json.dumps({
                "kind": "jfg-phase95-checkpoint", "schema": 1,
                "identity": identity, "rdram_sha256": rdram,
                "observation": {"polls": 10},
                "digests": {"State": digest(state), "side": digest(side)}}))
            return path

        source = checkpoint("source", "0" * 64)
        middle = checkpoint("middle", "1" * 64)
        middle_repeat = checkpoint("middle-repeat", "1" * 64)
        final = checkpoint("final", "2" * 64)
        final_repeat = checkpoint("final-repeat", "2" * 64)
        graph = FrontierGraph()
        graph.add_node("source", "checkpoint", metadata={
            "checkpoint_pointer": graph_pointer(source, root),
            "checkpoint_sha256": digest(source), "source_level": 21})
        graph.add_node("exit", "objective")
        graph.add_edge("search", "source", "exit", "objective",
                       source_variant="us", required_capabilities=("search-exit",),
                       metadata={"driver": "search-exit", "exit_id": "b" * 64,
                                 "checkpoint_sha256": digest(source),
                                 "max_nodes": 128, "max_expansions": 40,
                                 "radius": 25})
        graph.add_entrypoint("oracle-us", "source")
        cycle = root / "cycle"
        cycle.mkdir()
        graph_path = cycle / "graph.json"
        graph.save(graph_path)
        (cycle / "state.json").write_text(json.dumps({
            "kind": "jfg-phase95-frontier-cycle", "schema": 1,
            "next_index": 0, "attempt": 0, "jobs": [],
            "graph": graph_pointer(graph_path, root),
            "graph_sha256": digest(graph_path), "status": "budget_exhausted",
            "pending_node_verification": None, "pending_export": None,
            "pending_verification": None, "pending_discovery": None}))
        tool = Path(__file__).resolve().parents[1] / "scripts" / "phase95_frontier_verify_node.py"

        def proof(name, before, after, repeat, rdram, x):
            path = root / f"{name}.json"
            path.write_text(json.dumps({
                "kind": "jfg-phase95-replayed-frontier-node", "schema": 1,
                "verification_tool_sha256": digest(tool),
                "source_level": 21, "exit_id": "b" * 64,
                "selected_node": 1, "selected_distance": 2000.0,
                "player_position": [float(x), 0.0, -100.0],
                "source_identity": identity, "rdram_sha256": rdram,
                "controller_polls": 10,
                "source_checkpoint_pointer": graph_pointer(before, root),
                "checkpoint_pointers": [graph_pointer(after, root),
                                        graph_pointer(repeat, root)],
                "checkpoint_sha256": [digest(after), digest(repeat)]}))
            return path

        first = proof("proof-one", source, middle, middle_repeat, "1" * 64, 100)
        second = proof("proof-two", middle, final, final_repeat, "2" * 64, 300)
        return cycle, first, second

    def test_imports_exact_chain_without_covering_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle, first, second = self.fixture(root)
            result = import_chain(cycle, cycle / "import", [first, second],
                                  private_root=root)
            self.assertFalse(result["exit_covered"])
            self.assertEqual(len(result["checkpoint_nodes"]), 2)
            state = json.loads((cycle / "state.json").read_text())
            graph = FrontierGraph.load(root / state["graph"])
            self.assertEqual(graph.status(result["continuation"], "oracle-us"),
                             "unexplored")
            for node in result["checkpoint_nodes"]:
                links = [edge for edge in graph.edges.values()
                         if edge["target"] == node and edge["kind"] == "progression"]
                self.assertEqual(len(links), 1)
                self.assertEqual(graph.status(links[0]["id"], "oracle-us"), "covered")

    def test_discontinuous_chain_does_not_advance_cycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle, first, second = self.fixture(root)
            altered = json.loads(second.read_text())
            altered["source_checkpoint_pointer"] = "source.json"
            altered["source_checkpoint_sha256"] = digest(root / "source.json")
            second.write_text(json.dumps(altered))
            prior = (cycle / "state.json").read_bytes()
            with self.assertRaisesRegex(ValueError, "discontinuous"):
                import_chain(cycle, cycle / "bad-import", [first, second],
                             private_root=root)
            self.assertEqual((cycle / "state.json").read_bytes(), prior)
            self.assertFalse((cycle / "bad-import").exists())

    def test_import_continues_past_legacy_eight_hop_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cycle, first, _ = self.fixture(root)
            graph_path = cycle / "graph.json"
            graph = FrontierGraph.load(graph_path)
            graph.nodes["source"]["metadata"]["salvage_depth"] = 8
            graph.save(graph_path)
            state_path = cycle / "state.json"
            state = json.loads(state_path.read_text())
            state["graph_sha256"] = digest(graph_path)
            state_path.write_text(json.dumps(state))
            result = import_chain(cycle, cycle / "deeper", [first],
                                  private_root=root)
            updated = FrontierGraph.load(root / json.loads(
                state_path.read_text())["graph"])
            self.assertEqual(updated.nodes[result["checkpoint_nodes"][0]][
                "metadata"]["salvage_depth"], 9)
            self.assertGreater(MAX_SPATIAL_DEPTH, 8)


if __name__ == "__main__":
    unittest.main()
