import unittest

from scripts.phase9_instruction_effect_witnesses import bind


class EffectWitnessTests(unittest.TestCase):
    def setUp(self):
        self.entry = dict(invocation=7, phase=0, pc=0x80001000, opcode=0x24020001, device_sequence=12,
            thread_word=0x80002000, owner=0x80002000, gpr=tuple([0] * 31 + [0xffffffff80003000]),
            count=102, status=0x20000001, cause=0)
        self.device = dict(invocation=7, phase='instruction', sequence=12, pc=0x80001000,
            opcode=0x24020001, thread=0x80002000, clock_raw=100, status=0x20000001, cause=0,
            **{f'r{i}_{part}': (value >> shift) & 0xffffffff for i,value in enumerate(self.entry['gpr'])
               for part,shift in (('lo',0),('hi',32))})
        self.eret = {**self.entry, 'phase':2, 'opcode':0x42000018, 'pc':0x80001100,
                     'selected_owner':0x80002100, 'target':0x80003100}
        self.transfer = dict(invocation=7, pc=self.eret['pc'], opcode=self.eret['opcode'],
            from_thread=self.eret['owner'], to_thread=self.eret['selected_owner'], target_pc=self.eret['target'],
            status=self.eret['status'], count=self.eret['count'], **{f'r{i}':v for i,v in enumerate(self.eret['gpr'])})

    def test_exact_raw_witnesses_and_distinct_native_count_phases(self):
        report=bind(iter([self.entry, self.eret]), [self.device], [self.transfer], 7)
        self.assertEqual(report['device_instruction_witnesses'],1)
        self.assertEqual(report['eret_witnesses'],1)
        self.assertFalse(report['clock_alignment_validated'])
        self.assertFalse(report['all_effect_semantics_proved'])

    def test_every_point_boundary_field_is_required_without_aliasing(self):
        for field in ('pc','opcode','thread_word','status','cause'):
            row={**self.entry,field:self.entry[field]+4}
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'exact device witness'):
                bind(iter([row]),[self.device],[],7)
        row={**self.entry,'gpr':tuple([0]*31+[0x80003000])}
        with self.assertRaisesRegex(ValueError,'exact device witness'):
            bind(iter([row]),[self.device],[],7)

    def test_missing_point_wrong_sequence_and_extra_transfer_reject(self):
        for rows,devices,transfers in (([],[self.device],[]),([self.entry],[],[]),
                ([{**self.entry,'device_sequence':13}],[self.device],[]),
                ([self.entry],[self.device],[self.transfer]),
                ([self.entry,self.eret],[self.device],[])):
            with self.assertRaises(ValueError):
                bind(iter(rows),devices,transfers,7)

    def test_eret_raw_transfer_fields_and_all_gpr_bits_are_checked(self):
        for field in ('pc','opcode','owner','selected_owner','target','status','count'):
            row={**self.eret,field:self.eret[field]+4}
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'dedicated pre-handoff'):
                bind(iter([self.entry,row]),[self.device],[self.transfer],7)
        transfer={**self.transfer,'r31':0x80003000}
        with self.assertRaisesRegex(ValueError,'dedicated pre-handoff'):
            bind(iter([self.entry,self.eret]),[self.device],[transfer],7)

    def test_exhausts_reader_so_a_torn_footer_cannot_pass(self):
        def torn():
            yield self.entry
            raise ValueError('torn footer')
        with self.assertRaisesRegex(ValueError,'torn footer'):
            bind(torn(),[self.device],[],7)

    def test_no_rebinding_stale_device_sequence_or_cross_invocation(self):
        later={**self.entry,'pc':0x80001100}
        result=bind(iter([self.entry,later]),[self.device],[],7)
        self.assertEqual(result['device_instruction_witnesses'],1)
        for update in (0,True,1000001):
            with self.assertRaises(ValueError):
                bind(iter([self.entry]),[self.device],[],update)
        with self.assertRaisesRegex(ValueError,'invocation differs'):
            bind(iter([{**self.entry,'invocation':8}]),[self.device],[],7)
