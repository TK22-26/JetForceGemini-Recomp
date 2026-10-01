"""ROM-free reproducer for architectural JAL/JALR link values in generated C.

A failed control is recorded as a failed test, not treated as qualification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def call(*args):
    return subprocess.run(list(map(str, args)), check=True, text=True,
                          capture_output=True, timeout=120).stdout


def run(output, recompiler, include, guest_links=False, relocated=False, dynamic_returns=False, test_dynamic=False):
    output, recompiler, include = (p.resolve() for p in (output, recompiler, include))
    if not output.is_relative_to(ROOT / 'tools/private') or output.exists():
        raise ValueError('use a new private directory')
    output.mkdir()
    fixture = ROOT / 'tests/fixtures/guest_link_registers.S'
    call('mips-linux-gnu-as', '-march=vr4300', '-32', '-o', output / 'test.o', fixture)
    call('mips-linux-gnu-ld', '--emit-relocs', '-Ttext=0x80001000', '-e', 'link_direct', '-o', output / 'test.elf', output / 'test.o')
    symbols = call('mips-linux-gnu-nm', '-S', output / 'test.elf')
    leaf = re.search(r'^([0-9a-f]+) [0-9a-f]+ T link_leaf$', symbols, re.M)
    disassembly = call('mips-linux-gnu-objdump', '-dz', output / 'test.elf')
    sites = {name: [] for name in ('direct', 'indirect', 'clobber', 'conditional', 'likely')}
    owner = None
    for line in disassembly.splitlines():
        symbol = re.match(r'[0-9a-f]+ <link_(\w+)>:', line)
        if symbol:
            owner = symbol[1]
        match = re.match(r'\s*([0-9a-f]+):\s+([0-9a-f]{8})\s', line)
        if match:
            word = int(match[2], 16)
            if word >> 26 == 3 or (word >> 26 == 0 and word & 63 == 9) or \
                    (word >> 26 == 1 and (word >> 16) & 31 in (17, 19)):
                if owner == 'saved_return':
                    continue
                if owner not in sites:
                    raise ValueError('unexpected link site')
                sites[owner].append(int(match[1], 16))
    if leaf is None or any(len(rows) != 1 for rows in sites.values()):
        raise ValueError('incomplete link fixture')
    (output / 'link_addresses.h').write_text(
        f'#define LINK_SHIFT {"0x00123000U" if relocated else "0U"}\n' +
        f'#define LINK_LEAF 0x{leaf[1]}U\n' + ''.join(
            f'#define {name.upper()}_LINK 0x{rows[0] + 8:08x}U\n' for name, rows in sites.items()))
    (output / 'relocatable.txt').write_text('.text\n')
    (output / 'test.toml').write_text('[input]\nelf_path = "test.elf"\n'
        'output_func_path = "generated"\nuse_mdebug = false\nuse_lookup_for_all_function_calls = true\n' +
        ('emit_guest_link_registers = true\n' if guest_links else '') +
        ('emit_guest_dynamic_returns = true\n' if dynamic_returns else '') +
        'indirect_decision_sidecar_path = "generated/decisions.json"\n' +
        ('relocatable_sections_path = "relocatable.txt"\n' if relocated else ''))
    call(recompiler, output / 'test.toml')
    sources = [p for p in (output / 'generated').glob('*.c') if 'RECOMP_FUNC void link_' in p.read_text()]
    if not sources:
        raise ValueError('no generated fixture')
    if relocated and guest_links and not any('ctx->r31 = U64(ADD32(section_addresses[' in p.read_text() for p in sources):
        raise ValueError('relocated link generation missing')
    flags = ['-O1', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
    if test_dynamic:
        flags.append('-DTEST_DYNAMIC_RETURNS=1')
    objects = []
    for i, source in enumerate(sources):
        obj = output / f'body{i}.o'
        call('gcc', '-std=c11', *flags, '-I', include, '-c', source, '-o', obj)
        objects.append(obj)
    driver = ROOT / 'tests/generated_guest_links.cpp'
    call('g++', '-std=c++20', *flags, '-I', include, '-I', output, driver, *objects, '-o', output / 'links-test')
    result = subprocess.run([str(output / 'links-test')], capture_output=True, text=True, timeout=120)
    (output / 'stdout.log').write_text(result.stdout)
    (output / 'stderr.log').write_text(result.stderr)
    inputs = [fixture, driver, recompiler, include / 'recomp.h', *sources, Path(__file__)]
    sidecar = json.loads((output / 'generated/decisions.json').read_text())
    dynamic = [row for row in sidecar['decisions'] if row['classification'] == 'dynamic-tail-or-return']
    if dynamic_returns and (sidecar['schema_version'] != 2 or len(dynamic) != 2 or
            any(row['range'] != {'kind': 'generated-callable-or-matching-incoming-link'} for row in dynamic)):
        raise ValueError('incorrect checked-return sidecar')
    manifest = {'kind': 'jfg-generated-guest-link-test', 'acceptance': False, 'exit_code': result.returncode,
                'guest_link_profile': guest_links, 'relocated': relocated,
                'dynamic_return_profile': dynamic_returns, 'tested_dynamic_returns': test_dynamic,
                'architectural_links_match': result.returncode == 0 and result.stdout.endswith(
                    'matched\t10\t10\n' if test_dynamic else 'matched\t8\t8\n'),
                'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    (output / 'result.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))
    return 0 if manifest['architectural_links_match'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--recompiler', type=Path, required=True)
    parser.add_argument('--include', type=Path, required=True)
    parser.add_argument('--guest-links', action='store_true')
    parser.add_argument('--relocated', action='store_true')
    parser.add_argument('--dynamic-returns', action='store_true')
    parser.add_argument('--test-dynamic', action='store_true')
    args = parser.parse_args()
    try:
        raise SystemExit(run(args.output, args.recompiler, args.include, args.guest_links, args.relocated,
                             args.dynamic_returns, args.test_dynamic))
    except subprocess.CalledProcessError as error:
        print(error.stdout, error.stderr)
        raise
