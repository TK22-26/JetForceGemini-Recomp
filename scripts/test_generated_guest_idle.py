"""Regenerate and execute original ROM-free self-loop/delay-slot fixtures."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(output, recompiler, include):
    output, recompiler, include = output.resolve(), recompiler.resolve(strict=True), include.resolve(strict=True)
    if not output.is_relative_to(ROOT / 'tools/private') or output.exists():
        raise ValueError('use a new private output')
    output.mkdir()
    def call(*args):
        return subprocess.run(list(map(str, args)), text=True, capture_output=True, check=True, timeout=120).stdout
    fixture, driver = ROOT / 'tests/fixtures/guest_idle_loop.S', ROOT / 'tests/generated_guest_idle.cpp'
    call('mips-linux-gnu-as', '-EB', '-mips3', '-o', output / 'idle.o', fixture)
    call('mips-linux-gnu-ld', '-Ttext=0x80000400', '-e', 'idle_branch', '-o', output / 'idle.elf', output / 'idle.o')
    config = '[input]\nelf_path="idle.elf"\noutput_func_path="generated"\nuse_mdebug=false\nemit_guest_idle_loops=true\n[patches]\n'
    for name, entry in (('idle_branch', 0x80000400), ('idle_jump', 0x80000408)):
        for pc in (entry, entry + 4):
            code = f'extern void idle_probe(unsigned, recomp_context*); idle_probe(0x{pc:08x}U, ctx);'
            config += f'[[patches.hook]]\nfunc="{name}"\nbefore_vram=0x{pc:08x}\ntext={json.dumps(code)}\n'
    (output / 'config.toml').write_text(config)
    call(recompiler, output / 'config.toml')
    sources = [p for p in (output / 'generated').glob('*.c') if 'RECOMP_FUNC void' in p.read_text()]
    if not sources or any('pause_self(' in p.read_text() for p in sources):
        raise ValueError('idle profile still emits host park')
    control = config.replace('output_func_path="generated"', 'output_func_path="control"').replace('emit_guest_idle_loops=true', 'emit_guest_idle_loops=false')
    (output / 'control.toml').write_text(control)
    call(recompiler, output / 'control.toml')
    if sum(p.read_text().count('pause_self(') for p in (output / 'control').glob('*.c')) != 2:
        raise ValueError('legacy idle default changed')
    (output / 'invalid.toml').write_text(control.replace('emit_guest_idle_loops=false', 'emit_guest_idle_loops="true"'))
    rejected = subprocess.run([str(recompiler), str(output / 'invalid.toml')], capture_output=True, text=True, timeout=30)
    if rejected.returncode == 0 or 'emit_guest_idle_loops must be a boolean' not in rejected.stderr:
        raise ValueError('idle config type validation missing')
    flags = ['-O1', '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fexceptions']
    objects = []
    for i, source in enumerate(sources):
        obj = output / f'body{i}.o'
        call('gcc', '-std=c11', *flags, '-I', include, '-c', source, '-o', obj)
        objects.append(obj)
    call('g++', '-std=c++20', *flags, '-I', include, driver, *objects, '-o', output / 'idle-test')
    result = subprocess.run([str(output / 'idle-test')], capture_output=True, text=True, timeout=30)
    (output / 'stdout.log').write_text(result.stdout)
    (output / 'stderr.log').write_text(result.stderr)
    result.check_returncode()
    if result.stderr or result.stdout != 'generated idle-loop delay slots: 8 cases passed\n':
        raise ValueError('idle execution mismatch or sanitizer diagnostics')
    inputs = [fixture, driver, recompiler, include / 'recomp.h', *sources, Path(__file__)]
    manifest = {'kind': 'jfg-generated-idle-loop-test', 'acceptance': False, 'cases': 8,
                'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    (output / 'result.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--recompiler', type=Path, required=True)
    parser.add_argument('--include', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.output, args.recompiler, args.include)))
    except subprocess.CalledProcessError as error:
        print(error.stdout, error.stderr)
        raise
