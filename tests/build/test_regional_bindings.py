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

if __name__=='__main__':unittest.main()
