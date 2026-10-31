import tempfile
import unittest
from pathlib import Path
from scripts.compare_phase9_execution_work import compare, native_pairs, oracle_pairs, graphics_to_pacing


class ExecutionWorkTests(unittest.TestCase):
    def parse(self, parser, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.tsv"
            path.write_text(text)
            return parser(path)

    def test_native_pairs_and_incomplete_rejection(self):
        entry = "execution-work\t8\t18\t30\tentry\t80001000\t40\n"
        finish = "execution-work\t8\t18\t30\tentry-return\t80001000\t45\n"
        self.assertEqual(self.parse(native_pairs, entry + finish)[0]["instructions"], 5)
        for text in (entry, finish, entry + finish.replace("45", "39")):
            with self.assertRaises(ValueError):
                self.parse(native_pairs, text)

    def test_interrupt_not_treated_as_instruction_cost(self):
        text = ("event\tframe\tupdate\tpoll\tvi\tcount\tepc\tcause\n"
                "entry\t1\t8\t18\t30\t0xfffffff8\t0x00000000\t0x00000000\n"
                "exception\t1\t8\t18\t30\t0xfffffffc\t0x00000000\t0x00000000\n"
                "entry-return\t1\t8\t18\t31\t0x00000008\t0x00000000\t0x00000000\n"
                "result\ttrue\t3\n")
        oracle = self.parse(oracle_pairs, text)
        result = compare([{"update": 8, "poll": 18, "instructions": 5, "vi_delta": 0}], oracle)
        self.assertEqual(result["pairs"][0]["two_tick_residual"], 6)
        self.assertFalse(result["pairs"][0]["uninterrupted_candidate"])
        with self.assertRaises(ValueError):
            self.parse(oracle_pairs, text.replace("result\ttrue\t3", "result\ttrue\t2"))

    def test_different_updates_not_realigned(self):
        with self.assertRaises(ValueError):
            compare([{"update": 8, "poll": 18}], [{"update": 9, "poll": 18}])

    def interval(self, events, update=8):
        with tempfile.TemporaryDirectory() as directory:
            native, oracle = Path(directory) / "native", Path(directory) / "oracle"
            native.write_text("execution-work\t8\t18\t30\trecv-return\t800fe8a8\t40\n"
                              "execution-work\t8\t18\t30\tentry\t80054fbc\t45\n")
            header = "event\tframe\tupdate\tpoll\tvi\tcount\tepc\tcause\n"
            rows = [("return-80332240", 0xfffffff0, 0), *events, ("entry", 8, 0)]
            oracle.write_text(header + "".join(
                f"{kind}\t1\t{update}\t18\t30\t0x{count:08x}\t0x{pc:08x}\t0\n"
                for kind, count, pc in rows) + f"result\ttrue\t{len(rows)}\n")
            return graphics_to_pacing(native, oracle)["pairs"][0]

    def test_interval_subtracts_measured_interrupts_across_wrap(self):
        row = self.interval([("exception", 0xfffffff4, 0x80001000),
                             ("exception-resume-80001000", 2, 0)])
        self.assertEqual(row["interrupted_wall_ticks"], 14)
        self.assertEqual(row["guest_two_tick_residual"], 0)

    def test_interval_rejects_incomplete_and_shifted_pairing(self):
        with self.assertRaises(ValueError):
            self.interval([("exception", 0xfffffff4, 0x80001000)])
        with self.assertRaises(ValueError):
            self.interval([], update=9)

    def test_interval_unions_overlapping_interrupts(self):
        row = self.interval([("exception", 0xfffffff4, 0x80001000),
                             ("exception", 0xfffffff6, 0x80002000),
                             ("exception-resume-80002000", 0xfffffffa, 0),
                             ("exception-resume-80001000", 2, 0)])
        self.assertEqual(row["interrupted_wall_ticks"], 14)
