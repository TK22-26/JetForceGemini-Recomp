"""Program identity must remain correct when sections overlap or layouts differ."""
from dataclasses import replace
import unittest
from scripts.regional.program_model import (AddressDomain, CodeRef, FunctionAlias,
    FunctionBody, ProgramModel, Section, SectionKind)

def fixture(separate_entry=True):
    entry = Section("entry", SectionKind.ENTRY, 0, 64, 0x80000400, 16, 0, 0)
    main = Section("main", SectionKind.MAIN, 1, 80, 0x80000410, 32, 16, 16)
    overlays = (Section("overlay:1", SectionKind.OVERLAY, 2, 128, 0x100000, 32, 16, 16, 1, 8),
                Section("overlay:2", SectionKind.OVERLAY, 3, 176, 0x100000, 32, 0, 0, 2))
    sections = (entry, main, *overlays) if separate_entry else (replace(main, rom_start=64, linked_vram=0x80000400, text_size=48), *overlays)
    bodies = tuple(FunctionBody(s.id, 0, 16, ("start",)) for s in sections)
    return ProgramModel("synthetic-r0", "a" * 40, 256, "b" * 64, sections, bodies)

class ProgramModelTests(unittest.TestCase):
    def test_both_entry_layouts_and_overlay_address_overlap_are_valid(self):
        for split in (True, False):
            model = fixture(split)
            model.validate()
            a = model.resolve(CodeRef(model.revision_id, "overlay:1", 0))
            b = model.resolve(CodeRef(model.revision_id, "overlay:2", 0))
            self.assertNotEqual(a.identity, b.identity)

    def test_revision_is_part_of_every_code_reference(self):
        with self.assertRaisesRegex(ValueError, "another revision"):
            fixture().resolve(CodeRef("different-r0", "main", 0))

    def test_offset_inside_body_is_not_automatically_a_callable_entry(self):
        model = fixture()
        with self.assertRaisesRegex(ValueError, "not a declared"):
            model.resolve(CodeRef(model.revision_id, "main", 4))
        model = replace(model, aliases=(FunctionAlias("alternate", "main", 4, 0),))
        model.validate()
        self.assertEqual(model.resolve(CodeRef(model.revision_id, "main", 4)).offset, 0)

    def test_data_patch_offset_zero_is_normalized_after_text(self):
        section = fixture().sections[2]
        self.assertEqual(section.checked_offset(AddressDomain.DATA, 0, 4, patch=True), 32)
        self.assertEqual(section.checked_offset(AddressDomain.TEXT, 0, 4, patch=True), 0)
        for domain in (AddressDomain.BSS, AddressDomain.RETAINED_RELOCATIONS):
            with self.assertRaisesRegex(ValueError, "cannot write"):
                section.checked_offset(domain, 0, 4, patch=True)

    def test_access_cannot_cross_domain_boundary(self):
        section = fixture().sections[2]
        with self.assertRaisesRegex(ValueError, "leaves"):
            section.checked_offset(AddressDomain.DATA, 12, 8)
        with self.assertRaises(ValueError): section.checked_offset(AddressDomain.TEXT, True, 4)

    def test_static_overlap_and_reused_overlay_slot_rejected(self):
        model = fixture()
        for bad in (replace(model.sections[1], linked_vram=model.sections[0].linked_vram),
                    replace(model.sections[3], overlay_slot=1)):
            sections = tuple(bad if s.id == bad.id else s for s in model.sections)
            with self.assertRaises(ValueError): replace(model, sections=sections).validate()

    def test_functions_cannot_extend_into_data_or_overlap_unclassified(self):
        model = fixture()
        for bad in (FunctionBody("main", 16, 20, ("bad",)), FunctionBody("main", 4, 16, ("bad",))):
            with self.assertRaises(ValueError): replace(model, bodies=(*model.bodies, bad)).validate()

    def test_fingerprint_ignores_container_order_but_binds_revision(self):
        model = fixture()
        reordered = replace(model, sections=tuple(reversed(model.sections)), bodies=tuple(reversed(model.bodies)))
        self.assertEqual(model.fingerprint(), reordered.fingerprint())
        self.assertNotEqual(model.fingerprint(), replace(model, revision_id="other-r0").fingerprint())

if __name__ == "__main__": unittest.main()
