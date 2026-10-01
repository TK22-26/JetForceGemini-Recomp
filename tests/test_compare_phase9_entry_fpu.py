import json
from pathlib import Path
import tempfile
import unittest

from scripts.compare_phase9_entry_fpu import FPR_FIELDS, GPR_FIELDS, compare


class EntryFpuComparisonTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path]:
        native = root / "native"
        oracle = root / "oracle"
        native.mkdir()
        oracle.mkdir()
        shared = {"source_export": "selected", "input_sha256": "input",
                  "rom_sha256": "rom"}
        (native / "native-result.json").write_text(json.dumps({
            **shared, "entry_fpu_trace_complete": True,
            "entry_trace_complete": True, "entry_target": "0x80074acc",
            "initial_flash_sha256": "flash", "executable_sha256": "native"}))
        (oracle / "oracle-result.json").write_text(json.dumps({
            **shared, "entry_fpu_trace_complete": True,
            "entry_trace_complete": True, "entry_pc": "0x80074acc",
            "oracle_initial_flash_sha256": "flash",
            "initial_flash_matches_candidate": True,
            "emulator_sha256": "bizhawk", "script_sha256": "lua"}))
        (native / "entry-args.tsv").write_text(
            "update_candidate\tvi_retraces\tcontroller_polls\ttarget\ta0\ta1\ta2\ta3\n"
            "1265\t2675\t1268\t0x80074acc\t0x80360138\t0x800f8dc8\t0x8035fb80\t0x80359f38\n")
        (oracle / "entry-args.tsv").write_text(
            "frame\tcompleted_updates\tcontroller_polls\tconsumed_vi\tpc\ta0\ta1\ta2\ta3\n"
            "2909\t1260\t1270\t2880\t0x80074acc\t0x80360138\t0x800f8dc8\t0x8035fb80\t0x80359f38\n"
            "result\ttrue\t1\n")
        fields = "\t".join(FPR_FIELDS)
        values = ["0x00000000"] * len(FPR_FIELDS)
        (native / "entry-fpu.tsv").write_text(
            "update_candidate\tvi_retraces\tcontroller_polls\ttarget\t" + fields +
            "\n1265\t2675\t1268\t0x80074acc\t" + "\t".join(values) + "\n")
        values[0] = "0x00000001"
        (oracle / "entry-fpu.tsv").write_text(
            "frame\tcompleted_updates\tcontroller_polls\tconsumed_vi\tpc\t" + fields +
            "\n2909\t1260\t1270\t2880\t0x80074acc\t" +
            "\t".join(values) + "\nresult\ttrue\t1\n")
        return native, oracle

    def test_reports_exact_word_without_claiming_parity(self):
        with tempfile.TemporaryDirectory() as temporary:
            native, oracle = self.fixture(Path(temporary))
            report = compare(native, oracle, native_update=1265,
                             oracle_completed=1260, a0=0x80360138,
                             a3=0x80359F38)
            self.assertEqual(report["mismatch_count"], 1)
            self.assertEqual(report["mismatches"][0]["register_word"], "f0_lo")
            self.assertEqual(report["a3"], "0x80359f38")
            self.assertFalse(report["parity_verified"])

    def test_rejects_wrong_a0_and_incomplete_oracle(self):
        with tempfile.TemporaryDirectory() as temporary:
            native, oracle = self.fixture(Path(temporary))
            with self.assertRaises(ValueError):
                compare(native, oracle, native_update=1265,
                        oracle_completed=1260, a0=0x80360139)
            trace = oracle / "entry-fpu.tsv"
            trace.write_text(trace.read_text().replace("result\ttrue\t1\n", ""))
            with self.assertRaises(ValueError):
                compare(native, oracle, native_update=1265,
                        oracle_completed=1260, a0=0x80360138)

    def test_gpr_uses_same_bounded_comparison_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            native, oracle = self.fixture(Path(temporary))
            for directory, result_name in ((native, "native-result.json"),
                                           (oracle, "oracle-result.json")):
                result = directory / result_name
                data = json.loads(result.read_text())
                data["entry_gpr_trace_complete"] = True
                result.write_text(json.dumps(data))
                lines = (directory / "entry-fpu.tsv").read_text().splitlines()
                header = lines[0].split("\t")
                header[-64:] = GPR_FIELDS
                (directory / "entry-gpr.tsv").write_text(
                    "\t".join(header) + "\n" + "\n".join(lines[1:]) + "\n")
            report = compare(native, oracle, native_update=1265,
                             oracle_completed=1260, a0=0x80360138,
                             register_kind="gpr")
            self.assertEqual(report["kind"], "jfg-phase9-entry-gpr-comparison")
            self.assertEqual(report["mismatches"][0]["register_word"], "r0_lo")


if __name__ == "__main__":
    unittest.main()
