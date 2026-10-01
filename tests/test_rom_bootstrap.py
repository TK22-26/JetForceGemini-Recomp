"""ROM-free checks for bootstrap validation and local configuration derivation."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_from_rom import validate_rom
from generate_from_rom import audio_configuration, derive_layout
from identify_libultra import identify


class BootstrapTests(unittest.TestCase):
    def test_live_boot_device_services_are_intercepted(self):
        # Synthetic addresses exercise identification without a ROM or symbol map.
        services = ("__osSiRawStartDma", "bzero", "osCic6105SendData",
                    "osCic6105StartGetData", "osFlashAllErase", "osFlashClearStatus",
                    "osFlashInit", "osFlashReInit", "osFlashReadArray", "osFlashReadId",
                    "osFlashReadStatus", "osFlashSectorErase", "osFlashWriteArray",
                    "osFlashWriteBuffer")
        symbols = {name: 0x80001000 + i * 0x20 for i, name in enumerate(services)}
        generated = {address: f"fn_{address:08x}" for address in symbols.values()}
        result = identify(symbols, generated)
        self.assertEqual(result["mapped_to_generated"], len(services))
        self.assertEqual({entry["libultra"] for entry in result["detail"]["identified"]},
                         set(services))
        self.assertEqual(identify(symbols, {})["mapped_to_generated"], 0)

    def test_missing_rom_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                validate_rom(Path(directory) / "absent.z64")

    def test_correct_size_wrong_rom_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            rom = Path(directory) / "fixture.z64"
            with rom.open("wb") as stream:
                stream.truncate(32 * 1024 * 1024)
            with self.assertRaises(ValueError):
                validate_rom(rom)

    def audio_fixture(self):
        # Synthetic descriptors and dispatch targets; no game bytes.
        primary_address, secondary_address = 0x1100, 0x1300
        primary_size, secondary_size = 0xF00, 0x500
        data = struct.pack(">4I", 0, (primary_size - 1) << 16 | primary_address,
                           primary_size, (secondary_size - 1) << 16 | secondary_address)
        data += struct.pack(">16H", *range(0x1400, 0x1440, 4)) + b"\x00\x00"
        return bytes(primary_size + secondary_size), data

    def test_audio_config_uses_descriptors(self):
        program, data = self.audio_fixture()
        import tomllib
        config = tomllib.loads(audio_configuration(program, data))
        self.assertEqual(config["text_size"], 0xF00)
        self.assertEqual(config["overlay_slots"][0]["overlays"],
                         [{"offset": 0x200, "size": 0xD00}, {"offset": 0xF00, "size": 0x500}])

    def test_audio_truncation_and_inconsistent_descriptors_rejected(self):
        program, data = self.audio_fixture()
        for broken_program, broken_data in ((program[:-4], data), (program, data[:8]),
                (program, b"\x00\x00\x00\x04" + data[4:]),
                (program, data[:16] + b"\x00\x00" + data[18:])):
            with self.subTest(), self.assertRaises(ValueError):
                audio_configuration(broken_program, broken_data)

    def test_audio_alignment_padding_is_not_an_extra_dma_payload(self):
        program, data = self.audio_fixture()
        data = data[:12] + struct.pack(">I", (0x500 - 8 - 1) << 16 | 0x1300) + data[16:]
        import tomllib
        config = tomllib.loads(audio_configuration(program, data))
        self.assertEqual(config["overlay_slots"][0]["overlays"][1]["size"], 0x500)
        with self.assertRaisesRegex(ValueError, "alignment padding"):
            audio_configuration(program[:-1] + b"\x01", data)

    def test_layout_requires_unique_linker_boundaries(self):
        with self.assertRaisesRegex(ValueError, "Missing or ambiguous"):
            derive_layout(b"", "", {})


if __name__ == "__main__":
    unittest.main()
