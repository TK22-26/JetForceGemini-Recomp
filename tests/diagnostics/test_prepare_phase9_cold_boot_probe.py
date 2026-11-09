import unittest
from scripts.prepare_phase9_cold_boot_probe import explicit_neutral_gaps
from scripts.build_phase9_route_replays import Event, cold_boot_to_gameplay_probe_route


class NeutralGapTests(unittest.TestCase):
    def test_short_press_is_released_before_next_press(self):
        events = [Event(10, 20, 1, 0x8000, 0, 0), Event(50, 60, 1, 0x1000, 0, 0)]
        result = explicit_neutral_gaps(events, 70)
        self.assertEqual(result, [Event(0, 10, 1, 0, 0, 0), events[0],
                                 Event(20, 50, 1, 0, 0, 0), events[1],
                                 Event(60, 70, 1, 0, 0, 0)])

    def test_cold_route_is_contiguous(self):
        result = explicit_neutral_gaps(cold_boot_to_gameplay_probe_route(), 18000)
        self.assertEqual(result[0].first, 0)
        self.assertEqual(result[-1].last, 18000)
        self.assertTrue(all(a.last == b.first for a, b in zip(result, result[1:])))

    def test_invalid_intervals_rejected(self):
        for events in ([Event(3, 2, 1, 0, 0, 0)], [Event(0, 101, 1, 0, 0, 0)],
                       [Event(0, 10, 1, 0, 0, 0), Event(9, 20, 1, 0, 0, 0)]):
            with self.assertRaises(ValueError):
                explicit_neutral_gaps(events, 100)


if __name__ == "__main__":
    unittest.main()
