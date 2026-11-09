"""Alias qualification uses ELF section identity, never a bare overlapping address."""
from dataclasses import replace
from types import SimpleNamespace as Item
import unittest
from scripts.regional.symbol_inventory import reconcile
from tests.build.test_regional_program_model import fixture

def inputs(model):
    sections = [Item(index=i+1, name=".overlay_"+str(s.overlay_slot) if s.overlay_slot else "."+s.id,
                     flags="AX", address=s.linked_vram) for i,s in enumerate(model.sections)]
    symbols = [Item(symbol_type="FUNC", defined=True, section=str(i+1), value=s.linked_vram,
                    size=16, name="start") for i,s in enumerate(model.sections)]
    return sections,symbols

class SymbolInventoryTests(unittest.TestCase):
    def test_overlapping_overlay_addresses_keep_aliases_in_their_own_sections(self):
        model = fixture()
        sections,symbols = inputs(model)
        symbols.append(Item(symbol_type="FUNC", defined=True, section="3", value=0x100004, size=0, name="alternate"))
        bound, counts = reconcile(model, sections, symbols)
        self.assertEqual(bound.aliases[0].section, "overlay:1")
        self.assertEqual(bound.aliases[0].offset, 4)
        self.assertEqual(counts["interior_aliases"], 1)
        self.assertFalse(model.aliases)

    def test_compiler_label_rename_preserves_original_symbol_as_explicit_alias(self):
        model = fixture(); sections,symbols = inputs(model)
        renamed = replace(model.bodies[0], names=("start_disambiguated",))
        model = replace(model, bodies=(renamed, *model.bodies[1:]))
        bound, counts = reconcile(model, sections, symbols)
        self.assertEqual(counts["context_only_labels"], 1)
        self.assertEqual([(a.name, a.section, a.offset) for a in bound.aliases], [("start", "entry", 0)])

    def test_sized_symbol_must_match_declared_body_extent(self):
        model = fixture(); sections,symbols = inputs(model)
        symbols[0].size = 12
        with self.assertRaisesRegex(ValueError, "differs"):
            reconcile(model, sections, symbols)

    def test_missing_body_name_and_unowned_alias_are_rejected(self):
        model = fixture(); sections,symbols = inputs(model)
        with self.assertRaisesRegex(ValueError, "absent"):
            reconcile(model, sections, symbols[1:])
        symbols.append(Item(symbol_type="FUNC", defined=True, section="2", value=0x80000428, size=0, name="gap"))
        with self.assertRaisesRegex(ValueError, "unique body"):
            reconcile(model, sections, symbols)

if __name__ == "__main__": unittest.main()
