import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from scripts.phase95_goldwood_south_retry import run, validate_source


class SouthRetryCompositionTests(unittest.TestCase):
    def fixture(self, root):
        source = root / "source"
        source.mkdir()
        memory = bytearray(0xFB118)
        struct.pack_into(">i", memory, 0xFB114, 21)
        digest = hashlib.sha256(memory).hexdigest()
        checkpoint = source / "checkpoint-6e1.json"
        checkpoint.write_text(json.dumps({
            "kind": "jfg-phase95-checkpoint", "schema": 1,
            "rdram_sha256": digest,
            "observation": {"frame": 100, "polls": 50}}))
        (source / "common-south-result.json").write_text(json.dumps({
            "kind": "jfg-phase95-goldwood-common-south", "completed": True,
            "segments_completed": 15, "final_level": 21,
            "final_rdram_sha256": digest}))
        (source / "scenario-result.json").write_text(json.dumps({
            "kind": "jfg-phase95-goldwood-south-scenario", "completed": True,
            "stages_completed": 7, "final_level": 21,
            "final_rdram_sha256": digest}))
        return checkpoint, bytes(memory)

    def test_validated_composition_runs_ant_then_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint, memory = self.fixture(root)

            class Worker:
                def __init__(self):
                    self.root = root / "result"
                    self.root.mkdir()

                def observe(self):
                    return {"frame": 100, "polls": 50}, memory

            with mock.patch("scripts.phase95_goldwood_south_retry.approach",
                            return_value={"completed": True, "target_gap": 500,
                                          "target_proximity_verified": False,
                                          "live_ant_count": 2,
                                          "frontier_frame": 101,
                                          "frontier_rdram_sha256": "a" * 64}) as ant, \
                    mock.patch("scripts.phase95_goldwood_south_retry.run_retry",
                               return_value={"completed": True, "death_verified": True,
                                             "retry_verified": True,
                                             "death_frame": 102,
                                             "zero_health_sealed_frame": 103,
                                             "player_absent_frame": 104,
                                             "arrival_frames": [105, 106, 107],
                                             "verification_checkpoints": [
                                                 {"name": "health-zero", "frame": 102,
                                                  "rdram_sha256": "b" * 64}]}) as retry:
                result = run(Worker(), checkpoint)
            self.assertTrue(result["completed"])
            ant.assert_called_once()
            retry.assert_called_once()
            self.assertEqual(result["source"]["source_rdram_sha256"],
                             hashlib.sha256(memory).hexdigest())
            self.assertEqual([item["frame"] for item in
                              result["verification_checkpoints"]],
                             [100, 101, 102])

    def test_uncompleted_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint, _ = self.fixture(root)
            path = checkpoint.parent / "common-south-result.json"
            result = json.loads(path.read_text())
            result["completed"] = False
            path.write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, "completed common-south"):
                validate_source(checkpoint)

    def test_wrong_final_checkpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint, _ = self.fixture(root)
            wrong = checkpoint.parent / "checkpoint-6d1.json"
            wrong.write_bytes(checkpoint.read_bytes())
            with self.assertRaisesRegex(ValueError, "sealed health-pickup"):
                validate_source(wrong)


if __name__ == "__main__":
    unittest.main()
