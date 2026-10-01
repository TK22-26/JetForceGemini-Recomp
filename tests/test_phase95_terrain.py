import struct
import unittest
from scripts.phase95_terrain import terrain, vertical_surfaces
from scripts.phase95_observation import ObservationError


class TerrainTests(unittest.TestCase):
    def fixture(self):
        memory = bytearray(0x400000)
        struct.pack_into(">4I", memory, 0x1B650, 0x3C02800A, 0x8C420D60, 0x03E00008, 0)
        struct.pack_into(">I", memory, 0xA0D60, 0x80001000)
        struct.pack_into(">2I", memory, 0x1004, 0x80002000, 0x80003000)
        struct.pack_into(">h", memory, 0x101A, 1)
        struct.pack_into(">6h", memory, 0x3000, 0, 0, 0, 100, 100, 100)
        struct.pack_into(">2I", memory, 0x2000, 0x80005000, 0x80006000)
        struct.pack_into(">I", memory, 0x200C, 0x80004000)
        struct.pack_into(">h", memory, 0x2028, 1)
        struct.pack_into(">h", memory, 0x4018, 1)
        memory[0x6001:0x6004] = bytes([0, 1, 2])
        for i, point in enumerate(((0, 0, 0), (100, 100, 0), (0, 0, 100))):
            struct.pack_into(">3h", memory, 0x5000 + i * 10, *point)
        return memory

    def test_decode_and_surface_interpolation(self):
        geometry = terrain(self.fixture())
        self.assertEqual(len(geometry["blocks"][0]["triangles"]), 1)
        self.assertAlmostEqual(vertical_surfaces(geometry, 25, 25)[0]["height"], 25)
        self.assertEqual(vertical_surfaces(geometry, 101, 101), [])

    def test_reject_bad_profile_count_and_range(self):
        for offset, fmt, value in ((0x1B650, ">I", 0), (0x101A, ">h", -1),
                                   (0x4008, ">h", 2), (0x2000, ">I", 0)):
            memory = self.fixture()
            struct.pack_into(fmt, memory, offset, value)
            with self.assertRaises(ObservationError):
                terrain(memory)

    def test_degenerate_triangle_is_not_a_floor(self):
        geometry = terrain(self.fixture())
        geometry["blocks"][0]["triangles"][0]["vertices"] = [(0, 0, 0)] * 3
        self.assertEqual(vertical_surfaces(geometry, 0, 0), [])


if __name__ == "__main__":
    unittest.main()
