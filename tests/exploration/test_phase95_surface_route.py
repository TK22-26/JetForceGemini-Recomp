from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.phase95_surface_route import propose
from scripts.phase95_surface_follow import Segment
from scripts.phase95_observation import ObservationError


class SurfaceRouteTests(unittest.TestCase):
    def test_detour_around_missing_surface(self):
        def surfaces(_, x, z):
            return [] if 20 < x < 60 and z < 80 else [{"height": 0}]
        with patch("scripts.phase95_surface_route.vertical_surfaces", side_effect=surfaces):
            result = propose({}, (0, 0, 0), (80, 0, 0), margin=100, radius=10)
        self.assertFalse(result["acceptance"])
        self.assertTrue(any(point[2] >= 80 for point in result["waypoints"]))
        self.assertEqual(result["waypoints"][-1], (80, 0, 0))

    def test_missing_start_surface_rejected(self):
        with patch("scripts.phase95_surface_route.vertical_surfaces", return_value=[]):
            with self.assertRaisesRegex(ObservationError, "under route start"):
                propose({}, (0, 0, 0), (100, 0, 0))

    def test_exhaustion_is_incomplete(self):
        with patch("scripts.phase95_surface_route.vertical_surfaces", return_value=[{"height": 0}]):
            with self.assertRaisesRegex(ObservationError, "incomplete"):
                propose({}, (0, 0, 0), (1000, 0, 0), max_nodes=1)

    def test_vertical_target_separation_is_not_ignored(self):
        with patch("scripts.phase95_surface_route.vertical_surfaces", return_value=[{"height": 0}]):
            with self.assertRaises(ObservationError):
                propose({}, (0, 0, 0), (0, 200, 0), margin=100, radius=95)

    def test_overlapping_lower_surface_is_not_a_walkable_drop(self):
        # A continuous upper deck blocks walking down to an overlapping lower
        # triangle, even when the height difference is within the old 30-unit
        # permissive edge threshold.
        def surfaces(_, x, z):
            return [{"height": 60}, {"height": 49}]
        with patch("scripts.phase95_surface_route.vertical_surfaces", side_effect=surfaces):
            result = propose({}, (0, 60, 0), (80, 49, 0),
                             margin=100, radius=12)
        self.assertEqual([point[1] for point in result["waypoints"]], [60, 60, 60])

    def test_segment_slots_and_journals_are_disjoint(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = Mock(root=Path(directory))
            first, second = Segment(worker, 1), Segment(worker, 2)
            first.checkpoint("save", "b0000")
            second.checkpoint("save", "b0000")
            self.assertNotEqual(first.root, second.root)
            self.assertEqual(worker.checkpoint.call_args_list[0].args, ("save", "0001b0000"))
            self.assertEqual(worker.checkpoint.call_args_list[1].args, ("save", "0002b0000"))


if __name__ == "__main__":
    unittest.main()
