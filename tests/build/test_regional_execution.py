from dataclasses import replace
import unittest
from scripts.regional.execution import ExecutionSites,metadata
from scripts.regional.program_model import CodeRef

class ExecutionContractTests(unittest.TestCase):
    def test_scheduler_target_is_selected_explicitly(self):
        a=ExecutionSites('a','0'*64,CodeRef('a','main',0),0x80002000,(),frozenset())
        b=replace(a,revision_id='b',park_address=0x80004000)
        jal=0x0c000000|((0x80002000>>2)&0x03ffffff)
        self.assertTrue(metadata(0,0x80001000,jal,a)&(1<<9))
        self.assertFalse(metadata(0,0x80001000,jal,b)&(1<<9))
    def test_idle_instruction_is_not_a_callable_entry(self):
        a=ExecutionSites('a','0'*64,CodeRef('a','main',0),0x80002000,(('main',4),),frozenset({0x80001004}))
        self.assertTrue(metadata(0,0x80001004,0,a)&(1<<11))
        self.assertFalse(metadata(0,0x80001008,0,a)&(1<<11))
        self.assertTrue(metadata(0,0x80001008,0x1000ffff,a)&(1<<11))
    def test_architectural_costs_do_not_change_by_revision(self):
        a=ExecutionSites('a','0'*64,CodeRef('a','main',0),0x80002000,(),frozenset())
        b=replace(a,revision_id='b',park_address=0x80004000)
        for word in (0x46000000,0x8c820000,0xac820000,0x0000001a):self.assertEqual(metadata(3,0x80001000,word,a),metadata(3,0x80001000,word,b))

if __name__=='__main__':unittest.main()
