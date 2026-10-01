import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase95_poll_compare import (compare, discordance_windows,
                                          oracle_polls, transition_order)


class PollCompareTests(unittest.TestCase):
    def test_transition_order_ignores_duplicate_poll_samples_without_claiming_alignment(self):
        oracle = [{"poll": i, "frame": i * 2, "mode": 0, "level": 4,
                   "rng": rng} for i, rng in enumerate((10, 10, 20, 20, 30))]
        native = [{"poll": i, "vi_retrace": i * 3, "front_mode": 0,
                   "level_word": 4, "rng_seed": rng}
                  for i, rng in enumerate((10, 20, 20, 30, 30))]
        equal = transition_order(oracle, native)
        self.assertIsNone(equal["first_unmatched_ordinal"])
        self.assertFalse(equal["alignment_validated"])
        native[3]["rng_seed"] = 31
        native[4]["rng_seed"] = 31
        different = transition_order(oracle, native)
        self.assertEqual(different["first_unmatched_ordinal"]["ordinal"], 2)
        self.assertEqual(different["first_unmatched_ordinal"]["oracle"]["poll"], 4)
        self.assertEqual(different["first_unmatched_ordinal"]["native"]["poll"], 3)
        self.assertIsNone(different["nearby_exact_match_within_32_transitions"])

    def test_discordance_windows_separate_transient_and_sustained_differences(self):
        oracle = [{"frame": i * 2, "mode": 0, "level": 4, "rng": i}
                  for i in range(6)]
        native = [{"vi_retrace": i * 2 + 3, "front_mode": value,
                   "level_word": 4, "rng_seed": i}
                  for i, value in enumerate((0, 2, 0, 2, 2, 2))]
        summary = discordance_windows(oracle, native)
        self.assertEqual(summary["mode"]["mismatching_polls"], 4)
        self.assertEqual(summary["mode"]["windows"], 2)
        self.assertEqual(summary["mode"]["longest_window_polls"], 3)
        self.assertEqual(summary["mode"]["first_windows"][0]["first_poll"], 1)
        self.assertEqual(summary["mode"]["first_windows"][1]["last_poll"], 5)
        self.assertEqual(summary["level"]["windows"], 0)

    def test_rejects_oracle_trace_without_state_fields(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoints.tsv"
            path.write_text("input-poll\t40\tindex\t0\tbuttons\t0000\tstick\t0,0\n")
            with self.assertRaisesRegex(ValueError, "required state fields"):
                oracle_polls(path)

    def test_reports_observed_difference_without_claiming_common_boundary(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, oracle, native = (root / name for name in ("source", "oracle", "native"))
            for path in (source, oracle, native):
                path.mkdir()
            replay = "jfg-phase8-input-v2\n0,1,1,0000,0,0\n1,100,1,8000,0,0\n"
            (source / "controller.input").write_text(replay)
            (source / "initial.flash").write_bytes(b"flash")
            (source / "initial.pak").write_bytes(b"pak")
            sha = hashlib.sha256((source / "controller.input").read_bytes()).hexdigest()
            flash = hashlib.sha256((source / "initial.flash").read_bytes()).hexdigest()
            pak = hashlib.sha256((source / "initial.pak").read_bytes()).hexdigest()
            (source / "export-manifest.json").write_text(json.dumps({
                "input_sha256": sha, "controller_polls": 2, "oracle_final_frame": 100,
                "initial_state": {"flash_sha256": flash, "pak_sha256": pak}}))
            (oracle / "oracle-result.json").write_text(json.dumps({
                "input_sha256": sha, "trace_complete": True,
                "initial_flash_matches_candidate": True,
                "oracle_initial_flash_sha256": flash}))
            (native / "native-result.json").write_text(json.dumps({
                "input_sha256": sha, "probe_target_reached": True,
                "initial_flash_sha256": flash, "initial_pak_sha256": pak}))
            (oracle / "checkpoints.tsv").write_text(
                "input-poll\t40\tindex\t0\tbuttons\t0000\tstick\t0,0\tmode\t0\tlevel\t0\trng\t10\n"
                "input-poll\t72\tindex\t1\tbuttons\t8000\tstick\t0,0\tmode\t0\tlevel\t0\trng\t11\n")
            (native / "controller-polls.tsv").write_text(
                "poll\tvi_retrace\tvi_frame\tfront_mode\tlevel_word\trng_seed\tbuttons\tx\ty\n"
                "0\t0\t0\t0\t0\t10\t0\t0\t0\n"
                "1\t35\t35\t2\t0\t12\t32768\t0\t0\n")
            result = compare(source, oracle, native, root / "result.json")
            self.assertIsNone(result["first_input_mismatch"])
            self.assertEqual(result["first_schedule_mismatch"]["poll"], 0)
            self.assertEqual(result["first_observed_state_mismatch"]["poll"], 1)
            self.assertEqual(result["observed_transition_order"][
                "first_unmatched_ordinal"]["ordinal"], 1)
            self.assertIsNone(result["first_validated_gameplay_divergence"])
            self.assertFalse(result["native_parity_verified"])
            prefix = compare(source, oracle, native, root / "prefix.json",
                             prefix_polls=1)
            self.assertEqual(prefix["scope"], "prefix")
            self.assertEqual(prefix["shared_prefix_polls"], 1)
            self.assertIsNone(prefix["first_observed_state_mismatch"])
            self.assertTrue(prefix["initial_state"]["flash_matches_both"])
            self.assertEqual(prefix["initial_state"]["oracle_pak_equivalence"],
                             "not_verified")
            with self.assertRaisesRegex(ValueError, "invalid requested"):
                compare(source, oracle, native, root / "bad.json", prefix_polls=3)


if __name__ == "__main__":
    unittest.main()
