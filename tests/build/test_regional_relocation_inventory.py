import unittest
from scripts.regional.program_model import Section,SectionKind
from scripts.regional.relocation_inventory import ImageLayout,source_offset

class RegionalRelocationSourceTests(unittest.TestCase):
    def setUp(self):
        self.layout=ImageLayout(0x200,0x300,0x400,0x500,0x100,0x20)
        self.overlay=Section('overlay:1',SectionKind.OVERLAY,2,0x1000,0x80400000,0x100,0x20,0x40,1,0x10)
    def test_overlay_data_zero_is_after_text(self):
        self.assertEqual(source_offset(self.overlay,self.layout,3,0,2),0x100)
        self.assertEqual(source_offset(self.overlay,self.layout,3,0x1c,2),0x11c)
    def test_combined_entry_main_adds_entry_for_code_only(self):
        section=Section('main',SectionKind.MAIN,0,0x1000,0x80000400,0x150,0x20,0x40)
        self.assertEqual(source_offset(section,self.layout,0,0,4),0x50)
        self.assertEqual(source_offset(section,self.layout,3,0,2),0x150)
    def test_separate_main_does_not_add_entry(self):
        section=Section('main',SectionKind.MAIN,1,0x1050,0x80000450,0x100,0x20,0x40)
        self.assertEqual(source_offset(section,self.layout,0,0,4),0)
    def test_patch_cannot_write_bss_or_retained_metadata(self):
        for source,offset in ((3,0x20),(0,0x120),(1,0x160)):
            with self.subTest(source=source,offset=offset),self.assertRaises(ValueError):
                source_offset(self.overlay,self.layout,source,offset,2)
    def test_instruction_patch_cannot_write_data(self):
        with self.assertRaises(ValueError): source_offset(self.overlay,self.layout,3,0,5)
        with self.assertRaises(ValueError): source_offset(self.overlay,self.layout,0,0x100,4)
    def test_reject_unknown_encoding_or_unaligned_site(self):
        for source,offset,patch in ((4,0,2),(0,0,7),(0,1,2)):
            with self.subTest(source=source,offset=offset,patch=patch),self.assertRaises(ValueError):
                source_offset(self.overlay,self.layout,source,offset,patch)

if __name__=='__main__':unittest.main()
