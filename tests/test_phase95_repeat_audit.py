import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase95_repeat_audit import audit


class FrozenRepeatAuditTests(unittest.TestCase):
    def fixture(self, root):
        scenario = root / "scenario"
        repeat = root / "repeat"
        scenario.mkdir()
        repeat.mkdir()
        stages = []
        for index in range(7):
            raw = f"stage-{index}".encode()
            stages.append({"stage": index, "name": f"stage-{index}",
                           "frame": (index + 1) * 10,
                           "rdram_sha256": hashlib.sha256(raw).hexdigest()})
            if index in (0, 3, 5, 6):
                (repeat / f"checkpoint-{(index + 1) * 10:06d}.rdram").write_bytes(raw)
        (scenario / "scenario-stages.jsonl").write_text(
            "".join(json.dumps(stage) + "\n" for stage in stages))
        (scenario / "scenario-result.json").write_text(json.dumps({
            "completed": True, "stages_completed": 7,
            "final_rdram_sha256": stages[-1]["rdram_sha256"]}))
        oracle = {"kind": "jfg-phase95-oracle-poll-replay", "exit_code": 0,
                  "trace_complete": True, "target_frame": 70,
                  "input_clock": "controller-poll", "input_sha256": "i",
                  "final_rdram_sha256": stages[-1]["rdram_sha256"]}
        oracle.update({key: "p" for key in
                       ("source_export_sha256", "rom_sha256", "emulator_sha256",
                        "config_sha256", "runtime_sha256", "script_sha256")})
        (repeat / "oracle-result.json").write_text(json.dumps(oracle))
        return scenario, repeat

    def test_matching_replay_and_duplicate_root_rejection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            scenario, repeat = self.fixture(root)
            result = audit(scenario, [repeat], root / "audit.json")
            self.assertTrue(result["all_match"])
            self.assertEqual(len(result["repeats"][0]["checkpoints"]), 4)
            with self.assertRaisesRegex(ValueError, "distinct worker roots"):
                audit(scenario, [repeat, repeat], root / "duplicate.json")

    def test_gameplay_checkpoint_mismatch_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            scenario, repeat = self.fixture(root)
            (repeat / "checkpoint-000040.rdram").write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError, "stage 3"):
                audit(scenario, [repeat], root / "audit.json")


if __name__ == "__main__":
    unittest.main()
