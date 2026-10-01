"""Compile actual generated/normalized interior-entry hooks: protected red/green.

Run under WSL. The baseline is expected to fail exactly the three interior
entries while ordinary entry passes; the candidate must pass all four. No ROM,
game clock, comparison field, runtime or writer gate is patched by this test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from scripts.build_private_generated_root import add_continuation_dispatch

ROOT = Path(__file__).resolve().parents[1]


def run(output, baseline, candidate, include):
    output = output.resolve()
    if not output.is_relative_to(ROOT / "tools/private") or output.exists():
        raise ValueError("continuation proof output must be new and private")
    inputs = [Path(__file__), ROOT / 'scripts/build_private_generated_root.py',
              ROOT / 'tests/fixtures/instruction_continuation.S', ROOT / 'tests/generated_instruction_continuation.cpp',
              baseline.resolve(strict=True), candidate.resolve(strict=True), include.resolve(strict=True) / 'recomp.h']
    pins = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    output.mkdir()
    commands = []
    def command(args, expected=0):
        args = [str(arg) for arg in args]
        result = subprocess.run(args, cwd=output, capture_output=True, text=True, timeout=180)
        index = len(commands)
        (output / f'command-{index}.stdout').write_text(result.stdout)
        (output / f'command-{index}.stderr').write_text(result.stderr)
        commands.append({'argv':args,'exit_code':result.returncode,'expected_exit_code':expected})
        if result.returncode != expected:
            raise ValueError(f'continuation proof command {index} returned {result.returncode}: {result.stderr[-1000:]}')
        return result.stdout
    command(['mips-linux-gnu-as','-march=vr4300','-32','-o','test.o',inputs[2]])
    command(['mips-linux-gnu-ld','-Ttext=0x80001000','-e','continuation_effect','-o','test.elf','test.o'])
    row = {'name':'continuation_effect','section':7,'offset':0x100,'vram':0x80001000,'size':20}
    continuations = [{**row,'offset':0x100+n*4,'vram':0x80001000+n*4} for n in (1,2,3)]
    results = {}
    for name,compiler,expected in (('baseline',inputs[4],1),('candidate',inputs[5],0)):
        config = ['[input]','elf_path = "test.elf"',f'output_func_path = "{name}"',
                  'use_mdebug = false','emit_guest_link_registers = true','emit_guest_dynamic_returns = true','[patches]']
        for pc in range(0x80001000,0x80001014,4):
            for field,phase in (('before_vram',0),('after_vram',1)):
                text = ('extern void continuation_observe(unsigned, unsigned, recomp_context*); '
                        f'continuation_observe({phase}U, 0x{pc:08x}U, ctx);')
                config += ['[[patches.hook]]','func = "continuation_effect"',f'{field} = 0x{pc:08x}',f'text = {json.dumps(text)}']
        path=output/(name+'.toml'); path.write_text('\n'.join(config)+'\n')
        command([compiler,path])
        generated=list((output/name).glob('*.c'))
        if len(generated)!=1:
            raise ValueError('expected exactly one generated body')
        normalized=output/(name+'-normalized.c')
        normalized.write_text(add_continuation_dispatch(generated[0].read_text(),row,continuations))
        flags=['-O1','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer']
        command(['gcc','-std=c11',*flags,'-I',include.resolve(),'-I',generated[0].parent,'-c',normalized,'-o',name+'.o'])
        command(['g++','-std=c++20',*flags,'-I',include.resolve(),inputs[3],name+'.o','-o',name+'-test'])
        result=command([output/(name+'-test')],expected)
        correct = ('0\tpass\t7\t10\n1\tfail\t6\t8\n2\tfail\t4\t6\n3\tfail\t0\t4\nfailures\t3\n'
                   if name=='baseline' else
                   '0\tpass\t7\t10\n1\tpass\t6\t8\n2\tpass\t4\t6\n3\tpass\t0\t4\nfailures\t0\n')
        if result != correct:
            raise ValueError('continuation proof had unexpected failure shape: '+result)
        results[name]=result
    if pins != {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}:
        raise ValueError('continuation proof inputs changed')
    report={'schema':1,'kind':'jfg-generated-continuation-hook-proof','passed':True,'inputs':pins,
            'commands':commands,'results':results,'baseline_failed_cases':3,'candidate_passed_cases':4,
            'game_causal_fix_proved':False,'parity_verified':False}
    (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--include',type=Path,required=True)
    args=parser.parse_args()
    report=run(args.output,args.baseline,args.candidate,args.include)
    print(json.dumps({key:report[key] for key in ('passed','baseline_failed_cases','candidate_passed_cases','game_causal_fix_proved')}))
