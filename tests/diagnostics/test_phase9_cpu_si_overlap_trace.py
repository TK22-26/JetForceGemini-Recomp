from pathlib import Path
import tempfile
import unittest
from scripts.phase9_cpu_si_overlap_trace import parse_trace


class SiOverlapTraceTests(unittest.TestCase):
    def fixture(self):
        lines = ['case\tfirst\tsecond\tlast_pending\tfirst_complete\tlate_mi\tlate_si']
        lines += [f'{i}\t10000\t{10034 + i % 8 * 96}\t12300\t12314\t8\t0' for i in range(32)]
        return '\n'.join([*lines, 'result\ttrue\t32']) + '\n'

    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace'
            path.write_text(text)
            return parse_trace(path)

    def test_qualified_pairs(self):
        self.assertEqual(len(self.parse(self.fixture())['cases']), 32)

    def test_rejects_replaced_deadline_and_duplicate_interrupt(self):
        source = self.fixture()
        for invalid in (source.replace('12300\t12314', '12500\t12514', 1),
                        source.replace('\t8\t0', '\t10\t4096', 1),
                        source.replace('result\ttrue', 'result\tfalse'),
                        source.replace('0\t10000', '1\t10000', 1)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.parse(invalid)


if __name__ == '__main__':
    unittest.main()
