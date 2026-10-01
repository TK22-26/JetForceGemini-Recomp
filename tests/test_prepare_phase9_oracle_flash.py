import unittest
import hashlib

from scripts.prepare_phase9_oracle_flash import (
    FLASH_OFFSET, FLASH_SIZE, MEMPAK_OFFSET, MEMPAK_SIZE, SAVERAM_SIZE,
    inspect_mupen_saveram, prepare, swap_words,
)


class OracleFlashTests(unittest.TestCase):
    def test_layout_and_logical_round_trip(self):
        template = b"\xa5" * SAVERAM_SIZE
        flash = bytes(range(256)) * (FLASH_SIZE // 256)
        result = prepare(template, flash)
        self.assertEqual(result[:FLASH_OFFSET], template[:FLASH_OFFSET])
        self.assertEqual(result[FLASH_OFFSET + FLASH_SIZE:],
                         template[FLASH_OFFSET + FLASH_SIZE:])
        encoded = result[FLASH_OFFSET:FLASH_OFFSET + FLASH_SIZE]
        self.assertEqual(encoded[:4], b"\x03\x02\x01\x00")
        self.assertEqual(swap_words(encoded), flash)

    def test_reject_wrong_sizes(self):
        for template, flash in ((b"", b"\0" * FLASH_SIZE),
                                (b"\0" * SAVERAM_SIZE, b"")):
            with self.assertRaises(ValueError):
                prepare(template, flash)
        with self.assertRaises(ValueError):
            swap_words(b"123")

    def test_saveram_inventory_keeps_raw_pak_distinct_from_native_notes(self):
        image = bytearray(SAVERAM_SIZE)
        image[MEMPAK_OFFSET] = 0xA5
        image[MEMPAK_OFFSET + MEMPAK_SIZE] = 0x5A
        image[FLASH_OFFSET:FLASH_OFFSET + 4] = b"\x03\x02\x01\x00"
        report = inspect_mupen_saveram(bytes(image))
        sha = lambda value: hashlib.sha256(value).hexdigest()
        self.assertEqual(report["image_sha256"], sha(image))
        self.assertNotEqual(report["mempak_port_sha256"][0],
                            report["mempak_port_sha256"][1])
        self.assertEqual(report["mempak_port_sha256"][2],
                         report["mempak_port_sha256"][3])
        logical_flash = b"\x00\x01\x02\x03" + bytes(FLASH_SIZE - 4)
        self.assertEqual(report["flash_logical_sha256"], sha(logical_flash))
        self.assertFalse(report["native_pak_equivalence_validated"])
        with self.assertRaises(ValueError):
            inspect_mupen_saveram(bytes(image[:-1]))


if __name__ == "__main__":
    unittest.main()
