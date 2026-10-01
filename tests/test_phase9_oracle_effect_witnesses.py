import copy
import unittest
from scripts.phase9_oracle_effect_witnesses import bind


class OracleWitnessTests(unittest.TestCase):
    def setUp(self):
        entry = dict(invocation=7,phase='entry',device_sequence=12,pc=0x80001000,opcode=0,
            thread_word=0x80007000,count=100,anchor=0x80000ff0,status=1,cause=0,gpr=tuple(range(32)))
        device = dict(invocation=7,sequence=12,phase='instruction',pc=entry['pc'],opcode=0,
            thread=entry['thread_word'],clock_raw=100,clock_anchor_pc=entry['anchor'],status=1,cause=0)
        for i in range(32): device.update({f'r{i}_lo':i,f'r{i}_hi':0})
        eret = dict(entry,phase='eret',target=0x80004000,live_pc=0x80004000,epc=0x80004000,
            llbit=0,anchor=0x80004000,pc=0x80001010,opcode=0x42000018)
        cpu_eret = dict(invocation=7,kind='eret',pc=eret['pc'],target_pc=eret['target'],count_after=100,
            anchor_after=eret['anchor'],status_after=1,epc_after=eret['epc'],llbit_after=0,
            thread_word_after=eret['thread_word'],device_sequence=12,**{f'r{i}':i for i in range(32)})
        idle = dict(entry,phase='idle',idle_ticks=64)
        cpu_idle = dict(invocation=7,kind='count',reason='idle',pc=idle['pc'],count_after=100,
            anchor_after=idle['anchor'],operand=64,status=1,cause=0,thread_word=idle['thread_word'],device_sequence=12)
        self.rows, self.devices, self.cpu = [entry,eret,idle], [device], [cpu_eret,cpu_idle]

    def test_exact_local_witnesses_do_not_claim_cross_engine_alignment(self):
        result = bind(iter(self.rows),self.devices,self.cpu,7)
        self.assertEqual((result['device_instruction_witnesses'],result['eret_witnesses'],result['idle_witnesses']),(1,1,1))
        self.assertFalse(result['cross_engine_correspondence_validated'])

    def test_each_witness_is_required(self):
        for index in range(3):
            rows = copy.deepcopy(self.rows); rows.pop(index)
            with self.assertRaises(ValueError): bind(rows,self.devices,self.cpu,7)

    def test_wrong_values_or_register_bits_reject(self):
        for index,key in ((0,'count'),(0,'opcode'),(1,'epc'),(1,'device_sequence'),(2,'idle_ticks')):
            rows = copy.deepcopy(self.rows); rows[index][key] += 1
            with self.assertRaises(ValueError): bind(rows,self.devices,self.cpu,7)
        rows = copy.deepcopy(self.rows)
        rows[0]['gpr'] = (0, 1 | 0x100000000, *range(2,32))
        with self.assertRaises(ValueError): bind(rows,self.devices,self.cpu,7)

    def test_extra_effects_and_incomplete_iterator_reject(self):
        for index in (1,2):
            with self.assertRaises(ValueError): bind([*self.rows,self.rows[index]],self.devices,self.cpu,7)
        def truncated():
            yield from self.rows
            raise ValueError('missing footer')
        with self.assertRaisesRegex(ValueError,'footer'): bind(truncated(),self.devices,self.cpu,7)
