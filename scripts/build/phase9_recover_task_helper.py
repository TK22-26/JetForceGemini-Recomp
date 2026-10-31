"""Recover missing private OS symbol metadata without changing any loaded bytes.

This emits a NEW local ELF for a diagnostic generation revision. It does not
modify the original ELF, claim Phase 4 acceptance, or bypass fixed denominators.
Run with the MIPS binutils available (WSL).
"""

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from scripts.validate_elf import parse_header, parse_sections, parse_symbols

ROOT = Path(__file__).resolve().parents[2]
ROM_SHA256 = "159dde164c475976a3e527fbb20978431d4765f2c63019b3530c3aa8772595aa"
ENTRY, END, CALLER = 0x80098f40, 0x8009905c, 0x80099068
NAME = "_VirtualToPhysicalTask"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect(elf, option):
    return subprocess.run(["mips-linux-gnu-readelf", option, str(elf)],
                          capture_output=True, text=True, check=True, timeout=60).stdout


def validate_cfg(words, entry, allowed_calls):
    """Conservative acyclic integer-routine boundary check, not CPU execution."""
    if not words or entry % 4:
        raise ValueError("invalid routine extent")
    pending, visited, delays, calls, returns = [0], set(), set(), Counter(), 0
    while pending:
        index = pending.pop()
        if index in visited:
            continue
        if not 0 <= index < len(words) or index in delays:
            raise ValueError("control flow leaves body or enters a delay slot")
        visited.add(index)
        word = words[index]
        opcode = word >> 26
        pc = entry + index * 4
        transfer = opcode in (3, 4) or word == 0x03e00008
        if transfer:
            if index + 1 >= len(words) or index + 1 in visited:
                raise ValueError("missing or multiply entered delay slot")
            slot = words[index + 1]
            # Only non-branch integer operations are admitted in delay slots.
            if not (slot == 0 or slot >> 26 in (9, 15, 35, 43) or
                    (slot >> 26 == 0 and slot & 63 == 37)):
                raise ValueError("unqualified delay slot")
            delays.add(index + 1)
            if opcode == 3:
                target = ((pc + 4) & 0xf0000000) | ((word & 0x3ffffff) << 2)
                if target not in allowed_calls:
                    raise ValueError("unqualified callee")
                calls[target] += 1
                pending.append(index + 2)
            elif opcode == 4:
                immediate = word & 0xffff
                if immediate & 0x8000:
                    immediate -= 0x10000
                target = index + 1 + immediate
                if target <= index + 1 or target >= len(words):
                    raise ValueError("branch is not confined and forward")
                pending.extend((index + 2, target))
            else:
                returns += 1
                if index != len(words) - 2:
                    raise ValueError("unexpected return boundary")
        else:
            if not (word == 0 or opcode in (9, 15, 35, 43) or
                    (opcode == 0 and word & 63 == 37)):
                raise ValueError("unqualified instruction")
            pending.append(index + 1)
    if returns != 1 or visited & delays or len(visited | delays) != len(words):
        raise ValueError("body is not completely covered by validated control flow")
    return calls


def validate_pi_init(words):
    """Straight-line helper: integer loads/stores, one terminal return pair."""
    if len(words) != 30 or words[-2:] != (0x03e00008, 0):
        raise ValueError('PI initialization helper boundary differs')
    if any(word >> 26 not in (9, 15, 35, 40) for word in words[:-2]):
        raise ValueError('PI initialization helper has unqualified control flow')
    return Counter()


def validate_loop_cfg(words, entry, allowed_calls, dead_start):
    """Closed integer loop plus explicit unreachable padding/epilogue.

    The dead suffix must itself be linear, with one terminal return and at
    most one alignment NOP. It is not misreported as reachable code.
    """
    def integer(word):
        return word == 0 or word >> 26 in (9, 12, 15, 35, 37, 41, 43) or \
            (word >> 26 == 0 and word & 63 in (33, 35, 37, 43))
    if not words or entry % 4 or not 0 < dead_start < len(words):
        raise ValueError('invalid loop extent')
    pending, visited, delays, calls = [0], set(), set(), Counter()
    while pending:
        index = pending.pop()
        if index in visited:
            continue
        if not 0 <= index < dead_start or index in delays:
            raise ValueError('loop flow leaves live body or enters delay slot')
        visited.add(index)
        word, pc = words[index], entry + index * 4
        primary = word >> 26
        if primary in (3, 4, 5, 20, 21):
            if index + 1 >= dead_start or index + 1 in visited or not integer(words[index + 1]):
                raise ValueError('unqualified loop delay slot')
            delays.add(index + 1)
            if primary == 3:
                target = ((pc + 4) & 0xf0000000) | ((word & 0x3ffffff) << 2)
                if target not in allowed_calls:
                    raise ValueError('unqualified loop callee')
                calls[target] += 1
                pending.append(index + 2)
            else:
                offset = word & 0xffff
                if offset & 0x8000:
                    offset -= 0x10000
                pending.append(index + 1 + offset)
                # BEQ zero,zero has no fallthrough.
                if not (primary == 4 and (word >> 16) & 0x3ff == 0):
                    pending.append(index + 2)
        else:
            if not integer(word):
                raise ValueError('unqualified loop instruction')
            pending.append(index + 1)
    if visited & delays or visited | delays != set(range(dead_start)):
        raise ValueError('incomplete live loop coverage')
    suffix = words[dead_start:]
    if suffix[-1] == 0:
        suffix = suffix[:-1]
    if len(suffix) < 2 or suffix[-2] != 0x03e00008 or not integer(suffix[-1]) or \
            any(not integer(word) for word in suffix[:-2]):
        raise ValueError('unqualified unreachable epilogue')
    return calls


def validate_thread_entry_reference(words, entry, create_thread):
    """Validate a bounded LUI/addiu a2 argument feeding a direct create call."""
    value = None
    for index, word in enumerate(words):
        primary, rs, rt = word >> 26, (word >> 21) & 31, (word >> 16) & 31
        if index == len(words) - 2:
            if primary != 3 or ((word & 0x3ffffff) << 2 | 0x80000000) != create_thread:
                raise ValueError('thread entry has no create-thread caller')
        elif primary == 15 and rt == 6:
            value = (word & 0xffff) << 16
        elif primary == 9 and rs == rt == 6 and value is not None:
            immediate = word & 0xffff
            value = (value + (immediate - 0x10000 if immediate & 0x8000 else immediate)) & 0xffffffff
        elif primary not in (0, 9, 43) or (primary == 9 and rt == 6) or \
                (primary == 0 and word != 0 and (word & 63 != 37 or ((word >> 11) & 31) == 6)):
            raise ValueError('unqualified thread entry argument construction')
    if value != entry:
        raise ValueError('thread argument does not reference recovered entry')


def validate_returning_loop(words, entry):
    """Closed integer leaf with loops, one reachable return, alignment padding."""
    def integer(word):
        return word == 0 or word >> 26 in (0x09, 0x0a, 0x0d, 0x0f, 0x23, 0x24, 0x28, 0x29, 0x2a, 0x2b, 0x2e) or \
            (word >> 26 == 0 and word & 63 in (0, 33, 42))
    if not words or entry % 4:
        raise ValueError('invalid leaf loop extent')
    end = len(words)
    while end and words[end-1] == 0:
        end -= 1
    if len(words)-end > 2 or end < 2 or words[end-2] != 0x03e00008:
        raise ValueError('leaf loop return/padding differs')
    pending, visited, slots = [0], set(), set()
    while pending:
        index = pending.pop()
        if index in visited:
            continue
        if not 0 <= index < end or index in slots:
            raise ValueError('leaf flow leaves body or enters delay slot')
        visited.add(index)
        word = words[index]
        primary = word >> 26
        if primary in (4, 5, 6) or word == 0x03e00008:
            if index+1 >= end or index+1 in visited or not integer(words[index+1]):
                raise ValueError('unqualified leaf delay slot')
            slots.add(index+1)
            if word == 0x03e00008:
                if index != end-2:
                    raise ValueError('unexpected leaf return')
                continue
            offset = word & 0xffff
            if offset & 0x8000: offset -= 0x10000
            pending.append(index+1+offset)
            if primary != 4 or (word >> 16) & 0x3ff:
                pending.append(index+2)
        else:
            if not integer(word):
                raise ValueError('unqualified leaf instruction')
            pending.append(index+1)
    if visited & slots or visited | slots != set(range(end)):
        raise ValueError('incomplete leaf coverage')
    return Counter()



def validate_switch_boundary(words, entry, allowed_calls, switches, *, shared_slots=()):
    """Check every transfer in a pinned routine, including compiler padding.

    This is boundary validation, not a claim that every instruction is reachable.
    Each indirect branch must have an explicitly qualified complete jump table.
    The caller separately pins the full ROM and compares ELF body/table bytes.
    """
    if not words or entry % 4 or len(words) < 2 or words[-2] != 0x03e00008:
        raise ValueError("invalid switch routine boundary")
    def transfer(word):
        op = word >> 26
        return (op in (1, 2, 3, 4, 5, 6, 7, 20, 21, 22, 23) or
                (op == 0 and word & 63 in (8, 9)) or
                (op == 17 and (word >> 21) & 31 == 8))
    calls, targets, slots, returns, seen_switches = Counter(), set(), set(), 0, set()
    for index, word in enumerate(words):
        if not transfer(word):
            continue
        op, pc = word >> 26, entry + index * 4
        if index + 1 >= len(words) or transfer(words[index + 1]):
            raise ValueError("missing or branching delay slot")
        slots.add(index + 1)
        if op == 3:
            target = ((pc + 4) & 0xf0000000) | ((word & 0x3ffffff) << 2)
            if target not in allowed_calls:
                raise ValueError("unqualified switch callee")
            calls[target] += 1
        elif word == 0x03e00008:
            if index != len(words) - 2:
                raise ValueError("unexpected switch return boundary")
            returns += 1
        elif op == 0:
            if word & 63 != 8 or index not in switches or not switches[index]:
                raise ValueError("unqualified indirect transfer")
            targets.update(switches[index])
            seen_switches.add(index)
        elif op == 2:
            targets.add(((pc + 4) & 0xf0000000) | ((word & 0x3ffffff) << 2))
        else:
            if op == 1 and (word >> 16) & 31 not in (0, 1, 2, 3):
                raise ValueError("unqualified regimm transfer")
            immediate = word & 0xffff
            if immediate & 0x8000:
                immediate -= 0x10000
            targets.add(pc + 4 + immediate * 4)
    if returns != 1 or seen_switches != switches.keys():
        raise ValueError("incomplete switch boundary")
    shared_slots = set(shared_slots)
    if not shared_slots <= slots or any(entry + i * 4 not in targets for i in shared_slots):
        raise ValueError("unqualified shared delay-slot entry")
    if any(target % 4 or not entry <= target < entry + 4 * len(words) or
           ((target - entry) // 4 in slots - shared_slots) for target in targets):
        raise ValueError("switch or branch leaves body or enters delay slot")
    return calls


def run(output, elf, elf_sha256, rom, helper='task'):
    if helper == 'task':
        entry, end, caller, name = ENTRY, END, CALLER, NAME
    elif helper == 'pi-init':
        entry, end, caller, name = 0x80097788, 0x80097800, 0x8009767c, '_ObservedPiHandleInitialize'
    elif helper == 'vi-main':
        entry, end, caller, name = 0x80098bb8, 0x80098d50, 0x80098b30, '_ObservedViManagerMain'
    elif helper == 'cont-read-pack':
        entry, end, caller, name = 0x80097e7c, 0x80097f70, 0x80097d38, '_ObservedControllerReadPack'
    elif helper == 'printf-float':
        entry, end, caller, name = 0x8009cdc0, 0x8009d330, 0x8009d84c, '_ObservedPrintfFloat'
    elif helper == 'printf-field':
        entry, end, caller, name = 0x8009be20, 0x8009c490, 0x8009c768, '_ObservedPrintfField'
    else:
        raise ValueError('unknown helper')
    output_exists = output.exists() or output.is_symlink()
    output, elf, rom = output.resolve(), elf.resolve(strict=True), rom.resolve(strict=True)
    # Luke Deardoff (@lukedeardoff) reported the short-cache conflict and
    # proposed permitting external output while protecting the checkout.
    inside_checkout = output.is_relative_to(ROOT.resolve())
    if output_exists or (inside_checkout and not output.is_relative_to(ROOT.resolve() / "tools/private")):
        raise ValueError("use a new output directory outside the checkout or under tools/private")
    original, image = elf.read_bytes(), rom.read_bytes()
    if digest(original) != elf_sha256 or digest(image) != ROM_SHA256:
        raise ValueError("private input identity mismatch")
    header = parse_header(inspect(elf, "-h"))
    if (header.get("class"), header.get("endianness"), header.get("machine"), header.get("type")) != \
            ("ELF32", "big", "MIPS", "EXEC"):
        raise ValueError("unsupported ELF identity")
    sections = parse_sections(inspect(elf, "-SW"))
    symbols = parse_symbols(inspect(elf, "-sW"))
    main = [section for section in sections if section.name == ".main"]
    if len(main) != 1 or "X" not in main[0].flags:
        raise ValueError("missing unique executable main section")
    main = main[0]
    if not main.address <= entry < end <= main.address + main.size or \
            any(symbol.name == name for symbol in symbols):
        raise ValueError("helper metadata already present or outside main")
    functions = [symbol for symbol in symbols if symbol.symbol_type == "FUNC" and
                 symbol.section == str(main.index)]
    if any(symbol.value < end and symbol.value + max(1, symbol.size) > entry for symbol in functions) or \
            len([symbol for symbol in functions if symbol.value == end and symbol.size > 0]) != 1:
        raise ValueError("helper extent overlaps existing code ownership or lacks following boundary")
    body = original[main.offset + entry - main.address:main.offset + end - main.address]
    rom_offset = 0x1000 + entry - 0x80000400
    if len(body) != end - entry or body != image[rom_offset:rom_offset + len(body)]:
        raise ValueError("ELF and original ROM helper bytes differ")
    call_targets = {}
    callees = {'task': ('_bcopy', 'osVirtualToPhysical'), 'pi-init': (),
        'cont-read-pack': (), 'printf-field': ('_Litob', '_Ldtob', 'strlen'),
        'printf-float': ('memcpy',),
        'vi-main': ('__osViGetCurrentContext', 'osRecvMesg', '__osViSwapContext',
                    'osSendMesg', 'osGetCount', '__osTimerInterrupt')}[helper]
    for callee_name in callees:
        candidates = [symbol for symbol in functions if symbol.name == callee_name and symbol.size > 0]
        if len(candidates) != 1:
            raise ValueError("missing unique known OS callee")
        call_targets[callee_name] = candidates[0].value
    words = struct.unpack(f">{len(body) // 4}I", body)
    if helper == 'task':
        calls = validate_cfg(words, entry, set(call_targets.values()))
    elif helper == 'pi-init':
        calls = validate_pi_init(words)
    elif helper == 'cont-read-pack':
        calls = validate_returning_loop(words, entry)
    elif helper == 'printf-float':
        # Static _Genld, reached by the restored field formatter's floating
        # conversion path. The final return/NOP is an unreachable SDK suffix.
        # Pinned instruction 22 is a legal shared SLTI delay-slot entry, reached
        # directly by the general-format branch as well as its preceding BNE.
        if (digest(body) != 'f46c3799a2536e3fb29151c2db7a1134705df4c890492118c365cba910ff0060' or
            words[-2:] != (0x03e00008, 0)):
            raise ValueError('printf float body differs from qualified ROM')
        calls = validate_switch_boundary(words[:-2], entry, set(call_targets.values()), {},
                                         shared_slots={22})
        if calls != Counter({call_targets['memcpy']: 5}):
            raise ValueError('unexpected printf float call graph')
    elif helper == 'printf-field':
        # The static _Putfld has no FUNC metadata in the pinned upstream ELF.
        # Its switch table is data, not an additional executable function.
        table_address, table_size = 0x800afad4, 52 * 4
        table_sections = [s for s in sections if s.allocated and s.section_type != 'NOBITS'
                          and s.address <= table_address
                          and table_address + table_size <= s.address + s.size]
        if len(table_sections) != 1:
            raise ValueError('missing unique printf switch table')
        section = table_sections[0]
        table = original[section.offset + table_address - section.address:
                         section.offset + table_address - section.address + table_size]
        rom_table = 0x1000 + table_address - 0x80000400
        if (table != image[rom_table:rom_table + table_size] or
            digest(body) != '345ec57026773ced526589ec8fc2379375e2bd7a6c7315e24528335da4012eac' or
            digest(table) != '4ee2d8b8d3108914e6d0012d6d6bef6c86a2e5a134210e3cb90431c86a9ef77c'):
            raise ValueError('printf body or switch table differs from qualified ROM')
        calls = validate_switch_boundary(words, entry, set(call_targets.values()),
                                         {21: struct.unpack('>52I', table)})
        if calls != Counter({call_targets['_Litob']: 3, call_targets['_Ldtob']: 1,
                             call_targets['strlen']: 1}):
            raise ValueError('unexpected printf field call graph')
    else:
        calls = validate_loop_cfg(words, entry, set(call_targets.values()), (0x80098d08 - entry) // 4)
        expected = Counter(call_targets.values())
        expected[call_targets['__osViGetCurrentContext']] += 1
        if calls != expected:
            raise ValueError('unexpected VI worker call graph')
    if helper == 'task' and calls != Counter({call_targets["_bcopy"]: 1, call_targets["osVirtualToPhysical"]: 7}):
        raise ValueError("unexpected helper call graph")
    if helper == 'vi-main':
        create = [s for s in functions if s.name == 'osCreateThread' and s.size > 0]
        if len(create) != 1:
            raise ValueError('missing create-thread boundary')
        reference = struct.unpack_from('>15I', original, main.offset + caller - main.address)
        validate_thread_entry_reference(reference, entry, create[0].value)
    else:
        caller_word = struct.unpack_from(">I", original, main.offset + caller - main.address)[0]
        if caller_word >> 26 != 3 or ((caller + 4) & 0xf0000000) | ((caller_word & 0x3ffffff) << 2) != entry:
            raise ValueError("original caller does not call the recovered entry")
    output.mkdir()
    target = output / f"input-with-{helper}-helper.elf"
    subprocess.run(["mips-linux-gnu-objcopy", "--add-symbol",
                    f"{name}=.main:0x{entry - main.address:x},global,function", str(elf), str(target)],
                   check=True, timeout=60)
    modified = target.read_bytes()
    after_sections = parse_sections(inspect(target, "-SW"))
    if {(section.name, section.section_type, section.address, section.size, section.flags)
        for section in sections if section.allocated} != \
       {(section.name, section.section_type, section.address, section.size, section.flags)
        for section in after_sections if section.allocated}:
        raise ValueError("allocated section metadata changed")
    for section in sections:
        if not section.allocated or section.section_type == "NOBITS":
            continue
        matches = [candidate for candidate in after_sections if candidate.name == section.name]
        if len(matches) != 1 or matches[0].address != section.address or matches[0].size != section.size or \
                modified[matches[0].offset:matches[0].offset + section.size] != \
                original[section.offset:section.offset + section.size]:
            raise ValueError("loaded ELF bytes changed during metadata recovery")
    after_symbols = parse_symbols(inspect(target, "-sW"))
    recovered = [symbol for symbol in after_symbols if symbol.name == name]
    if len(after_symbols) != len(symbols) + 1 or len(recovered) != 1 or \
            recovered[0].symbol_type != "FUNC" or recovered[0].value != entry or recovered[0].size != 0:
        raise ValueError("recovered symbol identity incorrect")
    if digest(elf.read_bytes()) != elf_sha256:
        raise ValueError("source ELF changed")
    result = {"kind": "jfg-private-task-helper-symbol-recovery", "acceptance": False, "helper": helper,
              "source_elf_sha256": elf_sha256, "source_rom_sha256": ROM_SHA256,
              "output_elf_sha256": digest(modified), "helper_sha256": digest(body),
              "recovered_bytes": len(body), "direct_calls": sum(calls.values()),
              "loaded_sections_unchanged": True, "source_elf_unchanged": True,
              "size_policy": ('pinned ROM formatter; checked branches, switch table and calls; terminal return'
                              if helper == 'printf-field' else
                              'pinned ROM float formatter; checked branches/calls; explicit return suffix'
                              if helper == 'printf-float' else 'closed loop CFG; explicit unreachable epilogue/padding; next executable boundary'
                              if helper == 'vi-main' else 'validated integer CFG; terminal return; next executable boundary'),
              "phase4_denominator_refresh_required": True,
              "script_sha256": digest(Path(__file__).read_bytes())}
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--elf-sha256", required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--helper", choices=('task', 'pi-init', 'vi-main', 'cont-read-pack', 'printf-field', 'printf-float'), default='task')
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.elf, args.elf_sha256, args.rom, args.helper)))
