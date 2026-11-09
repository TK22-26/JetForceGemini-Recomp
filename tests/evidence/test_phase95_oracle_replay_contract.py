import unittest

from scripts.phase95_oracle_replay import (
    diagnostic_n64_variant, parse_domain_inventory, replay, select_target, validate_entry_fcr,
    validate_entry_fpu, validate_entry_gpr,
    validate_entry_memory, validate_entry_pc,
    validate_entry_register_catalog,
    validate_focus, validate_queue_trace,
    validate_watch_word,
)


class OracleReplayContractTests(unittest.TestCase):
    def test_queue_clock_requires_explicit_queue_trace(self):
        for value, queues in ((True, ()), (1, (0x800feb80,)), ("1", (0x800feb80,))):
            with self.subTest(value=value, queues=queues):
                with self.assertRaisesRegex(ValueError, "queue clock trace requires"):
                    replay(None, None, None, None, None,
                           queue_trace=queues, queue_clock_trace=value)

    def test_si_clock_requires_explicit_transaction_trace(self):
        for value, transactions in ((True, False), (1, True), ("1", True)):
            with self.subTest(value=value, transactions=transactions):
                with self.assertRaisesRegex(ValueError, "SI clock trace requires"):
                    replay(None, None, None, None, None,
                           si_trace=transactions, si_clock_trace=value)

    def test_memory_domain_inventory_is_bounded_and_unambiguous(self):
        self.assertEqual(parse_domain_inventory([
            "schema\t1", "memory-domain\tFlashRAM\t131072",
            "memory-domain\tRDRAM\t4194304"]), [
                {"name": "FlashRAM", "size": 131072},
                {"name": "RDRAM", "size": 4194304}])
        for lines in ([], ["memory-domain\tRDRAM\t0"],
                      ["memory-domain\tRDRAM\t4", "memory-domain\tRDRAM\t4"],
                      ["memory-domain\tRDRAM\t4", "memory-domain\tFlashRAM\t4"],
                      ["memory-domain\tRDRAM\tnope"]):
            with self.assertRaises(ValueError):
                parse_domain_inventory(lines)

    def test_diagnostic_n64_variant_isolated_and_fail_closed(self):
        key = "BizHawk.Emulation.Cores.Nintendo.N64.N64"
        settings = {"PreferredCores": {"N64": "Mupen64Plus"},
                    "CoreSyncSettings": {key: {"Core": 1, "Rsp": 0}}}
        pure = diagnostic_n64_variant(settings, None, 0)
        self.assertEqual(pure["CoreSyncSettings"][key]["Core"], 0)
        self.assertEqual(settings["CoreSyncSettings"][key]["Core"], 1)
        self.assertIs(diagnostic_n64_variant(settings, None, None), settings)
        ares = diagnostic_n64_variant(settings, "Ares64", None)
        self.assertEqual(ares["PreferredCores"]["N64"], "Ares64")
        self.assertEqual(settings["PreferredCores"]["N64"], "Mupen64Plus")
        for invalid in (True, -1, 3, "0"):
            with self.assertRaises(ValueError):
                diagnostic_n64_variant(settings, None, invalid)
        with self.assertRaisesRegex(ValueError, "cannot use"):
            diagnostic_n64_variant(settings, "Ares64", 0)
        with self.assertRaisesRegex(ValueError, "requires pinned"):
            diagnostic_n64_variant({"PreferredCores": {"N64": "Ares64"}},
                                   None, 0)

    def test_entry_fcr_requires_entry_probe(self):
        self.assertTrue(validate_entry_fcr(True, 0x80074434))
        self.assertFalse(validate_entry_fcr(False, None))
        for enabled, entry in ((True, None), ("yes", 0x80074434)):
            with self.assertRaises(ValueError):
                validate_entry_fcr(enabled, entry)

    def test_entry_gpr_requires_entry_probe(self):
        self.assertTrue(validate_entry_gpr(True, 0x800743D0))
        self.assertFalse(validate_entry_gpr(False, None))
        for enabled, entry in ((True, None), ("yes", 0x800743D0)):
            with self.assertRaises(ValueError):
                validate_entry_gpr(enabled, entry)

    def test_entry_memory_requires_entry_probe(self):
        self.assertTrue(validate_entry_memory(True, 0x800743D0))
        self.assertFalse(validate_entry_memory(False, None))
        for enabled, entry in ((True, None), ("yes", 0x800743D0)):
            with self.assertRaises(ValueError):
                validate_entry_memory(enabled, entry)

    def test_entry_fpu_requires_entry_probe(self):
        self.assertTrue(validate_entry_fpu(True, 0x80074ACC))
        self.assertFalse(validate_entry_fpu(False, None))
        for enabled, entry in ((True, None), ("yes", 0x80074ACC)):
            with self.assertRaises(ValueError):
                validate_entry_fpu(enabled, entry)

    def test_bounded_prefix_target(self):
        self.assertEqual(select_target(26441, None), 26441)
        self.assertEqual(select_target(26441, 120), 120)

    def test_rejects_unbounded_or_invalid_prefix(self):
        for export_target, requested in ((0, None), (12, 2), (12, 13),
                                         (12, True), (True, None)):
            with self.assertRaises(ValueError):
                select_target(export_target, requested)

    def test_focus_requires_bounded_update_hash_window(self):
        self.assertEqual(validate_focus((1248, 1260), True), (1248, 1260))
        for focus, enabled in (((0, 1), True), ((1, 17), True),
                               ((2, 1), True), ((1, 2), False),
                               ((True, 2), True)):
            with self.assertRaises(ValueError):
                validate_focus(focus, enabled)

    def test_watch_requires_focused_vi_trace_and_aligned_kseg0_word(self):
        self.assertEqual(validate_watch_word(0x801BC3E0, (1248, 1253), True),
                         0x801BC3E0)
        for address, focus, vi_trace in (
                (0x801BC3E0, None, True),
                (0x801BC3E0, (1248, 1253), False),
                (0x801BC3E1, (1248, 1253), True),
                (0x80400000, (1248, 1253), True),
                (True, (1248, 1253), True)):
            with self.assertRaises(ValueError):
                validate_watch_word(address, focus, vi_trace)

    def test_entry_probe_requires_focused_vi_trace_and_guest_pc(self):
        self.assertEqual(validate_entry_pc(0x8039078C, (1247, 1253), True),
                         0x8039078C)
        for address, focus, vi_trace in (
                (0x8039078D, (1247, 1253), True),
                (0x02F0084C, (1247, 1253), True),
                (0x8039078C, None, True),
                (0x8039078C, (1247, 1253), False)):
            with self.assertRaises(ValueError):
                validate_entry_pc(address, focus, vi_trace)

    def test_register_catalog_requires_an_entry_probe(self):
        self.assertTrue(validate_entry_register_catalog(True, 0x80074ACC))
        self.assertFalse(validate_entry_register_catalog(False, None))
        for enabled, entry in ((True, None), ("yes", 0x80074ACC)):
            with self.assertRaises(ValueError):
                validate_entry_register_catalog(enabled, entry)

    def test_queue_probe_requires_bounded_distinct_guest_queues(self):
        self.assertEqual(validate_queue_trace(
            (0x800FEB80, 0x800FE4B8), (1247, 1253), True),
            (0x800FE4B8, 0x800FEB80))
        self.assertEqual(validate_queue_trace((), None, False), ())
        for queues, focus, vi_trace in (
                ((0x800FE4B8,), None, True),
                ((0x800FE4B8,), (1247, 1253), False),
                ((0x800FE4B9,), (1247, 1253), True),
                ((0x80400000,), (1247, 1253), True),
                ((0x800FE4B8, 0x800FE4B8), (1247, 1253), True),
                ((True,), (1247, 1253), True),
                (tuple(range(0x800FE000, 0x800FE024, 4)),
                 (1247, 1253), True)):
            with self.assertRaises(ValueError):
                validate_queue_trace(queues, focus, vi_trace)


if __name__ == "__main__":
    unittest.main()
