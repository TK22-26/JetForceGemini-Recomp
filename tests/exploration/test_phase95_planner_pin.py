import tempfile
from pathlib import Path
import unittest

from scripts.phase95_planner_pin import source_pin


class PlannerPinTests(unittest.TestCase):
    def test_pin_is_order_independent_and_detects_source_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first, second = root / "a.py", root / "b.py"
            first.write_text("a = 1\n")
            second.write_text("b = 2\n")
            baseline = source_pin((first, second))
            self.assertEqual(baseline, source_pin((second, first)))
            second.write_text("b = 3\n")
            self.assertNotEqual(baseline["sha256"], source_pin((first, second))["sha256"])
            with self.assertRaisesRegex(ValueError, "unique"):
                source_pin((first, first))

    def test_default_pin_covers_frontier_and_search_code(self):
        files = source_pin()["files"]
        self.assertIn("phase95_frontier_job.py", files)
        self.assertIn("phase95_explore.py", files)
        self.assertIn("phase95_planner_pin.py", files)


if __name__ == "__main__":
    unittest.main()
