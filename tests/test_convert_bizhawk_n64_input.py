from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "convert_bizhawk_n64_input",
    ROOT / "scripts" / "convert_bizhawk_n64_input.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ConvertBizHawkN64InputTests(unittest.TestCase):
    def test_parse_and_convert_with_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "Input Log.txt"
            log.write_text(
                "[Input]\n"
                "LogKey:test\n"
                "|..|    0,    0,..................|    0,    0,..................|\n"
                "|..|   12,  -34,...........A.....r|    0,    0,..................|\n"
                "|..|   12,  -34,...........A.....r|    0,    0,..................|\n"
                "|..|    0,    0,..................|    0,    0,..................|\n",
                encoding="ascii",
            )
            prefix = root / "prefix.input"
            prefix.write_text(
                "jfg-phase8-input-v1\n10,20,1000,0,0\n", encoding="ascii"
            )
            events = MODULE.convert(
                MODULE.parse_log(log), 0, 4, 100,
                MODULE.load_prefix(prefix),
            )
            self.assertEqual(len(events), 2)
            self.assertEqual((events[1].first, events[1].end), (101, 103))
            self.assertEqual(events[1].sample.buttons, 0x8010)
            self.assertEqual((events[1].sample.stick_x, events[1].sample.stick_y), (12, -34))

    def test_rejects_overlap_and_invalid_axis(self) -> None:
        sample = MODULE.Sample(0x8000, 0, 0)
        with self.assertRaises(MODULE.ConversionError):
            MODULE.convert([sample], 0, 1, 5, [MODULE.Event(0, 6, sample)])
        with self.assertRaises(MODULE.ConversionError):
            MODULE.parse_player_column("128,0,..................")


if __name__ == "__main__":
    unittest.main()
