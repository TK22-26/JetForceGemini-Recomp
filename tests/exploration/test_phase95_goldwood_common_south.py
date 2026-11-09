"""Reviewed route composition must reject missing or misordered checkpoints."""
import unittest

from scripts.phase95_goldwood_common_south import SEGMENTS, validate_chain


class CommonSouthLineageTests(unittest.TestCase):
    def test_complete_adjacent_lineage(self):
        endpoints = [f"endpoint-{index}" for index in range(len(SEGMENTS))]
        entries = ["settled", *endpoints[:-1]]
        validate_chain("settled", endpoints, entries)

    def test_skipped_chunk_is_rejected(self):
        endpoints = [f"endpoint-{index}" for index in range(len(SEGMENTS))]
        entries = ["settled", *endpoints[:-1]]
        entries[-1] = endpoints[7]
        with self.assertRaisesRegex(ValueError, "does not join its predecessor"):
            validate_chain("settled", endpoints, entries)

    def test_incomplete_lineage_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate_chain("settled", ["endpoint"], ["settled"])


if __name__ == "__main__":
    unittest.main()
