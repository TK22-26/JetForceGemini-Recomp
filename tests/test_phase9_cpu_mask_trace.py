import tempfile
import unittest
from pathlib import Path
from scripts.phase9_cpu_mask_trace import parse_trace


class MaskProbeTests(unittest.TestCase):
    def trace(self):
        return ("old_mask\trequested_mask\tticks\tresult\tstatus\tmi_mask\n" + "".join(
            f"{old}\t{requested}\t{78 if old == 0 else 86}\t0x{old << 16 | 0xff00:08x}\t"
            f"0x0400ff00\t0x{requested:08x}\n" for old in (0, 63) for requested in range(64)) +
            "result\ttrue\t0x00000000\n")

    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.tsv"
            path.write_text(text)
            return parse_trace(path)

    def test_complete_independent_matrix(self):
        observed = self.parse(self.trace())
        self.assertEqual(len(observed["calls"]), 128)
        self.assertTrue(observed["mask_semantics_pass"])
        self.assertFalse(observed["interrupt_delivery_qualified"])

    def test_boot_mask_observed_not_assumed(self):
        self.assertEqual(self.parse(self.trace().replace("result\ttrue\t0x00000000",
            "result\ttrue\t0x0000003f"))["boot_mi_mask_observed"], 63)

    def test_reject_incomplete_and_bad_semantics(self):
        for text in (self.trace() + "extra\n", self.trace().replace("\t78\t", "\t0\t"),
                     self.trace().replace("0x0400ff00", "0x0400ff01"),
                     self.trace().replace("0x003fff00", "0x0000ff00"),
                     self.trace().replace("result\ttrue", "result\tfalse")):
            with self.assertRaises(ValueError): self.parse(text)
