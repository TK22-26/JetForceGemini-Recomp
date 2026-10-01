#!/usr/bin/env python3
"""Validate JFG's custom overlay linker metadata and emit safe aggregates."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .check_repository_hygiene import scan_blob
    from .probe_n64recomp_cpu import verify_private_work_directory
    from .public_safe import validate_canonical_json_numbers, validate_public_safe
except ImportError:  # Direct script execution.
    from check_repository_hygiene import scan_blob
    from probe_n64recomp_cpu import verify_private_work_directory
    from public_safe import validate_canonical_json_numbers, validate_public_safe


EXPECTED_ROM_SHA1 = "493ced9008dbe932d6e91179b68e8630cf23a023"
EXPECTED_ROM_SIZE = 33_554_432
HEADER = struct.Struct(">iiiiiHHii")
RELOCATION = struct.Struct(">II")
VALID_SOURCE_TYPES = {0, 1, 2, 3}
VALID_PATCH_TYPES = {2, 4, 5, 6}
INSTRUCTION_PATCH_TYPES = {4, 5, 6}
EXPECTED_JFG_DECOMP_COMMIT = "b49aa4791e8fb1e7acd3bba10346876358d0a9a7"
EXPECTED_N64RECOMP_COMMIT = "ffb39cdad1da5de07eaaa48bd1db4a89a7986771"
EXPECTED_N64RECOMP_SHA256 = "34958d6ae8c047adb772090c75fdcc051036646a1db58595694f814c3a4a09b6"
EXPECTED_ELF_SHA256 = "ea06a1f7fd54454fbf65f9dbe0bb6d731d5a44f732c16c8d157b475cb8078f1b"
EXPECTED_PHASE3_PUBLIC_AGGREGATE_SHA256 = (
    "c4b6836a476e20491413f9f4a6876c838ff958a4b78aa6dc859bb92a19959f46"
)


@dataclass(frozen=True)
class RomLayout:
    """Private locations needed to find the custom linker records."""

    main_relocation_start: int
    overlay_reference_table_start: int
    overlay_table_start: int
    overlay_data_start: int
    main_text_size: int
    main_data_size: int

    @classmethod
    def from_json(cls, value: object) -> "RomLayout":
        if not isinstance(value, dict):
            raise ValueError("private ROM layout must be a JSON object")
        expected = {
            "schema_version",
            "main_relocation_start",
            "overlay_reference_table_start",
            "overlay_table_start",
            "overlay_data_start",
            "main_text_size",
            "main_data_size",
        }
        if set(value) != expected:
            raise ValueError("private ROM layout has missing or unknown fields")
        if value["schema_version"] != 1:
            raise ValueError("private ROM layout schema version is unsupported")
        names = expected - {"schema_version"}
        if any(type(value[name]) is not int for name in names):
            raise ValueError("private ROM layout fields must be integers")
        layout = cls(**{name: value[name] for name in names})
        layout.validate()
        return layout

    def validate(self) -> None:
        offsets = (
            self.main_relocation_start,
            self.overlay_reference_table_start,
            self.overlay_table_start,
            self.overlay_data_start,
        )
        if any(offset < 0 or offset > EXPECTED_ROM_SIZE for offset in offsets):
            raise ValueError("private ROM layout offset is outside the supported ROM")
        if offsets != tuple(sorted(offsets)) or len(set(offsets)) != len(offsets):
            raise ValueError("private ROM layout regions are not strictly ordered")
        if any(offset % 4 for offset in offsets):
            raise ValueError("private ROM layout offsets must be word-aligned")
        if self.overlay_data_start - self.overlay_table_start != 157 * HEADER.size:
            raise ValueError("private ROM layout overlay table extent is invalid")
        if self.main_text_size <= 0 or self.main_data_size <= 0:
            raise ValueError("private ROM layout main extents must be positive")


def load_private_layout(path: Path) -> RomLayout:
    """Load a detailed layout only from an ignored or external path."""
    verify_private_artifact_path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"private ROM layout is invalid JSON: {error.msg}") from error
    return RomLayout.from_json(value)


def verify_private_artifact_path(path: Path) -> None:
    """Require private analyzer inputs and outputs to be ignored or external."""
    verify_private_work_directory(path)


@dataclass(frozen=True)
class OverlayHeader:
    slot: int
    vram_base: int
    rom_offset: int
    text_size: int
    data_size: int
    bss_size: int
    primary_bytes: int
    secondary_bytes: int
    init_offset: int
    resume_offset: int

    @property
    def populated(self) -> bool:
        return self.text_size + self.data_size != 0

    def rom_start(self, layout: RomLayout) -> int:
        return layout.overlay_data_start + self.rom_offset

    def primary_start(self, layout: RomLayout) -> int:
        return self.rom_start(layout) + self.text_size + self.data_size

    def secondary_start(self, layout: RomLayout) -> int:
        return self.primary_start(layout) + self.primary_bytes

    def rom_end(self, layout: RomLayout) -> int:
        return self.secondary_start(layout) + self.secondary_bytes

    @property
    def memory_size(self) -> int:
        return self.text_size + self.data_size + self.bss_size


@dataclass(frozen=True)
class ActiveOverlay:
    """One published guest-code range and its non-reusable lifetime token."""

    overlay_id: str
    guest_base: int
    text_size: int
    generation: int


@dataclass(frozen=True)
class OverlayPointer:
    """A guest-code reference that is valid for exactly one overlay lifetime."""

    overlay_id: str
    generation: int
    offset: int


class ActiveOverlayRegistry:
    """Fail-closed registry for dynamic overlay code ranges.

    Generations are monotonic per opaque overlay ID. Consequently, unloading and
    reloading the same overlay at the same guest address cannot make an old
    pointer valid again.
    """

    def __init__(self) -> None:
        self._active: dict[str, ActiveOverlay] = {}
        self._last_generation: dict[str, int] = {}

    def publish(self, overlay_id: str, guest_base: int, text_size: int) -> ActiveOverlay:
        if not overlay_id:
            raise ValueError("overlay ID must not be empty")
        if overlay_id in self._active:
            raise ValueError("overlay is already active")
        if guest_base < 0 or guest_base > 0xFFFFFFFF:
            raise ValueError("overlay guest base is outside the 32-bit guest address space")
        if text_size <= 0:
            raise ValueError("overlay text size must be positive")
        guest_end = guest_base + text_size
        if guest_end > 0x1_0000_0000:
            raise ValueError("overlay code range exceeds the 32-bit guest address space")
        for active in self._active.values():
            active_end = active.guest_base + active.text_size
            if guest_base < active_end and active.guest_base < guest_end:
                raise ValueError("active overlay code ranges overlap")

        generation = self._last_generation.get(overlay_id, 0) + 1
        active = ActiveOverlay(overlay_id, guest_base, text_size, generation)
        self._active[overlay_id] = active
        self._last_generation[overlay_id] = generation
        return active

    def unpublish(self, overlay_id: str, expected_generation: int) -> ActiveOverlay:
        active = self._active.get(overlay_id)
        if active is None:
            raise ValueError("overlay is not active")
        if active.generation != expected_generation:
            raise ValueError("stale overlay generation")
        del self._active[overlay_id]
        return active

    def resolve_address(self, address: int) -> OverlayPointer | None:
        for active in self._active.values():
            if active.guest_base <= address < active.guest_base + active.text_size:
                return OverlayPointer(
                    active.overlay_id,
                    active.generation,
                    address - active.guest_base,
                )
        return None

    def resolve_pointer(self, pointer: OverlayPointer) -> int:
        active = self._active.get(pointer.overlay_id)
        if active is None or active.generation != pointer.generation:
            raise ValueError("stale overlay pointer")
        if not 0 <= pointer.offset < active.text_size:
            raise ValueError("overlay pointer offset is outside active code")
        return active.guest_base + pointer.offset


def file_digest(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_headers(data: bytes, layout: RomLayout) -> list[OverlayHeader]:
    if len(data) % HEADER.size:
        raise ValueError("overlay header table is not record-aligned")
    headers = [
        OverlayHeader(slot, *values)
        for slot, values in enumerate(HEADER.iter_unpack(data), start=1)
    ]
    if len(headers) != 157:
        raise ValueError("overlay header slot count differs from the pinned baseline")
    for header in headers:
        if min(
            header.rom_offset,
            header.text_size,
            header.data_size,
            header.bss_size,
            header.primary_bytes,
            header.secondary_bytes,
        ) < 0:
            raise ValueError("overlay header contains a negative range")
        if header.primary_bytes % RELOCATION.size or header.secondary_bytes % RELOCATION.size:
            raise ValueError("overlay relocation byte size is not entry-aligned")
        if header.populated:
            if not (
                layout.overlay_data_start
                <= header.rom_start(layout)
                < header.rom_end(layout)
                <= EXPECTED_ROM_SIZE
            ):
                raise ValueError("overlay content is outside the supported ROM")
            for offset in (header.init_offset, header.resume_offset):
                if offset != -1 and not 0 <= offset < header.text_size:
                    raise ValueError("overlay callback offset is outside executable text")
    populated = sorted(
        (header for header in headers if header.populated),
        key=lambda item: (item.rom_start(layout), item.rom_end(layout)),
    )
    if len(populated) != 155:
        raise ValueError("overlay population differs from the pinned baseline")
    if any(
        current.rom_start(layout) < previous.rom_end(layout)
        for previous, current in zip(populated, populated[1:])
    ):
        raise ValueError("overlay ROM ranges overlap")
    return headers


def parse_relocations(data: bytes) -> list[tuple[int, int]]:
    if len(data) % RELOCATION.size:
        raise ValueError("relocation table is not record-aligned")
    return list(RELOCATION.iter_unpack(data))


def relocation_fields(entry: tuple[int, int]) -> tuple[int, int, int, int]:
    symbol_index, info = entry
    return symbol_index, info >> 8, (info >> 4) & 0xF, info & 0xF


def apply_patch_word(word: int, address: int, patch_type: int) -> int:
    """Model the four word mutations used by the custom runtime linker."""
    if patch_type == 2:
        return address & 0xFFFFFFFF
    if patch_type == 4:
        return (word & 0xFC000000) | ((address >> 2) & 0x03FFFFFF)
    if patch_type == 5:
        return (word & 0xFFFF0000) | (((address + 0x8000) >> 16) & 0xFFFF)
    if patch_type == 6:
        return (word & 0xFFFF0000) | (address & 0xFFFF)
    raise ValueError("unsupported relocation patch type")


def lookup_active_overlay(
    address: int, active_ranges: list[tuple[str, int, int]]
) -> tuple[str, int] | None:
    """Compatibility wrapper around the checked registry model."""
    registry = ActiveOverlayRegistry()
    for overlay_id, base, text_size in active_ranges:
        registry.publish(overlay_id, base, text_size)
    pointer = registry.resolve_address(address)
    return None if pointer is None else (pointer.overlay_id, pointer.offset)


def analyze_hi_lo_sequences(entries: list[tuple[int, int]]) -> collections.Counter[str]:
    """Describe the runtime linker's exact HI16/LO16 consumption semantics.

    A HI16 record causes the game to consume the immediately following record as
    its LO16 half. Standalone LO16 records are also supported by the linker, so
    they are counted explicitly rather than mislabeled as invalid pairs.
    """
    counts: collections.Counter[str] = collections.Counter(
        {
            "paired_hi16_lo16_count": 0,
            "unpaired_hi16_count": 0,
            "standalone_lo16_count": 0,
            "hi16_lo16_reference_mismatch_count": 0,
            "hi16_lo16_same_patch_target_count": 0,
        }
    )
    index = 0
    while index < len(entries):
        symbol, target, patch_type, source = relocation_fields(entries[index])
        if patch_type == 5:
            if index + 1 >= len(entries):
                counts["unpaired_hi16_count"] += 1
                index += 1
                continue
            lo_symbol, lo_target, lo_patch_type, lo_source = relocation_fields(
                entries[index + 1]
            )
            if lo_patch_type != 6:
                counts["unpaired_hi16_count"] += 1
                index += 1
                continue
            counts["paired_hi16_lo16_count"] += 1
            counts["hi16_lo16_reference_mismatch_count"] += (
                symbol != lo_symbol or source != lo_source
            )
            counts["hi16_lo16_same_patch_target_count"] += target == lo_target
            index += 2
        elif patch_type == 6:
            counts["standalone_lo16_count"] += 1
            index += 1
        else:
            index += 1
    return counts


def classify_ort_target(word: int) -> str:
    overlay = word >> 20
    if overlay == 0:
        return "main"
    if 1 <= overlay <= 157:
        return "overlay"
    if overlay in {0xFFD, 0xFFE}:
        return "main-data"
    if overlay == 0xFFF:
        return "main-bss"
    if overlay == 0xFFC:
        return "special-reserved"
    return "anomalous"


def counter_dict(counter: collections.Counter[int | str]) -> dict[str, int]:
    return {str(key): counter[key] for key in sorted(counter, key=str)}


def validate_table_count_reconciliation(
    tables: dict[str, collections.Counter[int]],
    aggregate: collections.Counter[int],
    expected_totals: dict[str, int],
    label: str,
) -> None:
    """Require every per-table diagnostic count to reconcile before omission."""
    if set(tables) != set(expected_totals):
        raise ValueError(f"{label} table names differ from the expected inventory")
    combined: collections.Counter[int] = collections.Counter()
    for table_name, expected_total in expected_totals.items():
        counts = tables[table_name]
        if sum(counts.values()) != expected_total:
            raise ValueError(f"{label} counts for {table_name} do not match its table")
        combined.update(counts)
    if combined != aggregate:
        raise ValueError(f"{label} per-table counts do not match the aggregate")


def validate_public_overlay_aggregate(value: object) -> None:
    """Fail closed if analyzer output grows a private or unreviewed channel."""

    if not isinstance(value, dict):
        raise ValueError("public overlay aggregate must be an object")

    def require_exact_keys(
        candidate: object, expected: set[str], location: str
    ) -> dict[str, object]:
        if not isinstance(candidate, dict) or set(candidate) != expected:
            raise ValueError(f"{location} has missing or unreviewed public fields")
        return candidate

    require_exact_keys(
        value,
        {
            "schema_version",
            "kind",
            "privacy",
            "overlay_headers",
            "reference_table",
            "relocations",
            "dependencies",
            "detailed_inventory_sha256",
        },
        "$",
    )
    require_exact_keys(
        value["overlay_headers"],
        {
            "slot_count",
            "populated_count",
            "empty_count",
            "dynamic_vram_count",
            "fixed_vram_count",
            "init_callback_count",
            "resume_callback_count",
            "invalid_callback_count",
            "rom_overlap_pair_count",
        },
        "$.overlay_headers",
    )
    require_exact_keys(
        value["reference_table"],
        {
            "entry_count",
            "target_class_counts",
            "invalid_overlay_number_count",
            "invalid_overlay_offset_count",
            "empty_overlay_target_count",
        },
        "$.reference_table",
    )
    relocations = require_exact_keys(
        value["relocations"],
        {
            "main_entry_count",
            "primary_entry_count",
            "secondary_entry_count",
            "total_entry_count",
            "source_type_counts",
            "patch_type_counts",
            "external_target_class_counts",
            "unknown_source_type_count",
            "unknown_patch_type_count",
            "invalid_symbol_index_count",
            "invalid_local_offset_count",
            "invalid_patch_target_count",
            "unaligned_patch_target_count",
            "paired_hi16_lo16_count",
            "unpaired_hi16_count",
            "standalone_lo16_count",
            "hi16_lo16_reference_mismatch_count",
            "hi16_lo16_same_patch_target_count",
            "referenced_anomaly_count",
        },
        "$.relocations",
    )
    require_exact_keys(
        value["dependencies"],
        {
            "main_to_overlay_edge_count",
            "overlay_to_overlay_edge_count",
            "self_overlay_reference_count",
        },
        "$.dependencies",
    )

    source_keys = {"0", "1", "2", "3"}
    patch_keys = {"2", "4", "5", "6"}
    target_keys = {
        "main",
        "overlay",
        "main-data",
        "main-bss",
        "special-reserved",
        "anomalous",
    }
    if set(relocations["source_type_counts"]) != source_keys:
        raise ValueError("public source-type aggregate is incomplete or unknown")
    if set(relocations["patch_type_counts"]) != patch_keys:
        raise ValueError("public patch-type aggregate is incomplete or unknown")
    if set(value["reference_table"]["target_class_counts"]) != target_keys:
        raise ValueError("public reference target classes are incomplete or unknown")
    if set(relocations["external_target_class_counts"]) != target_keys:
        raise ValueError("public relocation target classes are incomplete or unknown")
    def validate_primitives(candidate: object, location: str) -> None:
        if isinstance(candidate, dict):
            for key, child in candidate.items():
                validate_primitives(child, f"{location}.{key}")
        elif isinstance(candidate, str):
            allowed = {
                "jfg-phase3-cpu-overlay-evidence",
                "public-safe-aggregate-only",
            }
            if candidate not in allowed and not (
                len(candidate) == 64
                and all(character in "0123456789abcdef" for character in candidate)
            ):
                raise ValueError(f"{location} contains unreviewed public text")
        elif type(candidate) is not int or candidate < 0:
            raise ValueError(f"{location} must be a non-negative integer")
        elif candidate > EXPECTED_ROM_SIZE:
            raise ValueError(f"{location} exceeds the public aggregate limit")

    validate_primitives(value, "$")
    if value["schema_version"] != 1:
        raise ValueError("public overlay aggregate schema version is unsupported")
    if value["kind"] != "jfg-phase3-cpu-overlay-evidence":
        raise ValueError("public overlay aggregate kind is unsupported")
    if value["privacy"] != "public-safe-aggregate-only":
        raise ValueError("public overlay aggregate privacy marker is unsupported")
    hygiene_errors = scan_blob(
        (json.dumps(value, sort_keys=True) + "\n").encode("utf-8"),
        "public-overlay-aggregate",
        enforce_size=False,
    )
    if hygiene_errors:
        raise ValueError("; ".join(hygiene_errors))
    public_safe_errors = validate_public_safe(value)
    public_safe_errors.extend(validate_canonical_json_numbers(value))
    if public_safe_errors:
        raise ValueError("; ".join(public_safe_errors))


def tracked_overlay_fragment(value: object) -> dict[str, object]:
    """Transform analyzer output into the analyzer-owned tracked evidence fields."""
    validate_public_overlay_aggregate(value)
    assert isinstance(value, dict)
    relocations = value["relocations"]
    assert isinstance(relocations, dict)
    tracked_relocation_keys = {
        "main_entry_count",
        "primary_entry_count",
        "secondary_entry_count",
        "total_entry_count",
        "source_type_counts",
        "patch_type_counts",
        "external_target_class_counts",
        "unknown_source_type_count",
        "unknown_patch_type_count",
        "invalid_symbol_index_count",
        "invalid_local_offset_count",
        "invalid_patch_target_count",
        "unaligned_patch_target_count",
        "paired_hi16_lo16_count",
        "unpaired_hi16_count",
        "standalone_lo16_count",
        "hi16_lo16_reference_mismatch_count",
        "hi16_lo16_same_patch_target_count",
        "referenced_anomaly_count",
    }
    return {
        "headers": value["overlay_headers"],
        "reference_table": value["reference_table"],
        "relocations": {
            key: child for key, child in relocations.items() if key in tracked_relocation_keys
        },
        "dependencies": value["dependencies"],
        "detailed_inventory_sha256": value["detailed_inventory_sha256"],
    }


def verify_tracked_overlay_fragment(value: object, evidence: object) -> None:
    """Require a private pinned run to match the tracked aggregate exactly."""
    if not isinstance(evidence, dict) or not isinstance(evidence.get("overlays"), dict):
        raise ValueError("tracked Phase 3 evidence has no overlays object")
    try:
        validate_phase3_evidence(evidence)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            "tracked Phase 3 evidence does not match the reviewed canonical lock"
        ) from error
    tracked = dict(evidence["overlays"])
    tracked.pop("runtime_contract", None)
    if tracked_overlay_fragment(value) != tracked:
        raise ValueError("private overlay analysis differs from tracked aggregate evidence")


def analyze_rom(
    rom: bytes, layout: RomLayout
) -> tuple[dict[str, object], dict[str, object]]:
    if len(rom) != EXPECTED_ROM_SIZE:
        raise ValueError("ROM size does not match the supported US image")

    headers = parse_headers(
        rom[layout.overlay_table_start : layout.overlay_data_start], layout
    )
    header_by_slot = {header.slot: header for header in headers}
    ort_bytes = rom[
        layout.overlay_reference_table_start : layout.overlay_table_start
    ]
    if len(ort_bytes) % 4:
        raise ValueError("overlay reference table is not word-aligned")
    ort = [word for (word,) in struct.iter_unpack(">I", ort_bytes)]

    main_count = struct.unpack_from(">I", rom, layout.main_relocation_start)[0]
    main_payload_start = layout.main_relocation_start + 4
    main_payload_end = main_payload_start + main_count * RELOCATION.size
    if main_payload_end > layout.overlay_reference_table_start:
        raise ValueError("main relocation count exceeds its ROM region")
    main_padding = rom[main_payload_end : layout.overlay_reference_table_start]
    if any(main_padding):
        raise ValueError("main relocation padding is not zero")
    main_entries = parse_relocations(rom[main_payload_start:main_payload_end])

    source_counts: collections.Counter[int] = collections.Counter()
    patch_counts: collections.Counter[int] = collections.Counter()
    table_source_counts: dict[str, collections.Counter[int]] = {
        "main": collections.Counter(),
        "primary": collections.Counter(),
        "secondary": collections.Counter(),
    }
    table_patch_counts: dict[str, collections.Counter[int]] = {
        "main": collections.Counter(),
        "primary": collections.Counter(),
        "secondary": collections.Counter(),
    }
    target_classes: collections.Counter[str] = collections.Counter()
    invalid_symbol_indices = 0
    invalid_local_offsets = 0
    invalid_patch_targets = 0
    unaligned_patch_targets = 0
    hi_lo_counts: collections.Counter[str] = collections.Counter()
    unknown_source_types = 0
    unknown_patch_types = 0
    self_overlay_references = 0
    cross_overlay_edges: set[tuple[int, int]] = set()
    main_to_overlay_edges: set[tuple[int, int]] = set()
    anomaly_references = 0
    external_symbol_indices: set[int] = set()
    detailed_overlays: list[dict[str, object]] = []

    def consume(
        entries: list[tuple[int, int]],
        *,
        table_kind: str,
        source_module: int,
        text_size: int,
        data_size: int,
        memory_size: int,
    ) -> tuple[collections.Counter[int], collections.Counter[int], set[int]]:
        nonlocal invalid_symbol_indices, invalid_local_offsets
        nonlocal invalid_patch_targets, unaligned_patch_targets
        nonlocal unknown_source_types, unknown_patch_types
        nonlocal self_overlay_references, anomaly_references
        local_sources: collections.Counter[int] = collections.Counter()
        local_patches: collections.Counter[int] = collections.Counter()
        dependencies: set[int] = set()
        for entry in entries:
            symbol, target, patch_type, source_type = relocation_fields(entry)
            source_counts[source_type] += 1
            patch_counts[patch_type] += 1
            table_source_counts[table_kind][source_type] += 1
            table_patch_counts[table_kind][patch_type] += 1
            local_sources[source_type] += 1
            local_patches[patch_type] += 1
            unknown_source_types += source_type not in VALID_SOURCE_TYPES
            unknown_patch_types += patch_type not in VALID_PATCH_TYPES
            unaligned_patch_targets += target % 4 != 0

            if source_type == 3:
                patch_bound = data_size
            elif patch_type in INSTRUCTION_PATCH_TYPES:
                patch_bound = text_size
            else:
                patch_bound = text_size + data_size
            invalid_patch_targets += target >= patch_bound

            if source_type in {0, 3}:
                if symbol >= len(ort):
                    invalid_symbol_indices += 1
                    continue
                external_symbol_indices.add(symbol)
                target_word = ort[symbol]
                target_class = classify_ort_target(target_word)
                target_classes[target_class] += 1
                target_module = target_word >> 20
                if target_class == "overlay":
                    dependencies.add(target_module)
                    if source_module == target_module:
                        self_overlay_references += 1
                    elif source_module == 0:
                        main_to_overlay_edges.add((0, target_module))
                    else:
                        cross_overlay_edges.add((source_module, target_module))
                elif target_class == "anomalous":
                    anomaly_references += 1
            elif source_type == 1 and symbol >= memory_size:
                invalid_local_offsets += 1
        return local_sources, local_patches, dependencies

    consume(
        main_entries,
        table_kind="main",
        source_module=0,
        text_size=layout.main_text_size,
        data_size=layout.main_data_size,
        memory_size=layout.main_text_size + layout.main_data_size,
    )
    hi_lo_counts.update(analyze_hi_lo_sequences(main_entries))

    for header in headers:
        if not header.populated:
            continue
        primary = parse_relocations(
            rom[
                header.primary_start(layout) : header.primary_start(layout)
                + header.primary_bytes
            ]
        )
        secondary = parse_relocations(
            rom[
                header.secondary_start(layout) : header.secondary_start(layout)
                + header.secondary_bytes
            ]
        )
        primary_sources, primary_patches, primary_dependencies = consume(
            primary,
            table_kind="primary",
            source_module=header.slot,
            text_size=header.text_size,
            data_size=header.data_size,
            memory_size=header.memory_size,
        )
        secondary_sources, secondary_patches, secondary_dependencies = consume(
            secondary,
            table_kind="secondary",
            source_module=header.slot,
            text_size=header.text_size,
            data_size=header.data_size,
            memory_size=header.memory_size,
        )
        hi_lo_counts.update(analyze_hi_lo_sequences(primary))
        hi_lo_counts.update(analyze_hi_lo_sequences(secondary))
        detailed_overlays.append(
            {
                "id": f"ovl-{header.slot:03d}",
                "rom_start": header.rom_start(layout),
                "rom_end": header.rom_end(layout),
                "text_bytes": header.text_size,
                "data_bytes": header.data_size,
                "bss_bytes": header.bss_size,
                "primary_entry_count": len(primary),
                "secondary_entry_count": len(secondary),
                "primary_source_types": counter_dict(primary_sources),
                "secondary_source_types": counter_dict(secondary_sources),
                "primary_patch_types": counter_dict(primary_patches),
                "secondary_patch_types": counter_dict(secondary_patches),
                "dependency_ids": [
                    f"ovl-{target:03d}"
                    for target in sorted(primary_dependencies | secondary_dependencies)
                ],
            }
        )

    invalid_ort_overlay_numbers = 0
    invalid_ort_overlay_offsets = 0
    empty_overlay_targets = 0
    ort_classes: collections.Counter[str] = collections.Counter()
    ort_anomalies: list[dict[str, object]] = []
    for index, word in enumerate(ort):
        target_class = classify_ort_target(word)
        ort_classes[target_class] += 1
        target_module = word >> 20
        target_offset = word & 0xFFFFF
        if target_class == "overlay":
            target_header = header_by_slot[target_module]
            if not target_header.populated:
                empty_overlay_targets += 1
            if target_offset >= target_header.memory_size:
                invalid_ort_overlay_offsets += 1
        elif target_class == "anomalous":
            invalid_ort_overlay_numbers += 1
            ort_anomalies.append(
                {
                    "id": "ort-" + hashlib.sha256(f"{index}:{word}".encode()).hexdigest()[:16],
                    "referenced": index in external_symbol_indices,
                }
            )

    populated = [header for header in headers if header.populated]
    primary_count = sum(header.primary_bytes for header in populated) // RELOCATION.size
    secondary_count = sum(header.secondary_bytes for header in populated) // RELOCATION.size
    total_relocations = main_count + primary_count + secondary_count
    table_totals = {
        "main": main_count,
        "primary": primary_count,
        "secondary": secondary_count,
    }
    validate_table_count_reconciliation(
        table_source_counts, source_counts, table_totals, "source-type"
    )
    validate_table_count_reconciliation(
        table_patch_counts, patch_counts, table_totals, "patch-type"
    )
    manifest_material = {
        "headers": [header.__dict__ for header in headers],
        "ort": ort,
        "main": main_entries,
        "overlays": detailed_overlays,
    }
    safe = {
        "schema_version": 1,
        "kind": "jfg-phase3-cpu-overlay-evidence",
        "privacy": "public-safe-aggregate-only",
        "overlay_headers": {
            "slot_count": len(headers),
            "populated_count": len(populated),
            "empty_count": len(headers) - len(populated),
            "dynamic_vram_count": sum(header.vram_base == 0 for header in populated),
            "fixed_vram_count": sum(header.vram_base != 0 for header in populated),
            "init_callback_count": sum(header.init_offset != -1 for header in populated),
            "resume_callback_count": sum(header.resume_offset != -1 for header in populated),
            "invalid_callback_count": 0,
            "rom_overlap_pair_count": 0,
        },
        "reference_table": {
            "entry_count": len(ort),
            "target_class_counts": counter_dict(ort_classes),
            "invalid_overlay_number_count": invalid_ort_overlay_numbers,
            "invalid_overlay_offset_count": invalid_ort_overlay_offsets,
            "empty_overlay_target_count": empty_overlay_targets,
        },
        "relocations": {
            "main_entry_count": main_count,
            "primary_entry_count": primary_count,
            "secondary_entry_count": secondary_count,
            "total_entry_count": total_relocations,
            "source_type_counts": counter_dict(source_counts),
            "patch_type_counts": counter_dict(patch_counts),
            "external_target_class_counts": counter_dict(target_classes),
            "unknown_source_type_count": unknown_source_types,
            "unknown_patch_type_count": unknown_patch_types,
            "invalid_symbol_index_count": invalid_symbol_indices,
            "invalid_local_offset_count": invalid_local_offsets,
            "invalid_patch_target_count": invalid_patch_targets,
            "unaligned_patch_target_count": unaligned_patch_targets,
            **counter_dict(hi_lo_counts),
            "referenced_anomaly_count": anomaly_references,
        },
        "dependencies": {
            "main_to_overlay_edge_count": len(main_to_overlay_edges),
            "overlay_to_overlay_edge_count": len(cross_overlay_edges),
            "self_overlay_reference_count": self_overlay_references,
        },
        "detailed_inventory_sha256": canonical_hash(manifest_material),
    }
    detailed = {
        "safe": safe,
        "overlays": detailed_overlays,
        "reference_table_anomalies": ort_anomalies,
        "table_source_type_counts": {
            key: counter_dict(value) for key, value in table_source_counts.items()
        },
        "table_patch_type_counts": {
            key: counter_dict(value) for key, value in table_patch_counts.items()
        },
    }
    validate_public_overlay_aggregate(safe)
    return safe, detailed


def validate_phase3_evidence(evidence: dict[str, Any]) -> None:
    """Validate pinned identities and cross-field Phase 3 relationships."""

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(message)

    pins = evidence["pins"]
    inputs = evidence["inputs"]
    cpu = evidence["cpu"]
    overlays = evidence["overlays"]
    conclusions = evidence["conclusions"]

    require(pins["jfg_decomp"] == EXPECTED_JFG_DECOMP_COMMIT, "JFG decomp pin differs")
    require(pins["n64recomp"] == EXPECTED_N64RECOMP_COMMIT, "N64Recomp pin differs")
    require(inputs["supported_rom_sha1"] == EXPECTED_ROM_SHA1, "ROM SHA-1 differs")
    require(inputs["supported_rom_size"] == EXPECTED_ROM_SIZE, "ROM size differs")
    require(inputs["elf_sha256"] == EXPECTED_ELF_SHA256, "Phase 1 ELF identity differs")
    require(
        inputs["n64recomp_executable_sha256"] == EXPECTED_N64RECOMP_SHA256,
        "N64Recomp executable identity differs",
    )
    require(inputs["initial_config_pinned_parse_passed"] is True, "config parse is unproven")

    functions = cpu["functions"]
    require(
        functions["sized_count"] + functions["zero_size_count"]
        == functions["executable_symbol_count"],
        "function size partition does not equal executable symbol count",
    )
    require(
        functions["covered_zero_size_alias_count"] + functions["uncovered_zero_size_count"]
        == functions["zero_size_count"],
        "zero-size function partition is inconsistent",
    )
    require(
        functions["inferred_size_override_count"] == functions["uncovered_zero_size_count"],
        "inferred size overrides do not cover every uncovered zero-size function",
    )

    data = cpu["data"]
    require(
        data["valid_section_symbol_count"] + data["absolute_or_special_symbol_count"]
        == data["candidate_symbol_count"],
        "data symbol partition is inconsistent",
    )
    require(
        data["invalid_section_range_count"] <= data["valid_section_symbol_count"],
        "invalid data ranges exceed section-backed symbols",
    )
    require(
        not data["invalid_ranges_all_zero_size"]
        or data["invalid_section_range_count"] <= data["zero_size_symbol_count"],
        "zero-size invalid data claim is inconsistent",
    )

    context = cpu["context_dump"]
    require(
        context["function_count_after_size_overrides"]
        == functions["sized_count"] + functions["inferred_size_override_count"],
        "context function count does not match sized plus inferred functions",
    )
    coverage = cpu["coverage_gate"]
    require(
        coverage["context_executable_sections_inventoried"]
        == context["executable_section_count"],
        "coverage inventory differs from the context dump",
    )
    require(
        coverage["status"] == "open"
        and coverage["all_executable_sections_individually_attempted"] is False
        and coverage["all_candidate_functions_individually_classified"] is False,
        "G2 must remain explicitly open for the conservative pre-stub probe",
    )

    generation = cpu["conservative_generation_probe"]
    require(
        generation["placeholder_function_count"]
        <= context["function_count_after_size_overrides"],
        "placeholder function count exceeds context functions",
    )
    require(
        generation["indirect_transfer_candidate_function_count"]
        <= context["function_count_after_size_overrides"],
        "indirect candidate function count exceeds context functions",
    )
    require(
        not generation["final_probe_passed"] or generation["generated_c_file_count"] > 0,
        "successful conservative probe has no generated C files",
    )

    headers = overlays["headers"]
    require(
        headers["populated_count"] + headers["empty_count"] == headers["slot_count"],
        "overlay header population partition is inconsistent",
    )
    require(
        headers["dynamic_vram_count"] + headers["fixed_vram_count"]
        == headers["populated_count"],
        "overlay VRAM partition is inconsistent",
    )
    reference_table = overlays["reference_table"]
    require(
        sum(reference_table["target_class_counts"].values())
        == reference_table["entry_count"],
        "reference target classes do not sum to the reference table",
    )

    relocations = overlays["relocations"]
    require(
        relocations["main_entry_count"]
        + relocations["primary_entry_count"]
        + relocations["secondary_entry_count"]
        == relocations["total_entry_count"],
        "relocation table counts do not sum to the total",
    )
    require(
        sum(relocations["source_type_counts"].values()) == relocations["total_entry_count"],
        "relocation source classes do not sum to the total",
    )
    require(
        sum(relocations["patch_type_counts"].values()) == relocations["total_entry_count"],
        "relocation patch classes do not sum to the total",
    )
    require(
        relocations["paired_hi16_lo16_count"]
        + relocations["unpaired_hi16_count"]
        == relocations["patch_type_counts"]["5"],
        "HI16 sequence counts do not match HI16 relocations",
    )
    require(
        relocations["paired_hi16_lo16_count"]
        + relocations["standalone_lo16_count"]
        == relocations["patch_type_counts"]["6"],
        "LO16 sequence counts do not match LO16 relocations",
    )
    require(
        relocations["unpaired_hi16_count"] == 0
        and relocations["hi16_lo16_reference_mismatch_count"] == 0
        and relocations["hi16_lo16_same_patch_target_count"] == 0,
        "HI16/LO16 sequence safety checks failed",
    )
    require(
        sum(relocations["external_target_class_counts"].values())
        == relocations["source_type_counts"]["0"] + relocations["source_type_counts"]["3"],
        "external relocation targets do not match external source classes",
    )
    require(
        relocations["referenced_anomaly_count"]
        == relocations["external_target_class_counts"]["anomalous"],
        "referenced anomaly count differs from external anomaly targets",
    )

    runtime = overlays["runtime_contract"]
    require(
        runtime["generation_monotonic_per_overlay"]
        and runtime["same_base_reload_rejects_stale_pointer"]
        and runtime["overlapping_publish_rejected"]
        and runtime["stale_unpublish_rejected"],
        "active overlay registry safety contract is incomplete",
    )
    require(
        runtime["generated_code_integration_complete"] is False,
        "synthetic registry evidence cannot claim generated-code integration",
    )
    require(
        conclusions["standard_elf_metadata_is_sufficient"]
        == (data["standard_elf_relocation_entry_count"] > 0),
        "standard ELF metadata conclusion contradicts the relocation inventory",
    )
    require(
        conclusions["g2_complete"] is False
        and conclusions["initial_code_generation_enabled"] is False,
        "generation policy must remain disabled while G2 is open",
    )
    require(
        conclusions["generated_code_overlay_registry_integration_complete"]
        == runtime["generated_code_integration_complete"],
        "runtime integration conclusion differs from the registry evidence",
    )
    require(
        canonical_hash(evidence) == EXPECTED_PHASE3_PUBLIC_AGGREGATE_SHA256,
        "current-pin public aggregate differs from the maintainer-reviewed lock",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument(
        "--layout",
        required=True,
        type=Path,
        help="private seven-field JSON layout outside the repository or Git-ignored",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--details", type=Path)
    parser.add_argument(
        "--tracked-evidence",
        required=True,
        type=Path,
        help="fail if the private analysis differs from a tracked Phase 3 evidence file",
    )
    arguments = parser.parse_args()
    try:
        layout = load_private_layout(arguments.layout)
        if arguments.details:
            verify_private_artifact_path(arguments.details)
        if file_digest(arguments.rom, "sha1") != EXPECTED_ROM_SHA1:
            raise ValueError("ROM SHA-1 does not match the supported US image")
        safe, detailed = analyze_rom(arguments.rom.read_bytes(), layout)
        tracked_evidence = json.loads(
            arguments.tracked_evidence.read_text(encoding="utf-8")
        )
        verify_tracked_overlay_fragment(safe, tracked_evidence)
    except (OSError, ValueError, struct.error) as error:
        print(f"Phase 3 overlay analysis failed: {error}", file=sys.stderr)
        return 1
    rendered = json.dumps(safe, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if arguments.details:
        arguments.details.parent.mkdir(parents=True, exist_ok=True)
        arguments.details.write_text(
            json.dumps(detailed, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
