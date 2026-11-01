"""Adapt exact-ROM linker/context metadata to the shared program model."""
from __future__ import annotations
from collections import defaultdict
import re
from scripts.rom_profiles import identify_rom
from scripts.regional.program_model import FunctionBody, ProgramModel, Section, SectionKind, integer

def linker_symbol(text: str, name: str) -> int:
    matches = re.findall(r"^\s*(0x[0-9a-fA-F]+)\s+" + re.escape(name) + r"\s*=", text, re.M)
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous linker boundary: " + name)
    return int(matches[0], 16)

def from_context(rom: bytes, elf_sha256: str, context: dict, data_context: dict,
                 map_text: str, headers, layout) -> ProgramModel:
    profile, _, _ = identify_rom(rom)
    rows = context.get("section")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Executable context is missing")
    overlays = {h.rom_start(layout): h for h in headers if h.populated}
    if len(overlays) != sum(h.populated for h in headers):
        raise ValueError("Overlay ROM identities overlap")
    sections, bodies, mapped_slots = [], [], set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict): raise ValueError("Invalid executable context section")
        for field in ("rom", "vram", "size"):
            integer(row.get(field), "context " + field)
        name = row.get("name")
        if name in (".entry", ".main"):
            prefix = name[1:]
            text_end = linker_symbol(map_text, prefix + "_TEXT_END")
            if name == ".main":
                from scripts.regional.linker_layout import original_main_domains
                domains = original_main_domains(rom, row)
                if (layout.main_text_size, layout.main_data_size) != (domains.data-domains.code, domains.bss-domains.data):
                    raise ValueError("Image layout differs from original linker domains")
                text_end = domains.data
            text_size = text_end - row["vram"]
            data_size = row["size"] - text_size
            bss_rows = [s for s in data_context.get("section", []) if s.get("name") == name + "_bss"]
            if len(bss_rows) != 1 or "rom" in bss_rows[0] or bss_rows[0].get("vram") != row["vram"] + row["size"]:
                raise ValueError("Static BSS extent is missing or not contiguous")
            section = Section(prefix, SectionKind(prefix), index, row["rom"], row["vram"],
                              text_size, data_size, bss_rows[0]["size"])
        else:
            header = overlays.get(row["rom"])
            if header is None or name != ".overlay_" + str(header.slot) or header.slot in mapped_slots:
                raise ValueError("Executable section does not identify a unique original overlay")
            if row["size"] < header.text_size + header.data_size:
                raise ValueError("Executable context truncates an original overlay")
            section = Section("overlay:" + str(header.slot), SectionKind.OVERLAY, index,
                              row["rom"], row["vram"], header.text_size, header.data_size,
                              header.bss_size, header.slot, header.primary_bytes)
            mapped_slots.add(header.slot)
        section.validate(len(rom))
        sections.append(section)
        grouped = defaultdict(list)
        functions = row.get("functions")
        if not isinstance(functions, list): raise ValueError("Executable section has no function inventory")
        for function in functions:
            if not isinstance(function, dict): raise ValueError("Malformed function inventory")
            vram = integer(function.get("vram"), "function address")
            size = integer(function.get("size"), "function extent", minimum=1)
            symbol = function.get("name")
            if not isinstance(symbol, str) or not symbol: raise ValueError("Missing function identifier")
            grouped[(vram - section.linked_vram, size)].append(symbol)
        for (offset, size), names in grouped.items():
            bodies.append(FunctionBody(section.id, offset, size, tuple(sorted(names))))
    if mapped_slots != {h.slot for h in headers if h.populated}:
        raise ValueError("Executable context omits populated original overlays")
    model = ProgramModel(profile.revision_id, profile.sha1, len(rom), elf_sha256, tuple(sections), tuple(bodies))
    model.validate()
    return model
