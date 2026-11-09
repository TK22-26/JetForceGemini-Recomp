"""Qualify named SDK/linker bindings against exact original function hashes.

Recipes contain reviewed hashes and operand locations, not regional VRAM maps.
Generated coordinates and detailed evidence remain in the private input bundle.
"""
from pathlib import Path
from dataclasses import asdict
import hashlib,json,re,struct
from scripts.regional.generation_contract import GenerationContract
from scripts.regional.program_model import from_document,CodeRef,AddressDomain
from scripts.regional.json_contract import loads
from scripts.rom_profiles import PROFILES_BY_ID

ROOT=Path(__file__).resolve().parents[3]
RECIPES=ROOT/'config/roms/core-bindings.json'
NAME=re.compile(r'[a-z][A-Za-z0-9_.]*\Z')

def address_operand(body,hi_offset,lo_offset):
    if any(type(v) is not int or v<0 or v%4 or v+4>len(body) for v in (hi_offset,lo_offset)) or hi_offset>=lo_offset:raise ValueError('Invalid data-reference operand coordinates')
    hi=struct.unpack_from('>I',body,hi_offset)[0];lo=struct.unpack_from('>I',body,lo_offset)[0]
    if hi>>26!=15 or (hi>>21)&31 or not (hi>>16)&31 or (lo>>21)&31!=(hi>>16)&31 or lo>>26 not in (9,32,33,35,36,37,39,40,41,43,49,53,57,61):
        raise ValueError('Original data-reference register/opcode guard failed')
    return (((hi&65535)<<16)+(lo&65535)-(65536 if lo&32768 else 0))&0xffffffff

def validate_native_consumers(entry,root=ROOT):
    # Check required names before normalizing thousands of translation units.
    # This is consumer coverage, not proof of the referenced original behavior.
    paths=list((root/'src/boot/native').glob('*.cpp'))+list((root/'src/boot/native').glob('*.hpp'))
    paths += list((root/'src/boot').glob('*.inl'))
    paths+=list((root/'include/jfg/renderer').glob('*.hpp'))
    paths+=list((root/'include/jfg/mod').glob('*.hpp'))+list((root/'include/jfg/runtime').glob('*.hpp'))
    patterns=(('code',r'\b(?:game_code|game_overlay_token|overlay_dispatch_token|code_address|code_reference)\(\s*"([A-Za-z0-9_.]+)"'),
        ('data',r'\b(?:game_data|game_data_ref|game_overlay_data|overlay_data_offset|data_address|data_reference|global_u8|global_u16|global_u32|global_s16|global_f32|global_address|global_contains|global_valid)\(\s*"([A-Za-z0-9_.]+)"'),
        ('instructions',r'\b(?:game_instruction|game_instruction_word|game_overlay_site|game_member|member_offset|instruction_address|instruction_reference|instruction_matches)\(\s*"([A-Za-z0-9_.]+)"'))
    missing=[]
    for path in paths:
        source=path.read_text(encoding='utf-8')
        source=re.sub(r'//[^\n]*|/\*.*?\*/','',source,flags=re.S)
        for domain,pattern in patterns:
            for name in re.findall(pattern,source):
                if name not in entry[domain]:missing.append((str(path.relative_to(root)),domain,name))
        for name in re.findall(r'\boriginal_os_entry\(\s*"([A-Za-z0-9_.]+)"',source):
            if 'sdk.'+name not in entry['code']:missing.append((str(path.relative_to(root)),'original OS observer',name))
    if missing:raise ValueError('Native consumers require missing bindings: '+repr(sorted(set(missing))))


def read_recipes():
    recipes=loads(RECIPES.read_bytes())
    if set(recipes)!={'schema_version','kind','qualification','revisions'} or type(recipes['schema_version']) is not int or recipes['schema_version']!=1 or recipes['kind']!='jfg-core-binding-recipes' or set(recipes['revisions'])!=set(PROFILES_BY_ID):raise ValueError('Invalid core binding recipe catalog')
    sets=[]
    for entry in recipes['revisions'].values():
        if set(entry)!={'code','data','instructions','runlink_abi'}:raise ValueError('Incomplete core binding recipe')
        sets.append((set(entry['code']),set(entry['data']),set(entry['instructions'])))
    if any(s!=sets[0] for s in sets):raise ValueError('A revision omits a mandatory core semantic operation')
    if not {'runlink.cold_load','runlink.resume','runlink.resolve_reference'}<=sets[0][0] or not {'runlink.module_table_pointer','runlink.suspended_modules','os.current_thread','os.flash_handle','audio.cache_control','audio.cache_nodes','audio.cache_frame','audio.pending_dma'}<=sets[0][1] or not {'vi.initialize','vi.manager_idle','os.mi_mask_read','os.mi_mask_write','cutscene.sound_fire_and_forget','cutscene.sound_handle','cutscene.sound_positioned'}<=sets[0][2]:raise ValueError('Missing mandatory runlink operation')
    validate_native_consumers(next(iter(recipes['revisions'].values())))
    return recipes

def resolve_code(model,ref,alternates):
    try:return model.resolve(ref)
    except ValueError:
        section=next((s for s in model.sections if s.id==ref.section),None)
        if ref.revision_id!=model.revision_id or section is None or type(ref.offset) is not int or ref.offset%4:raise
        if not any(a['section']==section.source_index and a['offset']==ref.offset for a in alternates):raise
        owners=[b for b in model.bodies if b.section==ref.section and b.offset<ref.offset and ref.offset+4<=b.offset+b.size]
        if len(owners)!=1:raise ValueError('Callable alternate entry has no unique original body')
        return owners[0]


def qualify_audio_layout(bodies, code, sections):
    """Verify the cache ABI from independent initializer/owner witnesses."""
    callback=bodies['audio.source_callback'];factory=bodies['audio.source_factory']
    initialize=bodies['audio.manager_initialize'];reclaim=bodies['audio.cache_reclaim']
    control=address_operand(callback,0,4);nodes=address_operand(factory,24,28)
    frame=address_operand(callback,88,92);pending=address_operand(callback,332,336)
    ref=code['audio.source_callback'];target=sections[ref['section']].linked_vram+ref['offset']
    if (address_operand(factory,0,4)!=control or address_operand(factory,12,20)!=target or
        address_operand(initialize,648,652)!=nodes or address_operand(initialize,664,680)!=nodes+76*20 or
        address_operand(reclaim,100,104)!=control or address_operand(reclaim,112,120)!=frame or
        address_operand(reclaim,8,12)!=pending or nodes!=control+16 or pending!=frame+4):
        raise ValueError('Audio cache ABI owner witnesses disagree')
    qref=code['sdk.osCreateMesgQueue'];qaddr=sections[qref['section']].linked_vram+qref['offset']
    if struct.unpack_from('>II',initialize,0x300)!=(0x0c000000|((qaddr>>2)&0x3ffffff),0x24060008):raise ValueError('Audio frame queue initializer/capacity differs')
    queue=bodies['sdk.osCreateMesgQueue']
    if 0xac800008 not in struct.unpack('>'+str(len(queue)//4)+'I',queue):raise ValueError('SDK message valid-count field differs')
    for body,offset,word in ((initialize,704,0x26520014),(initialize,720,0x26100280),
                             (callback,68,0x24430280),(callback,380,0x24180280)):
        if struct.unpack_from('>I',body,offset)[0]!=word:raise ValueError('Unreviewed audio cache stride or buffer extent')


def qualify_code_recipes(recipes,model,rom,alternates):
    sections={s.id:s for s in model.sections};candidates={};selected={}
    for name,row in recipes.items():
        keys={'section_kind','body_sha256','body_size','entry_offset'}
        if row.get('section_kind')=='overlay':keys=keys|{'overlay_slot'}
        if not NAME.fullmatch(name) or set(row) not in (keys,keys|{'anchor'}) or row['section_kind'] not in ('main','overlay') or not isinstance(row['body_sha256'],str) or not re.fullmatch('[0-9a-f]{64}',row['body_sha256']) or any(type(row[k]) is not int or row[k]<0 for k in ('body_size','entry_offset')):
            raise ValueError('Invalid semantic code recipe')
        if row['section_kind']=='overlay' and (type(row['overlay_slot']) is not int or not 1<=row['overlay_slot']<=0xfff):raise ValueError('Invalid original overlay slot')
        if 'anchor' in row:
            anchor=row['anchor']
            if not isinstance(anchor,dict) or set(anchor)!={'source','instruction_offset'} or anchor['source'] not in recipes or anchor['source']==name or type(anchor['instruction_offset']) is not int or anchor['instruction_offset']<0 or anchor['instruction_offset']%4:
                raise ValueError('Invalid semantic code call anchor')
        found=[]
        for body in model.bodies:
            section=sections[body.section]
            if section.kind.value!=row['section_kind'] or body.size!=row['body_size']:continue
            if section.kind.value=='overlay' and section.overlay_slot!=row['overlay_slot']:continue
            start=section.rom_start+body.offset;payload=rom[start:start+body.size]
            if hashlib.sha256(payload).hexdigest()==row['body_sha256']:found.append((section,body,payload))
        if not found:raise ValueError('Semantic body is absent: '+name)
        candidates[name]=found
    pending=set(recipes)
    while pending:
        progressed=False
        for name in sorted(pending):
            row=recipes[name];found=candidates[name]
            if 'anchor' in row:
                anchor=row['anchor']
                if anchor['source'] not in selected:continue
                section,body,payload=selected[anchor['source']];offset=anchor['instruction_offset']
                if offset+4>len(payload):raise ValueError('Call anchor escapes its original owner')
                word=struct.unpack_from('>I',payload,offset)[0]
                if word>>26!=3:raise ValueError('Semantic anchor is not an original direct call')
                pc=section.linked_vram+body.offset+offset
                target=((pc+4)&0xf0000000)|((word&0x3ffffff)<<2)
                found=[v for v in found if v[0].linked_vram+v[1].offset+row['entry_offset']==target]
            if len(found)!=1:raise ValueError('Semantic body is absent or ambiguous: '+name)
            section,body,payload=found[0]
            if row['entry_offset']%4 or row['entry_offset']+4>body.size:raise ValueError('Code entry is outside its hashed original body')
            resolve_code(model,CodeRef(model.revision_id,section.id,body.offset+row['entry_offset']),alternates)
            selected[name]=found[0];pending.remove(name);progressed=True
        if not progressed:raise ValueError('Unresolved or cyclic semantic call anchors')
    return selected


def qualify_cutscene_sound_layout(bodies,code,instructions,sections):
    process=bodies['game.animseqProcessCommandList'];stop=bodies['game.animseqStopSounds']
    def word(body,offset):
        if offset<0 or offset+4>len(body):raise ValueError('Cutscene sound witness escapes original body')
        return struct.unpack_from('>I',body,offset)[0]
    base=code['game.animseqProcessCommandList']['offset'];sites=[]
    for name,target_name in (('fire_and_forget','game.amSndPlay'),('handle','game.amSndPlay'),('positioned','game.amSndPlayXYZ')):
        site=instructions['cutscene.sound_'+name]['offset']-base;target=code[target_name];address=sections[target['section']].linked_vram+target['offset']
        if word(process,site)!=(0x0c000000|((address>>2)&0x3ffffff)):raise ValueError('Cutscene sound call target differs from qualified operation')
        sites.append(site)
    first,handle,positioned=sites
    if not first<handle<positioned:raise ValueError('Cutscene sound opcode ownership differs')
    expected=((first-4,0x00002825),(first+4,0x02602025),(handle+4,0x02002825),
        (handle-40,0x0005c880),(handle-36,0x032e8021),(handle-32,0x8e040000),
        (handle-8,0xae000000),(positioned-56,0x8e020088),(positioned-32,0xae000088),
        (positioned-28,0x8e05000c),(positioned-24,0x8e060010),(positioned-20,0x8e070014),
        (positioned-12,0x26180088),(positioned-8,0xafb80014),(positioned-4,0xafaf0010))
    if any(word(process,offset)!=value for offset,value in expected):raise ValueError('Unreviewed cutscene sound argument, handle or actor ABI')
    start=address_operand(stop,12,28);end=address_operand(stop,16,24)
    if end!=start+64 or address_operand(process,handle-48,handle-44)!=start or word(stop,60)!=0x26100004 or word(stop,32)!=0x8e040000 or word(stop,56)!=0xae000000:
        raise ValueError('Cutscene sound slot extent/stride owners disagree')


def qualify_mesh_layout(bodies):
    # Shared packed mesh schema is admitted only after original constructors
    # and drawing loops agree on strides, range sentinels and matrix-bank size.
    # Model face bounds come from the final batch sentinel, as native rendering
    # does; an otherwise unused adjacent header halfword is not authoritative.
    expected = {
        'owner.layout.makeModelGfx': ((312, 605945866), (376, 2254569480), (384, 180480), (388, 2255749126), (392, 2255224854), (396, 2255290392), (1164, 645070864)),
        'owner.layout.modelCompactInstance': ((20, 290944), (24, 29650977), (28, 946240)),
        'owner.layout.modelInstance': ((40, 227712), (56, 606011402), (60, 52363289), (376, 2902786064), (380, 2904031252)),
    }
    for name, checks in expected.items():
        body=bodies[name]
        if any(offset+4>len(body) or struct.unpack_from('>I',body,offset)[0]!=word for offset,word in checks):
            raise ValueError('Unreviewed packed mesh schema: '+name)


def qualify_record_arrays(bodies):
    # Original character accessor proves (character & 3)*0x76 + 0x15c.
    # Collision matrix owner proves two 64-byte banks beginning at +0x80.
    # These shared packed-array constants are never inferred from a US delta.
    expected = {'owner.layout.mainGetGameCharacter': [(16, 816316419), (84, 545024), (88, 21516323), (92, 675968), (104, 21516323), (108, 675904), (112, 19533857), (116, 608305500)], 'owner.layout.bridgeMatrices': [(352, 2421686571), (360, 1624448), (364, 5842977), (384, 2420637995), (392, 543104), (396, 4794401), (404, 614793344)]}
    for name, checks in expected.items():
        body=bodies[name]
        if any(offset+4>len(body) or struct.unpack_from('>I',body,offset)[0]!=word for offset,word in checks):
            raise ValueError('Unreviewed game record array: '+name)


def qualify_effect_arrays(bodies):
    # Original draws multiply the selected bank by 80 beam bytes or by
    # 20 vertices * 10 bytes for shockwaves, then add the control allocation.
    expected = {'owner.layout.beamDraw': [(220, 604504144), (232, 2423849165), (240, 52953113), (248, 20498), (252, 6969377)], 'owner.layout.objDrawShockWave': [(392, 2420900314), (396, 604438548), (400, 25624601), (404, 604504074), (420, 49170), (432, 50855961), (436, 20498), (440, 4900897)]}
    for name, checks in expected.items():
        body=bodies[name]
        if any(offset+4>len(body) or struct.unpack_from('>I',body,offset)[0]!=word for offset,word in checks):
            raise ValueError('Unreviewed effect vertex bank: '+name)


def qualify_sound_queue_layout(bodies):
    # Original player constructor, callback, queue constructor/post/next verify
    # player queue/event/period/callback, free/head links, active/drop/high-water
    # counters, 28-byte nodes and 16-byte payload. Drop count is not capacity.
    expected = {'owner.audio.soundPlayerConstructor': [(76, 2911567948), (208, 612630548), (500, 2911698952), (528, 604700704), (532, 2813001768), (548, 633602068), (556, 2378563660), (568, 654573588), (576, 654639148)], 'owner.audio.eventQueueConstructor': [(24, 2780823568), (32, 2782920724), (40, 2801795090), (48, 2938109960), (56, 2902458380), (64, 2904555520), (72, 2906652676), (104, 813248), (108, 28076067), (112, 878720)], 'owner.audio.eventQueuePost': [(40, 2379153408), (68, 2535981074), (88, 2502557714), (92, 625672193), (96, 2771058706), (132, 604373008), (140, 614793228), (148, 2240610320), (156, 2777546768), (164, 2247622672), (168, 2247688212), (192, 2768896020), (228, 632160264)], 'audio.sound_next_event': [(32, 2379153416), (68, 604373008), (76, 612630540), (88, 2409955368), (96, 2401763336), (108, 2234122256), (120, 2771058704), (128, 604831743), (132, 2779512832)], 'audio.sound_callback': [(28, 2247622700), (64, 621019156), (72, 2365980748), (92, 612630572), (108, 623116308), (116, 623181868), (124, 2906783824)]}
    for name, checks in expected.items():
        body=bodies[name]
        if any(offset+4>len(body) or struct.unpack_from('>I',body,offset)[0]!=word for offset,word in checks):
            raise ValueError('Unreviewed sound queue ABI: '+name)


def qualify_inventory_arrays(bodies):
    expected = {'owner.layout.weaponPickupInit': [(124, 612499592), (128, 2755854336)], 'owner.layout.mainSetDefaultCharacter': [(112, 2789212180), (124, 2790785076), (120, 640745473), (132, 706805776), (136, 642908162)]}
    for name, checks in expected.items():
        body=bodies[name]
        if any(offset+4>len(body) or struct.unpack_from('>I',body,offset)[0]!=word for offset,word in checks):
            raise ValueError('Unreviewed inventory array or pickup payload: '+name)
    for name, delta in (('game.controlPlayer',0),):
        body=bodies[name]
        # JP inserts two earlier instructions. Select only the qualified
        # original destination-load sequence, never a region-wide delta.
        matches=[]
        for at in (0x184,0x18c):
            if struct.unpack_from('>I',body,at)[0]==0x240100ff:matches.append(at)
        if len(matches)!=1:raise ValueError('Exit destination sentinel owner differs')
        at=matches[0]
        expected=(0x240100ff,0x90a3000b,0x90a6000a,0x10610002,0x00037200,0x00ce3025)
        if struct.unpack_from('>6I',body,at)!=expected:raise ValueError('Exit destination sentinel schema differs')


def qualify_track_arrays(bodies):
    # Original loader and plane/light builders prove 72-byte blocks, 10-byte
    # vertices, 16-byte faces/batches/planes and 8-byte plane-index entries.
    expected = {'owner.layout.trackLoader': [(776, 638582856)], 'owner.layout.trackLightAllocate': [(260, 605356042), (272, 26542105), (388, 647233608)], 'owner.layout.trackPlanes': [(116, 604766218), (132, 2218983432), (136, 2219900952), (140, 2219835398), (156, 260352), (192, 2423128065), (204, 32243737), (240, 2219704322), (264, 2219769860), (288, 2423783426), (336, 2423128067), (624, 1970432), (632, 3876454400), (648, 3855351812), (664, 3875667976), (716, 3854827532), (732, 671023120), (756, 645070864), (904, 639168), (920, 2387542040)]}
    for name, checks in expected.items():
        body=bodies[name]
        if any(offset+4>len(body) or struct.unpack_from('>I',body,offset)[0]!=word for offset,word in checks):
            raise ValueError('Unreviewed track geometry schema: '+name)


def qualify_navigation_layout(bodies,code,data,sections):
    def require(name,expected):
        body=bodies[name]
        if any(offset+4>len(body) or struct.unpack_from('>I',body,offset)[0]!=word for offset,word in expected):
            raise ValueError('Unreviewed navigation array layout: '+name)
    require('owner.layout.cameraActors',((88,0x2413004c),(92,0x24140004),(136,0x26100001),(140,0x01f30019),(148,0x0258c821),(152,0x1614fff1)))
    require('owner.layout.multiplayerRecords',((48,0x240d0004),(120,0x24090075),(156,0x24420001),(160,0x246300a0),(172,0x254a00a0),(176,0x144dffe0),(180,0x256b00a0)))
    multi=bodies['owner.layout.multiplayerRecords']
    if address_operand(multi,16,28)!=address_operand(multi,0,4)+0x16:raise ValueError('Multiplayer inventory field differs')
    require('owner.layout.weaponPowerupObjects',((300,0x29010010),(312,0x2407000f),(336,0x00074840),(352,0x01495021)))
    require('owner.layout.exitConditions',((32,0x04600020),(36,0x28610019),(44,0x00037080),(56,0x01cf2821),(60,0x90a40000),(96,0x90b80001)))
    def address(name):
        ref=data[name];section=sections[ref['section']]
        return section.linked_vram+section.text_size+(section.data_size if ref['domain']=='bss' else 0)+ref['offset']
    accessor=bodies['game.objGetPlayerlist']
    if address_operand(accessor,0,4)!=address('globals.playerCount') or address_operand(accessor,8,16)!=address('globals.playerList'):
        raise ValueError('Player accessor differs from independently qualified state owners')


def qualify_transition_owner(bodies,code,data,sections):
    # This indirect scene handler has no direct resident caller. Identify its
    # behavior through independent semantic callees and transition-state owner.
    body=bodies['owner.guard.flight.func_80046070']
    for offset,target_name in ((76,'game.fxFadeOn'),(104,'game.setupClearScreen'),
        (120,'game.amTuneSetFade'),(264,'game.mainGetGameFlag'),(288,'game.mainSetGameFlag'),
        (1424,'game.runlinkIsModuleLoaded'),(1620,'game.partFreeLib'),
        (1748,'game.levelGetTune'),(1772,'game.amTuneStop')):
        ref=code[target_name];target=sections[ref['section']].linked_vram+ref['offset']
        if struct.unpack_from('>I',body,offset)[0]!=(0x0c000000|((target>>2)&0x3ffffff)):
            raise ValueError('Scene transition semantic callee differs: '+target_name)
    ref=data['globals.transitionPrompt'];section=sections[ref['section']]
    address=section.linked_vram+section.text_size+(section.data_size if ref['domain']=='bss' else 0)+ref['offset']
    if address_operand(body,16,20)!=address:raise ValueError('Scene transition state owner differs')


def qualify_sidekick_returns(bodies,code,instructions,sections):
    body=bodies['game.sidekickControl'];owner=code['game.sidekickControl']['offset']
    for site,target_name,delay in (('sidekick_owner_return','game.controlReadJoypad',0x24040001),
        ('sidekick_coop_return','game.controlReadJoypad',0),
        ('sidekick_flight_return','game.mathOneFloatPY',0xe7a200a8)):
        offset=instructions['native.'+site]['offset']-owner
        target=code[target_name];address=sections[target['section']].linked_vram+target['offset']
        if offset<8 or struct.unpack_from('>II',body,offset-8)!=(0x0c000000|((address>>2)&0x3ffffff),delay):
            raise ValueError('Sidekick return has a different semantic call or argument ABI: '+site)


def member_operand(word):
    if type(word) is not int or not 0<=word<=0xffffffff or word>>26 not in (32,33,35,36,37,39,40,41,43,49,53,57,61) or (word>>21)&31 in (0,29) or word&0x8000:
        raise ValueError('Layout member is not a positive object-relative memory operand')
    return word&0xffff


def qualify_turn_bank_layout(instructions):
    """Keep movement-generated body bank distinct from camera turn delta.

    The initializer and all three independently hashed character handlers must
    agree on the field. A valid memory operand alone cannot establish its role.
    """
    bank=member_operand(instructions['layout.playerControl.turnBank']['original_word'])
    turn=member_operand(instructions['layout.playerControl.turnDelta']['original_word'])
    if bank==turn:raise ValueError('Turn bank aliases camera turn delta')
    for character in ('juno','vela','lupus'):
        word=instructions['guard.control.'+character+'.turnBank']['original_word']
        if word>>26!=41 or (word>>21)&31!=16 or member_operand(word)!=bank:
            raise ValueError('Character turn-bank writer disagrees with initializer')


def relocated_data_operand(body, source_section, source_offset, offset, target_slot, sections, relocations):
    """Resolve a field through the reproduced original relocation inventory.

    GenerationContract.read has independently reconstructed these records from
    the exact original ROM. A recipe pins the original referring body and site;
    generated C, guessed regional deltas and loaded addresses are not authority.
    """
    if type(offset) is not int or offset<0 or offset%4 or offset+4>len(body):
        raise ValueError('Relocated data operand escapes its original body')
    if type(target_slot) is not int or not 0<=target_slot<=0xfff:
        raise ValueError('Invalid relocated data owner')
    word=struct.unpack_from('>I',body,offset)[0]
    if word>>26 not in (9,32,33,35,36,37,39,40,41,43,49,53,57,61):
        raise ValueError('Relocated data site is not an address or memory operand')
    found=[v for v in relocations if v['source_section']==source_section and v['source_offset']==source_offset+offset]
    if len(found)!=1 or found[0]['patch_type']!=6 or found[0]['disposition']!='resolved':
        raise ValueError('Data site lacks a unique original low relocation')
    ref=found[0];section=sections.get(ref['target_section'])
    if section is None or (section.kind.value!='main' if target_slot==0 else section.kind.value!='overlay' or section.overlay_slot!=target_slot):
        raise ValueError('Original data reference has a different module owner')
    relative=ref['target_offset']
    if type(relative) is not int or not section.text_size<=relative<section.memory_size:
        raise ValueError('Original data reference does not target DATA/BSS')
    return section,relative


def qualify(root:Path):
    contract=GenerationContract.read(root/'input-manifest.json')
    model=from_document(loads((root/'program-model.json').read_bytes()));rom=(root/'original-private.z64').read_bytes()
    recipes=read_recipes();recipe=recipes['revisions'][model.revision_id];sections={s.id:s for s in model.sections};code={};data={};instructions={};bodies={};evidence={};alternates=loads((root/'alternate-entries.json').read_bytes())
    relocations=loads((root/'translated-relocations.json').read_bytes())
    selected=qualify_code_recipes(recipe['code'],model,rom,alternates)
    for name,(s,b,payload) in selected.items():
        row=recipe['code'][name]
        ref=CodeRef(model.revision_id,s.id,b.offset+row['entry_offset'])
        code[name]=asdict(ref);bodies[name]=payload;evidence[name]={'original_body_sha256':row['body_sha256'],'section':s.id,'body_offset':b.offset,'body_size':b.size,'entry_offset':row['entry_offset']}
    for name,row in recipe['data'].items():
        scalar_keys={'source','hi_offset','lo_offset','size','alignment','writable'}
        relocation_keys={'source','relocation_offset','target_slot','size','alignment','writable'}
        if not NAME.fullmatch(name) or set(row) not in (scalar_keys,scalar_keys|{'content_sha256'},relocation_keys,relocation_keys|{'content_sha256'}) or row['source'] not in bodies or type(row['writable']) is not bool or any(type(row[k]) is not int or row[k]<=0 for k in ('size','alignment')):raise ValueError('Invalid semantic data recipe')
        if 'relocation_offset' in row:
            owner=evidence[row['source']]
            s,relative=relocated_data_operand(bodies[row['source']],owner['section'],owner['body_offset'],row['relocation_offset'],row['target_slot'],sections,relocations)
            address=s.linked_vram+relative
        else:
            address=address_operand(bodies[row['source']],row['hi_offset'],row['lo_offset'])
            owners=[s for s in model.sections if s.kind.value!='overlay' and s.linked_vram+s.text_size<=address and address+row['size']<=s.linked_vram+s.memory_size]
            if len(owners)!=1:raise ValueError('Semantic data operand lacks a resident DATA/BSS owner: '+name)
            s=owners[0];relative=address-s.linked_vram
        domain=AddressDomain.DATA if relative<s.initialized_size else AddressDomain.BSS;start=s.text_size if domain==AddressDomain.DATA else s.initialized_size;offset=relative-start
        try:s.checked_offset(domain,offset,row['size'])
        except ValueError as error:raise ValueError('Semantic data extent invalid: '+name) from error
        if 'content_sha256' in row:
            expected=row['content_sha256']
            if domain!=AddressDomain.DATA or not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('Invalid original data-content recipe')
            start=s.rom_start+relative
            if hashlib.sha256(rom[start:start+row['size']]).hexdigest()!=expected:raise ValueError('Original data content differs: '+name)

        if row['alignment']&(row['alignment']-1) or address%row['alignment']:raise ValueError('Unaligned semantic data binding')
        data[name]={'revision_id':model.revision_id,'section':s.id,'domain':domain.value,'offset':offset,'size':row['size'],'alignment':row['alignment'],'writable':row['writable']}
        evidence[name]={k:row[k] for k in ('source','hi_offset','lo_offset','relocation_offset','target_slot') if k in row}
        evidence[name]['source_body_sha256']=evidence[row['source']]['original_body_sha256']
    for name,row in recipe['instructions'].items():
        if not NAME.fullmatch(name) or set(row)!={'source','instruction_offset'} or row['source'] not in bodies:raise ValueError('Invalid instruction recipe')
        source=row['source'];offset=row['instruction_offset']
        if type(offset) is not int or offset<0 or offset%4 or offset+4>len(bodies[source]):raise ValueError('Instruction is outside its hashed original body')
        owner=evidence[source]
        if name.startswith('layout.'):
            member_operand(struct.unpack_from('>I',bodies[source],offset)[0])
            if any(v['source_section']==owner['section'] and v['source_offset']==owner['body_offset']+offset for v in relocations):raise ValueError('Object member cannot be an address relocation')
        instructions[name]={'revision_id':model.revision_id,'section':owner['section'],'offset':owner['body_offset']+offset,'original_word':struct.unpack_from('>I',bodies[source],offset)[0]}
        evidence[name]={'source':source,'instruction_offset':offset,'source_body_sha256':owner['original_body_sha256']}
    mi=bodies['sdk.osSetIntMask']
    if any(struct.unpack_from('>I',mi,offset)[0]!=word for offset,word in ((36,0x3c0aa430),(40,0x8d4a000c),(104,0x3c01a430),(108,0xac2a000c))):
        raise ValueError('Unreviewed original interrupt-mask instructions')
    qualify_turn_bank_layout(instructions)
    qualify_audio_layout(bodies,code,sections)
    qualify_sound_queue_layout(bodies)
    ai=bodies['audio.ai_submit']
    if any(struct.unpack_from('>I',ai,offset)[0]!=word for offset,word in ((128,0x3c0ca450),(132,0xad820000),(140,0x3c0fa450),(148,0xaded0004))):
        raise ValueError('Original AI submit register ABI differs')

    qualify_cutscene_sound_layout(bodies,code,instructions,sections)
    qualify_navigation_layout(bodies,code,data,sections)
    qualify_mesh_layout(bodies)
    qualify_record_arrays(bodies)
    qualify_track_arrays(bodies)
    qualify_inventory_arrays(bodies)
    qualify_effect_arrays(bodies)
    for name,word in (("frame.camera.allocate",0x27bdff10),("frame.camera.actor",0xafa400f0),("frame.camera.focus",0x27a40098),("frame.camera.point",0x27a5008c)):
        if instructions[name]['original_word']!=word:raise ValueError('Unreviewed camera stack ABI: '+name)

    qualify_transition_owner(bodies,code,data,sections)
    qualify_sidekick_returns(bodies,code,instructions,sections)
    original=loads((root/'original-relocations.json').read_bytes());slots=len(original['headers'])
    if recipe['runlink_abi']!={'record_size':32,'suspended_record_size':8,'suspended_record_count':16}:raise ValueError('Unreviewed runlink layout ABI')
    return {'schema_version':3,'kind':'jfg-qualified-core-bindings','revision_id':model.revision_id,'model_sha256':model.fingerprint(),'input_sha256':contract.input_manifest_sha256,'recipes_sha256':hashlib.sha256(RECIPES.read_bytes()).hexdigest(),'code':code,'data':data,'instructions':instructions,'evidence':evidence,'runlink_abi':dict(recipe['runlink_abi'],overlay_slot_count=slots)}

def validate_document(doc,descriptor):
    if not isinstance(doc,dict) or set(doc)!={'schema_version','kind','revision_id','model_sha256','input_sha256','recipes_sha256','code','data','instructions','evidence','runlink_abi'} or type(doc['schema_version']) is not int or doc['schema_version']!=3 or doc['kind']!='jfg-qualified-core-bindings':raise ValueError('Invalid qualified bindings schema')
    model=from_document(descriptor['model']);sections={s.id:s for s in model.sections}
    if (doc['revision_id'],doc['model_sha256'],doc['input_sha256'])!=(model.revision_id,model.fingerprint(),descriptor['input_sha256']):raise ValueError('Bindings belong to another program corpus')
    recipes=read_recipes();recipe=recipes['revisions'][model.revision_id]
    if doc['recipes_sha256']!=hashlib.sha256(RECIPES.read_bytes()).hexdigest() or set(doc['code'])!=set(recipe['code']) or set(doc['data'])!=set(recipe['data']) or set(doc['instructions'])!=set(recipe['instructions']) or set(doc['evidence'])!=set(doc['code'])|set(doc['data'])|set(doc['instructions']):raise ValueError('Bindings no longer match mandatory recipe coverage')
    for ref in doc['code'].values():resolve_code(model,CodeRef(**ref),descriptor['alternate_entries'])
    for name,ref in doc['instructions'].items():
        if set(ref)!={'revision_id','section','offset','original_word'} or ref['revision_id']!=model.revision_id or type(ref['offset']) is not int or ref['offset']%4 or type(ref['original_word']) is not int or not 0<=ref['original_word']<=0xffffffff:raise ValueError('Invalid instruction binding')
        row=recipe['instructions'][name];source=doc['code'][row['source']]
        owner=resolve_code(model,CodeRef(**source),descriptor['alternate_entries'])
        if ref['section']!=owner.section or ref['offset']!=owner.offset+row['instruction_offset'] or not owner.offset<=ref['offset']<=owner.offset+owner.size-4:raise ValueError('Instruction binding differs from original recipe')
    for ref in doc['data'].values():
        if set(ref)!={'revision_id','section','domain','offset','size','alignment','writable'} or ref['revision_id']!=model.revision_id or type(ref['writable']) is not bool:raise ValueError('Invalid qualified data binding')
        domain=AddressDomain(ref['domain']);s=sections[ref['section']]
        if domain not in (AddressDomain.DATA,AddressDomain.BSS):raise ValueError('Core data requires DATA/BSS')
        offset=s.checked_offset(domain,ref['offset'],ref['size'])
        if type(ref['alignment']) is not int or ref['alignment']<=0 or ref['alignment']&(ref['alignment']-1) or (s.linked_vram+offset)%ref['alignment']:raise ValueError('Invalid data binding alignment')
    abi=doc['runlink_abi']
    if set(abi)!={'record_size','suspended_record_size','suspended_record_count','overlay_slot_count'} or any(type(v) is not int for v in abi.values()) or {k:v for k,v in abi.items() if k!='overlay_slot_count'}!=recipe['runlink_abi'] or abi['overlay_slot_count']<max(s.overlay_slot or 0 for s in model.sections):raise ValueError('Invalid qualified runlink ABI')
    return model

def emit_cpp(doc,descriptor):
    model=validate_document(doc,descriptor);sections={s.id:s for s in model.sections};revision=json.dumps(model.revision_id)
    out=['// Private generated core bindings. Do not track.','#pragma once','#include "jfg/game/bindings.hpp"','#include "linked-descriptor.hpp"','namespace jfg::game::linked {',f'inline constexpr std::array<NamedCodeRef,{len(doc["code"])}> code_refs = {{{{']
    for name,ref in sorted(doc['code'].items()):out.append(f'  {{"{name}", {{{revision},{sections[ref["section"]].source_index}U,{ref["offset"]}U}}}},')
    out+=['}};',f'inline constexpr std::array<NamedDataRef,{len(doc["data"])}> data_refs = {{{{']
    for name,ref in sorted(doc['data'].items()):out.append(f'  {{"{name}", {{{revision},{sections[ref["section"]].source_index}U,DataDomain::{ref["domain"]},{ref["offset"]}U,{ref["size"]}U,{ref["alignment"]}U}}, {str(ref["writable"]).lower()}}},')
    out+=['}};',f'inline constexpr std::array<NamedInstructionRef,{len(doc["instructions"])}> instruction_refs = {{{{']
    for name,ref in sorted(doc['instructions'].items()):out.append(f'  {{"{name}", {{{revision},{sections[ref["section"]].source_index}U,{ref["offset"]}U}}, {ref["original_word"]}U}},')
    abi=doc['runlink_abi'];out+=['}};','inline constexpr Bindings bindings = {',f'  kBindingAbi,{revision},"{doc["model_sha256"]}","{doc["input_sha256"]}",code_refs,data_refs,',f'  {abi["overlay_slot_count"]}U,{abi["record_size"]}U,{abi["suspended_record_size"]}U,{abi["suspended_record_count"]}U, instruction_refs','};']
    sdk=[]
    for name,ref in doc['code'].items():
        if name.startswith('sdk.'):
            s=sections[ref['section']];sdk.append((s.linked_vram+ref['offset'],name[4:],s.source_index,ref['offset']))
    out.append(f'inline constexpr std::array<SdkMapping,{len(sdk)}> sdk_mappings = {{{{')
    for address,name,section,offset in sorted(sdk):out.append(f'  {{{address}U,"{name}",{{{revision},{section}U,{offset}U}}}},')
    out+=['}};',r"""consteval std::uint32_t code_address(std::string_view name) {
  for (const auto& binding : code_refs) if (binding.name == name) {
    const auto& ref = binding.reference;
    if (ref.revision != descriptor.revision || ref.section >= sections.size() || sections[ref.section].kind == SectionKind::overlay) throw "Code binding requires an overlay lease";
    return sections[ref.section].linked_address + ref.offset;
  }
  throw "Missing mandatory semantic code binding";
}
// This is the original linked dispatch identity, never a RAM address or a
// callable pointer. Execution continues through GeneratedOverlayRuntime's
// existing lifetime/dependency lease after the dispatch owner is resolved.
consteval std::uint32_t overlay_dispatch_token(std::string_view name) {
  for (const auto& binding : code_refs) if (binding.name == name) {
    const auto& ref = binding.reference;
    if (ref.revision != descriptor.revision || ref.section >= sections.size()) throw "Invalid overlay identity";
    const auto& section = sections[ref.section];
    if (section.kind != SectionKind::overlay || ref.offset >= section.text_size ||
        section.linked_address != (section.overlay_slot << 20U)) throw "Not an original overlay code identity";
    return section.linked_address + ref.offset;
  }
  throw "Missing mandatory overlay code binding";
}
consteval std::uint32_t instruction_word(std::string_view name) {
  for(const auto& binding:instruction_refs)if(binding.name==name)return binding.original_word;
  throw "Missing original instruction binding";
}
consteval std::uint32_t member_offset(std::string_view name) {
  if(!name.starts_with("layout."))throw "Not an object member binding";
  for(const auto& binding:instruction_refs)if(binding.name==name) {
    const auto word=binding.original_word,op=word>>26U,base=(word>>21U)&31U;
    if(base==0U || base==29U || (word&0x8000U) ||
       !(op==32U || op==33U || op==35U || op==36U || op==37U || op==39U || op==40U || op==41U || op==43U || op==49U || op==53U || op==57U || op==61U))throw "Invalid object member operand";
    return word&0xffffU;
  }
  throw "Missing object member binding";
}
consteval std::uint32_t instruction_address(std::string_view name) {
  for (const auto& binding : instruction_refs) if (binding.name == name) {
    const auto& ref = binding.reference;
    if (ref.revision != descriptor.revision || ref.section >= sections.size() || sections[ref.section].kind == SectionKind::overlay) throw "Instruction binding requires an overlay lease";
    return sections[ref.section].linked_address + ref.offset;
  }
  throw "Missing mandatory semantic instruction binding";
}
consteval CodeRef code_reference(std::string_view name) {
  for (const auto& binding : code_refs) if (binding.name == name) return binding.reference;
  throw "Missing mandatory semantic code binding";
}
consteval InstructionRef instruction_reference(std::string_view name) {
  for (const auto& binding : instruction_refs) if (binding.name == name) return binding.reference;
  throw "Missing mandatory semantic instruction binding";
}
consteval DataRef data_reference(std::string_view name) {
  for (const auto& binding : data_refs) if (binding.name == name) return binding.reference;
  throw "Missing mandatory semantic data binding";
}
// Only an offset within the named module is exposed. The caller must hold the
// live overlay view/lease; this never manufactures a loaded RAM address.
consteval std::uint32_t overlay_data_offset(std::string_view name, std::uint32_t owner) {
  const auto ref=data_reference(name);
  if(ref.revision!=descriptor.revision || ref.section!=owner || owner>=sections.size()) throw "Overlay data owner mismatch";
  const auto& section=sections[owner];
  if(section.kind!=SectionKind::overlay || (ref.domain!=DataDomain::data && ref.domain!=DataDomain::bss)) throw "Not overlay DATA/BSS";
  const auto size=ref.domain==DataDomain::data ? section.data_size : section.bss_size;
  if(!ref.size || ref.offset>size || ref.size>size-ref.offset) throw "Overlay data extent mismatch";
  return section.text_size+(ref.domain==DataDomain::bss?section.data_size:0U)+ref.offset;
}
consteval std::uint32_t data_address(std::string_view name) {
  for (const auto& binding : data_refs) if (binding.name == name) {
    const auto& ref = binding.reference;
    if (ref.revision != descriptor.revision || ref.section >= sections.size() || sections[ref.section].kind == SectionKind::overlay) throw "Data binding requires an overlay lease";
    const auto& section = sections[ref.section];
    return section.linked_address + section.text_size + (ref.domain == DataDomain::bss ? section.data_size : 0U) + ref.offset;
  }
  throw "Missing mandatory semantic data binding";
}""",'} // namespace jfg::game::linked','']
    return '\n'.join(out)
