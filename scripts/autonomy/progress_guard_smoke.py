"""Retained, ROM-free anti-stall acceptance with deliberately repetitive workers."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time

from scripts.autonomy import progress_guard as guard
from scripts.autonomy.job_store import JobStore
from scripts.autonomy.process_guard import real_python_executable
from scripts.autonomy.supervisor import enqueue_packet, run_once, _write_json_atomic, file_sha256


def run(output):
    root = Path(__file__).resolve().parents[2]
    producers = {name:file_sha256(root/name) for name in (
        'scripts/autonomy/progress_guard_smoke.py','scripts/autonomy/progress_guard.py',
        'scripts/autonomy/job_store.py','scripts/autonomy/supervisor.py',
        'scripts/autonomy/process_guard.py','scripts/autonomy/atomic_file.py',
        'scripts/autonomy/continuous.py','scripts/autonomy/service_entry.py',
        'tests/fixtures/autonomy_stalled_worker.py')}
    output = output.resolve()
    if not output.is_relative_to(root/'tools/private') or output.exists():
        raise ValueError('smoke output must be a new private directory')
    output.mkdir(parents=True)
    repo = output/'repo'; repo.mkdir()
    state = repo/'tools/private/autonomy'; state.mkdir(parents=True)
    (repo/'README.md').write_text('Original ROM-free automation trap fixture.\n')
    for args in (['init','-q'], ['config','user.name','Autonomy Fixture'],
                 ['config','user.email','autonomy-fixture@example.invalid'],
                 ['add','README.md'], ['commit','-qm','Original anti-stall fixture']):
        subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True,timeout=20)
    commit = subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    worker = output/'stalled-worker.py'
    shutil.copyfile(root/'tests/fixtures/autonomy_stalled_worker.py',worker)
    pins = {}
    for kind in ('rom','native','emulator'):
        path = output/(kind+'.fixture'); path.write_text('Synthetic pin only: '+kind)
        pins[kind] = str(path)
    def packet(name,mode):
        review = mode == 'TRAP_REVIEW'
        return {'schema':1,'job_id':name,'kind':'diagnose' if review else 'implement',
                'source_commit':commit,'pin_files':pins,'prompt':mode,
                'timeout_seconds':30,'validation':[] if review else [[real_python_executable(),'-c',
                    "from pathlib import Path; assert Path('candidate.txt').read_text() == 'independent fixture completed'"]],
                'prerequisites':[],'retry_budget':1,
                'allowed_paths':[] if review else ['candidate.txt'],
                'max_changed_files':0 if review else 1,'evidence_files':[]}
    names = [('repeat-1','TRAP_FAILURE'),('repeat-2','TRAP_FAILURE'),('repeat-3','TRAP_FAILURE'),
             ('fresh-review','TRAP_REVIEW'),('bounded-alternative','TRAP_ALTERNATIVE'),
             ('independent','TRAP_INDEPENDENT'),('stuck-process','TRAP_TIMEOUT')]
    with JobStore(state/'jobs.sqlite') as store:
        for name,mode in names: enqueue_packet(store,state,packet(name,mode),worker)
        guard.register(store,'stuck-fixture',roots=['repeat-1','repeat-2','repeat-3'],
                       recovery={'review':'fresh-review','alternative':'bounded-alternative'})
        guard.register(store,'independent-fixture',roots=['independent'])
        guard.register(store,'timeout-fixture',roots=['stuck-process'],
                       limits={**guard.DEFAULT_LIMITS,'max_seconds':1})
        guard.enable(store)
    start = time.monotonic(); outcomes = []
    for _ in range(8):
        result = run_once(repo,state,worker,agent_prefix=[real_python_executable(),str(worker)],require_auth=False)
        outcomes.append(result); print(result,flush=True)
        if result.startswith('progress-stopped:'): break
    with JobStore(state/'jobs.sqlite') as store:
        report = guard.status(store)
        stuck = next(p for p in report['problems'] if p['problem_id'] == 'stuck-fixture')
        timeout = next(p for p in report['problems'] if p['problem_id'] == 'timeout-fixture')
        assertions = {
            'third_repeat_never_launched':store.job('repeat-3')['attempts'] == 0,
            'one_review':store.job('fresh-review')['attempts'] == 1 and store.job('fresh-review')['state'] == 'passed',
            'one_alternative':store.job('bounded-alternative')['attempts'] == 1 and store.job('bounded-alternative')['state'] == 'failed',
            'independent_work_ran':store.job('independent')['state'] == 'passed',
            'stalled_problem_shelved':stuck['state'] == 'shelved',
            'running_process_stopped_by_problem_budget':store.job('stuck-process')['state'] == 'failed' and
                timeout['state'] == 'shelved' and timeout['spent'] < 15 and
                'investigation execution budget exhausted' in store.attempt_history('stuck-process')[0]['detail'],
            'no_self_awarded_progress':store.connection.execute('SELECT count(*) FROM problem_credits').fetchone()[0] == 0,
            'stop_not_endless_poll':outcomes[-1].startswith('progress-stopped:'),
            'no_active_jobs':not any(row['state'] in ('leased','running','verifying') for row in store.status_projection()['jobs'])}
        # Reopen proof: neither repeated registration nor a fresh worker gets another alternative.
        if store.job('bounded-alternative')['state'] == 'failed':
            store.retry_failed('bounded-alternative')
        assertions['restart_cannot_reset_allowance'] = store.lease_job('bounded-alternative','new-session') is None
        assertions['producer_files_unchanged'] = producers == {name:file_sha256(root/name) for name in producers}
        paths = [p for p in state.rglob('*') if p.is_file() and p.suffix != '.sqlite'
                 and not p.name.startswith('jobs.sqlite')]
        retained = {str(p.relative_to(output)):file_sha256(p) for p in paths}
    result = {'schema':1,'kind':'jfg-progress-guard-trap-qualification','complete':all(assertions.values()),
              'checks':assertions,'outcomes':outcomes,'progress':report,'elapsed_seconds':time.monotonic()-start,
              'evidence':retained,'real_subprocesses':True,'real_model_used':False,
              'producer_files':producers,'fixture_commit':commit,'worker_sha256':file_sha256(worker),
              'game_parity_verified':False,'general_recovery_planner_verified':False}
    _write_json_atomic(output/'result.json',result)
    if not result['complete']: raise ValueError('anti-stall acceptance failed; artifacts retained')
    return {key:value for key,value in result.items() if key not in ('evidence','progress')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    print(json.dumps(run(parser.parse_args().output)),flush=True)
