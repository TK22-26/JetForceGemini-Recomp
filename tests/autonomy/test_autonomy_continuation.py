"""Trusted continuation admission uses only fresh, synthetic fixture ledgers."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from scripts.autonomy import progress_guard as guard, supervisor
from scripts.autonomy.job_store import JobSpec, JobStore, SCHEMA_VERSION


PINS = {'source_commit': 'a'*40,
        **{k+'_sha256': 'b'*64 for k in ('tool', 'rom', 'native', 'emulator')}}
OLD_TABLES = ('jobs', 'attempts', 'resource_locks', 'guard_meta', 'investigations',
              'problem_jobs', 'problem_runs', 'problem_credits', 'guard_denials')


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='c')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.store = JobStore(self.root/'j.sqlite')
        self.addCleanup(self.store.close)

    def job(self, name, parents=(), resource=None):
        self.store.enqueue(JobSpec(name, PINS, ('synthetic-fixture',), parents,
                                   resource or 'w:'+name, 0, 'json_complete'), now=1)

    def finish(self, name, *, passed=False, blocked=False, now=10, grade=True):
        lease = self.store.lease_job(name, 'fixture', now=now, ttl=60)
        self.assertIsNotNone(lease)
        self.store.start(name, lease['token'], now=now)
        if passed:
            artifact = self.root/(name+'.json')
            artifact.write_text('{"complete":true}', encoding='utf-8')
            self.store.verify(name, lease['token'], now=now+1)
            self.store.seal_artifact(name, lease['token'], artifact, now=now+2)
            self.store.pass_job(name, lease['token'], now=now+3)
        else:
            self.store.fail_job(name, lease['token'], 'synthetic failure',
                                blocked=blocked, now=now+3)
        if grade:
            guard.decide(self.store, lease['token'], {
                'decision': 'activity' if passed else 'no-progress',
                'fingerprint': None, 'reason': 'independent fixture grade'})
        return lease

    def ready(self, *, limits=None, blocked=False):
        self.job('a'); self.job('b')
        guard.register(self.store, 'p', roots=['a'], limits=limits)
        guard.enable(self.store)
        return self.finish('a', blocked=blocked)

    def admit(self, predecessor='a', child='b', **kwargs):
        return guard.admit_continuation(self.store, 'p', predecessor_job_id=predecessor,
            job_id=child, reason=kwargs.pop('reason', 'Follow the failed fixture observation'),
            now=kwargs.pop('now', 20), **kwargs)

    def rows(self, table):
        return [dict(r) for r in self.store.connection.execute('SELECT * FROM '+table+' ORDER BY 1')]

    def snapshot(self):
        return {t: self.rows(t) for t in (*OLD_TABLES, 'problem_continuations')}

    def denied(self, **kwargs):
        before = self.snapshot()
        with self.assertRaises(ValueError): self.admit(**kwargs)
        self.assertEqual(self.snapshot(), before)

    def test_success_after_zero_retry_failure_preserves_history_and_inherits(self):
        lease = self.ready()
        original = self.snapshot()
        self.assertIsNone(self.store.lease_job('b', 'fixture', now=15))
        receipt = self.admit()
        self.assertEqual(receipt['predecessor_token'], lease['token'])
        self.assertEqual(receipt['admitted_at'], 20)
        for table in ('jobs', 'attempts', 'investigations', 'problem_runs', 'problem_credits', 'guard_meta'):
            self.assertEqual(self.rows(table), original[table])
        self.assertEqual(self.store.job('a')['state'], 'failed')
        with self.assertRaisesRegex(ValueError, 'retryable'): self.store.retry_failed('a')
        with self.assertRaisesRegex(ValueError, 'immutable'):
            guard.register(self.store, 'p', roots=['a', 'b'])
        self.finish('b', passed=True, now=30)
        self.job('c', ('b',))
        self.finish('c', passed=True, now=40)
        p = self.rows('investigations')[0]
        self.assertEqual((p['attempts'], p['spent'], p['no_progress'], p['activity']), (3, 9, 1, 2))
        self.assertEqual(guard.membership(self.store.connection, 'c')['problem_id'], 'p')
        self.assertEqual(self.rows('problem_credits'), [])

    def test_blocked_predecessor_and_remaining_deadline_heartbeat(self):
        self.ready(blocked=True, limits={**guard.DEFAULT_LIMITS, 'max_seconds': 10})
        self.admit()
        lease = self.store.lease_job('b', 'fixture', now=30, ttl=60)
        run = self.store.connection.execute('SELECT * FROM problem_runs WHERE token=?', (lease['token'],)).fetchone()
        self.assertEqual(run['deadline'], 37)  # 10 total minus 3 already spent.
        self.store.heartbeat('b', lease['token'], now=36)
        with self.assertRaisesRegex(ValueError, 'budget exhausted'):
            self.store.heartbeat('b', lease['token'], now=37)

    def test_second_failure_shelves_and_restart_cannot_continue(self):
        self.ready(); self.admit(); self.finish('b', now=30)
        self.job('c')
        self.assertEqual(self.rows('investigations')[0]['state'], 'shelved')
        self.denied(predecessor='b', child='c', now=40)
        self.denied(now=40)  # Even a replay cannot reopen a shelved investigation.
        with JobStore(self.store.db_path) as restarted:
            with self.assertRaises(ValueError):
                guard.admit_continuation(restarted, 'p', predecessor_job_id='b',
                    job_id='c', reason='No new allowance', now=40)
            self.assertIsNone(restarted.lease_job('c', 'fixture', now=40))
            self.assertEqual(restarted.job('c')['attempts'], 0)
            self.assertTrue(guard.enabled(restarted.connection))

    def test_restart_idempotence_conflicting_reason_and_duplicate_fork(self):
        self.ready(); receipt = self.admit(); before = self.snapshot()
        with JobStore(self.store.db_path) as restarted:
            replay = guard.admit_continuation(restarted, 'p', predecessor_job_id='a',
                job_id='b', reason=receipt['reason'], now=25)
            self.assertEqual(replay, receipt)
        self.assertEqual(self.snapshot(), before)
        self.denied(reason='Rewrite the reason')
        self.job('c'); self.denied(child='c')

    def test_child_cannot_be_reassigned_to_another_predecessor(self):
        for name in ('a', 'b', 'c'): self.job(name)
        guard.register(self.store, 'p', roots=['a', 'c'],
                       limits={**guard.DEFAULT_LIMITS, 'max_no_progress': 3})
        guard.enable(self.store)
        self.finish('a'); self.admit(); self.finish('c', now=30)
        self.denied(predecessor='c', now=40)

    def test_malformed_requests_are_atomic(self):
        self.ready()
        for reason in ('', ' ', ' trailing ', 'x\ny', 'x\x00y', 'x'*501, None, 7):
            with self.subTest(reason=repr(reason)): self.denied(reason=reason)
        for now in (float('nan'), float('inf'), -1, True, '20', 12):
            with self.subTest(now=now): self.denied(now=now)
        self.denied(predecessor='missing'); self.denied(child='missing')
        self.denied(child='a'); self.denied(child='../b')
        with self.assertRaises(ValueError):
            guard.admit_continuation(self.store, 'missing', predecessor_job_id='a', job_id='b', reason='Fixture')

    def test_all_active_allowances_must_remain(self):
        self.ready()
        for column, limit in (('attempts', 'max_attempts'), ('spent', 'max_seconds'),
                              ('no_progress', 'max_no_progress'), ('activity', 'max_activity')):
            original = self.rows('investigations')[0][column]
            # Simulate a restored active ledger at a limit, without relying on state transitions.
            self.store.connection.execute('UPDATE investigations SET '+column+'=?', (guard.DEFAULT_LIMITS[limit],))
            with self.subTest(column=column): self.denied()
            self.store.connection.execute('UPDATE investigations SET '+column+'=?', (original,))

    def test_disabled_and_recovery_states_deny_even_replays(self):
        self.ready(); self.admit()
        self.store.connection.execute("UPDATE guard_meta SET value='0' WHERE key='enabled'")
        self.denied()
        self.store.connection.execute("UPDATE guard_meta SET value='1' WHERE key='enabled'")
        for state in ('review-needed', 'review-running', 'alternative-ready', 'alternative-running', 'shelved'):
            self.store.connection.execute('UPDATE investigations SET state=?', (state,))
            with self.subTest(state=state): self.denied()

    def test_passed_live_ungraded_and_non_work_predecessors_deny(self):
        self.job('a'); self.job('b')
        guard.register(self.store, 'p', roots=['a']); guard.enable(self.store)
        self.denied()  # Queued, never attempted.
        lease = self.store.lease_job('a', 'fixture', now=10)
        self.denied()
        self.store.fail_job('a', lease['token'], 'fixture', now=13)
        self.denied()
        guard.decide(self.store, lease['token'], {'decision': 'no-progress', 'fingerprint': None, 'reason': 'Fixture grade'})
        for role in ('review', 'alternative'):
            self.store.connection.execute('UPDATE problem_jobs SET role=? WHERE job_id=?', (role, 'a'))
            self.denied()
        self.store.connection.execute("UPDATE problem_jobs SET role='work' WHERE job_id='a'")
        self.store.connection.execute("UPDATE jobs SET state='passed' WHERE job_id='a'")
        self.denied()

    def test_other_live_or_ungraded_attempt_serializes_admission(self):
        for name in ('a', 'b', 'c'): self.job(name)
        guard.register(self.store, 'p', roots=['a', 'c']); guard.enable(self.store)
        self.finish('a')
        lease = self.store.lease_job('c', 'fixture', now=15)
        self.denied()
        self.store.fail_job('c', lease['token'], 'fixture', now=18)
        self.denied()

    def test_latest_attempt_must_have_its_own_completed_grade(self):
        self.ready()
        # Missing/corrupt historical metadata must not borrow an earlier grade.
        self.store.connection.execute("UPDATE jobs SET attempts=2 WHERE job_id='a'")
        self.denied()
        self.store.connection.execute("UPDATE jobs SET attempts=1 WHERE job_id='a'")
        self.store.connection.execute('DELETE FROM problem_runs')
        self.denied()

    def test_cross_problem_and_mixed_unregistered_dependency_ancestry(self):
        self.ready(); self.job('x'); self.job('y'); self.job('z', ('x',))
        guard.register(self.store, 'q', roots=['y'])
        self.job('mix', ('a', 'y')); self.job('ind', ('z',)); self.job('unk', ('missing',))
        self.job('cross', ('y',)); self.job('bad', ('x',))
        for child in ('mix', 'ind', 'unk', 'cross', 'bad', 'y'):
            with self.subTest(child=child): self.denied(child=child)
        with self.assertRaises(ValueError):
            guard.admit_continuation(self.store, 'q', predecessor_job_id='a', job_id='b', reason='Cross problem', now=20)

    def test_assigned_dependency_does_not_hide_unregistered_ancestor(self):
        self.job('x'); self.job('d', ('x',)); self.job('a'); self.job('b', ('d',))
        guard.register(self.store, 'p', roots=['a', 'd']); guard.enable(self.store)
        self.finish('a'); self.denied()

    def test_ordinary_failed_prerequisites_remain_blocking(self):
        self.ready(); self.job('c', ('a',))
        self.admit(child='c')
        self.assertIsNone(self.store.lease_job('c', 'fixture', now=30))
        self.assertEqual(self.store.job('c')['attempts'], 0)
        self.assertEqual(self.store.job('a')['state'], 'failed')

    def test_same_problem_success_dependencies_and_resource_lock_still_apply(self):
        self.job('a'); self.job('d'); self.job('b', ('d',), resource='shared')
        self.job('x', resource='shared')
        guard.register(self.store, 'p', roots=['a', 'd'])
        guard.register(self.store, 'q', roots=['x']); guard.enable(self.store)
        self.finish('a'); self.admit()
        self.assertIsNone(self.store.lease_job('b', 'fixture', now=21))
        self.finish('d', passed=True, now=22)
        lock = self.store.lease_job('x', 'fixture', now=26)
        self.assertIsNone(self.store.lease_job('b', 'fixture', now=27))
        self.store.fail_job('x', lock['token'], 'fixture', now=28)
        self.assertIsNotNone(self.store.lease_job('b', 'fixture', now=29))

    def test_used_child_is_rejected_even_if_manually_requeued(self):
        self.job('b'); self.finish('b', now=2, grade=False)  # Before guard enabling.
        self.job('a'); guard.register(self.store, 'p', roots=['a']); guard.enable(self.store)
        self.finish('a'); self.denied()
        self.store.connection.execute("UPDATE jobs SET state='queued',attempts=0 WHERE job_id='b'")
        self.denied()

    def test_concurrent_fork_has_exactly_one_atomic_winner(self):
        self.ready(); self.job('c')
        barrier = threading.Barrier(2)
        def admit(child):
            with JobStore(self.store.db_path) as store:
                barrier.wait(timeout=10)
                try:
                    return guard.admit_continuation(store, 'p', predecessor_job_id='a',
                        job_id=child, reason='Concurrent fixture', now=20)
                except ValueError: return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(admit, ('b', 'c')))
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(len(self.rows('problem_continuations')), 1)
        self.assertEqual(len(self.rows('problem_jobs')), 2)
        self.assertEqual(self.rows('investigations')[0]['attempts'], 1)
        winner = next(r['job_id'] for r in results if r)
        loser = 'c' if winner == 'b' else 'b'
        self.assertIsNone(self.store.lease_job(loser, 'fixture', now=30))
        self.assertIsNotNone(self.store.lease_job(winner, 'fixture', now=30))

    def test_concurrent_identical_admissions_are_idempotent(self):
        self.ready(); barrier = threading.Barrier(2)
        def admit(_):
            with JobStore(self.store.db_path) as store:
                barrier.wait(timeout=10)
                return guard.admit_continuation(store, 'p', predecessor_job_id='a',
                    job_id='b', reason='Same fixture', now=20)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(admit, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.rows('problem_continuations')), 1)

    def test_v2_migration_preserves_enabled_state_definitions_counters_and_receipts(self):
        for name in ('a', 'b', 'c'): self.job(name)
        guard.register(self.store, 'p', roots=['a', 'c']); guard.enable(self.store)
        lease = self.finish('c', passed=True, now=2, grade=False)
        guard.decide(self.store, lease['token'], {'decision': 'progress', 'fingerprint': 'c'*64,
            'reason': 'Independent synthetic proof', 'metric': {'name': 'selected-update-prefix', 'value': 3}})
        self.finish('a')
        before = {t: self.rows(t) for t in OLD_TABLES}
        self.store.connection.execute('DROP TABLE problem_continuations')
        self.store.connection.execute('PRAGMA user_version=2')
        self.store.close()
        self.store = JobStore(self.root/'j.sqlite'); self.addCleanup(self.store.close)
        self.assertEqual({t: self.rows(t) for t in OLD_TABLES}, before)
        self.assertEqual(self.store.connection.execute('PRAGMA user_version').fetchone()[0], SCHEMA_VERSION)
        self.admit()

    def test_v1_migration_preserves_job_specs_seals_and_attempt_history(self):
        self.job('a'); self.job('b')
        self.finish('a', passed=True, grade=False); self.finish('b', grade=False)
        before = {t: self.rows(t) for t in ('jobs', 'attempts', 'resource_locks')}
        for table in ('problem_continuations', 'problem_credits', 'problem_runs', 'problem_jobs',
                      'investigations', 'guard_meta', 'guard_denials'):
            self.store.connection.execute('DROP TABLE '+table)
        self.store.connection.execute('PRAGMA user_version=1')
        self.store.close()
        self.store = JobStore(self.root/'j.sqlite'); self.addCleanup(self.store.close)
        self.assertEqual({t: self.rows(t) for t in before}, before)
        self.assertFalse(guard.enabled(self.store.connection))
        self.assertEqual(self.rows('problem_continuations'), [])


class RealContinuationSupervisorTests(unittest.TestCase):
    def test_original_fake_worker_failure_continuation_and_durable_stop(self):
        temporary = tempfile.TemporaryDirectory(prefix='s'); self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve(); repo = root/'r'; repo.mkdir()
        state = root/'s'; binary = root/'w.py'
        # Original synthetic inputs and a local fixture commit solely for detached worktrees.
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.STDOUT,
                                           timeout=10, text=True).strip()
        git('init', '-q')
        (repo/'README.md').write_text('Original continuation fixture.\n', encoding='utf-8')
        git('add', 'README.md')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture')
        commit = git('rev-parse', 'HEAD')
        binary.write_text("import pathlib,sys\nprompt=sys.stdin.read()\n"
                          "assert 'isolated worktree' in prompt\n"
                          "print('original synthetic worker', flush=True)\n"
                          "if 'FAIL-FIXTURE' in prompt: sys.exit(3)\n"
                          "pathlib.Path('c.txt').write_text('synthetic success')\n", encoding='utf-8')
        pins = {}
        for index, name in enumerate(('rom', 'emulator', 'native')):
            pin = root/('f'+str(index)); pin.write_text('Original synthetic pin '+name, encoding='utf-8')
            pins[name] = str(pin)
        originals = {p: p.read_bytes() for p in (binary, *(Path(p) for p in pins.values()))}
        with JobStore(state/'jobs.sqlite') as store:
            for name, parents, fail in (('a', [], True), ('b', [], False), ('c', ['b'], True), ('d', [], False)):
                packet = {'schema': 1, 'job_id': name, 'kind': 'implement', 'source_commit': commit,
                    'pin_files': pins, 'prompt': 'FAIL-FIXTURE' if fail else 'SUCCESS-FIXTURE',
                    'timeout_seconds': 10, 'validation': [[sys.executable, '-B', '-c',
                        "from pathlib import Path; assert Path('c.txt').read_text() == 'synthetic success'"]],
                    'prerequisites': parents, 'retry_budget': 0,
                    'allowed_paths': ['c.txt'], 'max_changed_files': 1, 'evidence_files': []}
                supervisor.enqueue_packet(store, state, packet, binary)
            guard.register(store, 'p', roots=['a'], limits={**guard.DEFAULT_LIMITS, 'max_seconds': 60})
            guard.enable(store)
        original_packet = (state/'packets/a.json').read_bytes()
        def run(name):
            return supervisor.run_once(repo, state, binary, job_id=name,
                agent_prefix=[sys.executable, '-B', str(binary)], require_auth=False)
        self.assertIn('a: failed', run('a'))
        with JobStore(state/'jobs.sqlite') as store:
            original_job = store.job('a'); original_attempts = store.attempt_history('a')
            before = guard.status(store)
            guard.admit_continuation(store, 'p', predecessor_job_id='a', job_id='b', reason='Continue original fixture')
            self.assertEqual(guard.status(store), before)
            self.assertEqual(store.job('a'), original_job)
        (state/'PAUSED').write_text('fixture pause', encoding='utf-8')
        self.assertEqual(run('b'), 'paused')
        (state/'PAUSED').unlink()
        self.assertEqual(run('b'), 'b: candidate sealed')
        self.assertIn('c: failed', run('c'))
        with JobStore(state/'jobs.sqlite') as store:
            self.assertTrue(guard.enabled(store.connection))
            self.assertEqual(store.job('a'), original_job)
            self.assertEqual(store.attempt_history('a'), original_attempts)
            p = guard.status(store)['problems'][0]
            self.assertEqual((p['state'], p['attempts'], p['no_progress'], p['activity']), ('shelved', 3, 2, 1))
            with self.assertRaises(ValueError):
                guard.admit_continuation(store, 'p', predecessor_job_id='c', job_id='d', reason='Denied fixture')
            self.assertEqual(store.job('d')['attempts'], 0)
        self.assertEqual((state/'packets/a.json').read_bytes(), original_packet)
        for path, content in originals.items(): self.assertEqual(path.read_bytes(), content)
        for name in ('a', 'b', 'c'):
            attempt = state/'attempts'/name/'0001'
            self.assertIn('original synthetic worker', (attempt/'agent.jsonl').read_text())
            if os.name == 'nt':
                self.assertEqual(json.loads((attempt/'agent.guard.json').read_text())['state'], 'finished')


if __name__ == '__main__': unittest.main()
