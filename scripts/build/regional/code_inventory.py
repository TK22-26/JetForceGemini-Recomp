"""Shared instruction and compiler-input inventory algorithms.

These operate on explicit section coordinates. Original ROM/model validation and
compiler decision reconciliation are separate required stages.
"""
from __future__ import annotations
import collections,json,struct
from pathlib import Path
from typing import Any

def read_word(rom: bytes | bytearray, offset: int) -> int:
    if offset < 0 or offset + 4 > len(rom) or offset % 4:
        raise ValueError("private word access is out of bounds or unaligned")
    return struct.unpack_from(">I", rom, offset)[0]


def sign_extend_16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def function_intervals(sections: list[dict[str, Any]]) -> dict[int, list[tuple[int, int]]]:
    result: dict[int, list[tuple[int, int]]] = {}
    for index, section in enumerate(sections):
        base = int(section["vram"])
        result[index] = sorted(
            (int(function["vram"]) - base, int(function["vram"]) - base + int(function["size"]))
            for function in section["functions"]
        )
    return result


def find_cross_body_branch_entries(
    rom: bytes,
    sections: list[dict[str, Any]],
) -> dict[int, set[int]]:
    entries: dict[int, set[int]] = collections.defaultdict(set)
    intervals = function_intervals(sections)
    for section_index, section in enumerate(sections):
        base = int(section["vram"])
        starts = {start for start, _ in intervals[section_index]}
        for function in section["functions"]:
            function_vram = int(function["vram"])
            function_size = int(function["size"])
            function_start = function_vram - base
            function_end = function_start + function_size
            function_rom = int(section["rom"]) + function_start
            for instruction_offset in range(0, function_size, 4):
                word = read_word(rom, function_rom + instruction_offset)
                opcode = word >> 26
                pc = function_vram + instruction_offset
                target_vram: int | None = None
                if opcode == 2:
                    target_vram = ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
                elif opcode in {4, 5, 6, 7, 20, 21, 22, 23}:
                    target_vram = (pc + 4 + (sign_extend_16(word & 0xFFFF) << 2)) & 0xFFFFFFFF
                elif opcode == 1 and ((word >> 16) & 0x1F) in {0, 1, 2, 3, 16, 17, 18, 19}:
                    target_vram = (pc + 4 + (sign_extend_16(word & 0xFFFF) << 2)) & 0xFFFFFFFF
                elif opcode == 17 and ((word >> 21) & 0x1F) == 8:
                    target_vram = (pc + 4 + (sign_extend_16(word & 0xFFFF) << 2)) & 0xFFFFFFFF
                if target_vram is None:
                    continue
                target_offset = target_vram - base
                if function_start <= target_offset < function_end or target_offset in starts:
                    continue
                if any(start < target_offset < end for start, end in intervals[section_index]):
                    entries[section_index].add(target_offset)
    return entries



def find_direct_interior_entries(rom, sections, r26_targets_by_site):
    """Every original direct JAL interior target needs an explicit callable.

    Relocated sites retain their section identity. An unrelocated target must
    have exactly one body owner; overlapping linked VRAM cannot select a body.
    The authoritative body remains intact and a support thunk owns the entry.
    """
    entries = collections.defaultdict(set)
    intervals = function_intervals(sections)
    for source_index, source in enumerate(sections):
        for function in source['functions']:
            start = function['vram'] - source['vram']
            for offset in range(start, start + function['size'], 4):
                word = read_word(rom, source['rom'] + offset)
                if word >> 26 != 3:
                    continue
                qualified = r26_targets_by_site.get((source_index, offset))
                if qualified is not None:
                    owners = [(qualified[0], a, b, qualified[1]) for a, b in intervals[qualified[0]] if a <= qualified[1] < b]
                else:
                    pc = source['vram'] + offset
                    target = ((pc + 4) & 0xf0000000) | ((word & 0x03ffffff) << 2)
                    owners = [(index, a, b, target - section['vram']) for index, section in enumerate(sections)
                              for a, b in intervals[index] if section['vram'] + a <= target < section['vram'] + b]
                if len(owners) > 1:
                    raise ValueError('Direct JAL target has ambiguous section/body ownership')
                if owners:
                    index, start, _, target_offset = owners[0]
                    if target_offset != start:
                        entries[index].add(target_offset)
    return entries


def find_constant_indirect_entries(rom: bytes, sections: list[dict[str, Any]]) -> dict[int, set[int]]:
    """Recognize witnessed LUI + ADDIU/ORI + JR/JALR constant targets.

    Keep authoritative bodies intact. A unique interior owner gets a callable
    entry; overlapping section ownership fails rather than choosing a region.
    This is a narrow instruction witness, not general register dataflow.
    """
    entries: dict[int, set[int]] = collections.defaultdict(set)
    intervals = function_intervals(sections)
    for source in sections:
        for body in source["functions"]:
            start = int(body["vram"]) - int(source["vram"])
            for offset in range(start, start + int(body["size"]) - 8, 4):
                upper, lower, jump = (read_word(rom, int(source["rom"]) + offset + n) for n in (0, 4, 8))
                register = (upper >> 16) & 31
                if upper >> 26 != 15 or (upper >> 21) & 31 or register == 0:
                    continue
                opcode = lower >> 26
                if opcode not in (9, 13) or (lower >> 21) & 31 != register or (lower >> 16) & 31 != register:
                    continue
                if jump >> 26 or (jump & 63) not in (8, 9) or (jump >> 21) & 31 != register:
                    continue
                if (jump >> 16) & 31 or (jump >> 6) & 31 or ((jump & 63) == 8 and (jump >> 11) & 31):
                    continue
                high = (upper & 65535) << 16
                target = ((high + sign_extend_16(lower & 65535)) if opcode == 9 else high | (lower & 65535)) & 0xffffffff
                if target % 4:
                    continue
                owners = [(index, a, target - int(section["vram"]))
                          for index, section in enumerate(sections) for a, b in intervals[index]
                          if int(section["vram"]) + a <= target < int(section["vram"]) + b]
                if len(owners) > 1:
                    raise ValueError("Constant register target has ambiguous section/body ownership")
                if owners:
                    index, body_start, target_offset = owners[0]
                    if target_offset != body_start:
                        entries[index].add(target_offset)
    return entries


def close_alternate_branch_entries(rom, sections, split_offsets):
    """Close branch destinations exposed by synthesized interior-entry bodies.

    A branch local to its authoritative body can leave a suffix thunk. Discover
    its callable destination against original coordinates until no new suffix
    exposes another destination. The finite original instruction set bounds it.
    """
    entries = collections.defaultdict(set, {index: set(offsets) for index, offsets in split_offsets.items()})
    discovered = collections.defaultdict(set)
    while True:
        functions, _, uncovered = split_functions(sections, entries)
        if uncovered: raise ValueError("Alternate branch entry has no original body")
        projected = [dict(section, functions=functions[index]) for index, section in enumerate(sections)]
        found = find_cross_body_branch_entries(rom, projected)
        additions = {index: offsets - entries[index] for index, offsets in found.items()}
        if not any(additions.values()): return dict(discovered)
        for index, offsets in additions.items():
            entries[index].update(offsets); discovered[index].update(offsets)


def find_indirect_transfer_sites(
    rom: bytes, sections: list[dict[str, Any]]
) -> list[dict[str, int | str]]:
    """Enumerate every JR/JALR in authoritative executable bodies.

    Register targets cannot be reconstructed statically here.  Each site is
    therefore carried as an ignored ledger row with an explicit fail-closed
    disposition instead of being silently omitted from the call denominator.
    """
    rows: list[dict[str, int | str]] = []
    for section_index, section in enumerate(sections):
        base = int(section["vram"])
        for function in section["functions"]:
            start = int(function["vram"]) - base
            size = int(function["size"])
            for offset in range(0, size, 4):
                word = read_word(rom, int(section["rom"]) + start + offset)
                if word >> 26 != 0:
                    continue
                function_code = word & 0x3F
                if function_code in {8, 9}:
                    rows.append({
                        "section": section_index,
                        "offset": start + offset,
                        "transfer_kind": "jr" if function_code == 8 else "jalr",
                        "source_register": (word >> 21) & 0x1F,
                    })
    return rows


def find_direct_call_candidates(
    rom: bytes,
    sections: list[dict[str, Any]],
    generated_functions: list[list[dict[str, int | str]]],
    approved_fail_closed_sites: set[tuple[int, int]],
    r26_targets_by_site: dict[tuple[int, int], tuple[int, int]],
) -> list[dict[str, int | str | None]]:
    """Decode every direct call/tail emission candidate in authoritative code."""
    generated_targets: dict[int, list[tuple[int, int, str]]] = collections.defaultdict(list)
    generated_targets_by_coordinate: dict[tuple[int, int], tuple[int, int, str]] = {}
    authoritative_starts = {
        (index, int(function["vram"]))
        for index, section in enumerate(sections)
        for function in section["functions"]
    }
    for section_index, functions in enumerate(generated_functions):
        base = int(sections[section_index]["vram"])
        for function in functions:
            target_vram = int(function["vram"])
            qualified_target = (
                section_index,
                target_vram - base,
                (
                    "authoritative-body"
                    if (section_index, target_vram) in authoritative_starts
                    else "alternate-entry"
                ),
            )
            generated_targets[target_vram].append(qualified_target)
            generated_targets_by_coordinate[
                (section_index, target_vram - base)
            ] = qualified_target

    rows_by_site: dict[tuple[int, int], dict[str, int | str | None]] = {}
    for section_index, section in enumerate(sections):
        base = int(section["vram"])
        rom_base = int(section["rom"])
        for function in generated_functions[section_index]:
            start = int(function["vram"]) - base
            size = int(function["size"])
            for function_offset in range(0, size, 4):
                site_offset = start + function_offset
                word = read_word(rom, rom_base + site_offset)
                opcode = word >> 26
                register_immediate = (word >> 16) & 0x1F
                transfer_role: str
                if opcode == 3:
                    instruction_class = "jal"
                    transfer_role = "linked-call"
                elif opcode == 1 and register_immediate == 17:
                    instruction_class = "bgezal"
                    transfer_role = "linked-call"
                elif opcode == 2:
                    jump_target = (
                        ((base + site_offset + 4) & 0xF0000000)
                        | ((word & 0x03FFFFFF) << 2)
                    )
                    function_start = int(function["vram"])
                    function_end = function_start + size
                    if function_start <= jump_target < function_end:
                        continue
                    instruction_class = "j"
                    transfer_role = "direct-tail"
                elif (opcode in {4, 5, 6, 7, 20, 21, 22, 23}
                      or (opcode == 1 and register_immediate in {0, 1, 2, 3})
                      or (opcode == 17 and ((word >> 21) & 0x1F) == 8)):
                    branch_target = (
                        base
                        + site_offset
                        + 4
                        + (sign_extend_16(word & 0xFFFF) << 2)
                    ) & 0xFFFFFFFF
                    function_start = int(function["vram"])
                    function_end = function_start + size
                    if function_start <= branch_target < function_end:
                        continue
                    instruction_class = "conditional-branch"
                    transfer_role = "direct-tail"
                else:
                    continue
                pc = base + site_offset
                target_vram = (
                    ((pc + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
                    if instruction_class in {"jal", "j"}
                    else (
                        pc + 4 + (sign_extend_16(word & 0xFFFF) << 2)
                    )
                    & 0xFFFFFFFF
                )
                site = (section_index, site_offset)
                relocation_target = r26_targets_by_site.get(site)
                if relocation_target is not None:
                    target = generated_targets_by_coordinate.get(relocation_target)
                    target_vram = (
                        int(sections[relocation_target[0]]["vram"])
                        + relocation_target[1]
                    )
                else:
                    candidates = generated_targets.get(target_vram, [])
                    if instruction_class in {"conditional-branch", "bgezal"}:
                        candidates = [candidate for candidate in candidates if candidate[0] == section_index]
                    if len(candidates) > 1:
                        raise ValueError("Direct target needs an explicit section-qualified relocation")
                    target = candidates[0] if candidates else None
                target_section, target_offset, target_class = (
                    target
                    if target is not None
                    else (None, None, "unresolved-candidate")
                )
                candidate = {
                    "source_section": section_index,
                    "source_offset": site_offset,
                    "transfer_role": transfer_role,
                    "instruction_class": instruction_class,
                    "decoded_target_vram": target_vram,
                    "target_section": target_section,
                    "target_offset": target_offset,
                    "target_class": target_class,
                    "disposition": (
                        "approved-fail-closed-trap"
                        if site in approved_fail_closed_sites
                        else "requires-n64recomp-direct-observation"
                    ),
                }
                previous = rows_by_site.get(site)
                if previous is not None and previous != candidate:
                    raise ValueError("direct-call owner projections disagree")
                rows_by_site[site] = candidate
    rows = [rows_by_site[site] for site in sorted(rows_by_site)]
    candidate_sites = {
        (int(row["source_section"]), int(row["source_offset"])) for row in rows
    }
    transfer_role_counts = collections.Counter(row["transfer_role"] for row in rows)
    instruction_class_counts = collections.Counter(
        row["instruction_class"] for row in rows
    )
    if not set(r26_targets_by_site).issubset(candidate_sites):
        raise ValueError("An original R26 site is absent from the instruction inventory")
    return rows


def split_functions(sections: list[dict[str, Any]], split_offsets: dict[int, set[int]]) -> tuple[list[list[dict[str, int | str]]], int, int]:
    rewritten: list[list[dict[str, int | str]]] = []
    split_count = 0
    uncovered_count = 0
    for section_index, section in enumerate(sections):
        base = int(section["vram"])
        functions = sorted(section["functions"], key=lambda item: int(item["vram"]))
        output: list[dict[str, int | str]] = []
        pending = set(split_offsets.get(section_index, set()))
        for function in functions:
            start = int(function["vram"]) - base
            end = start + int(function["size"])
            cuts = sorted(offset for offset in pending if start < offset < end)
            split_count += len(cuts)
            pending.difference_update(cuts)
            pending.discard(start)
            if end <= start or start % 4 or (end - start) % 4:
                raise ValueError("invalid function boundary")
            # Keep the authoritative body intact. Interior direct-call targets are
            # alternate entry points, so add deterministic overlapping bodies from
            # each entry to the original end instead of severing intra-body branches.
            output.append({"vram": base + start, "size": end - start})
            for entry in cuts:
                if entry % 4 or end <= entry:
                    raise ValueError("invalid synthesized entry boundary")
                output.append({"vram": base + entry, "size": end - entry})
        uncovered_count += len(pending)
        rewritten.append(sorted(output, key=lambda item: (int(item["vram"]), -int(item["size"]))))
    for section_index, functions in enumerate(rewritten):
        for ordinal, function in enumerate(functions):
            function["name"] = f"fn_{section_index:03d}_{ordinal:04d}"
    return rewritten, split_count, uncovered_count


def write_symbol_file(
    path: Path,
    sections: list[dict[str, Any]],
    functions: list[list[dict[str, int | str]]],
    relocs: dict[int, list[dict[str, int | str]]],
) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for section_index, section in enumerate(sections):
            stream.write("[[section]]\n")
            stream.write(f'name = "section_{section_index:03d}"\n')
            stream.write(f'rom = 0x{int(section["rom"]):08X}\n')
            stream.write(f'vram = 0x{int(section["vram"]):08X}\n')
            stream.write(f'size = 0x{int(section["size"]):08X}\n')
            stream.write(f'relocation_size = 0x{int(section["relocation_size"]):08X}\n')
            stream.write("functions = [\n")
            for function in functions[section_index]:
                stream.write(
                    "    { name = %s, vram = 0x%08X, size = 0x%08X },\n"
                    % (toml_quote(str(function["name"])), int(function["vram"]), int(function["size"]))
                )
            stream.write("]\n")
            stream.write("relocs = [\n")
            for reloc in sorted(relocs.get(section_index, []), key=lambda item: int(item["vram"])):
                stream.write(
                    "    { type = %s, vram = 0x%08X, target_section = %d, target_section_offset = 0x%08X },\n"
                    % (
                        toml_quote(str(reloc["type"])),
                        int(reloc["vram"]),
                        int(reloc["target_section"]),
                        int(reloc["target_section_offset"]),
                    )
                )
            stream.write("]\n\n")


def write_config(path: Path) -> None:
    path.write_text(
        "[input]\n"
        'symbols_file_path = "symbols-private.toml"\n'
        'rom_file_path = "patched-private.z64"\n'
        'output_func_path = "generated"\n'
        'indirect_decision_sidecar_path = "generated/indirect_decisions.json"\n'
        "functions_per_output_file = 50\n"
        "unpaired_lo16_warnings = false\n"
        "use_lookup_for_all_function_calls = true\n",
        encoding="utf-8",
        newline="\n",
    )
