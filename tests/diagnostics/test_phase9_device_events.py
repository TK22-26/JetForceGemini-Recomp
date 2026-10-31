import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts import phase9_device_events as events


class DeviceEventTests(unittest.TestCase):
    def test_opt_in_requires_focus_points_and_explicit_engine(self):
        self.assertIsNone(events.specification(False, [], None, side="native", qualified_engine=False))
        for enabled, pcs, focus, engine in ((1, [1], [7, 9], True), (True, [], [7, 9], True),
            (True, [1], None, True), (True, [1], [7, 9], False), (True, [1], [7, 1000000], True)):
            with self.subTest(enabled=enabled, pcs=pcs, focus=focus, engine=engine), self.assertRaises(ValueError):
                events.specification(enabled, pcs, focus, side="native", qualified_engine=engine)
        spec = events.specification(True, [0x8009693c], [1907, 1910], side="oracle", qualified_engine=True)
        self.assertEqual(spec["window"], [1906, 1911])
        self.assertTrue(spec["observation_only"])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "events.tsv"
        self.row = {key: "0x00000000" for key in (*events.BASE[4:10], *events.BASE[11:], *events.REGISTERS)}
        self.row.update(sequence="1", invocation="7", phase="dispatch", source="vi", deadline_valid="1",
                        pc="0x8009693c", clock_raw="0xffffffff", deadline="0x00000010",
                        r31_lo="0x80096930", r31_hi="0xffffffff")

    def write(self, rows=None, side="native", footer=True):
        rows = [self.row] if rows is None else rows
        columns = events.BASE + events.REGISTERS
        lines = [f"jfg-phase9-device-events-v1\t{events.CLOCKS[side]}\t7\t9", "\t".join(columns)]
        lines.extend("\t".join(row[key] for key in columns) for row in rows)
        if footer:
            lines.append(f"result\ttrue\t{len(rows)}")
        self.path.write_text("\n".join(lines) + "\n", encoding="ascii")

    def test_raw_clock_wrap_and_ra_are_preserved_without_qualification_claims(self):
        other = {**self.row, "sequence": "2", "phase": "state", "clock_raw": "0x00000002"}
        self.write([self.row, other])
        result = events.read(self.path, [7, 9], side="native")
        self.assertEqual([row["clock_raw"] for row in result["rows"]], [0xffffffff, 2])
        self.assertEqual(result["rows"][0]["r31_hi"], 0xffffffff)
        for flag in ("clock_alignment_validated", "retirement_validated", "causal_fix_proved", "parity_verified"):
            self.assertIs(result[flag], False)

    def test_wrong_engine_clock_basis_and_window_are_rejected(self):
        self.write()
        with self.assertRaises(ValueError): events.read(self.path, [7, 9], side="oracle")
        with self.assertRaises(ValueError): events.read(self.path, [6, 9], side="native")
        self.write(side="oracle")
        self.assertEqual(events.read(self.path, [7, 9], side="oracle")["clock_basis"], "oracle-lazy-count")

    def test_missing_footer_empty_or_torn_trace_is_not_complete(self):
        self.write(footer=False)
        with self.assertRaises(ValueError): events.read(self.path, [7, 9], side="native")
        self.write([])
        with self.assertRaises(ValueError): events.read(self.path, [7, 9], side="native")
        self.write()
        self.path.write_text(self.path.read_text().replace("result\ttrue\t1", "result\ttrue\t2"))
        with self.assertRaises(ValueError): events.read(self.path, [7, 9], side="native")

    def test_bad_sequence_outside_window_unknown_phases_and_zero_register_rejected(self):
        original = copy.deepcopy(self.row)
        for field, value in (("sequence", "2"), ("invocation", "6"), ("invocation", "10"),
                             ("phase", "retired"), ("source", "invented"), ("deadline_valid", "2"),
                             ("r0_hi", "0x00000001"), ("pc", "0x123")):
            with self.subTest(field=field, value=value):
                self.row = {**original, field: value}
                self.write()
                with self.assertRaises(ValueError): events.read(self.path, [7, 9], side="native")

    def test_absent_deadline_must_be_zero_and_invocations_cannot_rewind(self):
        self.row["deadline_valid"] = "0"
        self.write()
        with self.assertRaises(ValueError): events.read(self.path, [7, 9], side="native")
        self.row["deadline"] = "0x00000000"
        self.write([{**self.row, "invocation": "8"}, {**self.row, "sequence": "2", "invocation": "7"}])
        with self.assertRaises(ValueError): events.read(self.path, [7, 9], side="native")


if __name__ == "__main__":
    unittest.main()
