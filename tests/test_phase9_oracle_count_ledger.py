import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import phase9_device_events as devices
from scripts import phase9_oracle_cpu_boundaries as boundaries
from scripts import phase9_oracle_count_ledger as ledger
from scripts.phase95_bridge import digest


class OracleCountLedgerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        count = dict.fromkeys(boundaries.COUNT, 0)
        count.update(kind="count", sequence=1, invocation=7, reason="lazy", pc=0x80001010,
                     anchor_before=0x80001000, anchor_after=0x80001010,
                     count_before=100, count_after=108, device_sequence=1)
        eret = dict.fromkeys(boundaries.ERET, 0)
        eret.update(kind="eret", sequence=2, invocation=7, pc=0x80001010, target_pc=0x80002000,
                    count_before=100, count_after=108, anchor_before=0x80001000,
                    anchor_after=0x80002000, status_before=0x34000003, status_after=0x34000001,
                    epc_before=0x80002000, epc_after=0x80002000, device_sequence=1,
                    r31=0xffffffff80004000)
        tail = {**count, "sequence": 3, "device_sequence": 2, "pc": 0x80002010,
                "anchor_before": 0x80002000, "anchor_after": 0x80002010,
                "count_before": 108, "count_after": 116}
        self.cpu = [count, eret, tail]
        self.device = []
        for seq, value in ((1, 100), (2, 108)):
            row = dict.fromkeys(devices.BASE + devices.REGISTERS, 0)
            row.update(sequence=seq, invocation=7, phase="instruction", source="none",
                       pc=0x80001000 + seq * 4, clock_raw=value)
            self.device.append(row)

    def write(self):
        lines = ["jfg-oracle-cpu-boundaries-v1\t7", "\t".join(("count-columns", *boundaries.COUNT)),
                 "\t".join(("eret-columns", *boundaries.ERET))]
        for row in self.cpu:
            fields = boundaries.COUNT if row["kind"] == "count" else boundaries.ERET
            values = [row["kind"]]
            for key in fields:
                width = 16 if key.startswith("r") and key[1:].isdigit() else 8
                values.append(str(row[key]) if key in ("sequence", "invocation", "device_sequence", "reason")
                              else f"0x{row[key]:0{width}x}")
            lines.append("\t".join(values))
        counts = [sum(row["kind"] == kind for row in self.cpu) for kind in ("count", "eret")]
        lines.append(f"result\ttrue\t{len(self.cpu)}\t{counts[0]}\t{counts[1]}")
        cpu_path, device_path = self.directory / "cpu-boundaries.tsv", self.directory / "device-events.tsv"
        cpu_path.write_text("\n".join(lines) + "\n", encoding="ascii")
        lines = ["jfg-phase9-device-events-v1\toracle-lazy-count\t6\t8", "\t".join(devices.BASE + devices.REGISTERS)]
        for row in self.device:
            lines.append("\t".join(str(row[key]) if key in ("sequence", "phase", "source", "invocation", "deadline_valid")
                                   else f"0x{row[key]:08x}" for key in devices.BASE + devices.REGISTERS))
        lines.append(f"result\ttrue\t{len(self.device)}")
        device_path.write_text("\n".join(lines) + "\n", encoding="ascii")
        device_spec = devices.specification(True, [0x80001004, 0x80001008], [7, 7], side="oracle", qualified_engine=True)
        cpu_spec = boundaries.specification(7, device_spec, 1)
        self.metadata = {"exit_code": 0, "trace_complete": True, "completed_update_trace_complete": True,
            "focused_update_capture_complete": True, "focused_update_range": [7, 7], "mupen_cpu_core_override": 1,
            "preferred_n64_core_override": None,
            "device_events": {**device_spec, **devices.summary(device_path, device_spec, side="oracle"), "sha256": digest(device_path)},
            "cpu_boundaries": {**cpu_spec, **boundaries.summary(cpu_path, cpu_spec), "sha256": digest(cpu_path)}}
        self.save_metadata()

    def save_metadata(self):
        (self.directory / "oracle-result.json").write_text(json.dumps(self.metadata))

    def measure(self, first=1, last=2):
        return ledger.measure(self.directory, first=first, last=last)

    def test_real_readers_join_by_sequence_and_do_not_double_charge_eret(self):
        self.write()
        report = self.measure()
        self.assertEqual(len(report["ledger"]["joined_devices"]), 2)
        self.assertEqual(report["ledger"]["cpu_events_after_last_device"], 1)
        self.assertEqual(report["ledger"]["final_logged_count"], 116)
        self.assertEqual(report["interval"]["cpu_events"], 2)
        self.assertEqual(report["interval"]["count_events"], 1)
        self.assertEqual(report["interval"]["eret_events"], 1)
        self.assertEqual(report["interval"]["net_count_change_u32"], 8)
        self.assertEqual(report["interval"]["mutations_by_reason"], {"lazy": {"events": 1, "modular_delta": 8}})
        self.assertFalse(report["interval"]["elapsed_or_retired_ticks_proved"])
        for flag in ledger.LIMITS:
            self.assertFalse(report[flag])
            self.assertFalse(report["ledger"][flag])

    def test_contradiction_is_not_shifted_to_a_matching_count(self):
        self.device[0]["clock_raw"] = 108  # Later matching value must not align this row.
        self.write()
        with self.assertRaisesRegex(ValueError, "contradiction at device sequence 1"):
            self.measure()

    def test_equal_sequence_means_mutation_after_not_before_device(self):
        for row in self.cpu[:2]:
            row["device_sequence"] = 0
        self.write()
        with self.assertRaisesRegex(ValueError, "contradiction"):
            self.measure()
        self.device[0]["clock_raw"] = 108
        self.write()
        report = self.measure()
        self.assertEqual(report["interval"]["count_events"], 0)
        self.assertEqual(report["interval"]["net_count_change_u32"], 0)
        self.assertEqual(report["ledger"]["joined_devices"][0]["count_rows"], 1)

    def test_after_window_mutation_and_missing_device_rows_are_rejected(self):
        self.cpu[-1]["device_sequence"] = 3
        self.write()
        with self.assertRaisesRegex(ValueError, "escaped"):
            self.measure()
        with self.assertRaisesRegex(ValueError, "ordering"):
            ledger.reconcile(self.cpu, [{**self.device[0], "sequence": 2}], 7)

    def test_write_or_reset_is_explicit_not_elapsed_work(self):
        write = {**self.cpu[0], "sequence": 3, "reason": "write", "count_before": 108,
                 "count_after": 3, "operand": 3, "anchor_after": self.cpu[0]["anchor_before"]}
        self.cpu[-1].update(sequence=4, count_before=3, count_after=11)
        self.cpu.insert(2, write)
        self.device[1]["clock_raw"] = 3
        self.write()
        report = self.measure()["interval"]
        self.assertEqual(report["count_events"], 2)
        self.assertEqual(report["net_count_change_u32"], (3 - 100) & ledger.MASK)
        self.assertTrue(report["contains_count_write_or_reset"])
        self.assertFalse(report["elapsed_or_retired_ticks_proved"])

    def test_unsigned_count_wrap_is_reconciled_without_clock_unwrapping(self):
        self.cpu[0].update(count_before=0xfffffffc, count_after=4)
        self.cpu[1].update(count_before=0xfffffffc, count_after=4)
        self.cpu[2].update(count_before=4, count_after=12)
        self.device[0]["clock_raw"], self.device[1]["clock_raw"] = 0xfffffffc, 4
        self.write()
        self.assertEqual(self.measure()["interval"]["net_count_change_u32"], 8)

    def test_missing_footer_is_rejected_even_with_refreshed_digest(self):
        self.write()
        path = self.directory / "cpu-boundaries.tsv"
        path.write_text("\n".join(path.read_text().splitlines()[:-1]) + "\n")
        self.metadata["cpu_boundaries"]["sha256"] = digest(path)
        self.save_metadata()
        with self.assertRaisesRegex(ValueError, "footer"):
            self.measure()

    def test_declared_completion_core_summary_and_claims_are_checked(self):
        self.write()
        original = copy.deepcopy(self.metadata)
        for field, value in (("exit_code", 1), ("trace_complete", False), ("mupen_cpu_core_override", 0)):
            with self.subTest(field=field):
                self.metadata = {**copy.deepcopy(original), field: value}
                self.save_metadata()
                with self.assertRaises(ValueError):
                    self.measure()
        for field, value in (("events", 999), ("clock_alignment_validated", True), ("sha256", "0" * 64)):
            with self.subTest(field=field):
                self.metadata = copy.deepcopy(original)
                self.metadata["cpu_boundaries"][field] = value
                self.save_metadata()
                with self.assertRaises(ValueError):
                    self.measure()

    def test_interval_must_use_existing_ordered_instruction_entries(self):
        self.write()
        for first, last in ((0, 2), (2, 1), (1, 1), (True, 2), (1, 3)):
            with self.subTest(first=first, last=last), self.assertRaises(ValueError):
                self.measure(first, last)
        self.device[1].update(phase="dispatch", source="vi")
        self.write()
        with self.assertRaisesRegex(ValueError, "instruction entries"):
            self.measure()

    def test_malformed_capture_declarations_fail_as_validation_errors(self):
        self.write()
        original = copy.deepcopy(self.metadata)
        for field, value in (("window", None), ("window", []), ("window", [True, 8]),
                             ("pcs", "0x80001004"), ("pcs", [0x80001005]), ("pcs", [0, 0])):
            with self.subTest(field=field, value=value):
                self.metadata = copy.deepcopy(original)
                self.metadata["device_events"][field] = value
                self.save_metadata()
                with self.assertRaisesRegex(ValueError, "malformed"):
                    self.measure()
        (self.directory / "oracle-result.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "not an object"):
            self.measure()

    def test_backing_bytes_are_rechecked_after_computation(self):
        self.write()
        original = ledger.interval

        def mutate(*args):
            report = original(*args)
            with (self.directory / "device-events.tsv").open("a") as stream:
                stream.write("tampered\n")
            return report

        with mock.patch.object(ledger, "interval", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "changed during"):
                self.measure()

    def test_empty_completed_cpu_trace_is_not_positive_ledger_evidence(self):
        self.cpu = []
        self.write()
        with self.assertRaisesRegex(ValueError, "nonempty"):
            self.measure()

    def test_compact_history_retains_values_and_limits_without_raw_trace_dump(self):
        from scripts.autonomy import state_word_experiment as words, point_anchors
        self.write()
        report = self.measure()
        observations = [{"update": 7, "device_events_reconciled": 2, "oracle_count_ledger": report["interval"]}]
        item = {"observation_id": "count", "source": {}, "input_prefix_match": True,
            "plan": {"operation": "oracle-count-ledger", "prediction": None},
            "observation": {"prediction_observation": None, "prediction_observed": None,
                            "observations": observations, "qualification": {"passed": True}}}
        projection = words.planner_history([item])[0]["measurements"]
        self.assertEqual(projection[0]["oracle_count_ledger"]["net_count_change_u32"], 8)
        self.assertNotIn("pc_mutation_counts", projection[0]["oracle_count_ledger"])
        self.assertNotIn("eret_boundaries", projection[0]["oracle_count_ledger"])
        self.assertFalse(projection[0]["clock_alignment_validated"])
        with mock.patch.object(point_anchors, "inventory", return_value={}):
            facts = point_anchors.history_inventory(None, [7, 7], {}, [item],
                {"qualification": {"passed": True}, "summaries": {}}, {})
        self.assertEqual(facts["prior_observations"][0]["measurements"], projection)


if __name__ == "__main__":
    unittest.main()
