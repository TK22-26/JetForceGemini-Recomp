import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.autonomy import instruction_context as context


class InstructionContextTests(unittest.TestCase):
    def image(self):
        image = bytearray(4096)
        words = {0x100: 0x0c000100, 0x104: 0xafb00014, 0x108: 0x8fae0028,
                 0x10c: 0x00408025, 0x110: 0x8dcf0008, 0x114: 0x15e00012,
                 0x400: 0x40086000, 0x404: 0x2401fffe, 0x408: 0x01014824,
                 0x40c: 0x40896000, 0x410: 0x31020001, 0x414: 0, 0x418: 0x03e00008, 0x41c: 0}
        for offset, word in words.items():
            image[offset:offset + 4] = word.to_bytes(4, "big")
        return image

    def test_conditional_internal_link_and_loaded_branch_operand(self):
        images = [bytes(self.image())] * 8
        sites = context.sites(images, [0x80000114])
        self.assertEqual(len(sites), 1)
        self.assertEqual(context.projection({"sites": sites}), [{"pc": "0x80000114", "operand_register": 15,
            "load_base_register": 14, "load_offset": 8, "link_call_pc": "0x80000100", "callee": "0x80000400",
            "conditional_raw_ra": "0x80000108"}])
        self.assertEqual(len(sites[0]["callee_body"]), 8)

    def test_each_snapshot_must_match_call_corridor_and_callee(self):
        for offset in (0x100, 0x104, 0x108, 0x110, 0x114, 0x400, 0x418, 0x41c):
            original = self.image()
            other = copy.copy(original)
            other[offset] ^= 1
            with self.subTest(offset=offset):
                self.assertEqual(context.sites([bytes(original), bytes(original), bytes(other)], [0x80000114]), [])

    def test_unknown_flow_ra_writes_and_non_leaf_calls_do_not_supply_link_facts(self):
        mutations = [(0x104, 0x27ff0001), (0x10c, 0x10000001), (0x10c, 0xffffffff),
                     (0x400, 0x241f0001), (0x400, 0x0c000200), (0x400, 0xffffffff),
                     (0x418, 0x01000008), (0x41c, 0x241f0000)]
        for offset, word in mutations:
            image = self.image()
            image[offset:offset + 4] = word.to_bytes(4, "big")
            with self.subTest(offset=offset, word=word):
                self.assertEqual(context.sites([bytes(image)] * 2, [0x80000114]), [])

    def test_wrong_branch_operand_misalignment_and_bounds_are_not_sites(self):
        image = self.image()
        image[0x114:0x118] = (0x15c00012).to_bytes(4, "big")
        self.assertEqual(context.sites([bytes(image)], [0x80000114]), [])
        self.assertEqual(context.sites([bytes(self.image())], [0x80000000, 0x80000115, 0x80400000]), [])
        with self.assertRaisesRegex(ValueError, "target budget"):
            context.sites([bytes(image)], range(65))

    def test_inventory_retains_snapshot_identity_but_no_execution_or_parity_claim(self):
        image = bytes(self.image())
        with patch.object(context, "_records_at", return_value={7: {}, 8: {}}), \
                patch.object(context, "_snapshot", return_value=(image, {})):
            facts = context.inventory(Path("reference"), [7, 8], {"next_test": "branch at 0x80000114"})
        self.assertEqual(len(facts["snapshots"]), 4)
        self.assertEqual(len(facts["sites"]), 1)
        self.assertFalse(facts["execution_observed"])
        self.assertFalse(facts["caller_equivalence_proved"])
        self.assertFalse(facts["causal_fix_proved"])
        self.assertFalse(facts["parity_verified"])

    def test_decoder_does_not_promote_unknown_or_malformed_instructions(self):
        for word in (0xffffffff, 0x40286000, 0x40086001, 0x40896001, 0x03e10008, 0x03e00048, 0x3fe10001):
            with self.subTest(word=word):
                self.assertEqual(context.decode(0x80000100, word)["flow"], "unknown")

    def test_empty_images_and_invalid_windows_fail_closed_before_reading(self):
        self.assertIsNone(context.matching_words([], 0x80000000, 1))
        for window in ([], [1], [True, 2], [0, 2], [8, 7], [1, 17], [1, 1000001]):
            with self.subTest(window=window), patch.object(context, "_records_at") as read:
                with self.assertRaisesRegex(ValueError, "window"):
                    context.inventory(Path("unused"), window, {})
                read.assert_not_called()


if __name__ == "__main__":
    unittest.main()
