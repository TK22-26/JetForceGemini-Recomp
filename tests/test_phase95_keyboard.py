import struct
import unittest

from scripts.phase95_keyboard import keyboard
from scripts.phase95_observation import FRONT_MODE, RDRAM_SIZE, ObservationError


class KeyboardTests(unittest.TestCase):
    def setUp(self):
        self.memory = bytearray(RDRAM_SIZE)
        self.memory[FRONT_MODE] = 24
        self.put(0xFEAA0, 0x80001000)
        self.put(0x1000 + 42 * 32, 0x80002000)
        for hi, lo, first, second, target in (
            (0, 4, 0x3C02, 0x2442, 0x5000),
            (0x84, 0x8C, 0x3C02, 0x2442, 0x5048),
            (0x88, 0x90, 0x3C08, 0x2508, 0x5030),
            (0x9C, 0xA0, 0x3C01, 0xA020, 0x5090),
            (0x54, 0x58, 0x3C01, 0xA439, 0x504C),
            (0x206C, 0x2070, 0x3C18, 0x8F18, 0x5018),
        ):
            self.put(0x2000 + hi, first << 16 | 0x8000)
            self.put(0x2000 + lo, second << 16 | target)
        self.put(0x5000, 1)
        self.put(0x5048, 0x80005031)
        self.memory[0x5030] = 49
        self.memory[0x5090] = 1

    def put(self, offset, value):
        struct.pack_into(">I", self.memory, offset, value)

    def test_label(self):
        value = keyboard(self.memory)
        self.assertEqual(value["label_hex"], "31")
        self.assertEqual(value["label_length"], 1)

    def test_partial_initializer(self):
        self.put(0x5048, 0)
        self.assertIsNone(keyboard(self.memory))

    def test_wrong_opcode_rejected(self):
        self.put(0x2000, 0)
        with self.assertRaises(ObservationError):
            keyboard(self.memory)

    def test_selection_bounds(self):
        self.put(0x5018, 41)
        with self.assertRaises(ObservationError):
            keyboard(self.memory)

    def test_cursor_bounds_and_segment(self):
        for value in (0x80005050, 0xC0005031):
            self.put(0x5048, value)
            with self.assertRaises(ObservationError):
                keyboard(self.memory)


if __name__ == "__main__":
    unittest.main()
