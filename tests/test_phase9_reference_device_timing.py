from itertools import product
from pathlib import Path
import tempfile
import unittest
from scripts.phase9_reference_device_timing import qualify_rsp, qualify_vi, qualify_dma
from scripts.phase9_cpu_dma_trace import parse_trace as parse_dma
from scripts.phase9_cpu_vi_trace import parse_trace


class ReferenceDeviceTimingTests(unittest.TestCase):
    def dma_trace(self, wrap=False):
        lines = ['kind\tlength\tphase\tlaunch\tlast_pending\tfirst_complete']
        for kind, length, phase in product(range(3), (16, 64, 1024, 4096), range(8)):
            launch = 0xffffff00 if wrap else 10000
            latency = 2304 if kind else length // 8
            lower = latency + 2 - (2 + 2 * (phase % 7))
            if kind == 0 and length < 1024:
                lower, upper = 0, 24
            else:
                upper = lower + 14
            fields = (kind, length, phase, launch, (launch + lower) & 0xffffffff,
                      (launch + upper) & 0xffffffff)
            lines.append('\t'.join(map(str, fields)))
        return '\n'.join([*lines, 'result\ttrue\t96']) + '\n'

    def test_dma_thresholds_and_underresolved_small_transfers(self):
        for wrap in (False, True):
            result = self.run_trace(qualify_dma, self.dma_trace(wrap))
            self.assertEqual([r['effective_latency'] for r in result], [None, None, 128, 512] + [2304] * 8)

    def test_dma_rejects_missing_case_bad_state_and_inconsistent_windows(self):
        trace = self.dma_trace()
        for bad in (trace.replace('result\ttrue\t96', ''),
                    trace.replace('0\t16\t0', '3\t16\t0', 1)):
            with self.assertRaises(ValueError):
                self.run_trace(parse_dma, bad)
        lines = trace.splitlines()
        row = lines[18].split('\t')
        row[-2:] = ['10998', '11000']
        lines[18] = '\t'.join(row)
        with self.assertRaises(ValueError):
            self.run_trace(qualify_dma, '\n'.join(lines))

    def run_trace(self, function, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace"
            path.write_text(text)
            return function(path)

    def vi_trace(self, samples=32):
        lines = ["v_sync\th_sync\tsample\tticks"]
        for vertical, horizontal, sample in product((261, 262, 525, 526, 624, 625), (3093, 3177), range(samples)):
            lines.append(f"{vertical}\t{horizontal}\t{sample}\t{(vertical + 1) * 1500}")
        return "\n".join([*lines, f"result\ttrue\t{len(lines) - 1}"]) + "\n"

    def rsp_trace(self, wrap=False):
        lines = ["case\tlaunch\tlast_running\tfirst_halted\thelper_entry\tbefore_start"]
        lows = (1004, 1000, 996, 992, 1002, 998, 994, 1004,
                4000, 3996, 3992, 4002, 3998, 3994, 4004, 4000)
        for case, low in enumerate(lows, 1):
            launch = 0xfffffff0 if wrap else 20000 * case
            fields = (case, launch, (launch + low) & 0xffffffff,
                      (launch + low + 14) & 0xffffffff, launch, (launch - 40) & 0xffffffff)
            lines.append("\t".join(map(str, fields)))
        return "\n".join([*lines, "result\ttrue\t16"]) + "\n"

    def test_vi_periods(self):
        self.assertEqual(len(self.run_trace(qualify_vi, self.vi_trace())), 12)
        self.assertEqual(len(self.run_trace(parse_trace, self.vi_trace(5))["cases"]), 60)

    def test_reject_vi_insufficient_samples_or_bad_period(self):
        for text in (self.vi_trace(5), self.vi_trace().replace("393000", "393032", 1),
                     self.vi_trace().replace("\t0\t393000", "\t1\t393000", 1)):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.run_trace(qualify_vi, text)
        # Sum alone must not qualify large mutually cancelling errors.
        lines = self.vi_trace().splitlines()
        lines[1] = lines[1].replace("393000", "393100")
        lines[2] = lines[2].replace("393000", "392900")
        with self.assertRaises(ValueError):
            self.run_trace(qualify_vi, "\n".join(lines))

    def test_rsp_thresholds_and_count_wrap(self):
        for wrap in (False, True):
            result = self.run_trace(qualify_rsp, self.rsp_trace(wrap))
            self.assertEqual([r["effective_latency"] for r in result], [1000, 4000])

    def test_rsp_rejects_boundary_and_completion_changes(self):
        trace = self.rsp_trace()
        for text in (trace.replace("\t19960", "\t19962", 1),
                     trace.replace("21018", "21020", 1),
                     trace.replace("result\ttrue\t16", "result\ttrue\t15")):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.run_trace(qualify_rsp, text)


if __name__ == "__main__":
    unittest.main()
