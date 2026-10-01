"""Bounded controller caller trace validation."""

import tempfile
import unittest
from pathlib import Path

from scripts.phase9_controller_callers import HEADER, analyze, read


class ControllerCallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "controller-callers.tsv"

    def write(self, *rows):
        self.path.write_text("\t".join(HEADER) + "\n" +
                             "".join("\t".join(row) + "\n" for row in rows),
                             encoding="utf-8")

    def test_unique_caller_per_window(self):
        self.write(("1", "13", "4", "20", "22", "0x800431bc",
                    "0x800fb0c0"),
                   ("2", "552", "390", "560", "561", "0x800431bc",
                    "0x800fb0c0"))
        report = analyze(self.path, ((13, 21), (552, 576)))
        self.assertEqual(report["rows"], 2)
        self.assertEqual([item["unique_caller"] for item in
                          report["windows"]], ["0x800431bc"] * 2)

    def test_rejects_outside_window_or_unaligned_pc(self):
        self.write(("1", "22", "4", "20", "22", "0x800431bc",
                    "0x800fb0c0"))
        with self.assertRaises(ValueError):
            read(self.path, ((13, 21),))
        self.write(("1", "13", "4", "20", "22", "0x800431bd",
                    "0x800fb0c0"))
        with self.assertRaises(ValueError):
            read(self.path, ((13, 21),))

    def test_empty_trace_is_valid_but_not_selectable(self):
        self.write()
        report = analyze(self.path, ((13, 21),))
        self.assertEqual(report["windows"][0]["unique_caller"], None)


if __name__ == "__main__":
    unittest.main()
