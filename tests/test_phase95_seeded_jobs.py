import unittest

from scripts.phase95_seeded_jobs import plan


class SeededJobsTests(unittest.TestCase):
    def test_ten_seeded_jobs_cover_all_declared_objectives(self):
        jobs = plan()
        self.assertEqual(len(jobs), 10)
        self.assertEqual([item["seed"] for item in jobs], list(range(10)))
        self.assertEqual({item["objective"] for item in jobs},
                         {"south21", "east48", "death_retry"})
        self.assertEqual(jobs, plan())

    def test_invalid_range_rejected(self):
        for seed_start, count in ((-1, 10), (0, 0), (0, 101), (True, 10)):
            with self.assertRaises(ValueError):
                plan(seed_start, count)


if __name__ == "__main__":
    unittest.main()
