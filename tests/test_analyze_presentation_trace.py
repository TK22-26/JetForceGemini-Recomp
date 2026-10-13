import math
import unittest
from scripts.analyze_presentation_trace import analyze


def row(tick, rate, alpha, timestamp=0):
    return f"display\t{timestamp}\t{tick}\t{rate}\t120\t0\t4\t{alpha:.6g}\t42\t0\n"


class PresentationTraceTests(unittest.TestCase):
    def test_changing_source_cadence_keeps_uniform_output_phase(self):
        lines = [row(100, 30, 1)]
        lines += [row(103, 20, n / 6, n * 8333) for n in range(1, 7)]
        lines += [row(105, 30, .25, 7 * 8333)]
        report = analyze(lines, expected_fps=120)
        self.assertEqual(report["samples"], 8)
        self.assertEqual(report["uneven_phase_steps"], 0)
        self.assertEqual(report["repeated_phases"], 0)
        self.assertEqual(report["backward_phases"], 0)

    def test_stable_present_counter_does_not_hide_freeze_and_jump(self):
        lines = [row(100, 30, 1, n * 8333) for n in range(4)]
        lines += [row(104, 30, .25, 4 * 8333)]
        report = analyze(lines, expected_fps=120)
        self.assertEqual(report["present_interval_ms"]["maximum"], 8.333)
        self.assertEqual(report["repeated_phases"], 3)
        self.assertEqual(report["uneven_phase_steps"], 4)
        self.assertEqual(report["phase_step_counts"]["2.5000"], 1)

    def test_backwards_filter_and_uninterpolated_records(self):
        report = analyze(["render\tignored\n", row(99, 30, 1), row(102, 30, 1),
                          row(100, 30, 1), row(103, 0, 1), row(104, 30, 1)],
                         first_vi=100, last_vi=104)
        self.assertEqual(report["samples"], 2)
        self.assertEqual(report["backward_phases"], 1)

    def test_invalid_data_is_not_silently_successful(self):
        for line in ["display\t1\n", row(100, 30, math.nan), row(100, -1, .5)]:
            with self.assertRaises(ValueError):
                analyze([line])
        with self.assertRaises(ValueError):
            analyze([], expected_fps=0)
        self.assertEqual(analyze([])["samples"], 0)


if __name__ == "__main__":
    unittest.main()
