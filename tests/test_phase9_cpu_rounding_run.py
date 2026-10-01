from pathlib import Path
import tempfile
import unittest

from scripts.phase9_cpu_rounding_run import parse_trace


class CpuRoundingRunTests(unittest.TestCase):
    def test_parses_complete_manual_and_conflicting_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cpu-rounding.tsv"
            header = "status\tframe\toperand_bits\tconverted_word\tfcr31\tmarker\n"
            for word, expected in (("0x0000022e", True), ("0x0000022f", False)):
                path.write_text(header +
                                f"complete\t3\t0x440ba000\t{word}\t"
                                "0x00000004\t0x4a464743\n", encoding="utf-8")
                observed = parse_trace(path)
                self.assertEqual(observed["matches_vr4300_manual"], expected)
                self.assertEqual(observed["rounding_mode"], 0)

    def test_rejects_missing_marker_and_wrong_rounding_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "cpu-rounding.tsv"
            prefix = "status\tframe\toperand_bits\tconverted_word\tfcr31\tmarker\n"
            for row in ("not_reached\t180\n",
                        "complete\t3\t0x440ba000\t0x0000022e\t0x1\t0x4a464743\n"):
                path.write_text(prefix + row, encoding="utf-8")
                with self.assertRaises(ValueError):
                    parse_trace(path)


if __name__ == "__main__":
    unittest.main()
