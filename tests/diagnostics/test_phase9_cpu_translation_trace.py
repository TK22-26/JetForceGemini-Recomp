import tempfile
import unittest
from pathlib import Path
from scripts.phase9_cpu_translation_trace import parse_trace


class TranslationTraceTests(unittest.TestCase):
    def trace(self):
        return ("kind\tindex\thi_or_ticks\tlo0_or_result\tlo1\tmask\n" +
                "".join(f"tlb\t{i}\t0x00000000\t0x00000000\t0x00000000\t0x00000000\n"
                        for i in range(32)) +
                "call\t0\t118\t0xffffffff\t-\t-\n"
                "call\t1\t42\t0x00001234\t-\t-\n"
                "call\t2\t58\t0x00001234\t-\t-\nresult\ttrue\n")

    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.tsv"
            path.write_text(text)
            return parse_trace(path)

    def test_null_result_observed_not_assumed(self):
        for result in ("0xffffffff", "0x00000000"):
            row = self.parse(self.trace().replace("0xffffffff", result))
            self.assertEqual(row["calls"][0]["result"], result)
            self.assertFalse(row["hardware_qualified"])

    def test_rejects_missing_entries_wrong_direct_result_and_zero_time(self):
        for text in (self.trace().replace("tlb\t31", "tlb\t30"),
                     self.trace().replace("0x00001234", "0xffffffff"),
                     self.trace().replace("\t118\t", "\t0\t"),
                     self.trace().replace("result\ttrue", "result\tfalse")):
            with self.assertRaises(ValueError):
                self.parse(text)

    def test_extra_reference_probes_are_distinct_from_architectural_claims(self):
        probes = [5, 0x80000005, 5, 0x80000005, 17, 0x80000011]
        trace = self.trace().replace("result\ttrue\n", "".join(
            f"probe\t{i}\t-\t0x{value:08x}\t-\t-\n" for i, value in enumerate(probes)) +
            "result\ttrue\t0x00000000\n")
        self.assertEqual(len(self.parse(trace)["additional_probe_indices"]), 6)
        with self.assertRaises(ValueError):
            self.parse(trace.replace("0x80000011", "0x00000011"))
