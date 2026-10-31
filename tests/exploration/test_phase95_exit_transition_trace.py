"""Synthetic single-frame trace tests; no emulator is launched."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.phase95_bridge import Action
from scripts.phase95_exit_transition_trace import trace


class FakeWorker:
    def __init__(self, root):
        self.root = root
        self.frame = 0
        self.actions = []

    def observe(self):
        return ({"sequence": self.frame, "frame": self.frame,
                 "polls": self.frame // 2, "player": 1}, bytes([self.frame]))

    def act(self, action):
        self.actions.append(action)
        self.frame += action.frames


class ExitTransitionTraceTests(unittest.TestCase):
    def test_trace_preserves_each_frame_and_first_actor_disappearance(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = FakeWorker(Path(directory))

            def fake_sample(metadata, memory, _exit_id):
                index = metadata["frame"]
                return {**metadata, "level": 21, "mode": 16,
                        "selected_exit_present": index < 2,
                        "rdram_sha256": hashlib.sha256(memory).hexdigest()}

            with patch("scripts.phase95_exit_transition_trace.sample",
                       side_effect=fake_sample):
                result = trace(worker, "a" * 64, Action(1, x=60), 3,
                               hashlib.sha256(b"\x03").hexdigest())
            self.assertTrue(result["final_equal"])
            self.assertEqual(result["observed_changes"][0]["index"], 2)
            self.assertEqual(len((worker.root / "transition-frames.jsonl").read_text(
                ).splitlines()), 4)
            self.assertEqual(len(worker.actions), 3)
            self.assertFalse(json.loads((worker.root / "transition-result.json").read_text())[
                "completion_claim"])

    def test_rejects_unbounded_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = FakeWorker(Path(directory))
            with self.assertRaisesRegex(ValueError, "frame budget"):
                trace(worker, "a" * 64, Action(1), 121)
            self.assertFalse((worker.root / "transition-frames.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
