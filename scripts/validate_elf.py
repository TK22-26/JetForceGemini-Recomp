#!/usr/bin/env python3
"""Validate a MIPS ELF and emit a non-expressive structural summary.

Detailed section and symbol names are used only in memory to perform validation.
The returned and serialized summary contains counts, hashes, and pass/fail facts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


SECTION_LINE_RE = re.compile(r"^\s*\[\s*(?P<index>\d+)\]\s+(?P<body>.+?)\s*$")
SYMBOL_TABLE_RE = re.compile(
    r"^Symbol table '(?P<table>[^']+)' contains (?P<count>\d+) "
    r"entr(?:y|ies):\s*$"
)
SYMBOL_LINE_RE = re.compile(
    r"^\s*(?P<index>\d+):\s+(?P<value>[0-9A-Fa-f]+)\s+"
    r"(?P<size>(?:0[xX][0-9A-Fa-f]+|\d+))\s+(?P<type>\S+)\s+(?P<bind>\S+)\s+"
    r"(?P<visibility>\S+)\s+(?P<section>\S+)\s*(?P<name>.*)$"
)
MAP_SECTION_RE = re.compile(
    # GNU ld prints output sections at column zero; indented records are input
    # section contributions and may repeat with different sizes/addresses.
    r"^(?P<name>\.[^\s]+)\s+0x(?P<address>[0-9A-Fa-f]+)\s+"
    r"0x(?P<size>[0-9A-Fa-f]+)(?:\s|$)"
)
MAP_SECTION_NAME_RE = re.compile(r"^(?P<name>\.[^\s]+)\s*$")
MAP_SECTION_VALUE_RE = re.compile(
    r"^\s+0x(?P<address>[0-9A-Fa-f]+)\s+0x(?P<size>[0-9A-Fa-f]+)(?:\s|$)"
)
MAP_SYMBOL_RE = re.compile(
    r"^\s*0x(?P<value>[0-9A-Fa-f]+)\s+"
    r"(?P<name>[A-Za-z_.$][A-Za-z0-9_.$@]*)\s*$"
)
HEX_RE = re.compile(r"^[0-9A-Fa-f]+$")
SECTION_TYPES = {
    "NULL", "PROGBITS", "SYMTAB", "STRTAB", "RELA", "HASH", "DYNAMIC",
    "NOTE", "NOBITS", "REL", "SHLIB", "DYNSYM", "INIT_ARRAY", "FINI_ARRAY",
    "PREINIT_ARRAY", "GROUP", "SYMTAB_SHNDX", "GNU_HASH", "GNU_LIBLIST",
    "MIPS_ABIFLAGS", "MIPS_OPTIONS", "MIPS_REGINFO",
}


@dataclass(frozen=True)
class Section:
    index: int
    name: str
    section_type: str
    address: int
    offset: int
    size: int
    entry_size: int
    flags: str
    link: int
    info: int
    alignment: int

    @property
    def allocated(self) -> bool:
        return "A" in self.flags


@dataclass(frozen=True)
class Symbol:
    table: str
    index: int
    value: int
    size: int
    symbol_type: str
    binding: str
    visibility: str
    section: str
    name: str

    @property
    def defined(self) -> bool:
        return self.section not in {"UND", "UNDEF"}


def digest(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def readelf(path: Path, option: str) -> str:
    return subprocess.run(
        ["readelf", option, str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def parse_header(output: str) -> dict[str, str | int]:
    fields: dict[str, str] = {}
    for line in output.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()

    required = (
        "Class",
        "Data",
        "Type",
        "Machine",
        "Entry point address",
        "Number of section headers",
    )
    missing = [key for key in required if key not in fields]
    if missing:
        raise ValueError(f"ELF header is missing required fields: {', '.join(missing)}")
    if fields["Class"] != "ELF32":
        raise ValueError("ELF class is not ELF32")
    if "big endian" not in fields["Data"].lower():
        raise ValueError("ELF data encoding is not big-endian")
    if "MIPS" not in fields["Machine"]:
        raise ValueError("ELF machine is not MIPS")
    if not fields["Type"].startswith("EXEC"):
        raise ValueError("ELF type is not executable")

    entry_text = fields["Entry point address"]
    try:
        entry = int(entry_text, 0)
        section_header_count = int(fields["Number of section headers"], 10)
    except ValueError as error:
        raise ValueError("ELF entry point or section count is not parseable") from error
    return {
        "class": fields["Class"],
        "endianness": "big",
        "type": "EXEC",
        "machine": "MIPS",
        "entry_point": entry,
        "section_header_count": section_header_count,
    }


def parse_sections(output: str) -> list[Section]:
    sections: list[Section] = []
    for line in output.splitlines():
        match = SECTION_LINE_RE.match(line)
        if not match:
            continue
        tokens = match.group("body").split()
        if len(tokens) < 8:
            continue

        if tokens[0] in SECTION_TYPES and len(tokens) >= 8 and HEX_RE.fullmatch(tokens[1]):
            name = ""
            section_type = tokens[0]
            position = 1
        else:
            if len(tokens) < 9:
                continue
            name = tokens[0]
            section_type = tokens[1]
            position = 2

        numeric = tokens[position:position + 4]
        if len(numeric) != 4 or not all(HEX_RE.fullmatch(value) for value in numeric):
            continue
        try:
            link, info, alignment = (int(value, 10) for value in tokens[-3:])
        except ValueError:
            continue
        flags = "".join(tokens[position + 4:-3])
        sections.append(
            Section(
                index=int(match.group("index")),
                name=name,
                section_type=section_type,
                address=int(numeric[0], 16),
                offset=int(numeric[1], 16),
                size=int(numeric[2], 16),
                entry_size=int(numeric[3], 16),
                flags=flags,
                link=link,
                info=info,
                alignment=alignment,
            )
        )
    if not sections:
        raise ValueError("ELF has no parseable sections")
    if len({section.index for section in sections}) != len(sections):
        raise ValueError("ELF contains duplicate section indices")
    return sections


def parse_symbols(output: str) -> list[Symbol]:
    symbols: list[Symbol] = []
    table: str | None = None
    declared_counts: dict[str, int] = {}
    parsed_indices: defaultdict[str, list[int]] = defaultdict(list)
    for line in output.splitlines():
        table_match = SYMBOL_TABLE_RE.match(line)
        if table_match:
            table = table_match.group("table")
            if table in declared_counts:
                raise ValueError("readelf repeats a symbol-table declaration")
            declared_counts[table] = int(table_match.group("count"), 10)
            continue
        match = SYMBOL_LINE_RE.match(line)
        if not match:
            continue
        if table is None:
            raise ValueError("symbol record appears before a symbol-table declaration")
        name = match.group("name").split(" ", 1)[0]
        size_text = match.group("size")
        size = int(size_text, 16) if size_text.lower().startswith("0x") else int(size_text, 10)
        index = int(match.group("index"), 10)
        parsed_indices[table].append(index)
        symbols.append(
            Symbol(
                table=table,
                index=index,
                value=int(match.group("value"), 16),
                size=size,
                symbol_type=match.group("type"),
                binding=match.group("bind"),
                visibility=match.group("visibility"),
                section=match.group("section"),
                name=name,
            )
        )
    if not symbols:
        raise ValueError("ELF has no parseable symbols")
    for table_name, declared_count in declared_counts.items():
        indices = parsed_indices[table_name]
        if len(indices) != declared_count:
            raise ValueError("parsed symbol count differs from readelf's declared entry count")
        if sorted(indices) != list(range(declared_count)):
            raise ValueError("symbol-table indices do not cover the declared entry range")
    return symbols


def unexpected_section_overlaps(
    sections: list[Section],
    allowed_pairs: set[frozenset[str]] | None = None,
) -> list[tuple[Section, Section]]:
    allowed = allowed_pairs or set()
    allocated = sorted(
        (section for section in sections if section.allocated and section.size > 0),
        key=lambda section: (section.address, section.address + section.size, section.index),
    )
    overlaps: list[tuple[Section, Section]] = []
    active: list[Section] = []
    for section in allocated:
        active = [candidate for candidate in active if candidate.address + candidate.size > section.address]
        for candidate in active:
            pair = frozenset((candidate.name, section.name))
            if pair not in allowed:
                overlaps.append((candidate, section))
        active.append(section)
    return overlaps


def duplicate_export_count(symbols: list[Symbol]) -> int:
    preferred_table = ".symtab" if any(symbol.table == ".symtab" for symbol in symbols) else None
    definitions: defaultdict[str, set[tuple[int, str]]] = defaultdict(set)
    for symbol in symbols:
        if preferred_table and symbol.table != preferred_table:
            continue
        if not symbol.name or not symbol.defined or symbol.binding not in {"GLOBAL", "WEAK"}:
            continue
        definitions[symbol.name].add((symbol.value, symbol.section))
    return sum(1 for values in definitions.values() if len(values) > 1)


def parse_map(output: str) -> tuple[dict[str, tuple[int, int]], dict[str, set[int]]]:
    sections: dict[str, tuple[int, int]] = {}
    symbols: defaultdict[str, set[int]] = defaultdict(set)
    pending_section: str | None = None
    for line in output.splitlines():
        section_match = MAP_SECTION_RE.match(line)
        if section_match:
            name = section_match.group("name")
            value = (
                int(section_match.group("address"), 16),
                int(section_match.group("size"), 16),
            )
            if name in sections and sections[name] != value:
                raise ValueError("linker map contains conflicting output-section records")
            sections[name] = value
            pending_section = None
            continue
        section_name_match = MAP_SECTION_NAME_RE.match(line)
        if section_name_match:
            pending_section = section_name_match.group("name")
            continue
        if pending_section is not None:
            section_value_match = MAP_SECTION_VALUE_RE.match(line)
            if section_value_match:
                value = (
                    int(section_value_match.group("address"), 16),
                    int(section_value_match.group("size"), 16),
                )
                if pending_section in sections and sections[pending_section] != value:
                    raise ValueError("linker map contains conflicting output-section records")
                sections[pending_section] = value
                pending_section = None
                continue
            pending_section = None
        symbol_match = MAP_SYMBOL_RE.match(line)
        if symbol_match:
            symbols[symbol_match.group("name")].add(int(symbol_match.group("value"), 16))
    if not sections:
        raise ValueError("linker map has no parseable output sections")
    return sections, dict(symbols)


def map_consistency(
    elf_sections: list[Section],
    elf_symbols: list[Symbol],
    map_output: str,
) -> dict[str, int | bool]:
    map_sections, map_symbols = parse_map(map_output)
    alloc_sections = [section for section in elf_sections if section.allocated and section.size > 0]
    section_checked = 0
    section_missing = 0
    section_mismatches = 0
    for section in alloc_sections:
        expected = map_sections.get(section.name)
        if expected is None:
            section_missing += 1
            continue
        section_checked += 1
        if expected != (section.address, section.size):
            section_mismatches += 1

    preferred_table = ".symtab" if any(symbol.table == ".symtab" for symbol in elf_symbols) else None
    symbol_checked = 0
    symbol_missing = 0
    symbol_mismatches = 0
    seen: set[str] = set()
    for symbol in elf_symbols:
        if preferred_table and symbol.table != preferred_table:
            continue
        if (
            not symbol.name
            or symbol.name in seen
            or not symbol.defined
            or symbol.binding not in {"GLOBAL", "WEAK"}
        ):
            continue
        seen.add(symbol.name)
        values = map_symbols.get(symbol.name)
        if values is None:
            symbol_missing += 1
            continue
        symbol_checked += 1
        if symbol.value not in values:
            symbol_mismatches += 1

    checked_records_consistent = section_mismatches == 0 and symbol_mismatches == 0
    has_minimum_coverage = section_checked > 0 and symbol_checked > 0
    coverage_complete = section_missing == 0 and symbol_missing == 0
    if not checked_records_consistent:
        coverage_verdict = "inconsistent"
    elif not has_minimum_coverage:
        coverage_verdict = "insufficient"
    elif coverage_complete:
        coverage_verdict = "complete"
    else:
        coverage_verdict = "partial"
    return {
        # Consistency is bounded to records present in both inputs. Coverage is
        # reported independently so a partial map is never described as complete.
        "consistent": checked_records_consistent and has_minimum_coverage,
        "coverage_verdict": coverage_verdict,
        "coverage_complete": coverage_complete,
        "section_candidate_count": len(alloc_sections),
        "section_checked_count": section_checked,
        "section_missing_count": section_missing,
        "section_mismatch_count": section_mismatches,
        "symbol_candidate_count": len(seen),
        "symbol_checked_count": symbol_checked,
        "symbol_missing_count": symbol_missing,
        "symbol_mismatch_count": symbol_mismatches,
    }


def summarize(path: Path, map_path: Path | None = None) -> dict[str, object]:
    header = parse_header(readelf(path, "-hW"))
    sections = parse_sections(readelf(path, "-SW"))
    symbols = parse_symbols(readelf(path, "-sW"))
    if len(sections) != header["section_header_count"]:
        raise ValueError("parsed ELF section count differs from the ELF header")

    overlaps = unexpected_section_overlaps(sections)
    duplicate_exports = duplicate_export_count(symbols)
    if overlaps:
        raise ValueError(f"ELF has {len(overlaps)} unexpected allocated-section overlap(s)")
    if duplicate_exports:
        raise ValueError(f"ELF has {duplicate_exports} conflicting exported symbol name(s)")

    symbol_types = Counter(symbol.symbol_type for symbol in symbols)
    symbol_bindings = Counter(symbol.binding for symbol in symbols)
    relocation_count = sum(
        1
        for line in readelf(path, "-rW").splitlines()
        if re.match(r"^\s*[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+R_", line)
    )

    section_shape = [
        {
            "index": section.index,
            "name": section.name,
            "type": section.section_type,
            "address": section.address,
            "offset": section.offset,
            "size": section.size,
            "entry_size": section.entry_size,
            "flags": section.flags,
            "link": section.link,
            "info": section.info,
            "alignment": section.alignment,
        }
        for section in sections
    ]
    section_table_hash = hashlib.sha256(
        json.dumps(section_shape, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    result: dict[str, object] = {
        "schema_version": 2,
        "file_size": path.stat().st_size,
        "sha256": digest(path, "sha256"),
        "header": header,
        "section_count": len(sections),
        "allocated_section_count": sum(section.allocated for section in sections),
        "section_table_sha256": section_table_hash,
        # Retain the original key while Phase 1 evidence consumers migrate.
        "section_shape_sha256": section_table_hash,
        "unexpected_section_overlap_count": 0,
        "symbol_count": len(symbols),
        "symbol_types": dict(sorted(symbol_types.items())),
        "symbol_bindings": dict(sorted(symbol_bindings.items())),
        "conflicting_export_name_count": 0,
        "relocation_count": relocation_count,
    }
    if map_path is not None:
        if not map_path.is_file():
            raise ValueError("expected linker map does not exist")
        consistency = map_consistency(sections, symbols, map_path.read_text(encoding="utf-8"))
        if not consistency["consistent"]:
            raise ValueError("ELF and linker map are inconsistent")
        result["map"] = {
            "sha256": digest(map_path, "sha256"),
            **consistency,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("elf", type=Path)
    parser.add_argument("--map", dest="map_path", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    try:
        summary = summarize(arguments.elf, arguments.map_path)
    except (OSError, subprocess.CalledProcessError, UnicodeError, ValueError) as error:
        print(f"ELF validation failed: {error}", file=sys.stderr)
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
