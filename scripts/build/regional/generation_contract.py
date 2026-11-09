"""Immutable, exact-input denominators consumed by normalization.

Counts are projections of retained original/model inventories, never a region
switch or values accepted from the compiler's output. Compiler observations must
then reconcile site by site with those inventories.
"""
from __future__ import annotations
from dataclasses import asdict,dataclass
from types import MappingProxyType
from typing import Mapping
from scripts.regional.json_contract import loads
from scripts.regional.relocation_inventory import ImageLayout,derive
from scripts.regional.relocation_translation import ExceptionBindings,translate
from scripts.regional.program_model import CodeRef
from collections import Counter
from pathlib import Path
import hashlib,json
from scripts.rom_profiles import ROM_PROFILES
from scripts.regional.program_model import from_document

@dataclass(frozen=True)
class GenerationContract:
    revision_id: str
    input_manifest_sha256: str
    model_sha256: str
    original_inventory_sha256: str
    authoritative_body_count: int
    support_thunk_count: int
    overlay_slot_count: int
    empty_overlay_slot_count: int
    section_count: int
    r32_relocation_count: int
    r26_relocation_count: int
    direct_call_candidate_count: int
    direct_linked_call_candidate_count: int
    direct_tail_candidate_count: int
    direct_generated_target_candidate_count: int
    direct_unresolved_target_candidate_count: int
    executable_symbol_count: int
    covered_alias_count: int
    covered_alias_body_start_count: int
    covered_alias_interior_count: int
    manual_size_recovery_count: int
    instruction_relocation_count: int
    hi_lo_pair_count: int
    indirect_transfer_site_count: int
    native_return_site_count: int
    indirect_decision_site_count: int
    direct_transfer_role_counts: Mapping[str,int]
    direct_instruction_class_counts: Mapping[str,int]

    @classmethod
    def read(cls,path:Path) -> GenerationContract:
        path=path.resolve(strict=True);raw=path.read_bytes();doc=loads(raw)
        if not isinstance(doc,dict) or set(doc)!={'schema_version','kind','revision_id','rom_sha1','model_sha256','original_inventory_sha256','elf_sha256','counts','files'} or type(doc['schema_version']) is not int or doc['schema_version']!=3 or doc['kind']!='jfg-regional-generation-input':
            raise ValueError('Invalid generation input manifest')
        profiles={p.revision_id:p for p in ROM_PROFILES}
        profile=profiles.get(doc['revision_id'])
        if profile is None or profile.sha1!=doc['rom_sha1']:raise ValueError('Unknown or mismatched generation revision')
        required={'execution-contract.json','original-private.z64','image-layout.json','program-model.json','original-relocations.json','translated-relocations.json','direct-sites.json','indirect-sites.json','alternate-entries.json','exception-bindings.json','patched-private.z64','symbols-private.toml','recompile-private.toml'}
        if not isinstance(doc['files'],dict) or set(doc['files'])!=required:raise ValueError('Incomplete generation input bundle')
        values={}
        for name,expected in doc['files'].items():
            member=path.parent/name
            if member.is_symlink() or member.resolve(strict=True).parent!=path.parent:raise ValueError('Generation input escapes its bundle')
            data=member.read_bytes()
            if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Generation input digest mismatch: '+name)
            if name.endswith('.json'):values[name]=loads(data)
        model=from_document(values['program-model.json'])
        if (model.revision_id,model.rom_sha1,model.elf_sha256,model.fingerprint())!=(doc['revision_id'],doc['rom_sha1'],doc['elf_sha256'],doc['model_sha256']):raise ValueError('Generation model identity mismatch')
        original=values['original-relocations.json'];translated=values['translated-relocations.json'];counts=doc['counts']
        rom=(path.parent/'original-private.z64').read_bytes()
        if len(rom)!=profile.size or hashlib.sha1(rom).hexdigest()!=profile.sha1:
            raise ValueError('Generation bundle does not contain its exact original ROM')
        from scripts.regional.execution import validate_contract
        validate_contract(values['execution-contract.json'],rom,model,path.parent/'symbols-private.toml',path.parent/'recompile-private.toml',values['alternate-entries.json'])
        layout=ImageLayout.from_document(values['image-layout.json'])
        reproduced=derive(rom,model,layout)
        if loads(reproduced.canonical_bytes())!=original:
            raise ValueError('Original relocation inventory does not reproduce from ROM')
        binding_fields=dict(values['exception-bindings.json'])
        binding_fields['trap']=CodeRef(**binding_fields['trap'])
        translation=translate(rom,model,layout,reproduced,ExceptionBindings(**binding_fields))
        if [asdict(v) for v in translation.relocations]!=translated or translation.patched_rom!=(path.parent/'patched-private.z64').read_bytes():
            raise ValueError('Translated inputs do not reproduce from exact original records')
        canonical=(json.dumps(original,sort_keys=True,separators=(',',':'))+'\n').encode()
        if hashlib.sha256(canonical).hexdigest()!=doc['original_inventory_sha256'] or original['revision_id']!=model.revision_id or original['model_sha256']!=model.fingerprint() or original['rom_sha1']!=model.rom_sha1:raise ValueError('Original relocation identity mismatch')
        record_sites={(v['ordinal'],v['section'],v['section_offset'],v['patch_type']) for v in original['records']}
        translated_sites={(v['original_ordinal'],v['source_section'],v['source_offset'],v['patch_type']) for v in translated}
        if len(record_sites)!=len(original['records']) or len(translated)!=len(record_sites) or record_sites!=translated_sites:raise ValueError('Translated source inventory differs from original')
        patches=Counter(v['patch_type'] for v in original['records']);direct=values['direct-sites.json'];indirect=values['indirect-sites.json'];alternate=values['alternate-entries.json']
        roles={k:sum(v['transfer_role']==k for v in direct) for k in ('linked-call','direct-tail')}
        classes={k:sum(v['instruction_class']==k for v in direct) for k in ('jal','bgezal','j','conditional-branch')}
        targets=Counter(v['target_class'] for v in direct)
        if sum(roles.values())!=len(direct) or sum(classes.values())!=len(direct) or set(targets)-{'authoritative-body','alternate-entry','unresolved-candidate'}:raise ValueError('Unknown direct transfer classification')
        for rows,fields in ((direct,('source_section','source_offset')),(indirect,('section','offset')),(alternate,('section','offset'))):
            if len({tuple(row[f] for f in fields) for row in rows})!=len(rows):raise ValueError('Duplicate code inventory site')
        native_returns=sum(v['source_register']==31 for v in indirect)
        get=lambda k:counts.get(k,0)
        if (get('sections')!=len(model.sections) or get('bodies')!=len(model.bodies)
            or get('support_entries')!=len(alternate) or get('direct_sites')!=len(direct) or get('indirect_sites')!=len(indirect)
            or get('native_return_candidates')!=native_returns or get('indirect_decision_candidates')!=len(indirect)-native_returns
            or get('executable_symbols')!=get('sized_functions')+get('zero_size_functions')
            or get('zero_size_functions')!=get('covered_aliases')+get('recovered_zero_size_functions')
            or get('bodies')!=get('sized_functions')+get('recovered_zero_size_functions')
            or get('covered_aliases')!=get('body_start_aliases')+get('interior_aliases')
            or get('explicit_aliases')!=len(model.aliases)):
            raise ValueError('Generation denominator does not reconcile with source inventory')
        if any(type(v) is not int or v<0 for k,v in counts.items() if not isinstance(v,dict)):raise ValueError('Invalid generation count')
        return cls(model.revision_id,hashlib.sha256(raw).hexdigest(),model.fingerprint(),doc['original_inventory_sha256'],
                   len(model.bodies),len(alternate),len(original['headers']),sum(not h['text_size'] and not h['data_size'] for h in original['headers']),len(model.sections),
                   patches[2],patches[4],len(direct),roles['linked-call'],roles['direct-tail'],targets['authoritative-body']+targets['alternate-entry'],targets['unresolved-candidate'],
                   get('executable_symbols'),get('covered_aliases'),get('body_start_aliases'),get('interior_aliases'),get('recovered_zero_size_functions'),
                   patches[4]+patches[5]+patches[6],patches[5],len(indirect),native_returns,len(indirect)-native_returns,MappingProxyType(roles),MappingProxyType(classes))

    def check_identity(self,document:dict) -> None:
        if document.get('revision_id')!=self.revision_id or document.get('input_manifest_sha256')!=self.input_manifest_sha256 or document.get('model_sha256')!=self.model_sha256:
            raise ValueError('Runtime manifest belongs to a different generation input')
