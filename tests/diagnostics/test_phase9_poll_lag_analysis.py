import json
from pathlib import Path
import tempfile
import unittest

from scripts.compare_phase9_poll_hashes import HEADER, compare
from scripts.phase9_poll_lag_analysis import analyze
from scripts.phase95_bridge import digest


class PollLagAnalysisTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.native = self.root / "native" / "retrace-hashes.jsonl.polls.jsonl"
        self.oracle = self.root / "oracle" / "poll-hashes.jsonl"
        self.native.parent.mkdir()
        self.oracle.parent.mkdir()
        self.comparison = self.root / "comparison.json"
        replay = self.source / "controller.input"
        replay.write_text(
            "jfg-phase8-input-v2\n0,1,1,0000,0,0\n1,2,1,0000,0,0\n"
            "2,3,1,0000,0,0\n3,10,1,0000,0,0\n", encoding="ascii")
        flash = self.source / "initial.flash"
        pak = self.source / "initial.pak"
        flash.write_bytes(b"flash")
        pak.write_bytes(b"pak")
        self.manifest = self.source / "export-manifest.json"
        self.manifest.write_text(json.dumps({
            "kind": "jfg-phase95-selected-input-export", "schema": 1,
            "controller_polls": 4, "oracle_final_frame": 10,
            "input_sha256": digest(replay),
            "initial_state": {"flash_sha256": digest(flash),
                              "pak_sha256": digest(pak)},
        }), encoding="utf-8")

    @staticmethod
    def row(poll, side, mode):
        row = {"kind": "jfg-phase9-poll-hash", "schema": 1,
               "poll": poll, "connected": 1, "buttons": 0,
               "stick_x": 0, "stick_y": 0,
               "update_counter_valid": True, "completed_updates": poll,
               "front_mode": mode, "level_word": 47,
               "rng_seed": "0x00000001", "player_actor": "0x00000000",
               "player_sha256": None, "actor_list": "0x80001000",
               "actor_count": 0, "actor_table_sha256": "a" * 64,
               "globals_sha256": "b" * 64, "camera_sha256": "c" * 64,
               "actors": []}
        row["vi_retraces" if side == "native" else "emulator_frame"] = poll
        return row

    def prepare(self, native_modes=(0, 1, 2, 3), oracle_modes=(0, 0, 1, 2)):
        for path, side, modes in ((self.native, "native", native_modes),
                                  (self.oracle, "oracle", oracle_modes)):
            path.write_text("\n".join(json.dumps(item) for item in
                            [HEADER, *(self.row(i, side, mode)
                                       for i, mode in enumerate(modes))]) + "\n",
                            encoding="utf-8")
        (self.native.parent / "native-result.json").write_text(json.dumps({
            "kind": "jfg-phase95-native-selected-poll-replay", "exit_code": 0,
            "probe_target_reached": True, "poll_semantic_hashes": True,
            "poll_semantic_hash_trace_complete": True,
            "poll_semantic_hash_sha256": digest(self.native),
            "poll_semantic_hash_count": 4,
            "input_sha256": json.loads(self.manifest.read_text())["input_sha256"],
            "initial_flash_sha256": digest(self.source / "initial.flash"),
            "initial_pak_sha256": digest(self.source / "initial.pak"),
            "rom_sha256": "a" * 64, "executable_sha256": "b" * 64,
        }), encoding="utf-8")
        (self.oracle.parent / "oracle-result.json").write_text(json.dumps({
            "kind": "jfg-phase95-oracle-poll-replay", "exit_code": 0,
            "trace_complete": True, "poll_semantic_hashes": True,
            "poll_semantic_hash_trace_complete": True,
            "poll_semantic_hash_sha256": digest(self.oracle),
            "poll_semantic_hash_count": 4,
            "input_sha256": json.loads(self.manifest.read_text())["input_sha256"],
            "source_export_sha256": digest(self.manifest),
            "oracle_initial_flash_sha256": digest(self.source / "initial.flash"),
            "initial_flash_matches_candidate": True,
            "rom_sha256": "a" * 64, "emulator_sha256": "c" * 64,
        }), encoding="utf-8")
        self.comparison.write_text(json.dumps(compare(
            self.source, self.native, self.oracle)), encoding="utf-8")

    def test_reports_exact_shift_candidates_without_claiming_alignment(self):
        self.prepare()
        report = analyze(self.source, self.native, self.oracle,
                         self.comparison, radius=1)
        self.assertEqual(report["mismatching_polls"], 3)
        self.assertEqual(report["unique_shift_match"], 2)
        self.assertEqual(report["no_shift_match"], 1)
        self.assertEqual(report["unique_shift_offsets"], {"1": 2})
        self.assertEqual(report["first_unmatched_polls"], [3])
        self.assertFalse(report["alignment_validated"])
        self.assertFalse(report["parity_verified"])

    def test_rejects_tampered_report_or_input(self):
        self.prepare()
        report = json.loads(self.comparison.read_text())
        report["mismatching_polls"] = 2
        self.comparison.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            analyze(self.source, self.native, self.oracle, self.comparison)
        self.prepare()
        (self.source / "controller.input").write_text("changed", encoding="utf-8")
        with self.assertRaises(ValueError):
            analyze(self.source, self.native, self.oracle, self.comparison)

    def test_rejects_invalid_radius(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "radius"):
            analyze(self.source, self.native, self.oracle, self.comparison,
                    radius=0)


if __name__ == "__main__":
    unittest.main()
