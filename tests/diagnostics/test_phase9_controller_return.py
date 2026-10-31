import tempfile
import unittest
from pathlib import Path

from scripts.phase9_controller_return import HEADER, compare, read


def write(path: Path, rows: list[tuple[int, int, int, int, int, int, str]]) -> None:
    path.write_text("\t".join(HEADER) + "\n" + "\n".join(
        "\t".join(map(str, row[:5])) + f"\t0x{row[5]:08x}\t{row[6]}"
        for row in rows) + "\n", encoding="utf-8")


class ControllerReturnTests(unittest.TestCase):
    def test_same_poll_return_bytes_are_compared_without_update_shift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            native, oracle = root / "native.tsv", root / "oracle.tsv"
            data = "00" * 24
            changed = "80" + "00" * 23
            write(native, [(1, 559, 557, 1123, 1123, 0x800FB0C0, data),
                           (2, 560, 558, 1125, 1125, 0x800FB0C0, data)])
            write(oracle, [(1, 559, 553, 1219, 1248, 0x800FB0C0, data),
                           (2, 560, 554, 1221, 1250, 0x800FB0C0, changed)])
            report = compare(native, oracle, ((559, 560),))
        self.assertEqual(report["matching_shared_poll_prefix"], 1)
        self.assertEqual(report["first_same_poll_difference"]["poll"], 560)
        self.assertFalse(report["alignment_validated"])
        self.assertFalse(report["parity_verified"])

    def test_rejects_unbounded_or_malformed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.tsv"
            write(path, [(1, 559, 553, 1219, 1248, 0x800FB0C0,
                          "ff" * 23)])
            with self.assertRaises(ValueError):
                read(path, ((559, 560),))
            write(path, [(1, 559, 553, 1219, 1248, 0x800FB0C0,
                          "ff" * 24)])
            with self.assertRaises(ValueError):
                read(path, ((0, 100),))
            with self.assertRaises(ValueError):
                read(path, ((560, 561),))


if __name__ == "__main__":
    unittest.main()
