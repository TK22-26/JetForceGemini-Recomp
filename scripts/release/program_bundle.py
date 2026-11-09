"""Post-link regional bundle identity. Contains no ROM, symbols or game assets.

The binary reports its own pre-link identity. The manifest pins final binaries;
neither hash includes itself. Qualification remains a separate evidence decision.
"""
from __future__ import annotations
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "scripts"
import argparse, hashlib, json, os, re, subprocess
from pathlib import Path
from scripts.rom_profiles import PROFILES_BY_ID
from scripts.regional.json_contract import loads
from scripts.package_beta import GAME_FILES, RUNTIME_FILES

MANIFEST_NAME = "jfg-program.json"
IDENTITY_FIELDS = {"schema_version", "kind", "revision_id", "rom_sha1", "rom_size",
    "descriptor_abi", "binding_abi", "program_model_sha256", "generation_input_sha256",
    "initial_tv_mode", "qualification", "build_identity", "build"}
BUILD_FIELDS={"source_sha256","generated_sources_sha256","descriptor_sha256","bindings_sha256","generator_sha256","audio_sha256","dependencies_sha256","configuration_sha256","build_sha256"}

def digest(path: Path) -> str:
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()

def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')

def hash_value(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None

def validate_identity(value):
    if not isinstance(value, dict) or set(value) != IDENTITY_FIELDS:
        raise ValueError('Incomplete or unexpected embedded program identity')
    profile = PROFILES_BY_ID.get(value['revision_id'])
    if profile is None or value['kind'] != 'jfg-native-program-identity':
        raise ValueError('Unknown embedded program revision')
    for key, expected in (('schema_version',2), ('descriptor_abi',1), ('binding_abi',3),
                          ('rom_size',profile.size), ('initial_tv_mode',0 if profile.code=='pal' else 1)):
        if type(value[key]) is not int or value[key] != expected:
            raise ValueError('Incompatible embedded '+key)
    if value['rom_sha1'] != profile.sha1 or value['qualification'] != 'candidate':
        raise ValueError('Embedded ROM identity or qualification is invalid')
    if any(not hash_value(value[k]) for k in ('program_model_sha256','generation_input_sha256')):
        raise ValueError('Invalid embedded program digest')
    if not isinstance(value['build_identity'],str) or not re.fullmatch(r'[A-Za-z0-9_.+-]{1,128}',value['build_identity']):
        raise ValueError('Invalid compiler build identity')
    build=value['build']
    if not isinstance(build,dict) or set(build)!=BUILD_FIELDS or any(not hash_value(v) for v in build.values()):
        raise ValueError('Missing native source/generation/compiler identity')
    parts={k:v for k,v in build.items() if k!='build_sha256'}
    expected=hashlib.sha256(canonical(dict(parts,revision_id=profile.revision_id))).hexdigest()
    if build['build_sha256']!=expected:raise ValueError('Native compatibility key is inconsistent')
    return profile

def describe(executable: Path):
    environment={k:v for k,v in os.environ.items() if not k.upper().startswith('JFG_')}
    result=subprocess.run([str(executable.resolve()),'--describe'],cwd=executable.parent,
        env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode or result.stderr or len(result.stdout)>16384:
        raise ValueError('Runtime did not return a bounded program identity')
    identity=loads(result.stdout);validate_identity(identity)
    return identity

def validate_manifest(value):
    if not isinstance(value,dict) or set(value)!={'schema_version','kind','identity','provenance','files'} or type(value['schema_version']) is not int or value['schema_version']!=1 or value['kind']!='jfg-native-program-bundle':
        raise ValueError('Unsupported program bundle schema')
    profile=validate_identity(value['identity'])
    provenance=value['provenance']
    if not isinstance(provenance,dict) or set(provenance)!={'source_inputs_sha256','generator_sha256','dependencies_sha256','build_receipt_sha256'} or any(not hash_value(v) for v in provenance.values()):
        raise ValueError('Invalid bundle build provenance')
    files=value['files'];seen=set()
    if not isinstance(files,list):raise ValueError('Invalid bundle file inventory')
    for row in files:
        if not isinstance(row,dict) or set(row)!={'name','size','sha256'} or row['name'] not in RUNTIME_FILES or row['name'] in seen or type(row['size']) is not int or row['size']<=0 or not hash_value(row['sha256']):
            raise ValueError('Invalid, duplicate or unexpected bundle file')
        seen.add(row['name'])
    if not set(GAME_FILES)<=seen:raise ValueError('Incomplete program bundle')
    return profile

def read(path: Path):
    if path.stat().st_size>65536:raise ValueError('Program manifest is too large')
    value=loads(path.read_bytes());validate_manifest(value);return value

def verify(directory: Path, expected_revision: str|None=None, *, query=describe):
    value=read(directory/MANIFEST_NAME)
    if expected_revision is not None and value['identity']['revision_id']!=expected_revision:
        raise ValueError('Bundle belongs to another ROM revision')
    for row in value['files']:
        path=directory/row['name']
        if path.is_symlink() or not path.is_file() or path.stat().st_size!=row['size'] or digest(path)!=row['sha256']:
            raise ValueError('Bundle member is missing or changed: '+row['name'])
    actual=query(directory/'jfg-native-boot.exe');validate_identity(actual)
    if actual!=value['identity']:raise ValueError('Manifest does not describe the embedded program identity')
    # Query execution must not change the binary being admitted.
    executable=next(row for row in value['files'] if row['name']=='jfg-native-boot.exe')
    if digest(directory/executable['name'])!=executable['sha256']:raise ValueError('Runtime changed while checking its identity')
    return value

def create(directory: Path, generated: Path, build_receipt: Path, source_inputs: Path, root: Path):
    destination=directory/MANIFEST_NAME
    if destination.exists():raise ValueError('Preserve the existing bundle manifest; choose a fresh directory')
    receipt=loads(build_receipt.read_bytes());inputs=loads(source_inputs.read_bytes())
    if receipt.get('complete') is not True or receipt.get('changed_source_inputs')!=[] or receipt.get('sha256')!=digest(directory/'jfg-native-boot.exe'):
        raise ValueError('Successful unchanged native build receipt does not match this executable')
    if not isinstance(inputs,dict) or not inputs:raise ValueError('Missing captured source closure')
    for name,value in inputs.items():
        if not isinstance(name,str) or '\\' in name or name.startswith('/') or '..' in name.split('/') or not hash_value(value):
            raise ValueError('Invalid captured source closure member')
        path=(root/name).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file() or digest(path)!=value:
            raise ValueError('Native source changed after its captured build')
    identity=describe(directory/'jfg-native-boot.exe')
    corpus=loads((generated/'sources.json').read_bytes())
    if corpus.get('version')!=7 or (corpus.get('revision_id'),corpus.get('program_model_sha256'),corpus.get('generation_input_sha256')) != (identity['revision_id'],identity['program_model_sha256'],identity['generation_input_sha256']):
        raise ValueError('Generated corpus differs from linked runtime identity')
    from scripts.regional.producer_identity import fingerprint
    from scripts.prepare_generated_sources import _validate_normalizer_revision
    _validate_normalizer_revision(corpus)
    from scripts.native_program_identity import capture_source
    if inputs!=capture_source(root):raise ValueError('Captured native source closure is incomplete or stale')
    build=identity['build']
    native_receipt=receipt.get('native_identity_receipt')
    if not isinstance(native_receipt,str):raise ValueError('Build receipt omits the captured pre-link input closure')
    prelink=loads(Path(native_receipt).read_bytes())
    from scripts.native_program_identity import create as create_native_identity
    current,current_inputs=create_native_identity(root,generated,Path(prelink['audio_root']),prelink['options'],prelink['dependency_spec'])
    if current!=prelink['identity'] or current_inputs!=prelink or {k:current[k] for k in BUILD_FIELDS}!=build:
        raise ValueError('Actual generated sources, dependencies or compiler inputs changed since linking')
    files=[]
    for name in RUNTIME_FILES:
        path=directory/name
        if name not in GAME_FILES and not path.exists():continue
        if path.is_symlink() or not path.is_file():raise ValueError('Missing ordinary runtime member: '+name)
        files.append({'name':name,'size':path.stat().st_size,'sha256':digest(path)})
    value={'schema_version':1,'kind':'jfg-native-program-bundle','identity':identity,
        'provenance':{'source_inputs_sha256':hashlib.sha256(canonical(inputs)).hexdigest(),
            'generator_sha256':fingerprint(),'dependencies_sha256':build['dependencies_sha256'],
            'build_receipt_sha256':digest(build_receipt)},'files':files}
    validate_manifest(value)
    temporary=destination.with_suffix('.tmp')
    with temporary.open('x',encoding='ascii') as stream:
        json.dump(value,stream,indent=2,ensure_ascii=True);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    # Exclusive publication: a partially written manifest is never discoverable.
    if destination.exists():raise ValueError('Bundle manifest appeared during publication')
    temporary.rename(destination)
    return verify(directory)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('create','verify'))
    parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--revision')
    parser.add_argument('--generated-root',type=Path);parser.add_argument('--build-receipt',type=Path);parser.add_argument('--source-inputs',type=Path)
    args=parser.parse_args()
    if args.action=='create':
        if not all((args.generated_root,args.build_receipt,args.source_inputs)):parser.error('create requires generated root, build receipt and captured source inputs')
        result=create(args.directory.resolve(),args.generated_root,args.build_receipt,args.source_inputs,Path(__file__).resolve().parents[2])
    else:result=verify(args.directory.resolve(),args.revision)
    print(json.dumps({'revision_id':result['identity']['revision_id'],'verified':True,'qualification':'candidate'}))
    return 0
if __name__=='__main__':raise SystemExit(main())
