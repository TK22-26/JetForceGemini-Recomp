#!/usr/bin/env python3
"""Validate the local US overlay table and emit only safe aggregate facts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


EXPECTED_ROM_SHA1 = "493ced9008dbe932d6e91179b68e8630cf23a023"
EXPECTED_ROM_SIZE = 33_554_432
OVERLAY_RECORD = struct.Struct(">iiiiiHHii")
EXPECTED_TABLE_SLOTS = 157
ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL_NAME_RE = re.compile(r"^  - name:\s*(?P<name>\S+)\s*$")
TOP_LEVEL_END_RE = re.compile(r"^  - \[0x(?P<start>[0-9A-Fa-f]+)\]\s*$")
FIELD_RE = re.compile(
    r"^    (?P<field>start|vram|bss_size|exclusive_ram_id):\s*(?P<value>\S+)\s*$"
)
SUBSEGMENT_RE = re.compile(r"^      - \[0x(?P<start>[0-9A-Fa-f]+),")
OVERLAY_NAME_RE = re.compile(r"^overlay_(?P<id>\d+)$")


@dataclass(frozen=True)
class OverlayRomLayout:
    """Private coordinates required to locate the target overlay table."""

    table_start: int
    data_start: int

    @classmethod
    def from_mapping(cls, value: object) -> "OverlayRomLayout":
        if not isinstance(value, dict) or set(value) != {
            "schema_version",
            "overlay_table_start",
            "overlay_data_start",
        }:
            raise ValueError("private overlay layout has unexpected fields")
        if value.get("schema_version") != 1:
            raise ValueError("private overlay layout schema version is unsupported")
        coordinates = (value.get("overlay_table_start"), value.get("overlay_data_start"))
        if any(isinstance(item, bool) or not isinstance(item, int) for item in coordinates):
            raise ValueError("private overlay layout coordinates must be integers")
        table_start, data_start = coordinates
        assert isinstance(table_start, int) and isinstance(data_start, int)
        if table_start < 0 or data_start > EXPECTED_ROM_SIZE or data_start <= table_start:
            raise ValueError("private overlay layout coordinates are out of bounds")
        if table_start % 4 or data_start % 4:
            raise ValueError("private overlay layout coordinates must be word-aligned")
        if data_start - table_start != EXPECTED_TABLE_SLOTS * OVERLAY_RECORD.size:
            raise ValueError("private overlay layout does not describe the pinned slot count")
        return cls(table_start=table_start, data_start=data_start)


def private_input_is_safe(path: Path, *, repository_root: Path = ROOT) -> bool:
    """Accept layout files only outside the checkout or ignored by Git."""
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(repository_root.resolve())
    except ValueError:
        return True
    try:
        completed = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", relative.as_posix()],
            cwd=repository_root,
            check=False,
            capture_output=True,
        )
    except OSError:
        return False
    return completed.returncode == 0


def load_private_overlay_layout(path: Path) -> OverlayRomLayout:
    if not path.is_file():
        raise ValueError("private overlay layout file is missing")
    if not private_input_is_safe(path):
        raise ValueError("private overlay layout must be outside the repository or Git-ignored")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("private overlay layout could not be read") from error
    return OverlayRomLayout.from_mapping(value)


def digest_bytes(value: bytes, algorithm: str) -> str:
    return hashlib.new(algorithm, value).hexdigest()


def digest_file(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def parse_overlay_table(
    table: bytes,
    *,
    rom_size: int,
    data_base: int,
) -> list[dict[str, int]]:
    if len(table) % OVERLAY_RECORD.size != 0:
        raise ValueError("overlay table size is not a whole number of records")
    records: list[dict[str, int]] = []
    for zero_based, values in enumerate(OVERLAY_RECORD.iter_unpack(table)):
        (
            vram_base,
            rom_offset,
            text_size,
            data_size,
            bss_size,
            primary_relocation_bytes,
            secondary_relocation_bytes,
            _init_offset,
            _resume_offset,
        ) = values
        if min(rom_offset, text_size, data_size, bss_size) < 0:
            raise ValueError("overlay record contains a negative range field")
        if primary_relocation_bytes % 8 or secondary_relocation_bytes % 8:
            raise ValueError("overlay relocation byte size is not entry-aligned")
        if text_size == 0 and data_size == 0:
            continue
        rom_start = data_base + rom_offset
        rom_end = (
            rom_start
            + text_size
            + data_size
            + primary_relocation_bytes
            + secondary_relocation_bytes
        )
        if rom_start < data_base or rom_end < rom_start or rom_end > rom_size:
            raise ValueError("overlay ROM range is outside the supported image")
        records.append(
            {
                "id": zero_based + 1,
                "vram_base": vram_base,
                "rom_start": rom_start,
                "rom_end": rom_end,
                "text_size": text_size,
                "data_size": data_size,
                "bss_size": bss_size,
                "primary_relocation_bytes": primary_relocation_bytes,
                "secondary_relocation_bytes": secondary_relocation_bytes,
            }
        )
    if len({record["id"] for record in records}) != len(records):
        raise ValueError("overlay IDs are not unique")
    return records


def overlap_pair_count(records: list[dict[str, int]]) -> int:
    ordered = sorted(records, key=lambda item: (item["rom_start"], item["rom_end"], item["id"]))
    active: list[dict[str, int]] = []
    count = 0
    for record in ordered:
        active = [item for item in active if item["rom_end"] > record["rom_start"]]
        count += len(active)
        active.append(record)
    return count


def safe_summary(table: bytes, records: list[dict[str, int]]) -> dict[str, object]:
    if not records:
        raise ValueError("overlay table contains no populated records")
    manifest_hash = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "table_slot_count": len(table) // OVERLAY_RECORD.size,
        "populated_overlay_count": len(records),
        "empty_overlay_count": len(table) // OVERLAY_RECORD.size - len(records),
        "dynamic_vram_overlay_count": sum(record["vram_base"] == 0 for record in records),
        "fixed_vram_overlay_count": sum(record["vram_base"] != 0 for record in records),
        "all_rom_ranges_in_bounds": True,
        "text_bytes": sum(record["text_size"] for record in records),
        "data_bytes": sum(record["data_size"] for record in records),
        "bss_bytes": sum(record["bss_size"] for record in records),
        "primary_relocation_bytes": sum(
            record["primary_relocation_bytes"] for record in records
        ),
        "relocation_entry_count": sum(
            record["primary_relocation_bytes"] // 8 for record in records
        ),
        "secondary_relocation_bytes": sum(
            record["secondary_relocation_bytes"] for record in records
        ),
        "secondary_relocation_entry_count": sum(
            record["secondary_relocation_bytes"] // 8 for record in records
        ),
        # ROM overlap is an observed property of this mutually-exclusive table,
        # not an allocated ELF-section validation exception.
        "rom_overlap_pair_count": overlap_pair_count(records),
        "detailed_manifest_sha256": manifest_hash,
        "overlay_table_sha256": digest_bytes(table, "sha256"),
    }


def summarize_overlay_text(
    text: str,
    *,
    expected_count: int = 155,
    expected_slot_count: int = 157,
) -> dict[str, object]:
    """Validate pinned splat overlay ranges without publishing individual rows."""
    segments: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    terminal_start: int | None = None
    for line in text.splitlines():
        name_match = TOP_LEVEL_NAME_RE.match(line)
        if name_match:
            if current is not None:
                segments.append(current)
            current = {"name": name_match.group("name"), "subsegments": []}
            continue
        end_match = TOP_LEVEL_END_RE.match(line)
        if end_match:
            if current is not None:
                segments.append(current)
                current = None
            terminal_start = int(end_match.group("start"), 16)
            continue
        if current is None:
            continue
        field_match = FIELD_RE.match(line)
        if field_match:
            field = field_match.group("field")
            raw = field_match.group("value")
            current[field] = int(raw, 0) if field != "exclusive_ram_id" else raw
            continue
        subsegment_match = SUBSEGMENT_RE.match(line)
        if subsegment_match:
            subsegments = current["subsegments"]
            assert isinstance(subsegments, list)
            subsegments.append(int(subsegment_match.group("start"), 16))
    if current is not None:
        segments.append(current)

    for index, segment in enumerate(segments):
        if "start" not in segment:
            raise ValueError("segment is missing a ROM start")
        if index + 1 < len(segments):
            segment["end"] = segments[index + 1].get("start")
        else:
            segment["end"] = terminal_start

    overlays: list[dict[str, int | str]] = []
    for segment in segments:
        name = segment["name"]
        assert isinstance(name, str)
        overlay_match = OVERLAY_NAME_RE.fullmatch(name)
        if not overlay_match:
            continue
        required = ("start", "end", "vram", "bss_size", "exclusive_ram_id")
        if any(segment.get(field) is None for field in required):
            raise ValueError("overlay segment is missing required range metadata")
        start = int(segment["start"])
        end = int(segment["end"])
        vram = int(segment["vram"])
        bss = int(segment["bss_size"])
        if start < 0 or end <= start or vram < 0 or bss < 0:
            raise ValueError("overlay contains an invalid range")
        subsegments = segment["subsegments"]
        assert isinstance(subsegments, list)
        if (
            not subsegments
            or subsegments != sorted(set(subsegments))
            or int(subsegments[0]) != start
            or any(not start <= int(value) < end for value in subsegments)
        ):
            raise ValueError("overlay subsegment is outside its ROM range")
        if str(segment["exclusive_ram_id"]) != name:
            raise ValueError("overlay exclusive RAM identity is inconsistent")
        overlays.append(
            {
                "id": int(overlay_match.group("id")),
                "rom_start": start,
                "rom_end": end,
                "vram_start": vram,
                "vram_end": vram + (end - start) + bss,
                "exclusive_ram_id": str(segment["exclusive_ram_id"]),
            }
        )

    if len(overlays) != expected_count:
        raise ValueError("overlay count differs from the pinned baseline")
    ids = {int(overlay["id"]) for overlay in overlays}
    if len(ids) != len(overlays) or not ids or min(ids) < 1 or max(ids) != expected_slot_count:
        raise ValueError("overlay slot IDs differ from the pinned baseline")

    by_vram = sorted(overlays, key=lambda item: (int(item["vram_start"]), int(item["vram_end"])))
    for previous, current_overlay in zip(by_vram, by_vram[1:]):
        if int(current_overlay["vram_start"]) < int(previous["vram_end"]):
            raise ValueError("overlay synthetic VRAM ranges overlap unexpectedly")

    manifest_hash = hashlib.sha256(
        json.dumps(overlays, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "overlay_count": len(overlays),
        "empty_slot_count": expected_slot_count - len(overlays),
        "all_rom_ranges_well_formed": True,
        "all_synthetic_vram_ranges_nonoverlapping": True,
        "detailed_manifest_sha256": manifest_hash,
    }


def summarize_rom(path: Path, layout: OverlayRomLayout) -> dict[str, object]:
    if path.stat().st_size != EXPECTED_ROM_SIZE:
        raise ValueError("ROM size does not match the supported US image")
    if digest_file(path, "sha1") != EXPECTED_ROM_SHA1:
        raise ValueError("ROM SHA-1 does not match the supported US image")
    with path.open("rb") as stream:
        stream.seek(layout.table_start)
        table = stream.read(layout.data_start - layout.table_start)
    if len(table) != layout.data_start - layout.table_start:
        raise ValueError("overlay table could not be read")
    records = parse_overlay_table(
        table,
        rom_size=EXPECTED_ROM_SIZE,
        data_base=layout.data_start,
    )
    summary = safe_summary(table, records)
    if summary["table_slot_count"] != EXPECTED_TABLE_SLOTS:
        raise ValueError("overlay table slot count differs from the pinned baseline")
    if summary["populated_overlay_count"] != 155 or summary["empty_overlay_count"] != 2:
        raise ValueError("overlay population differs from the pinned baseline")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument(
        "--overlay-layout",
        required=True,
        type=Path,
        help="private JSON layout outside the repository or in a Git-ignored path",
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        layout = load_private_overlay_layout(arguments.overlay_layout)
        summary = summarize_rom(arguments.rom, layout)
    except (OSError, ValueError) as error:
        print(f"Overlay validation failed: {error}", file=sys.stderr)
        return 1
    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
