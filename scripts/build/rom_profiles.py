"""Canonical ROM identity and independently controlled native build admission."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "config/roms/revisions.json"
ADMISSION_PATH = ROOT / "config/roms/native-build-admission.json"

@dataclass(frozen=True)
class RomProfile:
    code: str
    title: str
    sha1: str
    country: int
    revision_id: str
    revision: int
    size: int
    extraction_recipe: str

    @property
    def native_supported(self) -> bool:
        """Compatibility API for native build admission, never gameplay acceptance."""
        return NATIVE_ADMISSION[self.revision_id]

def parse_catalog(value: Any) -> tuple[RomProfile, ...]:
    if not isinstance(value, dict) or set(value) != {"schema_version", "revisions"} or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("Unsupported ROM catalog schema.")
    rows = value["revisions"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("ROM catalog must contain revisions.")
    fields = {"id", "code", "title", "sha1", "country", "revision", "size", "byte_order", "extraction_recipe"}
    seen = {key: set() for key in ("id", "code", "sha1")}
    profiles = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != fields:
            raise ValueError("Unexpected ROM catalog fields.")
        for key, pattern in (("id", r"[a-z][a-z0-9-]+"), ("code", r"[a-z][a-z0-9]*"),
                             ("sha1", r"[0-9a-f]{40}"), ("country", r"[A-Z]"),
                             ("extraction_recipe", r"[a-z][a-z0-9-]+")):
            if not isinstance(row[key], str) or not re.fullmatch(pattern, row[key]):
                raise ValueError("Invalid ROM catalog " + key + ".")
        if not isinstance(row["title"], str) or not row["title"].strip() or any(ord(ch) < 32 for ch in row["title"]):
            raise ValueError("Invalid ROM title.")
        if type(row["size"]) is not int or row["size"] < 64 or row["size"] % 4:
            raise ValueError("Invalid ROM size.")
        if type(row["revision"]) is not int or not 0 <= row["revision"] <= 255 or row["byte_order"] != "big-endian":
            raise ValueError("Invalid ROM revision or canonical byte order.")
        for key, values in seen.items():
            if row[key] in values:
                raise ValueError("Duplicate ROM catalog " + key + ".")
            values.add(row[key])
        profiles.append(RomProfile(row["code"], row["title"], row["sha1"], ord(row["country"]),
                                   row["id"], row["revision"], row["size"], row["extraction_recipe"]))
    return tuple(profiles)

def parse_admission(value: Any, profiles: tuple[RomProfile, ...]) -> dict[str, bool]:
    if not isinstance(value, dict) or set(value) != {"schema_version", "native_builds", "scope"} or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("Unsupported native admission schema.")
    rows = value["native_builds"]
    if not isinstance(rows, dict) or set(rows) != {p.revision_id for p in profiles}:
        raise ValueError("Native admission does not match the ROM catalog.")
    result = {}
    for revision, row in rows.items():
        if not isinstance(row, dict) or set(row) != {"admitted", "evidence"} or type(row["admitted"]) is not bool:
            raise ValueError("Invalid native admission entry.")
        evidence = row["evidence"]
        if not isinstance(evidence, str) or not evidence.startswith("docs/") or ".." in evidence.split("/") or "\\" in evidence:
            raise ValueError("Invalid native admission evidence reference.")
        result[revision] = row["admitted"]
    if not isinstance(value["scope"], str) or not value["scope"].strip():
        raise ValueError("Native admission needs a scope.")
    return result

ROM_PROFILES = parse_catalog(json.loads(CATALOG_PATH.read_text(encoding="utf-8")))
NATIVE_ADMISSION = parse_admission(json.loads(ADMISSION_PATH.read_text(encoding="utf-8")), ROM_PROFILES)
PROFILES_BY_CODE = {p.code: p for p in ROM_PROFILES}
PROFILES_BY_ID = {p.revision_id: p for p in ROM_PROFILES}
US_ROM, PAL_ROM, JAPAN_ROM = (PROFILES_BY_CODE[code] for code in ("us", "pal", "jpn"))
# Legacy size API remains for existing consumers; actual identity uses each profile's size.
ROM_SIZE = US_ROM.size

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
    if len(data) not in {profile.size for profile in ROM_PROFILES}:
        raise ValueError("ROM size does not match a recognized original revision.")
    image, byte_order = normalize_byte_order(data)
    if byte_order != "big-endian" and not normalize:
        raise ValueError("This native build requires a big-endian .z64 ROM.")
    digest = hashlib.sha1(image).hexdigest()
    for profile in ROM_PROFILES:
        if profile.sha1 == digest and len(image) == profile.size:
            if image[0x3E] != profile.country or image[0x3F] != profile.revision:
                raise ValueError("ROM profile/header mismatch.")
            return profile, image, byte_order
    raise ValueError("ROM checksum does not match a recognized US, PAL or Japanese revision.")

def require_native_rom(data: bytes) -> RomProfile:
    profile, _, _ = identify_rom(data)
    if not profile.native_supported:
        raise ValueError(profile.title + " is recognized, but its native runtime is not supported yet. "
                         "Matching regional metadata does not supply generated overlays or regional host hooks.")
    return profile
