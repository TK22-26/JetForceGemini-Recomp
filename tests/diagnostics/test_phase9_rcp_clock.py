import tempfile
import unittest
from pathlib import Path
from scripts.phase9_rcp_clock import HEADER, summarize


class RcpClockTests(unittest.TestCase):
    def parse(self, row, cpu=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "rcp").write_text("\t".join(HEADER) + "\n" + row + "\nresult\ttrue\t1\n")
            (root / "cpu").write_text("event\tframe\tupdate\tpoll\tvi\tcount\tepc\tcause\n" +
                (cpu or "exception\t1\t3\t4\t5\t0x00000008\t0x80000000\t0x00000400") +
                "\nresult\ttrue\t1\n")
            return summarize(root / "rcp", root / "cpu")

    row = "exception\t3\t0x00000008\t0x0400ff03\t0x00000008\t0x0000003f\t0x00000243\t0x00000081\t0x00000000"

    def test_observations_are_not_latency_qualification(self):
        result = self.parse(self.row)
        self.assertEqual(result["exception_pending_masks"], {"0x08": 1})
        self.assertFalse(result["latency_model_qualified"])

    def test_reject_bad_register_exl_and_pairing(self):
        for row in (self.row.replace("0x0000003f", "0x00000040"),
                    self.row.replace("0x0400ff03", "0x0400ff01"),
                    self.row.replace("\t3\t", "\t4\t"), self.row + "\textra"):
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.parse(row)


if __name__ == "__main__":
    unittest.main()
