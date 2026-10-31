import copy
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from scripts import phase9_instruction_effect_trace as trace


class InstructionEffectTraceTests(unittest.TestCase):
    def test_configuration_clears_inherited_flags_and_requires_qualified_window(self):
        env = {"JFG_PHASE9_INSTRUCTION_EFFECT_UPDATE": "99", "unrelated": "kept"}
        device = {"window": [6, 10], "clock_basis": "native-pre-instruction-count"}
        eret = {"window": [6, 10], "phase": "after-cpu-eret-state-before-host-handoff"}
        self.assertIsNone(trace.configure(env, None, None, None))
        self.assertEqual(env, {"unrelated": "kept"})
        spec = trace.configure(env, 7, device, eret)
        self.assertEqual(env["JFG_PHASE9_INSTRUCTION_EFFECT_UPDATE"], "7")
        self.assertEqual(spec["update"], 7)
        self.assertFalse(spec["retirement_validated"])
        for update, dev, transfer in ((True, device, eret), (0, device, eret),
                (11, device, eret), (7, None, eret), (7, device, None),
                (7, {**device, "clock_basis": "oracle-lazy-count"}, eret),
                (7, device, {**eret, "window": [5, 10]}),
                (7, {**device, "window": [True, 10]}, eret)):
            with self.subTest(update=update, dev=dev, transfer=transfer), self.assertRaises(ValueError):
                trace.configure(env, update, dev, transfer)
            self.assertNotIn("JFG_PHASE9_INSTRUCTION_EFFECT_UPDATE", env)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "effect.bin"
        row = dict.fromkeys(trace.WORDS, 0)
        row.update(phase=0, section=12, pc=0x00401000, opcode=0x24020007,
                   owner=0x80001000, thread_word=0x80001000, count=0xfffffffc, device_sequence=11,
                   status=0x2400ff01, gpr=[0] * 32)
        row["gpr"][31] = 0xffffffff80004000
        effect = copy.deepcopy(row)
        effect.update(phase=1, count=0)
        effect["gpr"][2] = 7
        eret_entry = {**copy.deepcopy(effect), "phase": 0, "pc": 0x800759c0, "opcode": 0x42000018, "status": 0x2400ff03}
        eret = {**copy.deepcopy(eret_entry), "phase": 2, "status": 0x2400ff01,
                "target": 0x80302514, "thread_word": 0x80105410, "selected_owner": 0x80105410}
        self.rows = [row, effect, eret_entry, eret]

    def write(self, rows=None):
        rows = self.rows if rows is None else rows
        data = bytearray(trace.MAGIC + struct.pack("<I", 7))
        previous = [0] * 32
        for sequence, row in enumerate(rows):
            mask = sum(1 << i for i, value in enumerate(row["gpr"]) if sequence == 0 or value != previous[i])
            data.extend(bytes([row["phase"]]) + struct.pack("<12I", *(row[key] for key in trace.WORDS), mask))
            for i, value in enumerate(row["gpr"]):
                if mask & (1 << i):
                    data.extend(struct.pack("<Q", value))
            previous = list(row["gpr"])
        data.extend(b"\xff" + struct.pack("<I", len(rows)))
        self.path.write_bytes(data)
        return bytes(data)

    def test_delta_roundtrip_preserves_raw_full_width_fields_and_transfer(self):
        self.write()
        result = list(trace.records(self.path, 7))
        self.assertEqual(len(result), 4)
        self.assertEqual(result[0]["pc"], 0x00401000)
        self.assertEqual(result[1]["gpr"][31], 0xffffffff80004000)
        self.assertEqual(result[0]["gpr"][2], 0)
        self.assertEqual(result[1]["gpr"][2], 7)
        self.assertEqual([row["count"] for row in result[:2]], [0xfffffffc, 0])
        self.assertEqual(result[3]["owner"], 0x80001000)
        self.assertEqual(result[3]["selected_owner"], 0x80105410)
        summary = trace.summary(self.path, 7)
        self.assertTrue(summary["complete"])
        self.assertEqual((summary["entries"], summary["effects"], summary["eret_transfers"]), (2, 1, 1))
        for flag in trace.LIMITS:
            self.assertFalse(summary[flag])

    def test_every_truncation_and_trailing_bytes_reject(self):
        original = self.write()
        for end in range(len(original)):
            with self.subTest(end=end):
                self.path.write_bytes(original[:end])
                self.assertFalse(trace.summary(self.path, 7)["complete"])
        self.path.write_bytes(original + b"unexpected")
        self.assertFalse(trace.summary(self.path, 7)["complete"])

    def test_pairing_does_not_search_forward_or_ignore_owner(self):
        for index, key, value in ((1, "phase", 0), (1, "pc", 0x00401004), (1, "section", 13),
                                  (1, "owner", 0x80002000), (1, "opcode", 0), (3, "phase", 1)):
            rows = copy.deepcopy(self.rows)
            rows[index][key] = value
            with self.subTest(key=key):
                self.write(rows)
                self.assertFalse(trace.summary(self.path, 7)["complete"])

    def test_device_order_alignment_and_zero_register_reject(self):
        for index, key, value in ((1, "device_sequence", 10), (0, "pc", 0x00401001),
                                  (0, "thread_word", 0x80001001), (0, "device_sequence", 65537)):
            rows = copy.deepcopy(self.rows)
            rows[index][key] = value
            with self.subTest(key=key):
                self.write(rows)
                self.assertFalse(trace.summary(self.path, 7)["complete"])
        rows = copy.deepcopy(self.rows)
        rows[0]["gpr"][0] = 1
        self.write(rows)
        self.assertFalse(trace.summary(self.path, 7)["complete"])

    def test_eret_requires_committed_status_target_and_selected_thread(self):
        for key, value in (("status", 0x2400ff03), ("target", 0), ("selected_owner", 0),
                           ("thread_word", 0x80001000), ("target", 0x80302515)):
            rows = copy.deepcopy(self.rows)
            rows[-1][key] = value
            with self.subTest(key=key):
                self.write(rows)
                self.assertFalse(trace.summary(self.path, 7)["complete"])

    def test_pending_entry_empty_stream_and_bad_counts_reject(self):
        self.write(self.rows[:1])
        self.assertFalse(trace.summary(self.path, 7)["complete"])
        self.write([])
        self.assertFalse(trace.summary(self.path, 7)["complete"])
        data = self.write()
        self.path.write_bytes(data[:-4] + struct.pack("<I", 3))
        self.assertFalse(trace.summary(self.path, 7)["complete"])

    def test_initial_snapshot_and_redundant_delta_bits_reject(self):
        data = bytearray(self.write())
        data[57:61] = struct.pack("<I", 0xfffffffe)  # First mask must include every GPR.
        self.path.write_bytes(data)
        self.assertFalse(trace.summary(self.path, 7)["complete"])
        data = bytearray(self.write())
        # Second record mask is at 12 + (49 + 256) + 45.
        mask_offset = 12 + 305 + 45
        data[mask_offset:mask_offset+4] = struct.pack("<I", (1 << 2) | (1 << 31))
        data[mask_offset+12:mask_offset+12] = struct.pack("<Q", 0xffffffff80004000)
        self.path.write_bytes(data)
        self.assertFalse(trace.summary(self.path, 7)["complete"])

    def test_window_and_budgets_are_bounded(self):
        self.write()
        for update in (True, 0, 8, 1000001):
            self.assertFalse(trace.summary(self.path, update)["complete"])
        with mock.patch.object(trace, "MAX_ROWS", 2):
            self.assertFalse(trace.summary(self.path, 7)["complete"])
        with mock.patch.object(trace, "MAX_BYTES", 12):
            self.assertFalse(trace.summary(self.path, 7)["complete"])

    def test_every_register_bit_survives_changed_and_unchanged_deltas(self):
        for number, row in enumerate(self.rows):
            row["gpr"] = [0] + [((index << 56) | (1 << ((index + number) % 64)) | number)
                                    for index in range(1, 32)]
        self.rows[2]["gpr"] = list(self.rows[1]["gpr"])
        self.write()
        decoded = list(trace.records(self.path, 7))
        self.assertEqual([row["gpr"] for row in decoded], [tuple(row["gpr"]) for row in self.rows])


if __name__ == "__main__":
    unittest.main()
