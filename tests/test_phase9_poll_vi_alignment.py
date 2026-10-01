import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.phase95_bridge import digest
from scripts.phase9_poll_vi_alignment import (
    analyze, delta_windows, oracle_poll_vi_sequences,
)


class PollViAlignmentTests(unittest.TestCase):
    def test_oracle_event_order_maps_multiple_polls_to_last_vi(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "events.tsv"
            path.write_text(
                "vi-consumed\t30\tsequence\t1\n"
                "input-poll\t30\tindex\t0\tbuttons\t0000\tstick\t0,0\tmode\t0\tlevel\t0\trng\t1\n"
                "input-poll\t30\tindex\t1\tbuttons\t0000\tstick\t0,0\tmode\t0\tlevel\t0\trng\t1\n"
                "vi-consumed\t31\tsequence\t2\n"
                "input-poll\t31\tindex\t2\tbuttons\t0000\tstick\t0,0\tmode\t0\tlevel\t0\trng\t1\n",
                encoding="utf-8")
            self.assertEqual(oracle_poll_vi_sequences(path), ([1, 1, 2], 2))
            path.write_text("vi-consumed\t30\tsequence\t2\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing or reordered"):
                oracle_poll_vi_sequences(path)

    def test_delta_windows_preserve_dynamic_offsets(self):
        rows = [{"poll": index, "vi_delta": delta}
                for index, delta in enumerate((10, 10, 8, 8, 34))]
        self.assertEqual(delta_windows(rows), [
            {"first_poll": 0, "last_poll": 1, "polls": 2, "vi_delta": 10},
            {"first_poll": 2, "last_poll": 3, "polls": 2, "vi_delta": 8},
            {"first_poll": 4, "last_poll": 4, "polls": 1, "vi_delta": 34},
        ])

    def test_end_to_end_report_does_not_promote_poll_match_to_parity(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source, oracle, native = (root / name for name in ("source", "oracle", "native"))
            for path in (source, oracle, native):
                path.mkdir()
            (source / "controller.input").write_text(
                "jfg-phase8-input-v2\n0,1,1,0000,0,0\n1,100,1,8000,0,0\n",
                encoding="utf-8")
            input_sha = digest(source / "controller.input")
            (source / "export-manifest.json").write_text(json.dumps({
                "kind": "jfg-phase95-selected-input-export",
                "input_sha256": input_sha,
                "initial_state": {"flash_sha256": "a" * 64},
            }), encoding="utf-8")
            (oracle / "oracle-result.json").write_text(json.dumps({
                "kind": "jfg-phase95-oracle-poll-replay", "trace_complete": True,
                "vi_consumed_trace_complete": True, "vi_consumed_count": 2,
                "input_sha256": input_sha, "rom_sha256": "b" * 64,
                "oracle_initial_flash_sha256": "a" * 64,
                "initial_flash_matches_candidate": True,
            }), encoding="utf-8")
            (native / "native-result.json").write_text(json.dumps({
                "kind": "jfg-phase95-native-selected-poll-replay",
                "probe_target_reached": True, "input_sha256": input_sha,
                "rom_sha256": "b" * 64, "initial_flash_sha256": "a" * 64,
            }), encoding="utf-8")
            (oracle / "checkpoints.tsv").write_text(
                "vi-consumed\t30\tsequence\t1\n"
                "input-poll\t30\tindex\t0\tbuttons\t0000\tstick\t0,0\tmode\t0\tlevel\t0\trng\t1\n"
                "vi-consumed\t31\tsequence\t2\n"
                "input-poll\t31\tindex\t1\tbuttons\t8000\tstick\t0,0\tmode\t0\tlevel\t0\trng\t1\n",
                encoding="utf-8")
            (native / "controller-polls.tsv").write_text(
                "poll\tvi_retrace\tvi_frame\tfront_mode\tlevel_word\trng_seed\tbuttons\tx\ty\n"
                "0\t1\t1\t0\t0\t1\t0\t0\t0\n"
                "1\t2\t2\t2\t0\t1\t32768\t0\t0\n",
                encoding="utf-8")
            header = {"kind": "jfg-phase9-retrace-hash-header", "schema": 1}
            record = {"kind": "jfg-phase9-retrace-hash", "schema": 1,
                      "front_mode": 0, "actor_count": 0, "rng_seed": "0x00000001",
                      "player_actor": "0x00000000", "actor_list": "0x00000000",
                      "player_sha256": None, "actor_table_sha256": None,
                      "globals_sha256": "0" * 64, "camera_sha256": "1" * 64,
                      "actors": []}
            trace = (json.dumps(header) + "\n" +
                     json.dumps(dict(record, retrace=1)) + "\n" +
                     json.dumps(dict(record, retrace=2)) + "\n")
            (oracle / "consumed-vi-hashes.jsonl").write_text(trace, encoding="utf-8")
            (native / "retrace-hashes.jsonl").write_text(trace, encoding="utf-8")
            report = analyze(source, oracle, native, max_polls=2,
                             output=root / "report.json")
            self.assertIsNone(report["first_input_mismatch"])
            self.assertEqual(report["first_poll_state_mismatch"]["poll"], 1)
            self.assertEqual(report["prior_vi_hashes_equal_at_polls"], 2)
            self.assertFalse(report["alignment_validated"])
            self.assertIsNone(report["first_validated_gameplay_divergence"])


if __name__ == "__main__":
    unittest.main()
