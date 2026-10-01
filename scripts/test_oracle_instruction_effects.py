"""Compile exact engine dispatch/jump/ERET/exception bodies with the observer.

The surrounding CPU/device transport is controlled. Game captures remain a
separate acceptance gate, not inferred from these extracted-body tests.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from scripts.test_oracle_cpu_boundaries import body
from scripts.phase9_oracle_instruction_effects import records

ROOT = Path(__file__).resolve().parents[1]


def run(output, control, observed):
    output, control, observed = [path.resolve() for path in (output, control, observed)]
    if output.exists() or not output.is_relative_to(ROOT/'tools/private'):
        raise ValueError('use a new private proof directory')
    output.mkdir()
    files = [Path(__file__), ROOT/'scripts/test_oracle_cpu_boundaries.py',
        ROOT/'scripts/oracle_instruction_effects.c', ROOT/'scripts/oracle_instruction_effects.h',
        ROOT/'scripts/oracle_cpu_boundaries.h', ROOT/'scripts/phase9_oracle_instruction_effects.py',
        ROOT/'tests/oracle_instruction_effect_tests.c']
    files += [source/'src/r4300'/name for source in (control, observed)
              for name in ('r4300.c', 'interpreter_tlb.def', 'exception.c', 'recomp.c', 'recomp.h')]
    def pins(): return {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    before, commands = pins(), []
    def command(argv):
        argv = list(map(str, argv))
        env = {k:v for k,v in os.environ.items() if not k.upper().startswith('JFG_')}
        result = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=180)
        index = len(commands)
        (output/f'command-{index}.stdout').write_text(result.stdout)
        (output/f'command-{index}.stderr').write_text(result.stderr)
        commands.append({'argv':argv, 'exit_code':result.returncode})
        if result.returncode:
            raise ValueError(f'command {index} failed: {result.stderr[-1600:]}')
        return result.stdout
    try:
        stdout = []
        for name, source, mode in (('baseline',control,'disabled'), ('control',observed,'disabled'), ('observed',observed,'observed')):
            dest = output/name; dest.mkdir()
            core = source/'src/r4300'
            text = (core/'r4300.c').read_text()
            start, end = text.index('#define DECLARE_JUMP('), text.index('#define CHECK_MEMORY()')
            (dest/'oracle_jump_macro.inc').write_text(text[start:end])
            for filename, original, marker in (
                    ('oracle_dispatch_body.inc', 'r4300.c', 'static void jfg_observed_cached_execute(void)\n{'),
                    ('oracle_eret_body.inc', 'interpreter_tlb.def', 'DECLARE_INSTRUCTION(ERET)'),
                    ('oracle_exception_body.inc', 'exception.c', 'void exception_general(void)')):
                (dest/filename).write_text(body(core/original, marker))
            binary = dest/'test'
            command(['gcc','-std=c11','-D_POSIX_C_SOURCE=200809L','-O1','-Wall','-Wextra','-Werror',
                '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',
                '-I',ROOT/'scripts','-I',dest,ROOT/'tests/oracle_instruction_effect_tests.c','-o',binary])
            stdout.append(command([binary,dest,mode]))
        if len(set(stdout)) != 1 or not stdout[0].startswith('passed\t12\t'):
            raise ValueError('observer changed independently checked fixture results')
        rows = list(records(output/'observed/oracle-effects.bin',1))
        phases = [row['phase'] for row in rows]
        # Twelve top-level instructions plus four executed slots. The untaken
        # likely slot and the fast-forwarded idle slot must not appear.
        if phases.count('entry') != 16 or phases.count('branch') != 5 or phases.count('idle') != 1 or phases.count('eret') != 2 or phases.count('exception') != 1:
            raise ValueError(f'compiled observation path inventory differs: {phases}')
        # The first JAL's link is visible before its slot, not after returning.
        jump = next(i for i,row in enumerate(rows) if row['phase']=='branch' and row['opcode']==0x0c000404)
        if rows[jump]['gpr'][31] != 0xffffffff80001008 or rows[jump+1]['pc'] != 0x80001004:
            raise ValueError('observed link/slot order differs')
        for mode in ('bad-core','missing-effect','overlap','budget'):
            directory = output/mode; directory.mkdir()
            command([output/'observed/test', directory, mode])
            trace = directory/'oracle-effects.bin'
            if trace.exists():
                try: list(records(trace,1))
                except ValueError: pass
                else: raise ValueError('rejected capture has a valid footer')
        if before != pins(): raise ValueError('source changed during proof')
        report = {'kind':'jfg-oracle-instruction-effects-proof','passed':True,'cases':12,'rejections':4,
            'rows':len(rows),'sanitizers':['address','undefined'],'inputs':before,'commands':commands,
            'game_nonperturbation_verified':False,'hardware_tested':False,'parity_verified':False}
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        (output/'failure.json').write_text(json.dumps({'passed':False,'error':str(error),'commands':commands},indent=2)+'\n')
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--control',type=Path,required=True)
    parser.add_argument('--observed',type=Path,required=True)
    result = run(**vars(parser.parse_args()))
    print(json.dumps({k:v for k,v in result.items() if k not in ('inputs','commands')}))
