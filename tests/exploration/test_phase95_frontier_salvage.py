"""Synthetic paired-frontier evidence tests; no emulator or private ROM."""

import json
from pathlib import Path
import tempfile
import unittest

from scripts.phase95_bridge import digest
from scripts.phase95_frontier_salvage import salvage


EXIT_ID = "a" * 64
IDENTITY = {key: key + "-pinned" for key in (
    "rom_sha256", "emulator_sha256", "runtime_sha256", "config_sha256",
    "script_sha256")}


def worker(root, session, sample=(0, 0, 60)):
    root.mkdir()
    manifest = {"kind": "jfg-phase95-worker", "schema": 1,
                "session": session, **IDENTITY}
    (root / "manifest.json").write_text(json.dumps(manifest))
    (root / "world-inventory.json").write_text(json.dumps({
        "kind": "jfg-phase95-observed-world", "level": 47,
        "exits": [{"id": EXIT_ID, "source_level": 47,
                   "position": [0.0, 2.0, 0.0]}]}))
    (root / "search-failure.json").write_text(json.dumps({
        "kind": "jfg-phase95-search-incomplete", "unreachable": False}))
    node = {"id": 0, "slot": "a0000", "position": [1.0, 2.0, 3.0],
            "sha256": "b" * 64,
            "counters": {"frame": 10, "polls": 1, "player": 42}}
    (root / "search-nodes.jsonl").write_text(json.dumps(node) + "\n")
    state = root / "checkpoint-a0000.State"
    side = root / "checkpoint-a0000.side"
    state.write_bytes(b"synthetic state")
    side.write_text(f"{session} 1 10\n")
    (root / "checkpoint-a0000.json").write_text(json.dumps({
        "kind": "jfg-phase95-checkpoint", "schema": 1,
        "identity": manifest,
        "observation": {"frame": 10, "polls": 1, "player": 42},
        "rdram_sha256": "b" * 64,
        "digests": {"State": digest(state), "side": digest(side)}}))
    (root / "input-polls.tsv").write_text(
        f"schema\t1\tsession\t{session}\n"
        f"1\t10\t1\t{sample[0]}\t{sample[1]}\t{sample[2]}\n"
        "checkpoint\t1\tsave\ta0000\n")


class FrontierSalvageTests(unittest.TestCase):
    def test_identical_checkpoint_and_selected_inputs_are_paired(self):
        with tempfile.TemporaryDirectory() as temp:
            private = Path(temp)
            left, right, output = (private / name for name in ("left", "right", "pair"))
            worker(left, "left")
            worker(right, "right")
            result = salvage(left, right, EXIT_ID, output, private_root=private)
            self.assertTrue(result["paired"])
            self.assertFalse(result["acceptance"])
            self.assertFalse(result["native_parity_verified"])
            self.assertEqual(result["controller_polls"], 1)
            self.assertEqual(result["source_player_position"], [1.0, 2.0, 3.0])
            self.assertEqual(result["source_horizontal_distance"],
                             result["horizontal_distance"])
            self.assertEqual(result["checkpoint_pointers"],
                             ["left/checkpoint-a0000.json",
                              "right/checkpoint-a0000.json"])
            self.assertEqual(result, json.loads((output / "salvage-result.json").read_text()))

    def test_mismatched_selected_input_is_not_paired(self):
        with tempfile.TemporaryDirectory() as temp:
            private = Path(temp)
            left, right, output = (private / name for name in ("left", "right", "pair"))
            worker(left, "left")
            worker(right, "right", sample=(0, 0, -60))
            with self.assertRaisesRegex(ValueError, "no identical checkpoint"):
                salvage(left, right, EXIT_ID, output, private_root=private)
            self.assertFalse(output.exists())

    def test_mutated_state_or_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            private = Path(temp)
            left, right, output = (private / name for name in ("left", "right", "pair"))
            worker(left, "left")
            worker(right, "right")
            (right / "checkpoint-a0000.State").write_bytes(b"mutated")
            with self.assertRaisesRegex(ValueError, "checkpoint State digest mismatch"):
                salvage(left, right, EXIT_ID, output, private_root=private)
            self.assertFalse(output.exists())

    def test_output_cannot_be_inside_source_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            private = Path(temp)
            left, right = (private / name for name in ("left", "right"))
            worker(left, "left")
            worker(right, "right")
            with self.assertRaisesRegex(ValueError, "two distinct workers"):
                salvage(left, right, EXIT_ID, left / "nested", private_root=private)


if __name__ == "__main__":
    unittest.main()
