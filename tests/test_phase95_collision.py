import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.phase95_collision import bounds_inventory
from scripts.phase95_observation import ObservationError


class CollisionTests(unittest.TestCase):
    def fixture(self):
        memory = bytearray(0x400000)
        struct.pack_into(">7I", memory, 0x7E484, 0x3C0E8010, 0x8DCE47E0,
                         0x3C028010, 0xAC8E0000, 0x8C4247E4, 0x03E00008, 0)
        struct.pack_into(">iI", memory, 0x1047E0, 1, 0x80001000)
        struct.pack_into(">I", memory, 0x1000, 0x80002000)
        struct.pack_into(">I", memory, 0x205C, 0x80003000)
        struct.pack_into(">I", memory, 0x204C, 0x80004000)
        struct.pack_into(">6f", memory, 0x3100, -1, -2, -3, 1, 2, 3)
        struct.pack_into(">H", memory, 0x400A, 1)
        return memory

    def read(self, memory):
        with patch("scripts.phase95_collision.decode", return_value=SimpleNamespace(
                front_mode=16, actors=[SimpleNamespace(address=0x80002000, name="door")])):
            return bounds_inventory(memory)

    def test_bounds(self):
        result = self.read(self.fixture())
        self.assertEqual(result["models"][0]["lower"], (-1, -2, -3))
        self.assertTrue(result["models"][0]["polylist_enabled"])

    def test_invalid_bounds(self):
        for value in (float("nan"), 5):
            memory = self.fixture()
            struct.pack_into(">f", memory, 0x3100, value)
            with self.assertRaises(ObservationError):
                self.read(memory)

    def test_accessor_count_and_stale_actor_rejected(self):
        for offset, value in ((0x7E484, 0), (0x1047E0, 1025), (0x1000, 0x80005000)):
            memory = self.fixture()
            struct.pack_into(">I", memory, offset, value)
            with self.assertRaises(ObservationError):
                self.read(memory)

    def test_empty_registry(self):
        memory = self.fixture()
        struct.pack_into(">iI", memory, 0x1047E0, 0, 0)
        self.assertEqual(self.read(memory)["models"], [])


if __name__ == "__main__":
    unittest.main()
