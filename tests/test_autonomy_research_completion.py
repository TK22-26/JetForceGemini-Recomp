import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts.autonomy import research_completion as completion, experiment_feedback as feedback
from scripts.autonomy.job_store import JobSpec, JobStore
from scripts.autonomy.supervisor import (
    canonical_bytes, enqueue_packet, read_packet, run_once, recover_complete_result,
    BOUNDED_DIAGNOSIS_SCHEMA_FILE,
)


class ResearchCompletionTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.repo=Path(temporary.name); self.state=self.repo/'tools/private/autonomy'; self.state.mkdir(parents=True)
        for args in (("init","-q"),("config","user.name","Test"),("config","user.email","test@example.com"),
                     ("commit","--allow-empty","-qm","fixture")):
            subprocess.run(["git","-C",str(self.repo),*args],check=True,capture_output=True)
        self.commit=subprocess.check_output(["git","-C",str(self.repo),"rev-parse","HEAD"],text=True).strip()
        self.agent=self.repo/'agent.py'
        self.agent.write_text(
            "import json,pathlib,sys\n"
            "sys.stdin.read()\n"
            "answer={'classification':'insufficient_evidence','alignment':'unvalidated','first_supported_retrace':None,"
            "'evidence':['fixture measurement'],'hypothesis':'two explanations','next_test':'bounded new observation','confidence':'low'}\n"
            "pathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(answer))\n"
            "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(answer)}}))\n"
            "print(json.dumps({'type':'turn.completed'}))\n")
        self.store=JobStore(self.state/'jobs.sqlite'); self.addCleanup(self.store.close)
        self.observed='point-observe-fixture'; self.failed=feedback.feedback_id(self.observed)
        self.packet={"schema":1,"job_id":self.failed,"kind":"diagnose","source_commit":self.commit,
            "pin_files":{key:str(self.agent) for key in ('rom','native','emulator')},"prompt":"investigate",
            "timeout_seconds":30,"validation":[],"prerequisites":["retest","baseline",self.observed],
            "retry_budget":0,"allowed_paths":[],"max_changed_files":0,"evidence_files":[]}
        pins={"source_commit":self.commit,**{key:'0'*64 for key in ('tool_sha256','rom_sha256','emulator_sha256','native_sha256')}}
        for name in self.packet['prerequisites']:
            self.store.enqueue(JobSpec(name,pins,('fixture',),(),'fixture',0,'json_complete'),now=1)
            lease=self.store.lease_job(name,'fixture',now=1,ttl=1000); self.store.start(name,lease['token'],now=1)
            path=self.write('artifacts/'+name+'.json',{'complete':True})
            self.store.verify(name,lease['token'],now=1); self.store.seal_artifact(name,lease['token'],path,now=1)
            self.store.pass_job(name,lease['token'],now=1)
        enqueue_packet(self.store,self.state,self.packet,self.agent)
        lease=self.store.lease_job(self.failed,'fixture',now=1,ttl=1000); self.store.start(self.failed,lease['token'],now=1)
        self.store.fail_job(self.failed,lease['token'],'timeout',blocked=True,now=32)
        self.directory=self.state/'attempts'/self.failed/'0001'
        self.failure_path=self.write(f'attempts/{self.failed}/0001/result.json',
            {'complete':False,'job_id':self.failed,'attempt':1,'stop_reason':'timeout'})
        self.write(f'attempts/{self.failed}/0001/agent.guard.json',{'schema':1,'state':'finished','owner_pid':123,'child_pid':456})
        self.log=self.directory/'agent.jsonl'
        self.log.write_text(json.dumps({'type':'item.completed','item':{'id':'read1','type':'command_execution',
            'command':'read source','aggregated_output':'retained observations','exit_code':0,'status':'completed'}})+'\n')
        self.context={'observation_id':self.observed,'retest_id':'retest','baseline_id':'baseline',
            'baseline_packet':self.packet,'history':[],'observation_seal':self.state/'artifacts'/(self.observed+'.json'),
            'plan':{'prediction':{'kind':'event-count','update':7}},
            'observation':{'prediction_observed':True,'qualification':{'passed':True},
                           'observations':[{'update':7,'native':4,'oracle':5,'equal':False}]}}
        for target,kwargs in (("expired_attempt_contained",{'return_value':True}),
                              ("_git_ok",{'side_effect':lambda path,*args:self.commit if args[0]=='rev-parse' else ''})):
            patcher=patch.object(completion,target,**kwargs); patcher.start(); self.addCleanup(patcher.stop)
        patcher=patch.object(completion.words,'checked_observation',return_value=self.context)
        patcher.start(); self.addCleanup(patcher.stop)

    def write(self,relative,payload):
        path=self.state/relative; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(canonical_bytes(payload)); return path

    def queue(self):
        return completion.queue(self.store,self.repo,self.state,self.agent,self.observed)

    def test_bounded_successor_retains_failure_without_failed_prerequisite(self):
        before=self.failure_path.read_bytes(); job_id=self.queue()
        packet=read_packet(self.state/'packets'/(job_id+'.json'),self.repo)
        self.assertEqual(packet['timeout_seconds'],180); self.assertEqual(packet['retry_budget'],0)
        self.assertEqual(packet['prerequisites'],self.packet['prerequisites'])
        self.assertNotIn(self.failed,packet['prerequisites']); self.assertEqual(packet['allowed_paths'],[])
        self.assertEqual(self.failure_path.read_bytes(),before); self.assertEqual(self.store.job(self.failed)['state'],'blocked')
        self.assertLess(len(packet['prompt']),20000)
        self.assertIn('Do not call any tools',packet['prompt'])
        self.assertEqual(completion.successor(self.store,self.repo,self.state,self.agent,self.observed),job_id)
        self.assertIsNone(self.queue())

    def test_changed_retained_transcript_invalidates_successor(self):
        job_id=self.queue(); self.log.write_text(self.log.read_text()+'changed\n')
        with self.assertRaisesRegex(ValueError,'evidence changed'):
            read_packet(self.state/'packets'/(job_id+'.json'),self.repo)

    def test_verified_probe_and_registered_calibration_are_not_dropped(self):
        self.context['plan']['probe']={'entry_pc':'0x80000200','call_pc':'0x80000100'}
        self.context['capture']={'capture_result':{'input_prefix_match':True}}
        calibration=self.write('calibration.json',{'qualification':{'passed':True,'reasons':[]},
            'summaries':{'native':[{'update':7,'queue_valid_at_entry':2,'receives':['omitted full history']}],
                         'oracle':[{'update':7,'queue_valid_at_entry':3}]}})
        self.context['point_runtime']={'record':{'calibration':completion.words.pin(calibration)}}
        job_id=self.queue(); packet=read_packet(self.state/'packets'/(job_id+'.json'),self.repo)
        checkpoint=json.loads(Path(packet['research_completion']['checkpoint']['path']).read_text())
        summaries=checkpoint['measured_summary']
        self.assertEqual(summaries[0]['probe'],self.context['plan']['probe'])
        self.assertTrue(summaries[0]['input_prefix_match'])
        self.assertEqual(summaries[1]['measurements']['oracle'][0]['queue_valid_at_entry'],3)
        self.assertNotIn('receives',summaries[1]['measurements']['native'][0])
        self.assertIn(completion.words.pin(calibration),checkpoint['evidence'])
        calibration.write_text('{}')
        with self.assertRaisesRegex(ValueError,'evidence changed'):
            read_packet(self.state/'packets'/(job_id+'.json'),self.repo)

    def test_stale_calibration_binding_is_not_presented_as_measurement(self):
        calibration=self.write('calibration.json',{'qualification':{'passed':True}})
        self.context['point_runtime']={'record':{'calibration':completion.words.pin(calibration)}}
        calibration.write_text('{}')
        with self.assertRaisesRegex(ValueError,'calibration changed'):
            self.queue()

    def test_real_worker_seals_tool_free_result_and_recovery_rechecks_transcript(self):
        job_id=self.queue()
        message=run_once(self.repo,self.state,self.agent,agent_prefix=[sys.executable,str(self.agent)],
                         require_auth=False,job_id=job_id)
        self.assertEqual(message,job_id+': candidate sealed')
        directory=self.state/'attempts'/job_id/'0001'
        result=json.loads((directory/'result.json').read_text())
        self.assertTrue(result['complete']); self.assertEqual(result['changed_paths'],[])
        self.assertEqual(result['research_completion_trace_sha256'],completion.file_sha256(directory/'agent.jsonl'))
        packet=read_packet(self.state/'packets'/(job_id+'.json'),self.repo)
        lease={'job_id':job_id,'token':'mock-only','spec':self.store.job(job_id)['spec']}
        options={'comparison':False,'expected_validation':[],'diagnose':True,
                 'expected_diagnosis_schema':BOUNDED_DIAGNOSIS_SCHEMA_FILE,'diagnosis_packet':packet}
        self.assertTrue(recover_complete_result(MagicMock(),lease,directory,**options))
        with (directory/'agent.jsonl').open('a') as stream:
            stream.write('{"type":"item.started","item":{"type":"command_execution"}}\n')
        with self.assertRaisesRegex(ValueError,'tool'):
            recover_complete_result(MagicMock(),lease,directory,**options)

    def test_pause_uncontained_and_finished_output_do_not_launch(self):
        (self.state/'PAUSED').touch(); self.assertIsNone(self.queue()); (self.state/'PAUSED').unlink()
        with patch.object(completion,'expired_attempt_contained',return_value=False):
            self.assertIsNone(self.queue())
        (self.directory/'last-message.txt').write_text('existing output')
        self.assertIsNone(self.queue())

    def test_non_timeout_failure_does_not_get_extra_attempt(self):
        self.failure_path.write_text(json.dumps({'complete':False,'job_id':self.failed,'stop_reason':'read-only agent changed files'}))
        self.assertIsNone(self.queue())

    def test_dirty_source_refuses_checkpoint(self):
        with patch.object(completion,'_git_ok',side_effect=[self.commit,' M file']):
            with self.assertRaisesRegex(ValueError,'worktree changed'):
                self.queue()

    def test_count_ledger_is_retained_in_real_checkpoint_and_prompt(self):
        self.context['plan'].update(operation='oracle-count-ledger', prediction=None)
        ledger = {'first_device_sequence_inclusive':1644,'last_device_sequence_exclusive':1689,
            'start':{'sequence':1644,'pc':0x8009693c,'clock_raw':3637192372},
            'end':{'sequence':1689,'pc':0x80054fbc,'clock_raw':3637811104},
            'cpu_events':33716,'count_events':33712,'eret_events':4,
            'mutations_by_reason':{'lazy':{'events':33712,'modular_delta':618732}},
            'net_count_change_u32':618732,'contains_count_write_or_reset':False,
            'elapsed_or_retired_ticks_proved':False,'pc_mutation_counts':['omitted detail'],
            'eret_boundaries':['omitted detail']}
        self.context['observation'].update(prediction_observed=None, clock_alignment_validated=False,
            retirement_validated=False, observations=[{'update':1908,'device_events_reconciled':677,
                                                      'oracle_count_ledger':ledger}])
        job_id=self.queue(); packet=read_packet(self.state/'packets'/(job_id+'.json'),self.repo)
        checkpoint=json.loads(Path(packet['research_completion']['checkpoint']['path']).read_text())
        row=checkpoint['measured_summary'][0]
        self.assertEqual(row['measurements'][0]['device_events_reconciled'],677)
        measured=row['measurements'][0]['oracle_count_ledger']
        self.assertEqual(measured['count_events'],33712)
        self.assertEqual(measured['net_count_change_u32'],618732)
        self.assertEqual(measured['start'],ledger['start'])
        self.assertFalse(row['limits']['retirement_validated'])
        self.assertNotIn('pc_mutation_counts',measured)
        self.assertIn('omitted, not evidence of absence',row['projection_scope'])
        self.assertIn('618732',packet['prompt']); self.assertLess(len(packet['prompt']),20000)

    def test_device_projection_bounds_raw_events_without_losing_fixed_boundaries(self):
        side={'first_sequence_exclusive':1644,'last_sequence_exclusive':1689,
              'phase_source_counts':{'dispatch:vi':1},'events':['raw detail']*10000,
              'start_context':{'pc':0x8009693c,'r31_hi':0xffffffff,'r1_lo':123},
              'end_context':{'pc':0x80054fbc,'device_sequence':1689}}
        self.context['plan'].update(operation='device-events',prediction=None)
        self.context['observation'].update(clock_alignment_validated=False,
            observations=[{'update':1908,'native':side,'oracle':side}])
        row=completion.measured_summary([self.context])[0]
        self.assertEqual(row['measurements'][0]['oracle']['first_sequence_exclusive'],1644)
        self.assertEqual(row['measurements'][0]['native']['start_context']['r31_hi'],0xffffffff)
        self.assertNotIn('events',row['measurements'][0]['native'])
        self.assertNotIn('r1_lo',row['measurements'][0]['native']['start_context'])
        self.assertFalse(row['limits']['clock_alignment_validated'])
        self.assertLess(len(json.dumps(row)),2000)

    def test_prompt_shrinks_only_research_excerpt_not_verified_history(self):
        checkpoint={'measured_summary':[{'measurement':'m'*15000,'retirement_validated':False}],
            'receipts':[{'id':'read1','command':'c'*700,'output_excerpt':'e'*1800,
                'output_chars':9000,'command_sha256':'1'*64,'output_sha256':'2'*64,
                'exit_code':0,'status':'completed','excerpt_truncated':True}]}
        before=json.dumps(checkpoint,sort_keys=True)
        prompt=completion.prompt_for(checkpoint)
        self.assertLess(len(prompt),18500)
        self.assertIn('m'*15000,prompt)
        self.assertIn('"prompt_excerpt_truncated":true',prompt)
        self.assertIn('"output_chars":9000',prompt)
        self.assertIn('"output_sha256":"'+'2'*64+'"',prompt)
        self.assertEqual(json.dumps(checkpoint,sort_keys=True),before)

    def test_interrupted_enqueue_reuses_exact_checkpoint(self):
        with patch.object(completion,'enqueue_packet',side_effect=RuntimeError('interrupted')):
            with self.assertRaises(RuntimeError): self.queue()
        path=self.state/'research-completions'/(self.failed+'.json'); before=path.read_bytes()
        self.assertIsNotNone(self.queue()); self.assertEqual(path.read_bytes(),before)

    def test_torn_tail_is_not_a_completed_read_and_bad_middle_is_rejected(self):
        original=self.log.read_text(); self.log.write_text(original+'{"type":')
        self.assertEqual(len(completion.receipts(self.log)),1)
        self.log.write_text('{malformed}\n'+original)
        with self.assertRaisesRegex(ValueError,'malformed'): completion.receipts(self.log)

    def test_completed_turn_or_duplicate_receipt_is_not_salvaged(self):
        original=self.log.read_text(); self.log.write_text(original+original)
        with self.assertRaisesRegex(ValueError,'duplicated'): completion.receipts(self.log)
        self.log.write_text(original+'{"type":"turn.completed"}\n')
        with self.assertRaisesRegex(ValueError,'completed research'): completion.receipts(self.log)

    def test_prompt_budget_omits_excerpts_explicitly_without_losing_raw_pin(self):
        self.queue(); path=self.state/'research-completions'/(self.failed+'.json'); data=json.loads(path.read_text())
        receipt=data['receipts'][0]; receipt['output_excerpt']='x'*1800
        data['receipts']=[dict(receipt,id=str(i)) for i in range(128)]
        prompt=completion.prompt_for(data)
        self.assertLess(len(prompt),20000); self.assertIn('of 128 command receipts',prompt)

    def test_tool_free_output_is_checked_on_sealing_and_consumption(self):
        packet={'research_completion':{}}
        diagnosis={'alignment':'unvalidated','classification':'insufficient_evidence','first_supported_retrace':None}
        self.log.write_text('{"type":"item.completed","item":{"type":"agent_message"}}\n{"type":"turn.completed"}\n')
        digest=completion.validate_output(packet,self.directory,diagnosis)
        completion.validate_output(packet,self.directory,diagnosis,{'research_completion_trace_sha256':digest})
        with self.assertRaisesRegex(ValueError,'transcript changed'):
            completion.validate_output(packet,self.directory,diagnosis,{'research_completion_trace_sha256':'0'*64})
        for kind in ('command_execution','mcp_tool_call','web_search','file_change','unknown'):
            self.log.write_text(json.dumps({'type':'item.started','item':{'type':kind}})+'\n{"type":"turn.completed"}\n')
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'tool'):
                completion.validate_output(packet,self.directory,diagnosis)

    def test_output_cannot_claim_alignment_or_finish_without_completed_turn(self):
        packet={'research_completion':{}}
        diagnosis={'alignment':'unvalidated','classification':'insufficient_evidence','first_supported_retrace':None}
        self.log.write_text('{"type":"turn.completed"}\n')
        for key,value in (('alignment','validated'),('classification','code_divergence'),('first_supported_retrace',7)):
            with self.assertRaisesRegex(ValueError,'certainty'):
                completion.validate_output(packet,self.directory,dict(diagnosis,**{key:value}))
        self.log.write_text('{"type":"turn.started"}\n')
        with self.assertRaisesRegex(ValueError,'no completed turn'):
            completion.validate_output(packet,self.directory,diagnosis)


if __name__=='__main__':
    unittest.main()
