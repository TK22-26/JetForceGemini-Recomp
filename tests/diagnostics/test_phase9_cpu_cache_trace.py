import tempfile
import unittest
from pathlib import Path

from scripts.phase9_cpu_cache_trace import CASES, parse_trace
from scripts.test_generated_os_cache import compare_cases


class CacheTraceTests(unittest.TestCase):
    def trace(self):
        return ("kind\tfunction\talignment\tlength\tvalue\n" + "".join(
            f"call\t{f}\t{a}\t{n}\t14\n" for f, a, n in CASES) + "".join(
            f"alias\t{f}\t{phase}\t-\t{value}\n" for f in range(4)
            for phase, value in enumerate(("0x13579bdf", "0x2468ace0", "0x2468ace0"))) +
            "result\ttrue\t0x0400ff00\n")

    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.tsv"
            path.write_text(text)
            return parse_trace(path)

    def test_coherence_is_observation_not_assumption(self):
        self.assertTrue(self.parse(self.trace())["data_aliases_coherent_in_probe"])
        self.assertFalse(self.parse(self.trace().replace("0x13579bdf", "0x00000000"))[
            "data_aliases_coherent_in_probe"])

    def test_rejects_incomplete_or_reordered_or_enabled(self):
        for text in (self.trace().replace("call\t0\t0\t-4\t14\n", ""),
                     self.trace().replace("call\t0\t0\t-4", "call\t0\t0\t-1"),
                     self.trace().replace("\t14\n", "\t0\n"),
                     self.trace().replace("0x0400ff00", "0x0400ff01"),
                     self.trace().replace("result\ttrue", "result\tfalse")):
            with self.assertRaises(ValueError): self.parse(text)

    def test_strict_same_case_comparison(self):
        native = "function\talignment\tlength\tinstructions\tcache_operations\n" + "".join(
            f"{f}\t{a}\t{n}\t4\t0\n" for f, a, n in CASES) + "passed\t193\n"
        oracle = self.parse(self.trace())
        self.assertEqual(compare_cases(native, oracle), [])
        self.assertEqual(len(compare_cases(native.replace("\t4\t0\n", "\t5\t0\n", 1), oracle)), 1)
        with self.assertRaises(ValueError): compare_cases(native.replace("0\t0\t-4", "0\t0\t-1"), oracle)
