import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import compare_phase9_point_pacing as pacing
from scripts.compare_phase9_point_pacing import summarize
from scripts.phase95_bridge import digest


class PacingObservationTests(unittest.TestCase):
    def fixture(self, successful=2, oracle=False):
        rows = []
        def row(pc, **updates):
            item = {"pc": pc, "r29_lo": 0x800f8fb8, "r31_lo": 0x800457bc, "r2_lo": 0, "r16_lo": 1,
                    "r1_lo": 0, "r3_lo": 3, "r4_lo": 0x800feb80, "r5_lo": 0, "r6_lo": 0,
                    "r14_lo": 0, "r24_lo": 3, "r25_lo": 3, "m800a9e90": 0x800f92a0,
                    "m800feb88": 0, "m800feb8c": 0, "m800feca8": 0x01000000,
                    "m800fecac": 0x03000000, "m800feccc": 0, "controller_polls": 1918,
                    "completed_updates" if oracle else "update_candidate": 1907 if oracle else 1908}
            item.update(updates)
            rows.append(item)
        row(0x80054fbc, r29_lo=0x800f8fe8, r4_lo=0, m800feb88=successful)
        for i in range(successful + 1):
            pc = 0x80055034 if i == 0 else 0x8005505c
            row(0x80096910, r31_lo=pc, m800feb88=successful-i, r16_lo=i+1)
            row(pc, r31_lo=pc, r2_lo=0 if i < successful else 0xffffffff, r16_lo=i+1)
        for pc in (0x80055074, 0x800550f8, 0x80055110):
            row(pc, r16_lo=successful+1)
        row(0x80055144, r3_lo=successful+1)
        row(0x80096910, r31_lo=0x8005515c, r6_lo=1, r16_lo=successful+1)
        row(0x8005515c, r31_lo=0x8005515c, r16_lo=successful+1)
        row(0x800457bc, r29_lo=0x800f8fe8, r2_lo=successful+1)
        return rows

    def test_extra_receive_changes_count_not_final_wait(self):
        for count in (2, 3):
            for oracle in (False, True):
                report = summarize(self.fixture(count, oracle), oracle=oracle, window=(1908,1908))[0]
                self.assertEqual(report["return_v0"], count+1)
                self.assertEqual(report["counted_receives"], count)
                self.assertEqual(report["receives"][-1]["kind"], "final-wait-not-counted")

    def test_thread_stack_caller_or_mode_mismatch_rejected(self):
        base = self.fixture()
        for index, field, value in ((0,"r31_lo",0), (-1,"m800a9e90",0), (-1,"r29_lo",0),
                                     (1,"r31_lo",0), (1,"r6_lo",1), (1,"r5_lo",8), (2,"r29_lo",0)):
            rows = copy.deepcopy(base)
            rows[index][field] = value
            with self.subTest(index=index, field=field), self.assertRaises(ValueError):
                summarize(rows, oracle=False, window=(1908,1908))

    def test_missing_duplicate_and_unmatched_events_are_not_qualified(self):
        base = self.fixture()
        bad = [base[1:], base[:-1], [base[0]] + base, base[:2] + base[3:],
               [row for row in base if row["pc"] != 0x80055144],
               [row for row in base if row["pc"] != 0x80055110],
               [row for row in base if row["pc"] != 0x8005515c]]
        for rows in bad:
            with self.assertRaises(ValueError):
                summarize(rows, oracle=False, window=(1908,1908))

    def test_counter_and_return_inconsistency_rejected(self):
        for index, key in ((2,"r16_lo"), (-1,"r2_lo")):
            rows = self.fixture()
            rows[index][key] += 1
            with self.assertRaises(ValueError):
                summarize(rows, oracle=False, window=(1908,1908))

    def test_other_thread_events_cannot_satisfy_missing_calls(self):
        rows = self.fixture()
        rows[1]["m800a9e90"] = 0x800f0000
        with self.assertRaises(ValueError):
            summarize(rows, oracle=False, window=(1908,1908))

    def comparison(self, mutation=None, *, expected_record_reads=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dirs = [root / name for name in ("native", "oracle", "reference_native", "reference_oracle")]
            image = bytearray(4*1024*1024)
            image[0x457b4:0x457bc] = bytes.fromhex("0c0153ef00000000")
            for side, directory in enumerate(dirs):
                directory.mkdir()
                (directory / "point-probe.tsv").write_text("point trace\n")
                (directory / pacing.TRACE["native" if side % 2 == 0 else "oracle"]).write_text("trace\n")
                meta = {key: "pin" for key in ("source_export", "input_sha256", "rom_sha256", "execution_profile",
                        "initial_flash_sha256", "initial_pak_sha256", "emulator_sha256", "config_sha256",
                        "runtime_sha256", "oracle_initial_flash_sha256")}
                meta.update(exit_code=0, target_retraces=4800, target_frame=7200, observed_controller_polls=1984,
                            probe_target_reached=True, trace_complete=True, focused_update_capture_complete=True,
                            completed_update_trace_complete=True, focused_update_range=[1908,1908],
                            point_probe={"pcs": list(pacing.PCS), "words": list(pacing.WORDS),
                                         "phase": pacing.probe.PHASE, "complete": True,
                                         "sha256": digest(directory / "point-probe.tsv")})
                path = directory / ("native-result.json" if side % 2 == 0 else "oracle-result.json")
                path.write_text(json.dumps(meta))
            if mutation in ("pin", "failed-replay"):
                path = dirs[0] / "native-result.json"
                meta = json.loads(path.read_text())
                meta["input_sha256" if mutation == "pin" else "probe_target_reached"] = "changed" if mutation == "pin" else False
                path.write_text(json.dumps(meta))
            if mutation == "trace":
                (dirs[0] / pacing.TRACE["native"]).write_text("different trace\n")
            def snapshot(directory, record):
                data = bytes(image)
                if mutation == "snapshot" and directory == dirs[0]:
                    data = b"X" + data[1:]
                if mutation in ("trace-during-snapshot", "control-during-snapshot") and directory == dirs[0]:
                    target = dirs[0 if mutation == "trace-during-snapshot" else 2]
                    (target / pacing.TRACE["native"]).write_text("changed during measurement\n")
                return data, {}
            def read(path, *args, oracle):
                rows = self.fixture(oracle=oracle)
                for row in rows:
                    row["opcode"] = 0
                if mutation == "opcode":
                    rows[0]["opcode"] = 1
                return rows
            def polls(source, oracle, native, output, **kwargs):
                result = {"shared_prefix_polls": 1984, "first_input_mismatch": {} if mutation == "input" else None,
                          "initial_state": {"oracle_pak_equivalence": "not_verified"}}
                output.write_text(json.dumps(result))
                if mutation == "trace-during-polls":
                    (dirs[0] / pacing.TRACE["native"]).write_text("changed after snapshot checks\n")
                return result
            with patch.object(pacing, "_snapshot", side_effect=snapshot), patch.object(pacing, "_records_at", return_value={1908:{}}) as records, \
                    patch.object(pacing.probe, "read", side_effect=read), patch.object(pacing, "compare_polls", side_effect=polls):
                result = pacing.compare(*dirs, input_report_path=root / "polls.json", window=(1908,1908))
                if expected_record_reads is not None:
                    self.assertEqual(records.call_count, expected_record_reads)
                return result

    def test_identical_traces_parsed_once_per_side_and_never_cached_across_calls(self):
        first = self.comparison(expected_record_reads=2)
        self.assertEqual(self.comparison(expected_record_reads=2), first)

    def test_different_control_is_still_independently_parsed(self):
        result = self.comparison("trace", expected_record_reads=3)
        self.assertIn("native-full-update-trace-changed", result["qualification"]["reasons"])

    def test_trace_changes_during_snapshot_or_input_checks_are_rejected(self):
        for mutation in ("trace-during-snapshot", "control-during-snapshot", "trace-during-polls"):
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, "trace changed during"):
                self.comparison(mutation)

    def test_comparison_qualifies_only_local_observation(self):
        result = self.comparison()
        self.assertTrue(result["qualification"]["passed"])
        for key in ("alignment_validated", "causal_fix_proved", "parity_verified"):
            self.assertFalse(result[key])

    def test_changed_state_trace_or_inputs_are_inconclusive(self):
        for mutation in ("snapshot", "trace", "input"):
            with self.subTest(mutation=mutation):
                self.assertFalse(self.comparison(mutation)["qualification"]["passed"])

    def test_changed_pins_opcodes_and_failed_capture_are_rejected(self):
        for mutation in ("pin", "opcode", "failed-replay"):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.comparison(mutation)


if __name__ == "__main__":
    unittest.main()
