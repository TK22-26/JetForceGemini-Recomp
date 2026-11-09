"""Synthetic bounds/identity regressions for shared program extraction."""
from pathlib import Path
from types import SimpleNamespace
import hashlib,tempfile,unittest
from scripts.regional.audio_payloads import locate_payload
from scripts.regional.pipeline import prove_original_sections
from scripts.regional.program_model import SectionKind

class PayloadTests(unittest.TestCase):
    def model(self,sections):return SimpleNamespace(revision_id='synthetic-r0',sections=sections,fingerprint=lambda:'a'*64)
    def section(self,**changes):
        row=dict(id='main',kind=SectionKind.MAIN,rom_start=0,linked_vram=0x80001000,initialized_size=64)
        row.update(changes);return SimpleNamespace(**row)
    def recipe(self,raw):return {'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'prefix_size':4,'prefix_sha256':hashlib.sha256(raw[:4]).hexdigest(),'alignment':8}
    def test_unique_original_payload_uses_section_coordinates(self):
        payload=b'abcdefgh';rom=b'\0'*8+payload+b'\0'*48;ref,data=locate_payload(rom,self.model([self.section()]),self.recipe(payload))
        self.assertEqual((ref.section,ref.offset,ref.size,data),('main',8,8,payload))
    def test_duplicate_resident_payload_is_ambiguous(self):
        payload=b'abcdefgh';rom=payload*2+b'\0'*48
        with self.assertRaisesRegex(ValueError,'ambiguous'):locate_payload(rom,self.model([self.section()]),self.recipe(payload))
    def test_overlay_and_uninitialized_bytes_do_not_supply_resident_payloads(self):
        payload=b'abcdefgh';rom=b'\0'*64+payload
        for sections in ([self.section(initialized_size=64)],[self.section(rom_start=64,initialized_size=8,kind=SectionKind.OVERLAY)]):
            with self.subTest(),self.assertRaises(ValueError):locate_payload(rom,self.model(sections),self.recipe(payload))
    def test_prefix_match_does_not_override_full_hash(self):
        payload=b'abcdefgh';rom=b'abcdxxxx'+b'\0'*56
        with self.assertRaises(ValueError):locate_payload(rom,self.model([self.section()]),self.recipe(payload))
    def test_alignment_applies_to_rom_and_linked_memory(self):
        payload=b'abcdefgh'
        for rom,section in ((b'\0'*4+payload+b'\0'*52,self.section()),(payload+b'\0'*56,self.section(linked_vram=0x80001004))):
            with self.subTest(),self.assertRaises(ValueError):locate_payload(rom,self.model([section]),self.recipe(payload))
    def test_bad_recipe_sizes_and_alignment_are_rejected(self):
        for change in ({'size':0},{'size':True},{'prefix_size':9},{'alignment':3}):
            recipe=self.recipe(b'abcdefgh');recipe.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):locate_payload(bytes(64),self.model([self.section()]),recipe)

class OriginalSectionTests(unittest.TestCase):
    def test_every_original_initialized_section_must_agree(self):
        model=SimpleNamespace(sections=[SimpleNamespace(id='main',overlay_slot=None,linked_vram=0x80001000,rom_start=8,initialized_size=4),SimpleNamespace(id='overlay:7',overlay_slot=7,linked_vram=0x700000,rom_start=16,initialized_size=4)])
        sections=[SimpleNamespace(name='.main',allocated=True,section_type='PROGBITS',address=0x80001000,size=4,offset=0),SimpleNamespace(name='.overlay_7',allocated=True,section_type='PROGBITS',address=0x700000,size=4,offset=4)]
        rom=b'\0'*8+b'abcd'+b'\0'*4+b'efgh'
        with tempfile.TemporaryDirectory() as d:
            elf=Path(d)/'fixture.elf';elf.write_bytes(b'abcdefgh');prove_original_sections(rom,model,elf,sections)
            elf.write_bytes(b'abcdEFGH')
            with self.assertRaisesRegex(ValueError,'bytes differ'):prove_original_sections(rom,model,elf,sections)
            elf.write_bytes(b'abcdefgh')
            with self.assertRaisesRegex(ValueError,'ownership'):prove_original_sections(rom,model,elf,sections[:1])

if __name__=='__main__':unittest.main()
