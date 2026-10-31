#!/usr/bin/env python3
"""Validate release source identity and version before playable-bundle publication."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
ROOT = Path(__file__).resolve().parents[2]

VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?')


def launcher_version(root: Path) -> str:
    source = (root / 'launcher/windows/Launcher.cs').read_text(encoding='utf-8')
    versions = re.findall(r'AssemblyInformationalVersion\("([^"\n]*)"\)', source)
    if len(versions) != 1 or not VERSION.fullmatch(versions[0]):
        raise ValueError('Launcher informational version must be a semantic version')
    version = versions[0]
    suffix = VERSION.fullmatch(version)[4]
    if suffix and any(part.isdigit() and len(part) > 1 and part.startswith('0') for part in suffix.split('.')):
        raise ValueError('Numeric prerelease identifiers must not have leading zeros')
    return version


def command(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(list(args), cwd=cwd, text=True).strip()


def release_metadata(root: Path, tag: str, ref_type: str) -> dict:
    if ref_type != 'tag':
        raise ValueError('Run this workflow on an existing version tag, not a branch')
    version = launcher_version(root)
    if tag != 'v' + version:
        raise ValueError('Tag must match the launcher version: v' + version)
    cmake = (root / 'CMakeLists.txt').read_text(encoding='utf-8')
    match = re.search(r'project\(\s*jfg_recomp\s+VERSION\s+([0-9.]+)', cmake)
    if not match or match[1] != version.split('-', 1)[0]:
        raise ValueError('CMake and launcher versions disagree')
    commit = command('git', 'rev-parse', 'HEAD', cwd=root)
    tagged = command('git', 'rev-parse', 'refs/tags/' + tag + '^{commit}', cwd=root)
    if tagged != commit:
        raise ValueError('The release tag does not identify the checked-out commit')
    subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'origin/main'], cwd=root, check=True)
    return {'tag': tag, 'version': version, 'commit': commit, 'prerelease': '-' in version}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check',))
    parser.parse_args()
    print(json.dumps(release_metadata(ROOT, os.environ.get('RELEASE_TAG', ''), os.environ.get('RELEASE_REF_TYPE', '')), sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
