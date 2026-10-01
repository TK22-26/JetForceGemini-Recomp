from pathlib import Path
import tempfile
import unittest
from scripts.phase9_cpu_vi_phase_trace import qualify
from scripts.phase9_cpu_vi_manager_trace import parse_trace as parse_manager
from scripts.phase9_cpu_boot_state_trace import parse_trace as parse_boot


class ViPhaseTests(unittest.TestCase):
    def parse(self, function, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'trace'
            path.write_text(content)
            return function(path)

    def phase(self):
        lines = ['v_sync\tsample\tcount\tcurrent\tedge_count']
        deadline, previous = 5005000, 0
        for vertical in (0, 525, 262, 625):
            for edge in range(4):
                if len(lines) > 1:
                    deadline += (previous + 1) * 1500 if previous else 500000
                previous = vertical
                for sample in range(8):
                    count = deadline + 24 + sample * 4428
                    current = (count - 2 - deadline) // 1500 & ~1
                    lines.append(f'{vertical}\t{edge * 8 + sample}\t{count}\t{current}\t{deadline + 16}')
        return '\n'.join([*lines, 'result\ttrue\t128'])

    def test_startup_latch_and_cpu_scanline(self):
        self.assertEqual(self.parse(qualify, self.phase())['scanline_reads'], 128)

    def test_bad_phase_line_reordered_and_incomplete_rejected(self):
        lines = self.phase().splitlines()
        for index, column, value in ((1, 4, '5005015'), (2, 3, '99'), (1, 1, '1'), (2, 4, '123')):
            bad = lines.copy()
            row = bad[index].split('\t')
            row[column] = value
            bad[index] = '\t'.join(row)
            with self.subTest(index=index, column=column), self.assertRaises(ValueError):
                self.parse(qualify, '\n'.join(bad))
        with self.assertRaises(ValueError):
            self.parse(qualify, '\n'.join(lines[:-1]))

    def test_manager_observations_retain_origin(self):
        lines = ['case\tcount\tpayload\tvi_count\ttime_hi\ttime_lo\tstatus']
        for i in range(24):
            count = 1000000 + i * 789000
            lines.append(f'{i}\t{count}\t1234\t{i+2}\t0\t{count-492}\t{0x0400ff01}')
        text = '\n'.join([*lines, 'result\ttrue\t24'])
        result = self.parse(parse_manager, text)
        self.assertEqual(result['cases'][0]['count'], 1000000)
        self.assertEqual(result['intervals'], [789000] * 23)
        with self.assertRaises(ValueError):
            self.parse(parse_manager, text.replace('1234', '1235', 1))

    def test_boot_capture_requires_unique_entries(self):
        header = 'event\tcount\tstatus\tcause\tcompare\tfcr31\tmi_pending\tmi_mask\tv_sync\th_sync'
        rows = [key + '\t' + '\t'.join(['00000000'] * 9)
                for key in ('entry', 'handoff', 'os-init', 'vi-init', 'vi-init-return')]
        text = '\n'.join([header, *rows, 'result\ttrue\t120'])
        self.assertEqual(len(self.parse(parse_boot, text)['events']), 5)
        with self.assertRaises(ValueError):
            self.parse(parse_boot, text.replace('handoff', 'entry'))
