"""Build a path-free pre-link identity from the actual native source/input closure.

The final executable digest belongs to the post-link bundle, never this header.
Source changes, private CPU/RSP output changes and compiler/option changes each
invalidate the compatibility key. Nothing here grants gameplay qualification.
"""
from __future__ import annotations
if __package__ in (None, ""):
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    __package__="scripts"
import argparse,hashlib,json,re
from pathlib import Path
from scripts.regional.json_contract import loads

ROOT=Path(__file__).resolve().parents[2]
SOURCE_FOLDERS=('src','include','cmake','config','patches','scripts/build','scripts/diagnostics')
# Capture every file in the declared source roots: extension allowlists silently
# miss textual includes, shaders and newly introduced compiler inputs. Python
# bytecode caches are execution residue, never source input.
SOURCE_CACHE_SUFFIXES={'.pyc','.pyo'}
AUDIO_FILES=('production-audio-adapter.cpp','brokered-rsp.hpp','brokered-jfg-audio-probe.cpp','jfg-audio-probe.cpp','input.toml','program.bin')

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')
def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def fingerprint(value):return hashlib.sha256(canonical(value)).hexdigest()

def capture_source(root:Path,paths=None):
    root=root.resolve()
    if paths is None:
        paths=[root/'CMakeLists.txt',root/'dependencies.lock.json']
        for folder in SOURCE_FOLDERS:
            directory=root/folder
            if not directory.is_dir():raise ValueError('Native source closure is missing '+folder)
            paths.extend(p for p in directory.rglob('*') if p.is_file()
                         and p.suffix not in SOURCE_CACHE_SUFFIXES
                         and '__pycache__' not in p.relative_to(root).parts)
    records={}
    for path in sorted(paths):
        path=Path(path)
        if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
            raise ValueError('Native source input is missing or escapes the source root')
        name=path.relative_to(root).as_posix()
        if name in records:raise ValueError('Duplicate native source input')
        records[name]=digest(path)
    if not records:raise ValueError('Empty native source closure')
    return records

def capture_tree(root:Path):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():raise ValueError('Missing ordinary input directory')
    root=root.resolve();paths=[]
    for path in root.rglob('*'):
        if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('Input closure contains a link or escaped member')
        if path.is_file():paths.append(path)
    return capture_source(root,paths)


def capture_dependencies(root:Path,spec):
    if not isinstance(spec,dict) or set(spec)!={'schema_version','headers','artifacts','variants'} or spec['schema_version']!=1:
        raise ValueError('Invalid actual dependency input specification')
    records={'lock_sha256':digest(root/'dependencies.lock.json'),'headers':{},'artifacts':{},'variants':{}}
    for group in ('headers','artifacts','variants'):
        if not isinstance(spec[group],dict):raise ValueError('Invalid dependency input group')
        for name,path in sorted(spec[group].items()):
            if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+',name) or not isinstance(path,str):raise ValueError('Invalid dependency input name')
            candidate=Path(path)
            if group=='headers':records[group][name]=capture_tree(candidate)
            else:
                if candidate.is_symlink() or not candidate.is_file():raise ValueError('Missing ordinary compiled dependency or variant: '+name)
                records[group][name]=digest(candidate)
    return records


def validate_options(value):
    if not isinstance(value,dict) or set(value)!={'schema_version','platform','compiler','configuration','options'} or type(value['schema_version']) is not int or value['schema_version']!=1:
        raise ValueError('Invalid native build options schema')
    if value['platform'] not in ('windows-x64','linux-x64') or value['configuration'] not in ('Debug','Release','RelWithDebInfo','MinSizeRel'):
        raise ValueError('Unsupported native target/configuration')
    compiler=value['compiler']
    if not isinstance(compiler,dict) or set(compiler)!={'id','version','target','flags'} or any(not isinstance(v,str) or not v or len(v)>16384 or '\0' in v for k,v in compiler.items() if k!='flags') or not isinstance(compiler['flags'],str) or len(compiler['flags'])>16384 or '\0' in compiler['flags']:
        raise ValueError('Incomplete native compiler identity')
    options=value['options']
    if not isinstance(options,dict) or not options or any(not isinstance(k,str) or not re.fullmatch(r'JFG_[A-Z0-9_]+',k) or type(v) not in (str,int,bool) for k,v in options.items()):
        raise ValueError('Missing semantic build options')
    return value

def create(root:Path,generated:Path,audio:Path,options,dependency_spec):
    from scripts.prepare_generated_sources import _load_manifest,_validate_normalizer_revision,_resolve_contained
    options=validate_options(options);manifest=_load_manifest(generated/'sources.json')
    if manifest['version']!=7:raise ValueError('Native identity requires the shared regional corpus')
    _validate_normalizer_revision(manifest)
    for key in ('game_descriptor','game_bindings'):
        if digest(_resolve_contained(generated.resolve(),manifest[key],key))!=manifest[key+'_sha256']:
            raise ValueError('Changed linked program metadata')
    source=capture_source(root);audio_inputs={}
    for name in AUDIO_FILES:
        path=audio/name
        if path.is_symlink() or not path.is_file():raise ValueError('Incomplete RSP producer output: '+name)
        audio_inputs[name]=digest(path)
    generated_inputs=capture_tree(generated);dependency_inputs=capture_dependencies(root,dependency_spec)
    parts={'source_sha256':fingerprint(source),'generated_sources_sha256':fingerprint(generated_inputs),
        'descriptor_sha256':manifest['game_descriptor_sha256'],'bindings_sha256':manifest['game_bindings_sha256'],
        'generator_sha256':manifest['normalizer_revision_sha256'],'audio_sha256':fingerprint(audio_inputs),
        'dependencies_sha256':fingerprint(dependency_inputs),'configuration_sha256':fingerprint(options)}
    identity={'schema_version':1,'kind':'jfg-native-build-identity','revision_id':manifest['revision_id'],**parts,
        'build_sha256':fingerprint({'revision_id':manifest['revision_id'],**parts})}
    private={'identity':identity,'source_inputs':source,'generated_inputs':generated_inputs,'audio_inputs':audio_inputs,'dependency_inputs':dependency_inputs,'dependency_spec':dependency_spec,'audio_root':str(audio.resolve()),'options':options}
    return identity,private

def header(identity):
    fields={'source_sha256':'kSourceSha256','generated_sources_sha256':'kGeneratedSourcesSha256','descriptor_sha256':'kDescriptorSha256',
        'bindings_sha256':'kBindingsSha256','generator_sha256':'kGeneratorSha256','audio_sha256':'kAudioSha256',
        'dependencies_sha256':'kDependenciesSha256','configuration_sha256':'kConfigurationSha256','build_sha256':'kBuildSha256'}
    rows=['// Generated pre-link build identity; no private paths or game bytes.','#pragma once','#include <string_view>','namespace jfg::game::build {']
    for key,name in fields.items():
        value=identity.get(key)
        if not isinstance(value,str) or not re.fullmatch(r'[0-9a-f]{64}',value):raise ValueError('Invalid native build digest')
        rows.append(f'inline constexpr std::string_view {name} = "{value}";')
    return '\n'.join(rows+['} // namespace jfg::game::build',''])

def write_if_changed(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists() or path.read_text(encoding='utf-8')!=text:path.write_text(text,encoding='utf-8',newline='\n')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--generated-root',type=Path,required=True);p.add_argument('--audio-root',type=Path,required=True)
    p.add_argument('--dependency-inputs',type=Path,required=True);p.add_argument('--options',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--private-receipt',type=Path,required=True)
    a=p.parse_args();identity,private=create(ROOT,a.generated_root,a.audio_root,loads(a.options.read_bytes()),loads(a.dependency_inputs.read_bytes()))
    write_if_changed(a.output,header(identity));write_if_changed(a.private_receipt,json.dumps(private,indent=2)+'\n')
    print(json.dumps(identity));return 0
if __name__=='__main__':raise SystemExit(main())
