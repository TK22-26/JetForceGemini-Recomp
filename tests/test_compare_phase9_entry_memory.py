import json
from pathlib import Path
import tempfile
import unittest

from scripts.compare_phase9_entry_memory import compare


class EntryMemoryComparisonTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[Path, Path]:
        native = root / "native"
        oracle = root / "oracle"
        native.mkdir()
        oracle.mkdir()
        shared = {"source_export": "selected", "input_sha256": "input",
                  "rom_sha256": "rom"}
        (native / "native-result.json").write_text(json.dumps({
            **shared, "entry_memory_trace_complete": True,
            "entry_trace_complete": True, "entry_target": "0x800743d0",
            "initial_flash_sha256": "flash", "executable_sha256": "native"}))
        (oracle / "oracle-result.json").write_text(json.dumps({
            **shared, "entry_memory_trace_complete": True,
            "entry_trace_complete": True, "entry_pc": "0x800743d0",
            "oracle_initial_flash_sha256": "flash",
            "initial_flash_matches_candidate": True,
            "emulator_sha256": "bizhawk", "script_sha256": "lua"}))
        (native / "entry-args.tsv").write_text(
            "update_candidate\tvi_retraces\tcontroller_polls\ttarget\ta0\ta1\ta2\ta3\n"
            "1265\t2675\t1268\t0x800743d0\t0x80360138\t0x800f8dc8\t0x8035fb80\t0x80359f38\n")
        (oracle / "entry-args.tsv").write_text(
            "frame\tcompleted_updates\tcontroller_polls\tconsumed_vi\tpc\ta0\ta1\ta2\ta3\n"
            "2909\t1260\t1270\t2880\t0x800743d0\t0x80360138\t0x800f8dc8\t0x8035fb80\t0x80359f38\n"
            "result\ttrue\t1\n")
        zeros = "00000000" * 32
        altered = "00000001" + "00000000" * 31
        (native / "entry-memory.tsv").write_text(
            "update_candidate\tvi_retraces\tcontroller_polls\ttarget\t"
            "a1_128\ta2_128\ta3_128\n"
            f"1265\t2675\t1268\t0x800743d0\t{zeros}\t{zeros}\t{zeros}\n")
        (oracle / "entry-memory.tsv").write_text(
            "frame\tcompleted_updates\tcontroller_polls\tconsumed_vi\tpc\t"
            "a1_128\ta2_128\ta3_128\n"
            f"2909\t1260\t1270\t2880\t0x800743d0\t{zeros}\t{zeros}\t{altered}\n"
            "result\ttrue\t1\n")
        return native, oracle

    def test_reports_exact_word_without_claiming_parity(self):
        with tempfile.TemporaryDirectory() as temporary:
            native, oracle = self.fixture(Path(temporary))
            report = compare(native, oracle, native_update=1265,
                             oracle_completed=1260, a0=0x80360138,
                             a3=0x80359F38)
            self.assertEqual(report["mismatch_count"], 1)
            self.assertEqual(report["mismatches"][0]["argument"], "a3")
            self.assertEqual(report["mismatches"][0]["offset"], 0)
            self.assertFalse(report["parity_verified"])

    def test_rejects_wrong_selector_and_truncated_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            native, oracle = self.fixture(Path(temporary))
            with self.assertRaises(ValueError):
                compare(native, oracle, native_update=1265,
                        oracle_completed=1260, a0=0x80360138, a3=0x80359F39)
            trace = oracle / "entry-memory.tsv"
            trace.write_text(trace.read_text().replace("result\ttrue\t1\n", ""))
            with self.assertRaises(ValueError):
                compare(native, oracle, native_update=1265,
                        oracle_completed=1260, a0=0x80360138, a3=0x80359F38)

    def test_accepts_wider_bounded_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            native, oracle = self.fixture(Path(temporary))
            for directory in (native, oracle):
                trace = directory / "entry-memory.tsv"
                lines = trace.read_text().splitlines()
                lines[0] = lines[0].replace("_128", "_256")
                values = lines[1].split("\t")
                values[-3:] = [value + "00000000" * 32 for value in values[-3:]]
                lines[1] = "\t".join(values)
                trace.write_text("\n".join(lines) + "\n")
            report = compare(native, oracle, native_update=1265,
                             oracle_completed=1260, a0=0x80360138,
                             a3=0x80359F38)
            self.assertEqual(report["memory_span_bytes"], 256)


if __name__ == "__main__":
    unittest.main()
