import struct,unittest
from scripts.regional.code_inventory import find_direct_call_candidates,find_indirect_transfer_sites,find_cross_body_branch_entries,split_functions

class RegionalCodeInventoryTests(unittest.TestCase):
    def test_overlapping_addresses_use_explicit_relocation_identity(self):
        rom=struct.pack('>IIII',0x0c000400,0,0x03e00008,0)
        sections=[{'rom':0,'vram':0x1000,'size':8,'functions':[{'vram':0x1000,'size':8}]},
                  {'rom':8,'vram':0x1000,'size':8,'functions':[{'vram':0x1000,'size':8}]}]
        functions,_,_=split_functions(sections,{})
        rows=find_direct_call_candidates(rom,sections,functions,set(),{(0,0):(1,0)})
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['target_section'],1)
        with self.assertRaisesRegex(ValueError,'explicit section-qualified'):
            find_direct_call_candidates(rom,sections,functions,set(),{})
    def test_conditional_tail_includes_likely_regimm_and_fpu_branches(self):
        sections=[{'rom':0,'vram':0x1000,'size':16,'functions':[{'vram':0x1000,'size':8},{'vram':0x1008,'size':8}]}]
        functions,_,_=split_functions(sections,{})
        for word in (0x15000001,0x55000001,0x05000001,0x05020001,0x45010001):
            with self.subTest(word=hex(word)):
                rows=find_direct_call_candidates(struct.pack('>IIII',word,0,0x03e00008,0),sections,functions,set(),{})
                self.assertEqual(len(rows),1)
                self.assertEqual((rows[0]['instruction_class'],rows[0]['target_offset']),('conditional-branch',8))

    def test_missing_original_call_site_is_rejected(self):
        sections=[{'rom':0,'vram':0x1000,'size':8,'functions':[{'vram':0x1000,'size':8}]}]
        functions,_,_=split_functions(sections,{})
        with self.assertRaisesRegex(ValueError,'absent'):
            find_direct_call_candidates(bytes(8),sections,functions,set(),{(0,0):(0,0)})
    def test_indirect_inventory_keeps_section_coordinates(self):
        sections=[{'rom':0,'vram':0x1000,'functions':[{'vram':0x1000,'size':8}]},
                  {'rom':8,'vram':0x1000,'functions':[{'vram':0x1000,'size':8}]}]
        rows=find_indirect_transfer_sites(struct.pack('>IIII',0x03e00008,0,0x0320f809,0),sections)
        self.assertEqual([(r['section'],r['offset'],r['source_register']) for r in rows],[(0,0,31),(1,0,25)])
    def test_alternate_entry_preserves_authoritative_body(self):
        sections=[{'rom':0,'vram':0x1000,'functions':[{'vram':0x1000,'size':16}]}]
        functions,count,gaps=split_functions(sections,{0:{8}})
        self.assertEqual((count,gaps),(1,0));self.assertEqual([(r['vram'],r['size']) for r in functions[0]],[(0x1000,16),(0x1008,8)])

if __name__=='__main__':unittest.main()


class DirectInteriorEntryTests(unittest.TestCase):
    def test_jal_into_a_merged_original_body_gets_a_thunk_without_splitting(self):
        from scripts.regional.code_inventory import find_direct_interior_entries
        import struct
        section={'vram':0x80000400,'rom':0,'functions':[{'vram':0x80000400,'size':16},{'vram':0x80000410,'size':32}]}
        rom=bytearray(48);struct.pack_into('>I',rom,0,0x0c000000|((0x80000420>>2)&0x3ffffff))
        self.assertEqual(dict(find_direct_interior_entries(rom,[section],{})),{0:{32}})
        self.assertEqual(section['functions'][1]['size'],32)
    def test_overlapping_target_coordinates_need_original_relocation_identity(self):
        from scripts.regional.code_inventory import find_direct_interior_entries
        import struct
        sections=[{'vram':0x80000400,'rom':0,'functions':[{'vram':0x80000400,'size':16}]},
                  {'vram':0x100000,'rom':16,'functions':[{'vram':0x100000,'size':16}]},
                  {'vram':0x100000,'rom':32,'functions':[{'vram':0x100000,'size':16}]}]
        rom=bytearray(48);struct.pack_into('>I',rom,16,0x0c000000|((0x100008>>2)&0x3ffffff))
        with self.assertRaisesRegex(ValueError,'ambiguous'):find_direct_interior_entries(rom,sections,{})
        self.assertEqual(dict(find_direct_interior_entries(rom,sections,{(1,0):(2,8)})),{2:{8}})


class ConstantIndirectEntryTests(unittest.TestCase):
    def test_addiu_signed_low_and_ori_preserve_body(self):
        from scripts.regional.code_inventory import find_constant_indirect_entries
        for base, upper, lower in ((0x80075250,0x3c1a8007,0x275a5260),(0x8007fff0,0x3c1a8008,0x275afffc),(0x8007fff0,0x3c1a8007,0x375afffc)):
            with self.subTest(base=hex(base),lower=hex(lower)):
                section={'vram':base,'rom':0,'functions':[{'vram':base,'size':32}]}
                rom=struct.pack('>IIIIIIII',upper,lower,0x03400008,0,0,0,0,0)
                result=find_constant_indirect_entries(rom,[section]);expected=16 if base==0x80075250 else 12
                self.assertEqual(dict(result),{0:{expected}})
                functions,count,gaps=split_functions([section],result)
                self.assertEqual((functions[0][0]['size'],count,gaps),(32,1,0))
    def test_different_register_and_existing_entry_do_not_invent_entry(self):
        from scripts.regional.code_inventory import find_constant_indirect_entries
        section={'vram':0x80075250,'rom':0,'functions':[{'vram':0x80075250,'size':32}]}
        for lower,jump in ((0x275b5260,0x03400008),(0x275a5260,0x03600008),(0x275a5250,0x03400008)):
            self.assertEqual(dict(find_constant_indirect_entries(struct.pack('>IIIIIIII',0x3c1a8007,lower,jump,0,0,0,0,0),[section])),{})
    def test_ambiguous_overlay_owner_rejected(self):
        from scripts.regional.code_inventory import find_constant_indirect_entries
        sections=[{'vram':0x80075250,'rom':n,'functions':[{'vram':0x80075250,'size':32}]} for n in (0,32)]
        rom=struct.pack('>IIIIIIII',0x3c1a8007,0x275a5260,0x03400008,0,0,0,0,0)+bytes(32)
        with self.assertRaisesRegex(ValueError,'ambiguous'):find_constant_indirect_entries(rom,sections)


class AlternateBranchClosureTests(unittest.TestCase):
    def test_suffix_entry_backward_branch_gets_callable_without_cutting_owner(self):
        from scripts.regional.code_inventory import close_alternate_branch_entries
        section={'vram':0x80001000,'rom':0,'functions':[{'vram':0x80001000,'size':32}]}
        # A suffix starts at +16 and branches back to +4 in its full owner.
        rom=struct.pack('>IIIIIIII',0,0,0,0,0x5500fffc,0,0x03e00008,0)
        self.assertEqual(dict(find_cross_body_branch_entries(rom,[section])),{})
        additions=close_alternate_branch_entries(rom,[section],{0:{16}})
        self.assertEqual(additions,{0:{4}})
        functions,_,_=split_functions([section],{0:{4,16}})
        rows=find_direct_call_candidates(rom,[section],functions,set(),{})
        self.assertEqual([(row['target_offset'],row['target_class']) for row in rows],[(4,'alternate-entry')])
        self.assertEqual(functions[0][0]['size'],32)
        self.assertEqual(close_alternate_branch_entries(rom,[section],{0:{4,16}}),{})

    def test_suffix_entries_close_more_than_one_backward_branch_layer(self):
        from scripts.regional.code_inventory import close_alternate_branch_entries
        section={'vram':0x80001000,'rom':0,'functions':[{'vram':0x80001000,'size':48}]}
        words=[0]*12;words[5]=0x1500fffb;words[8]=0x1500fffb;words[10]=0x03e00008
        rom=struct.pack('>12I',*words)
        self.assertEqual(close_alternate_branch_entries(rom,[section],{0:{32}}),{0:{4,16}})
