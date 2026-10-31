import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import phase9_poll_semantic_pair as pair
from scripts.compare_phase9_poll_hashes import HEADER
from scripts.phase95_bridge import digest, runtime_digest
from scripts.prepare_phase9_oracle_flash import SAVERAM_SIZE


class PollSemanticPairTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.private = self.root / "private"
        self.private.mkdir()
        self.output = self.private / "pair"
        self.source = self.root / "source"
        self.source.mkdir()
        replay = self.source / "controller.input"
        replay.write_text("jfg-phase8-input-v2\n0,1,1,0000,0,0\n"
                          "1,10,1,8000,0,0\n", encoding="ascii")
        flash = self.source / "initial.flash"
        pak = self.source / "initial.pak"
        flash.write_bytes(b"flash")
        pak.write_bytes(b"pak")
        (self.source / "export-manifest.json").write_text(json.dumps({
            "kind": "jfg-phase95-selected-input-export", "schema": 1,
            "oracle_final_frame": 10, "controller_polls": 2,
            "input_sha256": digest(replay),
            "initial_state": {"flash_sha256": digest(flash),
                              "pak_sha256": digest(pak)},
        }), encoding="utf-8")
        self.native_exe = self.root / "native.exe"
        emulator_dir = self.root / "emulator"
        emulator_dir.mkdir()
        self.emulator = emulator_dir / "EmuHawk.exe"
        self.rom = self.root / "game.z64"
        for path in (self.native_exe, self.emulator, self.rom):
            path.write_bytes(path.name.encode("ascii"))
        self.rom_sha = digest(self.rom)

    @staticmethod
    def rows(side):
        return [{"kind": "jfg-phase9-poll-hash", "schema": 1,
                 "poll": index, "connected": 1,
                 "buttons": 0x8000 if index else 0,
                 "stick_x": 0, "stick_y": 0,
                 "update_counter_valid": True, "completed_updates": index,
                 "front_mode": 3, "level_word": 47,
                 "rng_seed": "0x00000001", "player_actor": "0x00000000",
                 "player_sha256": None, "actor_list": "0x80001000",
                 "actor_count": 0, "actor_table_sha256": "a" * 64,
                 "globals_sha256": "b" * 64, "camera_sha256": "c" * 64,
                 "actors": [],
                 "vi_retraces" if side == "native" else "emulator_frame":
                     index + (10 if side == "native" else 40)}
                for index in range(2)]

    def _write_side(self, side, output):
        output.mkdir()
        trace = output / ("retrace-hashes.jsonl.polls.jsonl"
                          if side == "native" else "poll-hashes.jsonl")
        trace.write_text("\n".join(json.dumps(row) for row in
                                   [HEADER, *self.rows(side)]) + "\n",
                         encoding="utf-8")
        manifest = json.loads((self.source / "export-manifest.json").read_text())
        common = {"source_export": str(self.source.resolve()),
                  "rom_sha256": self.rom_sha,
                  "input_sha256": manifest["input_sha256"],
                  "poll_semantic_hashes": True,
                  "completed_update_trace": True,
                  "poll_semantic_hash_trace_complete": True,
                  "poll_semantic_hash_sha256": digest(trace),
                  "poll_semantic_hash_count": 2, "exit_code": 0}
        if side == "native":
            result = {**common,
                      "kind": "jfg-phase95-native-selected-poll-replay",
                      "target_retraces": 5, "probe_target_reached": True,
                      "executable_sha256": digest(self.native_exe),
                      "initial_flash_sha256": manifest["initial_state"]["flash_sha256"],
                      "initial_pak_sha256": manifest["initial_state"]["pak_sha256"]}
            name = "native-result.json"
        else:
            saveram = output / "emulator" / "N64" / "SaveRAM" / "game.SaveRAM"
            saveram.parent.mkdir(parents=True)
            saveram.write_bytes(bytes(SAVERAM_SIZE))
            result = {**common,
                      "kind": "jfg-phase95-oracle-poll-replay",
                      "target_frame": 5, "trace_complete": True,
                      "emulator_sha256": digest(self.emulator),
                      "runtime_sha256": runtime_digest(self.emulator.parent),
                      "source_export_sha256": digest(self.source / "export-manifest.json"),
                      "oracle_initial_flash_sha256":
                          manifest["initial_state"]["flash_sha256"],
                      "initial_flash_matches_candidate": True,
                      "domain_inventory": True,
                      "memory_domains": [{"name": "FlashRAM", "size": 131072}],
                      "mupen_saveram_regions": {
                          "kind": "jfg-phase9-mupen-saveram-regions",
                          "image_sha256": digest(saveram),
                          "native_pak_equivalence_validated": False}}
            name = "oracle-result.json"
        (output / name).write_text(json.dumps(result), encoding="utf-8")
        return result

    def test_one_command_and_completed_side_resume(self):
        with patch.object(pair, "PRIVATE_ROOT", self.private), \
                patch.object(pair.phase95_native_replay, "replay",
                             side_effect=lambda source, output, *_args, **_kwargs:
                             self._write_side("native", output)) as native, \
                patch.object(pair.phase95_oracle_replay, "replay",
                             side_effect=lambda output, *_args, **_kwargs:
                             self._write_side("oracle", output)) as oracle:
            first = pair.run(self.output, self.source, self.native_exe,
                             self.emulator, self.rom, self.rom_sha,
                             target=5, timeout=60)
            second = pair.run(self.output, self.source, self.native_exe,
                              self.emulator, self.rom, self.rom_sha,
                              target=5, timeout=60)
        self.assertEqual(first, second)
        self.assertTrue(first["complete"])
        self.assertFalse(first["parity_verified"])
        self.assertEqual(first["shared_polls"], 2)
        self.assertEqual(native.call_count, 1)
        self.assertEqual(oracle.call_count, 1)
        self.assertTrue(oracle.call_args.kwargs["domain_inventory"])
        saveram = (self.output / "oracle" / "emulator" / "N64" /
                   "SaveRAM" / "game.SaveRAM")
        saveram.write_bytes(b"changed")
        with patch.object(pair, "PRIVATE_ROOT", self.private), \
                self.assertRaisesRegex(ValueError, "existing oracle capture"):
            pair.run(self.output, self.source, self.native_exe,
                     self.emulator, self.rom, self.rom_sha,
                     target=5, timeout=60)

    def test_interrupted_side_is_preserved(self):
        with patch.object(pair, "PRIVATE_ROOT", self.private):
            plan = pair._plan(self.source.resolve(), self.native_exe.resolve(),
                              self.emulator.resolve(), self.rom.resolve(),
                              self.rom_sha, 5, 60)
            self.output.mkdir()
            pair.write_json_atomic(self.output / "plan.json", plan)
            (self.output / "native").mkdir()
            with self.assertRaisesRegex(ValueError, "interrupted native"):
                pair.run(self.output, self.source, self.native_exe,
                         self.emulator, self.rom, self.rom_sha,
                         target=5, timeout=60)
            self.assertTrue((self.output / "native").is_dir())


if __name__ == "__main__":
    unittest.main()
