from itertools import product
from pathlib import Path
import tempfile
import unittest
from scripts.phase9_cpu_branch_trace import HEADER, parse_trace


class BranchTraceTests(unittest.TestCase):
    def trace(self, annulled_charged=True):
        rows = ['\t'.join(HEADER)]
        for kind, taken, count in product(range(7), range(2), (16, 128)):
            executed = kind == 6 or taken
            ticks = 2 + count * (10 if executed or annulled_charged else 8)
            rows.append(f'{kind}\t{taken}\t{count}\t{count if executed else 0}\t{ticks}')
        return '\n'.join([*rows, 'result\ttrue\t28']) + '\n'

    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace.tsv'
            path.write_text(text)
            return parse_trace(path)

    def test_qualification_and_alternate_behavior(self):
        self.assertTrue(self.parse(self.trace())['counts_annulled_slots_at_two_ticks'])
        self.assertFalse(self.parse(self.trace(False))['counts_annulled_slots_at_two_ticks'])

    def test_reject_wrong_effects_order_and_partial(self):
        text = self.trace()
        for wrong in (text.replace('0\t0\t16\t0', '0\t0\t16\t16', 1),
                      text.replace('0\t0\t16\t0', '0\t0\t17\t0', 1),
                      text.replace('result\ttrue\t28', 'result\tfalse\t28'),
                      text + 'extra\n', text.replace('\t162\n', '\t-1\n', 1)):
            with self.subTest(text=wrong[:80]), self.assertRaises(ValueError):
                self.parse(wrong)
