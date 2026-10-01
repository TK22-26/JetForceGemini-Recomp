import tempfile
import unittest
from pathlib import Path

from scripts.phase9_update_word import compare, read, validate_update_word
from scripts.phase9_update_word_pair import native_capable, CAPABILITY_MARKER


class UpdateWordTests(unittest.TestCase):
    def test_validates_single_hashed_guest_word(self):
        self.assertEqual(validate_update_word(0x800A3294, True), 0x800A3294)
        for address, enabled in ((0x800A3295, True),
                                 (0x80400000, True),
                                 (0x800A3294, False)):
            with self.assertRaises(ValueError):
                validate_update_word(address, enabled)

    def test_pair_requires_compiled_opt_in_hook(self):
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "native.exe"
            binary.write_bytes(b"unrelated")
            self.assertFalse(native_capable(binary))
            binary.write_bytes(b"x" * (1024 * 1024 - 5) +
                               CAPABILITY_MARKER + b"y")
            self.assertTrue(native_capable(binary))

    def test_first_mismatching_update_keeps_clock_context(self):
        header = "update\tcontroller_polls\tvi\tframe\taddress\tvalue\n"
        with tempfile.TemporaryDirectory() as directory:
            native, oracle = (Path(directory) / name
                              for name in ("native.tsv", "oracle.tsv"))
            native.write_text(header +
                "1\t3\t5\t5\t0x800a3294\t0x0000001e\n"
                "2\t4\t7\t7\t0x800a3294\t0x0000001c\n",
                encoding="utf-8")
            oracle.write_text(header +
                "1\t5\t6\t6\t0x800a3294\t0x0000001e\n"
                "2\t6\t8\t8\t0x800a3294\t0x00000018\n",
                encoding="utf-8")
            report = compare(native, oracle, 0x800A3294)
            self.assertEqual(report["matching_update_prefix"], 1)
            self.assertEqual(report["first_difference"]["update"], 2)
            self.assertEqual(report["first_difference"]["native_value"],
                             "0x0000001c")
            self.assertEqual(report["first_difference"]["oracle_value"],
                             "0x00000018")
            self.assertFalse(report["parity_verified"])
            oracle.write_text(header +
                "2\t6\t8\t8\t0x800a3294\t0x00000018\n",
                encoding="utf-8")
            with self.assertRaises(ValueError):
                read(oracle, 0x800A3294)


if __name__ == "__main__":
    unittest.main()
