"""Bounded regional overlay metadata from the pinned original linker format.

Only the enclosing ROM preparation command admits real images. These helpers
also accept synthetic bytes so malformed boundaries can be tested without ROMs.
"""
from dataclasses import dataclass
from scripts.transform_private_n64recomp_inputs import HEADER, Header


@dataclass(frozen=True)
class RegionalLayout:
    main_relocations: int
    references: int
    headers: int
    data: int
    symbols: int
    names: int


# Table/symbol boundaries: pinned decomp tools/extract_symbols.py ROM_OFFSETS.
# Main relocation boundaries: unique bounded table and direct-call validation.
REGIONAL_LAYOUTS = {
    "pal": RegionalLayout(0x1EC7CF0, 0x1EC8D40, 0x1ECB260, 0x1ECC600, 0x1FE5660, 0x1FE81C0),
    "jpn": RegionalLayout(0x1EC65F0, 0x1EC7640, 0x1EC9B60, 0x1ECAF00, 0x1FE23A0, 0x1FE4F00),
}


def checked_headers(rom: bytes, layout: RegionalLayout) -> list[Header]:
    boundaries = (layout.main_relocations, layout.references, layout.headers,
                  layout.data, layout.symbols, layout.names, len(rom))
    if any(a < 0 or a >= b or a % 4 for a, b in zip(boundaries, boundaries[1:])):
        raise ValueError("Unordered or unaligned regional boundaries.")
    if layout.data - layout.headers != 157 * HEADER.size:
        raise ValueError("Unexpected regional overlay table size.")
    headers = [Header(slot, *row) for slot, row in
               enumerate(HEADER.iter_unpack(rom[layout.headers:layout.data]), 1)]
    if sum(h.populated for h in headers) != 155:
        raise ValueError("Unexpected regional overlay population.")
    previous_end = layout.data
    for h in headers:
        if not h.populated:
            if h.primary_bytes or h.secondary_bytes:
                raise ValueError("Empty overlay has relocation bytes.")
            continue
        start = layout.data + h.rom_offset
        end = start + h.text_size + h.data_size + h.primary_bytes + h.secondary_bytes
        if (h.rom_offset < 0 or start < previous_end or start % 8 or h.text_size <= 0
                or h.text_size % 4 or h.data_size < 0 or h.data_size % 4
                or h.bss_size < 0 or h.primary_bytes % 8 or h.secondary_bytes % 8
                or end > layout.symbols):
            raise ValueError("Invalid regional overlay extent or relocation byte count.")
        if any(value != -1 and (value < 0 or value >= h.text_size or value % 4)
               for value in (h.init_offset, h.resume_offset)):
            raise ValueError("Regional overlay entry lies outside executable code.")
        previous_end = end
    return headers


def overlay_segments(rom: bytes, layout: RegionalLayout, region: str) -> str:
    if region not in REGIONAL_LAYOUTS:
        raise ValueError("Unknown metadata region.")
    lines = []
    previous_end = layout.data
    for h in checked_headers(rom, layout):
        if not h.populated:
            continue
        start = layout.data + h.rom_offset
        if start > previous_end:
            lines.extend(["  - type: bin", f"    start: 0x{previous_end:X}"])
        vram = h.vram_base or h.slot << 20
        lines.extend([f"  - name: overlay_{h.slot}", "    type: code",
                      f"    start: 0x{start:X}", f"    vram: 0x{vram:X}",
                      f"    bss_size: 0x{h.bss_size:X}", "    align: 0x8",
                      f"    dir: overlays_{region}/o{h.slot}",
                      f"    exclusive_ram_id: overlay_{h.slot}",
                      "    symbol_name_format: $SEG_$VRAM_$ROM", "    subsegments:",
                      f"      - [0x{start:X}, asm, overlay_{h.slot}]"])
        if h.data_size:
            lines.append(f"      - [0x{start+h.text_size:X}, data, overlay_{h.slot}]")
        if h.primary_bytes + h.secondary_bytes:
            lines.append(f"      - [0x{start+h.text_size+h.data_size:X}, bin, overlay_{h.slot}_reloc]")
        previous_end = start + h.text_size + h.data_size + h.primary_bytes + h.secondary_bytes
    if previous_end < layout.symbols:
        lines.extend(["  - type: bin", f"    start: 0x{previous_end:X}"])
    return "\n".join(lines) + "\n"


def expand_regional_overlays(text: str, rom: bytes, region: str) -> str:
    layout = REGIONAL_LAYOUTS[region]
    segments = overlay_segments(rom, layout, region)
    if region == "jpn":
        start, end = "  - name: overlay_1\n", "  - name: symbolsTable_offsets\n"
        if text.count(start) != 1 or text.count(end) != 1 or text.index(start) >= text.index(end):
            raise ValueError("Unexpected Japanese overlay metadata shape.")
        return text[:text.index(start)] + segments + text[text.index(end):]
    marker = "  - type: bin\n    start: 0xB1A30"
    if text.count(marker) != 1 or not text.rstrip().endswith("- [0x2000000]"):
        raise ValueError("Unexpected PAL opaque metadata shape.")
    named = [("assets", 0xB1A30), ("mainRelocTable", layout.main_relocations),
             ("overlayRomTable", layout.references), ("overlayTable", layout.headers)]
    prefix = "".join(f"  - name: {name}\n    type: bin\n    start: 0x{offset:X}\n"
                     for name, offset in named)
    suffix = (f"  - name: symbolsTable_offsets\n    type: bin\n    start: 0x{layout.symbols:X}\n"
              f"  - name: symbolsTable_symbol_names\n    type: bin\n    start: 0x{layout.names:X}\n"
              "  - [0x2000000]\n")
    return text[:text.index(marker)] + prefix + segments + suffix
