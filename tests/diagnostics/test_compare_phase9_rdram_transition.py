import unittest

from scripts.compare_phase9_rdram_transition import (
    RDRAM_BYTES, stable_actor_slots, summarize_actor_words,
    summarize_transition, summarize_words,
)


class RdramTransitionTests(unittest.TestCase):
    def test_new_actor_and_non_actor_bytes_are_separate(self):
        before_native = bytearray(RDRAM_BYTES)
        before_oracle = bytearray(RDRAM_BYTES)
        after_native = bytearray(RDRAM_BYTES)
        after_oracle = bytearray(RDRAM_BYTES)
        before_native[0x3000] = 1
        after_native[0x1001] = 2
        after_native[0x5000] = 3
        report = summarize_transition(
            *(bytes(item) for item in (
                before_native, before_oracle, after_native, after_oracle)),
            [(0x1000, 0x1200)])
        self.assertEqual(report["before_differing_bytes"], 1)
        self.assertEqual(report["after_differing_bytes"], 2)
        self.assertEqual(report["resolved_differing_bytes"], 1)
        self.assertEqual(report["new_differing_bytes"], 2)
        self.assertEqual(report["new_actor_bytes"], 1)
        self.assertEqual(report["new_non_actor_bytes"], 1)
        self.assertEqual(report["new_differing_pages"], 2)

    def test_rejects_invalid_actor_region(self):
        blank = bytes(RDRAM_BYTES)
        with self.assertRaisesRegex(ValueError, "invalid actor region"):
            summarize_transition(blank, blank, blank, blank, [(0x1000, 0x1001)])

    def test_focused_word_probe_keeps_before_and_after_values(self):
        images = [bytearray(RDRAM_BYTES) for _ in range(4)]
        for image, value in zip(images, (0x01020304, 0x01020304,
                                         0x05060708, 0x090a0b0c)):
            image[0x1234:0x1238] = value.to_bytes(4, "big")
        rows = summarize_words(tuple(bytes(image) for image in images),
                               (0x80001234, 0x80001234))
        self.assertEqual(rows, [{
            "address": "0x80001234", "native_before": "01020304",
            "oracle_before": "01020304", "native_after": "05060708",
            "oracle_after": "090a0b0c", "matches_before": True,
            "matches_after": False, "newly_divergent": True,
        }])

    def test_focused_word_probe_rejects_bad_address(self):
        blank = bytes(RDRAM_BYTES)
        for address in (0x80000001, 0x80400000, True):
            with self.assertRaisesRegex(ValueError, "aligned KSEG0"):
                summarize_words((blank,) * 4, (address,))

    def test_actor_word_detail_reports_only_new_differences(self):
        images = [bytearray(RDRAM_BYTES) for _ in range(4)]
        images[0][0x1000 + 0x10] = 7
        images[2][0x1000 + 0xEC + 2] = 1
        images[3][0x1000 + 0xEC + 2] = 2
        images[2][0x1000 + 0xFC + 3] = 3
        images[3][0x1000 + 0xFC + 3] = 4
        detail = summarize_actor_words(tuple(bytes(image) for image in images),
                                       [{"index": 11, "address": "0x80001000"}])
        self.assertEqual(detail["total_newly_divergent_words"], 2)
        self.assertEqual([item["word_offset"] for item in
                          detail["first_newly_divergent_words"]],
                         ["0x0ec", "0x0fc"])
        self.assertEqual(detail["first_newly_divergent_words"][0][
            "new_byte_offsets"], [2])
        self.assertEqual(detail["first_newly_divergent_words"][0][
            "guest_address"], "0x800010ec")

    def test_actor_word_detail_is_bounded_but_counts_all_words(self):
        images = [bytearray(RDRAM_BYTES) for _ in range(4)]
        for word in range(33):
            images[2][0x1000 + word * 4] = 1
        detail = summarize_actor_words(tuple(bytes(image) for image in images),
                                       [{"index": 0, "address": "0x80001000"}])
        self.assertEqual(detail["total_newly_divergent_words"], 33)
        self.assertEqual(len(detail["first_newly_divergent_words"]), 32)

    def test_only_stable_actor_slots_are_classified(self):
        before = {"actors": [{"index": 0, "address": "0x80001000"},
                              {"index": 1, "address": "0x80002000"}]}
        after = {"actors": [{"index": 0, "address": "0x80001000"},
                             {"index": 1, "address": "0x80003000"}]}
        self.assertEqual(stable_actor_slots(before, after), before["actors"][:1])

    def test_actor_word_detail_rejects_duplicate_address(self):
        blank = bytes(RDRAM_BYTES)
        with self.assertRaisesRegex(ValueError, "duplicate stable actor"):
            summarize_actor_words((blank,) * 4,
                                  [{"index": 0, "address": "0x80001000"},
                                   {"index": 1, "address": "0x80001000"}])


if __name__ == "__main__":
    unittest.main()
