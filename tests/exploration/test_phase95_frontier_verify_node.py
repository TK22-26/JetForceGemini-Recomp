"""Synthetic selected-node verifier checks; no emulator or ROM is launched."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.phase95_frontier_verify_node import _nodes, _path, _same_observation


def saved_nodes(root):
    raw = b"synthetic state"
    common = {"position": [0.0, 0.0, 0.0], "yaw": 0,
              "sha256": hashlib.sha256(raw).hexdigest(),
              "counters": {"frame": 10, "polls": 5, "player": 42},
              "distance": 120.0}
    nodes = [{**common, "id": 0, "slot": "a0000", "parent": None,
              "depth": 0, "action": None},
             {**common, "id": 1, "slot": "a0001", "parent": 0,
              "depth": 1, "action": {"frames": 60, "buttons": 0,
                                      "x": 0, "y": 60}}]
    (root / "search-nodes.jsonl").write_text(
        "\n".join(json.dumps(node) for node in nodes) + "\n")
    return nodes, raw


class VerifyNodeTests(unittest.TestCase):
    def test_selected_parent_chain_and_observation_match(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _, raw = saved_nodes(root)
            nodes = _nodes(root)
            self.assertEqual([node["id"] for node in _path(nodes, 1)], [1])
            self.assertTrue(_same_observation(
                {"frame": 10, "polls": 5, "player": 42}, raw, nodes[1]))
            self.assertFalse(_same_observation(
                {"frame": 10, "polls": 6, "player": 42}, raw, nodes[1]))

    def test_invalid_parent_or_action_fails_before_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            nodes, _ = saved_nodes(root)
            nodes[1]["parent"] = 1
            (root / "search-nodes.jsonl").write_text(
                "\n".join(json.dumps(node) for node in nodes) + "\n")
            with self.assertRaisesRegex(ValueError, "invalid saved search node"):
                _nodes(root)
            nodes[1]["parent"] = 0
            nodes[1]["action"]["x"] = 200
            (root / "search-nodes.jsonl").write_text(
                "\n".join(json.dumps(node) for node in nodes) + "\n")
            with self.assertRaisesRegex(ValueError, "invalid bounded controller action"):
                _nodes(root)


if __name__ == "__main__":
    unittest.main()
