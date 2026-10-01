"""Durable, bounded instruction-evidence intake; never a parity promotion.

The request names explicit experimental builds, not a replacement for another
job's baseline. A supervisor-owned child requalifies the evidence independently.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

from scripts.autonomy import instruction_observation as observation, source_build
from scripts.autonomy.job_store import JobSpec, JobStore
from scripts.autonomy.supervisor import (SupervisorError, canonical_bytes, file_sha256,
    _write_json_atomic, bounded_command, real_python_executable)

PREFIX = 'instruction-observation:'
TOOLS = ('scripts/autonomy/instruction_job.py', 'scripts/autonomy/instruction_observation.py',
         'scripts/autonomy/supervisor.py', 'scripts/autonomy/job_store.py', 'scripts/autonomy/atomic_file.py',
         'scripts/autonomy/process_guard.py', 'scripts/autonomy/source_build.py', 'scripts/autonomy/source_snapshot.py',
         'scripts/autonomy/device_observation.py', 'scripts/autonomy/point_plan.py',
         'scripts/autonomy/entry_plan.py', 'scripts/autonomy/experiment_plan.py',
         'scripts/autonomy/point_interval_observation.py',
         'scripts/phase9_instruction_correspondence.py', 'scripts/phase9_instruction_effect_trace.py',
         'scripts/phase9_oracle_instruction_effects.py', 'scripts/phase9_instruction_effect_witnesses.py',
         'scripts/phase9_oracle_effect_witnesses.py', 'scripts/phase9_eret_transfers.py',
         'scripts/phase9_oracle_cpu_boundaries.py', 'scripts/phase9_device_events.py', 'scripts/phase9_point_probe.py',
         'scripts/phase95_bridge.py', 'scripts/phase95_poll_compare.py', 'scripts/build_phase9_route_replays.py',
         'scripts/compare_phase9_focus_rdram.py', 'scripts/oracle_instruction_effects.c',
         'scripts/compare_phase9_retrace_hashes.py', 'scripts/compare_phase9_update_hashes.py',
         'scripts/oracle_instruction_effects.h')


def tool_sha():
    root = Path(__file__).resolve().parents[2]
    return hashlib.sha256(canonical_bytes({name:file_sha256(root/name) for name in TOOLS})).hexdigest()


def inventory(repo, request):
    """Pin the exact measurement inventory; do not run the instruction comparison."""
    directories = observation.validate_request(repo, request)
    native_path = source_build.pinned_file(repo, request['native_build'])
    native = json.loads(native_path.read_text())
    native = source_build.validate(repo, request['native_build'], Path(native['executable']))
    oracle, support = observation.oracle_build(repo, request['oracle_build'])
    paths = [native_path, *support, *(source_build.pinned_file(repo, p) for p in native['evidence'])]
    metadata = {}
    for key, directory in directories.items():
        side = key.split('_')[0]
        path = directory / f'{side}-result.json'
        meta = json.loads(path.read_text())
        metadata[key] = meta
        paths.extend([path, *observation.capture_files(directory, side, meta, request['window'])])
        stream = directory / ('instruction-effects.bin' if side == 'native' else 'oracle-effects.bin')
        if key.endswith('_control'):
            if stream.exists(): raise ValueError('observer-off control contains instruction stream')
        else:
            paths.append(stream)
    source = observation.private_directory(repo, metadata['native']['source_export'])
    paths.extend(source/name for name in ('controller.input','export-manifest.json','initial.flash','initial.pak'))
    pins = {str(p.resolve(strict=True)):file_sha256(p) for p in paths}
    for path, sha in pins.items():
        source_build.pinned_file(repo, {'path':path,'sha256':sha})
    return pins, {'source_commit':native['source_commit'], 'native_sha256':native['runtime_sha256'],
                  'emulator_sha256':oracle['runtime_sha256'], 'rom_sha256':metadata['native']['rom_sha256'],
                  'tool_sha256':tool_sha()}


def packet_path(state, job_id):
    from scripts.autonomy.job_store import ID_RE
    if not isinstance(job_id,str) or not ID_RE.fullmatch(job_id): raise ValueError('invalid instruction job ID')
    return state/'instruction-packets'/(job_id+'.json')


def queue(store, repo, state, request, *, prerequisites=()):
    if (state/'PAUSED').exists(): return None
    evidence, pins = inventory(repo, request)
    body = {'schema':1, 'kind':'instruction-observation-packet', 'request':request,
            'evidence':evidence, 'pins':pins, 'prerequisites':list(prerequisites)}
    job_id = 'instruction-observe-' + hashlib.sha256(canonical_bytes(body)).hexdigest()[:24]
    packet = {**body,'job_id':job_id}
    spec = JobSpec(job_id,pins,(PREFIX+hashlib.sha256(canonical_bytes(packet)).hexdigest(),),
                   tuple(prerequisites),'analysis:instruction-effects',1,'json_complete')
    spec.validate()
    path = packet_path(state,job_id)
    if (state/'PAUSED').exists(): return None
    if path.exists() and path.read_bytes() != canonical_bytes(packet):
        raise SupervisorError('instruction packet is immutable')
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        _write_json_atomic(path,packet)
    store.enqueue(spec)
    return job_id


def read_packet(repo, state, job_id, spec):
    path = packet_path(state,job_id)
    if path.stat().st_size > 2*1024*1024: raise ValueError('instruction packet exceeds budget')
    packet = json.loads(path.read_text())
    fields = {'schema','kind','request','evidence','pins','prerequisites','job_id'}
    if (not isinstance(packet,dict) or set(packet)!=fields or type(packet['schema']) is not int or packet['schema']!=1 or
            packet['kind']!='instruction-observation-packet' or packet['job_id']!=job_id):
        raise ValueError('instruction packet schema differs')
    body = {k:v for k,v in packet.items() if k!='job_id'}
    digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
    if (job_id!='instruction-observe-'+hashlib.sha256(canonical_bytes(body)).hexdigest()[:24] or
            spec['inputs']!=[PREFIX+digest] or spec['pins']!=packet['pins'] or
            spec['prerequisites']!=packet['prerequisites'] or packet['pins']['tool_sha256']!=tool_sha()):
        raise ValueError('instruction packet identity or producer changed')
    if not isinstance(packet['evidence'],dict) or not 1<=len(packet['evidence'])<=8192:
        raise ValueError('instruction evidence inventory is invalid')
    observation.validate_request(repo,packet['request'])
    for path,sha in packet['evidence'].items():
        source_build.pinned_file(repo,{'path':path,'sha256':sha})
    return packet,digest


def measure_job(store, repo, state, job_id):
    spec = store.job(job_id)['spec']
    packet,digest = read_packet(repo,state,job_id,spec)
    report = observation.measure(repo,packet['request'])
    if (report['evidence']!=packet['evidence'] or report['source_commit']!=spec['pins']['source_commit'] or
            report['native_runtime_sha256']!=spec['pins']['native_sha256'] or
            report['oracle_runtime_sha256']!=spec['pins']['emulator_sha256'] or
            report['rom_sha256']!=spec['pins']['rom_sha256']):
        raise ValueError('instruction measurement changed its pinned inventory or build identity')
    read_packet(repo,state,job_id,spec)
    return {**report,'job_id':job_id,'packet_sha256':digest,'pins':spec['pins']}


def verify_result(repo,state,job_id,spec,path):
    packet,digest = read_packet(repo,state,job_id,spec)
    report = json.loads(path.read_text())
    if (report.get('kind')!='jfg-qualified-instruction-observation' or report.get('complete') is not True or
            report.get('job_id')!=job_id or report.get('packet_sha256')!=digest or report.get('pins')!=spec['pins'] or
            report.get('evidence')!=packet['evidence'] or report.get('qualification',{}).get('passed') is not True or
            report.get('correspondence',{}).get('streams_complete') is not True or
            report.get('source_commit')!=spec['pins']['source_commit'] or
            report.get('native_runtime_sha256')!=spec['pins']['native_sha256'] or
            report.get('oracle_runtime_sha256')!=spec['pins']['emulator_sha256'] or
            report.get('rom_sha256')!=spec['pins']['rom_sha256'] or
            report.get('promoted') is not False or any(report.get(k) is not False for k in observation.native_effects.LIMITS)):
        raise ValueError('instruction result is incomplete or contradicts its pinned packet')
    return report


def checked_observation(store,repo,state,job_id):
    """Consumer gate: authenticate the ledger, then independently recompute."""
    job=store.job(job_id)
    if job['state']!='passed' or not job.get('sealed_artifact') or not job.get('sealed_sha256'):
        raise ValueError('instruction observation has not passed')
    seal=source_build.pinned_file(repo,{'path':job['sealed_artifact'],'sha256':job['sealed_sha256']})
    report=verify_result(repo,state,job_id,job['spec'],seal)
    measured=measure_job(store,repo,state,job_id)
    if canonical_bytes(report)!=canonical_bytes(measured) or file_sha256(seal)!=job['sealed_sha256']:
        raise ValueError('sealed instruction finding contradicts remeasured evidence')
    return report


def run_lease(store,lease,repo,state):
    job_id,token = lease['job_id'],lease['token']
    directory = state/'attempts'/job_id/f"{lease['attempt']:04d}"
    directory.mkdir(parents=True,exist_ok=True)
    path = directory/'result.json'
    try:
        read_packet(repo,state,job_id,lease['spec'])
        store.start(job_id,token)
        command = [real_python_executable(),'-m','scripts.autonomy.instruction_job','--measure-job',job_id,
                   '--repo',str(repo),'--state',str(state),'--output',str(path)]
        code,reason = bounded_command(command,repo,directory/'measurement.stdout',directory/'measurement.stderr',
            time.monotonic()+1200,lambda:store.heartbeat(job_id,token,ttl=120),state/'PAUSED',
            memory_limit_bytes=4*1024**3,cpu_seconds=2400,guard_record=directory/'measurement.guard.json')
        if code!=0 or reason is not None: raise ValueError(reason or 'instruction measurement failed; retained stderr')
        verify_result(repo,state,job_id,lease['spec'],path)
        store.verify(job_id,token)
        store.seal_artifact(job_id,token,path)
        store.pass_job(job_id,token)
        return f'{job_id}: instruction observation sealed'
    except (OSError,ValueError) as error:
        # Never overwrite a complete child report while recording why admission failed.
        _write_json_atomic(directory/'failure.json',{'complete':False,'job_id':job_id,'stop_reason':str(error)[:300]})
        store.fail_job(job_id,token,str(error)[:300],blocked=True)
        return f'{job_id}: instruction observation blocked ({error})'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--state',type=Path)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--queue',type=Path)
    mode.add_argument('--measure-job')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    repo=args.repo.resolve(strict=True)
    state=(args.state or repo/'tools/private/autonomy').resolve()
    if not state.is_relative_to(repo/'tools/private'): parser.error('state must be private')
    with JobStore(state/'jobs.sqlite') as store:
        if args.measure_job:
            job=store.job(args.measure_job)
            expected=state/'attempts'/args.measure_job/f"{job['attempts']:04d}"/'result.json'
            if (args.output is None or args.output.resolve()!=expected.resolve() or
                    args.output.exists() or job['state']!='running'):
                parser.error('measurement output must be new and belong to the running attempt')
            _write_json_atomic(args.output,measure_job(store,repo,state,args.measure_job))
            return
        job_id=queue(store,repo,state,json.loads(args.queue.read_text()))
        status=store.job(job_id)['state'] if job_id else 'paused'
    print(json.dumps({'job_id':job_id,'state':status}),flush=True)
    if args.execute and status=='queued':
        from scripts.autonomy.supervisor import run_once
        print(run_once(repo,state,Path('unused-deterministic-worker'),allow_agent=False,job_id=job_id),flush=True)


if __name__=='__main__': main()
