"""Decode original custom-linker records into checked section coordinates.

This inventory is derived from the identified original image before rewriting
instructions. It is independent of generated C and emitted runtime tables.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from collections import Counter
import hashlib
import json
import struct
from scripts.regional.program_model import AddressDomain, ProgramModel, Section, SectionKind, aligned, integer

@dataclass(frozen=True)
class ImageLayout:
    main_relocation_start: int
    overlay_reference_table_start: int
    overlay_table_start: int
    overlay_data_start: int
    main_text_size: int
    main_data_size: int

    @classmethod
    def from_document(cls, value: dict) -> ImageLayout:
        required=set(cls.__dataclass_fields__)
        if not isinstance(value,dict) or not required.issubset(value):
            raise ValueError("Missing original-image layout")
        result=cls(**{key:value[key] for key in required})
        for key in required: aligned(getattr(result,key),key)
        return result

    def validate(self, rom_size: int) -> None:
        for key in self.__dataclass_fields__: aligned(getattr(self,key),key)
        if not (64 <= self.main_relocation_start < self.overlay_reference_table_start < self.overlay_table_start < self.overlay_data_start <= rom_size):
            raise ValueError("Original-image tables are unordered or out of bounds")
        if (self.overlay_data_start-self.overlay_table_start)%32:
            raise ValueError("Partial overlay header")

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
    def populated(self) -> bool: return self.text_size+self.data_size != 0
    def rom_start(self, layout: ImageLayout) -> int: return layout.overlay_data_start+self.rom_offset

@dataclass(frozen=True)
class OriginalRelocation:
    ordinal: int
    table_rom: int
    module: int
    table_kind: str
    symbol: int
    patch_type: int
    source_type: int
    encoded_offset: int
    section: str
    section_offset: int
    site_rom: int
    original_word: int

    @property
    def site(self) -> tuple[str,int]: return self.section,self.section_offset

def word(rom: bytes, offset: int) -> int:
    aligned(offset,"ROM word")
    if offset+4>len(rom): raise ValueError("ROM word is out of bounds")
    return struct.unpack_from(">I",rom,offset)[0]

def source_offset(section: Section, layout: ImageLayout, source_type: int,
                  encoded_offset: int, patch_type: int) -> int:
    """DATA offsets start at data zero for both main and overlay modules."""
    aligned(encoded_offset,"relocation source")
    if source_type not in (0,1,2,3) or patch_type not in (2,4,5,6):
        raise ValueError("Unsupported original relocation encoding")
    if source_type==3:
        offset=section.checked_offset(AddressDomain.DATA,encoded_offset,4,patch=True)
    else:
        delta=section.text_size-layout.main_text_size if section.kind==SectionKind.MAIN else 0
        if delta<0: raise ValueError("Main text extent is inconsistent")
        offset=delta+encoded_offset
        if offset+4>section.initialized_size:
            raise ValueError("Relocation source leaves initialized memory")
    if patch_type!=2 and offset+4>section.text_size:
        raise ValueError("Instruction relocation does not patch text")
    return offset

@dataclass(frozen=True)
class OriginalInventory:
    revision_id: str
    rom_sha1: str
    model_sha256: str
    headers: tuple[OverlayHeader,...]
    references: tuple[int,...]
    records: tuple[OriginalRelocation,...]
    input_fingerprint: str

    def counts(self) -> dict:
        return {"overlay_slots":len(self.headers),"empty_slots":sum(not h.populated for h in self.headers),
                "relocations":len(self.records),"patch_types":dict(sorted(Counter(str(r.patch_type) for r in self.records).items())),
                "source_types":dict(sorted(Counter(("main" if r.module==0 else "overlay")+":"+str(r.source_type) for r in self.records).items()))}

    def canonical_bytes(self) -> bytes:
        return (json.dumps(asdict(self),sort_keys=True,separators=(",",":"))+"\n").encode()

    def fingerprint(self) -> str: return hashlib.sha256(self.canonical_bytes()).hexdigest()

def derive(rom: bytes, model: ProgramModel, layout: ImageLayout) -> OriginalInventory:
    model.validate();layout.validate(len(rom))
    if len(rom)!=model.rom_size or hashlib.sha1(rom).hexdigest()!=model.rom_sha1:
        raise ValueError("Original relocation inventory has a different ROM identity")
    modules={s.overlay_slot:s for s in model.sections if s.kind==SectionKind.OVERLAY}
    main=next(s for s in model.sections if s.kind==SectionKind.MAIN);modules[0]=main
    if main.data_size!=layout.main_data_size or main.text_size<layout.main_text_size:
        raise ValueError("Main model and original-image layout disagree")
    headers=[];ranges=[]
    for index,values in enumerate(struct.iter_unpack(">iiiiiHHii",rom[layout.overlay_table_start:layout.overlay_data_start]),1):
        h=OverlayHeader(index,*values);headers.append(h)
        for key in ('rom_offset','text_size','data_size','bss_size','primary_bytes','secondary_bytes'):
            aligned(getattr(h,key),key)
        if h.primary_bytes%8 or h.secondary_bytes%8: raise ValueError("Partial relocation record")
        if not h.populated:
            if index in modules: raise ValueError("Empty slot has an executable model")
            continue
        s=modules.get(index)
        if s is None or (s.rom_start,s.text_size,s.data_size,s.bss_size,s.retained_relocation_size)!=(h.rom_start(layout),h.text_size,h.data_size,h.bss_size,h.primary_bytes):
            raise ValueError("Overlay header and program model disagree")
        start=s.rom_start+s.initialized_size;end=start+h.primary_bytes+h.secondary_bytes
        if end>len(rom): raise ValueError("Overlay relocation table leaves ROM")
        ranges.append((s.rom_start,end))
    if set(modules)-{0}!={h.slot for h in headers if h.populated}: raise ValueError("Overlay inventory does not close")
    ranges.sort()
    if any(a[1]>b[0] for a,b in zip(ranges,ranges[1:])): raise ValueError("Overlay records overlap another image")
    n=word(rom,layout.main_relocation_start)
    start=layout.main_relocation_start+4;end=start+n*8
    if end>layout.overlay_reference_table_start: raise ValueError("Main relocation table crosses reference table")
    tables=[(0,'main',start,end)]
    for h in headers:
        if h.populated:
            start=h.rom_start(layout)+h.text_size+h.data_size
            tables.extend(((h.slot,'primary',start,start+h.primary_bytes),(h.slot,'secondary',start+h.primary_bytes,start+h.primary_bytes+h.secondary_bytes)))
    records=[];sites=set();input_hash=hashlib.sha256()
    for module,kind,start,end in tables:
        input_hash.update(struct.pack('>III',module,start,end));input_hash.update(rom[start:end])
        s=modules[module]
        for table_rom in range(start,end,8):
            symbol,info=struct.unpack_from('>II',rom,table_rom);patch=(info>>4)&15;source=info&15;encoded=info>>8
            offset=source_offset(s,layout,source,encoded,patch)
            site=(s.id,offset)
            if site in sites: raise ValueError("Duplicate original relocation patch site")
            sites.add(site);value=word(rom,s.rom_start+offset)
            if patch==4 and value>>26!=3: raise ValueError("Original R26 site is not JAL")
            if patch==5 and value>>26!=15: raise ValueError("Original HI16 site is not LUI")
            records.append(OriginalRelocation(len(records),table_rom,module,kind,symbol,patch,source,encoded,s.id,offset,s.rom_start+offset,value))
    for i,r in enumerate(records):
        if r.patch_type==5:
            if i+1>=len(records): raise ValueError("Unpaired original HI16")
            low=records[i+1]
            if (low.module,low.table_kind,low.symbol,low.source_type,low.patch_type)!=(r.module,r.table_kind,r.symbol,r.source_type,6):
                raise ValueError("Original HI16/LO16 identity mismatch")
            if low.table_rom!=r.table_rom+8: raise ValueError("Original HI16/LO16 crosses table")
    references=tuple(x[0] for x in struct.iter_unpack('>I',rom[layout.overlay_reference_table_start:layout.overlay_table_start]))
    for r in records:
        if r.source_type in (0,3) and r.symbol>=len(references): raise ValueError("Original reference index is out of bounds")
    input_hash.update(rom[layout.overlay_reference_table_start:layout.overlay_data_start])
    return OriginalInventory(model.revision_id,model.rom_sha1,model.fingerprint(),tuple(headers),references,tuple(records),input_hash.hexdigest())
