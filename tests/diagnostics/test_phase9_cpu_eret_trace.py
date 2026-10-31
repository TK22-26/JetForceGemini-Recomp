import tempfile
import unittest
from pathlib import Path
from scripts.phase9_cpu_eret_trace import parse_trace


class ErETTraceTests(unittest.TestCase):
    def test_reference_and_control(self):
        valid = ('kind\titerations\teffects\tticks\tstatus\n'
                 '0\t16\t16\t290\t67108866\n0\t128\t128\t2306\t67108866\n'
                 '1\t16\t16\t258\t67108864\n1\t128\t128\t2050\t67108864\n'
                 'result\ttrue\t4\n')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace'
            path.write_text(valid)
            self.assertTrue(parse_trace(path)['eret_zero_increment_reference'])
            path.write_text(valid.replace('2050', '2052'))
            self.assertFalse(parse_trace(path)['eret_zero_increment_reference'])
            for malformed in (valid.replace('67108864', '67108866'),
                              valid.replace('1\t16\t16', '1\t16\t15'), valid[:-4],
                              valid.replace('2050', '-1')):
                path.write_text(malformed)
                with self.assertRaises(ValueError):
                    parse_trace(path)
