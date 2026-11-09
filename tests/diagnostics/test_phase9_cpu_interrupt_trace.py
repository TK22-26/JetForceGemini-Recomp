import tempfile
from pathlib import Path
import unittest

from scripts.phase9_cpu_interrupt_trace import HEADER, parse_trace


class InterruptTraceTests(unittest.TestCase):
    def source(self):
        return '\t'.join(HEADER) + '\n' + ''.join(
            f'{i}\t{1750 if i == 1 else 1366}\t{100+i}\t{200+i}\t1065353216\t8388608\t{i}\t1234\n'
            for i in range(1, 9)) + 'result\ttrue\t8\n'

    def parse(self, data):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'trace.tsv'
            path.write_text(data)
            return parse_trace(path)

    def test_complete(self):
        self.assertEqual(len(self.parse(self.source())['cases']), 8)

    def test_truncated(self):
        with self.assertRaises(ValueError):
            self.parse(self.source().replace('result\ttrue\t8\n', ''))

    def test_corrupt_state(self):
        for old, new in [('1234', '1235'), ('8388608', '0'), ('1065353216', '4294967296'), ('1750', '0')]:
            with self.subTest(old=old), self.assertRaises(ValueError):
                self.parse(self.source().replace(old, new, 1))
