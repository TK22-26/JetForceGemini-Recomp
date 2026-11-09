import unittest

from scripts.phase95_movement import displacement


class MovementTests(unittest.TestCase):
    def test_horizontal_ignores_vertical_fall(self):
        self.assertEqual(displacement((0, 5, 0), (3, -100, 4))["horizontal"], 5)

    def test_no_movement(self):
        self.assertEqual(displacement((1, 2, 3), (1, 2, 3))["horizontal"], 0)

    def test_invalid_coordinate(self):
        with self.assertRaises(ValueError):
            displacement((0, 0, 0), (float("nan"), 0, 0))


if __name__ == "__main__":
    unittest.main()
