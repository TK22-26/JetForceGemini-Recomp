"""Locate exact shared RSP payloads within validated original resident images."""
from pathlib import Path
from dataclasses import dataclass,asdict
import hashlib
from scripts.rom_profiles import identify_rom
from scripts.regional.json_contract import loads
from scripts.regional.program_model import digest,SectionKind

ROOT=Path(__file__).resolve().parents[3]
RECIPES=ROOT/'config/roms/audio-payloads.json'
@dataclass(frozen=True)
class PayloadRef:
    revision_id:str
    model_sha256:str
    section:str
    offset:int
    size:int
    sha256:str

def locate_payload(rom,model,recipe):
    if set(recipe)!={'size','sha256','prefix_size','prefix_sha256','alignment'}:raise ValueError('Invalid RSP payload recipe')
    size,prefix,alignment=(recipe[k] for k in ('size','prefix_size','alignment'))
    if any(type(v) is not int or v<=0 for v in (size,prefix,alignment)) or size>256*1024 or prefix>size or alignment&(alignment-1) or alignment>4096:raise ValueError('Invalid RSP payload extent/alignment')
    digest(recipe['sha256'],64,'RSP payload hash');digest(recipe['prefix_sha256'],64,'RSP prefix hash');found=[]
    for section in model.sections:
        if section.kind==SectionKind.OVERLAY:continue
        start=section.rom_start;end=start+section.initialized_size
        for position in range((start+alignment-1)&-alignment,end-size+1,alignment):
            if (section.linked_vram+position-start)%alignment:continue
            if hashlib.sha256(rom[position:position+prefix]).hexdigest()!=recipe['prefix_sha256']:continue
            raw=rom[position:position+size]
            if hashlib.sha256(raw).hexdigest()==recipe['sha256']:found.append((PayloadRef(model.revision_id,model.fingerprint(),section.id,position-start,size,recipe['sha256']),raw))
    if len(found)!=1:raise ValueError('RSP payload is absent or ambiguous in the original resident image')
    return found[0]

def extract(rom,model,*,recipes_path=RECIPES):
    model.validate();profile,_,_=identify_rom(rom)
    if profile.revision_id!=model.revision_id or profile.sha1!=model.rom_sha1 or len(rom)!=model.rom_size:raise ValueError('RSP input/model mismatch')
    catalog=loads(Path(recipes_path).read_bytes())
    if set(catalog)!={'schema_version','kind','payloads'} or type(catalog['schema_version']) is not int or catalog['schema_version']!=1 or catalog['kind']!='jfg-shared-audio-payload-recipes' or set(catalog['payloads'])!={'program','data'}:raise ValueError('Invalid shared audio payload catalog')
    refs={};payloads={}
    for name,recipe in catalog['payloads'].items():
        ref,raw=locate_payload(rom,model,recipe);refs[name]=asdict(ref);payloads[name]=raw
    a,b=(refs[k] for k in ('program','data'))
    if a['section']==b['section'] and a['offset']<b['offset']+b['size'] and b['offset']<a['offset']+a['size']:raise ValueError('RSP program and companion data overlap')
    return payloads,{'schema_version':1,'revision_id':model.revision_id,'model_sha256':model.fingerprint(),'payloads':refs,'recipes_sha256':hashlib.sha256(Path(recipes_path).read_bytes()).hexdigest()}
