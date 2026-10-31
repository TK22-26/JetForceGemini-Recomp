import json
from pathlib import Path
import tempfile
import unittest

from scripts.compare_phase9_poll_hashes import HEADER, compare, records
from scripts.phase95_bridge import digest


class PollHashComparisonTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        replay = self.source / "controller.input"
        replay.write_text("jfg-phase8-input-v2\n0,1,1,0000,0,0\n"
                          "1,2,1,8000,0,0\n2,10,1,0000,0,0\n",
                          encoding="ascii")
        (self.source / "export-manifest.json").write_text(json.dumps({
            "kind": "jfg-phase95-selected-input-export", "schema": 1,
            "controller_polls": 3, "oracle_final_frame": 10,
            "input_sha256": digest(replay),
        }), encoding="utf-8")
        self.native = self.root / "native.jsonl"
        self.oracle = self.root / "oracle.jsonl"

    @staticmethod
    def row(poll, side, *, mode=3, buttons=0):
        row = {"kind": "jfg-phase9-poll-hash", "schema": 1,
               "poll": poll, "connected": 1, "buttons": buttons,
               "stick_x": 0, "stick_y": 0,
               "update_counter_valid": True, "completed_updates": poll,
               "front_mode": mode, "level_word": 47,
               "rng_seed": "0x00000001", "player_actor": "0x00000000",
               "player_sha256": None, "actor_list": "0x80001000",
               "actor_count": 0, "actor_table_sha256": "a" * 64,
               "globals_sha256": "b" * 64, "camera_sha256": "c" * 64,
               "actors": []}
        row["vi_retraces" if side == "native" else "emulator_frame"] = poll + (
            10 if side == "native" else 40)
        return row

    @staticmethod
    def write(path, rows):
        path.write_text("\n".join(json.dumps(row) for row in [HEADER, *rows]) +
                        "\n", encoding="utf-8")

    def test_matches_semantics_despite_different_clocks_and_update_counts(self):
        native = [self.row(i, "native", buttons=0x8000 if i == 1 else 0)
                  for i in range(3)]
        oracle = [self.row(i, "oracle", buttons=0x8000 if i == 1 else 0)
                  for i in range(3)]
        oracle[2]["completed_updates"] = 1
        self.write(self.native, native)
        self.write(self.oracle, oracle)
        result = compare(self.source, self.native, self.oracle)
        self.assertTrue(result["semantic_prefix_match"])
        self.assertTrue(result["input_prefix_match"])
        self.assertEqual(result["first_clock_difference"]["poll"], 0)
        self.assertFalse(result["alignment_validated"])
        self.assertFalse(result["parity_verified"])

    def test_localizes_first_semantic_mismatch_and_checks_remaining_input(self):
        native = [self.row(i, "native", buttons=0x8000 if i == 1 else 0)
                  for i in range(3)]
        oracle = [self.row(i, "oracle", buttons=0x8000 if i == 1 else 0)
                  for i in range(3)]
        oracle[1]["front_mode"] = 24
        self.write(self.native, native)
        self.write(self.oracle, oracle)
        result = compare(self.source, self.native, self.oracle)
        self.assertFalse(result["semantic_prefix_match"])
        self.assertTrue(result["input_prefix_match"])
        self.assertEqual(result["first_semantic_mismatch"]["poll"], 1)
        self.assertEqual(result["first_semantic_mismatch"]["components"],
                         ["front_mode"])
        self.assertEqual(result["first_mismatch_windows"], [{
            "first_poll": 1, "last_poll": 1, "polls": 1,
            "reconvergence_poll": 2}])
        self.assertEqual(result["first_reconvergence_poll"], 2)
        oracle[2]["buttons"] = 0x1000
        self.write(self.oracle, oracle)
        result = compare(self.source, self.native, self.oracle)
        self.assertFalse(result["input_prefix_match"])
        self.assertEqual(result["first_input_mismatch"]["poll"], 2)

    def test_rejects_gaps_and_wrong_boundary(self):
        self.write(self.native, [self.row(1, "native")])
        with self.assertRaisesRegex(ValueError, "missing poll 0"):
            list(records(self.native, "native"))
        self.native.write_text(json.dumps({**HEADER, "boundary": "post-input"}) +
                               "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "header"):
            list(records(self.native, "native"))
        row = self.row(0, "native")
        row["update_counter_valid"] = False
        self.write(self.native, [row])
        with self.assertRaisesRegex(ValueError, "update-counter provenance"):
            list(records(self.native, "native"))

    def test_checks_pinned_producer_and_initial_state_artifacts(self):
        native = [self.row(i, "native", buttons=0x8000 if i == 1 else 0)
                  for i in range(3)]
        oracle = [self.row(i, "oracle", buttons=0x8000 if i == 1 else 0)
                  for i in range(3)]
        self.write(self.native, native)
        self.write(self.oracle, oracle)
        flash = self.source / "initial.flash"
        pak = self.source / "initial.pak"
        flash.write_bytes(b"flash")
        pak.write_bytes(b"pak")
        manifest_path = self.source / "export-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["initial_state"] = {"flash_sha256": digest(flash),
                                     "pak_sha256": digest(pak)}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        native_result = self.root / "native-result.json"
        oracle_result = self.root / "oracle-result.json"
        native_result.write_text(json.dumps({
            "kind": "jfg-phase95-native-selected-poll-replay", "exit_code": 0,
            "probe_target_reached": True, "poll_semantic_hashes": True,
            "poll_semantic_hash_trace_complete": True,
            "poll_semantic_hash_sha256": digest(self.native),
            "poll_semantic_hash_count": 3,
            "input_sha256": manifest["input_sha256"],
            "initial_flash_sha256": digest(flash),
            "initial_pak_sha256": digest(pak),
            "rom_sha256": "a" * 64, "executable_sha256": "b" * 64,
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "only one"):
            compare(self.source, self.native, self.oracle)
        oracle_result.write_text(json.dumps({
            "kind": "jfg-phase95-oracle-poll-replay", "exit_code": 0,
            "trace_complete": True, "poll_semantic_hashes": True,
            "poll_semantic_hash_trace_complete": True,
            "poll_semantic_hash_sha256": digest(self.oracle),
            "poll_semantic_hash_count": 3,
            "input_sha256": manifest["input_sha256"],
            "source_export_sha256": digest(manifest_path),
            "oracle_initial_flash_sha256": digest(flash),
            "initial_flash_matches_candidate": True,
            "rom_sha256": "a" * 64, "emulator_sha256": "c" * 64,
        }), encoding="utf-8")
        self.assertTrue(compare(self.source, self.native, self.oracle)[
            "producer_provenance"]["verified"])
        pak.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "initial-state pin"):
            compare(self.source, self.native, self.oracle)


if __name__ == "__main__":
    unittest.main()
