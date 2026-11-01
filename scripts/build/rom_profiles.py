"""Exact original ROM identities. Recognition is separate from native support."""
from dataclasses import dataclass
import hashlib

ROM_SIZE = 32 * 1024 * 1024

@dataclass(frozen=True)
class RomProfile:
    code: str
    title: str
    sha1: str
    country: int
    native_supported: bool = False

US_ROM = RomProfile("us", "Jet Force Gemini (USA)",
    "493ced9008dbe932d6e91179b68e8630cf23a023", ord("E"), True)
PAL_ROM = RomProfile("pal", "Jet Force Gemini (Europe)",
    "50651c4e0c46332f7f0b45870263f0a8b9a49602", ord("P"))
JAPAN_ROM = RomProfile("jpn", "Star Twins (Japan)",
    "15099233760b36e7afad7da36b9464da1512c4b1", ord("J"))
ROM_PROFILES = (US_ROM, PAL_ROM, JAPAN_ROM)


def normalize_byte_order(data: bytes) -> tuple[bytes, str]:
    """Return big-endian bytes without changing the input or guessing from its name."""
    if len(data) < 4 or len(data) % 4:
        raise ValueError("ROM bytes must contain complete 32-bit words.")
    magic = data[:4]
    if magic == bytes.fromhex("80371240"):
        return data, "big-endian"
    output = bytearray(len(data))
    if magic == bytes.fromhex("37804012"):
        output[0::2], output[1::2] = data[1::2], data[0::2]
        return bytes(output), "byte-swapped"
    if magic == bytes.fromhex("40123780"):
        for index in range(4):
            output[index::4] = data[3-index::4]
        return bytes(output), "little-endian"
    raise ValueError("Unrecognized N64 byte-order marker.")


def identify_rom(data: bytes, *, normalize: bool = False) -> tuple[RomProfile, bytes, str]:
    if len(data) != ROM_SIZE:
        raise ValueError("The supported original ROM revisions are exactly 32 MiB.")
    image, byte_order = normalize_byte_order(data)
    if byte_order != "big-endian" and not normalize:
        raise ValueError("This native build requires a big-endian .z64 ROM.")
    digest = hashlib.sha1(image).hexdigest()
    for profile in ROM_PROFILES:
        if profile.sha1 == digest:
            # Hash identity includes header region and revision; check the contract explicitly.
            if image[0x3E] != profile.country or image[0x3F] != 0:
                raise ValueError("ROM profile/header mismatch.")
            return profile, image, byte_order
    raise ValueError("ROM checksum does not match a recognized US, PAL or Japanese revision.")


def require_native_rom(data: bytes) -> RomProfile:
    profile, _, _ = identify_rom(data)
    if not profile.native_supported:
        raise ValueError(profile.title + " is recognized, but its native runtime is not supported yet. "
                         "Matching regional metadata does not supply generated overlays or regional host hooks.")
    return profile
