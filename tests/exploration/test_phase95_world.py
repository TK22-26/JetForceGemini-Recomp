import struct
import unittest
from types import SimpleNamespace

from scripts.phase95_world import read_exit, select_exit
from scripts.phase95_observation import ObservationError


class WorldTests(unittest.TestCase):
    def fixture(self):
        memory = bytearray(0x400000)
        actors = [SimpleNamespace(name="exit", address=0x80001000 + i * 0x100,
                                  position=(1.0, 2.0, 3.0)) for i in range(2)]
        for i, actor in enumerate(actors):
            setup = 0x2001 + i * 0x20  # setup data is byte-addressed, not word-aligned
            struct.pack_into(">I", memory, (actor.address & 0x1FFFFFFF) + 0x3C, 0x80000000 + setup)
            memory[setup + 0xA] = 48 + i
            memory[setup + 0xB] = 255
            memory[setup + 0x14] = 255
        return memory, actors

    def test_colocated_exits_remain_distinct(self):
        memory, actors = self.fixture()
        first, second = [read_exit(memory, actor, 47) for actor in actors]
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(select_exit(memory, actors, 47, second["id"])[0], actors[1])
        self.assertEqual(first["destination_level"], 48)
        self.assertEqual(first["reachability"], "unknown")

    def test_ambiguous_or_missing_identity_rejected(self):
        memory, actors = self.fixture()
        for key in (None, "missing"):
            with self.assertRaises(ObservationError):
                select_exit(memory, actors, 47, key)
        key = read_exit(memory, actors[0], 47)["id"]
        with self.assertRaises(ObservationError):
            select_exit(memory, [actors[0], actors[0]], 47, key)

    def test_identity_survives_heap_relocation_but_not_setup_change(self):
        memory, actors = self.fixture()
        original = read_exit(memory, actors[0], 47)["id"]
        relocated = SimpleNamespace(name="exit", address=0x80003000, position=actors[0].position)
        memory[0x4003:0x401F] = memory[0x2001:0x201D]
        struct.pack_into(">I", memory, 0x303C, 0x80004003)
        self.assertEqual(read_exit(memory, relocated, 47)["id"], original)
        memory[0x4018] ^= 1
        self.assertNotEqual(read_exit(memory, relocated, 47)["id"], original)

    def test_invalid_setup_pointer_rejected(self):
        memory, actors = self.fixture()
        struct.pack_into(">I", memory, 0x103C, 0x803FFFF0)
        with self.assertRaises(ObservationError):
            read_exit(memory, actors[0], 47)


if __name__ == "__main__":
    unittest.main()
