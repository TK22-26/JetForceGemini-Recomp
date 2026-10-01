from pathlib import Path
import tempfile
import unittest

from scripts.phase9_cpu_links_trace import HEADER, SENTINEL, expected, parse_trace, payload_words, verify_payload


class LinkTraceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'links.tsv'
        self.lines = ['\t'.join(HEADER)]
        for case in range(12):
            pc = 0x80000420 + case * 0x70
            slot, link, taken = expected(case, pc)
            self.lines.append('\t'.join(f'{v:08x}' for v in
                (case, pc, slot >> 32, slot & 0xffffffff, link >> 32, link & 0xffffffff, taken)))
        self.lines.append('result\ttrue\t12')

    def read(self, lines=None):
        self.path.write_text('\n'.join(self.lines if lines is None else lines) + '\n')
        return parse_trace(self.path)

    def test_complete_architectural_values_and_qualification_limits(self):
        value = self.read()
        self.assertTrue(value['matches_vr4300_manual'])
        self.assertEqual(len(value['cases']), 12)
        self.assertFalse(value['hardware_tested'])
        self.assertFalse(value['game_cause_proved'])

    def test_expected_not_derived_from_observed_values(self):
        self.assertEqual(expected(0, 0x80000420), (0xffffffff80000428, 0xffffffff80000428, 1))
        self.assertEqual(expected(1, 0x80000420), (SENTINEL, 0xffffffff8000042c, 1))
        self.assertEqual(expected(5, 0x80000420), (0xffffffff80000428, 0xffffffff80000428, 0))
        self.assertEqual(expected(9, 0x80000420), (SENTINEL, 0xffffffff80000428, 0))

    def test_semantic_failure_is_retained_not_a_parse_failure(self):
        for column in (2, 3, 4, 5, 6):
            lines = self.lines.copy()
            words = lines[1].split('\t')
            words[column] = '00000000'
            lines[1] = '\t'.join(words)
            with self.subTest(column=column):
                result = self.read(lines)
                self.assertFalse(result['matches_vr4300_manual'])
                self.assertEqual([row['case'] for row in result['mismatches']], [0])

    def test_header_footer_order_width_address_and_extra_rows_reject(self):
        for lines in (self.lines[:-1], self.lines + ['extra'], self.lines[1:],
                      [*self.lines[:2], self.lines[1], *self.lines[3:]],
                      [self.lines[0], self.lines[1].replace('80000420','00000420'), *self.lines[2:]],
                      [self.lines[0], self.lines[1].replace('80000420','80000422'), *self.lines[2:]],
                      [self.lines[0], self.lines[1].replace('80000420','8000042'), *self.lines[2:]]):
            with self.assertRaises(ValueError):
                self.read(lines)

    def test_case_and_byte_limits(self):
        for case,pc in ((True,0x80000400),(12,0x80000400),(0,0x80001000)):
            with self.assertRaises(ValueError): expected(case,pc)
        self.path.write_text('x' * 16385)
        with self.assertRaises(ValueError): parse_trace(self.path)

    def test_payload_binds_exact_sites_and_high_low_store_instructions(self):
        observed = self.read()
        rom = Path(self.temp.name) / 'private-test.n64'
        data = bytearray(2*1024*1024)
        for row in observed['cases']:
            for relative,word in payload_words(row['case'],row['pc']).items():
                offset = 0x1000 + row['pc'] - 0x80000400 + relative
                data[offset:offset+4] = word.to_bytes(4,'big')
        rom.write_bytes(data)
        self.assertEqual(verify_payload(rom,observed)['checked_instruction_words'],228)
        # The actual O32 pseudo-op mistake must not qualify as a 64-bit store.
        offset=0x1000+observed['cases'][0]['pc']-0x80000400+40
        data[offset:offset+4]=(0xae120008).to_bytes(4,'big')
        rom.write_bytes(data)
        with self.assertRaisesRegex(ValueError,'assembled link payload'):
            verify_payload(rom,observed)
