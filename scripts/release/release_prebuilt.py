#!/usr/bin/env python3
"""Verify a maintainer-built ROM-required bundle before publishing its draft."""
from __future__ import annotations

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"

import argparse, hashlib, json, os, subprocess, zipfile
from pathlib import Path
from scripts.package_beta import RUNTIME_FILES
from scripts import program_bundle
from scripts.rom_profiles import PROFILES_BY_ID
from scripts.release.release_metadata import release_metadata
ROOT = Path(__file__).resolve().parents[2]

def verify_bundle(output: Path, metadata: dict) -> list[Path]:
    stem = 'JFG-' + metadata['version'] + '-windows-x64'
    archive = output / (stem + '.zip')
    inventory_path = output / (stem + '.inventory.json')
    checksum = output / (stem + '.sha256')
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if inventory['version'] != metadata['version'] or inventory['launcher_source'] != metadata['commit']:
        raise ValueError('Bundle source or version differs from the release tag')
    if inventory['sha256'] != digest or checksum.read_text().strip() != digest + '  ' + archive.name:
        raise ValueError('Bundle checksum mismatch')
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or set(names) != set(inventory['members']) or z.testzip():
            raise ValueError('Bundle membership or ZIP integrity mismatch')
        # New releases use the same revision-indexed format as the packager and
        # launcher. Historical tags retain their own schema-1 verifier.
        if 'jfg-package.json' not in names:
            raise ValueError('Bundle is missing the playable runtime or release documentation')
        raw_index = z.read('jfg-package.json')
        if len(raw_index) > 16384:
            raise ValueError('Runtime manifest is too large')
        manifest = program_bundle.loads(raw_index)
        if not isinstance(manifest, dict) or set(manifest) != {'schema', 'version', 'runtimes'} or type(manifest['schema']) is not int or manifest['schema'] != 2 or manifest['version'] != metadata['version']:
            raise ValueError('Runtime manifest version mismatch')
        entries = manifest['runtimes']
        if not isinstance(entries, list) or not 1 <= len(entries) <= len(PROFILES_BY_ID):
            raise ValueError('Invalid regional runtime inventory')
        revisions = set()
        required = {'JFG-Launcher.exe', 'jfg-package.json', 'LICENSE',
                    'RUNTIME-NOTICES.md', 'THIRD-PARTY.txt', 'START HERE.txt',
                    'CHANGELOG.md', 'dependencies.lock.json'}
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {'revision_id', 'manifest_sha256'}:
                raise ValueError('Invalid regional runtime entry')
            revision = entry['revision_id']
            if not isinstance(revision, str) or revision not in PROFILES_BY_ID or revision in revisions or not program_bundle.hash_value(entry['manifest_sha256']):
                raise ValueError('Unknown or duplicate regional runtime identity')
            if not PROFILES_BY_ID[revision].native_supported:
                raise ValueError('Native release admission is closed for ' + revision)
            revisions.add(revision)
            prefix = 'runtimes/' + revision + '/'
            required.update(prefix + name for name in (*RUNTIME_FILES, program_bundle.MANIFEST_NAME, 'jfg-native-boot.exe.support'))
        if not required <= set(names):
            raise ValueError('Bundle is missing the playable runtime or release documentation')
        if not isinstance(inventory.get('runtime_sources'), dict) or set(inventory['runtime_sources']) != revisions:
            raise ValueError('Runtime source inventory mismatch')
        for name in names:
            if name not in required and not (name.startswith('licenses/') and name.endswith(('.txt', '.json'))):
                raise ValueError('Unexpected bundle member: ' + name)
            if '\\' in name or any(p in ('', '.', '..') for p in name.split('/')):
                raise ValueError('Unsafe bundle path')
            if hashlib.sha256(z.read(name)).hexdigest() != inventory['members'][name]:
                raise ValueError('Member hash mismatch: ' + name)
        for entry in entries:
            revision = entry['revision_id']
            prefix = 'runtimes/' + revision + '/'
            raw_program = z.read(prefix + program_bundle.MANIFEST_NAME)
            if len(raw_program) > 65536 or hashlib.sha256(raw_program).hexdigest() != entry['manifest_sha256']:
                raise ValueError('Regional program manifest digest mismatch')
            program = program_bundle.loads(raw_program)
            program_bundle.validate_manifest(program)
            if program['identity']['revision_id'] != revision:
                raise ValueError('Regional program identity mismatch')
            if len(program['files']) != len(RUNTIME_FILES) or {e['name'] for e in program['files']} != set(RUNTIME_FILES):
                raise ValueError('Runtime manifest does not include all required libraries')
            for member in program['files']:
                data = z.read(prefix + member['name'])
                if not data.startswith(b'MZ') or len(data) != member['size'] or hashlib.sha256(data).hexdigest() != member['sha256']:
                    raise ValueError('Runtime manifest digest mismatch')
            receipt = z.read(prefix + 'jfg-native-boot.exe.support')
            if len(receipt) > 16384:
                raise ValueError('Runtime build identity is too large')
            pairs = [line.split('=', 1) for line in receipt.decode('ascii').splitlines() if '=' in line]
            identity = dict(pairs)
            source = inventory['runtime_sources'][revision]
            if len(identity) != len(pairs) or not isinstance(source, str) or not source or identity.get('build_dirty') != '0' or identity.get('build_runtime_sha256') != inventory['members'][prefix + 'jfg-native-boot.exe'] or identity.get('build_source') != source:
                raise ValueError('Runtime build identity mismatch')
    return [archive, inventory_path, checksum]

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('verify', 'publish'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    metadata = release_metadata(ROOT, os.environ.get('RELEASE_TAG', ''), os.environ.get('RELEASE_REF_TYPE', ''))
    assets = verify_bundle(args.output, metadata)
    if args.action == 'publish':
        repo = os.environ['GITHUB_REPOSITORY']
        # The REST tag endpoint excludes drafts. The CLI resolves draft releases
        # by tag through its authenticated release listing.
        release = json.loads(subprocess.check_output(
            ['gh', 'release', 'view', metadata['tag'], '--repo', repo,
             '--json', 'isDraft,assets,url,tagName'], text=True))
        if release['tagName'] != metadata['tag']:
            raise ValueError('Draft tag differs from the verified source')
        if {a['name'] for a in release['assets']} != {p.name for p in assets}:
            raise ValueError('Draft assets differ from the verified bundle')
        if not release['isDraft']:
            raise ValueError('Release is already public; do not overwrite it')
        subprocess.run(['gh', 'release', 'edit', metadata['tag'], '--repo', repo,
                        '--draft=false', '--prerelease=' + ('true' if metadata['prerelease'] else 'false'), '--latest=' + ('false' if metadata['prerelease'] else 'true')], check=True)
        print(release['url'])
    else:
        print(json.dumps({'verified': True, 'tag': metadata['tag'], 'assets': [p.name for p in assets]}))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
