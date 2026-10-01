import unittest

from scripts.phase95_aim_turn import aim_settled, candidates, signed_yaw_error, turn


class AimTurnTests(unittest.TestCase):
    def test_signed_wraparound_error(self):
        self.assertEqual(signed_yaw_error(100, 65500), 136)
        self.assertEqual(signed_yaw_error(65500, 100), -136)
        self.assertEqual(signed_yaw_error(37768, 32768), 5000)
        for invalid in (-1, 65536, 0.5, True):
            with self.assertRaises(ValueError):
                signed_yaw_error(invalid, 0)

    def test_axis_candidates_are_bounded_and_hold_aim(self):
        yaw, pitch = candidates("yaw"), candidates("pitch")
        self.assertEqual(len(yaw), 29)
        self.assertEqual(len(pitch), 29)
        self.assertTrue(all(actions[0].buttons == 0x0010
                            and 0 < actions[0].frames <= 60 for actions in yaw + pitch))
        self.assertTrue(all(len(actions) == 2 and actions[1].frames == 60
                            and actions[1].x == actions[1].y == 0
                            for actions in yaw[:-1] + pitch[:-1]))
        self.assertTrue(all(actions[0].y == 0 for actions in yaw))
        self.assertTrue(all(actions[0].x == 0 for actions in pitch))
        with self.assertRaises(ValueError):
            candidates("roll")

    def test_angle_does_not_count_while_aim_motion_remains(self):
        state = {"manual_delta_x": 0.0, "manual_delta_y": 0.0}
        self.assertTrue(aim_settled(state))
        state["manual_delta_x"] = -179.8310546875
        self.assertFalse(aim_settled(state))
        state["manual_delta_x"] = 0.0
        state["manual_delta_y"] = float("nan")
        self.assertFalse(aim_settled(state))

    def test_rejects_unreachable_or_unbounded_objective_before_acting(self):
        for value, axis in ((65536, "yaw"), (-1, "yaw"), (16385, "pitch"),
                            (-16385, "pitch"), (1, "roll")):
            with self.assertRaises(ValueError):
                turn(None, value, axis=axis)
        with self.assertRaises(ValueError):
            turn(None, 100, tolerance=0)
        with self.assertRaises(ValueError):
            turn(None, 100, max_steps=31)


if __name__ == "__main__":
    unittest.main()
