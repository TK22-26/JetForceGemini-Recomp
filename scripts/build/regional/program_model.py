"""Checked section-qualified program identity, independent of regional coordinates.

This module accepts synthetic data for contract tests. Real-input adapters must
verify ROM identity and matching reconstruction before constructing a model.
Models are private metadata, not gameplay qualification or runtime admission.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import re

class SectionKind(str, Enum):
    ENTRY = "entry"
    MAIN = "main"
    OVERLAY = "overlay"

class AddressDomain(str, Enum):
    TEXT = "text"
    DATA = "data"
    BSS = "bss"
    RETAINED_RELOCATIONS = "retained-relocations"

def integer(value: int, label: str, *, minimum: int = 0, maximum: int = 0xFFFFFFFF) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid " + label)
    return value

def aligned(value: int, label: str, alignment: int = 4) -> int:
    integer(value, label)
    if value % alignment:
        raise ValueError("Unaligned " + label)
    return value

def digest(value: str, size: int, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{" + str(size) + "}", value):
        raise ValueError("Invalid " + label)
    return value

@dataclass(frozen=True)
class Section:
    id: str
    kind: SectionKind
    source_index: int
    rom_start: int
    linked_vram: int
    text_size: int
    data_size: int
    bss_size: int
    overlay_slot: int | None = None
    retained_relocation_size: int = 0

    @property
    def initialized_size(self) -> int:
        return self.text_size + self.data_size

    @property
    def memory_size(self) -> int:
        return self.initialized_size + self.bss_size

    def validate(self, rom_size: int) -> None:
        if not isinstance(self.id, str) or not re.fullmatch(r"[a-z][a-z0-9:_-]*", self.id):
            raise ValueError("Invalid section identity")
        if not isinstance(self.kind, SectionKind):
            raise ValueError("Unknown section kind")
        integer(self.source_index, "source index")
        for name in ("rom_start", "linked_vram", "text_size", "data_size", "bss_size", "retained_relocation_size"):
            aligned(getattr(self, name), name)
        if self.text_size == 0 or self.rom_start + self.initialized_size > rom_size:
            raise ValueError("Section lies outside ROM or has no executable text")
        if self.linked_vram + self.memory_size + self.retained_relocation_size > 0x100000000:
            raise ValueError("Section address range overflows")
        if self.kind == SectionKind.OVERLAY:
            integer(self.overlay_slot, "overlay slot", minimum=1)
        elif self.overlay_slot is not None or self.retained_relocation_size:
            raise ValueError("Static section carries overlay-only metadata")

    def domain(self, kind: AddressDomain) -> tuple[int, int]:
        if kind == AddressDomain.TEXT: return 0, self.text_size
        if kind == AddressDomain.DATA: return self.text_size, self.data_size
        if kind == AddressDomain.BSS: return self.initialized_size, self.bss_size
        if kind == AddressDomain.RETAINED_RELOCATIONS: return self.memory_size, self.retained_relocation_size
        raise ValueError("Unknown address domain")

    def checked_offset(self, kind: AddressDomain, offset: int, width: int = 1, *, patch: bool = False) -> int:
        integer(offset, "domain offset")
        integer(width, "access width", minimum=1)
        start, size = self.domain(kind)
        if offset + width > size:
            raise ValueError("Access leaves its declared section domain")
        if patch and kind not in (AddressDomain.TEXT, AddressDomain.DATA):
            raise ValueError("Relocation patch cannot write BSS or retained metadata")
        return start + offset

@dataclass(frozen=True)
class FunctionBody:
    section: str
    offset: int
    size: int
    names: tuple[str, ...]

    @property
    def identity(self) -> tuple[str, int]:
        return self.section, self.offset

@dataclass(frozen=True)
class FunctionAlias:
    name: str
    section: str
    offset: int
    body_offset: int

@dataclass(frozen=True)
class CodeRef:
    revision_id: str
    section: str
    offset: int

@dataclass(frozen=True)
class ProgramModel:
    revision_id: str
    rom_sha1: str
    rom_size: int
    elf_sha256: str
    sections: tuple[Section, ...]
    bodies: tuple[FunctionBody, ...]
    aliases: tuple[FunctionAlias, ...] = ()
    schema_version: int = 1

    def validate(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported program model schema")
        if not isinstance(self.revision_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]+", self.revision_id):
            raise ValueError("Invalid revision identity")
        digest(self.rom_sha1, 40, "ROM digest")
        digest(self.elf_sha256, 64, "ELF digest")
        integer(self.rom_size, "ROM size", minimum=64)
        if not self.sections or sum(s.kind == SectionKind.MAIN for s in self.sections) != 1 or sum(s.kind == SectionKind.ENTRY for s in self.sections) > 1:
            raise ValueError("Program needs one main and at most one distinct entry section")
        sections = {}
        source_indices = set()
        slots = set()
        for section in self.sections:
            section.validate(self.rom_size)
            if section.id in sections or section.source_index in source_indices:
                raise ValueError("Duplicate section identity or source index")
            sections[section.id] = section
            source_indices.add(section.source_index)
            if section.overlay_slot is not None:
                if section.overlay_slot in slots: raise ValueError("Duplicate overlay slot")
                slots.add(section.overlay_slot)
        rom_ranges = sorted((s.rom_start, s.rom_start + s.initialized_size) for s in self.sections)
        if any(left[1] > right[0] for left, right in zip(rom_ranges, rom_ranges[1:])):
            raise ValueError("Initialized ROM sections overlap")
        static_ranges = sorted((s.linked_vram, s.linked_vram + s.memory_size) for s in self.sections if s.kind != SectionKind.OVERLAY)
        if any(left[1] > right[0] for left, right in zip(static_ranges, static_ranges[1:])):
            raise ValueError("Static memory sections overlap")
        names = set()
        identities = set()
        body_ranges = {}
        for body in self.bodies:
            section = sections.get(body.section)
            if section is None: raise ValueError("Function has an unknown section")
            aligned(body.offset, "function offset")
            aligned(body.size, "function size")
            if body.size == 0 or body.offset + body.size > section.text_size:
                raise ValueError("Function extends outside executable text")
            if body.identity in identities: raise ValueError("Duplicate function body")
            identities.add(body.identity)
            if not body.names or len(set(body.names)) != len(body.names): raise ValueError("Missing or duplicate function names")
            for name in body.names:
                if not isinstance(name, str) or not name or (body.section, body.offset, name) in names:
                    raise ValueError("Ambiguous function name")
                names.add((body.section, body.offset, name))
            body_ranges.setdefault(body.section, []).append((body.offset, body.offset + body.size))
        for ranges in body_ranges.values():
            ranges.sort()
            if any(a[1] > b[0] for a, b in zip(ranges, ranges[1:])):
                raise ValueError("Overlapping function bodies need explicit alias classification")
        bodies = {b.identity: b for b in self.bodies}
        for alias in self.aliases:
            aligned(alias.offset, "alias offset")
            aligned(alias.body_offset, "alias body offset")
            body = bodies.get((alias.section, alias.body_offset))
            if body is None or not body.offset <= alias.offset < body.offset + body.size:
                raise ValueError("Alias does not resolve inside its declared body")
            if not isinstance(alias.name, str) or not alias.name or (alias.section, alias.offset, alias.name) in names:
                raise ValueError("Ambiguous alias name")
            names.add((alias.section, alias.offset, alias.name))

    def resolve(self, reference: CodeRef) -> FunctionBody:
        self.validate()
        if reference.revision_id != self.revision_id:
            raise ValueError("Code reference belongs to another revision")
        aligned(reference.offset, "code reference")
        for body in self.bodies:
            if body.identity == (reference.section, reference.offset): return body
        for alias in self.aliases:
            if (alias.section, alias.offset) == (reference.section, reference.offset):
                return next(b for b in self.bodies if b.identity == (alias.section, alias.body_offset))
        raise ValueError("Code reference is not a declared function or alternate entry")

    def canonical_bytes(self) -> bytes:
        self.validate()
        value = asdict(self)
        value["sections"] = sorted(value["sections"], key=lambda row: row["id"])
        value["bodies"] = sorted(value["bodies"], key=lambda row: (row["section"], row["offset"]))
        value["aliases"] = sorted(value["aliases"], key=lambda row: (row["section"], row["offset"], row["name"]))
        return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def from_document(value: dict) -> ProgramModel:
    """Read a complete model; reject unknown fields and malformed collections."""
    if not isinstance(value, dict) or set(value) != set(ProgramModel.__dataclass_fields__):
        raise ValueError("Invalid program model fields")
    for name in ("sections", "bodies", "aliases"):
        if not isinstance(value[name], list): raise ValueError("Invalid model collection")
    def row(kind, item):
        if not isinstance(item, dict) or set(item) != set(kind.__dataclass_fields__):
            raise ValueError("Invalid model row fields")
        return dict(item)
    sections = []
    for item in value["sections"]:
        item = row(Section, item); item["kind"] = SectionKind(item["kind"])
        sections.append(Section(**item))
    bodies = []
    for item in value["bodies"]:
        item = row(FunctionBody, item)
        if not isinstance(item["names"], list): raise ValueError("Invalid body names")
        item["names"] = tuple(item["names"]); bodies.append(FunctionBody(**item))
    model = ProgramModel(**{**value, "sections": tuple(sections), "bodies": tuple(bodies),
                            "aliases": tuple(FunctionAlias(**row(FunctionAlias, a)) for a in value["aliases"])})
    model.validate()
    return model
