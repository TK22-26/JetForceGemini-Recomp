import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import compare_phase9_focus_rdram as focus
from scripts.compare_phase9_focus_rdram import (
    compare, _input_between, _record_at, _records_at, RDRAM_BYTES,
)
from scripts.build_phase9_route_replays import Event


def _record(index, data, *, consumed_vi=None):
    actor = data[0x1000:0x1200]
    record = {"kind": "jfg-phase9-update-hash", "schema": 1,
            "update": index, "front_mode": 0, "rng_seed": "0x00000000",
            "player_actor": "0x00000000", "player_sha256": None,
            "actor_list": "0x80000100", "actor_count": 1,
            "actor_table_sha256": "0" * 64, "globals_sha256": "1" * 64,
            "camera_sha256": "2" * 64,
            "actors": [{"index": 0, "address": "0x80001000",
                        "sha256": hashlib.sha256(actor).hexdigest()}],
            "controller_polls": index,
            "vi_retraces": index * 2}
    if consumed_vi is not None:
        record["oracle_consumed_vi"] = consumed_vi
    return record


class FocusRecordBatchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "updates.jsonl"
        self.rows = [{"kind":"jfg-phase9-update-hash-header","schema":1},
                     *(_record(index, bytes(RDRAM_BYTES)) for index in range(1, 6))]
        self.write()

    def write(self):
        self.path.write_text("\n".join(json.dumps(row) for row in self.rows)+"\n", encoding="utf-8")

    def test_one_prefix_scan_retains_only_requested_records(self):
        with patch.object(focus, "records", wraps=focus.records) as reader:
            selected = _records_at(self.path, [5, 3, 5])
        reader.assert_called_once_with(self.path)
        self.assertEqual(selected, {3:self.rows[3],5:self.rows[5]})
        self.assertEqual(_record_at(self.path, 3), selected[3])

    def test_intervening_record_is_still_validated(self):
        self.rows[2]["actors"][0]["sha256"] = "invalid"
        self.write()
        with self.assertRaises(ValueError):
            _records_at(self.path, [3, 5])

    def test_missing_requested_update_rejected(self):
        with self.assertRaisesRegex(ValueError, "update 6 is missing"):
            _records_at(self.path, [3, 6])

    def test_later_call_rereads_changed_evidence(self):
        self.assertEqual(_records_at(self.path, [3])[3]["controller_polls"], 3)
        self.rows[3]["controller_polls"] = 4
        self.write()
        self.assertEqual(_records_at(self.path, [3])[3]["controller_polls"], 4)

    def test_reader_stops_at_last_requested_update(self):
        self.rows[5] = {"invalid":"outside requested prefix"}
        self.write()
        self.assertEqual(_records_at(self.path, [3,4]), {3:self.rows[3],4:self.rows[4]})
        with self.assertRaises(ValueError):
            _records_at(self.path, [5])

    def test_invalid_requests_rejected_before_open(self):
        for updates in ([], [0], [-1], [True], [1.5]):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                _records_at(Path("missing-file"), updates)


class FocusRdramComparisonTests(unittest.TestCase):
    def test_controller_interval_distinguishes_values_and_gaps(self):
        events = [Event(0, 2, 1, 0, 0, 0),
                  Event(2, 3, 1, 0x8000, 0, 0)]
        self.assertEqual(_input_between(events, [0, 2],
                                        {"controller_polls": 1},
                                        {"controller_polls": 2})[0]["buttons"],
                         "0000")
        self.assertEqual(_input_between(events, [0, 2],
                                        {"controller_polls": 2},
                                        {"controller_polls": 3})[0]["buttons"],
                         "8000")
        with self.assertRaisesRegex(ValueError, "missing poll 3"):
            _input_between(events, [0, 2], {"controller_polls": 3},
                           {"controller_polls": 4})

    def test_actor_byte_onset_and_snapshot_integrity(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            native, oracle = root / "native", root / "oracle"
            native.mkdir()
            oracle.mkdir()
            source = root / "source"
            source.mkdir()
            input_path = source / "controller.input"
            input_path.write_text("jfg-phase8-input-v2\n0,3,1,0000,0,0\n",
                                  encoding="ascii")
            before = bytes(RDRAM_BYTES)
            after_native = bytearray(before)
            after_oracle = bytearray(before)
            after_native[0x1000 + 10] = 1
            after_oracle[0x1000 + 10] = 2
            header = {"kind": "jfg-phase9-update-hash-header", "schema": 1}
            for directory, name, after in ((native,
                                             "retrace-hashes.jsonl.updates.jsonl",
                                             bytes(after_native)),
                                            (oracle, "update-hashes.jsonl",
                                             bytes(after_oracle))):
                (directory / "focus-update-1.rdram").write_bytes(before)
                (directory / "focus-update-2.rdram").write_bytes(after)
                (directory / name).write_text("\n".join(json.dumps(item) for item in (
                    header, _record(1, before,
                                    consumed_vi=2 if directory == oracle else None),
                    _record(2, after,
                            consumed_vi=4 if directory == oracle else None))) + "\n",
                    encoding="utf-8")
            common = {"source_export": str(source),
                      "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
                      "rom_sha256": "b" * 64,
                      "focused_update_range": [1, 2],
                      "focused_update_capture_complete": True}
            (native / "native-result.json").write_text(json.dumps({
                **common, "probe_target_reached": True,
                "initial_flash_sha256": "c" * 64}), encoding="utf-8")
            (oracle / "oracle-result.json").write_text(json.dumps({
                **common, "trace_complete": True,
                "oracle_initial_flash_sha256": "c" * 64}), encoding="utf-8")
            report = compare(native, oracle, native_before=1, oracle_before=1,
                             native_after=2, oracle_after=2)
            self.assertTrue(report["before"]["semantic_state_match"])
            self.assertEqual(report["before"]["actor_byte_differences"], [])
            self.assertFalse(report["after"]["semantic_state_match"])
            self.assertTrue(report["controller_inputs_between"]["same_values"])
            self.assertTrue(report["vi_consumption_between"]["same_count"])
            self.assertEqual(report["controller_inputs_between"]["native"], [{
                "poll": 1, "connected": 1, "buttons": "0000",
                "stick_x": 0, "stick_y": 0}])
            self.assertEqual(report["after"]["actor_byte_differences"][0][
                "first_offsets"], [10])
            self.assertFalse(report["parity_verified"])
            (native / "focus-update-2.rdram").write_bytes(before)
            with self.assertRaisesRegex(ValueError, "do not match update trace"):
                compare(native, oracle, native_before=1, oracle_before=1,
                        native_after=2, oracle_after=2)


if __name__ == "__main__":
    unittest.main()
