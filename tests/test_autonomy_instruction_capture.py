import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import phase9_point_probe as point_probe
from scripts.autonomy import instruction_capture as lane, supervisor
from scripts.autonomy.job_store import JobStore, JobSpec


def finding():
    return {'complete':True,'qualification':{'passed':True},'update':8,'rom_sha256':'2'*64,
            'load_evidence':{'address':0x80001000,'width':8,'snapshots':[
                {'update':7,'equal':False,'precedes_observed_update':True},
                {'update':8,'equal':False,'precedes_observed_update':False}]}}


class SelectionTests(unittest.TestCase):
    def test_predecessor_is_evidence_selected_not_a_causal_claim(self):
        plan = lane.select(finding())
        self.assertEqual((plan['update'],plan['window']),(7,[6,8]))
        self.assertFalse(plan['causal_fix_proved'])
        self.assertFalse(plan['monotonic_memory_assumed'])

    def test_equal_or_later_snapshots_and_unknown_load_require_instrumentation(self):
        for variant in ('equal','later','none'):
            report = finding()
            if variant == 'none': report['load_evidence'] = None
            elif variant == 'equal': report['load_evidence']['snapshots'][0]['equal'] = True
            else: report['load_evidence']['snapshots'][0]['precedes_observed_update'] = False
            self.assertEqual(lane.select(report)['operation'],'needs-instrumentation')

    def test_nonmonotonic_snapshots_do_not_support_binary_search(self):
        report = finding()
        report['load_evidence']['snapshots'].insert(0,{'update':5,'equal':False,'precedes_observed_update':True})
        report['load_evidence']['snapshots'].insert(1,{'update':6,'equal':True,'precedes_observed_update':True})
        self.assertEqual(lane.select(report)['update'],5)

    def test_first_invocation_and_invalid_progress(self):
        report = finding()
        report['load_evidence']['snapshots'][0]['update'] = 1
        self.assertEqual(lane.select(report)['window'],[1,2])
        for n in (0,8,True):
            report['load_evidence']['snapshots'][0]['update'] = n
            with self.assertRaises(ValueError): lane.select(report)
        report['complete'] = False
        with self.assertRaises(ValueError): lane.select(report)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve(); self.state = self.repo/'tools/private/autonomy'
        self.state.mkdir(parents=True)
        self.store = JobStore(self.state/'jobs.sqlite'); self.addCleanup(self.store.close)
        self.rom = self.repo/'owned.z64'; self.rom.write_bytes(b'ROM fixture, not game bytes')
        self.pins = {'source_commit':'1'*40,'native_sha256':'2'*64,'emulator_sha256':'2'*64,
                     'rom_sha256':supervisor.file_sha256(self.rom),'tool_sha256':'3'*64}
        self.store.enqueue(JobSpec('parent',self.pins,('instruction-observation:test',),(),
                                   'analysis:instruction-effects',0,'json_complete'))
        lease = self.store.lease_job('parent','test'); self.store.start('parent',lease['token'])
        self.seal = self.state/'parent-result.json'; self.seal.write_text('{"complete":true}')
        self.store.verify('parent',lease['token']); self.store.seal_artifact('parent',lease['token'],self.seal)
        self.store.pass_job('parent',lease['token'])
        self.report = {**finding(),'rom_sha256':self.pins['rom_sha256']}
        self.recipe = {'native_build':{'path':'native','sha256':'4'*64},
                       'oracle_build':{'path':'oracle','sha256':'5'*64}, 'source_export':'route',
                       'native_target':30,'oracle_target':40,
                       'probe':{'entry_pc':'0x80001000','call_pc':'0x80002000',
                                'pcs':['0x80001000','0x80002008'],
                                'words':['0x800a9e90','0x803ffffc']}}
        lane.observation.validate_probe(self.recipe['probe'])
        self.context = (self.report,{},lane.source_build.pin(self.seal))
        for obj,name,value in ((lane,'tool_sha','3'*64),(lane,'parent_context',self.context),
                               (lane,'recipe',self.recipe)):
            patch = mock.patch.object(obj,name,return_value=value); patch.start(); self.addCleanup(patch.stop)

    def enqueue(self):
        return lane.enqueue(self.store,self.repo,self.state,'parent',self.rom)['job_id']

    def check(self,job_id):
        return lane.checked_packet(self.store,self.repo,self.state,job_id)

    def result(self,job_id):
        packet = self.check(job_id)
        directory = self.state/'attempts'/job_id/'0001'
        request = lane.request_for(packet,directory)
        measured = {'complete':True,'qualification':{'passed':True},'evidence':{},'promoted':False,
                    'source_commit':self.pins['source_commit'],'native_runtime_sha256':self.pins['native_sha256'],
                    'oracle_runtime_sha256':self.pins['emulator_sha256'],'rom_sha256':self.pins['rom_sha256'],
                    **lane.observation.native_effects.LIMITS}
        return {'schema':1,'kind':'instruction-predecessor-capture-result','complete':True,'job_id':job_id,
                'packet_sha256':supervisor.file_sha256(lane.packet_path(self.state,job_id)),
                'parent_result':packet['parent_result'],'request':request,'measurement':measured,
                'parity_verified':False,'promoted':False}

    def child(self,job_id,alter=None):
        def run(argv,repo,stdout,stderr,deadline,heartbeat,paused,**kwargs):
            self.assertEqual(argv[1:3],['-m','scripts.autonomy.instruction_capture'])
            self.assertEqual(kwargs['guard_record'].name,'capture.guard.json')
            self.assertGreater(kwargs['memory_limit_bytes'],0); heartbeat()
            report = self.result(job_id)
            if alter: alter(report)
            (stdout.parent/'result.json').write_bytes(supervisor.canonical_bytes(report))
            return 0,None
        return run

    def execute(self,job_id,alter=None):
        with mock.patch.object(lane,'bounded_command',side_effect=self.child(job_id,alter)), \
                mock.patch.object(lane.observation_job,'inventory',return_value=({},self.pins)), \
                mock.patch.object(supervisor,'require_chatgpt_login',side_effect=AssertionError('no agent')):
            return supervisor.run_once(self.repo,self.state,Path('unused'),allow_agent=False,job_id=job_id)

    def test_packet_is_idempotent_in_queued_running_and_blocked_states(self):
        job_id = self.enqueue(); self.assertEqual(job_id,self.enqueue())
        lease = self.store.lease_job(job_id,'test'); self.store.start(job_id,lease['token'])
        self.assertEqual(job_id,self.enqueue())
        self.store.fail_job(job_id,lease['token'],'test',blocked=True)
        self.assertEqual(job_id,self.enqueue()); self.assertEqual(self.store.job(job_id)['attempts'],1)

    def test_pause_and_unsupported_selection_do_not_queue(self):
        (self.state/'PAUSED').touch()
        self.assertIsNone(lane.enqueue(self.store,self.repo,self.state,'parent',self.rom))
        (self.state/'PAUSED').unlink()
        self.report['load_evidence'] = None
        self.assertEqual(lane.enqueue(self.store,self.repo,self.state,'parent',self.rom)['operation'],'needs-instrumentation')
        self.assertFalse((self.state/'instruction-capture-packets').exists())

    def test_packet_plan_rom_and_tool_changes_are_rejected(self):
        job_id = self.enqueue(); path = lane.packet_path(self.state,job_id)
        original = path.read_bytes(); changed = json.loads(original); changed['plan']['update'] = 4
        path.write_text(json.dumps(changed))
        with self.assertRaises(ValueError): self.check(job_id)
        path.write_bytes(original)
        with mock.patch.object(lane,'tool_sha',return_value='6'*64),self.assertRaises(ValueError): self.check(job_id)
        self.rom.write_bytes(b'changed')
        with self.assertRaises(ValueError): self.check(job_id)

    def test_changed_parent_cannot_supply_another_plan(self):
        job_id = self.enqueue(); self.report['load_evidence']['snapshots'][0]['update'] = 6
        with self.assertRaisesRegex(ValueError,'verified parent'): self.check(job_id)

    def test_guarded_dispatch_seals_and_enqueues_independent_observation(self):
        job_id = self.enqueue(); self.assertIn('sealed',self.execute(job_id))
        self.assertEqual(self.store.job(job_id)['state'],'passed'); self.assertEqual(job_id,self.enqueue())
        with mock.patch.object(lane.observation_job,'inventory',return_value=({},self.pins)), \
                mock.patch.object(lane.observation_job,'queue',return_value='observation') as queue:
            self.assertEqual(lane.next_observation(self.store,self.repo,self.state,job_id),'observation')
            self.assertEqual(queue.call_args.kwargs['prerequisites'],(job_id,))
        self.assertEqual(self.store.job(job_id)['attempts'],1)

    def test_bad_child_is_retained_without_promotion_or_followup(self):
        for key,value in (('complete',False),('promoted',True),('request',{}),('measurement',{})):
            with self.subTest(key=key):
                self.recipe['native_target'] += 1
                job_id = self.enqueue()
                self.assertIn('blocked',self.execute(job_id,lambda r:r.update({key:value})))
                directory = self.state/'attempts'/job_id/'0001'
                self.assertTrue((directory/'result.json').exists()); self.assertTrue((directory/'failure.json').exists())
                self.assertIsNone(lane.next_observation(self.store,self.repo,self.state,job_id))

    def test_emulator_resource_is_exclusive(self):
        job_id = self.enqueue()
        self.store.enqueue(JobSpec('other',self.pins,('test',),(),'emulator:bizhawk',0,'json_complete'))
        self.store.lease_job('other','test')
        self.assertIsNone(self.store.lease_job(job_id,'test'))

    def test_expired_attempt_requires_containment_before_relaunch(self):
        job_id = self.enqueue(); lease = self.store.lease_job(job_id,'test',ttl=1,now=1)
        directory = self.state/'attempts'/job_id/'0001'; directory.mkdir(parents=True)
        self.store.reclaim_expired(now=3)
        lease = self.store.lease_job(job_id,'retry')
        with mock.patch.object(lane,'expired_attempt_contained',return_value=False), \
                mock.patch.object(lane,'bounded_command') as command:
            self.assertIn('may still be alive',lane.run_lease(self.store,lease,self.repo,self.state))
            command.assert_not_called()

    def test_worker_derives_four_runs_and_remeasures_parent_before_launch(self):
        job_id = self.enqueue(); packet = self.check(job_id)
        original_packet = copy.deepcopy(packet)
        packet_bytes = lane.packet_path(self.state,job_id).read_bytes()
        original_recipe = copy.deepcopy(self.recipe)
        receipt = self.state/'build.json'; receipt.write_text(json.dumps({'executable':'game.exe'}))
        directory = self.state/'attempts'/job_id/'0001'
        original_request = copy.deepcopy(lane.request_for(packet,directory))
        with mock.patch.object(lane,'checked_packet',return_value=packet) as checked, \
                mock.patch.object(lane.source_build,'pinned_file',return_value=receipt), \
                mock.patch.object(lane.source_build,'validate'), mock.patch.object(lane.observation,'oracle_build'), \
                mock.patch.object(lane.observation,'measure',return_value={'measured':True}) as measure, \
                mock.patch.object(lane.shutil,'disk_usage',return_value=mock.Mock(free=8*1024**3)), \
                mock.patch('scripts.phase95_native_replay.replay') as native, \
                mock.patch('scripts.phase95_oracle_replay.replay') as oracle:
            result = lane.capture_worker(self.store,self.repo,self.state,job_id,directory)
        self.assertTrue(checked.call_args_list[0].kwargs['remeasure'])
        self.assertEqual(native.call_count,2); self.assertEqual(oracle.call_count,2)
        for side,adapter in (('native',native),('oracle',oracle)):
            self.assertIsNone(adapter.call_args_list[0].kwargs['instruction_effect_update'])
            self.assertEqual(adapter.call_args_list[1].kwargs['instruction_effect_update'],7)
            self.assertEqual(adapter.call_args_list[1].kwargs['focus_updates'],[6,8])
            for call in adapter.call_args_list:
                args = call.kwargs
                with self.subTest(side=side, instruction_effect_update=args['instruction_effect_update']):
                    enabled = (args['execution_profile'] == 'original-os-probe' if side == 'native'
                               else args['vi_trace'])
                    pcs,words = point_probe.validate(args['point_pcs'],args['point_words'],
                                                     args['focus_updates'],enabled)
                    self.assertEqual(pcs,(0x80001000,0x80002008))
                    self.assertEqual(words,(0x800a9e90,0x803ffffc))
        self.assertEqual(native.call_args.kwargs['execution_profile'],'original-os-probe')
        self.assertEqual(oracle.call_args.kwargs['cpu_boundary_update'],7)
        self.assertEqual(result['measurement'],{'measured':True})
        measure.assert_called_once_with(self.repo,original_request)
        self.assertEqual(result['request'],original_request)
        self.assertEqual(packet,original_packet)
        self.assertEqual(self.recipe,original_recipe)
        self.assertEqual(lane.packet_path(self.state,job_id).read_bytes(),packet_bytes)

    def test_request_probe_rejects_malformed_out_of_range_and_unaligned_addresses(self):
        packet = {'recipe':self.recipe,'plan':lane.select(self.report)}
        request = lane.request_for(packet,self.state/'capture')
        for key in ('pcs','words'):
            for invalid in (0x80001000,True,'80001000','0x8000100g','0x800A9E90',
                            ' 0x80001000','0x7ffffffc','0x80400000','0x80001001'):
                altered = copy.deepcopy(request)
                altered['probe'][key].append(invalid)
                with self.subTest(key=key,invalid=invalid), \
                        mock.patch.object(lane.observation,'private_directory') as directory, \
                        mock.patch.object(lane.source_build,'pinned_file') as pinned:
                    with self.assertRaisesRegex(ValueError,'canonical KSEG0 strings|unique aligned KSEG0'):
                        lane.observation.validate_request(self.repo,altered)
                    directory.assert_not_called(); pinned.assert_not_called()

    def test_complete_expired_attempt_is_recovered_without_new_capture(self):
        job_id = self.enqueue()
        lease = self.store.lease_job(job_id,'old',ttl=1,now=1)
        directory = self.state/'attempts'/job_id/'0001'; directory.mkdir(parents=True)
        (directory/'result.json').write_bytes(supervisor.canonical_bytes(self.result(job_id)))
        self.store.reclaim_expired(now=3)
        lease = self.store.lease_job(job_id,'retry')
        with mock.patch.object(lane,'expired_attempt_contained',return_value=True), \
                mock.patch.object(lane.observation_job,'inventory',return_value=({},self.pins)), \
                mock.patch.object(lane,'bounded_command') as command:
            self.assertIn('recovered',lane.run_lease(self.store,lease,self.repo,self.state))
            command.assert_not_called()
        self.assertEqual(self.store.job(job_id)['state'],'passed')
        self.assertEqual(Path(self.store.job(job_id)['sealed_artifact']).parent,directory)

    def test_cycle_reuses_passed_jobs_and_does_not_drain_backlog(self):
        job_id = self.enqueue(); self.execute(job_id)
        with mock.patch.object(lane,'next_observation',return_value='parent'), \
                mock.patch.object(supervisor,'run_once',side_effect=AssertionError('no new worker')):
            result = lane.cycle(self.repo,self.state,'parent',self.rom,1)
        self.assertEqual(result['state'],'step-budget-complete')
        self.assertEqual(result['parent_id'],'parent')

    def test_packet_path_and_step_limits(self):
        for value in ('../bad','a/b','',None):
            with self.assertRaises(ValueError): lane.packet_path(self.state,value)
        for n in (0,9,True):
            with self.assertRaises(ValueError): lane.cycle(self.repo,self.state,'parent',self.rom,n)

    def test_producer_closure_includes_capture_and_all_observation_tools(self):
        root = Path(__file__).resolve().parents[1]
        self.assertTrue(all((root/path).is_file() for path in lane.EXTRA_TOOLS))
        self.assertEqual(len(lane.tool_sha()),64)


if __name__ == '__main__': unittest.main()
