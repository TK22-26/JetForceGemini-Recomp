#!/usr/bin/env python3
"""Build ROM-free Windows targets using a short checkout-specific output path."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
from build_from_rom import find_cmake
from build_paths import windows_cache

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', choices=('Debug', 'Release'), default='Debug')
    parser.add_argument('--build-root', type=Path, help='Optional short writable local cache folder')
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--jobs', type=int, default=min(os.cpu_count() or 4, 8))
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('This command is for Windows; use the Linux CMake presets on Linux.')
    if not 1 <= args.jobs <= 32:
        parser.error('--jobs must be between 1 and 32')
    build = windows_cache(ROOT, args.build_root) / 'c'
    cmake = find_cmake()
    print('Windows build output: ' + str(build), flush=True)
    subprocess.run([cmake, '--preset', 'windows-msvc', '-B', str(build)], cwd=ROOT, check=True)
    subprocess.run([cmake, '--build', str(build), '--config', args.config, '--parallel', str(args.jobs)], cwd=ROOT, check=True)
    if args.test:
        ctest = str(Path(cmake).with_name('ctest.exe'))
        subprocess.run([ctest, '--test-dir', str(build), '-C', args.config, '--output-on-failure'], cwd=ROOT, check=True)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
