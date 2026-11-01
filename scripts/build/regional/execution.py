"""Region-bound instruction accounting for the one original-OS runtime.

The hardware cost model is shared. Only verified guest scheduling/idle sites are
revision data. These settings describe the existing timing implementation and
do not claim native-console timing parity.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib,json,tomllib
from scripts.regional.json_contract import loads
from scripts.regional.program_model import CodeRef
from scripts.regional.bindings import read_recipes
from scripts.rom_profiles import PROFILES_BY_ID
from scripts.original_timing_generation import INTEGER_COST,FLOAT_COST

ROOT=Path(__file__).resolve().parents[3]
RECIPE=ROOT/'config/roms/execution-sites.json'

@dataclass(frozen=True)
class ExecutionSites:
    revision_id: str
    model_sha256: str
    park: CodeRef
    park_address: int
    slow: tuple[tuple[str,int],...]
    slow_addresses: frozenset[int]

def locate(rom,model,row):
    sections={s.id:s for s in model.sections};matches=[]
    for b in model.bodies:
        s=sections[b.section]
        if s.kind.value!=row['section_kind'] or b.size!=row['body_size']:continue
        start=s.rom_start+b.offset
        if hashlib.sha256(rom[start:start+b.size]).hexdigest()==row['body_sha256']:matches.append((s,b))
    if len(matches)!=1:raise ValueError('Execution site has no unique exact original body')
    return matches[0]

def qualify_sites(rom,model,alternate_entries=()):
    doc=loads(RECIPE.read_bytes())
    if set(doc)!={'schema_version','revisions'} or type(doc['schema_version']) is not int or doc['schema_version']!=1 or set(doc['revisions'])!=set(PROFILES_BY_ID):raise ValueError('Invalid execution-site recipe')
    recipe=doc['revisions'][model.revision_id]
    if set(recipe)!={'park','slow_sites'} or set(recipe['park'])!={'section_kind','body_sha256','body_size','entry_offset'} or not isinstance(recipe['slow_sites'],list) or not recipe['slow_sites']:raise ValueError('Missing execution scheduling semantics')
    code_recipe=recipe['park']
    section,body=locate(rom,model,code_recipe);inner=code_recipe['entry_offset']
    if type(inner) is not int or inner<0 or inner%4 or inner+4>body.size:raise ValueError('Scheduler park is outside its original body')
    park=CodeRef(model.revision_id,section.id,body.offset+inner)
    if inner and (section.source_index,park.offset) not in {(v['section'],v['offset']) for v in alternate_entries}:raise ValueError('Scheduler park lacks an independently inventoried callable entry')
    park_address=section.linked_vram+park.offset
    slow=[];addresses=[];names=set()
    for site in recipe['slow_sites']:
        if set(site)!={'name','section_kind','body_sha256','body_size','instruction_offset'} or site['name'] in names:raise ValueError('Invalid or duplicate execution site')
        names.add(site['name']);s,b=locate(rom,model,site);offset=site['instruction_offset']
        if type(offset) is not int or offset<0 or offset%4 or offset+4>b.size:raise ValueError('Execution site is not an owned instruction')
        slow.append((s.id,b.offset+offset));addresses.append(s.linked_vram+b.offset+offset)
    if len(set(slow))!=len(slow):raise ValueError('Duplicate execution instruction')
    return ExecutionSites(model.revision_id,model.fingerprint(),park,park_address,tuple(slow),frozenset(addresses))

def metadata(section,pc,word,sites):
    primary=word>>26
    fpu=primary in (0x11,0x31,0x35,0x39,0x3d)
    park=primary==3 and (((pc+4)&0xf0000000)|((word&0x03ffffff)<<2))==sites.park_address
    branch=primary in range(1,8) or primary in range(20,24) or (primary==0 and word&63 in (8,9)) or (primary==0x11 and (word>>21)&31==8)
    slow=word==0x1000ffff or pc in sites.slow_addresses
    extra=INTEGER_COST.get(word&63,0) if primary==0 else FLOAT_COST.get(((word>>21)&31,word&63),0) if primary==17 else 0
    reads=(0x1a,0x1b,*range(0x20,0x28),0x30,0x31,0x34,0x35,0x37);writes=(*range(0x28,0x2f),0x38,0x39,0x3c,0x3d,0x3f)
    kind=1 if primary in reads else 2 if primary in writes else 3 if primary==0x2f else 0
    if type(section) is not int or not 0<=section<256 or not 0<=extra<128:raise ValueError('Instruction metadata exceeds shared hook ABI')
    return section|(fpu<<8)|(park<<9)|(branch<<10)|(slow<<11)|(kind<<12)|(extra<<16)

def configure(root,rom,model,alternate_entries):
    config=root/'recompile-private.toml';text=config.read_text()
    if 'emit_guest_' in text or '[[patches.hook]]' in text:raise ValueError('Execution hooks require a fresh compiler configuration')
    sites=qualify_sites(rom,model,alternate_entries);symbols=tomllib.loads((root/'symbols-private.toml').read_text());patched=(root/'patched-private.z64').read_bytes()
    settings='emit_guest_link_registers = true\nemit_guest_cpu_state = true\nemit_guest_dynamic_returns = true\nemit_guest_idle_loops = true\n'
    rows=[text+'\n'+settings+'[patches]\n'];count=0
    for index,section in enumerate(symbols['section']):
        for function in section['functions']:
            start,size=function['vram'],function['size'];offset=section['rom']+start-section['vram']
            if size<=0 or size%4 or start%4 or offset<0 or offset+size>len(patched):raise ValueError('Invalid instruction extent')
            for byte in range(0,size,4):
                pc=start+byte;word=int.from_bytes(patched[offset+byte:offset+byte+4],'big')
                hook=f'jfg_phase9_execution_probe_predecoded(0x{(metadata(index,pc,word,sites)|(0x800000 if size<=512 else 0)):08x}U, 0x{pc:08x}U, 0x{word:08x}U, ctx);'
                rows.append('[[patches.hook]]\nfunc = '+json.dumps(function['name'])+f'\nbefore_vram = 0x{pc:08x}\ntext = '+json.dumps(hook)+'\n');count+=1
    config.write_text('\n'.join(rows),encoding='utf-8',newline='\n')
    return {'schema_version':1,'kind':'jfg-original-execution-contract','revision_id':model.revision_id,'model_sha256':model.fingerprint(),'architecture':'original-os-cache-device-clock','hook_abi':1,'instruction_sites':count,'park':asdict(sites.park),'slow':[{'section':s,'offset':o} for s,o in sites.slow],'recipes_sha256':hashlib.sha256(RECIPE.read_bytes()).hexdigest()}

def validate_contract(doc,rom,model,symbols_path,config_path,alternate_entries):
    sites=qualify_sites(rom,model,alternate_entries)
    expected_keys={'schema_version','kind','revision_id','model_sha256','architecture','hook_abi','instruction_sites','park','slow','recipes_sha256'}
    if set(doc)!=expected_keys or doc['schema_version']!=1 or doc['kind']!='jfg-original-execution-contract' or doc['architecture']!='original-os-cache-device-clock' or doc['hook_abi']!=1 or (doc['revision_id'],doc['model_sha256'])!=(model.revision_id,model.fingerprint()) or doc['park']!=asdict(sites.park) or doc['slow']!=[{'section':s,'offset':o} for s,o in sites.slow] or doc['recipes_sha256']!=hashlib.sha256(RECIPE.read_bytes()).hexdigest():raise ValueError('Execution contract differs from original site bindings')
    symbols=tomllib.loads(symbols_path.read_text());count=sum(f['size']//4 for s in symbols['section'] for f in s['functions']);text=config_path.read_text()
    if type(doc['instruction_sites']) is not int or doc['instruction_sites']!=count or text.count('[[patches.hook]]')!=count or text.count('jfg_phase9_execution_probe_predecoded(')!=count or any(text.count(k+' = true')!=1 for k in ('emit_guest_link_registers','emit_guest_cpu_state','emit_guest_dynamic_returns','emit_guest_idle_loops')):raise ValueError('Compiler input omits original execution hooks')
