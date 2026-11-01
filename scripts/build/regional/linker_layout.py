"""Read game relocation domains from exact original linker instructions.

ELF extraction categories are not the original game's relocation domains. In
particular an RSP blob may be labelled ELF data although the guest linker counts
it in main text. No regional offset delta or ELF TEXT_END fallback is permitted.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib,struct
from scripts.regional.json_contract import loads
from scripts.regional.relocation_inventory import ImageLayout
from scripts.rom_profiles import identify_rom

ROOT=Path(__file__).resolve().parents[3]
RECIPE=ROOT/'config/roms/relocation-domains.json'

@dataclass(frozen=True)
class MainDomains:
    code: int
    data: int
    bss: int
    resolver_rom: int
    resolver_body_sha256: str

def immediate_pair(body: bytes, hi_offset: int, lo_offset: int) -> int:
    if any(type(v) is not int or v<0 or v%4 or v+4>len(body) for v in (hi_offset,lo_offset)) or hi_offset>=lo_offset:
        raise ValueError('Invalid linker boundary instruction offsets')
    hi=struct.unpack_from('>I',body,hi_offset)[0];lo=struct.unpack_from('>I',body,lo_offset)[0]
    register=(hi>>16)&31
    if hi>>26!=15 or (hi>>21)&31 or not register or lo>>26!=9 or (lo>>21)&31!=register or (lo>>16)&31!=register:
        raise ValueError('Linker boundary is not the pinned LUI/ADDIU register pair')
    signed=(lo&65535)-(65536 if lo&32768 else 0)
    return (((hi&65535)<<16)+signed)&0xffffffff

def decode_domains(body: bytes, recipe: dict):
    fields={'resolver_body_sha256','resolver_body_size','code_pairs','data_pairs','bss_pairs'}
    if not isinstance(recipe,dict) or set(recipe)!=fields or type(recipe['resolver_body_size']) is not int or len(body)!=recipe['resolver_body_size'] or hashlib.sha256(body).hexdigest()!=recipe['resolver_body_sha256']:
        raise ValueError('Original relocation resolver differs from pinned evidence')
    values=[]
    for field in ('code_pairs','data_pairs','bss_pairs'):
        pairs=recipe[field]
        if not isinstance(pairs,list) or not pairs or any(not isinstance(p,list) or len(p)!=2 for p in pairs):raise ValueError('Invalid boundary recipe operands')
        decoded={immediate_pair(body,*p) for p in pairs}
        if len(decoded)!=1:raise ValueError('Independent original linker boundary operands disagree')
        values.append(decoded.pop())
    if not values[0]<values[1]<values[2] or any(v%4 for v in values):raise ValueError('Original main relocation domains are unordered')
    return tuple(values)

def original_main_domains(rom: bytes, main: dict) -> MainDomains:
    profile,_,_=identify_rom(rom)
    recipes=loads(RECIPE.read_bytes())
    if set(recipes)!={'schema_version','source','revisions'} or type(recipes['schema_version']) is not int or recipes['schema_version']!=1:raise ValueError('Invalid relocation-domain recipes')
    recipe=recipes['revisions'].get(profile.revision_id)
    if recipe is None:raise ValueError('Missing exact-revision relocation-domain recipe')
    matches=[]
    for function in main['functions']:
        if function['size']!=recipe['resolver_body_size']:continue
        start=main['rom']+function['vram']-main['vram'];body=rom[start:start+function['size']]
        if hashlib.sha256(body).hexdigest()==recipe['resolver_body_sha256']:matches.append((start,body))
    if len(matches)!=1:raise ValueError('Pinned original relocation resolver has no unique context owner')
    start,body=matches[0];code,data,bss=decode_domains(body,recipe)
    if not main['vram']<=code<data<bss or bss!=main['vram']+main['size']:
        raise ValueError('Original relocation domains do not fit the matching static image')
    return MainDomains(code,data,bss,start,recipe['resolver_body_sha256'])

def derive_layout(rom: bytes, map_text: str, context: dict) -> ImageLayout:
    from scripts.regional.context_model import linker_symbol
    rows=[s for s in context.get('section',[]) if s['name']=='.main']
    if len(rows)!=1:raise ValueError('Missing or ambiguous main executable context')
    domains=original_main_domains(rom,rows[0])
    layout=ImageLayout(*(linker_symbol(map_text,name+'_ROM_START') for name in ('mainRelocTable','overlayRomTable','overlayTable','overlay_1')),domains.data-domains.code,domains.bss-domains.data)
    layout.validate(len(rom))
    return layout
