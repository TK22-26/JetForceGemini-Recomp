import copy
import unittest
from scripts import phase9_instruction_correspondence as probe


class InstructionCorrespondenceTests(unittest.TestCase):
    def setUp(self):
        self.gpr = tuple([0]+[0xa0b0000000000000+i for i in range(1,31)]+[0xffffffff80044bf8])
        self.native,self.oracle = [],[]
        def item(pc,opcode,phase,gpr,status=3,**extra):
            return dict(pc=pc,opcode=opcode,phase=phase,gpr=tuple(gpr),status=status,cause=0,
                thread_word=0x80007000,owner=0x80007000,section=0,count=100,anchor=pc,
                delay_slot=0,target=0,flags=0,invocation=7,**extra)
        lead_pc=0x80045814
        self.oracle = [item(lead_pc,0x03e00008,'entry',self.gpr),item(lead_pc,0x03e00008,'branch',self.gpr),
                       item(lead_pc+4,0,'entry',self.gpr),item(lead_pc+4,0,'ordinary',self.gpr)]
        self.oracle[1].update(flags=1,target=0x80044bf8)
        self.oracle[2]['delay_slot']=self.oracle[3]['delay_slot']=1
        for phase in (0,1):
            self.native.append(item(0x80044bf8,0,phase,self.gpr))
            self.oracle.append(item(0x80044bf8,0,'entry' if phase==0 else 'ordinary',self.gpr))
        registers=list(self.gpr)
        for index,opcode in enumerate(probe.VECTOR_WORDS):
            for phase in (0,1):
                if phase and index==0: registers[26]=0xffffffff80070000
                if phase and index==1: registers[26]=0xffffffff80075030
                self.native.append(item(probe.VECTOR_SOURCE+index*4,opcode,phase,registers))
                tag='entry' if phase==0 else 'branch' if index==2 else 'ordinary'
                value=item(probe.VECTOR_INSTALLED+index*4,opcode,tag,registers)
                if index==2 and phase: value.update(flags=1,target=probe.VECTOR_TARGET)
                if index==3: value['delay_slot']=1
                self.oracle.append(value)
        for phase in (0,1):
            self.native.append(item(probe.VECTOR_TARGET,0,phase,registers))
            self.oracle.append(item(probe.VECTOR_TARGET,0,'entry' if phase==0 else 'ordinary',registers))
        for rows in (self.native,self.oracle):
            for index,value in enumerate(rows,1): value['sequence']=index
        data=bytearray(4*1024*1024)
        words=b''.join(word.to_bytes(4,'big') for word in probe.VECTOR_WORDS)
        for address in (probe.VECTOR_SOURCE,probe.VECTOR_INSTALLED):
            offset=address & 0x1fffffff; data[offset:offset+16]=words
        self.snapshots={7:bytes(data)}
        self.evidence=probe.qualify_vector_snapshots(self.snapshots,self.snapshots)

    def compare(self,native=None,oracle=None):
        return probe.compare(iter(self.native if native is None else native),
            iter(self.oracle if oracle is None else oracle),7,self.evidence)

    def test_exact_epilogue_vector_and_target_preserve_raw_addresses(self):
        result=self.compare()
        self.assertEqual(result['matching_rows'],12)
        self.assertEqual(result['first_difference']['kind'],'window-end')
        self.assertEqual(len(result['vector_mappings']),1)
        row=result['vector_mappings'][0]['rows'][0]
        self.assertEqual((row['native_pc'],row['oracle_pc']),(probe.VECTOR_SOURCE,probe.VECTOR_INSTALLED))
        self.assertEqual(result['return_anchor']['caller_native_sequence'],1)
        self.assertEqual(result['return_anchor']['caller_oracle_sequence'],5)
        for key in ('clock_alignment_validated','all_code_identity_qualified','causal_fix_proved','parity_verified'):
            self.assertFalse(result[key])

    def test_snapshot_identity_is_more_than_source_and_destination_equality(self):
        data=bytearray(self.snapshots[7])
        for address in (probe.VECTOR_SOURCE,probe.VECTOR_INSTALLED): data[address & 0x1fffffff]=0
        for a,b in (({},{}),(self.snapshots,{8:self.snapshots[7]}),({7:b'X'},self.snapshots),({7:bytes(data)},{7:bytes(data)})):
            with self.assertRaises(ValueError): probe.qualify_vector_snapshots(a,b)

    def test_arbitrary_lead_in_offset_or_non_nop_slot_rejects(self):
        for index,field,value in ((0,'opcode',0x03e00009),(1,'target',0x80044bfc),(2,'opcode',1),
                                  (2,'pc',0x8004581c),(3,'delay_slot',0),(4,'pc',0x80044bfc)):
            rows=copy.deepcopy(self.oracle); rows[index][field]=value
            with self.subTest(index=index,field=field),self.assertRaises(ValueError): self.compare(oracle=rows)

    def test_equal_but_wrong_vector_register_effects_reject(self):
        a,b=copy.deepcopy(self.native),copy.deepcopy(self.oracle)
        for rows,index in ((a,3),(b,7)):
            registers=list(rows[index]['gpr']); registers[26]+=1; rows[index]['gpr']=tuple(registers)
        result=self.compare(a,b)
        self.assertEqual(result['first_difference']['kind'],'unqualified-code-mapping')
        self.assertEqual(result['matching_rows'],2)

    def test_equal_but_wrong_vector_opcodes_reject(self):
        a,b=copy.deepcopy(self.native),copy.deepcopy(self.oracle)
        a[2]['opcode']=b[6]['opcode']=0
        self.assertEqual(self.compare(a,b)['first_difference']['kind'],'unqualified-code-mapping')

    def test_vector_entry_state_order_target_and_following_handler_are_required(self):
        for side,index,field,value in (('native',2,'section',1),('native',2,'status',1),
                ('oracle',11,'target',0x80075034),('oracle',12,'delay_slot',0),
                ('oracle',14,'pc',0x80075034),('oracle',6,'thread_word',0x80009000)):
            a,b=copy.deepcopy(self.native),copy.deepcopy(self.oracle)
            (a if side=='native' else b)[index][field]=value
            with self.subTest(field=field):
                self.assertEqual(self.compare(a,b)['first_difference']['kind'],'unqualified-code-mapping')

    def test_no_general_address_offset_or_search(self):
        rows=copy.deepcopy(self.oracle); rows[5]['pc']+=4
        result=self.compare(oracle=rows)
        self.assertEqual(result['matching_rows'],1)
        self.assertEqual(result['first_difference']['kind'],'raw-code-identity')

    def test_shared_state_difference_is_retained(self):
        for field in ('status','cause','thread_word'):
            rows=copy.deepcopy(self.oracle); rows[5][field]+=4
            result=self.compare(oracle=rows)
            self.assertEqual(result['first_difference']['kind'],'shared-state')
            self.assertIn(field,result['first_difference']['fields'])
        rows=copy.deepcopy(self.oracle); registers=list(rows[5]['gpr']); registers[3]^=1<<40
        rows[5]['gpr']=tuple(registers)
        self.assertIn('3',self.compare(oracle=rows)['first_difference']['fields']['gpr'])

    def test_unknown_special_phase_is_not_an_ordinary_effect(self):
        for phase in ('idle','exception'):
            rows=copy.deepcopy(self.oracle); rows[5]['phase']=phase
            self.assertEqual(self.compare(oracle=rows)['first_difference']['kind'],'effect-boundary')

    def test_tail_reader_failure_prevents_accepted_prefix_finding(self):
        rows=copy.deepcopy(self.oracle); rows[5]['pc']+=4
        def incomplete():
            yield from rows
            raise ValueError('missing footer')
        with self.assertRaisesRegex(ValueError,'footer'):
            probe.compare(iter(self.native),incomplete(),7,self.evidence)

    def test_counts_are_not_fitted_or_claimed_equivalent(self):
        rows=copy.deepcopy(self.oracle)
        for row in rows: row['count']+=10000
        result=self.compare(oracle=rows)
        self.assertEqual(result['matching_rows'],12)
        self.assertFalse(result['clock_alignment_validated'])
        self.assertEqual(result['preceding_context'][-1]['oracle']['count'],10100)

    def test_invalid_update_and_absent_proof_reject(self):
        for update,evidence in ((True,self.evidence),(0,self.evidence),(7,None)):
            with self.assertRaises(ValueError): probe.compare(iter(self.native),iter(self.oracle),update,evidence)
