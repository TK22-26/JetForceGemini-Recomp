"""Bind explicit native boot evidence to an exact regional program and backend.

The default original-OS smoke mode checks repeatability and artifact identity;
it never claims emulator parity. The explicit cooperative-phase6 mode retains
the historical oracle checkpoint contract without changing signed evidence.
"""
from __future__ import annotations
if __package__ in (None, ''):
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    __package__='scripts'
import argparse,hashlib,json,os,re,subprocess
from pathlib import Path
from scripts import verify_phase6_native_boot as observations
from scripts import program_bundle
from scripts.native_program_identity import capture_source,capture_tree,fingerprint
from scripts.prepare_generated_sources import _load_manifest,_validate_normalizer_revision,_resolve_contained
from scripts.regional.json_contract import loads
from scripts.rom_profiles import identify_rom

ROOT=Path(__file__).resolve().parents[2]

def require_matching_identities(profile,identity,corpus,oracle=None):
    program_bundle.validate_identity(identity)
    if (identity['revision_id'],identity['rom_sha1'],identity['rom_size'])!=(profile.revision_id,profile.sha1,profile.size):
        raise ValueError('Native executable belongs to another ROM revision')
    if corpus.get('version')!=7 or (corpus.get('revision_id'),corpus.get('program_model_sha256'),corpus.get('generation_input_sha256'))!=(profile.revision_id,identity['program_model_sha256'],identity['generation_input_sha256']):
        raise ValueError('Generated corpus differs from the linked program')
    if oracle is not None and (not isinstance(oracle,dict) or (oracle.get('revision_id'),oracle.get('rom_sha1'))!=(profile.revision_id,profile.sha1)):
        raise ValueError('Oracle lacks matching explicit revision and ROM identity')

def verify(executable,rom,oracle_path,generated_root,bizhawk_executable,oracle_probe,private_out,public_out,repeat=3,expected_build_identity=None):
    if type(repeat) is not int or not 2<=repeat<=20:raise ValueError('Repeat count must be 2..20')
    profile,_,_=identify_rom(rom.read_bytes())
    identity=program_bundle.describe(executable)
    corpus=_load_manifest(generated_root/'sources.json');_validate_normalizer_revision(corpus)
    oracle=loads(oracle_path.read_bytes());require_matching_identities(profile,identity,corpus,oracle)
    for field in ('game_descriptor','game_bindings'):
        digest=program_bundle.digest(_resolve_contained(generated_root.resolve(),corpus[field],field))
        if digest!=corpus[field+'_sha256'] or digest!=identity['build']['descriptor_sha256' if field=='game_descriptor' else 'bindings_sha256']:
            raise ValueError('Linked descriptor or bindings changed')
    if fingerprint(capture_source(ROOT))!=identity['build']['source_sha256'] or fingerprint(capture_tree(generated_root))!=identity['build']['generated_sources_sha256']:
        raise ValueError('Native source or generated corpus changed after linking')
    environment={k:v for k,v in os.environ.items() if not k.upper().startswith('JFG_')}
    environment['JFG_ORIGINAL_TIMING']='0'
    outputs=[];runs=[]
    for index in range(repeat):
        output,result=observations.run_native(executable,rom,expected_build_identity,environment=environment)
        if outputs:
            divergence=observations.first_divergence(outputs[0],runs[0],output,result,index+1)
            if divergence is not None:raise ValueError('Native determinism divergence: '+json.dumps(divergence,sort_keys=True))
        outputs.append(output);runs.append(result)
    observations.verify_invalid_rom(executable,environment)
    observations.validate_oracle(oracle,runs[0])
    provenance={'executable_sha256':program_bundle.digest(executable),'generated_tree_sha256':identity['build']['generated_sources_sha256'],
        'oracle_checkpoint_sha256':program_bundle.digest(oracle_path),'oracle_probe_sha256':program_bundle.digest(oracle_probe),
        'bizhawk_executable_sha256':program_bundle.digest(bizhawk_executable),'verifier_sha256':program_bundle.digest(Path(__file__)),
        'observation_contract_sha256':program_bundle.digest(Path(observations.__file__))}
    private={'schema_version':1,'kind':'jfg-regional-native-boot-evidence','revision_id':profile.revision_id,'identity':identity,
        'runs':runs,'oracle':oracle,'provenance':provenance,'execution_backend':'cooperative-phase6','scope':'Historical cooperative boot/checkpoint parity only; no original-OS, gameplay or release acceptance'}
    private_out.parent.mkdir(parents=True,exist_ok=True);private_out.write_text(json.dumps(private,indent=2)+'\n')
    public={'schema_version':1,'kind':'jfg-regional-native-boot-summary','revision_id':profile.revision_id,'rom_sha1':profile.sha1,
        'build_sha256':identity['build']['build_sha256'],'repeat':repeat,'deterministic':True,'oracle_checkpoint_parity':True,
        'invalid_rom_rejected':True,'provenance':provenance,'private_receipt_sha256':program_bundle.digest(private_out),
        'gameplay_qualified':False,'scope':private['scope']}
    public_out.parent.mkdir(parents=True,exist_ok=True);public_out.write_text(json.dumps(public,indent=2)+'\n');return public

def validate_original_os_result(payload, retraces):
    if type(retraces) is not int or not 3<=retraces<=6000:
        raise ValueError('Original-OS smoke target must be 3..6000 retraces')
    result=loads(payload)
    if not isinstance(result,dict):raise ValueError('Original-OS observation must be one object')
    expected={'kind':'jfg-phase9-original-os-probe','acceptance':False,'status':'retrace-target',
        'poll_target':0,'retrace_target':retraces,'vi_retraces':retraces,
        'unsupported_accesses':0,'runtime_snapshot_complete':False}
    if any(type(result.get(key)) is not type(value) or result[key]!=value for key,value in expected.items()):
        raise ValueError('Original-OS observation has a different boundary, backend or acceptance claim')
    for name in ('controller_samples','completed_updates','cpu_count','instructions','graphics_tasks','decoded_audio_tasks'):
        value=result.get(name)
        if type(value) is not int or not 0<=value<=2**64-1 or (name in ('cpu_count','instructions') and value==0):
            raise ValueError('Original-OS observation has an invalid counter: '+name)
    if not isinstance(result.get('state_hash'),str) or not re.fullmatch('[0-9a-f]{64}',result['state_hash']):
        raise ValueError('Original-OS observation lacks its native state digest')
    return result


def verify_original_os(executable,rom,generated_root,private_out,public_out,
        repeat=3,retraces=200,expected_build_identity=None):
    """Current backend smoke only. No emulator fields or snapshot completeness are inferred."""
    if type(repeat) is not int or not 2<=repeat<=20:raise ValueError('Repeat count must be 2..20')
    if type(retraces) is not int or not 3<=retraces<=6000:raise ValueError('Smoke target must be 3..6000 retraces')
    if private_out.resolve()==public_out.resolve() or private_out.exists() or public_out.exists():
        raise ValueError('Evidence destinations must be distinct and new')
    profile,_,_=identify_rom(rom.read_bytes())
    bundle=program_bundle.verify(executable.parent,profile.revision_id)
    identity=bundle['identity']
    if program_bundle.describe(executable)!=identity:raise ValueError('Executable differs from its verified bundle')
    if expected_build_identity is not None and identity['build_identity']!=expected_build_identity:
        raise ValueError('Unexpected configured native build identity')
    corpus=_load_manifest(generated_root/'sources.json');_validate_normalizer_revision(corpus)
    require_matching_identities(profile,identity,corpus)
    for field in ('game_descriptor','game_bindings'):
        actual=program_bundle.digest(_resolve_contained(generated_root.resolve(),corpus[field],field))
        if actual!=corpus[field+'_sha256'] or actual!=identity['build']['descriptor_sha256' if field=='game_descriptor' else 'bindings_sha256']:
            raise ValueError('Linked descriptor or bindings changed')
    if fingerprint(capture_source(ROOT))!=identity['build']['source_sha256'] or fingerprint(capture_tree(generated_root))!=identity['build']['generated_sources_sha256']:
        raise ValueError('Native source or generated corpus changed after linking')
    private_out.parent.mkdir(parents=True,exist_ok=True)
    run_root=private_out.with_name(private_out.stem+'-runs');run_root.mkdir()
    replay=run_root/'neutral-input.txt'
    replay.write_text('jfg-phase8-input-v2\n'+''.join(f'{i},{i+1},1,0000,0,0\n' for i in range(retraces*4)),encoding='ascii')
    environment={k:v for k,v in os.environ.items() if not k.upper().startswith('JFG_')}
    environment.update(JFG_ORIGINAL_TIMING='1',JFG_PHASE8_INPUT_REPLAY=str(replay.resolve()),JFG_PHASE9_REPLAY_BY_POLL='1')
    before=program_bundle.digest(executable);runs=[];scope='Repeated bounded original-OS smoke only; no emulator parity, complete runtime snapshot, gameplay or release acceptance'
    try:
        for index in range(repeat):
            directory=run_root/str(index+1);directory.mkdir()
            command=[str(executable.resolve()),'--rom',str(rom.resolve()),'--save',str((directory/'fresh.flash').resolve()),
                '--controller-pak',str((directory/'fresh.pak').resolve()),'--probe-retraces',str(retraces),'--watchdog-ms','300000']
            process=subprocess.run(command,cwd=executable.parent,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                timeout=330,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            (directory/'stdout.log').write_bytes(process.stdout);(directory/'stderr.log').write_bytes(process.stderr)
            if process.returncode!=0 or process.stderr:raise ValueError('Original-OS native run failed; preserved stdout/stderr in '+str(directory))
            result=validate_original_os_result(process.stdout,retraces)
            if result['controller_samples']>retraces*4:raise ValueError('Neutral input corpus was exhausted')
            if runs:
                divergence=observations.first_divergence(b'',runs[0],b'',result,index+1)
                if divergence is not None:raise ValueError('Native determinism divergence: '+json.dumps(divergence,sort_keys=True))
            runs.append(result)
        if program_bundle.digest(executable)!=before or program_bundle.verify(executable.parent,profile.revision_id)['identity']!=identity:
            raise ValueError('Program bundle changed during verification')
        provenance={'executable_sha256':before,'generated_tree_sha256':identity['build']['generated_sources_sha256'],
            'input_sha256':program_bundle.digest(replay),'verifier_sha256':program_bundle.digest(Path(__file__)),
            'observation_comparison_sha256':program_bundle.digest(Path(observations.__file__))}
        private={'schema_version':1,'kind':'jfg-regional-native-boot-evidence','evidence_kind':'original-os-smoke',
            'execution_backend':'original-os','revision_id':profile.revision_id,'identity':identity,'runs':runs,
            'provenance':provenance,'scope':scope,'complete':True,'oracle_checkpoint_parity':False,'gameplay_qualified':False}
        private_out.write_text(json.dumps(private,indent=2)+'\n')
        public={'schema_version':1,'kind':'jfg-regional-native-boot-summary','evidence_kind':'original-os-smoke',
            'revision_id':profile.revision_id,'rom_sha1':profile.sha1,'build_sha256':identity['build']['build_sha256'],
            'repeat':repeat,'retraces':retraces,'deterministic':True,'oracle_checkpoint_parity':False,
            'gameplay_qualified':False,'scope':scope,'provenance':provenance,'private_receipt_sha256':program_bundle.digest(private_out)}
        public_out.parent.mkdir(parents=True,exist_ok=True);public_out.write_text(json.dumps(public,indent=2)+'\n')
        return public
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        private_out.write_text(json.dumps({'complete':False,'evidence_kind':'original-os-smoke','identity':identity,
            'runs':runs,'error':str(error),'scope':scope},indent=2)+'\n')
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('executable','rom','generated-root','private-out','public-out'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('oracle','bizhawk-executable','oracle-probe'):p.add_argument('--'+name,type=Path)
    p.add_argument('--backend',choices=('original-os','cooperative-phase6'),default='original-os')
    p.add_argument('--retraces',type=int,default=200);p.add_argument('--repeat',type=int,default=3);p.add_argument('--expected-build-identity')
    args=vars(p.parse_args());backend=args.pop('backend');retraces=args.pop('retraces')
    try:
        if backend=='original-os':
            if any(args.pop(name) is not None for name in ('oracle','bizhawk_executable','oracle_probe')):
                raise ValueError('Original-OS smoke cannot claim a historical cooperative oracle checkpoint')
            result=verify_original_os(**args,retraces=retraces)
        else:
            if any(args[name] is None for name in ('oracle','bizhawk_executable','oracle_probe')):
                raise ValueError('Cooperative checkpoint requires all three explicit oracle inputs')
            args['oracle_path']=args.pop('oracle');result=verify(**args)
    except (OSError,ValueError,subprocess.SubprocessError) as error:print('regional boot verification:',error);return 1
    print(json.dumps(result,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
