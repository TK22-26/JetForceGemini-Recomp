"""Regional linker tables are untrusted input even after profile selection."""
from dataclasses import replace
import struct
import unittest
from scripts.regional_overlays import RegionalLayout, checked_headers, overlay_segments
from scripts.transform_private_n64recomp_inputs import HEADER

class RegionalOverlayTests(unittest.TestCase):
    def setUp(self):
        table = 0x100
        data = table + 157 * HEADER.size
        self.layout = RegionalLayout(0x20, 0x40, table, data, data + 155 * 32, data + 155 * 32 + 16)
        self.rom = bytearray(self.layout.names + 16)
        for index in range(157):
            row = (0, index*32, 8, 8, 16, 8, 8, 0, 4) if index < 155 else (0,0,0,0,0,0,0,-1,-1)
            HEADER.pack_into(self.rom, table + index * HEADER.size, *row)

    def change(self, slot, field, value):
        start = self.layout.headers + (slot-1)*HEADER.size
        row = list(HEADER.unpack_from(self.rom, start)); row[field] = value
        HEADER.pack_into(self.rom, start, *row)

    def test_all_overlays_and_relocation_byte_extents(self):
        headers = checked_headers(self.rom, self.layout)
        self.assertEqual(len(headers), 157)
        text = overlay_segments(self.rom, self.layout, "pal")
        self.assertEqual(text.count("    type: code"), 155)
        self.assertIn(f"[0x{self.layout.data+16:X}, bin, overlay_1_reloc]", text)
        self.assertIn(f"start: 0x{self.layout.data+32:X}", text)
        self.assertNotIn("name: overlay_156", text)

    def test_overlap_negative_extent_and_overrun_rejected(self):
        for slot, field, value in [(2,1,0),(1,1,-8),(1,2,-4),(1,3,-4),(1,4,-1),(155,1,155*32)]:
            with self.subTest(slot=slot, field=field, value=value):
                self.setUp(); self.change(slot,field,value)
                with self.assertRaises(ValueError): checked_headers(self.rom,self.layout)

    def test_relocations_must_contain_whole_records(self):
        for field in (5,6):
            self.setUp();self.change(1,field,4)
            with self.assertRaisesRegex(ValueError,"byte count"): checked_headers(self.rom,self.layout)

    def test_entries_must_be_aligned_within_text(self):
        for field in (7,8):
            for value in (-2,2,8):
                self.setUp();self.change(1,field,value)
                with self.assertRaisesRegex(ValueError,"outside executable"): checked_headers(self.rom,self.layout)

    def test_truncated_reordered_and_misaligned_tables_rejected(self):
        for layout in (replace(self.layout,data=self.layout.data-32),
                       replace(self.layout,headers=self.layout.data),
                       replace(self.layout,headers=self.layout.headers+1)):
            with self.assertRaises(ValueError): checked_headers(self.rom,layout)
        with self.assertRaises(ValueError): checked_headers(self.rom[:self.layout.names],self.layout)

    def test_population_and_empty_overlay_relocations_rejected(self):
        self.change(1,2,0); self.change(1,3,0)
        with self.assertRaisesRegex(ValueError,"population"): checked_headers(self.rom,self.layout)
        self.setUp();self.change(156,5,8)
        with self.assertRaisesRegex(ValueError,"Empty overlay"): checked_headers(self.rom,self.layout)
