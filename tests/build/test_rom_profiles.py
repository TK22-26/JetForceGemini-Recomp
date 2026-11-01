"""ROM-free byte-order and regional metadata safety checks."""
import unittest
from unittest.mock import patch
from scripts.rom_profiles import (normalize_byte_order, identify_rom, require_native_rom,
                                  ROM_PROFILES, PAL_ROM, JAPAN_ROM, US_ROM)
from scripts.prepare_regional_metadata import regional_splat, pal_linker_symbols

class RegionalRomTests(unittest.TestCase):
    def test_all_storage_orders_normalize_without_mutating_input(self):
        big = bytes.fromhex("80371240 01020304 fffefd00")
        little = b"".join(big[i:i+4][::-1] for i in range(0, len(big), 4))
        swapped = b"".join(big[i:i+2][::-1] for i in range(0, len(big), 2))
        for data, order in ((big, "big-endian"), (little, "little-endian"), (swapped, "byte-swapped")):
            with self.subTest(order=order):
                before = bytes(data)
                self.assertEqual(normalize_byte_order(data), (big, order))
                self.assertEqual(data, before)

    def test_truncated_and_unknown_storage_orders_rejected(self):
        for data in (b"", b"\x80\x37\x12", bytes.fromhex("80371240ff"), b"abcd"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                normalize_byte_order(data)

    def test_header_alone_does_not_identify_a_game(self):
        with self.assertRaises(ValueError):
            identify_rom(bytes.fromhex("80371240"))
        with self.assertRaisesRegex(ValueError, "checksum"):
            identify_rom(bytes.fromhex("80371240") + bytes(32*1024*1024-4))

    def test_recognized_regional_roms_cannot_enter_us_native_runtime(self):
        for profile in (PAL_ROM, JAPAN_ROM):
            with self.subTest(region=profile.code), patch("scripts.rom_profiles.identify_rom",
                    return_value=(profile, b"", "big-endian")):
                with self.assertRaisesRegex(ValueError, "native runtime is not supported"):
                    require_native_rom(b"")
        self.assertEqual([p.code for p in ROM_PROFILES if p.native_supported], [US_ROM.code])

    def test_japanese_opaque_executable_prefix_keeps_text_order(self):
        source = "sha1: " + JAPAN_ROM.sha1 + "\n  - [0x1000, c, first]\n  - [0x9E4D0, bin]\n  - [0x9E620, textbin]\n  - [0xA1120, data]\n"
        result = regional_splat(source, "jpn")
        self.assertIn("[0x1000, asm, first]", result)
        self.assertIn("[0x9E4D0, textbin]", result)
        self.assertIn("[0xA1120, data]", result)
        with self.assertRaises(ValueError):
            regional_splat(result, "jpn")
        with self.assertRaises(ValueError):
            regional_splat(source.replace(JAPAN_ROM.sha1, US_ROM.sha1), "jpn")

    def test_pal_linker_cleanup_does_not_invent_missing_boundaries(self):
        names = ("overlay_1_ROM_START", "assets_lut_ROM_START", "assets_lut_ROM_END",
                 "symbolsTable_offsets_ROM_START", "symbolsTable_symbol_names_ROM_START")
        source = "preserved = 0x80000400;\n" + "".join("alias%d = %s;\n" % (i, n) for i, n in enumerate(names))
        self.assertEqual(pal_linker_symbols(source), "preserved = 0x80000400;\n")
        with self.assertRaises(ValueError):
            pal_linker_symbols(source.replace(names[0], "unexpected_boundary"))

if __name__ == "__main__":
    unittest.main()
