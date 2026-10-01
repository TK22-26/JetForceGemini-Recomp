import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.phase95_aim import aim_state
from scripts.phase95_observation import ObservationError


class AimTests(unittest.TestCase):
    def fixture(self):
        memory = bytearray(0x400000)
        for offset, word in ((0x3AABC, 0x27BDFFA8), (0x3AC74, 0xE60201EC),
                             (0x3AC7C, 0xE60E01F0), (0x3AC88, 0xE61201F0),
                             (0x3B09C, 0xA618011C), (0x3B0C8, 0xA60F01E2)):
            struct.pack_into(">I", memory, offset, word)
        struct.pack_into(">I", memory, 0x6068, 0x80007000)
        struct.pack_into(">I", memory, 0xA18B0, 0x800A18D8)
        struct.pack_into(">ffff", memory, 0x7000 + 0x1E4, -30, 20, 1, 0)
        struct.pack_into(">h", memory, 0x7000 + 0x11C, -200)
        struct.pack_into(">h", memory, 0x7000 + 0x1E2, 100)
        struct.pack_into(">hh", memory, 0x7000 + 0x1FC, -1, 0)
        memory[0x7000 + 0x1F4] = 1
        state = SimpleNamespace(front_mode=16,
                                player=SimpleNamespace(address=0x80006000,
                                                       position=(1, 2, 3), yaw=300))
        return memory, state

    def test_read_validated_manual_aim_fields(self):
        memory, state = self.fixture()
        with patch("scripts.phase95_aim.decode", return_value=state):
            result = aim_state(memory, {"sequence": 1, "player": state.player.address})
        self.assertEqual((result["manual_delta_x"], result["manual_delta_y"]), (-30, 20))
        self.assertEqual((result["manual_yaw"], result["manual_pitch"]), (-200, 100))
        self.assertEqual(result["control_mode"], "expert")

    def test_unknown_code_and_control_mode_fail_closed(self):
        memory, state = self.fixture()
        with patch("scripts.phase95_aim.decode", return_value=state):
            struct.pack_into(">I", memory, 0x3B0C8, 0)
            with self.assertRaises(ObservationError):
                aim_state(memory, {"sequence": 1, "player": state.player.address})
            struct.pack_into(">I", memory, 0x3B0C8, 0xA60F01E2)
            struct.pack_into(">I", memory, 0xA18B0, 0)
            with self.assertRaises(ObservationError):
                aim_state(memory, {"sequence": 1, "player": state.player.address})
            struct.pack_into(">I", memory, 0xA18B0, 0x800A18D8)
            memory[0xA4FC4] = 1
            with self.assertRaises(ObservationError):
                aim_state(memory, {"sequence": 1, "player": state.player.address})


if __name__ == "__main__":
    unittest.main()
