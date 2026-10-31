import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.compare_phase9_focus_rdram import RDRAM_BYTES
from scripts.compare_phase9_vi_boundary import compare


def state(kind, index, actor_sha, **clock):
    return {
        "kind": kind, "schema": 1,
        "update" if kind.endswith("update-hash") else "retrace": index,
        "front_mode": 0, "rng_seed": "0x00000000",
        "player_actor": "0x00000000", "player_sha256": None,
        "actor_list": "0x80000100", "actor_count": 1,
        "actor_table_sha256": "0" * 64,
        "globals_sha256": "1" * 64, "camera_sha256": "2" * 64,
        "actors": [{"index": 0, "address": "0x80001000", "sha256": actor_sha}],
        **clock,
    }


def trace(path, header_kind, records):
    path.write_text("\n".join(json.dumps(record) for record in (
        {"kind": header_kind, "schema": 1}, *records)) + "\n", encoding="utf-8")


class ViBoundaryComparisonTests(unittest.TestCase):
    def test_extra_vi_precedes_first_actor_mismatch(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            native, oracle, source = (root / name for name in
                                      ("native", "oracle", "source"))
            for directory in (native, oracle, source):
                directory.mkdir()
            input_path = source / "controller.input"
            input_path.write_text("jfg-phase8-input-v2\n0,4,1,0000,0,0\n",
                                  encoding="ascii")
            before = bytes(RDRAM_BYTES)
            n_after = bytearray(before)
            o_after = bytearray(before)
            n_after[0x1000 + 5], o_after[0x1000 + 5] = 1, 2
            n_after, o_after = bytes(n_after), bytes(o_after)
            sha = lambda data: hashlib.sha256(data[0x1000:0x1200]).hexdigest()
            before_hash, native_hash, oracle_hash = map(sha,
                                                         (before, n_after, o_after))
            for directory, after in ((native, n_after), (oracle, o_after)):
                (directory / "focus-update-2.rdram").write_bytes(before)
                (directory / "focus-update-3.rdram").write_bytes(after)
            common = {"source_export": str(source),
                      "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
                      "rom_sha256": "a" * 64,
                      "focused_update_range": [2, 3],
                      "focused_update_capture_complete": True}
            (native / "native-result.json").write_text(json.dumps({
                **common, "probe_target_reached": True,
                "initial_flash_sha256": "b" * 64}), encoding="utf-8")
            (oracle / "oracle-result.json").write_text(json.dumps({
                **common, "trace_complete": True,
                "oracle_initial_flash_sha256": "b" * 64}), encoding="utf-8")
            trace(native / "retrace-hashes.jsonl.updates.jsonl",
                  "jfg-phase9-update-hash-header", [
                      state("jfg-phase9-update-hash", 1, before_hash,
                            controller_polls=1, vi_retraces=2),
                      state("jfg-phase9-update-hash", 2, before_hash,
                            controller_polls=2, vi_retraces=4),
                      state("jfg-phase9-update-hash", 3, native_hash,
                            controller_polls=3, vi_retraces=7),
                  ])
            trace(oracle / "update-hashes.jsonl",
                  "jfg-phase9-update-hash-header", [
                      state("jfg-phase9-update-hash", 1, before_hash,
                            controller_polls=1, emulator_frame=20,
                            oracle_consumed_vi=10),
                      state("jfg-phase9-update-hash", 2, before_hash,
                            controller_polls=2, emulator_frame=22,
                            oracle_consumed_vi=12),
                      state("jfg-phase9-update-hash", 3, oracle_hash,
                            controller_polls=3, emulator_frame=24,
                            oracle_consumed_vi=14),
                  ])
            trace(native / "retrace-hashes.jsonl",
                  "jfg-phase9-retrace-hash-header", [
                      state("jfg-phase9-retrace-hash", index,
                            before_hash if index <= 4 else native_hash)
                      for index in range(1, 8)])
            trace(oracle / "consumed-vi-hashes.jsonl",
                  "jfg-phase9-retrace-hash-header", [
                      state("jfg-phase9-retrace-hash", index,
                            before_hash if index <= 12 else oracle_hash)
                      for index in range(1, 15)])
            report = compare(native, oracle, native_before=2, oracle_before=2,
                             native_after=3, oracle_after=3)
            self.assertIsNone(report["lead_in"]["first_relative_mismatch"])
            self.assertEqual(report["onset"]["first_relative_mismatch"][
                "relative_consumption"], 1)
            self.assertEqual(report["onset"]["extra_native_vi"], [7])
            self.assertFalse(report["alignment_validated"])
            self.assertFalse(report["parity_verified"])


if __name__ == "__main__":
    unittest.main()
