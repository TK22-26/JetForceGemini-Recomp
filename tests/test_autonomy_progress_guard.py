import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

from scripts.autonomy import progress_guard as guard, supervisor
from scripts.autonomy.job_store import JobSpec, JobStore, SCHEMA_VERSION

PINS = {'source_commit':'a'*40, **{k+'_sha256':'b'*64 for k in ('tool','rom','native','emulator')}}


class ProgressGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve(); self.state = self.repo/'tools/private/state'
        self.store = JobStore(self.state/'jobs.sqlite'); self.addCleanup(self.store.close)

    def job(self,name,parents=(),inputs=('fixture',)):
        self.store.enqueue(JobSpec(name,PINS,inputs,parents,'worker:'+name,2,'json_complete'),now=1)
        return name

    def enable(self,roots=('root',),**options):
        guard.register(self.store,'problem',roots=list(roots),**options); guard.enable(self.store)

    def finish(self,name,*,passed=False,now=10,payload=None):
        lease = self.store.lease_job(name,'test',now=now,ttl=60)
        self.assertIsNotNone(lease)
        self.store.start(name,lease['token'],now=now)
        if passed:
            path = self.state/(name+'.json'); path.write_text(json.dumps(payload or {'complete':True,'progress':True}))
            self.store.verify(name,lease['token'],now=now+1)
            self.store.seal_artifact(name,lease['token'],path,now=now+1)
            self.store.pass_job(name,lease['token'],now=now+2)
        else: self.store.fail_job(name,lease['token'],'synthetic repeated failure',now=now+2)
        return lease

    def grade(self,lease,decision='no-progress',fingerprint=None):
        guard.decide(self.store,lease['token'],{'decision':decision,'fingerprint':fingerprint,'reason':'independent test result'})

    def problem(self): return guard.status(self.store)['problems'][0]

    def review(self):
        self.job('review',inputs=('packet:test',)); self.job('alternative')
        path = self.state/'packets/review.json'; path.parent.mkdir()
        path.write_text(json.dumps({'kind':'diagnose','allowed_paths':[],'max_changed_files':0,'validation':[]}))

    def test_renamed_children_share_budget_and_cannot_self_claim_progress(self):
        self.job('root'); self.job('renamed',('root',)); self.job('again',('renamed',))
        self.enable(limits={**guard.DEFAULT_LIMITS,'max_activity':2})
        for name in ('root','renamed'):
            self.finish(name,passed=True)
            guard.reconcile(self.store,self.repo,self.state)
        self.assertIsNone(self.store.lease_job('again','test',now=20))
        self.assertEqual(self.problem()['state'],'shelved')
        self.assertEqual((self.problem()['attempts'],self.problem()['activity']),(2,2))
        self.assertEqual(self.store.job('again')['attempts'],0)

    def test_failures_across_new_job_ids_count_toward_same_problem(self):
        for name in ('a','b','c'): self.job(name)
        self.enable(roots=('a','b','c'))
        for name in ('a','b'):
            lease = self.finish(name); self.grade(lease)
        self.assertIsNone(self.store.lease_job('c','new-worker',now=20))
        self.assertEqual(self.problem()['no_progress'],2)

    def test_budget_survives_connection_restart_and_immutable_registration(self):
        self.job('root'); self.enable()
        lease = self.finish('root'); self.grade(lease)
        with JobStore(self.store.db_path) as other:
            guard.register(other,'problem',roots=['root'])
            self.assertEqual(guard.status(other)['problems'][0]['attempts'],1)
            with self.assertRaisesRegex(ValueError,'immutable'):
                guard.register(other,'problem',roots=['root'],limits={**guard.DEFAULT_LIMITS,'max_attempts':99})

    def test_new_root_and_cross_problem_dependency_fail_closed(self):
        self.job('root'); self.job('other'); self.job('mixed',('root','other')); self.job('renamed-root')
        self.enable(); guard.register(self.store,'second',roots=['other'])
        self.finish('root',passed=True); guard.reconcile(self.store,self.repo,self.state)
        self.finish('other',passed=True); guard.reconcile(self.store,self.repo,self.state)
        for name in ('mixed','renamed-root'):
            self.assertIsNone(self.store.lease_job(name,'worker',now=20))

    def test_pending_independent_grade_blocks_same_problem_not_other_work(self):
        for name in ('root','second','independent'): self.job(name)
        self.enable(roots=('root','second')); guard.register(self.store,'independent',roots=['independent'])
        lease = self.finish('root',passed=True)
        self.assertIsNone(self.store.lease_job('second','worker',now=20))
        self.assertIsNotNone(self.store.lease_job('independent','worker',now=20))
        self.grade(lease,'activity')
        self.assertIsNotNone(self.store.lease_job('second','worker',now=20))

    def test_unknown_success_is_only_bounded_supporting_activity(self):
        self.job('root'); self.enable()
        self.finish('root',passed=True,payload={'complete':True,'tests_passed':5000,'fixed':True,'progress':True})
        guard.reconcile(self.store,self.repo,self.state)
        self.assertEqual(self.problem()['activity'],1)
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM problem_credits').fetchone()[0],0)

    def test_duplicate_semantic_outcome_does_not_reset_stall_counter(self):
        for name in ('a','b','c','d'): self.job(name)
        self.enable(roots=('a','b','c','d'))
        for name in ('a','b','c'):
            self.grade(self.finish(name,passed=True),'progress','d'*64)
        self.assertEqual(self.problem()['no_progress'],2)
        self.assertEqual(self.problem()['state'],'shelved')
        self.assertIsNone(self.store.lease_job('d','worker',now=30))

    def test_verified_progress_does_not_reset_total_time_or_attempt_budget(self):
        for name in ('a','b','c'): self.job(name)
        self.enable(roots=('a','b','c'),limits={**guard.DEFAULT_LIMITS,'max_attempts':2})
        self.grade(self.finish('a',passed=True),'progress','c'*64)
        self.grade(self.finish('b',passed=True),'progress','d'*64)
        self.assertIsNone(self.store.lease_job('c','worker',now=20))
        self.assertEqual((self.problem()['attempts'],self.problem()['spent']),(2,4))

    def test_frontier_must_beat_high_water_even_with_fresh_baseline_or_fingerprint(self):
        for name in ('a','b','c'): self.job(name)
        self.enable(roots=('a','b','c'))
        for name,value,fingerprint in (('a',2000,'a'),('b',1990,'b'),('c',2000,'c')):
            lease = self.finish(name,passed=True)
            guard.decide(self.store,lease['token'],{'decision':'progress','fingerprint':fingerprint*64,
                'reason':'independent frontier measurement','metric':{'name':'selected-update-prefix','value':value}})
        self.assertEqual(self.problem()['state'],'shelved')
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM problem_credits').fetchone()[0],1)

    def test_deadline_is_cumulative_and_heartbeat_rejects_overrun(self):
        self.job('root'); self.enable(limits={**guard.DEFAULT_LIMITS,'max_seconds':3})
        lease = self.store.lease_job('root','worker',now=10,ttl=60)
        self.store.heartbeat('root',lease['token'],now=12,ttl=60)
        with self.assertRaisesRegex(ValueError,'budget exhausted'):
            self.store.heartbeat('root',lease['token'],now=13,ttl=60)
        self.store.fail_job('root',lease['token'],'budget',now=13)
        self.grade(lease)
        self.store.retry_failed('root',now=14)
        self.assertIsNone(self.store.lease_job('root','worker',now=14))

    def test_expiry_charges_attempt_once_and_preserves_no_progress(self):
        self.job('root'); self.enable()
        lease = self.store.lease_job('root','worker',now=1,ttl=2)
        self.store.reclaim_expired(now=3); self.store.reclaim_expired(now=5)
        guard.reconcile(self.store,self.repo,self.state)
        self.assertEqual((self.problem()['attempts'],self.problem()['spent'],self.problem()['no_progress']),(1,2,1))
        other = self.store.lease_job('root','new-worker',now=6,ttl=2)
        self.assertNotEqual(lease['token'],other['token'])

    def test_one_fresh_review_and_one_alternative_then_durable_shelf(self):
        for name in ('a','b','more'): self.job(name)
        self.review()
        self.enable(roots=('a','b','more'),recovery={'review':'review','alternative':'alternative'})
        self.assertIsNone(self.store.lease_job('review','worker',now=2))
        for name in ('a','b'): self.grade(self.finish(name))
        self.assertEqual(self.problem()['state'],'review-needed')
        self.assertIsNone(self.store.lease_job('more','worker',now=15))
        review = self.finish('review',passed=True); self.grade(review,'review-complete')
        self.assertEqual(self.problem()['state'],'alternative-ready')
        alternative = self.finish('alternative'); self.grade(alternative)
        self.assertEqual(self.problem()['state'],'shelved')
        self.store.retry_failed('alternative',now=30)
        self.assertIsNone(self.store.lease_job('alternative','new-worker',now=30))
        self.assertEqual((self.problem()['reviews'],self.problem()['alternatives']),(1,1))

    def test_failed_review_does_not_open_alternative(self):
        self.job('root'); self.review()
        self.enable(limits={**guard.DEFAULT_LIMITS,'max_no_progress':1},recovery={'review':'review','alternative':'alternative'})
        self.grade(self.finish('root')); self.grade(self.finish('review'))
        self.assertIsNone(self.store.lease_job('alternative','worker',now=20))
        self.assertEqual(self.problem()['state'],'shelved')

    def test_write_capable_or_reused_reviewer_is_not_admitted(self):
        self.job('root'); self.review()
        path = self.state/'packets/review.json'
        payload = json.loads(path.read_text()); payload['kind'] = 'implement'; path.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError,'read-only'):
            self.enable(recovery={'review':'review'})

    def test_live_job_is_not_mistaken_for_stagnation(self):
        self.job('root'); self.job('unregistered'); self.enable()
        self.assertIsNone(self.store.lease_job('unregistered','worker',now=2))
        self.assertTrue(guard.halted(self.store))
        self.store.lease_job('root','worker',now=3)
        self.assertFalse(guard.halted(self.store))

    def test_continuous_service_exits_instead_of_replanning_denied_queue(self):
        from scripts.autonomy.continuous import serve
        self.job('unregistered'); guard.enable(self.store)
        with mock.patch('scripts.autonomy.scheduler.advance_jobs',return_value=[]) as advance, \
                mock.patch('scripts.autonomy.continuous.time.sleep',side_effect=AssertionError('must stop')):
            outcomes = serve(self.repo,self.state,Path('unused'),max_cycles=3,max_agent_attempts_per_utc_day=0)
        self.assertEqual(len(outcomes),1)
        self.assertTrue(outcomes[0].startswith('progress-stopped:'))
        advance.assert_called_once()

    def test_named_denial_reports_reason_without_consuming_an_attempt(self):
        self.job('unregistered'); guard.enable(self.store)
        outcome = supervisor.run_once(self.repo,self.state,Path('unused'),allow_agent=False,job_id='unregistered')
        self.assertIn('unregistered investigation',outcome)
        self.assertEqual(self.store.job('unregistered')['attempts'],0)

    def test_decision_is_idempotent_and_cannot_be_rewritten(self):
        self.job('root'); self.enable(); lease = self.finish('root')
        self.grade(lease); self.grade(lease)
        self.assertEqual(self.problem()['no_progress'],1)
        with self.assertRaisesRegex(ValueError,'immutable'): self.grade(lease,'progress','d'*64)

    def test_production_adapter_requires_checked_candidate_not_self_report(self):
        self.job('root',inputs=('candidate-retest-packet:test',)); self.enable(verifier='candidate-frontier')
        self.finish('root',passed=True)
        with mock.patch('scripts.autonomy.candidate_feedback.checked_outcome',side_effect=ValueError('bad receipts')) as check:
            guard.reconcile(self.store,self.repo,self.state)
            check.assert_called_once()
        self.assertEqual(self.problem()['no_progress'],1)

    def test_production_adapter_recognizes_verified_frontier_gain(self):
        self.job('root',inputs=('candidate-retest-packet:test',)); self.enable(verifier='candidate-frontier')
        self.finish('root',passed=True)
        facts = {'disposition':'retained-for-integration-review','input_prefix_match':True,
                 'raw_frontier':{'classification':'moved-later','candidate_first_raw_mismatch':1909}}
        with mock.patch('scripts.autonomy.candidate_feedback.checked_outcome',return_value=(facts,{},[])):
            guard.reconcile(self.store,self.repo,self.state)
        self.assertEqual(self.store.connection.execute('SELECT count(*) FROM problem_credits').fetchone()[0],1)
        self.assertEqual(self.problem()['activity'],0)

    def test_migrates_v1_without_changing_old_jobs_or_seals(self):
        self.job('root'); self.finish('root',passed=True)
        previous = self.store.job('root')
        # Reconstruct the genuine pre-guard schema, preserving the old job tables.
        self.store.close()
        db = sqlite3.connect(self.state/'jobs.sqlite')
        for name in ('problem_continuations','problem_credits','problem_runs','problem_jobs','investigations','guard_meta','guard_denials'):
            db.execute('DROP TABLE '+name)
        db.execute('PRAGMA user_version=1'); db.commit(); db.close()
        self.store = JobStore(self.state/'jobs.sqlite'); self.addCleanup(self.store.close)
        self.assertEqual(self.store.job('root'),previous)
        self.assertEqual(self.store.connection.execute('PRAGMA user_version').fetchone()[0],SCHEMA_VERSION)
        self.assertFalse(guard.enabled(self.store.connection))


class RealSupervisorTrapTests(unittest.TestCase):
    def test_repetitive_real_workers_are_stopped_and_independent_work_runs(self):
        from test_autonomy_supervisor import SupervisorTests
        from scripts.autonomy.process_guard import real_python_executable
        fixture = SupervisorTests(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        # These are real bounded subprocesses, not a model or a mocked launcher.
        names = ('repeat-1','repeat-2','repeat-3','independent')
        for name in names: fixture.queue(fixture.packet(name))
        with JobStore(fixture.state/'jobs.sqlite') as store:
            guard.register(store,'stalled',roots=list(names[:3]),limits={**guard.DEFAULT_LIMITS,'max_activity':2})
            guard.register(store,'independent',roots=['independent'])
            guard.enable(store)
        outcomes = []
        for _ in range(4):
            outcomes.append(supervisor.run_once(fixture.repo,fixture.state,fixture.fake_agent,
                agent_prefix=[real_python_executable(),str(fixture.fake_agent)],require_auth=False))
        self.assertTrue(outcomes[0].startswith('repeat-1:'))
        self.assertTrue(outcomes[1].startswith('repeat-2:'))
        self.assertTrue(outcomes[2].startswith('independent:'))
        self.assertTrue(outcomes[3].startswith('progress-stopped:'))
        with JobStore(fixture.state/'jobs.sqlite') as store:
            self.assertEqual(store.job('repeat-3')['attempts'],0)
            self.assertEqual(store.job('independent')['state'],'passed')
            self.assertEqual(store.connection.execute('SELECT count(*) FROM problem_credits').fetchone()[0],0)
        self.assertTrue((fixture.state/'investigation-progress.json').is_file())


if __name__ == '__main__': unittest.main()
