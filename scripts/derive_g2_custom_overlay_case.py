#!/usr/bin/env python3
"""Derive a private, bounded v3 custom-overlay relocation suite.

This helper reads ROM-derived material only from ignored/external regular paths
and writes new private artifacts only under ``tools``.  Its output contains no
expected observations and is deliberately unsuitable for publication.

Packed v3, little endian:

* ``JFG2OVL3`` followed by ``<IHHIII16s32s32s>`` (version, subject count, module
  count, guest span, exact static initialized size, static BSS size, suite
  token, a private plan-blinding salt, and the exact reviewed plan-file digest),
  followed by the static image;
* module records ``<QIIIIIIB3x>`` (opaque token, overlay slot, guest base,
  text size, reserved zero, image size, reviewed function offset, context
  seed) and their initialized images;
* one subject record per selected overlay: ``<II>`` (slot, generated-R32
  count), R32 entries ``<IB3x>``, custom count, custom entries
  ``<IBB2xIi>``, binding count, and bindings ``<IIB3xI>``.  Bindings carry
  opaque reference-table index, target offset, binding class (static/self/
  provider), and a provider slot (zero unless class is provider).

The suite has at most seven subjects: one for each required coverage bit
(full-word, jump, HI16, LO16, static, self, provider).  It is selected exactly
by minimum subject count, then maximum total relocation records, then stable
opaque binding order.  Every dependency-closed packed module is also a subject
so its generated relocation inventory is checked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
MAGIC = b"JFG2OVL3"
SUITE_HEADER = struct.Struct("<IHHIII16s32s32s")
MODULE_HEADER = struct.Struct("<QIIIIIIB3x")
SUBJECT_HEADER = struct.Struct("<II")
RELOC = struct.Struct(">II")
CUSTOM = struct.Struct("<IBB2xIi")
BINDING = struct.Struct("<IIB3xI")
MAX_ROM = 64 * 1024 * 1024
MAX_CASE = 64 * 1024 * 1024
MAX_EXECUTION_GUEST = 8 * 1024 * 1024
MAX_SUBJECTS = 7
MAX_SELECTION_STATES = 100_000
VALID_SOURCES = {0, 1, 2, 3}
VALID_PATCHES = {2, 4, 5, 6}
CLASS_NAMES = {2: "full-word", 4: "jump-target", 5: "hi16", 6: "lo16"}
STATIC_TARGET_KINDS = {0, 0xFFD, 0xFFE, 0xFFF}
STATIC_BINDING = 0
SELF_BINDING = 1
PROVIDER_BINDING = 2
CONTEXT_SEEDS = {
    "zero": 0,
    "stack": 1,
    "stack-and-frame": 2,
    "stack-and-arguments": 3,
    "stack-frame-and-arguments": 4,
}


class DerivationError(RuntimeError):
    pass


def _private(path: Path) -> Path:
    """Reject reparse points and tracked repository paths."""
    path = Path(os.path.abspath(path))
    current = path
    while True:
        try:
            meta = current.lstat()
        except OSError as error:
            raise DerivationError("input boundary is invalid") from error
        attrs = getattr(meta, "st_file_attributes", 0)
        if current.is_symlink() or attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise DerivationError("input boundary is invalid")
        if current.parent == current:
            break
        current = current.parent
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return path
    try:
        check = subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "-q", "--", rel.as_posix()],
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise DerivationError("input boundary is invalid") from error
    if check.returncode != 0:
        raise DerivationError("input boundary is invalid")
    return path


def _file(path: Path, maximum: int = MAX_CASE) -> bytes:
    path = _private(path)
    try:
        meta = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= maximum:
            raise DerivationError("input boundary is invalid")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        try:
            opened = os.fstat(fd)
            if not os.path.samestat(meta, opened):
                raise DerivationError("input changed")
            data = bytearray()
            while len(data) <= maximum:
                block = os.read(fd, min(1024 * 1024, maximum + 1 - len(data)))
                if not block:
                    break
                data.extend(block)
        finally:
            os.close(fd)
    except OSError as error:
        raise DerivationError("input could not be read") from error
    if not data or len(data) > maximum:
        raise DerivationError("input size is invalid")
    return bytes(data)


def _decode_json(data: bytes) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        output: dict[str, object] = {}
        for key, value in items:
            if key in output:
                raise DerivationError("private JSON is invalid")
            output[key] = value
        return output

    try:
        value = json.loads(data, object_pairs_hook=pairs)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise DerivationError("private JSON is invalid") from error
    if not isinstance(value, dict):
        raise DerivationError("private JSON is invalid")
    return value


def _json(path: Path) -> dict[str, object]:
    return _decode_json(_file(path, 4 * 1024 * 1024))


def _u(value: object, maximum: int = 0xFFFFFFFF) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise DerivationError("private layout is invalid")
    return value


@dataclass(frozen=True)
class Layout:
    main_relocation_start: int
    overlay_reference_table_start: int
    overlay_table_start: int
    overlay_data_start: int
    main_text_size: int
    main_data_size: int


def load_layout(path: Path) -> Layout:
    value = _json(path)
    fields = set(Layout.__annotations__)
    if set(value) != fields | {"schema_version"} or value.get("schema_version") != 1:
        raise DerivationError("private layout is invalid")
    layout = Layout(**{key: _u(value[key]) for key in fields})
    points = (
        layout.main_relocation_start,
        layout.overlay_reference_table_start,
        layout.overlay_table_start,
        layout.overlay_data_start,
    )
    if points != tuple(sorted(points)) or len(set(points)) != 4 or any(point & 3 for point in points):
        raise DerivationError("private layout is invalid")
    if (layout.overlay_data_start - layout.overlay_table_start) % HEADER.size:
        raise DerivationError("private layout is invalid")
    return layout


@dataclass(frozen=True)
class Header:
    slot: int
    vram: int
    rom_offset: int
    text: int
    data: int
    bss: int
    primary: int
    secondary: int

    @property
    def initialized(self) -> int:
        return self.text + self.data

    @property
    def memory(self) -> int:
        return self.initialized + self.bss


HEADER = struct.Struct(">iiiiiHHii")


def headers(rom: bytes, layout: Layout) -> list[Header]:
    if layout.overlay_data_start > len(rom):
        raise DerivationError("private layout is outside ROM")
    raw = rom[layout.overlay_table_start : layout.overlay_data_start]
    result: list[Header] = []
    for slot, record in enumerate(HEADER.iter_unpack(raw), 1):
        vram, offset, text, data, bss, primary, secondary, _init, _resume = record
        if min(offset, text, data, bss, primary, secondary) < 0 or primary % 8 or secondary % 8:
            raise DerivationError("overlay metadata is invalid")
        header = Header(slot, vram & 0xFFFFFFFF, offset, text, data, bss, primary, secondary)
        end = layout.overlay_data_start + offset + header.initialized + primary + secondary
        if header.initialized and (header.vram & 3 or header.text & 3 or header.data & 3 or end > len(rom)):
            raise DerivationError("overlay metadata is invalid")
        result.append(header)
    if not result:
        raise DerivationError("overlay metadata is empty")
    return result


def fields(record: tuple[int, int]) -> tuple[int, int, int, int]:
    symbol, info = record
    return symbol, info >> 8, (info >> 4) & 15, info & 15


def table(rom: bytes, start: int, size: int) -> list[tuple[int, int]]:
    if start < 0 or size < 0 or start + size > len(rom) or size % 8:
        raise DerivationError("relocation table is invalid")
    return list(RELOC.iter_unpack(rom[start : start + size]))


def _be32(image: bytes, offset: int) -> int:
    return struct.unpack_from(">I", image, offset)[0]


def _normalize_linked_addend(value: int) -> int:
    value &= 0xFFFFFFFF
    if value & 0x80000000:
        value -= 0x80000000
    if value > 0x7FFFFFFF:
        raise DerivationError("relocation addend is out of range")
    return value


def _addend(word: int, source: int, patch: int, pair_word: int | None = None) -> int:
    """Recover the original linker's explicit, section-relative addend."""
    if source not in VALID_SOURCES or patch not in VALID_PATCHES or (patch == 5 and pair_word is None):
        raise DerivationError("unsupported relocation addend")
    if patch == 5:
        assert pair_word is not None
        return _normalize_linked_addend(
            ((word & 0xFFFF) << 16)
            + (pair_word & 0xFFFF)
            - (0x10000 if pair_word & 0x8000 else 0)
        )
    if patch == 6:
        return word & 0xFFFF
    if patch == 2 and source == 1:
        return _normalize_linked_addend(word)
    return 0


def _runtime_manifest(path: Path) -> dict[str, object]:
    value = _json(path)
    if (
        set(value) != {"schema_version", "sections", "r_mips_32"}
        or value.get("schema_version") != 1
        or not isinstance(value["sections"], list)
        or not isinstance(value["r_mips_32"], list)
    ):
        raise DerivationError("generated runtime manifest is invalid")
    seen_modules: set[int] = set()
    main_count = 0
    section_keys = {
        "section",
        "module",
        "kind",
        "rom",
        "linked_vram",
        "text_offset",
        "text_size",
        "data_size",
        "bss_size",
    }
    for index, section in enumerate(value["sections"]):
        if not isinstance(section, dict) or set(section) != section_keys:
            raise DerivationError("generated runtime manifest is invalid")
        numeric = tuple(
            section.get(key)
            for key in (
                "section",
                "module",
                "rom",
                "linked_vram",
                "text_offset",
                "text_size",
                "data_size",
                "bss_size",
            )
        )
        kind = section.get("kind")
        if (
            any(type(item) is not int or not 0 <= item <= 0xFFFFFFFF for item in numeric)
            or kind not in {"main", "overlay"}
            or section.get("section") != index
            or section.get("text_size") == 0
            or any(section.get(key) & 3 for key in (
                "linked_vram", "text_offset", "text_size", "data_size", "bss_size"
            ))
        ):
            raise DerivationError("generated runtime manifest is invalid")
        module = section["module"]
        extent = (
            section["text_offset"]
            + section["text_size"]
            + section["data_size"]
            + section["bss_size"]
        )
        if (
            module in seen_modules
            or extent > 0xFFFFFFFF
            or section["linked_vram"] + extent > 0xFFFFFFFF
            or (kind == "main") != (module == 0)
        ):
            raise DerivationError("generated runtime manifest is invalid")
        seen_modules.add(module)
        main_count += kind == "main"
    if main_count != 1:
        raise DerivationError("generated runtime manifest is invalid")
    return value


def _function_plan(
    path: Path, runtime: dict[str, object]
) -> tuple[bytes, bytes, dict[int, tuple[int, int]]]:
    exact_bytes = _file(path, 4 * 1024 * 1024)
    value = _decode_json(exact_bytes)
    if set(value) != {"schema_version", "commitment_salt", "modules"} or value.get("schema_version") != 1:
        raise DerivationError("generated-body plan is invalid")
    salt_text = value.get("commitment_salt")
    if not isinstance(salt_text, str) or len(salt_text) != 64:
        raise DerivationError("generated-body plan is invalid")
    try:
        commitment_salt = bytes.fromhex(salt_text)
    except ValueError as error:
        raise DerivationError("generated-body plan is invalid") from error
    if len(commitment_salt) != 32 or len(set(commitment_salt)) < 16:
        raise DerivationError("generated-body plan is invalid")
    modules = value.get("modules")
    if not isinstance(modules, list) or not modules:
        raise DerivationError("generated-body plan is invalid")
    section_extents = {
        section["section"]: section["text_size"]
        for section in runtime["sections"]
        if section["kind"] == "overlay"
    }
    result: dict[int, tuple[int, int]] = {}
    for module in modules:
        if not isinstance(module, dict) or set(module) != {
            "section", "function_offset", "context_seed"
        }:
            raise DerivationError("generated-body plan is invalid")
        section = module.get("section")
        offset = module.get("function_offset")
        seed_name = module.get("context_seed")
        if (
            type(section) is not int
            or section not in section_extents
            or section in result
            or type(offset) is not int
            or offset < 0
            or offset & 3
            or offset >= section_extents[section]
            or seed_name not in CONTEXT_SEEDS
        ):
            raise DerivationError("generated-body plan is invalid")
        result[section] = (offset, CONTEXT_SEEDS[seed_name])
    return commitment_salt, hashlib.sha256(exact_bytes).digest(), result


def _root(path: Path, runtime: dict[str, object]) -> None:
    path = _private(path)
    try:
        if not path.is_dir() or path.is_symlink():
            raise DerivationError("generated root is invalid")
        manifest = _json(path / "sources.json")
    except OSError as error:
        raise DerivationError("generated root is invalid") from error
    if manifest.get("version") not in {2, 3} or not isinstance(
        manifest.get("normalizer_revision_sha256"), str
    ):
        raise DerivationError("generated root is invalid")
    expected = hashlib.sha256(
        json.dumps(
            runtime,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    ).hexdigest()
    try:
        bound = _file(path / "runtime-manifest.canonical.sha256", 128).decode("ascii")
    except UnicodeDecodeError as error:
        raise DerivationError("generated root is invalid") from error
    if bound != expected + "\n":
        raise DerivationError("generated root does not match the runtime manifest")


def _site_ok(source: int, patch: int, site: int, text: int, initialized: int) -> bool:
    return (
        site % 4 == 0
        and site + 4 <= initialized
        and (site >= text if source == 3 else patch == 2 or site < text)
    )


@dataclass(frozen=True)
class Binding:
    opaque: int
    offset: int
    kind: int
    provider_slot: int


@dataclass(frozen=True)
class R32Truth:
    source: int
    target_module: int
    target_offset: int


@dataclass(frozen=True)
class Candidate:
    header: Header
    section_index: int
    image: bytes
    r32_sites: tuple[int, ...]
    records: tuple[tuple[int, int, int, int, int], ...]
    bindings: tuple[Binding, ...]
    dependencies: tuple[int, ...]
    coverage: int

    @property
    def opaque_order(self) -> tuple[int, ...]:
        return tuple(binding.opaque for binding in self.bindings)


def _binding(
    source: int,
    symbol: int,
    ort: list[int],
    subject_slot: int,
    usable_slots: set[int],
    static_targets: dict[int, tuple[int, int]],
) -> Binding:
    if symbol >= len(ort):
        raise DerivationError("external relocation is invalid")
    target = ort[symbol]
    target_kind = target >> 20
    offset = target & 0xFFFFF
    if target_kind in STATIC_TARGET_KINDS:
        static_base, static_extent = static_targets[target_kind]
        if offset >= static_extent or static_base > 0xFFFFFFFF - offset:
            raise DerivationError("static relocation is outside its declared extent")
        return Binding(symbol + 1, static_base + offset, STATIC_BINDING, 0)
    if target_kind == subject_slot:
        return Binding(symbol + 1, offset, SELF_BINDING, 0)
    if target_kind not in usable_slots:
        raise DerivationError("external relocation is unsupported")
    return Binding(symbol + 1, offset, PROVIDER_BINDING, target_kind)


def _custom_records(
    rom: bytes,
    layout: Layout,
    header: Header,
    section_index: int,
    ort: list[int],
    r32: dict[int, R32Truth],
    r32_dependencies: set[int],
    usable_slots: set[int],
    static_targets: dict[int, tuple[int, int]],
) -> Candidate:
    image_start = layout.overlay_data_start + header.rom_offset
    image = rom[image_start : image_start + header.initialized]
    records: list[tuple[int, int, int, int, int]] = []
    bindings: dict[int, Binding] = {}
    sites: set[int] = set()
    seen_r32: set[int] = set()
    for part in (
        table(rom, image_start + header.initialized, header.primary),
        table(rom, image_start + header.initialized + header.primary, header.secondary),
    ):
        local = 0
        while local < len(part):
            symbol, raw_site, patch, source = fields(part[local])
            site = header.text + raw_site if source == 3 else raw_site
            if (
                source not in VALID_SOURCES
                or patch not in VALID_PATCHES
                or not _site_ok(source, patch, site, header.text, header.initialized)
                or site in sites
            ):
                raise DerivationError("custom relocation is invalid")
            word = _be32(image, site)
            # The normalizer promotes an authoritative full-word record at an
            # R32 site into the generated relocation table.  Keep the site in
            # the exact packed R32 inventory, but do not apply it a second time
            # through the custom relocator.
            if site in r32:
                truth = r32[site]
                if patch != 2 or source != truth.source:
                    raise DerivationError("generated R32 does not match a full-word record")
                if source in {0, 3}:
                    binding = _binding(
                        source,
                        symbol,
                        ort,
                        header.slot,
                        usable_slots,
                        static_targets,
                    )
                    target_module = (
                        0 if binding.kind == STATIC_BINDING
                        else header.slot if binding.kind == SELF_BINDING
                        else binding.provider_slot
                    )
                    target_offset = binding.offset
                elif source == 1:
                    addend = _addend(word, source, patch)
                    if symbol > 0xFFFFFFFF - addend:
                        raise DerivationError("generated R32 target is invalid")
                    target_module = header.slot
                    target_offset = symbol + addend
                else:
                    raise DerivationError("generated R32 source is invalid")
                if (
                    truth.target_module != target_module
                    or truth.target_offset != target_offset
                ):
                    raise DerivationError("generated R32 target does not match the relocation table")
                seen_r32.add(site)
                sites.add(site)
                local += 1
                continue
            pair_word: int | None = None
            pair_site: int | None = None
            if patch == 5:
                if local + 1 >= len(part):
                    raise DerivationError("HI16 record lacks LO16")
                next_symbol, raw_next, next_patch, next_source = fields(part[local + 1])
                pair_site = header.text + raw_next if next_source == 3 else raw_next
                if (
                    next_patch != 6
                    or next_symbol != symbol
                    or next_source != source
                    or pair_site == site
                    or not _site_ok(next_source, next_patch, pair_site, header.text, header.initialized)
                    or pair_site in r32
                    or pair_site in sites
                ):
                    raise DerivationError("HI16/LO16 pair is invalid")
                pair_word = _be32(image, pair_site)
            target = 0
            if source in {0, 3}:
                binding = _binding(
                    source,
                    symbol,
                    ort,
                    header.slot,
                    usable_slots,
                    static_targets,
                )
                previous = bindings.setdefault(binding.opaque, binding)
                if previous != binding:
                    raise DerivationError("external relocation binding is inconsistent")
                target = binding.opaque
            elif source == 1:
                if symbol >= header.memory:
                    raise DerivationError("local relocation is invalid")
                target = symbol
            # Source 2 has no resolver target: the original instruction carries it.
            addend = _addend(word, source, patch, pair_word)
            records.append((site, source, patch, target, addend))
            sites.add(site)
            if patch == 5:
                assert pair_site is not None
                records.append((pair_site, source, 6, target, addend))
                sites.add(pair_site)
                local += 2
            else:
                local += 1
    if seen_r32 != set(r32):
        raise DerivationError("generated R32 inventory does not match the relocation tables")
    ordered_bindings = tuple(sorted(bindings.values(), key=lambda item: item.opaque))
    coverage = 0
    for _, _, patch, _, _ in records:
        coverage |= 1 << (patch - 2 if patch == 2 else patch - 3)
    if seen_r32:
        coverage |= 1  # Generated R32 is the promoted full-word relocation class.
    # Bits 4..6 require all three binding classes over the selected suite.
    for binding in ordered_bindings:
        coverage |= 1 << (4 + binding.kind)
    dependencies = tuple(sorted(
        {binding.provider_slot for binding in ordered_bindings if binding.kind == PROVIDER_BINDING}
        | r32_dependencies
    ))
    return Candidate(
        header,
        section_index,
        image,
        tuple(sorted(seen_r32)),
        tuple(records),
        ordered_bindings,
        dependencies,
        coverage,
    )


def _r32_by_module(
    runtime: dict[str, object],
) -> tuple[dict[int, dict[int, R32Truth]], dict[int, set[int]]]:
    sections = runtime["sections"]
    assert isinstance(sections, list)
    result: dict[int, dict[int, R32Truth]] = {}
    dependencies: dict[int, set[int]] = {}
    for entry in runtime["r_mips_32"]:
        if not isinstance(entry, dict) or set(entry) != {
            "source_section",
            "source_type",
            "site_offset",
            "target_class",
            "target_section",
            "target_section_offset",
        }:
            raise DerivationError("generated runtime manifest is invalid")
        section = entry.get("source_section")
        site = entry.get("site_offset")
        target_section = entry.get("target_section")
        target_offset = entry.get("target_section_offset")
        if (
            type(section) is not int
            or type(site) is not int
            or type(target_section) is not int
            or type(target_offset) is not int
            or entry.get("source_type") not in {0, 1, 3}
            or entry.get("target_class") not in {"local-offset", "overlay"}
            or not 0 <= section < len(sections)
            or not 0 <= target_section < len(sections)
            or site < 0
            or target_offset < 0
        ):
            raise DerivationError("generated runtime manifest is invalid")
        section_data = sections[section]
        target_data = sections[target_section]
        module = section_data.get("module") if isinstance(section_data, dict) else None
        target_module = target_data.get("module") if isinstance(target_data, dict) else None
        target_kind = target_data.get("kind") if isinstance(target_data, dict) else None
        if (
            type(module) is not int
            or type(target_module) is not int
            or target_kind not in {"main", "overlay"}
        ):
            raise DerivationError("generated runtime manifest is invalid")
        sites = result.setdefault(module, {})
        if site in sites:
            raise DerivationError("generated runtime manifest contains a duplicate R32 site")
        sites[site] = R32Truth(entry["source_type"], target_module, target_offset)
        if target_kind == "overlay" and target_module != module:
            dependencies.setdefault(module, set()).add(target_module)
    return result, dependencies


def _section_indices(runtime: dict[str, object]) -> dict[int, int]:
    sections = runtime["sections"]
    assert isinstance(sections, list)
    return {
        int(section["module"]): index
        for index, section in enumerate(sections)
        if isinstance(section, dict)
    }


def _static_targets(runtime: dict[str, object]) -> dict[int, tuple[int, int]]:
    sections = runtime["sections"]
    assert isinstance(sections, list)
    main_sections = [
        section
        for section in sections
        if isinstance(section, dict)
        and section.get("kind") == "main"
        and section.get("module") == 0
    ]
    if len(main_sections) != 1:
        raise DerivationError("generated main section is invalid")
    main = main_sections[0]
    values = tuple(
        main.get(key)
        for key in ("text_offset", "text_size", "data_size", "bss_size")
    )
    if any(type(value) is not int or value < 0 for value in values):
        raise DerivationError("generated main section is invalid")
    text_offset, text_size, data_size, bss_size = values
    if text_offset + text_size + data_size + bss_size > 0xFFFFFFFF:
        raise DerivationError("generated main section is invalid")
    return {
        # ORT kind zero is already relative to the main linked base.  The
        # leading text offset is part of its valid executable extent, not an
        # additional address bias.
        0: (0, text_offset + text_size),
        0xFFD: (text_offset + text_size, data_size),
        0xFFE: (text_offset + text_size, data_size),
        0xFFF: (text_offset + text_size + data_size, bss_size),
    }


def _selection_closure(
    selection: tuple[Candidate, ...],
    candidates: dict[int, Candidate],
) -> tuple[Candidate, ...]:
    needed = {item.header.slot for item in selection}
    pending = list(needed)
    while pending:
        candidate = candidates[pending.pop()]
        for provider in candidate.dependencies:
            if provider not in candidates:
                raise DerivationError("dynamic provider section is unavailable")
            if provider not in needed:
                needed.add(provider)
                pending.append(provider)
    return tuple(candidates[slot] for slot in sorted(needed))


def _selection_is_acyclic(selection: tuple[Candidate, ...]) -> bool:
    by_slot = {item.header.slot: item for item in selection}
    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(slot: int) -> bool:
        if slot in visited:
            return True
        if slot in visiting:
            return False
        visiting.add(slot)
        for provider in by_slot[slot].dependencies:
            if provider == slot or provider not in by_slot:
                continue
            if not visit(provider):
                return False
        visiting.remove(slot)
        visited.add(slot)
        return True

    return all(visit(slot) for slot in by_slot)


def _selection_records(selection: tuple[Candidate, ...]) -> int:
    return sum(len(item.records) + len(item.r32_sites) for item in selection)


def _selection_order(selection: tuple[Candidate, ...]) -> tuple[tuple[tuple[int, ...], int], ...]:
    return tuple(sorted((item.opaque_order, item.header.slot) for item in selection))


def _choose(rom: bytes, layout: Layout, runtime: dict[str, object]) -> tuple[Candidate, ...]:
    all_headers = headers(rom, layout)
    by_slot = {header.slot: header for header in all_headers if header.initialized}
    if not by_slot:
        raise DerivationError("overlay metadata is empty")
    ort_raw = rom[layout.overlay_reference_table_start : layout.overlay_table_start]
    if len(ort_raw) % 4:
        raise DerivationError("reference table is invalid")
    ort = [item[0] for item in struct.iter_unpack(">I", ort_raw)]
    r32, r32_dependencies = _r32_by_module(runtime)
    section_indices = _section_indices(runtime)
    static_targets = _static_targets(runtime)
    all_candidates: dict[int, Candidate] = {}
    for slot in sorted(by_slot):
        if slot not in section_indices:
            continue
        try:
            candidate = _custom_records(
                rom,
                layout,
                by_slot[slot],
                section_indices[slot],
                ort,
                r32.get(slot, {}),
                r32_dependencies.get(slot, set()),
                set(by_slot),
                static_targets,
            )
        except DerivationError:
            continue
        all_candidates[slot] = candidate
    candidates = [
        candidate
        for candidate in all_candidates.values()
        if candidate.records or candidate.r32_sites
    ]
    if not candidates:
        raise DerivationError("valid custom overlay is unavailable")

    # Exact bounded search over dependency-closed subject sets.  Coverage has
    # only seven bits, and every accepted suite has at most seven subjects, so
    # choosing the rarest missing requirement first avoids the quadratic
    # candidate-subset explosion without weakening the result.
    required = (1 << 7) - 1
    closures: dict[int, frozenset[int]] = {}
    closure_coverage: dict[int, int] = {}
    closure_has_r32: dict[int, bool] = {}
    for candidate in candidates:
        try:
            closure = _selection_closure((candidate,), all_candidates)
        except DerivationError:
            continue
        if len(closure) > MAX_SUBJECTS or not _selection_is_acyclic(closure):
            continue
        slot = candidate.header.slot
        closures[slot] = frozenset(item.header.slot for item in closure)
        closure_coverage[slot] = 0
        closure_has_r32[slot] = False
        for item in closure:
            closure_coverage[slot] |= item.coverage
            closure_has_r32[slot] = closure_has_r32[slot] or bool(item.r32_sites)
    if not closures:
        raise DerivationError("complete valid multi-overlay custom relocation suite is unavailable")

    def materialize(slots: frozenset[int]) -> tuple[Candidate, ...]:
        return tuple(all_candidates[slot] for slot in sorted(slots))

    def coverage(slots: frozenset[int]) -> tuple[int, bool]:
        mask = 0
        has_r32 = False
        for slot in slots:
            item = all_candidates[slot]
            mask |= item.coverage
            has_r32 = has_r32 or bool(item.r32_sites)
        return mask, has_r32

    best: tuple[Candidate, ...] | None = None
    pending: list[frozenset[int]] = [frozenset()]
    seen: set[frozenset[int]] = {frozenset()}
    while pending:
        slots = pending.pop()
        if best is not None and len(slots) > len(best):
            continue
        mask, has_r32 = coverage(slots)
        if mask == required and has_r32:
            selected = materialize(slots)
            if best is None or (
                len(selected),
                -_selection_records(selected),
                _selection_order(selected),
            ) < (
                len(best),
                -_selection_records(best),
                _selection_order(best),
            ):
                best = selected
            continue

        requirements: list[list[int]] = []
        for bit in range(7):
            if mask & (1 << bit):
                continue
            requirements.append([
                slot for slot in closures if closure_coverage[slot] & (1 << bit)
            ])
        if not has_r32:
            requirements.append([
                slot for slot in closures if closure_has_r32[slot]
            ])
        if not requirements or any(not options for options in requirements):
            continue
        options = min(requirements, key=len)
        expanded_sets = {
            slots | closures[slot]
            for slot in options
            if len(slots | closures[slot]) <= MAX_SUBJECTS
        }
        for expanded in sorted(
            expanded_sets,
            key=lambda item: (
                len(item),
                -_selection_records(materialize(item)),
                _selection_order(materialize(item)),
            ),
            reverse=True,
        ):
            if expanded == slots or expanded in seen:
                continue
            seen.add(expanded)
            if len(seen) > MAX_SELECTION_STATES:
                raise DerivationError("custom suite selection exceeded its bounded state cap")
            pending.append(expanded)
    if best is None:
        raise DerivationError("complete valid multi-overlay custom relocation suite is unavailable")
    # Every packed populated module is a subject so its generated relocation
    # inventory is formula-checked, including transitive providers.
    return tuple(sorted(best, key=lambda item: (item.opaque_order, item.header.slot)))


def _module(
    token: bytes,
    candidate: Candidate,
    base: int,
    image: bytes,
    function_offset: int,
    context_seed: int,
) -> bytes:
    return MODULE_HEADER.pack(
        int.from_bytes(token[:8], "little") or 1,
        candidate.section_index,
        base,
        candidate.header.text,
        0,
        len(image),
        function_offset,
        context_seed,
    ) + image


def _geometry(
    selected: tuple[Candidate, ...],
    rom: bytes,
    layout: Layout,
    runtime: dict[str, object],
) -> tuple[list[tuple[Candidate, bytes, int]], int]:
    modules: list[tuple[Candidate, bytes, int]] = []
    sections = runtime["sections"]
    if not isinstance(sections, list):
        raise DerivationError("generated runtime manifest is invalid")
    static_end = 0x80010000
    for section in sections:
        if not isinstance(section, dict):
            raise DerivationError("generated runtime manifest is invalid")
        if section["kind"] != "main":
            continue
        end = (
            section["linked_vram"]
            + section["text_offset"]
            + section["text_size"]
            + section["data_size"]
            + section["bss_size"]
        )
        static_end = max(static_end, end)
    base = (static_end + 0xFFF) & ~0xFFF
    if base > 0xFFFFFFFF:
        raise DerivationError("suite guest geometry is invalid")
    for candidate in sorted(selected, key=lambda item: item.header.slot):
        header = candidate.header
        image_start = layout.overlay_data_start + header.rom_offset
        image = rom[image_start : image_start + header.initialized]
        if len(image) != header.initialized:
            raise DerivationError("provider image is invalid")
        modules.append((candidate, image, base))
        base = (base + header.memory + 0xFFF) & ~0xFFF
    guest = (base - 0x80000000) + 0x1000
    if guest > MAX_EXECUTION_GUEST:
        raise DerivationError("suite guest geometry is invalid")
    return modules, guest


def _static_image(
    rom: bytes, runtime: dict[str, object]
) -> tuple[bytes, int]:
    sections = runtime.get("sections")
    if not isinstance(sections, list):
        raise DerivationError("generated runtime manifest is invalid")
    main = [section for section in sections if section.get("kind") == "main"]
    if len(main) != 1 or main[0].get("section") != 0:
        raise DerivationError("static initialized image is unavailable")
    section = main[0]
    start = section["rom"]
    size = section["text_offset"] + section["text_size"] + section["data_size"]
    bss = section["bss_size"]
    if (
        size <= 0
        or size & 3
        or bss <= 0
        or bss & 3
        or start > len(rom)
        or size > len(rom) - start
    ):
        raise DerivationError("static initialized image is unavailable")
    return rom[start : start + size], bss


def derive(
    rom_path: Path,
    layout_path: Path,
    generated_root: Path,
    runtime_manifest: Path,
    function_plan_path: Path,
) -> tuple[bytes, dict[str, object]]:
    rom = _file(rom_path, MAX_ROM)
    layout = load_layout(layout_path)
    runtime = _runtime_manifest(runtime_manifest)
    _root(generated_root, runtime)
    commitment_salt, function_plan_digest, function_plan = _function_plan(
        function_plan_path, runtime
    )
    selected = _choose(rom, layout, runtime)
    if any(candidate.section_index not in function_plan for candidate in selected):
        raise DerivationError("reviewed generated-body identity is unavailable")
    seed = hashlib.sha256(rom + b"g2-custom-overlay-v3").digest()
    modules, guest = _geometry(selected, rom, layout, runtime)
    static_image, static_bss = _static_image(rom, runtime)
    sections_by_module = {candidate.header.slot: candidate.section_index for candidate in selected}
    body: list[bytes] = [
        MAGIC,
        SUITE_HEADER.pack(
            3,
            len(selected),
            len(modules),
            guest,
            len(static_image),
            static_bss,
            seed[:16],
            commitment_salt,
            function_plan_digest,
        ),
        static_image,
    ]
    for index, (candidate, image, base) in enumerate(modules):
        function_offset, context_seed = function_plan[candidate.section_index]
        body.append(_module(
            hashlib.sha256(seed + index.to_bytes(4, "little")).digest(),
            candidate,
            base,
            image,
            function_offset,
            context_seed,
        ))
    for candidate in selected:
        body.append(SUBJECT_HEADER.pack(candidate.section_index, len(candidate.r32_sites)))
        for site in candidate.r32_sites:
            body.append(struct.pack("<IB3x", site, 0))
        body.append(struct.pack("<I", len(candidate.records)))
        for record in candidate.records:
            body.append(CUSTOM.pack(*record))
        body.append(struct.pack("<I", len(candidate.bindings)))
        for binding in candidate.bindings:
            provider_section = 0
            if binding.kind == PROVIDER_BINDING:
                try:
                    provider_section = sections_by_module[binding.provider_slot]
                except KeyError as error:
                    raise DerivationError("dynamic provider section is unavailable") from error
            body.append(BINDING.pack(
                binding.opaque,
                binding.offset,
                binding.kind,
                provider_section,
            ))
    payload = b"".join(body)
    if len(payload) > MAX_CASE:
        raise DerivationError("suite is too large")
    digest = hashlib.sha256(payload).hexdigest()
    all_records = [record for candidate in selected for record in candidate.records]
    binding_kinds = {binding.kind for candidate in selected for binding in candidate.bindings}
    sidecar = {
        "schema_version": 1,
        "case_id": "g2-custom-" + digest[:16],
        "custom_relocation_class_counts": {CLASS_NAMES[kind]: sum(1 for item in all_records if item[2] == kind) for kind in sorted(CLASS_NAMES)},
        "contains_generated_r32": any(candidate.r32_sites for candidate in selected),
        "multi_module_closure": True,
        "subject_module_count": len(selected),
        "binding_class_counts": {
            "static": sum(1 for candidate in selected for binding in candidate.bindings if binding.kind == STATIC_BINDING),
            "self": sum(1 for candidate in selected for binding in candidate.bindings if binding.kind == SELF_BINDING),
            "provider": sum(1 for candidate in selected for binding in candidate.bindings if binding.kind == PROVIDER_BINDING),
        },
        "case_commitment_sha256": digest,
    }
    if set(binding_kinds) != {STATIC_BINDING, SELF_BINDING, PROVIDER_BINDING}:
        raise DerivationError("complete binding-class closure is unavailable")
    return payload, sidecar


def _new_output(path: Path, payload: bytes) -> None:
    path = Path(os.path.abspath(path))
    parent = path.parent
    try:
        tools_root = Path(os.path.abspath(TOOLS))
        path.relative_to(tools_root)
        current = parent
        while True:
            meta = current.lstat()
            attrs = getattr(meta, "st_file_attributes", 0)
            if (
                current.is_symlink()
                or attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                or not stat.S_ISDIR(meta.st_mode)
            ):
                raise DerivationError("output boundary is invalid")
            if current == tools_root:
                break
            if current.parent == current:
                raise DerivationError("output boundary is invalid")
            current = current.parent
        if path.exists() or path.is_symlink():
            raise DerivationError("output boundary is invalid")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        try:
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("short write")
                view = view[written:]
        finally:
            os.close(fd)
    except (OSError, ValueError) as error:
        raise DerivationError("output boundary is invalid") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--layout", type=Path, required=True)
    parser.add_argument("--generated-root", type=Path, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--function-plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        payload, sidecar = derive(
            args.rom,
            args.layout,
            args.generated_root,
            args.runtime_manifest,
            args.function_plan,
        )
        _new_output(args.output, payload)
        _new_output(args.sidecar, (json.dumps(sidecar, sort_keys=True, separators=(",", ":")) + "\n").encode())
    except DerivationError as error:
        print("G2 custom-overlay derivation failed: " + str(error), file=sys.stderr)
        return 1
    print("G2 custom-overlay suite derived")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
