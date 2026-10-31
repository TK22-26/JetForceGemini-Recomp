"""Bounded raw-SI transaction validation."""

import tempfile
import unittest
from pathlib import Path

from scripts.phase9_si_trace import HEADER, analyze, read


class SiTraceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "si-transactions.tsv"

    def write(self, *rows):
        self.path.write_text("\t".join(HEADER) + "\n" +
                             "".join("\t".join(row) + "\n" for row in rows),
                             encoding="utf-8")

    def row(self, direction="1", after=None, caller="0x80093254"):
        before = "00" * 64
        return ("1", "1332", "567", "574", "1303", "1332", "567",
                "574", "1303", direction, "0x80105030", caller,
                before, after or before)

    def test_bounded_transaction_report(self):
        self.write(self.row(after="01" + "00" * 63))
        report = analyze(self.path, (566, 569))
        self.assertEqual(report["rows"], 1)
        self.assertEqual(report["write_calls"], 1)
        self.assertEqual(report["changed_buffers"], 1)
        self.assertEqual(report["callers"], ["0x80093254"])

    def test_rejects_outside_focus_or_bad_payload(self):
        self.write(("1", "1332", "563", "574", "1303", "1332", "563",
                    "574", "1303", "0", "0x80105030", "0x80093270",
                    "00" * 64, "00" * 64))
        with self.assertRaises(ValueError):
            read(self.path, (566, 569))
        self.write(self.row(after="00" * 63))
        with self.assertRaises(ValueError):
            read(self.path, (566, 569))


if __name__ == "__main__":
    unittest.main()
