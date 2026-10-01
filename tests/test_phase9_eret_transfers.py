from pathlib import Path
import tempfile
import unittest

from scripts import phase9_eret_transfers as events


class EretTransferTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "eret.tsv"
        self.row = {key: "0x00000000" for key in events.BASE[2:]}
        self.row.update({key: "0x0000000000000000" for key in events.REGISTERS})
        self.row.update(sequence="1", invocation="7", pc="0x80001000", opcode="0x42000018",
                        from_thread="0x80002000", to_thread="0x80003000", target_pc="0x80004000",
                        status="0x34000001", count="0xfffffff0", r31="0xffffffff80000000")

    def write(self, rows=None):
        rows = [self.row] if rows is None else rows
        columns = events.BASE + events.REGISTERS
        lines = ["jfg-native-eret-transfers-v1\t7\t8", "\t".join(columns)]
        lines += ["\t".join(row[key] for key in columns) for row in rows]
        lines += [f"result\ttrue\t{len(rows)}"]
        self.path.write_text("\n".join(lines) + "\n", encoding="ascii")

    def test_opt_in_requires_native_device_capture_and_clears_inherited_flag(self):
        for enabled, device in ((1, None), (True, None), (True, {"clock_basis": "oracle-lazy-count"})):
            with self.subTest(enabled=enabled, device=device), self.assertRaises(ValueError):
                events.specification(enabled, device)
        environment = {"PATH": "unchanged", "JFG_PHASE9_ERET_TRANSFERS": "ambient"}
        self.assertIsNone(events.configure(environment, False, None))
        self.assertEqual(environment, {"PATH": "unchanged"})
        spec = events.configure(environment, True,
                                {"clock_basis": "native-pre-instruction-count", "window": [7, 8]})
        self.assertEqual(environment["JFG_PHASE9_ERET_TRANSFERS"], "1")
        self.assertEqual(spec["window"], [7, 8])

    def test_raw_count_wrap_register_words_and_same_thread_preserved(self):
        self.write([self.row, {**self.row, "sequence": "2", "invocation": "8", "count": "0x00000002",
                              "from_thread": self.row["to_thread"]}])
        result = events.read(self.path, [7, 8])
        self.assertEqual([row["count"] for row in result["rows"]], [0xfffffff0, 2])
        self.assertEqual(result["rows"][0]["r31"], 0xffffffff80000000)
        for flag in ("clock_alignment_validated", "retirement_validated", "causal_fix_proved", "parity_verified"):
            self.assertIs(result[flag], False)
        self.assertEqual(events.summary(self.path, {"window": [7, 8]})["same_thread"], 1)

    def test_bad_boundary_and_order_are_rejected(self):
        for key, value in (("sequence", "2"), ("invocation", "6"), ("invocation", "9"),
                           ("opcode", "0x00000000"), ("status", "0x34000003"),
                           ("status", "0x34000005"), ("target_pc", "0x80004001"),
                           ("from_thread", "0x80002002"), ("pc", "0x80001002"),
                           ("to_thread", "0x00000000"), ("r0", "0x0000000100000000"),
                           ("r31", "0x80000000"), ("count", "-1")):
            with self.subTest(key=key, value=value):
                self.write([{**self.row, key: value}])
                with self.assertRaises(ValueError): events.read(self.path, [7, 8])
        self.write([{**self.row, "invocation": "8"}, {**self.row, "sequence": "2"}])
        with self.assertRaises(ValueError): events.read(self.path, [7, 8])

    def test_missing_torn_and_wrong_count_footer_fail_closed(self):
        self.assertFalse(events.summary(self.path, {"window": [7, 8]})["complete"])
        for footer in ("", "result\tfalse\t1\n", "result\ttrue\t2\n"):
            self.write()
            self.path.write_text(self.path.read_text().replace("result\ttrue\t1\n", footer))
            self.assertFalse(events.summary(self.path, {"window": [7, 8]})["complete"])

    def test_empty_window_is_a_complete_observation_not_a_retirement_claim(self):
        self.write([])
        result = events.summary(self.path, {"window": [7, 8]})
        self.assertTrue(result["complete"])
        self.assertEqual(result["events"], 0)
        self.assertFalse(result["retirement_validated"])

    def test_wrong_window_columns_or_extra_fields_rejected(self):
        self.write()
        with self.assertRaises(ValueError): events.read(self.path, [7, 9])
        original = self.path.read_text()
        for changed in (original.replace("\tcount\tr0", "\tcount\textra\tr0"),
                        original.replace("\nresult", "\textra\nresult"),
                        original.replace("\tr31\n", "\n")):
            self.path.write_text(changed)
            with self.assertRaises(ValueError): events.read(self.path, [7, 8])


if __name__ == "__main__":
    unittest.main()
