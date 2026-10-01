import tempfile
import unittest
from pathlib import Path
from scripts.phase9_cpu_clock_trace import parse_trace
from scripts.phase9_cpu_rounding_run import run


class ClockTraceTests(unittest.TestCase):
    def parse(self, text):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "clock.tsv"
            path.write_text(text)
            return parse_trace(path)

    @staticmethod
    def valid():
        return ("case\tticks\nalu100\t802\nalu1000\t8002\n"
                "cached100\t802\ncached1000\t8002\n"
                "uncached100\t802\nuncached1000\t8002\nresult\ttrue\n")

    def test_aggregate_slope_is_not_hardware_qualification(self):
        result = self.parse(self.valid())
        self.assertEqual(result["delta_ticks_per_3600_instructions"],
                         {"alu": 7200, "cached": 7200, "uncached": 7200})
        self.assertFalse(result["hardware_qualified"])

    def test_invalid_capture_rejected(self):
        for text in ("", self.valid().replace("result\ttrue", "result\tfalse"),
                     self.valid().replace("8002", "1"),
                     self.valid().replace("802", "-1"),
                     self.valid().replace("802", "4294967296"),
                     self.valid().replace("alu100\t", "unknown\t"),
                     self.valid() + "extra\n"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.parse(text)

    def test_unknown_probe_rejected_before_filesystem_access(self):
        with self.assertRaisesRegex(ValueError, "unsupported CPU probe"):
            run(None, None, None, None, None, probe="unknown")
