"""Translate checked original records without regional address defaults.

Every output record retains the original ordinal. Exception bindings are explicit
inputs bound to an exact model and exact exceptional source-record set.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass
from collections import Counter
import hashlib,json,struct
from scripts.regional.program_model import ProgramModel,CodeRef,SectionKind,digest,integer
from scripts.regional.relocation_inventory import OriginalInventory,OriginalRelocation,ImageLayout,derive

def canonical_digest(value) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def exceptional_records(inventory: OriginalInventory) -> tuple[OriginalRelocation,...]:
    return tuple(r for r in inventory.records if r.source_type in (0,3)
                 and inventory.references[r.symbol]>>20 not in ({0,0xffd,0xffe,0xfff}|{h.slot for h in inventory.headers if h.populated}))

@dataclass(frozen=True)
class ExceptionBindings:
    revision_id: str
    model_sha256: str
    records_sha256: str
    trap: CodeRef
    unresolved_section: str
    unresolved_offset: int
    evidence_sha256: str

    def validate(self, model: ProgramModel, inventory: OriginalInventory) -> None:
        if self.revision_id!=model.revision_id or self.model_sha256!=model.fingerprint():
            raise ValueError('Exception bindings identify a different program')
        digest(self.evidence_sha256,64,'exception evidence')
        if self.records_sha256!=canonical_digest([asdict(r) for r in exceptional_records(inventory)]):
            raise ValueError('Exceptional relocation inventory has changed')
        model.resolve(self.trap)
        s=next((s for s in model.sections if s.id==self.unresolved_section),None)
        integer(self.unresolved_offset,'unresolved data offset')
        if s is None or s.kind!=SectionKind.MAIN or not s.text_size<=self.unresolved_offset<=s.memory_size-4 or self.unresolved_offset%4:
            raise ValueError('Unresolved-data binding is not aligned static data/BSS')
        classes=Counter((r.patch_type,inventory.references[r.symbol]) for r in exceptional_records(inventory))
        if classes!={(4,0xd6600000):1,(5,0xffc00300):1,(6,0xffc00300):1}:
            raise ValueError('Unreviewed exceptional relocation encoding')

@dataclass(frozen=True)
class TranslatedRelocation:
    original_ordinal: int
    source_section: str
    source_offset: int
    patch_type: int
    target_section: str
    target_offset: int
    target_class: str
    disposition: str = 'resolved'

@dataclass(frozen=True)
class Translation:
    revision_id: str
    model_sha256: str
    original_inventory_sha256: str
    patched_rom: bytes
    relocations: tuple[TranslatedRelocation,...]

    def validate_correspondence(self, inventory: OriginalInventory) -> None:
        if self.revision_id!=inventory.revision_id or self.model_sha256!=inventory.model_sha256 or self.original_inventory_sha256!=inventory.fingerprint():
            raise ValueError('Translation and original inventory identities differ')
        expected={(r.ordinal,r.section,r.section_offset,r.patch_type) for r in inventory.records}
        actual={(r.original_ordinal,r.source_section,r.source_offset,r.patch_type) for r in self.relocations}
        if expected!=actual or len(self.relocations)!=len(expected):
            raise ValueError('Translation did not account for every original record exactly once')

def sign16(value: int) -> int: return value-0x10000 if value&0x8000 else value

def normalize_addend(value: int, unresolved: int|None=None) -> int:
    value &= 0xffffffff
    if unresolved is not None and value==unresolved:return 0
    return value-0x80000000 if value&0x80000000 else value

def translate(rom: bytes,model: ProgramModel,layout: ImageLayout,
              inventory: OriginalInventory,bindings: ExceptionBindings) -> Translation:
    # Re-read exact original inputs; a caller-authored inventory is not authority.
    if derive(rom,model,layout)!=inventory: raise ValueError('Original relocation inventory does not reproduce')
    bindings.validate(model,inventory)
    sections={s.id:s for s in model.sections};modules={s.overlay_slot:s for s in model.sections if s.kind==SectionKind.OVERLAY}
    main=next(s for s in model.sections if s.kind==SectionKind.MAIN);modules[0]=main
    main_delta=main.text_size-layout.main_text_size
    unresolved=sections[bindings.unresolved_section].linked_vram+bindings.unresolved_offset
    patched=bytearray(rom);translated=[]
    def target(r):
        if r.source_type==1:return r.section,r.symbol,'local-offset'
        if r.source_type==2:return r.section,(r.original_word&0x3ffffff)<<2,'local-jump'
        encoded=inventory.references[r.symbol];module=encoded>>20;offset=encoded&0xfffff
        if module==0:return main.id,main_delta+offset,'main'
        if module in modules:return modules[module].id,offset,'overlay'
        if module in (0xffd,0xffe):return main.id,main.text_size+offset,'main-data'
        if module==0xfff:return main.id,main.initialized_size+offset,'main-bss'
        if module==0xffc and r.patch_type in (5,6):return bindings.unresolved_section,bindings.unresolved_offset,'reserved-atomic-hi-lo'
        if encoded==0xd6600000 and r.patch_type==4:return bindings.trap.section,bindings.trap.offset,'fail-closed-trap'
        raise ValueError('Original relocation target is unsupported')
    def checked(section,offset,alignment=1):
        s=sections[section]
        if type(offset) is not int or not 0<=offset<s.memory_size+s.retained_relocation_size or offset%alignment:
            raise ValueError('Relocation target leaves its explicit section extent')
        return s.linked_vram+offset
    def emit(r,section,offset,kind):
        translated.append(TranslatedRelocation(r.ordinal,r.section,r.section_offset,r.patch_type,section,offset,kind,
                          'reserved-atomic-pair' if kind=='reserved-atomic-hi-lo' else 'fail-closed-trap' if kind=='fail-closed-trap' else 'resolved'))
    i=0
    while i<len(inventory.records):
        record=inventory.records[i];section,offset,kind=target(record);value=record.original_word
        if record.patch_type==2:
            if record.source_type==1:offset+=normalize_addend(value)
            checked(section,offset);emit(record,section,offset,kind);i+=1;continue
        if record.patch_type==5:
            low=inventory.records[i+1]
            if kind!='reserved-atomic-hi-lo':offset+=normalize_addend(((value&0xffff)<<16)+sign16(low.original_word&0xffff),unresolved)
            address=checked(section,offset)
            struct.pack_into('>I',patched,record.site_rom,(value&0xffff0000)|(((address+0x8000)>>16)&0xffff))
            struct.pack_into('>I',patched,low.site_rom,(low.original_word&0xffff0000)|(address&0xffff))
            emit(record,section,offset,kind);emit(low,section,offset,kind);i+=2;continue
        if record.patch_type==6:
            offset+=value&0xffff;address=checked(section,offset)
            struct.pack_into('>I',patched,record.site_rom,(value&0xffff0000)|(address&0xffff))
        elif record.patch_type==4:
            address=checked(section,offset,4)
            # Linked overlay coordinates are compiler surrogates, not loaded
            # CPU addresses. The emitted R26 record carries the exact target
            # section/offset; its upper bits must not be inferred from the
            # source PC's architectural jump region during offline rewriting.
            struct.pack_into('>I',patched,record.site_rom,(value&0xfc000000)|((address>>2)&0x3ffffff))
        else:raise ValueError('Unsupported instruction relocation')
        emit(record,section,offset,kind);i+=1
    result=Translation(model.revision_id,model.fingerprint(),inventory.fingerprint(),bytes(patched),tuple(translated))
    result.validate_correspondence(inventory)
    return result
