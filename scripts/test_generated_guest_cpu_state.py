"""ROM-free generated HI/LO and FP condition/control state qualification.

This tests stored state and finite comparisons, not floating exception synthesis.
The header and generator must be rebuilt as a matched explicit-profile pair.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def call(*args):
    return subprocess.run(list(map(str, args)), check=True, capture_output=True,
                          text=True, timeout=120).stdout


def run(args):
    output, recompiler, include = (getattr(args, k).resolve() for k in ('output', 'recompiler', 'include'))
    if not output.is_relative_to(ROOT / 'tools/private') or output.exists():
        raise ValueError('use a new private output directory')
    output.mkdir()
    fixture = ROOT / 'tests/fixtures/guest_cpu_state.S'
    call('mips-linux-gnu-as', '-EB', '-mips3', '-o', output / 'test.o', fixture)
    call('mips-linux-gnu-ld', '-Ttext=0x80001000', '-e', 'state_read', '-o', output / 'test.elf', output / 'test.o')
    (output / 'test.toml').write_text('[input]\nelf_path="test.elf"\noutput_func_path="generated"\n'
        'use_mdebug=false\nemit_guest_link_registers=true\n' +
        ('emit_guest_cpu_state=true\n' if args.guest_cpu_state else ''))
    call(recompiler, output / 'test.toml')
    sources = [p for p in (output / 'generated').glob('*.c') if 'RECOMP_FUNC void state_' in p.read_text()]
    if not sources:
        raise ValueError('missing generated bodies')
    flags = ['-O1', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
    objects = []
    for index, source in enumerate(sources):
        obj = output / f'body{index}.o'
        call('gcc', '-std=c11', *flags, '-I', include, '-c', source, '-o', obj)
        objects.append(obj)
    driver = ROOT / 'tests/generated_guest_cpu_state.cpp'
    call('g++', '-std=c++20', *flags, '-I', include, driver, *objects, '-o', output / 'cpu-state-test')
    result = subprocess.run([str(output / 'cpu-state-test')], capture_output=True, text=True, timeout=120)
    (output / 'stdout.log').write_text(result.stdout)
    (output / 'stderr.log').write_text(result.stderr)
    inputs = [fixture, driver, recompiler, include / 'recomp.h', *sources, Path(__file__)]
    report = {'kind': 'jfg-generated-guest-cpu-state', 'acceptance': False,
        'guest_cpu_state': args.guest_cpu_state, 'exit_code': result.returncode,
        'passed': result.returncode == 0 and result.stdout == 'matched\t30\t30\n',
        'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--recompiler', type=Path, required=True)
    parser.add_argument('--include', type=Path, required=True)
    parser.add_argument('--guest-cpu-state', action='store_true')
    try:
        raise SystemExit(run(parser.parse_args()))
    except subprocess.CalledProcessError as error:
        print(error.stdout, error.stderr)
        raise
