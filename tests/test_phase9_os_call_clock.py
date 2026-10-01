import tempfile
import unittest
from pathlib import Path
from scripts.phase9_os_call_clock import HEADER, read, summarize


class OsClockTests(unittest.TestCase):
    def trace(self, rows, footer=None):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "trace.tsv"
        path.write_text("\t".join(HEADER) + "\n" + "\n".join(rows) + "\n" +
                        (footer or f"result\ttrue\t{len(rows)}\t0") + "\n")
        return path

    @staticmethod
    def row(id=1, valid=1, block=0, exceptions=0, switches=0, ticks=120):
        return (f"{id}\t1290\t0x80001000\trecv\t0x800feb80\t{block}\t{valid}"
                f"\t8\t0\t0x80055034\t{ticks}\t{exceptions}\t{switches}\t0x00000000")

    def test_cpu_samples_exclude_wait_and_other_execution(self):
        result = summarize(self.trace([self.row(), self.row(2, valid=0, block=1),
                                      self.row(3, exceptions=1), self.row(4, switches=1)]))
        self.assertEqual(result["uninterrupted_groups"][0]["distinct_ticks"], [120])
        self.assertEqual(result["uninterrupted_groups"][0]["samples"], 1)
        self.assertEqual(sum(result["excluded"].values()), 3)
        self.assertFalse(result["cost_model_qualified"])

    def test_incomplete_and_duplicate_calls_rejected(self):
        for rows, footer in (([self.row()], "result\ttrue\t2\t0"),
                             ([self.row(), self.row()], None),
                             ([self.row(valid=9)], None),
                             ([self.row(ticks=-1)], None)):
            with self.assertRaises(ValueError):
                read(self.trace(rows, footer))

    def test_unfinished_calls_are_explicit(self):
        result = summarize(self.trace([self.row()], "result\ttrue\t1\t2"))
        self.assertEqual(result["unfinished"], 2)
