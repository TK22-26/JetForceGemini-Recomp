import unittest

from scripts.phase95_startup import Startup
from scripts.phase95_observation import FRONT_MODE, RDRAM_SIZE, ObservationError


class StartupTests(unittest.TestCase):
    def memory(self, mode):
        data = bytearray(RDRAM_SIZE)
        data[FRONT_MODE] = mode
        return data

    def test_loading_is_neutral(self):
        for mode in (0, 2):
            self.assertEqual(Startup().choose(0, self.memory(mode)).buttons, 0)

    def test_confirmation_has_release_edge(self):
        policy = Startup()
        self.assertEqual(policy.choose(0, self.memory(3)).buttons, 0x8000)
        self.assertEqual(policy.choose(1, self.memory(3)).buttons, 0)
        self.assertEqual(policy.choose(2, self.memory(3)).buttons, 0x8000)

    def test_transition_stops_without_extra_input(self):
        policy = Startup()
        policy.choose(0, self.memory(3))
        self.assertIsNone(policy.choose(1, self.memory(24)))

    def test_unknown_mode_not_gameplay_success(self):
        with self.assertRaises(ObservationError):
            Startup().choose(0, self.memory(16))

    def test_stale_or_incomplete_observation(self):
        policy = Startup()
        policy.choose(0, self.memory(0))
        with self.assertRaises(ObservationError):
            policy.choose(0, self.memory(3))
        with self.assertRaises(ObservationError):
            Startup().choose(0, b"")

    def test_gameplay_requires_player(self):
        policy = Startup(gameplay=True)
        self.assertEqual(policy.choose(0, self.memory(16)).buttons, 0)

    def test_gameplay_waits_after_name_screen(self):
        policy = Startup(gameplay=True)
        policy.saw_keyboard = True
        self.assertEqual(policy.choose(0, self.memory(0)).buttons, 0)

    def test_character_screen_confirmation(self):
        policy = Startup(gameplay=True)
        self.assertEqual(policy.choose(0, self.memory(5)).buttons, 0x8000)

    def test_keyboard_decisions(self):
        from unittest.mock import patch
        cases = (({"submode": 0}, 0x8000, 0),
                 ({"submode": 1, "label_length": 0, "key": 0}, 0x8000, 0),
                 ({"submode": 1, "label_length": 1, "key": 0}, 0, -80),
                 ({"submode": 1, "label_length": 1, "key": 30}, 0, 80),
                 ({"submode": 1, "label_length": 1, "key": 40}, 0x8000, 0))
        for state, buttons, x in cases:
            with patch("scripts.phase95_startup.keyboard", return_value=state):
                action = Startup(complete_label=True).choose(0, self.memory(24))
                self.assertEqual((action.buttons, action.x), (buttons, x))

    def test_keyboard_stall_has_bounded_recovery(self):
        from unittest.mock import patch
        state = {"submode": 1, "label_length": 1, "key": 0}
        policy = Startup(complete_label=True)
        actions = []
        with patch("scripts.phase95_startup.keyboard", return_value=state):
            with self.assertRaisesRegex(ObservationError, "bounded retries"):
                for sequence in range(30):
                    action = policy.choose(sequence, self.memory(24))
                    if action.x:
                        actions.append(action)
        self.assertTrue(any(action.frames == 12 for action in actions))
        self.assertTrue(any(action.x == 80 for action in actions))


if __name__ == "__main__":
    unittest.main()
