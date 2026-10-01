import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.autonomy import instruction_job as lane, instruction_observation as observation, supervisor
from scripts.autonomy.job_store import JobStore


class InstructionJobTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve()
        self.state = self.repo/'tools/private/autonomy'
        self.state.mkdir(parents=True)
        self.store = JobStore(self.state/'jobs.sqlite')
        self.addCleanup(self.store.close)
        self.raw = self.state/'raw.bin'
        self.raw.write_bytes(b'raw fixture')
        self.evidence = {str(self.raw):supervisor.file_sha256(self.raw)}
        self.pins = {'source_commit':'1'*40, **{key+'_sha256':'2'*64 for key in ('native','emulator','rom')},
                     'tool_sha256':'3'*64}
        self.request = {'fixture':True}
        for owner, name, value in ((lane,'tool_sha',self.pins['tool_sha256']),
                                   (lane,'inventory',(self.evidence,self.pins)),
                                   (observation,'validate_request',{})):
            patch = mock.patch.object(owner,name,return_value=value)
            patch.start()
            self.addCleanup(patch.stop)

    def queue(self):
        return lane.queue(self.store,self.repo,self.state,self.request)

    def report(self,job_id):
        packet,digest = lane.read_packet(self.repo,self.state,job_id,self.store.job(job_id)['spec'])
        return {'kind':'jfg-qualified-instruction-observation','complete':True,'job_id':job_id,
                'packet_sha256':digest,'pins':self.pins,'evidence':self.evidence,
                'source_commit':self.pins['source_commit'],'native_runtime_sha256':self.pins['native_sha256'],
                'oracle_runtime_sha256':self.pins['emulator_sha256'],'rom_sha256':self.pins['rom_sha256'],
                'qualification':{'passed':True},'correspondence':{'streams_complete':True},
                'promoted':False, **observation.native_effects.LIMITS}

    def child(self,job_id,mutate=None):
        def command(argv,repo,stdout,stderr,deadline,heartbeat,paused,**kwargs):
            self.assertEqual(argv[1:3],['-m','scripts.autonomy.instruction_job'])
            self.assertGreater(kwargs['memory_limit_bytes'],0)
            self.assertGreater(kwargs['cpu_seconds'],0)
            self.assertEqual(kwargs['guard_record'].name,'measurement.guard.json')
            heartbeat()
            report = self.report(job_id)
            if mutate: mutate(report)
            Path(argv[argv.index('--output')+1]).write_bytes(supervisor.canonical_bytes(report))
            return 0,None
        return command

    def test_repeat_intake_is_idempotent_for_all_existing_states(self):
        job_id = self.queue()
        self.assertEqual(self.queue(),job_id)
        lease = self.store.lease_job(job_id,'test',ttl=120)
        self.store.start(job_id,lease['token'])
        self.assertEqual(self.queue(),job_id)
        self.assertEqual(self.store.job(job_id)['state'],'running')
        self.store.fail_job(job_id,lease['token'],'test',blocked=True)
        self.assertEqual(self.queue(),job_id)
        self.assertEqual(self.store.job(job_id)['state'],'blocked')
        self.assertEqual(self.store.job(job_id)['attempts'],1)

    def test_pause_prevents_inventory_and_publication(self):
        (self.state/'PAUSED').touch()
        with mock.patch.object(lane,'inventory') as inventory:
            self.assertIsNone(self.queue())
            inventory.assert_not_called()
        self.assertFalse((self.state/'instruction-packets').exists())

    def test_envelope_tampering_rejected_before_measurement(self):
        job_id = self.queue()
        path = lane.packet_path(self.state,job_id)
        original = json.loads(path.read_text())
        for field,value in (('kind','wrong'),('job_id','different'),('schema',True),('pins',{}),('request',{})):
            with self.subTest(field=field):
                changed = {**original,field:value}
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    lane.read_packet(self.repo,self.state,job_id,self.store.job(job_id)['spec'])
        path.write_bytes(supervisor.canonical_bytes(original))
        self.raw.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):
            lane.read_packet(self.repo,self.state,job_id,self.store.job(job_id)['spec'])

    def test_job_identity_includes_build_evidence_and_producer(self):
        first = self.queue()
        with mock.patch.object(lane,'inventory',return_value=(self.evidence,{**self.pins,'tool_sha256':'4'*64})):
            self.assertNotEqual(first,self.queue())

    def test_independent_measurement_rejects_changed_inventory_and_build_identity(self):
        job_id = self.queue()
        for field,value in (('evidence',{}),('source_commit','5'*40),('native_runtime_sha256','6'*64),
                            ('oracle_runtime_sha256','7'*64),('rom_sha256','8'*64)):
            with self.subTest(field=field), mock.patch.object(observation,'measure',return_value={**self.report(job_id),field:value}):
                with self.assertRaisesRegex(ValueError,'pinned inventory or build'):
                    lane.measure_job(self.store,self.repo,self.state,job_id)

    def test_guarded_child_seals_complete_observation_once_without_agent(self):
        job_id = self.queue()
        with mock.patch.object(lane,'bounded_command',side_effect=self.child(job_id)), \
                mock.patch.object(supervisor,'require_chatgpt_login',side_effect=AssertionError('no model')):
            result = supervisor.run_once(self.repo,self.state,Path('unused'),allow_agent=False,job_id=job_id)
        self.assertIn('sealed',result)
        self.assertEqual(self.store.job(job_id)['state'],'passed')
        self.assertEqual(self.queue(),job_id)
        self.assertEqual(self.store.job(job_id)['attempts'],1)

    def test_incomplete_or_parity_claiming_child_cannot_pass_and_is_retained(self):
        for field,value in (('complete',False),('parity_verified',True),('promoted',True),('evidence',{})):
            with self.subTest(field=field):
                # A new input identity gives each independent rejection its own job.
                self.request = {'fixture':field}
                job_id = self.queue()
                lease = self.store.lease_job(job_id,'test',ttl=120)
                with mock.patch.object(lane,'bounded_command',side_effect=self.child(job_id,lambda r:r.update({field:value}))):
                    self.assertIn('blocked',lane.run_lease(self.store,lease,self.repo,self.state))
                self.assertEqual(self.store.job(job_id)['state'],'blocked')
                attempt = self.state/'attempts'/job_id/'0001'
                self.assertTrue((attempt/'result.json').is_file())
                self.assertTrue((attempt/'failure.json').is_file())

    def test_producer_change_does_not_launch_child(self):
        job_id = self.queue()
        lease = self.store.lease_job(job_id,'test',ttl=120)
        with mock.patch.object(lane,'tool_sha',return_value='9'*64), mock.patch.object(lane,'bounded_command') as command:
            self.assertIn('blocked',lane.run_lease(self.store,lease,self.repo,self.state))
            command.assert_not_called()

    def test_consumer_recomputes_and_rejects_a_contradiction(self):
        job_id=self.queue()
        lease=self.store.lease_job(job_id,'test',ttl=120)
        with mock.patch.object(lane,'bounded_command',side_effect=self.child(job_id)):
            lane.run_lease(self.store,lease,self.repo,self.state)
        result=self.report(job_id)
        with mock.patch.object(lane,'measure_job',return_value=result) as measure:
            self.assertEqual(lane.checked_observation(self.store,self.repo,self.state,job_id),result)
            measure.assert_called_once()
        with mock.patch.object(lane,'measure_job',return_value={**result,'unexpected':True}):
            with self.assertRaisesRegex(ValueError,'contradicts'):
                lane.checked_observation(self.store,self.repo,self.state,job_id)

    def test_packet_ids_cannot_escape_state(self):
        for value in ('../bad','',None,'a/b'):
            with self.subTest(value=value),self.assertRaises(ValueError): lane.packet_path(self.state,value)


class LoadEvidenceTests(unittest.TestCase):
    def fixture(self,op=55,base=0xffffffff80001000,offset=8,rs=26):
        word=(op<<26)|(rs<<21)|(27<<16)|(offset&65535)
        regs=[0]*32; regs[rs]=base
        entry={'pc':0x80002000,'opcode':word,'gpr':regs,'phase':0}
        oracle_entry={**entry,'phase':'entry'}
        a={**entry,'phase':1,'gpr':[*regs]}; a['gpr'][27]=1
        b={**a,'phase':'ordinary','gpr':[*regs]}
        report={'first_difference':{'kind':'shared-state','fields':{'gpr':{'27':{'native':1,'oracle':0}}},
                                    'native':a,'oracle':b},
                'preceding_context':[{'native':entry,'oracle':oracle_entry}]}
        native=bytearray(4*1024*1024); oracle=bytearray(native)
        width=8 if op==55 else 4
        address=((base+offset)&0xffffffff)-0x80000000
        if 0<=address<len(native)-width: native[address:address+width]=(1).to_bytes(width,'big')
        return report,{'native':{6:bytes(native),7:bytes(native)},'oracle':{6:bytes(oracle),7:bytes(oracle)}}

    def test_loaded_address_and_earlier_snapshot_are_not_live_memory_proof(self):
        report,snapshots=self.fixture()
        result=observation.load_evidence(report,snapshots,7)
        self.assertEqual(result['address'],0x80001008)
        self.assertEqual(result['width'],8)
        self.assertEqual(result['snapshots'][0],{'update':6,'native':1,'oracle':0,'equal':False,'precedes_observed_update':True})
        self.assertFalse(result['snapshots'][1]['precedes_observed_update'])
        self.assertFalse(result['live_memory_read_witness'])
        self.assertFalse(result['earlier_store_identified'])

    def test_negative_displacement_and_signed_word(self):
        report,snapshots=self.fixture(35,offset=-4)
        native=bytearray(snapshots['native'][6]); native[0xffc:0x1000]=bytes.fromhex('ffffffff')
        snapshots['native'][6]=bytes(native)
        result=observation.load_evidence(report,snapshots,7)
        self.assertEqual(result['address'],0x80000ffc)
        self.assertEqual(result['snapshots'][0]['native'],0xffffffffffffffff)

    def test_unknown_instruction_phase_target_or_address_has_no_load_claim(self):
        for op,base,offset in ((0,0xffffffff80001000,8),(55,0xffffffffa0001000,8),(55,0xffffffff80001000,1)):
            with self.subTest(op=op,base=base,offset=offset):
                report,snapshots=self.fixture(op,base,offset)
                self.assertIsNone(observation.load_evidence(report,snapshots,7))
        report,snapshots=self.fixture()
        report['first_difference']['fields']['status']={}
        self.assertIsNone(observation.load_evidence(report,snapshots,7))
        report,snapshots=self.fixture()
        report['preceding_context'][0]['oracle']['pc']+=4
        self.assertIsNone(observation.load_evidence(report,snapshots,7))

    def test_input_base_is_before_load_even_when_destination_aliases_base(self):
        report,snapshots=self.fixture(rs=27)
        # Do not substitute post-effect state for the instruction's address input.
        result=observation.load_evidence(report,snapshots,7)
        self.assertEqual(result['address'],0x80001008)

    def test_equal_snapshots_do_not_blame_an_earlier_store(self):
        report,snapshots=self.fixture()
        snapshots['native']=copy.deepcopy(snapshots['oracle'])
        result=observation.load_evidence(report,snapshots,7)
        self.assertTrue(all(row['equal'] for row in result['snapshots']))
        self.assertIn('do not locate an earlier divergence',result['next_question'])


class RequestTests(unittest.TestCase):
    def test_distinct_private_off_on_captures_and_pinned_builds_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp).resolve(); private=repo/'tools/private'; private.mkdir(parents=True)
            request={'schema':1,'kind':'instruction-observation-request','window':[7,8],'update':7,
                'probe':{'entry_pc':'0x80001000','call_pc':'0x80002000',
                         'pcs':['0x80001000','0x80002008'],'words':['0x800a9e90']}}
            for name in ('native','native_control','oracle','oracle_control'):
                path=private/name; path.mkdir(); request[name]=str(path)
            for name in ('native_build','oracle_build'):
                path=private/(name+'.json'); path.write_text('{}')
                request[name]={'path':str(path),'sha256':supervisor.file_sha256(path)}
            self.assertEqual(len(observation.validate_request(repo,request)),4)
            with self.assertRaisesRegex(ValueError,'distinct'):
                observation.validate_request(repo,{**request,'native_control':request['native']})
            with self.assertRaisesRegex(ValueError,'escaped'):
                observation.validate_request(repo,{**request,'oracle':str(repo)})
            bad=copy.deepcopy(request); bad['oracle_build']['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'changed'):
                observation.validate_request(repo,bad)

    def test_schema_and_window_reject_before_access(self):
        request={key:None for key in observation.FIELDS}
        request.update(schema=1,kind='instruction-observation-request',window=[7,8],update=7)
        for field,value in (('schema',True),('kind','other'),('window',[7,23]),('window',[8,7]),
                            ('window',[True,8]),('update',6),('update',True)):
            with self.subTest(field=field),self.assertRaises(ValueError):
                observation.validate_request(Path('.'),{**request,field:value})

    def test_checkpoint_inventory_rejects_duplicates_and_nonintegers(self):
        for checkpoints in ([],[True],[7,7],[-1],list(range(1,18))):
            with self.subTest(checkpoints=checkpoints),self.assertRaises(ValueError):
                observation.capture_files(Path('.'),'oracle',{'checkpoints':checkpoints},[7,8])


class ProducerTests(unittest.TestCase):
    def test_identity_covers_both_readers_witnesses_and_build_validator(self):
        before=lane.tool_sha(); real=lane.file_sha256
        for name in ('instruction_observation.py','phase9_instruction_effect_trace.py',
                     'phase9_oracle_instruction_effects.py','phase9_instruction_effect_witnesses.py',
                     'phase9_oracle_effect_witnesses.py','source_build.py','process_guard.py'):
            with self.subTest(name=name),mock.patch.object(lane,'file_sha256',side_effect=lambda p:'0'*64 if p.name==name else real(p)):
                self.assertNotEqual(before,lane.tool_sha())


if __name__=='__main__': unittest.main()
