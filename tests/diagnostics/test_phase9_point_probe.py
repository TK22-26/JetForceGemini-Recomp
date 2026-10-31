import tempfile
import unittest
from pathlib import Path

from scripts import phase9_point_probe as probe


class PointProbeTests(unittest.TestCase):
    def test_bounded_specification(self):
        pcs, words = probe.validate([0x80000000], [0x803ffffc], [1, 2], True)
        self.assertEqual(probe.specification(words), "0x803ffffc")
        self.assertEqual(pcs, (0x80000000,))
        for args in [([0x80000000] * 2, [], [1, 2], True),
                     ([0x80000000 + 4 * i for i in range(17)], [], [1, 2], True),
                     ([0x80000001], [], [1, 2], True),
                     ([0x80400000], [], [1, 2], True),
                     ([0x80000000], [0xa4000000], [1, 2], True),
                     ([0x80000000], [], None, True),
                     ([0x80000000], [], [1, 2], False),
                     ([], [0x80000000], [1, 2], True),
                     ([True], [], [1, 2], True)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                probe.validate(*args)

    def fixture(self, oracle=False):
        clock = ["frame", "completed_updates", "controller_polls", "consumed_vi"] if oracle else [
            "update_candidate", "vi_retraces", "controller_polls"]
        header = clock + ["pc", "opcode"] + [f"r{i}_{part}" for i in range(32) for part in ("lo", "hi")] + ["m800feb88"]
        row = (["20", "9", "19", "18"] if oracle else ["10", "18", "19"]) + ["0x80055034", "0x2411ffff"] + ["0x00000000"] * 64 + ["0x00000002"]
        return header, row

    def parse(self, header, rows, *, oracle=False, footer=None):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "point-probe.tsv"
            lines = ["\t".join(header), *("\t".join(row) for row in rows)]
            if footer is not None:
                lines.append(footer)
            path.write_text("\n".join(lines) + "\n")
            return probe.read(path, [0x80055034], [0x800feb88], [9, 12], oracle=oracle)

    def test_preserves_raw_clocks_register_halves_and_words(self):
        for oracle in (False, True):
            header, row = self.fixture(oracle)
            row[header.index("r2_lo")] = "0xffffffff"
            row[header.index("r2_hi")] = "0xffffffff"
            result = self.parse(header, [row], oracle=oracle, footer="result\ttrue\t1" if oracle else None)
            self.assertEqual(result[0]["r2_hi"], 0xffffffff)
            self.assertEqual(result[0]["m800feb88"], 2)
            self.assertEqual(result[0]["completed_updates" if oracle else "update_candidate"], 9 if oracle else 10)

    def test_rejects_truncated_unknown_and_out_of_window_rows(self):
        header, row = self.fixture()
        for key, value in [("pc", "0x80055038"), ("r0_lo", "0x00000001"),
                           ("r2_hi", "0x100000000"), ("update_candidate", "15"),
                           ("vi_retraces", "-1")]:
            altered = row.copy()
            altered[header.index(key)] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(header, [altered])
        for altered in (row[:-1], row + ["extra"]):
            with self.assertRaises(ValueError):
                self.parse(header, [altered])
        with self.assertRaises(ValueError):
            self.parse(header[::-1], [row])

    def test_rejects_clock_reversal_empty_and_overflow(self):
        header, row = self.fixture()
        older = row.copy()
        older[header.index("controller_polls")] = "18"
        for rows in ([], [row, older], [row] * 4097):
            with self.assertRaises(ValueError):
                self.parse(header, rows)

    def test_oracle_footer_is_required_and_counts_events(self):
        header, row = self.fixture(True)
        for footer in (None, "result\tfalse\t1", "result\ttrue\t2"):
            with self.subTest(footer=footer), self.assertRaises(ValueError):
                self.parse(header, [row], oracle=True, footer=footer)

    def test_summary_preserves_parse_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = probe.summary(Path(temporary) / "missing.tsv", [0x80055034], [], [9,12], oracle=False)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["events"])
        self.assertTrue(result["error"])


if __name__ == "__main__":
    unittest.main()
