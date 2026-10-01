"""Evidence-selected, bounded predecessor captures using the ordinary supervisor.

No new game/build/model policy: reuse the qualified runtime and delivered route.
A differing earlier snapshot selects an experiment, not a causal repair.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time

from scripts.autonomy import instruction_job as observation_job
from scripts.autonomy import instruction_observation as observation
from scripts.autonomy import source_build
from scripts.autonomy.job_store import ID_RE, JobSpec, JobStore
from scripts.autonomy.supervisor import (canonical_bytes, file_sha256, _write_json_atomic,
    bounded_command, real_python_executable, expired_attempt_contained)

PREFIX = 'instruction-capture:'
EXTRA_TOOLS = ('scripts/autonomy/instruction_capture.py',
    'scripts/phase95_native_replay.py', 'scripts/phase95_oracle_replay.py',
    'scripts/phase9_bizhawk_oracle.lua', 'scripts/prepare_phase9_oracle_flash.py',
    'scripts/compare_phase9_poll_hashes.py', 'scripts/phase9_event_trace.py',
    'scripts/phase9_update_word.py', 'scripts/phase9_controller_return.py',
    'scripts/phase9_controller_callers.py', 'scripts/phase9_si_trace.py')


def tool_sha():
    root = Path(__file__).resolve().parents[2]
    return hashlib.sha256(canonical_bytes({name:file_sha256(root/name)
        for name in sorted(set((*observation_job.TOOLS, *EXTRA_TOOLS)))})).hexdigest()


def select(report):
    """No monotonic-memory assumption or binary search over snapshots."""
    if report.get('complete') is not True or report.get('qualification', {}).get('passed') is not True:
        raise ValueError('predecessor selection requires a qualified observation')
    load = report.get('load_evidence')
    if not load:
        return {'operation':'needs-instrumentation', 'reason':'no qualified first-load mismatch'}
    earlier = [row['update'] for row in load['snapshots']
               if row['precedes_observed_update'] and not row['equal']]
    if not earlier:
        return {'operation':'needs-instrumentation', 'reason':'no earlier differing snapshot; live load evidence needed'}
    update = min(earlier)
    if type(update) is not int or not 1 <= update < report['update']:
        raise ValueError('predecessor observation does not move backward')
    return {'operation':'capture-predecessor', 'update':update,
            'window':[max(1, update-1), update+1], 'address':load['address'], 'width':load['width'],
            'reason':'capture invocation producing earliest retained differing snapshot',
            'causal_fix_proved':False, 'monotonic_memory_assumed':False}


def packet_path(state, job_id):
    if not isinstance(job_id,str) or not ID_RE.fullmatch(job_id):
        raise ValueError('invalid capture job ID')
    return state/'instruction-capture-packets'/(job_id+'.json')


def rom_pin(path, sha):
    path = Path(path).resolve(strict=True)
    if not path.is_file() or file_sha256(path) != sha:
        raise ValueError('capture ROM differs from qualified observation')
    return {'path':str(path), 'sha256':sha}


def parent_context(store, repo, state, parent_id, *, remeasure=False):
    job = store.job(parent_id)
    if job['state'] != 'passed' or not job.get('sealed_artifact') or not job.get('sealed_sha256'):
        raise ValueError('capture parent must be a sealed observation')
    path = source_build.pinned_file(repo, {'path':job['sealed_artifact'], 'sha256':job['sealed_sha256']})
    report = (observation_job.checked_observation(store,repo,state,parent_id) if remeasure else
              observation_job.verify_result(repo,state,parent_id,job['spec'],path))
    packet,_ = observation_job.read_packet(repo,state,parent_id,job['spec'])
    return report,packet,source_build.pin(path)


def recipe(repo, parent_packet):
    request = parent_packet['request']
    native = json.loads((Path(request['native'])/'native-result.json').read_text())
    oracle = json.loads((Path(request['oracle'])/'oracle-result.json').read_text())
    if native['execution_profile'] != 'original-os-probe' or oracle['mupen_cpu_core_override'] != 1:
        raise ValueError('unsupported predecessor replay profile')
    targets = {'native_target':native['target_retraces'], 'oracle_target':oracle['target_frame']}
    if any(type(n) is not int or not 4 <= n <= 1000000 for n in targets.values()):
        raise ValueError('unbounded predecessor replay target')
    return {**targets, 'source_export':str(observation.private_directory(repo,native['source_export'])),
            'native_build':request['native_build'], 'oracle_build':request['oracle_build'],
            'probe':request['probe']}


def enqueue(store, repo, state, parent_id, rom):
    if (state/'PAUSED').exists(): return None
    # The bounded child remeasures the entire parent before any capture launch.
    report,parent,seal = parent_context(store,repo,state,parent_id)
    plan = select(report)
    if plan['operation'] != 'capture-predecessor': return plan
    body = {'schema':1, 'kind':'instruction-predecessor-capture', 'parent_id':parent_id,
            'parent_result':seal, 'plan':plan, 'recipe':recipe(repo,parent),
            'rom':rom_pin(rom,report['rom_sha256']), 'tool_sha256':tool_sha()}
    job_id = 'instruction-capture-' + hashlib.sha256(canonical_bytes(body)).hexdigest()[:24]
    packet = {**body,'job_id':job_id}
    pins = {**store.job(parent_id)['spec']['pins'], 'tool_sha256':body['tool_sha256']}
    spec = JobSpec(job_id,pins,(PREFIX+hashlib.sha256(canonical_bytes(packet)).hexdigest(),),
                   (parent_id,), 'emulator:bizhawk', 1, 'json_complete')
    spec.validate()
    if (state/'PAUSED').exists(): return None
    path = packet_path(state,job_id)
    if path.exists() and path.read_bytes() != canonical_bytes(packet):
        raise ValueError('capture packet is immutable')
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        _write_json_atomic(path,packet)
    store.enqueue(spec)
    return {'operation':'capture-predecessor','job_id':job_id,'plan':plan}


def checked_packet(store,repo,state,job_id, *, remeasure=False):
    path = packet_path(state,job_id)
    if path.stat().st_size > 65536: raise ValueError('capture packet is too large')
    packet = json.loads(path.read_text())
    if set(packet) != {'schema','kind','parent_id','parent_result','plan','recipe','rom','tool_sha256','job_id'}:
        raise ValueError('capture packet schema differs')
    body = {k:v for k,v in packet.items() if k != 'job_id'}
    spec = store.job(job_id)['spec']
    if (type(packet['schema']) is not int or packet['schema'] != 1 or
            packet['kind'] != 'instruction-predecessor-capture' or packet['job_id'] != job_id or
            job_id != 'instruction-capture-'+hashlib.sha256(canonical_bytes(body)).hexdigest()[:24] or
            spec['inputs'] != [PREFIX+hashlib.sha256(canonical_bytes(packet)).hexdigest()] or
            spec['prerequisites'] != [packet['parent_id']] or packet['tool_sha256'] != tool_sha()):
        raise ValueError('capture packet identity or producer differs')
    report,parent,seal = parent_context(store,repo,state,packet['parent_id'],remeasure=remeasure)
    expected_pins = {**store.job(packet['parent_id'])['spec']['pins'], 'tool_sha256':tool_sha()}
    if (packet['parent_result'] != seal or packet['plan'] != select(report) or
            packet['recipe'] != recipe(repo,parent) or spec['pins'] != expected_pins or
            packet['plan']['operation'] != 'capture-predecessor' or
            packet['rom'] != rom_pin(packet['rom']['path'],report['rom_sha256'])):
        raise ValueError('capture plan is not derived from this verified parent')
    return packet


def request_for(packet, directory):
    plan,recipe = packet['plan'],packet['recipe']
    return {'schema':1,'kind':'instruction-observation-request',
            **{key:str((directory/key).resolve()) for key in ('native','native_control','oracle','oracle_control')},
            **{key:recipe[key] for key in ('native_build','oracle_build','probe')},
            'update':plan['update'],'window':plan['window']}


def capture_worker(store,repo,state,job_id,directory):
    from scripts.phase95_native_replay import replay as native_replay
    from scripts.phase95_oracle_replay import replay as oracle_replay
    packet = checked_packet(store,repo,state,job_id,remeasure=True)
    if (state/'PAUSED').exists(): raise ValueError('capture paused')
    # Four retained runs, full snapshots and binary effects need bounded free space.
    if shutil.disk_usage(state).free < 4*1024**3: raise ValueError('capture requires 4 GiB free space')
    request = request_for(packet,directory)
    native = json.loads(source_build.pinned_file(repo,request['native_build']).read_text())
    source_build.validate(repo,request['native_build'],Path(native['executable']))
    observation.oracle_build(repo,request['oracle_build'])
    emulator = Path(request['oracle_build']['path']).parent/'emulator/EmuHawk.exe'
    r,plan = packet['recipe'],packet['plan']
    for key in ('native_control','native','oracle_control','oracle'):
        if (state/'PAUSED').exists(): raise ValueError('capture paused between runs')
        checked_packet(store,repo,state,job_id)
        print(json.dumps({'stage':key,'update':plan['update']}),flush=True)
        # Requests retain canonical hex strings; the replay APIs require integers.
        common = dict(timeout=600,update_hashes=True,focus_updates=plan['window'],
                      point_pcs=[int(value,16) for value in r['probe']['pcs']],
                      point_words=[int(value,16) for value in r['probe']['words']],device_events=True,
                      instruction_effect_update=None if key.endswith('_control') else plan['update'])
        if key.startswith('native'):
            native_replay(Path(r['source_export']),Path(request[key]),Path(native['executable']),
                Path(packet['rom']['path']),packet['rom']['sha256'],poll_trace=True,
                execution_profile='original-os-probe',target_retraces=r['native_target'],eret_transfers=True,**common)
        else:
            oracle_replay(Path(request[key]),emulator,Path(packet['rom']['path']),packet['rom']['sha256'],
                Path(r['source_export']),checkpoints=[r['oracle_target']],target_frame=r['oracle_target'],
                vi_trace=True,mupen_cpu_core=1,cpu_boundary_update=plan['update'],**common)
    measured = observation.measure(repo,request)
    checked_packet(store,repo,state,job_id)
    return {'schema':1,'kind':'instruction-predecessor-capture-result','complete':True,'job_id':job_id,
            'packet_sha256':file_sha256(packet_path(state,job_id)), 'parent_result':packet['parent_result'],
            'request':request,'measurement':measured,'parity_verified':False,'promoted':False}


def verified_result(store,repo,state,job_id,path):
    packet = checked_packet(store,repo,state,job_id)
    report = json.loads(path.read_text())
    if (type(report.get('schema')) is not int or report['schema'] != 1 or
            report.get('kind') != 'instruction-predecessor-capture-result' or report.get('complete') is not True or
            report.get('job_id') != job_id or report.get('packet_sha256') != file_sha256(packet_path(state,job_id)) or
            report.get('parent_result') != packet['parent_result'] or
            report.get('request') != request_for(packet,path.parent) or
            report.get('parity_verified') is not False or report.get('promoted') is not False):
        raise ValueError('capture result is incomplete or has different inputs')
    measured = report.get('measurement',{})
    evidence,pins = observation_job.inventory(repo,report['request'])
    if (measured.get('complete') is not True or measured.get('qualification',{}).get('passed') is not True or
            measured.get('evidence') != evidence or measured.get('promoted') is not False or
            any(measured.get(k) is not False for k in observation.native_effects.LIMITS) or
            measured.get('source_commit') != pins['source_commit'] or
            measured.get('native_runtime_sha256') != pins['native_sha256'] or
            measured.get('oracle_runtime_sha256') != pins['emulator_sha256'] or
            measured.get('rom_sha256') != pins['rom_sha256']):
        raise ValueError('capture measurement does not bind the generated evidence')
    return report


def next_observation(store,repo,state,job_id):
    if (state/'PAUSED').exists(): return None
    job = store.job(job_id)
    if job['state'] != 'passed': return None
    seal = source_build.pinned_file(repo,{'path':job['sealed_artifact'],'sha256':job['sealed_sha256']})
    report = verified_result(store,repo,state,job_id,seal)
    # Independent observation child remeasures; it never trusts the capture result's success flag.
    return observation_job.queue(store,repo,state,report['request'],prerequisites=(job_id,))


def run_lease(store,lease,repo,state):
    job_id,token = lease['job_id'],lease['token']
    directory = state/'attempts'/job_id/f"{lease['attempt']:04d}"
    directory.mkdir(parents=True,exist_ok=True)
    path = directory/'result.json'
    try:
        checked_packet(store,repo,state,job_id)
        for old in store.attempt_history(job_id):
            if old['number'] < lease['attempt'] and old['outcome'] == 'expired':
                prior = state/'attempts'/job_id/f"{old['number']:04d}"
                if prior.exists() and not expired_attempt_contained(prior):
                    raise ValueError('expired capture child may still be alive')
                if (prior/'result.json').is_file():
                    verified_result(store,repo,state,job_id,prior/'result.json')
                    store.start(job_id,token)
                    store.verify(job_id,token)
                    store.seal_artifact(job_id,token,prior/'result.json')
                    store.pass_job(job_id,token)
                    return f'{job_id}: complete prior predecessor capture recovered'
        store.start(job_id,token)
        command = [real_python_executable(),'-m','scripts.autonomy.instruction_capture','--worker',job_id,
                   '--repo',str(repo),'--state',str(state)]
        code,reason = bounded_command(command,repo,directory/'capture.stdout',directory/'capture.stderr',
            time.monotonic()+3000,lambda:store.heartbeat(job_id,token,ttl=120),state/'PAUSED',
            memory_limit_bytes=6*1024**3,cpu_seconds=6000,guard_record=directory/'capture.guard.json',
            minimum_free_bytes=2*1024**3,output_tree=directory,max_output_tree_bytes=4*1024**3)
        if code != 0 or reason is not None: raise ValueError(reason or 'capture child failed; retained stderr')
        verified_result(store,repo,state,job_id,path)
        store.verify(job_id,token)
        store.seal_artifact(job_id,token,path)
        store.pass_job(job_id,token)
        return f'{job_id}: predecessor capture sealed'
    except (OSError,ValueError) as error:
        _write_json_atomic(directory/'failure.json',{'complete':False,'job_id':job_id,'stop_reason':str(error)[:300]})
        store.fail_job(job_id,token,str(error)[:300],blocked=True)
        return f'{job_id}: predecessor capture blocked ({error})'


def cycle(repo,state,parent_id,rom,steps):
    from scripts.autonomy.supervisor import run_once
    if type(steps) is not int or not 1 <= steps <= 8: raise ValueError('cycle steps must be 1..8')
    for _ in range(steps):
        with JobStore(state/'jobs.sqlite') as store:
            chosen = enqueue(store,repo,state,parent_id,rom)
        if chosen is None: return {'state':'paused','parent_id':parent_id}
        if chosen['operation'] != 'capture-predecessor': return {**chosen,'parent_id':parent_id}
        capture_id = chosen['job_id']
        for stage in ('capture','observation'):
            with JobStore(state/'jobs.sqlite') as store:
                store.reclaim_expired()
                job_id = capture_id if stage == 'capture' else next_observation(store,repo,state,capture_id)
                if job_id is None: return {'state':'paused','parent_id':parent_id}
                status = store.job(job_id)['state']
            if status == 'queued':
                print(run_once(repo,state,Path('unused-deterministic-worker'),allow_agent=False,job_id=job_id),flush=True)
                with JobStore(state/'jobs.sqlite') as store: status = store.job(job_id)['state']
            if status != 'passed': return {'state':status,'job_id':job_id,'parent_id':parent_id}
        parent_id = job_id
    return {'state':'step-budget-complete','parent_id':parent_id,'parity_verified':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--state',type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--parent'); mode.add_argument('--worker')
    parser.add_argument('--rom',type=Path); parser.add_argument('--steps',type=int,default=1)
    args = parser.parse_args()
    repo = args.repo.resolve(strict=True)
    state = (args.state or repo/'tools/private/autonomy').resolve()
    if not state.is_relative_to(repo/'tools/private'): parser.error('capture state must be private')
    if args.worker:
        with JobStore(state/'jobs.sqlite') as store:
            job = store.job(args.worker)
            directory = state/'attempts'/args.worker/f"{job['attempts']:04d}"
            if job['state'] != 'running' or (directory/'result.json').exists():
                parser.error('capture worker needs a running, unpublished attempt')
            result = capture_worker(store,repo,state,args.worker,directory)
            _write_json_atomic(directory/'result.json',result)
    else:
        if args.rom is None: parser.error('capture cycle requires a legally supplied --rom')
        print(json.dumps(cycle(repo,state,args.parent,args.rom,args.steps)),flush=True)


if __name__ == '__main__': main()
