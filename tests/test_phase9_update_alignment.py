import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.phase9_update_alignment import analyze


class UpdateAlignmentTests(unittest.TestCase):
    def test_separates_poll_clock_drift_from_first_state_difference(self):
        native = [
            {"value": "a", "controller_polls": 3, "vi_retraces": 5},
            {"value": "b", "controller_polls": 4, "vi_retraces": 7},
            {"value": "c", "controller_polls": 5, "vi_retraces": 9},
        ]
        oracle = [
            {"value": "a", "controller_polls": 5,
             "oracle_consumed_vi": 6, "emulator_frame": 6},
            {"value": "b", "controller_polls": 6,
             "oracle_consumed_vi": 8, "emulator_frame": 8},
            {"value": "d", "controller_polls": 7,
             "oracle_consumed_vi": 10, "emulator_frame": 10},
        ]
        with tempfile.TemporaryDirectory() as directory:
            left, right = Path(directory) / "native", Path(directory) / "oracle"
            left.write_bytes(b"native")
            right.write_bytes(b"oracle")
            with patch("scripts.phase9_update_alignment.records",
                       side_effect=[(row for row in native),
                                    (row for row in oracle)]), \
                 patch("scripts.phase9_update_alignment.semantic_digest",
                       side_effect=lambda row: row["value"]), \
                 patch("scripts.phase9_update_alignment.describe_difference",
                       return_value=(["rng_seed"], [{"index": 2}])):
                report = analyze(left, right)
        self.assertEqual(report["matching_update_prefix"], 2)
        self.assertEqual(report["first_poll_clock_difference"], {
            "update": 1, "native_polls": 3, "oracle_polls": 5})
        self.assertEqual(report["first_semantic_difference"], {
            "update": 3, "reason": "state-difference",
            "components": ["rng_seed"], "actor_indices": [2],
            "native_clock": {"controller_polls": 5, "vi_retraces": 9},
            "oracle_clock": {"controller_polls": 7,
                             "oracle_consumed_vi": 10, "emulator_frame": 10},
        })
        self.assertFalse(report["alignment_validated"])
        self.assertFalse(report["parity_verified"])

    def test_missing_update_is_not_reported_as_parity(self):
        with tempfile.TemporaryDirectory() as directory:
            left, right = Path(directory) / "native", Path(directory) / "oracle"
            left.write_bytes(b"native")
            right.write_bytes(b"oracle")
            with patch("scripts.phase9_update_alignment.records",
                       side_effect=[(row for row in [{"value": "a"}]),
                                    (row for row in [{"value": "a"},
                                                     {"value": "b"}])]), \
                 patch("scripts.phase9_update_alignment.semantic_digest",
                       side_effect=lambda row: row["value"]):
                report = analyze(left, right)
        self.assertEqual(report["matching_update_prefix"], 1)
        self.assertEqual(report["first_semantic_difference"]["reason"],
                         "missing-update")
        self.assertEqual(report["first_semantic_difference"]["missing"],
                         "native")


if __name__ == "__main__":
    unittest.main()
