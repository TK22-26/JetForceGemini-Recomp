"""Emit revision-bound runtime metadata from retained original inventories."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import hashlib,json,tomllib
from scripts.regional.program_model import from_document,SectionKind
from scripts.regional.generation_contract import GenerationContract
from scripts.transform_private_n64recomp_inputs import opaque_ledger_id,canonical_digest,approval_digest

def emit(root:Path,elf_sections,elf_symbols) -> dict:
    contract=GenerationContract.read(root/'input-manifest.json')
    read=lambda name:json.loads((root/name).read_text())
    model=from_document(read('program-model.json'));original=read('original-relocations.json');translated=read('translated-relocations.json')
    model_sections={s.id:s for s in model.sections};elf_by_index={str(s.index):s for s in elf_sections}
    named={('.overlay_'+str(s.overlay_slot) if s.kind==SectionKind.OVERLAY else '.'+s.id):s for s in model.sections}
    functions=tomllib.loads((root/'symbols-private.toml').read_text())['section']
    generated={(i,f['vram']-s['vram']):f['name'] for i,s in enumerate(functions) for f in s['functions']}
    executable=[v for v in elf_symbols if v.symbol_type=='FUNC' and v.defined and v.section in elf_by_index and 'X' in elf_by_index[v.section].flags]
    aliases=[];manual=[]
    for symbol in executable:
        if symbol.size:continue
        section=named[elf_by_index[symbol.section].name];offset=symbol.value-section.linked_vram
        owners=[v for v in executable if v.size>0 and v.section==symbol.section and v.value<=symbol.value<v.value+v.size]
        if len(owners)>1:raise ValueError('Ambiguous alias ownership')
        if owners:
            owner=owners[0];source={'private_name':symbol.name,'private_owner_name':owner.name,'section':section.source_index,'offset':offset,'owner_offset':owner.value-section.linked_vram,'owner_size':owner.size}
            name=generated[(section.source_index,offset)];role='authoritative-body' if source['offset']==source['owner_offset'] else 'alternate-entry-thunk';disposition='deterministic-body-alias' if role=='authoritative-body' else 'deterministic-thunk-alias'
            oid=opaque_ledger_id('alias',{'private_name':source['private_name'],'section':source['section'],'offset':source['offset'],'generated_function':name})
            aliases.append({'opaque_id':oid,'mapping_role':role,'evidence_class':'zero-size-covered-function','reason':'covered-address-in-authoritative-body','disposition':disposition,'approval_sha256':approval_digest('phase4-covered-alias-policy-v1',oid,'zero-size-covered-alias',disposition),'generated_function':name,'private_source':source})
        else:
            body=next(b for b in model.bodies if b.section==section.id and b.offset==offset)
            source={'private_name':symbol.name,'generated_function':body.names[0],'section':section.source_index,'offset':offset,'recovered_size':body.size};oid=opaque_ledger_id('manual-size',source)
            manual.append({'opaque_id':oid,'mapping_role':'authoritative-body','evidence_class':'uncovered-zero-size-function','reason':'next-executable-symbol-boundary','disposition':'recovered-authoritative-body','approval_sha256':approval_digest('phase4-manual-size-recovery-policy-v1',oid,'uncovered-zero-size-function','recovered-authoritative-body'),'generated_function':source['generated_function'],'private_source':source})
    aliases.sort(key=lambda r:(r['private_source']['section'],r['private_source']['offset'],r['private_source']['private_name']))
    manual.sort(key=lambda r:(r['private_source']['section'],r['private_source']['offset'],r['private_source']['private_name']))
    def private_record(record):return {'source_module':record['module'],'table_kind':record['table_kind'],'symbol':record['symbol'],'site_offset':record['encoded_offset'],'patch_type':record['patch_type'],'source_type':record['source_type']}
    exceptions=[];reserved=set();anomalous=set()
    for row in translated:
        if row['disposition']=='resolved':continue
        record=original['records'][row['original_ordinal']];private=private_record(record);oid=opaque_ledger_id('exception',private)
        direct=row['disposition']=='fail-closed-trap';category='anomalous-r-mips-26' if direct else 'reserved-atomic-hi-lo';disposition='fail-closed-trap' if direct else 'unresolved-data-atomic-pair'
        (anomalous if direct else reserved).add(record['ordinal'])
        exceptions.append({'opaque_id':oid,'category':category,'evidence_class':'direct-call' if direct else 'instruction-relocation','owner_role':'transformer','reason':'out-of-domain-overlay-reference' if direct else 'reserved-reference-class','disposition':disposition,'approval_sha256':approval_digest('phase4-transform-exception-policy-v1',oid,category,disposition),'private_record':private})
    direct=[{'opaque_id':opaque_ledger_id('direct-call',row),**row} for row in read('direct-sites.json')]
    indirect=[{'opaque_id':opaque_ledger_id('indirect',row),'transfer_kind':row['transfer_kind'],'source_register':row['source_register'],'discovery_class':'native-return-candidate' if row['source_register']==31 else 'indirect-decision-candidate','disposition':'requires-n64recomp-observation','private_site':{'section':row['section'],'offset':row['offset']}} for row in read('indirect-sites.json')]
    if len(aliases)!=contract.covered_alias_count or len(manual)!=contract.manual_size_recovery_count:raise ValueError('ELF alias inventory changed')
    instruction=[r for r in original['records'] if r['patch_type']!=2];r32=[r for r in original['records'] if r['patch_type']==2]
    audit={
      'overlay_slot_count':contract.overlay_slot_count,'empty_overlay_slot_count':contract.empty_overlay_slot_count,
      'exception_ledger_sha256':canonical_digest(exceptions),'exception_approval_set_sha256':canonical_digest(sorted(r['approval_sha256'] for r in exceptions)),
      'exception_category_counts':dict(Counter(r['category'] for r in exceptions)),
      'covered_alias_count':contract.covered_alias_count,'covered_alias_body_start_count':contract.covered_alias_body_start_count,'covered_alias_interior_count':contract.covered_alias_interior_count,
      'covered_alias_ledger_sha256':canonical_digest(aliases),'covered_alias_approval_set_sha256':canonical_digest(sorted(r['approval_sha256'] for r in aliases)),
      'manual_size_recovery_count':contract.manual_size_recovery_count,'manual_size_recovery_ledger_sha256':canonical_digest(manual),'manual_size_recovery_approval_set_sha256':canonical_digest(sorted(r['approval_sha256'] for r in manual)),
      'direct_call_candidate_count':len(direct),'direct_linked_call_candidate_count':contract.direct_linked_call_candidate_count,'direct_tail_candidate_count':contract.direct_tail_candidate_count,
      'direct_instruction_class_counts':dict(contract.direct_instruction_class_counts),'direct_generated_target_candidate_count':contract.direct_generated_target_candidate_count,'direct_unresolved_target_candidate_count':contract.direct_unresolved_target_candidate_count,
      'direct_pending_n64recomp_observation_count':len(direct),'direct_call_candidate_ledger_sha256':canonical_digest(direct),'direct_call_approval_set_sha256':canonical_digest(sorted(r['approval_sha256'] for r in exceptions if r['evidence_class']=='direct-call')),
      'r26_relocation_count':contract.r26_relocation_count,'r26_relocation_resolved_count':contract.r26_relocation_count-len(anomalous),'r26_relocation_exception_count':len(anomalous),
      'instruction_relocation_count':len(instruction),'instruction_resolved_count':len(instruction)-len(reserved),'instruction_fail_closed_count':len(reserved),
      'instruction_relocation_ledger_sha256':canonical_digest([{'opaque_id':opaque_ledger_id('instruction',private_record(v)),'disposition':'approved-fail-closed-atomic-pair' if v['ordinal'] in reserved else 'resolved'} for v in instruction]),
      'instruction_relocation_approval_set_sha256':canonical_digest(sorted(r['approval_sha256'] for r in exceptions if r['evidence_class']=='instruction-relocation')),
      'hi_lo_pair_count':contract.hi_lo_pair_count,'r32_count':len(r32),'r32_ledger_sha256':canonical_digest([opaque_ledger_id('r32',private_record(v)) for v in r32]),'r32_approval_set_sha256':canonical_digest([]),
      'indirect_transfer_ledger_sha256':canonical_digest(indirect),'indirect_transfer_count':len(indirect),'indirect_native_return_candidate_count':contract.native_return_site_count,'indirect_decision_candidate_count':contract.indirect_decision_site_count,'indirect_pending_n64recomp_observation_count':len(indirect),'stub_ledger_sha256':canonical_digest([])}
    main_offsets={v['section_offset']-v['encoded_offset'] for v in original['records'] if v['module']==0 and v['source_type']!=3}
    if len(main_offsets)!=1:raise ValueError('Main relocation origin is ambiguous')
    main_offset=next(iter(main_offsets))
    sections=[{'module':s.overlay_slot or 0,'section':s.source_index,'kind':s.kind.value,'rom':s.rom_start,'linked_vram':s.linked_vram,'text_offset':main_offset if s.kind==SectionKind.MAIN else 0,'text_size':s.text_size-(main_offset if s.kind==SectionKind.MAIN else 0),'data_size':s.data_size,'bss_size':s.bss_size} for s in sorted(model.sections,key=lambda s:s.source_index)]
    slots=[];by_slot={s.overlay_slot:s for s in model.sections if s.kind==SectionKind.OVERLAY}
    for header in original['headers']:
        s=by_slot.get(header['slot']);slots.append({'slot':header['slot'],'section':s.source_index if s else None,'disposition':'populated' if s else 'empty-fail-closed','source_binding':canonical_digest(header)})
    runtime=[{'source_section':model_sections[v['source_section']].source_index,'site_offset':v['source_offset'],'target_section':model_sections[v['target_section']].source_index,'target_section_offset':v['target_offset'],'source_type':original['records'][v['original_ordinal']]['source_type'],'target_class':v['target_class']} for v in translated if v['patch_type']==2]
    doc={'schema_version':2,'revision_id':model.revision_id,'input_manifest_sha256':contract.input_manifest_sha256,'model_sha256':contract.model_sha256,
         'sections':sections,'r_mips_32':runtime,'overlay_slots':slots,'audit':audit,'semantic_ledgers':{'exception_ledger':exceptions,'covered_alias_ledger':aliases,'manual_size_recovery_ledger':manual,'direct_call_candidate_ledger':direct,'indirect_transfer_ledger':indirect}}
    path=root/'runtime-link-private.json'
    if path.exists():raise ValueError('Runtime manifest output already exists')
    path.write_text(json.dumps(doc,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return doc
