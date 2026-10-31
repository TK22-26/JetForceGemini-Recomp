import math
import struct
import unittest

from scripts.phase95_observation import (
    ACTOR_COUNT, ACTOR_LIST, FRONT_MODE, RDRAM_SIZE, FreshnessGuard,
    ObservationError, decode, physical,
)


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.ram = bytearray(RDRAM_SIZE)
        self.ram[FRONT_MODE] = 16
        self.put(ACTOR_COUNT, 1)
        self.put(ACTOR_LIST, 0x80001000)
        self.put(0x1000, 0x80002000)
        self.put(0x2040, 0x80003000)
        self.ram[0x3004:0x300C] = b"TestBot\0"
        struct.pack_into(">fff", self.ram, 0x200C, 19, -102, 199)

    def put(self, offset, value):
        struct.pack_into(">I", self.ram, offset, value)

    def observe(self, **kwargs):
        return decode(self.ram, sequence=1, **kwargs)

    def test_valid_player_and_explicit_unknowns(self):
        value = self.observe(player_pointer=0x80002000)
        self.assertEqual(value.player.position, (19, -102, 199))
        self.assertEqual(value.player.name, "TestBot")
        self.assertIn("health", value.unavailable)
        self.assertNotIn("player", value.unavailable)

    def test_no_player_is_not_guessed_from_name(self):
        self.assertIsNone(self.observe().player)

    def test_stale_player_rejected(self):
        with self.assertRaises(ObservationError):
            self.observe(player_pointer=0x80004000)

    def test_pointer_bounds_and_segments(self):
        for address in (0, 0x1000, 0xC0001000, 0x80000001, 0x803FFFF0, True):
            with self.subTest(address=address), self.assertRaises(ObservationError):
                physical(address, 0x44)
        self.assertEqual(physical(0xA0001000, 4), 0x1000)

    def test_count_and_table_fail_closed(self):
        self.put(ACTOR_COUNT, 1025)
        with self.assertRaises(ObservationError):
            self.observe()
        self.put(ACTOR_COUNT, 1)
        self.put(ACTOR_LIST, 0)
        with self.assertRaises(ObservationError):
            self.observe()

    def test_empty_startup_table(self):
        self.put(ACTOR_COUNT, 0)
        self.put(ACTOR_LIST, 0)
        self.assertEqual(self.observe().actors, ())

    def test_duplicate_alias_rejected(self):
        self.put(ACTOR_COUNT, 2)
        self.put(0x1004, 0xA0002000)
        with self.assertRaises(ObservationError):
            self.observe()

    def test_nonfinite_coordinates_rejected(self):
        for value in (math.nan, math.inf, -math.inf):
            struct.pack_into(">f", self.ram, 0x200C, value)
            with self.assertRaises(ObservationError):
                self.observe()

    def test_bad_profile_size_sequence(self):
        with self.assertRaises(ObservationError):
            self.observe(profile="unknown")
        with self.assertRaises(ObservationError):
            decode(self.ram[:-1], sequence=1)
        with self.assertRaises(ObservationError):
            decode(self.ram, sequence=True)

    def test_freshness(self):
        guard = FreshnessGuard()
        guard.accept(self.observe())
        with self.assertRaises(ObservationError):
            guard.accept(self.observe())
        guard.accept(decode(self.ram, sequence=2))


if __name__ == "__main__":
    unittest.main()
