"""Insert native logical FlashRAM into a BizHawk Mupen64Plus SaveRAM template.

Layout and byte order follow pinned BizHawk libmupen64plus pif.c save_saveram
and flashram.c dma_read_flashram (S8=3 on the supported little-endian host).
Other save devices are preserved, not claimed equivalent to native Pak state.
"""
import argparse
import hashlib
import json
from pathlib import Path

FLASH_SIZE = 0x20000
FLASH_OFFSET = 0x800 + 4 * 0x8000
SAVERAM_SIZE = FLASH_OFFSET + FLASH_SIZE + 0x8000
MEMPAK_OFFSET = 0x800
MEMPAK_SIZE = 0x8000
MEMPAK_PORTS = 4


def swap_words(data: bytes) -> bytes:
    if len(data) % 4:
        raise ValueError("word-swapped data must have a multiple-of-four size")
    return b"".join(data[i:i + 4][::-1] for i in range(0, len(data), 4))


def prepare(template: bytes, flash: bytes) -> bytes:
    if len(template) != SAVERAM_SIZE:
        raise ValueError("unexpected Mupen64Plus SaveRAM size")
    if len(flash) != FLASH_SIZE:
        raise ValueError("unexpected native FlashRAM size")
    return (template[:FLASH_OFFSET] + swap_words(flash)
            + template[FLASH_OFFSET + FLASH_SIZE:])


def inspect_mupen_saveram(image: bytes) -> dict:
    """Hash each raw device without equating Mupen Pak bytes to native notes."""
    if len(image) != SAVERAM_SIZE or \
            MEMPAK_OFFSET + MEMPAK_PORTS * MEMPAK_SIZE != FLASH_OFFSET:
        raise ValueError("unexpected Mupen64Plus SaveRAM layout")
    sha256 = lambda value: hashlib.sha256(value).hexdigest()
    mempaks = [image[MEMPAK_OFFSET + port * MEMPAK_SIZE:
                     MEMPAK_OFFSET + (port + 1) * MEMPAK_SIZE]
                for port in range(MEMPAK_PORTS)]
    return {
        "kind": "jfg-phase9-mupen-saveram-regions", "schema": 1,
        "image_sha256": sha256(image),
        "eeprom_sha256": sha256(image[:MEMPAK_OFFSET]),
        "mempak_port_sha256": [sha256(pak) for pak in mempaks],
        "flash_logical_sha256": sha256(swap_words(
            image[FLASH_OFFSET:FLASH_OFFSET + FLASH_SIZE])),
        "sram_sha256": sha256(image[FLASH_OFFSET + FLASH_SIZE:]),
        "native_pak_equivalence_validated": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", type=Path)
    parser.add_argument("native_flash", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    template, flash = args.template.read_bytes(), args.native_flash.read_bytes()
    result = prepare(template, flash)
    # Never overwrite a save or silently replace the provenance source.
    with args.output.open("xb") as stream:
        stream.write(result)
    digest = lambda value: hashlib.sha256(value).hexdigest()
    print(json.dumps({"template_sha256": digest(template),
                      "native_flash_sha256": digest(flash),
                      "oracle_saveram_sha256": digest(result),
                      "flash_offset": FLASH_OFFSET,
                      "flash_byte_order": "word-swapped-32",
                      "other_devices": "preserved-from-template"}, sort_keys=True))


if __name__ == "__main__":
    main()
