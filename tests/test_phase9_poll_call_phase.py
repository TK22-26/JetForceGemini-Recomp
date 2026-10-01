import json
from pathlib import Path
import tempfile
import unittest

from scripts.compare_phase9_poll_hashes import HEADER
from scripts.phase9_poll_call_phase import analyze


class PollCallPhaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def trace(self, side, counts):
        path = self.root / f"{side}.jsonl"
        rows = [HEADER]
        for poll, (start, get) in enumerate(counts):
            rows.append({
                "kind": "jfg-phase9-poll-hash", "schema": 1, "poll": poll,
                "connected": 1, "buttons": 0, "stick_x": 0, "stick_y": 0,
                "update_counter_valid": False, "completed_updates": None,
                "front_mode": 0, "level_word": 0,
                "rng_seed": "0x00000000", "player_actor": "0x00000000",
                "player_sha256": None, "actor_list": "0x00000000",
                "actor_count": 0, "actor_table_sha256": None,
                "globals_sha256": None, "camera_sha256": None, "actors": [],
                "vi_retraces" if side == "native" else "emulator_frame": poll,
                "controller_read_start_calls": start,
                "controller_get_data_calls": get,
            })
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n",
                        encoding="utf-8")
        return path

    def test_same_phase_still_does_not_validate_alignment(self):
        report = analyze(self.trace("native", [(1, 0), (2, 1)]),
                         self.trace("oracle", [(1, 0), (2, 1)]))
        self.assertTrue(report["same_call_phase"])
        self.assertTrue(report["hooks_observed"])
        self.assertFalse(report["alignment_validated"])
        self.assertFalse(report["parity_verified"])

    def test_first_difference_and_offsets(self):
        report = analyze(self.trace("native", [(1, 0), (2, 1)]),
                         self.trace("oracle", [(1, 0), (1, 1)]))
        self.assertEqual(report["first_call_phase_difference"]["poll"], 1)
        self.assertEqual(report["offset_counts"], [
            {"native_minus_oracle_start": 0, "native_minus_oracle_get": 0,
             "polls": 1},
            {"native_minus_oracle_start": 1, "native_minus_oracle_get": 0,
             "polls": 1},
        ])

    def test_missing_or_decreasing_counters_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "lacks call-phase"):
            analyze(self.trace("native", [(1, 0)]),
                    self.trace("oracle", [(None, 0)]))
        with self.assertRaisesRegex(ValueError, "decreased"):
            analyze(self.trace("native", [(2, 0), (1, 1)]),
                    self.trace("oracle", [(2, 0), (2, 1)]))

    def test_different_lengths_fail_closed(self):
        with self.assertRaises(ValueError):
            analyze(self.trace("native", [(1, 0), (2, 1)]),
                    self.trace("oracle", [(1, 0)]))
        report = analyze(self.trace("native", [(1, 0), (2, 1)]),
                         self.trace("oracle", [(1, 0)]), prefix_polls=1)
        self.assertEqual(report["polls_compared"], 1)
        with self.assertRaises(ValueError):
            analyze(self.trace("native", [(1, 0), (2, 1)]),
                    self.trace("oracle", [(1, 0)]), prefix_polls=2)


if __name__ == "__main__":
    unittest.main()
