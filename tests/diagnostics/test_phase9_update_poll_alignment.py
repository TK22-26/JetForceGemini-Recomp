import json
import tempfile
import unittest
from pathlib import Path

from scripts.phase9_update_poll_alignment import diagnose


def trace(path, states, polls, *, oracle=False, clocks=None,
          consumed_vi=None):
    header = {"kind": "jfg-phase9-update-hash-header", "schema": 1}
    lines = [json.dumps(header)]
    for index, (state, poll) in enumerate(zip(states, polls), 1):
        record = {"kind": "jfg-phase9-update-hash", "schema": 1,
                  "update": index, "front_mode": state, "actor_count": 0,
                  "actors": [], "rng_seed": f"0x{state:08x}",
                  "actor_list": "0x00000000", "player_actor": "0x00000000",
                  "player_sha256": None, "actor_table_sha256": None,
                  "globals_sha256": "0" * 64, "camera_sha256": "1" * 64,
                  "controller_polls": poll}
        record["emulator_frame" if oracle else "vi_retraces"] = \
            clocks[index - 1] if clocks is not None else index * 2
        if consumed_vi is not None:
            record["oracle_consumed_vi"] = consumed_vi[index - 1]
        lines.append(json.dumps(record))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class UpdatePollAlignmentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_same_poll_resynchronization_is_diagnostic_only(self):
        native = self.root / "native.jsonl"
        oracle = self.root / "oracle.jsonl"
        trace(native, [0, 1, 2, 2, 2, 2, 3, 4, 5, 6],
              [0, 1, 2, 3, 4, 5, 8, 9, 10, 11])
        trace(oracle, [0, 1, 2, 3, 4, 5, 6], [0, 1, 2, 8, 9, 10, 11],
              oracle=True)
        report = diagnose(native, oracle, 4, max_slip=4, minimum_run=4)
        self.assertEqual(report["classification"],
                         "poll-anchored-semantic-resynchronization")
        self.assertEqual(report["same_poll_anchor"]["native_update"], 7)
        self.assertEqual(report["same_poll_anchor"]["oracle_update"], 4)
        self.assertEqual(report["matched_update_run"], 4)
        self.assertTrue(report["native_suffix_exhausted"])
        self.assertIsNone(report["first_later_mismatch"])
        self.assertGreaterEqual(report["clock_delta_change_count"], 1)
        self.assertEqual(report["first_clock_delta_changes"][0]["update"], 1)
        self.assertFalse(report["alignment_validated"])
        self.assertFalse(report["parity_verified"])

    def test_without_same_poll_anchor_remains_unresolved(self):
        native = self.root / "native.jsonl"
        oracle = self.root / "oracle.jsonl"
        trace(native, [0, 1, 2, 2, 2, 3, 4, 5], [0, 1, 2, 3, 4, 8, 9, 10])
        trace(oracle, [0, 1, 2, 3, 4, 5], [0, 1, 2, 7, 9, 10], oracle=True)
        report = diagnose(native, oracle, 4, max_slip=4, minimum_run=3)
        self.assertEqual(report["classification"], "unresolved-update-mismatch")
        self.assertIsNone(report["same_poll_anchor"])

    def test_rejects_missing_poll_metadata(self):
        native = self.root / "native.jsonl"
        oracle = self.root / "oracle.jsonl"
        trace(native, [0, 1], [0, 1])
        trace(oracle, [0, 2], [0, 1], oracle=True)
        lines = native.read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[2])
        record.pop("controller_polls")
        native.write_text(lines[0] + "\n" + lines[1] + "\n" +
                          json.dumps(record) + "\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            diagnose(native, oracle, 2, minimum_run=2)

    def test_reports_later_mismatch_after_valid_anchor(self):
        native = self.root / "native.jsonl"
        oracle = self.root / "oracle.jsonl"
        trace(native, [0, 1, 2, 2, 2, 2, 3, 4, 99],
              [0, 1, 2, 3, 4, 5, 8, 9, 10])
        trace(oracle, [0, 1, 2, 3, 4, 5],
              [0, 1, 2, 8, 9, 10], oracle=True)
        report = diagnose(native, oracle, 4, max_slip=4, minimum_run=2)
        self.assertEqual(report["matched_update_run"], 2)
        self.assertFalse(report["native_suffix_exhausted"])
        self.assertEqual(report["first_later_mismatch"]["native_update"], 9)
        self.assertEqual(report["first_later_mismatch"]["oracle_update"], 6)

    def test_clock_shift_precedes_later_semantic_mismatch(self):
        native = self.root / "native.jsonl"
        oracle = self.root / "oracle.jsonl"
        trace(native, [0, 1, 2, 2, 2, 2, 3, 4, 5, 99],
              [0, 1, 2, 3, 4, 5, 8, 9, 10, 11],
              clocks=[2, 4, 6, 8, 10, 12, 14, 16, 19, 22])
        trace(oracle, [0, 1, 2, 3, 4, 5, 6, 7],
              [0, 1, 2, 8, 9, 10, 11, 12], oracle=True)
        report = diagnose(native, oracle, 4, max_slip=4, minimum_run=2)
        self.assertEqual(report["first_later_mismatch"]["native_update"], 10)
        self.assertEqual(report["first_later_mismatch"]["native_vi_since_previous"], 3)
        self.assertEqual(report["first_later_mismatch"]["oracle_clock_since_previous"], 2)
        clock = report["paired_update_clock"]
        self.assertTrue(clock["metadata_complete"])
        self.assertEqual(clock["delta_mismatch_count"], 2)
        self.assertEqual(clock["first_delta_mismatch"], {
            "native_update": 9, "oracle_update": 6,
            "native_vi_since_previous": 3,
            "oracle_clock_since_previous": 2,
            "semantic_state_match": True})
        self.assertFalse(clock["last_delta_mismatches"][-1][
            "semantic_state_match"])

    def test_configured_vi_counter_takes_precedence_over_emulator_frames(self):
        native = self.root / "native.jsonl"
        oracle = self.root / "oracle.jsonl"
        trace(native, [0, 1, 2, 2, 2, 2, 3, 4, 5, 99],
              [0, 1, 2, 3, 4, 5, 8, 9, 10, 11],
              clocks=[2, 4, 6, 8, 10, 12, 14, 16, 19, 22])
        trace(oracle, [0, 1, 2, 3, 4, 5, 6, 7],
              [0, 1, 2, 8, 9, 10, 11, 12], oracle=True,
              clocks=[20, 40, 60, 80, 100, 120, 140, 160],
              consumed_vi=[2, 4, 6, 8, 10, 12, 14, 16])
        report = diagnose(native, oracle, 4, max_slip=4, minimum_run=2)
        self.assertEqual(report["paired_update_clock"]["units"],
                         "native-configured-VI-queue-vs-oracle-configured-VI-queue")
        self.assertEqual(report["paired_update_clock"]["delta_mismatch_count"], 2)
        self.assertEqual(report["first_later_mismatch"]["oracle_consumed_vi"], 14)


if __name__ == "__main__":
    unittest.main()
