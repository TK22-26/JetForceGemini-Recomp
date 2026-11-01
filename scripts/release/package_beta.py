#!/usr/bin/env python3
"""Create a prebuilt Windows release; never include a ROM or extracted asset files."""
from __future__ import annotations

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"

import argparse, hashlib, json, re, shutil, subprocess, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME_FILES = ('jfg-native-boot.exe', 'SDL2.dll', 'dxcompiler.dll', 'dxil.dll')
VC_RUNTIME_FILES = ('concrt140.dll', 'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'msvcp140_atomic_wait.dll', 'msvcp140_codecvt_ids.dll', 'vccorlib140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'vcruntime140_threads.dll')
RUNTIME_FILES = GAME_FILES + VC_RUNTIME_FILES

def runtime_inputs(runtime: Path, vc_runtime: Path | None = None) -> dict[str, Path]:
    crt = vc_runtime if vc_runtime is not None else runtime
    return {name: (crt if name in VC_RUNTIME_FILES else runtime)/name for name in RUNTIME_FILES}

def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def runtime_manifest(runtime: Path, version: str, vc_runtime: Path | None = None) -> dict:
    entries=[]
    for name,path in runtime_inputs(runtime,vc_runtime).items():
        if not path.is_file() or path.is_symlink() or path.stat().st_size <= 0:
            raise ValueError('Incomplete runtime: '+name)
        with path.open('rb') as stream:
            if stream.read(2) != b'MZ': raise ValueError('Expected Windows executable: '+name)
        entries.append({'name':name,'size':path.stat().st_size,'sha256':digest(path)})
    return {'schema':1,'version':version,'files':entries}

def package(launcher: Path, runtime, output: Path, version: str, vc_runtime: Path | None = None) -> Path:
    """Package one or more independently verified revision bundles."""
    from scripts import program_bundle
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-beta\.[0-9]+)?',version):
        raise ValueError('Use an explicit release or beta version')
    archive=output.parent/('JFG-'+version+'-windows-x64.zip')
    if output.exists() or archive.exists():raise ValueError('Preserve existing package output; select a new destination')
    if '-beta.' not in version:
        build=json.loads((launcher.parent/'launcher-build.json').read_text(encoding='utf-8-sig'))
        source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        if build['source_commit']!=source or build['executable_sha256']!=digest(launcher):
            raise ValueError('Launcher build identity differs from the release source')
        if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():
            raise ValueError('Stable releases require a clean source checkout')
        if any(digest(ROOT/name)!=value for name,value in build['inputs'].items()):
            raise ValueError('Launcher source inputs changed after building')
    runtimes=[runtime] if isinstance(runtime,Path) else list(runtime)
    if not 1<=len(runtimes)<=3:raise ValueError('Supply one to three exact revision bundles')
    manifests={};files={};origins={}
    for directory in runtimes:
        directory=Path(directory)
        # Validate the full embedded identity before copying or relabeling files.
        bundled=program_bundle.verify(directory,query=program_bundle.describe)
        revision=bundled['identity']['revision_id']
        if revision in manifests:raise ValueError('Duplicate runtime revision: '+revision)
        profile=program_bundle.validate_identity(bundled['identity'])
        if not profile.native_supported:raise ValueError('Native release admission is closed for '+revision)
        complete=runtime_manifest(directory,version,vc_runtime)
        receipt=directory/'jfg-native-boot.exe.support'
        if not receipt.is_file():raise ValueError('Runtime build identity is required')
        identity=dict(line.split('=',1) for line in receipt.read_text().splitlines() if '=' in line)
        if identity.get('build_runtime_sha256')!=complete['files'][0]['sha256']:
            raise ValueError('Runtime differs from its build identity')
        if identity.get('build_dirty')!='0':raise ValueError('Use a reviewed clean runtime build')
        # The packaged inventory includes the supplied CRT. Program identity and
        # build provenance stay unchanged; hashes cover the actual copied files.
        bundled=dict(bundled,files=complete['files']);program_bundle.validate_manifest(bundled)
        manifests[revision]=bundled;origins[revision]=identity.get('build_source')
        prefix='runtimes/'+revision+'/'
        files.update((prefix+name,path) for name,path in runtime_inputs(directory,vc_runtime).items())
        files[prefix+'jfg-native-boot.exe.support']=receipt
    files.update({'JFG-Launcher.exe':launcher,'LICENSE':ROOT/'LICENSE',
        'RUNTIME-NOTICES.md':ROOT/'THIRD_PARTY_NOTICES.md','THIRD-PARTY.txt':ROOT/'launcher/ui/THIRD-PARTY.txt',
        'dependencies.lock.json':ROOT/'dependencies.lock.json','CHANGELOG.md':ROOT/'CHANGELOG.md'})
    for folder in ('licenses','fonts'):
        for item in (ROOT/'launcher/ui'/folder).glob('*.txt'):files['licenses/'+item.name]=item
    for relative in ('fonts/manifest.json','licenses/provenance.json'):
        files['licenses/'+('font-manifest.json' if relative.startswith('fonts') else 'provenance.json')]=ROOT/'launcher/ui'/relative
    for name in ('n64recomp','rt64','plume','cic','ares'):
        files['licenses/'+name+'-LICENSE.txt']=ROOT/'patches'/name/'LICENSE.upstream'
    for item in (ROOT/'launcher/runtime-licenses').glob('*.txt'):files['licenses/runtime/'+item.name]=item
    # Fixed names only; never recurse into build, profile or ROM directories.
    for name,path in files.items():
        if not path.is_file() or path.is_symlink():raise ValueError('Missing package input: '+name)
    output.mkdir(parents=True)
    for name,path in files.items():
        destination=output/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
    revisions=[]
    for revision,bundled in sorted(manifests.items()):
        directory=output/'runtimes'/revision;path=directory/program_bundle.MANIFEST_NAME
        path.write_text(json.dumps(bundled,indent=2)+'\n',encoding='utf-8')
        program_bundle.verify(directory,revision,query=program_bundle.describe)
        revisions.append({'revision_id':revision,'manifest_sha256':digest(path)})
    manifest={'schema':2,'version':version,'runtimes':revisions}
    (output/'jfg-package.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    (output/'START HERE.txt').write_text(
        'JFG '+version+' - Windows x64\n\n'
        '1. Extract the complete ZIP to a writable folder.\n'
        '2. Open JFG-Launcher.exe and select your supported original ROM.\n'
        '3. Click Play. The launcher chooses the matching installed runtime.\n\n'
        'Included revisions: '+', '.join(sorted(manifests))+'.\n'
        'No Git, Python, Visual Studio or WSL installation is required.\n'
        'Microsoft runtime libraries are included beside each game executable.\n'
        'No ROM, extracted game assets or personal saves are supplied.\n'
        'Game > Verify game files checks the selected regional bundle.\n'
        'Keep the launcher and runtimes folder together when moving or updating.\n'
        'Each revision has separate campaign and navigation save storage.\n'
        'Game > Settings > Change directory chooses the storage location.\n'
        'A compatible hardware graphics device is required for play.\n\n'
        'Compiled program and third-party license scopes remain separate;\n'
        'see LICENSE and RUNTIME-NOTICES.md.\n',encoding='utf-8')
    members=sorted(p for p in output.rglob('*') if p.is_file())
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in members:z.write(path,path.relative_to(output).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert set(z.namelist())=={p.relative_to(output).as_posix() for p in members}
        assert not any(Path(name).suffix.lower() in ('.z64','.n64','.v64','.pdb','.flash','.pak') for name in z.namelist())
    evidence={'version':version,'archive':archive.name,'sha256':digest(archive),'bytes':archive.stat().st_size,
        'launcher_source':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'runtime_sources':origins,'members':{p.relative_to(output).as_posix():digest(p) for p in members},
        'scope':'Verified revision bundles; no ROM, extracted assets, saves or debug symbols'}
    archive.with_suffix('.inventory.json').write_text(json.dumps(evidence,indent=2)+'\n')
    archive.with_suffix('.sha256').write_text(evidence['sha256']+'  '+archive.name+'\n')
    return archive


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launcher',required=True,type=Path)
    parser.add_argument('--runtime',required=True,type=Path,action='append',help='Verified regional bundle; repeat for additional admitted revisions')
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--vc-runtime',required=True,type=Path,help='x64 Microsoft.VC143.CRT from the maintainer Visual Studio redist directory')
    parser.add_argument('--version',required=True)
    args=parser.parse_args()
    print(package(args.launcher.resolve(),[path.resolve() for path in args.runtime],args.output.resolve(),args.version,args.vc_runtime.resolve()))
