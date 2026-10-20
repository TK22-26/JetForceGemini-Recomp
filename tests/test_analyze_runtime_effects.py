import math
import unittest

from scripts.analyze_runtime_effects import analyze


def row(time_us, event, *values):
    return f"{time_us}\t{event}\t" + "\t".join(f"{value:x}" for value in values) + "\n"


class RuntimeEffectTraceTests(unittest.TestCase):
    def test_reticle_calls_without_writes_do_not_qualify_visibility(self):
        report = analyze([row(1, "reticle-line-output", 2, 0x10ff00, 0),
                          row(2, "reticle-line-output", 4, 0x135700, 12),
                          row(3, "rain-pixel-output", 4, 0x135700, 76800, 28)],
                         from_seconds=0)
        self.assertEqual(report["cpu_effects"]["reticle"],
                         {"calls": 2, "calls_with_changed_pixels": 1, "changed_pixels": 12})
        self.assertEqual(report["cpu_effects"]["rain"]["changed_pixels"], 28)

    def test_queue_age_uses_current_bytes_and_sample_rate_not_total(self):
        # Cumulative output is large; only 4000 bytes are waiting (100 ms).
        report = analyze([row(12_000_000, "audio-queue", 4000, 4_000_000, 3_996_000, 10000, 1)])
        self.assertEqual(report["audio"]["queue_ms_playing"]["maximum"], 100)
        self.assertEqual(report["audio"]["playing_samples_over_250ms"], 0)

    def test_startup_and_paused_queue_are_separate_from_playing_latency(self):
        report = analyze([row(1_000_000, "audio-queue", 40000, 40000, 0, 10000, 0),
                          row(12_000_000, "audio-queue", 60000, 60000, 0, 10000, 0),
                          row(13_000_000, "audio-queue", 4000, 64000, 60000, 10000, 1)])
        self.assertEqual(report["audio"]["queue_samples"], 2)
        self.assertEqual(report["audio"]["queue_ms_all_states"]["maximum"], 1500)
        self.assertEqual(report["audio"]["queue_ms_playing"]["maximum"], 100)

    def test_persistent_backlog_is_reported_without_underrun_event(self):
        report = analyze([row(t, "audio-queue", 48000, 48000 + i * 4000, i * 4000, 10000, 1)
                          for i, t in enumerate((12_000_000, 62_000_000, 122_000_000))])
        self.assertEqual(report["audio"]["playing_samples_over_1000ms"], 3)
        self.assertEqual(report["audio"]["minute_medians_ms"], {"0": 1200, "1": 1200, "2": 1200})
        self.assertNotIn("audio-underrun", report["event_counts"])

    def test_missing_probes_and_malformed_data_do_not_mean_clean_capture(self):
        report = analyze(["jfg-gameplay-trace-v1\ttime_us\tevent\tvalues_hex\n"])
        self.assertIsNone(report["audio"]["queue_ms_playing"])
        self.assertEqual(report["cpu_effects"]["reticle"]["calls"], 0)
        for trace in ([row(12_000_000, "audio-queue", 4000, 3000, 0, 10000, 1)],
                      [row(12_000_000, "audio-queue", 0, 0, 0, 0, 1)],
                      [row(12_000_000, "reticle-line-output", 1, 2)],
                      [row(12_000_000, "reticle-line-output", 1, 2, 0),
                       row(11_000_000, "reticle-line-output", 1, 2, 0)]):
            with self.assertRaises(ValueError):
                analyze(trace)
        for start in (-1, math.inf, math.nan):
            with self.assertRaises(ValueError):
                analyze([], from_seconds=start)


if __name__ == "__main__":
    unittest.main()
