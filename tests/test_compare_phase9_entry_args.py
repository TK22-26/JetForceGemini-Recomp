import json
from pathlib import Path
import tempfile
import unittest

from scripts.compare_phase9_entry_args import compare


class EntryArgumentComparisonTests(unittest.TestCase):
    def test_first_mismatching_argument_is_reported_without_parity_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            native, oracle = Path(temporary) / "native", Path(temporary) / "oracle"
            native.mkdir()
            oracle.mkdir()
            common = {"input_sha256": "a" * 64, "rom_sha256": "b" * 64,
                      "source_export": "selected-input", "entry_trace_complete": True}
            (native / "native-result.json").write_text(json.dumps({
                **common, "entry_target": "0x02f0084c", "executable_sha256": "c" * 64,
                "initial_flash_sha256": "f" * 64,
            }))
            (oracle / "oracle-result.json").write_text(json.dumps({
                **common, "entry_pc": "0x8039078c", "emulator_sha256": "d" * 64,
                "script_sha256": "e" * 64, "config_sha256": "1" * 64,
                "runtime_sha256": "2" * 64,
                "oracle_initial_flash_sha256": "f" * 64,
                "initial_flash_matches_candidate": True,
            }))
            (native / "entry-args.tsv").write_text(
                "update_candidate\tvi_retraces\tcontroller_polls\ttarget\t"
                "a0\ta1\ta2\ta3\n"
                "1253\t2652\t1256\t0x02f0084c\t0x80303b50\t"
                "0x3d4cccce\t0x00000003\t0x00000003\n")
            (oracle / "entry-args.tsv").write_text(
                "frame\tcompleted_updates\tcontroller_polls\tconsumed_vi\t"
                "pc\ta0\ta1\ta2\ta3\n"
                "2885\t1248\t1258\t2856\t0x8039078c\t0x80303b50\t"
                "0x3d088889\t0x00000002\t0x00000002\n"
                "result\ttrue\t1\n")
            report = compare(native, oracle, native_update=1253,
                             oracle_completed=1248)
            self.assertTrue(report["all_a0_match"])
            self.assertEqual(report["first_argument_mismatch_call"], 0)
            self.assertFalse(report["calls"][0]["arguments"]["a1"]["match"])
            self.assertFalse(report["alignment_validated"])
            self.assertFalse(report["parity_verified"])

    def test_rejects_missing_oracle_completion(self):
        with tempfile.TemporaryDirectory() as temporary:
            native, oracle = Path(temporary) / "native", Path(temporary) / "oracle"
            native.mkdir()
            oracle.mkdir()
            for directory, name in ((native, "native-result.json"),
                                    (oracle, "oracle-result.json")):
                (directory / name).write_text(json.dumps({
                    "entry_trace_complete": False,
                }))
            with self.assertRaisesRegex(ValueError, "provenance or completion"):
                compare(native, oracle, native_update=1253, oracle_completed=1248)


if __name__ == "__main__":
    unittest.main()
