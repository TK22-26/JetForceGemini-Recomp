"""Tests for the facts-only libultra identification tool (ROM-free).

Fixtures are built in a temp directory; nothing decomp-derived is tracked.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.identify_libultra import identify, _parse_decomp_symbols, \
    _parse_generated_symbols


class LibultraIdentification(unittest.TestCase):
    def test_maps_libultra_name_to_generated_function(self) -> None:
        decomp = {
            "entrypoint": 0x80000400,
            "osCreateThread": 0x800759D0,
            "osRecvMesg": 0x80096910,
            "amSetMuteMode": 0x80000450,  # a non-libultra (audio) function
            "osViSwapBuffer": 0x80099590,  # present but not in generated set
        }
        generated = {
            0x800759D0: "fn_000_1221",
            0x80096910: "fn_000_1510",
            0x80000450: "fn_000_0000",
        }
        result = identify(decomp, generated)
        detail = result["detail"]
        self.assertEqual(detail["entrypoint_vram"], "0x80000400")
        by_name = {e["libultra"]: e for e in detail["identified"]}
        # Boot-critical libultra present in the decomp are identified.
        self.assertIn("osCreateThread", by_name)
        self.assertEqual(by_name["osCreateThread"]["generated_function"],
                         "fn_000_1221")
        self.assertTrue(by_name["osCreateThread"]["in_generated_set"])
        # A libultra name present in decomp but absent from the generated set
        # is reported as identified-but-unmapped, not silently dropped.
        self.assertIn("osViSwapBuffer", by_name)
        self.assertFalse(by_name["osViSwapBuffer"]["in_generated_set"])
        # Non-libultra names are never identified as libultra.
        self.assertNotIn("amSetMuteMode", by_name)
        self.assertEqual(result["mapped_to_generated"], 2)
        self.assertEqual(result["present_in_decomp"], 3)

    def test_parsers_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="libultra-id-") as temp:
            root = Path(temp)
            decomp = root / "symbol_addrs.us.txt"
            decomp.write_text(
                "entrypoint = 0x80000400;\nosRecvMesg = 0x80096910;\n",
                encoding="utf-8",
            )
            gen = root / "symbols.toml"
            gen.write_text(
                '[[section]]\nfuncs = [\n'
                '    { name = "fn_000_1510", vram = 0x80096910, size = 0x10 },\n'
                "]\n",
                encoding="utf-8",
            )
            names = _parse_decomp_symbols(decomp)
            vram_to_fn = _parse_generated_symbols(gen)
        self.assertEqual(names["osRecvMesg"], 0x80096910)
        self.assertEqual(vram_to_fn[0x80096910], "fn_000_1510")


if __name__ == "__main__":
    unittest.main()
