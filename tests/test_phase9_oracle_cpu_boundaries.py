from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import phase9_oracle_cpu_boundaries as probe


class OracleCpuBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "cpu.tsv"
        self.count = {key: 0 for key in probe.COUNT}
        self.count.update(sequence=1, invocation=7, reason="lazy", pc=0x80001010,
                          anchor_before=0x80001000, anchor_after=0x80001010,
                          count_before=100, count_after=108, status=0x34000003)
        self.eret = {key: 0 for key in probe.ERET}
        self.eret.update(sequence=2, invocation=7, pc=0x80001010, target_pc=0x80002000,
                         count_before=100, count_after=108, anchor_before=0x80001000,
                         anchor_after=0x80002000, status_before=0x34000003, status_after=0x34000001,
                         epc_before=0x80002000, epc_after=0x80002000, llbit_before=1,
                         thread_word_before=0x80003000, thread_word_after=0x80003000,
                         r31=0xffffffff80004000)

    def write(self, rows=None):
        rows = [("count", self.count), ("eret", self.eret)] if rows is None else rows
        lines = ["jfg-oracle-cpu-boundaries-v1\t7", "\t".join(("count-columns", *probe.COUNT)),
                 "\t".join(("eret-columns", *probe.ERET))]
        for kind, row in rows:
            values = [kind]
            for key in (probe.COUNT if kind == "count" else probe.ERET):
                value = row[key]
                if key in ("sequence", "invocation", "device_sequence", "reason"):
                    values.append(str(value))
                else:
                    width = 16 if key.startswith("r") and key[1:].isdigit() else 8
                    values.append(f"0x{value:0{width}x}")
            lines.append("\t".join(values))
        lines.append(f"result\ttrue\t{len(rows)}\t{sum(k=='count' for k,_ in rows)}\t{sum(k=='eret' for k,_ in rows)}")
        self.path.write_text("\n".join(lines) + "\n", encoding="ascii")

    def test_bounded_explicit_cached_core_and_environment_isolation(self):
        device = {"clock_basis": "oracle-lazy-count", "window": [6, 9]}
        for update, core, spec in ((True, 1, device), (0, 1, device), (10, 1, device),
                                   (7, 0, device), (7, True, device), (7, 1, None)):
            with self.subTest(update=update, core=core), self.assertRaises(ValueError):
                probe.specification(update, spec, core)
        spec = probe.specification(7, device, 1)
        environment = {"PATH": "kept", "JFG_PHASE9_CPU_BOUNDARY_UPDATE": "999"}
        probe.configure(environment, None)
        self.assertEqual(environment, {"PATH": "kept"})
        probe.configure(environment, spec)
        self.assertEqual(environment["JFG_PHASE9_CPU_BOUNDARY_UPDATE"], "7")

    def test_records_retained_without_retirement_or_alignment_claims(self):
        self.write()
        result = probe.read(self.path, 7)
        self.assertEqual(result["rows"][1]["r31"], 0xffffffff80004000)
        for flag in ("clock_alignment_validated", "retirement_validated", "causal_fix_proved", "parity_verified"):
            self.assertFalse(result[flag])
        summary = probe.summary(self.path, {"update": 7})
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["count_reasons"], {"lazy": 1})
        self.assertEqual(summary["eret_events"], 1)

    def test_unsigned_pc_and_count_wrap(self):
        self.write([("count", {**self.count, "pc": 8, "anchor_before": 0xfffffffc,
                               "anchor_after": 8, "count_before": 0xfffffffc, "count_after": 2})])
        self.assertEqual(probe.read(self.path, 7)["rows"][0]["count_after"], 2)

    def test_count_arithmetic_operands_and_order_rejected(self):
        for key, value in (("count_after", 109), ("anchor_after", 0x80001000), ("reason", "invented"),
                           ("operand", 1), ("sequence", 2), ("invocation", 8), ("pc", 0x80001011)):
            with self.subTest(key=key):
                self.write([("count", {**self.count, key: value})])
                with self.assertRaises(ValueError): probe.read(self.path, 7)
        for reason, operand in (("idle", 3), ("compare-up", 3), ("compare-down", 3),
                                 ("hard-reset", 7), ("nmi-reset", 7)):
            self.write([("count", {**self.count, "reason": reason, "operand": operand})])
            with self.assertRaises(ValueError): probe.read(self.path, 7)

    def test_unaccounted_count_or_device_reversal_rejected(self):
        second = {**self.count, "sequence": 2, "count_before": 109, "count_after": 117}
        self.write([("count", self.count), ("count", second)])
        with self.assertRaisesRegex(ValueError, "continuity"): probe.read(self.path, 7)
        self.write([("count", {**self.count, "device_sequence": 1}), ("eret", self.eret)])
        with self.assertRaisesRegex(ValueError, "ordering"): probe.read(self.path, 7)

    def test_eret_requires_its_real_count_update_and_exact_state_transition(self):
        self.write([("eret", {**self.eret, "sequence": 1})])
        with self.assertRaises(ValueError): probe.read(self.path, 7)
        for key, value in (("count_before", 99), ("count_after", 109), ("status_before", 0x34000007),
                           ("status_after", 0x34000003), ("epc_after", 0x80002004),
                           ("target_pc", 0x80002004), ("llbit_after", 1), ("llbit_before", 2), ("r0", 1)):
            with self.subTest(key=key):
                self.write([("count", self.count), ("eret", {**self.eret, key: value})])
                with self.assertRaises(ValueError): probe.read(self.path, 7)

    def test_previous_eret_selector_cannot_be_reinvented(self):
        second_count = {**self.count, "sequence": 3, "count_before": 108, "count_after": 116}
        second_eret = {**self.eret, "sequence": 4, "count_before": 108, "count_after": 116,
                       "previous_eret_thread_word": self.eret["thread_word_after"]}
        self.write([("count", self.count), ("eret", self.eret), ("count", second_count), ("eret", second_eret)])
        self.assertEqual(len(probe.read(self.path, 7)["rows"]), 4)
        second_eret["previous_eret_thread_word"] = 0
        self.write([("count", self.count), ("eret", self.eret), ("count", second_count), ("eret", second_eret)])
        with self.assertRaises(ValueError): probe.read(self.path, 7)

    def test_torn_footer_budget_columns_and_extra_rows_rejected(self):
        self.assertFalse(probe.summary(self.path, {"update": 7})["complete"])
        self.write(); original = self.path.read_text()
        for changed in (original.replace("result\ttrue\t2\t1\t1\n", ""),
                        original.replace("result\ttrue\t2\t1\t1", "result\ttrue\t3\t1\t2"),
                        original + "extra\n", original.replace("\tcount_before\t", "\tunknown\t", 1),
                        original.replace("0xffffffff80004000", "0x80004000")):
            self.path.write_text(changed)
            with self.assertRaises(ValueError): probe.read(self.path, 7)
        self.write()
        with mock.patch.object(probe, "MAX_ROWS", 1), self.assertRaises(ValueError): probe.read(self.path, 7)


if __name__ == "__main__":
    unittest.main()
