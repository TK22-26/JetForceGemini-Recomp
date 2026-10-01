"""Execute original jump-table assembly through the actual offline compiler.

Retain failed controls as failures. Run in Linux/WSL with fatal ASan/UBSan.
This qualifies bounded switch semantics, not unrestricted dynamic guest code.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(output, recompiler, include, relocated=False):
    output = output.resolve()
    recompiler, include = recompiler.resolve(strict=True), include.resolve(strict=True)
    if not output.is_relative_to(ROOT / 'tools/private') or output.exists():
        raise ValueError('use a new private directory')
    output.mkdir()
    receipts = []

    def command(args, require_success=True):
        result = subprocess.run(list(map(str, args)), cwd=output, capture_output=True, text=True, timeout=180)
        index = len(receipts)
        (output / f'command-{index}.stdout').write_text(result.stdout)
        (output / f'command-{index}.stderr').write_text(result.stderr)
        receipts.append({'argv': list(map(str, args)), 'exit_code': result.returncode})
        if require_success and result.returncode != 0:
            raise ValueError(f'command {index} failed: {result.stderr[-2000:]}')
        return result

    fixture = ROOT / 'tests/fixtures/guest_jump_tables.S'
    driver = ROOT / 'tests/generated_guest_jump_tables.cpp'
    try:
        command(['mips-linux-gnu-as', '-march=vr4300', '-32', '-o', 'test.o', fixture])
        command(['mips-linux-gnu-ld', '--emit-relocs', '-Ttext=0x80001000', '-e', 'table_observe',
                 '-o', 'test.elf', 'test.o'])
        symbols = command(['mips-linux-gnu-nm', 'test.elf']).stdout
        addresses = dict((name, int(address, 16)) for address, name in
                         re.findall(r'^([0-9a-f]+) [tT] (table_\w+)$', symbols, re.M))
        if len(addresses) != 10:
            raise ValueError('incomplete symbol inventory')
        (output / 'table_addresses.h').write_text(
            f'#define TABLE_SHIFT {"0x00123000U" if relocated else "0U"}\n' +
            ''.join(f'#define {name.upper()} 0x{address:08x}U\n' for name, address in addresses.items()))
        (output / 'relocatable.txt').write_text('.text\n')
        (output / 'test.toml').write_text('[input]\nelf_path="test.elf"\noutput_func_path="generated"\n'
            'use_mdebug=false\nemit_guest_cpu_state=true\n'
            'indirect_decision_sidecar_path="generated/decisions.json"\n' +
            ('relocatable_sections_path="relocatable.txt"\n' if relocated else ''))
        command([recompiler, 'test.toml'])
        sidecar = json.loads((output / 'generated/decisions.json').read_text())
        switches = [row for row in sidecar['decisions'] if row['classification'] == 'bounded-switch']
        if len(switches) != 2:
            raise ValueError('fixture did not lower to two bounded switches')
        sources = sorted((output / 'generated').glob('*.c'))
        flags = ['-O1', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
        objects = []
        for i, source in enumerate(sources):
            obj = output / f'body{i}.o'
            command(['gcc', '-std=c11', *flags, '-I', include, '-c', source, '-o', obj])
            objects.append(obj)
        binary = output / 'tables-test'
        command(['g++', '-std=c++20', *flags, '-I', include, '-I', output, driver, *objects, '-o', binary])
        ordinary = command([binary], False)
        rejects = [command([binary, kind], False) for kind in ('unknown', 'unaligned')]
        passed = ordinary.returncode == 0 and ordinary.stdout.endswith('matched\t16\t16\n') and all(
            result.returncode == 86 and result.stdout == 'rejected-target\n' for result in rejects)
        inputs = [fixture, driver, Path(__file__), recompiler, include / 'recomp.h', *sources,
                  output / 'test.elf', output / 'test.toml', output / 'generated/decisions.json']
        report = {'kind': 'jfg-generated-guest-jump-tables', 'complete': True, 'passed': passed,
                  'cases': 16, 'rejections': 2, 'relocated': relocated,
                  'sanitizers': ['address', 'undefined'], 'parity_verified': False,
                  'inputs': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
                  'commands': receipts}
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        return report
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        (output / 'failure.json').write_text(json.dumps({'complete': False, 'error': str(error),
                                                       'commands': receipts}, indent=2) + '\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--recompiler', type=Path, required=True)
    parser.add_argument('--include', type=Path, required=True)
    parser.add_argument('--relocated', action='store_true')
    args = parser.parse_args()
    report = run(args.output, args.recompiler, args.include, args.relocated)
    print(json.dumps({key: value for key, value in report.items() if key not in ('inputs', 'commands')}))
    raise SystemExit(0 if report['passed'] else 1)
