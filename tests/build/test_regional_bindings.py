import struct,unittest
from scripts.regional.json_contract import loads
from scripts.regional.bindings import address_operand,read_recipes

class BindingContractTests(unittest.TestCase):
    def test_duplicate_members_and_nonfinite_values_rejected(self):
        for value in ('{"revision":1,"revision":2}','{"x":NaN}','{"x":Infinity}'):
            with self.assertRaises(ValueError):loads(value)
    def test_data_operand_requires_original_opcode_and_base_register(self):
        body=struct.pack('>II',0x3c188010,0x8f18e500)
        self.assertEqual(address_operand(body,0,4),0x800fe500)
        for word in (0x8ef8e500,0x3718e500,0x0018e500):
            with self.assertRaises(ValueError):address_operand(struct.pack('>II',0x3c188010,word),0,4)
    def test_every_revision_declares_the_same_mandatory_core_operations(self):
        revisions=read_recipes()['revisions'];first=next(iter(revisions.values()))
        self.assertGreaterEqual(sum(n.startswith('sdk.') for n in first['code']),58)
        for row in revisions.values():
            self.assertEqual(set(row['code']),set(first['code']))
            self.assertTrue(set(row['data'])>={'runlink.module_table_pointer','runlink.suspended_modules','os.current_thread','os.flash_handle','audio.cache_control','audio.cache_nodes','audio.cache_frame','audio.pending_dma'})

class CallAnchorTests(unittest.TestCase):
    def fixture(self):
        import hashlib
        from scripts.regional.program_model import ProgramModel,Section,SectionKind,FunctionBody
        address=0x80001000
        source=struct.pack('>II',0x0c000000|((address+24)>>2&0x3ffffff),0)
        leaf=struct.pack('>I',0x03e00008)
        rom=source+bytes(8)+leaf+bytes(4)+leaf+bytes(36)
        model=ProgramModel('synthetic-r0','a'*40,len(rom),'b'*64,
            (Section('main',SectionKind.MAIN,0,0,address,len(rom),0,0),),
            (FunctionBody('main',0,8,('source',)),FunctionBody('main',16,4,('other',)),FunctionBody('main',24,4,('target',))))
        def recipe(body):return dict(section_kind='main',body_sha256=hashlib.sha256(body).hexdigest(),body_size=len(body),entry_offset=0)
        recipes={'game.source':recipe(source),'game.target':dict(recipe(leaf),anchor={'source':'game.source','instruction_offset':0})}
        return recipes,model,rom

    def test_original_call_disambiguates_identical_body_bytes(self):
        from scripts.regional.bindings import qualify_code_recipes
        recipes,model,rom=self.fixture()
        self.assertEqual(qualify_code_recipes(recipes,model,rom,[])['game.target'][1].offset,24)

    def test_missing_invalid_and_cyclic_anchors_cannot_admit_an_ambiguous_leaf(self):
        from scripts.regional.bindings import qualify_code_recipes
        for kind in ('absent','not-call','outside','cycle','wrong-hash'):
            recipes,model,rom=self.fixture()
            if kind=='absent':recipes['game.target'].pop('anchor')
            elif kind=='not-call':recipes['game.target']['anchor']['instruction_offset']=4
            elif kind=='outside':recipes['game.target']['anchor']['instruction_offset']=8
            elif kind=='cycle':recipes['game.source']['anchor']={'source':'game.target','instruction_offset':0}
            else:recipes['game.target']['body_sha256']='0'*64
            with self.subTest(kind=kind),self.assertRaises(ValueError):qualify_code_recipes(recipes,model,rom,[])

class NativeConsumerCoverageTests(unittest.TestCase):
    def test_missing_original_observer_fails_before_codegen(self):
        import tempfile
        from pathlib import Path
        from scripts.regional.bindings import validate_native_consumers
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'src/boot/native';source.mkdir(parents=True)
            (source/'observer.cpp').write_text('target==original_os_entry("missing")',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'missing bindings'):
                validate_native_consumers(dict(code={},data={},instructions={}),root)
    def test_bound_game_read_and_site_require_their_own_domains(self):
        import tempfile
        from pathlib import Path
        from scripts.regional.bindings import validate_native_consumers
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'src/boot/native';source.mkdir(parents=True)
            (source/'observer.cpp').write_text('m.global_u8("globals.state");m.instruction_matches("guard.site");',encoding='utf-8')
            entry=dict(code={'globals.state':{},'guard.site':{}},data={},instructions={})
            with self.assertRaisesRegex(ValueError,'missing bindings'):validate_native_consumers(entry,root)
            entry['data']['globals.state']={};entry['instructions']['guard.site']={}
            validate_native_consumers(entry,root)

class OverlayOwnerRecipeTests(unittest.TestCase):
    def fixture(self):
        import hashlib
        from scripts.regional.program_model import ProgramModel,Section,SectionKind,FunctionBody
        payload=struct.pack('>II',0x03e00008,0)
        model=ProgramModel('synthetic-r0','a'*40,64,'b'*64,
            (Section('main',SectionKind.MAIN,0,16,0x80000400,8,0,0),
             Section('overlay:15',SectionKind.OVERLAY,1,0,15<<20,8,0,0,15),
             Section('overlay:16',SectionKind.OVERLAY,2,8,16<<20,8,0,0,16)),
            (FunctionBody('overlay:15',0,8,('first',)),FunctionBody('overlay:16',0,8,('second',))))
        recipe=dict(section_kind='overlay',overlay_slot=16,body_sha256=hashlib.sha256(payload).hexdigest(),body_size=8,entry_offset=0)
        return recipe,model,payload*2+bytes(48)
    def test_identical_bytes_in_another_overlay_do_not_change_owner(self):
        from scripts.regional.bindings import qualify_code_recipes
        row,model,rom=self.fixture()
        section,body,payload=qualify_code_recipes({'overlay.test':row},model,rom,[])['overlay.test']
        self.assertEqual(section.overlay_slot,16)
    def test_missing_invalid_and_absent_overlay_owners_fail(self):
        from scripts.regional.bindings import qualify_code_recipes
        for value in (None,True,0,17,0x1000):
            row,model,rom=self.fixture()
            if value is None:row.pop('overlay_slot')
            else:row['overlay_slot']=value
            with self.subTest(value=value),self.assertRaises(ValueError):qualify_code_recipes({'overlay.test':row},model,rom,[])
    def test_main_recipe_cannot_carry_an_overlay_slot(self):
        from scripts.regional.bindings import qualify_code_recipes
        row,model,rom=self.fixture();row['section_kind']='main'
        with self.assertRaises(ValueError):qualify_code_recipes({'overlay.test':row},model,rom,[])

class RelocatedDataRecipeTests(unittest.TestCase):
    def fixture(self):
        from scripts.regional.program_model import Section,SectionKind
        section=Section('overlay:15',SectionKind.OVERLAY,2,0,15<<20,8,8,8,15)
        ref=dict(source_section='overlay:16',source_offset=44,patch_type=6,disposition='resolved',target_section=section.id,target_offset=18)
        return struct.pack('>I',0x95020000),{section.id:section},[ref]
    def resolve(self,body,sections,refs,**kw):
        from scripts.regional.bindings import relocated_data_operand
        return relocated_data_operand(body,'overlay:16',44,kw.get('offset',0),kw.get('owner',15),sections,refs)
    def test_data_uses_original_target_module_and_domain(self):
        body,sections,refs=self.fixture();section,offset=self.resolve(body,sections,refs)
        self.assertEqual((section.overlay_slot,offset),(15,18))
    def test_wrong_owner_missing_or_duplicate_relocation_and_code_targets_fail(self):
        for kind in ('owner','missing','duplicate','text','retained','jump','exception','outside','opcode'):
            body,sections,refs=self.fixture();kw={}
            if kind=='owner':kw['owner']=16
            elif kind=='missing':refs=[]
            elif kind=='duplicate':refs*=2
            elif kind=='text':refs[0]['target_offset']=4
            elif kind=='retained':refs[0]['target_offset']=24
            elif kind=='jump':refs[0]['patch_type']=4
            elif kind=='exception':refs[0]['disposition']='reserved-atomic-pair'
            elif kind=='outside':kw['offset']=4
            elif kind=='opcode':body=struct.pack('>I',0x0c000000)
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.resolve(body,sections,refs,**kw)

class ObjectMemberTests(unittest.TestCase):
    def test_members_reject_addresses_stack_operands_and_negative_offsets(self):
        from scripts.regional.bindings import member_operand
        self.assertEqual(member_operand(0x92020568),0x568)
        for word in (0x8fa20010,0x8c020010,0x9202fff8,0x3c02800a,True):
            with self.subTest(word=word),self.assertRaises(ValueError):member_operand(word)

class PackedMeshSchemaTests(unittest.TestCase):
    def test_changed_stride_or_range_operand_is_rejected(self):
        from scripts.regional.bindings import qualify_mesh_layout
        checks={'owner.layout.makeModelGfx': [(312, 605945866), (376, 2254569480), (384, 180480), (388, 2255749126), (392, 2255224854), (396, 2255290392), (1164, 645070864)], 'owner.layout.modelCompactInstance': [(20, 290944), (24, 29650977), (28, 946240)], 'owner.layout.modelInstance': [(40, 227712), (56, 606011402), (60, 52363289), (376, 2902786064), (380, 2904031252)]}
        originals={name:bytearray(max(p for p,w in rows)+4) for name,rows in checks.items()}
        for name,rows in checks.items():
            for offset,word in rows:struct.pack_into('>I',originals[name],offset,word)
        qualify_mesh_layout(originals)
        for name,rows in checks.items():
            for offset,word in rows:
                changed={k:bytearray(v) for k,v in originals.items()}
                struct.pack_into('>I',changed[name],offset,word^1)
                with self.subTest(owner=name,offset=offset),self.assertRaisesRegex(ValueError,'mesh schema'):
                    qualify_mesh_layout(changed)

class RecordArraySchemaTests(unittest.TestCase):
    def test_changed_character_stride_or_matrix_bank_is_rejected(self):
        from scripts.regional.bindings import qualify_record_arrays
        checks={'owner.layout.mainGetGameCharacter': [(16, 816316419), (84, 545024), (88, 21516323), (92, 675968), (104, 21516323), (108, 675904), (112, 19533857), (116, 608305500)], 'owner.layout.bridgeMatrices': [(352, 2421686571), (360, 1624448), (364, 5842977), (384, 2420637995), (392, 543104), (396, 4794401), (404, 614793344)]}
        originals={name:bytearray(max(p for p,w in rows)+4) for name,rows in checks.items()}
        for name,rows in checks.items():
            for offset,word in rows:struct.pack_into('>I',originals[name],offset,word)
        qualify_record_arrays(originals)
        for name,rows in checks.items():
            for offset,word in rows:
                changed={k:bytearray(v) for k,v in originals.items()}
                struct.pack_into('>I',changed[name],offset,word^1)
                with self.subTest(owner=name,offset=offset),self.assertRaisesRegex(ValueError,'record array'):
                    qualify_record_arrays(changed)

class EffectBankSchemaTests(unittest.TestCase):
    def test_changed_bank_scale_or_base_is_rejected(self):
        from scripts.regional.bindings import qualify_effect_arrays
        checks={'owner.layout.beamDraw': [(220, 604504144), (232, 2423849165), (240, 52953113), (248, 20498), (252, 6969377)], 'owner.layout.objDrawShockWave': [(392, 2420900314), (396, 604438548), (400, 25624601), (404, 604504074), (420, 49170), (432, 50855961), (436, 20498), (440, 4900897)]}
        originals={name:bytearray(max(p for p,w in rows)+4) for name,rows in checks.items()}
        for name,rows in checks.items():
            for offset,word in rows:struct.pack_into('>I',originals[name],offset,word)
        qualify_effect_arrays(originals)
        for name,rows in checks.items():
            for offset,word in rows:
                changed={k:bytearray(v) for k,v in originals.items()}
                struct.pack_into('>I',changed[name],offset,word^1)
                with self.subTest(owner=name,offset=offset),self.assertRaisesRegex(ValueError,'vertex bank'):
                    qualify_effect_arrays(changed)

class SoundQueueSchemaTests(unittest.TestCase):
    def test_changed_queue_layout_or_payload_is_rejected(self):
        from scripts.regional.bindings import qualify_sound_queue_layout
        checks={'owner.audio.soundPlayerConstructor': [(76, 2911567948), (208, 612630548), (500, 2911698952), (528, 604700704), (532, 2813001768), (548, 633602068), (556, 2378563660), (568, 654573588), (576, 654639148)], 'owner.audio.eventQueueConstructor': [(24, 2780823568), (32, 2782920724), (40, 2801795090), (48, 2938109960), (56, 2902458380), (64, 2904555520), (72, 2906652676), (104, 813248), (108, 28076067), (112, 878720)], 'owner.audio.eventQueuePost': [(40, 2379153408), (68, 2535981074), (88, 2502557714), (92, 625672193), (96, 2771058706), (132, 604373008), (140, 614793228), (148, 2240610320), (156, 2777546768), (164, 2247622672), (168, 2247688212), (192, 2768896020), (228, 632160264)], 'audio.sound_next_event': [(32, 2379153416), (68, 604373008), (76, 612630540), (88, 2409955368), (96, 2401763336), (108, 2234122256), (120, 2771058704), (128, 604831743), (132, 2779512832)], 'audio.sound_callback': [(28, 2247622700), (64, 621019156), (72, 2365980748), (92, 612630572), (108, 623116308), (116, 623181868), (124, 2906783824)]}
        originals={name:bytearray(max(p for p,w in rows)+4) for name,rows in checks.items()}
        for name,rows in checks.items():
            for offset,word in rows:struct.pack_into('>I',originals[name],offset,word)
        qualify_sound_queue_layout(originals)
        for name,rows in checks.items():
            for offset,word in rows:
                changed={k:bytearray(v) for k,v in originals.items()}
                struct.pack_into('>I',changed[name],offset,word^1)
                with self.subTest(owner=name,offset=offset),self.assertRaisesRegex(ValueError,'sound queue ABI'):
                    qualify_sound_queue_layout(changed)

class InventorySchemaTests(unittest.TestCase):
    def test_changed_inventory_and_exit_formulas_reject(self):
        from scripts.regional.bindings import qualify_inventory_arrays
        checks={'owner.layout.weaponPickupInit': [[124, 612499592], [128, 2755854336]], 'owner.layout.mainSetDefaultCharacter': [[112, 2789212180], [124, 2790785076], [120, 640745473], [132, 706805776], [136, 642908162]]}
        for base in (0x184,0x18c):
            originals={name:bytearray(max(p for p,w in rows)+4) for name,rows in checks.items()}
            for name,rows in checks.items():
                for offset,word in rows:struct.pack_into('>I',originals[name],offset,word)
            originals['game.controlPlayer']=bytearray(0x1a4)
            sequence=(0x240100ff,0x90a3000b,0x90a6000a,0x10610002,0x00037200,0x00ce3025)
            struct.pack_into('>6I',originals['game.controlPlayer'],base,*sequence)
            qualify_inventory_arrays(originals)
            mutations={**checks,'game.controlPlayer':[(base+i*4,w) for i,w in enumerate(sequence)]}
            for name,rows in mutations.items():
                for offset,word in rows:
                    changed={k:bytearray(v) for k,v in originals.items()}
                    struct.pack_into('>I',changed[name],offset,word^1)
                    with self.subTest(owner=name,offset=offset),self.assertRaises(ValueError):
                        qualify_inventory_arrays(changed)

class TrackSchemaTests(unittest.TestCase):
    def test_changed_geometry_stride_or_range_rejects(self):
        from scripts.regional.bindings import qualify_track_arrays
        checks={'owner.layout.trackLoader': [[776, 638582856]], 'owner.layout.trackLightAllocate': [[260, 605356042], [272, 26542105], [388, 647233608]], 'owner.layout.trackPlanes': [[116, 604766218], [132, 2218983432], [136, 2219900952], [140, 2219835398], [156, 260352], [192, 2423128065], [204, 32243737], [240, 2219704322], [264, 2219769860], [288, 2423783426], [336, 2423128067], [624, 1970432], [632, 3876454400], [648, 3855351812], [664, 3875667976], [716, 3854827532], [732, 671023120], [756, 645070864], [904, 639168], [920, 2387542040]]}
        originals={name:bytearray(max(p for p,w in rows)+4) for name,rows in checks.items()}
        for name,rows in checks.items():
            for offset,word in rows:struct.pack_into('>I',originals[name],offset,word)
        qualify_track_arrays(originals)
        for name,rows in checks.items():
            for offset,word in rows:
                changed={k:bytearray(v) for k,v in originals.items()}
                struct.pack_into('>I',changed[name],offset,word^1)
                with self.subTest(owner=name,offset=offset),self.assertRaisesRegex(ValueError,'track geometry'):
                    qualify_track_arrays(changed)

if __name__=='__main__':unittest.main()

class TurnBankOwnershipTests(unittest.TestCase):
    def fixture(self,bank=0x120):
        fields={'layout.playerControl.turnBank':0xa6f80000|bank,
                'layout.playerControl.turnDelta':0xa600010a}
        fields.update({'guard.control.'+who+'.turnBank':word|bank for who,word in
                       [('juno',0xa60b0000),('vela',0xa6190000),('lupus',0xa60a0000)]})
        return {name:{'original_word':word} for name,word in fields.items()}
    def test_initializer_and_independent_character_writers_own_bank(self):
        from scripts.regional.bindings import qualify_turn_bank_layout
        for bank in (0x120,0x122,0x124):
            qualify_turn_bank_layout(self.fixture(bank))
    def test_regional_conversion_cannot_alias_bank_to_camera_delta(self):
        from scripts.regional.bindings import qualify_turn_bank_layout
        fields=self.fixture();fields['layout.playerControl.turnBank']=fields['layout.playerControl.turnDelta']
        with self.assertRaisesRegex(ValueError,'aliases'):qualify_turn_bank_layout(fields)
    def test_wrong_character_field_or_read_only_witness_is_rejected(self):
        from scripts.regional.bindings import qualify_turn_bank_layout
        for who in ('juno','vela','lupus'):
            for wrong in (0xa60b010a,0x860b0120):
                fields=self.fixture();fields['guard.control.'+who+'.turnBank']['original_word']=wrong
                with self.subTest(character=who,word=wrong),self.assertRaises(ValueError):
                    qualify_turn_bank_layout(fields)
