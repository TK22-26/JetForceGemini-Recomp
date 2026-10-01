"""Execute private original SP task loading and compare with a black-box probe.

Resolve bodies by pinned symbol addresses, not unstable generated ordinals.
No OS implementation is transcribed into this ROM-free driver.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tomllib

from scripts.phase9_cpu_rsp_trace import parse_trace
from scripts.phase9_cpu_branch_trace import parse_trace as parse_branch_trace

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CLOSURE = {0x8009905c, 0x800991bc, 0x80098f40, 0x80098030, 0x80098050,
                    0x8009b920, 0x8009b960, 0x8009b9f0, 0x80096ea0, 0x8009ad00, 0x80099950}
FIELDS = 'case sp_mem sp_dram read_length dma_full dma_busy sp_pc sp_status task_dmem boot_imem'.split()


def load_observations(path, native=False):
    lines = path.read_text().splitlines()
    header = [FIELDS[0], 'load_instructions', 'load_annulled', 'start_instructions', *FIELDS[1:]] if native else FIELDS
    if len(lines) != 18 or lines[0].split('\t') != header or \
            lines[-1] != ('passed\t16' if native else 'result\ttrue\t16'):
        raise ValueError('incomplete task load observations')
    rows = list(csv.DictReader(lines[:-1], delimiter='\t'))
    for index, row in enumerate(rows, 1):
        if set(row) != set(header) or any(value is None for value in row.values()) or row['case'] != str(index):
            raise ValueError('malformed task load observation')
        for key in header:
            if key in ('task_dmem', 'boot_imem'):
                if re.fullmatch('[0-9a-f]{%d}' % (128 if key == 'task_dmem' else 768), row[key]) is None:
                    raise ValueError('malformed DMA content')
            elif not row[key].isdecimal() or not 0 <= int(row[key]) <= 0xffffffff:
                raise ValueError('malformed task load register')
    return rows


def run(output, root, symbols, rom, oracle, branch_oracle):
    output, root, symbols, rom, oracle = (p.resolve() for p in (output, root, symbols, rom, oracle))
    if not output.is_relative_to(ROOT / 'tools/private') or output.exists():
        raise ValueError('use a new private output directory')
    if hashlib.sha256(rom.read_bytes()).hexdigest() != '159dde164c475976a3e527fbb20978431d4765f2c63019b3530c3aa8772595aa':
        raise ValueError('unsupported original ROM')
    reference = load_observations(oracle / 'rsp-loads.tsv')
    timing = parse_trace(oracle / 'cpu-rsp.tsv')['cases']
    branch_oracle = branch_oracle.resolve(strict=True)
    if not parse_branch_trace(branch_oracle)['counts_annulled_slots_at_two_ticks']:
        raise ValueError('reference did not qualify annulled-slot accounting')
    inventory = tomllib.loads(symbols.read_text())['section'][0]['functions']
    rows = {row['vram']: row for row in inventory}
    todo, functions = [0x8009905c, 0x800991bc], {}
    while todo:
        address = todo.pop()
        if address in functions:
            continue
        if address not in EXPECTED_CLOSURE or address not in rows:
            raise ValueError('unexpected task load call closure')
        name = rows[address]['name'] + '_recomp'
        source = root / 'baseline' / (name + '.c')
        text = source.read_text()
        first = re.search(r'jfg_phase9_execution_probe\(0U, 0x([0-9a-f]{8})U,', text)
        if first is None or int(first[1], 16) != address:
            raise ValueError('source is not the original observed entry')
        calls = re.findall(r'LOOKUP_FUNC\(0x([0-9A-F]+)\)', text)
        if len(calls) != text.count('LOOKUP_FUNC('):
            raise ValueError('unqualified indirect call')
        functions[address] = (name, source)
        todo.extend(int(call, 16) for call in calls)
    if set(functions) != EXPECTED_CLOSURE:
        raise ValueError('incomplete original task load closure')
    output.mkdir()
    binding = '#include "recomp.h"\n'
    for name, _ in functions.values():
        binding += f'void {name}(uint8_t*, recomp_context*);\n'
    binding += 'recomp_func_t* get_function(int32_t address) { switch ((uint32_t)address) {\n'
    for address, (name, _) in functions.items():
        binding += f'case 0x{address:08x}U: return {name};\n'
    binding += 'default: abort(); } }\n'
    (output / 'bindings.c').write_text(binding)
    flags = ['-O1', '-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    sources = [source for _, source in functions.values()] + [output / 'bindings.c']
    objects = []
    for index, source in enumerate(sources):
        obj = output / f'load{index}.o'
        subprocess.run(list(map(str, ['gcc', '-std=c11', *flags, '-I', root / 'include',
            '-I', root, '-c', source, '-o', obj])), check=True, timeout=120)
        objects.append(obj)
    driver = ROOT / 'tests/generated_os_sp_load.cpp'
    subprocess.run(list(map(str, ['g++', '-std=c++20', *flags, '-I', root / 'include',
        '-I', ROOT / 'include', driver, *objects, '-o', output / 'sp-load-test'])), check=True, timeout=120)
    result = subprocess.run([str(output / 'sp-load-test'), str(rom)], capture_output=True, text=True, timeout=120)
    (output / 'cases.tsv').write_text(result.stdout)
    (output / 'stderr.log').write_text(result.stderr)
    result.check_returncode()
    actual = load_observations(output / 'cases.tsv', native=True)
    mismatches = []
    for row, expected, ticks in zip(actual, reference, timing):
        differing = [key for key in FIELDS if row[key] != expected[key]]
        for function in ('load', 'start'):
            # Independently measured branch micro-ROM, not a fitted load cost:
            # Mupen charges an annulled likely slot although it has no effects.
            annulled = int(row['load_annulled']) if function == 'load' else 0
            if (int(row[function + '_instructions']) + annulled) * 2 + 6 != ticks[function + '_ticks']:
                differing.append(function + '_ticks')
        if differing:
            mismatches.append({'case': row['case'], 'fields': differing})
    inputs = [*sources, root / 'include/recomp.h', root / 'funcs.h', symbols, driver,
        ROOT / 'include/jfg/boot/reference_sp_dma.hpp', ROOT / 'include/jfg/boot/sp_status.hpp',
        ROOT / 'include/jfg/boot/reference_cache.hpp', oracle / 'rsp-loads.tsv', oracle / 'cpu-rsp.tsv',
        branch_oracle, ROOT / 'scripts/phase9_cpu_branch_trace.py', Path(__file__)]
    manifest = {'kind': 'jfg-private-generated-os-sp-load', 'acceptance': False,
                'cases': 16, 'sanitizers': ['address', 'undefined'], 'mismatches': mismatches,
                'reference_profile_only': True, 'game_clock_integrated': False,
                'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    (output / 'result.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if mismatches:
        raise ValueError('task load differs from reference; see result.json')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    for name in ('root', 'symbols', 'rom', 'oracle', 'branch-oracle'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.root, args.symbols, args.rom, args.oracle, args.branch_oracle)))
