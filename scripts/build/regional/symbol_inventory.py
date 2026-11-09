"""Reconcile every ELF executable symbol with section-qualified bodies and aliases."""
from __future__ import annotations
from collections import Counter
from dataclasses import replace
from scripts.regional.program_model import FunctionAlias, ProgramModel

def reconcile(model: ProgramModel, elf_sections, symbols) -> tuple[ProgramModel, dict[str, int]]:
    model.validate()
    source_sections = {str(s.index): s for s in elf_sections}
    by_name = {(".overlay_" + str(s.overlay_slot) if s.overlay_slot is not None else "." + s.id): s for s in model.sections}
    executable = [s for s in symbols if s.symbol_type == "FUNC" and s.defined
                  and s.section in source_sections and "X" in source_sections[s.section].flags]
    names = {(body.section, body.offset, name) for body in model.bodies for name in body.names}
    seen, reached, reached_bodies, aliases = set(), set(), set(), []
    counts = Counter(executable_symbols=len(executable))
    for symbol in executable:
        source = source_sections[symbol.section]
        section = by_name.get(source.name)
        if section is None: raise ValueError("Executable symbol belongs to an unmodeled section")
        if section.linked_vram != source.address: raise ValueError("ELF/context section address mismatch")
        coordinate = symbol.value - section.linked_vram
        owners = [b for b in model.bodies if b.section == section.id and b.offset <= coordinate < b.offset + b.size]
        if len(owners) != 1: raise ValueError("Executable symbol has no unique body owner")
        body = owners[0]
        identity = (section.id, coordinate, symbol.name)
        if identity in seen: raise ValueError("Duplicate ELF executable symbol at the same section coordinate")
        seen.add(identity)
        if symbol.size:
            if coordinate != body.offset or symbol.size != body.size:
                raise ValueError("Sized ELF function differs from its context body")
            counts["sized_functions"] += 1
            reached_bodies.add(body.identity)
        else:
            counts["zero_size_functions"] += 1
            positive = [s for s in executable if s.size > 0 and s.section == symbol.section
                        and s.value <= symbol.value < s.value + s.size]
            if len(positive) > 1: raise ValueError("Zero-size alias has ambiguous ELF ownership")
            if positive:
                counts["covered_aliases"] += 1
                counts["body_start_aliases" if coordinate == body.offset else "interior_aliases"] += 1
            else:
                following = sorted({s.value for s in executable if s.section == symbol.section and s.value > symbol.value} | {source.address + source.size})
                if coordinate != body.offset or not following or following[0] - symbol.value != body.size:
                    raise ValueError("Uncovered zero-size function boundary differs from its context body")
                counts["recovered_zero_size_functions"] += 1
                reached_bodies.add(body.identity)
        if identity in names:
            if coordinate != body.offset: raise ValueError("Body name reused at an interior entry")
            reached.add(identity)
        else:
            aliases.append(FunctionAlias(symbol.name, section.id, coordinate, body.offset))
    if reached_bodies != {body.identity for body in model.bodies}:
        raise ValueError("Context bodies contain boundaries absent from the ELF symbol inventory")
    # The pinned recompiler disambiguates repeated local labels with ROM suffixes.
    # These are compiler labels; ELF ownership is proved by section and extent.
    counts["context_only_labels"] = len(names - reached)
    result = replace(model, aliases=tuple(aliases))
    result.validate()
    if len(reached) + len(aliases) != len(executable):
        raise ValueError("ELF symbol accounting did not close")
    counts["bodies"] = len(result.bodies)
    counts["explicit_aliases"] = len(aliases)
    return result, dict(sorted(counts.items()))
