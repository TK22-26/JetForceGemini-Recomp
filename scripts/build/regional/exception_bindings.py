"""Derive reviewed exceptional relocation targets from original instructions."""
from pathlib import Path
from dataclasses import asdict
from scripts.rom_profiles import PROFILES_BY_ID,identify_rom
from scripts.regional.json_contract import loads
from scripts.regional.program_model import CodeRef,SectionKind
from scripts.regional.bindings import address_operand
from scripts.regional.execution import locate
from scripts.regional.relocation_translation import ExceptionBindings,exceptional_records,canonical_digest

ROOT=Path(__file__).resolve().parents[3]
RECIPES=ROOT/'config/roms/relocation-exceptions.json'
def qualify(rom,model,inventory,*,recipes_path=RECIPES):
    profile,_,_=identify_rom(rom)
    if profile.revision_id!=model.revision_id:raise ValueError('Exception ROM/model mismatch')
    catalog=loads(Path(recipes_path).read_bytes())
    if set(catalog)!={'schema_version','kind','revisions'} or type(catalog['schema_version']) is not int or catalog['schema_version']!=1 or catalog['kind']!='jfg-original-relocation-exception-recipes' or set(catalog['revisions'])!=set(PROFILES_BY_ID):raise ValueError('Invalid relocation exception catalog')
    recipe=catalog['revisions'][model.revision_id]
    if set(recipe)!={'trap','unresolved_witnesses','records_sha256'}:raise ValueError('Invalid exception binding recipe')
    records=canonical_digest([asdict(v) for v in exceptional_records(inventory)])
    if records!=recipe['records_sha256']:raise ValueError('Original exceptional record set changed')
    row=recipe['trap']
    if set(row)!={'section_kind','body_size','body_sha256','entry_offset'} or row['section_kind']!='main':raise ValueError('Invalid original trap recipe')
    section,body=locate(rom,model,row);inner=row['entry_offset']
    if type(inner) is not int or inner<0 or inner%4 or inner>=body.size:raise ValueError('Invalid trap entry')
    trap=CodeRef(model.revision_id,section.id,body.offset+inner);model.resolve(trap)
    witnesses=recipe['unresolved_witnesses'];values=[];seen=set();evidence=[]
    if not isinstance(witnesses,list) or len(witnesses)<2:raise ValueError('Unresolved pointer requires independent original body witnesses')
    for row in witnesses:
        if set(row)!={'section_kind','body_size','body_sha256','pairs'} or row['section_kind']!='main' or not isinstance(row['pairs'],list) or not row['pairs']:raise ValueError('Invalid unresolved data witness')
        section,body=locate(rom,model,row)
        if body.identity in seen:raise ValueError('Repeated witness is not independent')
        seen.add(body.identity);start=section.rom_start+body.offset;raw=rom[start:start+body.size]
        for pair in row['pairs']:
            if not isinstance(pair,list) or len(pair)!=2:raise ValueError('Invalid witness operand pair')
            values.append(address_operand(raw,*pair))
        evidence.append({'section':section.id,'offset':body.offset,'body_sha256':row['body_sha256'],'pairs':row['pairs']})
    if len(set(values))!=1:raise ValueError('Original unresolved-pointer witnesses disagree')
    address=values[0];owners=[s for s in model.sections if s.kind==SectionKind.MAIN and s.linked_vram+s.text_size<=address and address+4<=s.linked_vram+s.memory_size]
    if len(owners)!=1 or address%4:raise ValueError('Unresolved pointer lacks aligned resident DATA/BSS ownership')
    section=owners[0]
    result=ExceptionBindings(model.revision_id,model.fingerprint(),records,trap,section.id,address-section.linked_vram,canonical_digest({'recipe':recipe,'witnesses':evidence,'model_sha256':model.fingerprint()}))
    result.validate(model,inventory)
    return result
