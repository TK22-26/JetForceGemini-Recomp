import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.phase95_bridge import Action, Worker, parse_ready


class ProtocolTests(unittest.TestCase):
    def test_action(self):
        self.assertEqual(Action(12, 32768, -80, 0).encode("abc", 2),
                         "phase95-v1 abc 2 12 32768 -80 0\n")

    def test_invalid_actions(self):
        for action in (Action(-1), Action(121), Action(True), Action(1, 65536),
                       Action(1, 0, -129), Action(1, 0, 0, 128), Action(0, 1)):
            with self.subTest(action=action), self.assertRaises(ValueError):
                action.encode("abc", 0)

    def test_session_and_sequence(self):
        for session, seq in (("bad token", 0), ("", 0), ("abc", -1), ("abc", True)):
            with self.assertRaises(ValueError):
                Action().encode(session, seq)

    def test_ready(self):
        value = parse_ready("phase95-v1 abc 2 120 4 0\n", "abc", 2)
        self.assertEqual(value["frame"], 120)

    def test_reject_bad_ready(self):
        for text in ("phase95-v1 def 2 120 4 0", "phase95-v1 abc 1 120 4 0",
                     "phase95-v1 abc 2 -1 4 0", "phase95-v1 abc 2 1 4 4294967296",
                     "phase95-v1 abc 2 1 4 0 extra"):
            with self.assertRaises(ValueError):
                parse_ready(text, "abc", 2)


class ObservationTransportTests(unittest.TestCase):
    def worker(self, root):
        worker = Worker.__new__(Worker)
        worker.root = root
        worker.timeout = 1
        worker.session = "abc"
        worker.sequence = 2
        worker.observed = False
        worker.pending_checkpoint = None
        worker.process = Mock()
        worker.process.poll.return_value = None
        return worker

    def test_transient_read_failure_retries_same_observation(self):
        for exception in (PermissionError, FileNotFoundError):
            for target in ("header", "memory"):
                with self.subTest(exception=exception, target=target), tempfile.TemporaryDirectory() as directory:
                    worker = self.worker(Path(directory))
                    header = "phase95-v1 abc 2 120 4 0"
                    memory = bytes(0x400000)
                    with patch.object(Path, "read_text", side_effect=(
                            [exception(), header] if target == "header" else [header, header])), patch.object(
                            Path, "read_bytes", side_effect=(
                            [exception(), memory] if target == "memory" else [memory])), patch(
                            "scripts.phase95_bridge.time.sleep"):
                        metadata, actual = worker.observe()
                    self.assertEqual(actual, memory)
                    self.assertEqual(metadata["sequence"], 2)
                    self.assertEqual(worker.sequence, 2)
                    self.assertEqual(len((worker.root / "observations.jsonl").read_text().splitlines()), 1)

    def test_persistent_denial_obeys_original_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = self.worker(Path(directory))
            with patch.object(Path, "read_text", side_effect=PermissionError), patch(
                    "scripts.phase95_bridge.time.monotonic", side_effect=[0, 0, 2]), patch(
                    "scripts.phase95_bridge.time.sleep"), self.assertRaises(TimeoutError):
                worker.observe()
            self.assertFalse(worker.observed)

    def test_malformed_observation_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = self.worker(Path(directory))
            with patch.object(Path, "read_text", return_value="bad"), patch.object(
                    Path, "read_bytes", return_value=bytes(0x400000)), patch(
                    "scripts.phase95_bridge.time.sleep") as sleep, self.assertRaises(ValueError):
                worker.observe()
            sleep.assert_not_called()

    def test_exited_process_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = self.worker(Path(directory))
            worker.process.poll.return_value = 1
            with self.assertRaisesRegex(RuntimeError, "oracle exited"):
                worker.observe()


if __name__ == "__main__":
    unittest.main()
