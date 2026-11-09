"""Prepare compiler inputs from the same validated model for every revision."""
from __future__ import annotations
from collections import defaultdict,Counter
from dataclasses import asdict,replace
from pathlib import Path
import hashlib,json
from scripts.regional.program_model import ProgramModel,SectionKind
from scripts.regional.relocation_inventory import ImageLayout,derive
from scripts.regional.relocation_translation import ExceptionBindings,translate,canonical_digest
from scripts.regional.symbol_inventory import reconcile
from scripts.regional.code_inventory import (function_intervals,find_cross_body_branch_entries,
    find_indirect_transfer_sites,find_direct_call_candidates,read_word,sign_extend_16,
    split_functions,write_symbol_file,write_config,find_direct_interior_entries,find_constant_indirect_entries,close_alternate_branch_entries)

def prepare(rom:bytes,model:ProgramModel,layout:ImageLayout,bindings:ExceptionBindings,
            elf_sections,elf_symbols,output:Path) -> dict:
    model.validate()
    qualified,symbol_counts=reconcile(replace(model,aliases=()),elf_sections,elf_symbols)
    if qualified.fingerprint()!=model.fingerprint(): raise ValueError('ELF and program model no longer reconcile')
    ordered=sorted(model.sections,key=lambda s:s.source_index)
    if [s.source_index for s in ordered]!=list(range(len(ordered))):raise ValueError('Compiler section indices are not dense')
    by_id={s.id:s for s in ordered};sections=[]
    for section in ordered:
        bodies=[b for b in model.bodies if b.section==section.id]
        sections.append({'rom':section.rom_start,'vram':section.linked_vram,
                         'size':section.initialized_size,'relocation_size':section.memory_size+section.retained_relocation_size,
                         'functions':[{'vram':section.linked_vram+b.offset,'size':b.size,'name':b.names[0]} for b in bodies]})
    original=derive(rom,model,layout);translation=translate(rom,model,layout,original,bindings)
    intervals=function_intervals(sections);split_offsets=defaultdict(set);relocs=defaultdict(list)
    r26={};anomalous=set();split_reasons=defaultdict(set)
    for row in translation.relocations:
        source=by_id[row.source_section];target=by_id[row.target_section]
        if row.patch_type==2:continue
        relocs[source.source_index].append({'type':{4:'R_MIPS_26',5:'R_MIPS_HI16',6:'R_MIPS_LO16'}[row.patch_type],
              'vram':source.linked_vram+row.source_offset,'target_section':target.source_index,'target_section_offset':row.target_offset})
        if row.patch_type==4:
            r26[(source.source_index,row.source_offset)]=(target.source_index,row.target_offset)
            if row.disposition=='fail-closed-trap':anomalous.add((source.source_index,row.source_offset))
            starts={start for start,_ in intervals[target.source_index]}
            if row.target_offset not in starts:
                if not any(start<row.target_offset<end for start,end in intervals[target.source_index]):
                    raise ValueError('Original R26 target has no authoritative body owner: '+row.target_section+':'+hex(row.target_offset))
                split_offsets[target.source_index].add(row.target_offset);split_reasons[(target.source_index,row.target_offset)].add('relocated-call')
    for index,offsets in find_direct_interior_entries(translation.patched_rom,sections,r26).items():
        for offset in offsets:split_offsets[index].add(offset);split_reasons[(index,offset)].add('direct-call')
    for index,offsets in find_constant_indirect_entries(translation.patched_rom,sections).items():
        for offset in offsets:split_offsets[index].add(offset);split_reasons[(index,offset)].add('constant-register-transfer')
    for index,offsets in find_cross_body_branch_entries(translation.patched_rom,sections).items():
        for offset in offsets:split_offsets[index].add(offset);split_reasons[(index,offset)].add('cross-body-branch')
    for section in ordered:
        for body in (b for b in model.bodies if b.section==section.id):
            for offset in range(body.offset,body.offset+body.size,4):
                word=read_word(translation.patched_rom,section.rom_start+offset)
                if word>>26==1 and (word>>16)&31==17:
                    target=offset+4+(sign_extend_16(word&65535)<<2)
                    if body.offset<target<body.offset+body.size:
                        split_offsets[section.source_index].add(target);split_reasons[(section.source_index,target)].add('same-body-link')
    for alias in model.aliases:
        if alias.offset!=alias.body_offset:
            index=by_id[alias.section].source_index;split_offsets[index].add(alias.offset);split_reasons[(index,alias.offset)].add('covered-alias')
    for index,offsets in close_alternate_branch_entries(translation.patched_rom,sections,split_offsets).items():
        for offset in offsets:split_offsets[index].add(offset);split_reasons[(index,offset)].add('alternate-entry-branch')
    rewritten,support_count,uncovered=split_functions(sections,split_offsets)
    if uncovered or support_count!=sum(len(s) for s in split_offsets.values()):raise ValueError('Alternate entry inventory does not close')
    direct=find_direct_call_candidates(translation.patched_rom,sections,rewritten,anomalous,r26)
    indirect=find_indirect_transfer_sites(translation.patched_rom,sections)
    # Every instruction relocation must be inside a real body. Alternate-entry
    # emission never permits writing through holes in the original code model.
    for row in translation.relocations:
        if row.patch_type!=2 and not any(b.section==row.source_section and b.offset<=row.source_offset<b.offset+b.size for b in model.bodies):
            raise ValueError('Original instruction relocation has no body owner')
    if output.exists():raise ValueError('Compiler input output already exists')
    output.mkdir(parents=True)
    (output/'original-private.z64').write_bytes(rom)
    (output/'patched-private.z64').write_bytes(translation.patched_rom)
    write_symbol_file(output/'symbols-private.toml',sections,rewritten,relocs)
    write_config(output/'recompile-private.toml')
    from scripts.regional.execution import configure as configure_execution
    alternate_entries=[{'section':index,'offset':offset,'reasons':sorted(reasons)} for (index,offset),reasons in sorted(split_reasons.items())]
    execution=configure_execution(output,rom,model,alternate_entries)
    counts={**symbol_counts,'sections':len(ordered),'support_entries':support_count,
            **original.counts(),'direct_sites':len(direct),'direct_classes':dict(sorted(Counter(v['instruction_class'] for v in direct).items())),
            'direct_roles':dict(sorted(Counter(v['transfer_role'] for v in direct).items())),
            'direct_target_classes':dict(sorted(Counter(v['target_class'] for v in direct).items())),
            'indirect_sites':len(indirect),'native_return_candidates':sum(v['source_register']==31 for v in indirect)}
    counts['indirect_decision_candidates']=counts['indirect_sites']-counts['native_return_candidates']
    receipts={'execution-contract.json':execution,'image-layout.json':asdict(layout),'program-model.json':json.loads(model.canonical_bytes()),'original-relocations.json':json.loads(original.canonical_bytes()),
              'translated-relocations.json':[asdict(v) for v in translation.relocations],
              'direct-sites.json':direct,'indirect-sites.json':indirect,
              'alternate-entries.json':alternate_entries,
              'exception-bindings.json':asdict(bindings)}
    for name,value in receipts.items():(output/name).write_text(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    manifest={'schema_version':3,'kind':'jfg-regional-generation-input','revision_id':model.revision_id,
              'rom_sha1':model.rom_sha1,'model_sha256':model.fingerprint(),'original_inventory_sha256':original.fingerprint(),
              'elf_sha256':model.elf_sha256,'counts':counts,
              'files':{name:hashlib.sha256((output/name).read_bytes()).hexdigest() for name in (*receipts,'original-private.z64','patched-private.z64','symbols-private.toml','recompile-private.toml')}}
    (output/'input-manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return manifest
