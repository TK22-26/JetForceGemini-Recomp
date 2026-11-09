import copy
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
from scripts import phase9_oracle_instruction_effects as probe


def row(phase, **values):
    result = dict.fromkeys(probe.WORDS, 0)
    result.update(pc=0x80001000, live_pc=0x80001000, anchor=0x80001000,
                  opcode=0x24420001, status=1, thread_word=0x80007000, **values)
    result['phase'] = phase
    result['gpr'] = [0]+[(0xa0b0c00000000000 | index) for index in range(1,32)]
    return result


def encode(rows, update=7):
    data = bytearray(probe.MAGIC+struct.pack('<I', update))
    previous = None
    for item in rows:
        mask = sum(1 << index for index in range(32) if previous is None or previous[index] != item['gpr'][index])
        data += bytes([item['phase']])+struct.pack('<16I',*[item[key] for key in probe.WORDS],mask)
        for index in range(32):
            if mask & (1 << index): data += struct.pack('<Q',item['gpr'][index])
        previous = item['gpr']
    return data+b'\xff'+struct.pack('<I',len(rows))


class OracleEffectTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)/'effects.bin'
        self.rows = [row(0), row(1)]
        self.rows[1]['gpr'][2] += 1
        self.rows[1]['live_pc'] += 4

    def read(self, rows=None, raw=None):
        self.path.write_bytes(encode(self.rows if rows is None else rows) if raw is None else raw)
        return list(probe.records(self.path,7))

    def test_all_gpr_bits_survive_canonical_deltas(self):
        result = self.read()
        self.assertEqual(result[0]['gpr'],tuple(self.rows[0]['gpr']))
        self.assertEqual(result[1]['gpr'],tuple(self.rows[1]['gpr']))
        self.assertEqual(result[1]['phase'],'ordinary')
        summary = probe.summary(self.path,{'update':7})
        self.assertEqual(summary['phases'],{'entry':1,'ordinary':1})
        for field in probe.LIMITS: self.assertFalse(summary[field])

    def test_branch_eret_exception_and_idle_have_distinct_boundaries(self):
        for phase, opcode, start_status, changes in (
                (2,0x0c000404,1,dict(target=0x80001010,flags=1)),
                (3,0x42000018,3,dict(target=0x80004000,live_pc=0x80004000,
                    epc=0x80004000,anchor=0x80004000,status=1)),
                (4,0x0000000c,1,dict(target=0x80000180,live_pc=0x80000180,status=3)),
                (5,0x1000ffff,1,dict(target=0x80001000,idle_ticks=64))):
            rows = [row(0),row(phase)]
            for item in rows: item.update(opcode=opcode,status=start_status)
            rows[1].update(changes)
            with self.subTest(phase=phase):
                self.assertEqual(self.read(rows)[1]['phase'],probe.PHASES[phase])
                rows[1]['phase'] = 1
                with self.assertRaises(ValueError): self.read(rows)

    def test_every_truncation_and_trailing_bytes_reject(self):
        raw = encode(self.rows)
        for size in range(len(raw)):
            with self.assertRaises(ValueError): self.read(raw=raw[:size])
        with self.assertRaises(ValueError): self.read(raw=raw+b'X')

    def test_missing_wrong_or_overlapping_entry_rejects(self):
        for rows in ([self.rows[1]], [self.rows[0]], [self.rows[0],self.rows[0]],
                     [self.rows[0],{**self.rows[1],'pc':0x80001004}]):
            with self.assertRaises(ValueError): self.read(rows)

    def test_row_fields_and_phase_metadata_reject(self):
        for field,value in (('pc',1),('anchor',1),('thread_word',1),('delay_slot',4),
                            ('llbit',2),('device_sequence',65537),('flags',1),('idle_ticks',4),('status',3)):
            rows = copy.deepcopy(self.rows); rows[1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.read(rows)
        rows = copy.deepcopy(self.rows); rows[0]['device_sequence'] = 5
        with self.assertRaises(ValueError): self.read(rows)
        rows = copy.deepcopy(self.rows); rows[0]['gpr'][0] = 1
        with self.assertRaises(ValueError): self.read(rows)

    def test_mtc0_status_can_change_exl_without_masquerading_as_exception(self):
        rows = copy.deepcopy(self.rows)
        for item in rows: item['opcode'] = 0x40806000
        rows[1]['status'] = 3
        self.assertEqual(self.read(rows)[1]['phase'],'ordinary')

    def test_delay_branch_and_wrong_special_boundaries_reject(self):
        for phase, opcode, changes in (
                (0,0x0c000404,dict(delay_slot=1)),
                (2,0x24420001,dict(target=0x80001010)),
                (3,0x42000018,dict(status=3)),
                (4,0x0000000c,dict(status=3,target=0x80001000)),
                (5,0x1000ffff,dict(target=0x80001000,idle_ticks=2))):
            rows = [row(0),row(phase)]
            for item in rows: item['opcode'] = opcode
            rows[1].update(changes)
            with self.subTest(phase=phase), self.assertRaises(ValueError): self.read(rows)

    def test_budgets_and_invalid_header(self):
        with mock.patch.object(probe,'MAX_ROWS',1):
            with self.assertRaises(ValueError): self.read()
        with mock.patch.object(probe,'MAX_BYTES',10):
            with self.assertRaises(ValueError): self.read()
        for raw in (encode(self.rows,8), b'X'+encode(self.rows)[1:],encode([])):
            with self.assertRaises(ValueError): self.read(raw=raw)

    def test_configuration_requires_exact_cpu_window_and_clears_inheritance(self):
        cpu = {'update':7,'count_basis':'original-oracle-count-mutations'}
        for update,parent in ((True,cpu),(0,cpu),(8,cpu),(7,None),(7,{'update':7})):
            with self.assertRaises(ValueError): probe.specification(update,parent)
        spec = probe.specification(7,cpu)
        env = {'PATH':'kept','JFG_PHASE9_ORACLE_EFFECT_UPDATE':'999'}
        probe.configure(env,None); self.assertEqual(env,{'PATH':'kept'})
        probe.configure(env,spec); self.assertEqual(env['JFG_PHASE9_ORACLE_EFFECT_UPDATE'],'7')
