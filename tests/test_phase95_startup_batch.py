import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase95_startup_batch import inspect_job, run_batch


class StartupBatchTests(unittest.TestCase):
    def test_accepts_only_fresh_gameplay_and_exact_restore(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(json.dumps({
                "session": "isolated-1", "initial_save": "fresh isolated worker",
                "rom_sha256": "r", "emulator_sha256": "e", "config_sha256": "c",
                "script_sha256": "s", "runtime_sha256": "u"}))
            (root / "startup-result.json").write_text(json.dumps({
                "endpoint": "player-mode-16", "state": {"front_mode": 16,
                "level_number": 92, "player": 1, "frame": 10, "polls": 5}}))
            (root / "movement-result.json").write_text(json.dumps({
                "checkpoint_continuation_equal": True, "checkpoint_steps": 6}))
            (root / "bridge-result.txt").write_text("stopped\n")
            (root / "keyboard-entry.rdram").write_bytes(b"startup")
            (root / "observation.rdram").write_bytes(b"final")
            self.assertTrue(inspect_job(root)["passed"])
            (root / "movement-result.json").write_text(json.dumps({
                "checkpoint_continuation_equal": False, "checkpoint_steps": 6}))
            self.assertFalse(inspect_job(root)["passed"])
            (root / "movement-result.json").write_text(json.dumps({
                "checkpoint_continuation_equal": True, "checkpoint_steps": 6}))
            (root / "manifest.json").write_text(json.dumps({
                "session": "isolated-1", "initial_save": "existing SaveRAM",
                "rom_sha256": "r", "emulator_sha256": "e", "config_sha256": "c",
                "script_sha256": "s", "runtime_sha256": "u"}))
            self.assertFalse(inspect_job(root)["passed"])

    def test_rejects_existing_output_and_invalid_count(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                run_batch(root, None, None, "unused", 10)
            with self.assertRaises(ValueError):
                run_batch(root / "new", None, None, "unused", 11)


if __name__ == "__main__":
    unittest.main()
