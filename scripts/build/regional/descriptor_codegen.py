"""Create a linked descriptor from a validated private generated corpus."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
if __package__ in (None, ""):
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from scripts.regional.program_model import from_document,SectionKind
from scripts.regional.generation_contract import GenerationContract
from scripts.regional.json_contract import loads
from scripts.rom_profiles import PROFILES_BY_ID

def document(input_root: Path):
    contract=GenerationContract.read(input_root/'input-manifest.json')
    model=from_document(loads((input_root/'program-model.json').read_bytes()))
    rom=(input_root/'original-private.z64').read_bytes()
    entrypoint=int.from_bytes(rom[8:12],'big')
    sections={s.id:s for s in model.sections}
    entries=[s for s in model.sections if s.kind!=SectionKind.OVERLAY and s.linked_vram<=entrypoint<s.linked_vram+s.text_size]
    if len(entries)!=1 or entrypoint%4:raise ValueError('ROM entry point has no unique resident text owner')
    entry=entries[0]
    return {'schema_version':1,'kind':'jfg-linked-game-descriptor','revision_id':contract.revision_id,
            'model_sha256':contract.model_sha256,'input_sha256':contract.input_manifest_sha256,
            'model':loads(model.canonical_bytes()),'entry':{'section':entry.id,'offset':entrypoint-entry.linked_vram},
            'alternate_entries':loads((input_root/'alternate-entries.json').read_bytes())}

def emit(doc):
    if not isinstance(doc,dict) or set(doc)!={'schema_version','kind','revision_id','model_sha256','input_sha256','model','entry','alternate_entries'} or type(doc['schema_version']) is not int or doc['schema_version']!=1 or doc['kind']!='jfg-linked-game-descriptor':
        raise ValueError('Invalid linked descriptor schema')
    model=from_document(doc['model']);profile=PROFILES_BY_ID.get(doc['revision_id'])
    if profile is None or (model.revision_id,model.rom_sha1,model.rom_size,model.fingerprint())!=(profile.revision_id,profile.sha1,profile.size,doc['model_sha256']):
        raise ValueError('Linked descriptor model identity differs from catalog')
    from scripts.regional.program_model import digest
    digest(doc['input_sha256'],64,'generation input digest')
    ordered=sorted(model.sections,key=lambda s:s.source_index)
    if [s.source_index for s in ordered]!=list(range(len(ordered))):raise ValueError('Descriptor sections are not dense')
    by_id={s.id:s for s in ordered};revision=json.dumps(model.revision_id)
    entry=doc['entry']
    if not isinstance(entry,dict) or set(entry)!={'section','offset'} or entry['section'] not in by_id:raise ValueError('Invalid descriptor entry')
    section=by_id[entry['section']]
    if section.kind==SectionKind.OVERLAY or type(entry['offset']) is not int or entry['offset']%4 or not 0<=entry['offset']<=section.text_size-4:raise ValueError('Descriptor entry must be resident text')
    alternates=doc['alternate_entries'];seen=set()
    if not isinstance(alternates,list):raise ValueError('Invalid descriptor alternate entries')
    for a in alternates:
        if not isinstance(a,dict) or set(a)!={'section','offset','reasons'} or type(a['section']) is not int or not 0<=a['section']<len(ordered) or type(a['offset']) is not int or a['offset']%4:
            raise ValueError('Invalid alternate entry coordinate')
        pair=(a['section'],a['offset'])
        if pair in seen or not any(b.section==ordered[a['section']].id and b.offset<a['offset']<b.offset+b.size for b in model.bodies):raise ValueError('Alternate entry has no unique interior body ownership')
        seen.add(pair)
    out=['// Private generated descriptor. Do not track.','#pragma once','#include "jfg/game/descriptor.hpp"','#include <array>','namespace jfg::game::linked {']
    out.append(f'inline constexpr std::array<Section,{len(ordered)}> sections = {{{{')
    for s in ordered:out.append(f'  {{SectionKind::{s.kind.value}, {s.rom_start}U, {s.linked_vram}U, {s.text_size}U, {s.data_size}U, {s.bss_size}U, {s.retained_relocation_size}U, {s.overlay_slot or 0}U}},')
    out+=['}};',f'inline constexpr std::array<FunctionBody,{len(model.bodies)}> bodies = {{{{']
    for b in model.bodies:out.append(f'  {{{by_id[b.section].source_index}U, {b.offset}U, {b.size}U}},')
    out+=['}};',f'inline constexpr std::array<CodeRef,{len(alternates)}> alternate_entries = {{{{']
    for a in alternates:out.append(f'  {{{revision}, {a["section"]}U, {a["offset"]}U}},')
    out+=['}};', 'inline constexpr Descriptor descriptor = {',
          f'  kDescriptorAbi, {revision}, "{model.rom_sha1}", "{doc["model_sha256"]}", "{doc["input_sha256"]}",',
          f'  sections, bodies, alternate_entries, {{{revision}, {section.source_index}U, {entry["offset"]}U}}, TvMode::{"pal" if profile.country==ord("P") else "ntsc"}',
          '};','} // namespace jfg::game::linked','']
    return '\n'.join(out)

def main():
    p=argparse.ArgumentParser();p.add_argument('--generated-root',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    from scripts.prepare_generated_sources import _load_manifest,_resolve_contained,_validate_normalizer_revision
    manifest=_load_manifest(a.generated_root/'sources.json')
    if manifest['version']!=7:raise ValueError('A regional descriptor requires a regional generated corpus')
    _validate_normalizer_revision(manifest)
    raw=_resolve_contained(a.generated_root.resolve(),manifest['game_descriptor'],'game-descriptor').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest['game_descriptor_sha256']:raise ValueError('Linked descriptor digest mismatch')
    doc=loads(raw)
    if (doc['revision_id'],doc['model_sha256'],doc['input_sha256'])!=(manifest['revision_id'],manifest['program_model_sha256'],manifest['generation_input_sha256']):raise ValueError('Linked descriptor belongs to a different corpus')
    output=emit(doc)
    from scripts.regional.bindings import emit_cpp as emit_bindings
    binding_raw=_resolve_contained(a.generated_root.resolve(),manifest['game_bindings'],'game-bindings').read_bytes()
    if hashlib.sha256(binding_raw).hexdigest()!=manifest['game_bindings_sha256']:raise ValueError('Game binding digest mismatch')
    binding_output=emit_bindings(loads(binding_raw),doc)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(output,encoding='utf-8',newline='\n')
    (a.output.parent/'linked-bindings.hpp').write_text(binding_output,encoding='utf-8',newline='\n')
    return 0

if __name__=='__main__':raise SystemExit(main())
