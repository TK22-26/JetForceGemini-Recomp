import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.phase95_bridge import digest, runtime_digest
from scripts.phase95_checkpoint_visual import PNG_SIGNATURE, capture


class CheckpointVisualTests(unittest.TestCase):
    def test_sealed_checkpoint_capture_checks_state_and_png(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory)
            emulator_dir = private / "emulator-source"
            emulator_dir.mkdir()
            emulator = emulator_dir / "EmuHawk.exe"
            emulator.write_bytes(b"synthetic executable")
            (emulator_dir / "config.ini").write_text("{}\n")
            rom = private / "game.z64"
            rom.write_bytes(b"synthetic ROM")
            rom_sha = digest(rom)
            memory = bytes(0x400000)
            memory_sha = hashlib.sha256(memory).hexdigest()
            checkpoint = private / "checkpoint.json"
            state_file = checkpoint.with_suffix(".State")
            side_file = checkpoint.with_suffix(".side")
            state_file.write_bytes(b"synthetic savestate")
            side_file.write_text("abc 1 2\n")
            identity = {"rom_sha256": rom_sha,
                        "emulator_sha256": digest(emulator),
                        "runtime_sha256": runtime_digest(emulator_dir),
                        "config_sha256": digest(emulator_dir / "config.ini"),
                        "script_sha256": "a" * 64}
            checkpoint.write_text(json.dumps({
                "kind": "jfg-phase95-checkpoint", "schema": 1,
                "identity": identity, "rdram_sha256": memory_sha,
                "observation": {"frame": 123},
                "digests": {"State": digest(state_file), "side": digest(side_file)}}))
            output = private / "capture"

            def fake_command(_argv, _cwd, _stdout, _stderr, _deadline,
                             _heartbeat, _pause_file, **kwargs):
                self.assertEqual(kwargs["environment_overrides"][
                    "JFG_PHASE95_VISUAL_STATE"], str(state_file))
                (output / "visual.rdram").write_bytes(memory)
                (output / "visual.png").write_bytes(PNG_SIGNATURE + bytes(120))
                (output / "visual-status.txt").write_text("captured\n")
                return 0, None

            result = capture(checkpoint, output, emulator, rom, rom_sha,
                             private_root=private, command_runner=fake_command)
            self.assertTrue(result["read_only"])
            self.assertEqual(result["source_rdram_sha256"], memory_sha)
            self.assertEqual(json.loads((output / "visual-result.json").read_text()),
                             result)


if __name__ == "__main__":
    unittest.main()
