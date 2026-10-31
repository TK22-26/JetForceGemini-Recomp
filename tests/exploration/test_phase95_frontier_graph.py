import json
from pathlib import Path
import tempfile
import unittest

from scripts.phase95_frontier_graph import FrontierGraph


def graph_fixture():
    graph = FrontierGraph()
    graph.add_node("start", "checkpoint", label="Fresh start")
    graph.add_node("goldwood", "level")
    graph.add_node("south", "branch")
    graph.add_node("east", "branch")
    graph.add_node("boss", "objective")
    graph.add_edge("enter-goldwood", "start", "goldwood", "transition", priority=1)
    graph.add_edge("south-route", "goldwood", "south", "branch", priority=20)
    graph.add_edge("east-route", "goldwood", "east", "branch", priority=10,
                   source_variant="jp", source_pointer="tas/movie.bk2#frame=2400")
    graph.add_edge("boss-from-east", "east", "boss", "objective",
                   required_capabilities=("player2-floyd",))
    graph.add_entrypoint("tas-jp", "start")
    graph.add_entrypoint("oracle-us", "start")
    return graph


class FrontierGraphTests(unittest.TestCase):
    def test_lane_local_reachability_and_deterministic_schedule(self):
        graph = graph_fixture()
        self.assertEqual(graph.frontier("tas-jp"), ["enter-goldwood"])
        graph.record("movie:1", "enter-goldwood", "tas-jp", "covered",
                     "movie.bk2#frame=1200")
        self.assertEqual(graph.frontier("tas-jp"), ["east-route", "south-route"])
        self.assertEqual(graph.frontier("oracle-us"), ["enter-goldwood"])
        graph.record("movie:2", "east-route", "tas-jp", "covered",
                     "movie.bk2#frame=2400")
        self.assertEqual(graph.frontier("tas-jp", capabilities=("player2-floyd",),
                                        limit=2),
                         ["south-route", "boss-from-east"])
        self.assertEqual(graph.frontier("tas-jp"), ["south-route"])
        self.assertEqual(graph.edges["east-route"]["source_variant"], "jp")
        self.assertEqual(graph.reached_nodes("tas-jp"),
                         ("east", "goldwood", "start"))

    def test_blocked_attempt_is_retryable_and_covered_supersedes(self):
        graph = graph_fixture()
        graph.record("failed", "enter-goldwood", "oracle-us", "blocked",
                     "runs/failed/journal.jsonl", reason="US exit mechanics differ")
        self.assertEqual(graph.status("enter-goldwood", "oracle-us"), "blocked")
        self.assertEqual(graph.frontier("oracle-us"), [])
        self.assertEqual(graph.frontier("oracle-us", include_blocked=True),
                         ["enter-goldwood"])
        graph.record("success", "enter-goldwood", "oracle-us", "covered",
                     "runs/success/oracle-result.json")
        self.assertEqual(graph.status("enter-goldwood", "oracle-us"), "covered")
        self.assertEqual(graph.frontier("oracle-us"), ["east-route", "south-route"])
        self.assertEqual(len(graph.evidence), 2)
        self.assertEqual(graph.evidence["failed"]["reason"],
                         "US exit mechanics differ")

    def test_resume_merge_is_idempotent_and_order_independent(self):
        left = graph_fixture()
        right = graph_fixture()
        left.record("tas:entry", "enter-goldwood", "tas-jp", "covered",
                    "route/events.jsonl#1")
        right.record("us:entry", "enter-goldwood", "oracle-us", "covered",
                     "runs/us/oracle-result.json")
        right.add_entrypoint("native-us", "start")
        merged = FrontierGraph.from_dict(left.to_dict()).merge(right).merge(right)
        reversed_merge = FrontierGraph.from_dict(right.to_dict()).merge(left)
        self.assertEqual(merged.to_dict(), reversed_merge.to_dict())
        self.assertEqual(len(merged.evidence), 2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frontier.json"
            merged.save(path)
            encoded = path.read_bytes()
            loaded = FrontierGraph.load(path)
            loaded.save(path)
            self.assertEqual(path.read_bytes(), encoded)
            self.assertEqual(loaded.to_dict(), merged.to_dict())
            self.assertEqual(json.loads(encoded)["schema"], 1)

    def test_conflicts_rejected_without_partial_merge(self):
        original = graph_fixture()
        conflicting = graph_fixture()
        conflicting.evidence["same"] = {
            "id": "same", "edge": "enter-goldwood", "lane": "tas-jp",
            "outcome": "covered", "pointer": "movie#1", "reason": None,
            "notes": None}
        original.record("same", "enter-goldwood", "tas-jp", "blocked", "movie#2",
                        reason="collision mismatch")
        before = original.to_dict()
        with self.assertRaises(ValueError):
            original.merge(conflicting)
        self.assertEqual(original.to_dict(), before)
        with self.assertRaises(ValueError):
            original.record("same", "enter-goldwood", "tas-jp", "covered", "movie#1")

    def test_schema_and_validation(self):
        graph = graph_fixture()
        self.assertEqual(graph.summary("oracle-us")["coverage_denominator"],
                         "declared edges only; full game unknown")
        self.assertEqual(graph.summary("oracle-us")["covered"], 0)
        with self.assertRaises(ValueError):
            graph.add_edge("bad", "missing", "goldwood", "transition")
        with self.assertRaises(ValueError):
            graph.add_edge("bad", "start", "goldwood", "transition", priority=True)
        with self.assertRaises(ValueError):
            graph.record("bad", "enter-goldwood", "tas-jp", "covered", "")
        with self.assertRaises(ValueError):
            graph.record("bad", "enter-goldwood", "tas-jp", "covered",
                         "C:\\private\\movie.bk2")
        with self.assertRaises(ValueError):
            graph.record("bad", "enter-goldwood", "oracle-us", "blocked",
                         "runs/failed/journal.jsonl")
        with self.assertRaises(ValueError):
            graph.add_edge("bad", "start", "goldwood", "transition",
                           required_capabilities="player2-floyd")
        document = graph.to_dict()
        document["schema"] = 2
        with self.assertRaises(ValueError):
            FrontierGraph.from_dict(document)


if __name__ == "__main__":
    unittest.main()
