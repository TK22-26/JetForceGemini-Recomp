#!/usr/bin/env python3
"""Package only the independently compiled launcher, setup guides and license."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'build' / 'launcher'
NAME = 'JFG-Launcher-0.4.0-preview.2-windows-x64.zip'


def main() -> int:
    members = {
        'JFG-Launcher.exe': OUTPUT / 'JFG-Launcher.exe',
        'README.md': ROOT / 'docs/development/launcher.md',
        'BUILD-SETUP.md': ROOT / 'docs/development/rom-bootstrap.md',
        'LICENSE': ROOT / 'LICENSE',
    }
    for name, path in members.items():
        if not path.is_file() or path.is_symlink():
            raise SystemExit('Missing or linked package input: ' + name)
    binary = members['JFG-Launcher.exe'].read_bytes()
    if not binary.startswith(b'MZ') or len(binary) > 1_048_576:
        raise SystemExit('Unexpected launcher executable')
    receipt = json.loads((OUTPUT / 'launcher-build.json').read_text(encoding='utf-8-sig'))
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).strip():
        raise SystemExit('Commit the reviewed source changes before packaging the pinned launcher')
    expected_inputs = {'launcher/windows/Launcher.cs', 'launcher/windows/FirstRun.cs',
                       'launcher/windows/Setup.ps1', 'launcher/windows/Support.cs', 'launcher/windows/Diagnostics.cs', 'launcher/windows/Controller.cs', 'launcher/windows/NavigationMap.cs', 'launcher/windows/Audio.cs', 'launcher/windows/MapLayers.cs', 'launcher/windows/NavigationRoute.cs', 'launcher/windows/NavigationExplorer.cs', 'launcher/windows/NavigationCollision.cs', 'launcher/windows/BoxJump.cs', 'launcher/windows/ChestRoute.cs', 'launcher/windows/AutonomousExplorer.cs', 'launcher/windows/InventoryWindow.cs', 'scripts/build_launcher.ps1'}
    if (receipt.get('source_commit') != revision or set(receipt.get('inputs', {})) != expected_inputs
            or receipt.get('executable_sha256') != hashlib.sha256(binary).hexdigest()
            or any(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest
                   for name, digest in receipt['inputs'].items())):
        raise SystemExit('Launcher build is stale; compile and test this revision before packaging')
    # Compiler debug paths are not needed in the distributable launcher.
    for data in (binary.lower(), binary.decode('utf-16le', errors='ignore').lower().encode('utf-8')):
        if b':\\users\\' in data or b'/home/' in data or b'.pdb' in data:
            raise SystemExit('Executable contains a debug or personal path')
    archive = OUTPUT / NAME
    if archive.exists():
        raise SystemExit('Package already exists; preserve it and use a new reviewed version')
    payloads = {name: path.read_bytes() for name, path in members.items()}
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as package:
        for name, payload in payloads.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(info, payload)
    with zipfile.ZipFile(archive) as package:
        if set(package.namelist()) != set(members) or package.testzip() is not None:
            raise SystemExit('Archive verification failed')
        for name, payload in payloads.items():
            if package.read(name) != payload:
                raise SystemExit('Archive member changed')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (OUTPUT / 'SHA256SUMS.txt').write_text(digest + '  ' + NAME + '\n' + hashlib.sha256(binary).hexdigest() + '  JFG-Launcher.exe\n', encoding='ascii')
    (OUTPUT / 'package-inventory.json').write_text(json.dumps({
        'package': NAME,
        'source_commit': revision,
        'sha256': digest,
        'members': {name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()},
        'scope': 'Launcher only; no game runtime or ROM-derived inputs',
    }, indent=2) + '\n', encoding='utf-8')
    print('Verified launcher-only archive: ' + NAME)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
