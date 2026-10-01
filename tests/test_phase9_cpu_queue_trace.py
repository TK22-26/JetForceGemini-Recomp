import tempfile
import unittest
from pathlib import Path
from scripts.phase9_cpu_queue_trace import parse_trace


class QueueMicroTests(unittest.TestCase):
    TEXT = ("case\tticks\tresult\tvalid\nleaf\t12\t0x00000000\t0\n"
            "empty_recv\t86\t0xffffffff\t0\nsend\t138\t0x00000000\t1\n"
            "recv_output\t140\t0x00000000\t0\nrefill\t138\t0x00000000\t1\n"
            "full_send\t96\t0xffffffff\t1\nrecv_discard\t126\t0x00000000\t0\n"
            "result\ttrue\t1234\n")

    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.tsv"
            path.write_text(text)
            return parse_trace(path)

    def test_semantics_verified_separately_from_cost(self):
        result = self.parse(self.TEXT)
        self.assertTrue(result["queue_semantics_pass"])
        self.assertFalse(result["hardware_qualified"])
        self.assertFalse(result["covers_blocking_or_wakeup"])

    def test_missing_or_incorrect_results_rejected(self):
        for text in ("", self.TEXT.replace("1234", "5678"),
                     self.TEXT.replace("0xffffffff", "0x00000000"),
                     self.TEXT.replace("138", "0"), self.TEXT + "extra\n"):
            with self.assertRaises(ValueError):
                self.parse(text)
