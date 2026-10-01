"""Private original-OS queue/thread execution with a stackful ERET bridge.

The fixture is the same original assembly run by the independent micro-ROM.
OS initialization is an explicit, untimed fixture setup, not an implementation
or timing qualification of osInitialize. All measured queue/thread paths use
original private instructions. No guessed scheduling or CPU call costs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib

from scripts.phase9_cpu_queue_threads_trace import parse_trace
from scripts.phase9_cpu_branch_trace import parse_trace as parse_branch
from scripts.phase9_cpu_eret_trace import parse_trace as parse_eret
from scripts.phase9_cpu_interrupt_trace import parse_trace as parse_interrupt
from scripts.phase9_cpu_vi_manager_trace import parse_trace as parse_vi_manager

ROOT = Path(__file__).resolve().parents[1]
ROM_SHA = '159dde164c475976a3e527fbb20978431d4765f2c63019b3530c3aa8772595aa'
SETUP = 0x80097520
ENTRY = (0x800759d0, 0x80096bb0, 0x80096be0, 0x80097800,
         0x80096f20, 0x80096910, 0x80096d30)


def call(*args):
    return subprocess.run(list(map(str, args)), capture_output=True, text=True,
                          check=True, timeout=180).stdout


def run(args):
    if args.pending_mask:
        args.initialize = args.interrupt = True
    if args.vi_manager:
        args.initialize = args.interrupt = True
    if args.initialize and not args.interrupt:
        raise ValueError('initialization qualification requires the interrupt fixture')
    output, root, symbols, rom, oracle, recompiler = (getattr(args, key).resolve() for key in
        ('output', 'root', 'symbols', 'rom', 'oracle', 'recompiler'))
    if not output.is_relative_to(ROOT / 'tools/private') or output.exists():
        raise ValueError('use a new private output directory')
    if hashlib.sha256(rom.read_bytes()).hexdigest() != ROM_SHA:
        raise ValueError('unsupported ROM')
    parser = parse_vi_manager if args.vi_manager else parse_interrupt if args.interrupt else parse_trace
    expected = parser(oracle)
    branch_oracle, eret_oracle = args.branch_oracle.resolve(), args.eret_oracle.resolve()
    if not parse_branch(branch_oracle)['counts_annulled_slots_at_two_ticks'] or \
            not parse_eret(eret_oracle)['eret_zero_increment_reference']:
        raise ValueError('independent reference CPU timing not qualified')
    inventory = {row['vram']: row for row in tomllib.loads(symbols.read_text())['section'][0]['functions']}
    vector = oracle.parent / 'vector.tsv'
    if args.interrupt and not args.vi_manager:
        observed = vector.read_text().strip().split('\t')
        image = rom.read_bytes()
        offset = 0x80075020 - 0x80000400 + 0x1000
        original = [f'{int.from_bytes(image[p:p+4], "big"):08x}' for p in range(offset, offset + 16, 4)]
        if observed != ['general-exception-vector', *original]:
            raise ValueError('reference exception vector differs from original preamble')
    todo, functions = list(ENTRY) + ([0x80075020, 0x80075030, 0x800978e0] if args.interrupt else []) + ([SETUP] if args.initialize else []) + ([0x80098a40, 0x80098bb8, 0x80098e30] if args.vi_manager else []), {}
    while todo:
        address = todo.pop()
        if address in functions:
            continue
        row = inventory[address]
        name = row['name'] + '_recomp'
        source = root / 'baseline' / (name + '.c')
        if not source.exists():
            name = row['name']
            source = root / 'support' / (name + '.c')
        content = source.read_text()
        calls = re.findall(r'LOOKUP_FUNC\(0x([0-9A-F]+)\)', content)
        if len(calls) != content.count('LOOKUP_FUNC(') and not (args.interrupt and address in (0x80075020, 0x80075030, 0x800755b0)):
            raise ValueError(f'unexpected indirect OS transfer at {address:08x} ({name})')
        if calls and not 'ctx->r31 = ' in content and 'jal ' in content:
            raise ValueError('original OS needs architectural guest links')
        functions[address] = (name, source)
        todo.extend(int(target, 16) for target in calls)
    output.mkdir()
    fixture = ROOT / ('scripts/phase9_cpu_vi_manager_micro.S' if args.vi_manager else 'scripts/phase9_cpu_interrupt_micro.S' if args.interrupt else 'scripts/phase9_cpu_queue_threads_micro.S')
    if args.pending_mask:
        fixture = ROOT / 'scripts/phase9_cpu_interrupt_mask_micro.S'
    call('mips-linux-gnu-as', '-EB', '-mips3', '-o', output / 'fixture.o', fixture)
    call('mips-linux-gnu-ld', '-Ttext=0x80000400', '-e', '_start', '-o', output / 'fixture.elf', output / 'fixture.o')
    call('mips-linux-gnu-objcopy', '-O', 'binary', '-j', '.text', output / 'fixture.elf', output / 'fixture.bin')
    names = re.findall(r'^([0-9a-f]+) ([0-9a-f]+) T (\w+)$', call('mips-linux-gnu-nm', '-S', output / 'fixture.elf'), re.M)
    payload = (output / 'fixture.bin').read_bytes()
    config = '[input]\nelf_path="fixture.elf"\noutput_func_path="generated"\nuse_mdebug=false\n' \
        'use_lookup_for_all_function_calls=true\nemit_guest_link_registers=true\n' + \
        ('emit_guest_cpu_state=true\nemit_guest_dynamic_returns=true\n' if args.interrupt else '') + '[patches]\n'
    for addr, size, name in names:
        for offset in range(0, int(size, 16), 4):
            pc = int(addr, 16) + offset
            word = int.from_bytes(payload[pc-0x80000400:pc-0x80000400+4], 'big')
            hook = f'jfg_phase9_execution_probe(0U, 0x{pc:08x}U, 0x{word:08x}U, ctx);'
            config += f'[[patches.hook]]\nfunc="{name}"\nbefore_vram=0x{pc:08x}\ntext={json.dumps(hook)}\n'
    (output / 'fixture.toml').write_text(config)
    call(recompiler, output / 'fixture.toml')
    generated = output / 'generated'
    declaration = '\nvoid jfg_phase9_execution_probe(unsigned, unsigned, unsigned, void*);\n'
    header = generated / 'funcs.h'
    header.write_text(header.read_text() + declaration)
    fixture_sources = [p for p in generated.glob('*.c') if 'RECOMP_FUNC void ' in p.read_text()]
    bindings = '#include "recomp.h"\nvoid fixture_setup(uint8_t*,recomp_context*);\n'
    all_names = {**{a: n for a, (n, _) in functions.items()},
                 **{int(a, 16): n for a, _, n in names}}
    for name in all_names.values():
        bindings += f'void {name}(uint8_t*,recomp_context*);\n'
    bindings += 'recomp_func_t* get_function(int32_t address) { switch ((uint32_t)address) {\n'
    if not args.initialize:
        bindings += f'case 0x{SETUP:08x}U: return fixture_setup;\n'
    for address, name in all_names.items():
        bindings += f'case 0x{address:08x}U: return {name};\n'
    bindings += 'default: abort(); } }\n'
    (output / 'bindings.c').write_text(bindings)
    sources = [p for _, p in functions.values()] + fixture_sources + [output / 'bindings.c']
    flags = ['-O1', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-fexceptions']
    if args.interrupt:
        flags.append('-DJFG_TEST_INTERRUPTS=1')
    if args.initialize:
        flags.append('-DJFG_TEST_INITIALIZE=1')
    if args.vi_manager:
        flags.append('-DJFG_TEST_VI_MANAGER=1')
    if args.pending_mask:
        flags.append('-DJFG_TEST_PENDING_MASK=1')
    objects = []
    for index, source in enumerate(sources):
        obj = output / f'body{index}.o'
        call('gcc', '-std=c11', *flags, '-I', root / 'include', '-I', root,
             '-D_start=queue_fixture_start', '-c', source, '-o', obj)
        objects.append(obj)
    driver = ROOT / 'tests/generated_os_threads.cpp'
    executor = ROOT / 'src/boot/executor.cpp'
    call('g++', '-std=c++20', *flags, '-pthread', '-I', root / 'include', '-I', ROOT / 'include',
         driver, executor, *objects, '-o', output / 'threads-test')
    command = [str(output / 'threads-test'), str(rom)]
    if args.initialize:
        command.append(str(output / 'initialization.tsv'))
    if args.pending_mask:
        command.append(str(output / 'exceptions.tsv'))
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    trace = output / ('cpu-vi_manager.tsv' if args.vi_manager else 'cpu-interrupt.tsv' if args.interrupt else 'cpu-queue_threads.tsv')
    trace.write_text(result.stdout)
    (output / 'stderr.log').write_text(result.stderr)
    result.check_returncode()
    actual = parser(trace)
    if args.vi_manager:
        # This isolates the steady-state worker, NOT IPL phase qualification.
        # Origins remain in artifacts; compare 23 intervals and message/state
        # transitions without asserting that the first interrupt is aligned.
        def steady(result):
            rows = result['cases']
            return [{'payload': r['payload'], 'status': r['status'],
                     'vi_count': r['vi_count'] - rows[0]['vi_count'],
                     'count': (r['count'] - rows[0]['count']) & 0xffffffff,
                     'time': (r['time_lo'] - rows[0]['time_lo']) & 0xffffffff,
                     'worker_to_receive': (r['count'] - r['time_lo']) & 0xffffffff}
                    for r in rows]
        mismatches = [] if steady(expected) == steady(actual) else ['vi-worker-steady-state']
    else:
        mismatches = [key for key in expected if expected[key] != actual[key]]
    if args.pending_mask:
        # Absolute fixture Count origins differ; preserve and compare exact
        # exception causes and architectural EPCs, without shifting any PC.
        def exception_sites(path, oracle_startup=False):
            lines = path.read_text().splitlines()
            # The independent ROM can retain an IPL VI pending before the
            # measured main-loop fixture. Keep it in the artifact, but do not
            # claim that our deliberately origin-free fixture models IPL.
            if oracle_startup and len(lines) == 12 and lines[1].startswith('00000400\t'):
                lines = [lines[0], *lines[2:]]
            if len(lines) != 11 or lines[0] != 'cause\tepc\tcount':
                raise ValueError('ten exception observations required')
            return [line.split('\t')[:2] for line in lines[1:]]
        if exception_sites(oracle.parent / 'exceptions.tsv', True) != exception_sites(output / 'exceptions.tsv'):
            mismatches.append('exception-boundaries')
    if args.initialize and not args.vi_manager:
        reference_init = oracle.parent / 'initialization.tsv'
        def init_rows(path):
            rows = [line.split('\t') for line in path.read_text().splitlines()]
            if len(rows) != 2 or [r[0] for r in rows] != ['entry', 'return']:
                raise ValueError('incomplete initialization capture')
            parsed = [dict(item.split('=') for item in row[1:]) for row in rows]
            # Absolute Count originates at the private ROM boot. Compare the
            # measured original function interval, not a copied clock offset.
            ticks = (int(parsed[1].pop('CP0 REG9'), 16) - int(parsed[0].pop('CP0 REG9'), 16)) & 0xffffffff
            return parsed, ticks
        if init_rows(reference_init) != init_rows(output / 'initialization.tsv'):
            mismatches.append('initialization')
    inputs = [fixture, driver, executor, recompiler, oracle, branch_oracle, eret_oracle,
              ROOT / 'scripts/phase9_cpu_branch_trace.py', ROOT / 'scripts/phase9_cpu_eret_trace.py',
              symbols, root / 'include/recomp.h',
              ROOT / 'include/jfg/boot/mi_interrupt_mask.hpp',
              ROOT / 'include/jfg/boot/guest_thread_transport.hpp',
              ROOT / 'include/jfg/boot/reference_pif_boot.hpp',
              ROOT / 'include/jfg/boot/reference_cache.hpp', ROOT / 'include/jfg/boot/tlb.hpp',
              *sources, Path(__file__)]
    if args.interrupt and not args.vi_manager:
        inputs.append(vector)
    if args.pending_mask:
        inputs.extend([ROOT / 'scripts/phase9_cpu_interrupt_micro.S', oracle.parent / 'exceptions.tsv'])
    if args.initialize and not args.vi_manager:
        inputs.append(reference_init)
    manifest = {'kind': 'jfg-original-os-thread-handoff', 'acceptance': False,
        'initialization_qualified': args.initialize and not args.vi_manager and not mismatches,
        'interrupt_fixture': args.interrupt, 'vi_manager_fixture': args.vi_manager,
        'pending_mask_fixture': args.pending_mask,
        'initial_vi_phase_qualified': False,
        'os_body_closure': [f'{a:08x}' for a in sorted(functions)],
        'mismatches': mismatches, 'expected': expected, 'actual': actual,
        'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    (output / 'result.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))
    return 1 if mismatches else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--interrupt', action='store_true')
    parser.add_argument('--initialize', action='store_true')
    parser.add_argument('--vi-manager', action='store_true')
    parser.add_argument('--pending-mask', action='store_true')
    for key in ('root', 'symbols', 'rom', 'oracle', 'branch-oracle', 'eret-oracle', 'recompiler'):
        parser.add_argument('--' + key, type=Path, required=True)
    try:
        raise SystemExit(run(parser.parse_args()))
    except subprocess.CalledProcessError as error:
        print(error.stdout, error.stderr)
        raise
