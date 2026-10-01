#!/usr/bin/env python3
"""Package only the independently compiled launcher, setup guides and license."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'build' / 'launcher'
NAME = 'JFG-Launcher-0.2.0-prototype.1-windows-x64.zip'


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
    (OUTPUT / 'SHA256SUMS.txt').write_text(digest + '  ' + NAME + '\n', encoding='ascii')
    (OUTPUT / 'package-inventory.json').write_text(json.dumps({
        'package': NAME,
        'sha256': digest,
        'members': {name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()},
        'scope': 'Launcher only; no game runtime or ROM-derived inputs',
    }, indent=2) + '\n', encoding='utf-8')
    print('Verified launcher-only archive: ' + NAME)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
