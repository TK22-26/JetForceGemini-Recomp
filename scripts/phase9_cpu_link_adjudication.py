"""Revalidate a link-register oracle repair against independent CPU evidence.

This is a deterministic proof artifact, not a model verdict, automatic oracle
promotion, or complete CPU/game qualification. It executes no supplied commands.
"""
import argparse
import json
from pathlib import Path

from scripts.phase95_bridge import digest, runtime_digest
from scripts.phase9_cpu_links_trace import parse_trace, verify_payload

ROOT = Path(__file__).resolve().parents[1]


def check_capture(directory, rom, core, cpu, pins):
    files = [directory / name for name in ('result.json','manifest.json','cpu-links.tsv','input-config.json')]
    pins.update({str(path):digest(path) for path in files})
    result, manifest, config = [json.loads(files[index].read_text(encoding='utf-8-sig'))
        for index in (0, 1, 3)]
    identity = {'schema', 'kind', 'acceptance', 'core', 'rom_sha256',
                'config_sha256', 'input_config_sha256', 'script_sha256',
                'emulator_sha256', 'runtime_sha256'}
    if not identity.issubset(manifest) or manifest.get('acceptance') is not False:
        raise ValueError('link capture manifest identity is incomplete')
    if (result.get('schema') != 1 or result.get('kind') != 'jfg-phase9-cpu-links-microtest' or
            result.get('complete') is not True or result.get('exit_code') != 0 or result.get('core') != core or
            result.get('rom_sha256') != digest(rom) or result.get('trace_sha256') != digest(files[2]) or
            result.get('config_sha256') != digest(files[3]) or
            result.get('input_config_sha256') != digest(files[3]) or
            any(result.get(key) != value for key,value in manifest.items())):
        raise ValueError('link capture identity or completion differs')
    if config.get('PreferredCores',{}).get('N64') != core:
        raise ValueError('link core configuration differs')
    if cpu is not None:
        sync = config.get('CoreSyncSettings',{}).get('BizHawk.Emulation.Cores.Nintendo.N64.N64',{})
        if (type(sync.get('Core')) is not int or sync['Core'] != cpu or
                type(manifest.get('mupen_cpu_core_override')) is not int or
                manifest['mupen_cpu_core_override'] != cpu):
            raise ValueError('link interpreter configuration differs')
    elif 'mupen_cpu_core_override' in manifest:
        raise ValueError('link reference cannot override the Mupen interpreter')
    if (result.get('script_sha256') != digest(ROOT/'scripts/phase9_cpu_links_probe.lua') or
            result.get('emulator_sha256') != digest(directory/'emulator/EmuHawk.exe') or
            result.get('runtime_sha256') != runtime_digest(directory/'emulator')):
        raise ValueError('link capture producer changed')
    observed = parse_trace(files[2])
    if result.get('observed') != observed:
        raise ValueError('link raw trace contradicts reported observation')
    payload = verify_payload(rom, observed)
    return result, payload


def classify(baseline, reference, cached, pure):
    observations = [item['observed'] for item in (baseline,reference,cached,pure)]
    if ([row['case'] for row in observations[0]['mismatches']] != list(range(12)) or
            observations[0]['matches_vr4300_manual'] is not False or
            any(item['matches_vr4300_manual'] is not True or item['mismatches'] for item in observations[1:])):
        raise ValueError('link repair lacks the independently required red/green cases')
    if observations[1] != observations[2] or observations[1] != observations[3]:
        raise ValueError('repaired interpreters do not reproduce independent raw cases')
    if (cached['runtime_sha256'] != pure['runtime_sha256'] or
            cached['runtime_sha256'] == baseline['runtime_sha256']):
        raise ValueError('link repair runtime identity is not distinct and consistent')
    return {'baseline_failures':12,'reference_passes':12,'cached_passes':12,'pure_passes':12,
            'hardware_tested':False,'clock_alignment_validated':False,
            'game_cause_proved':False,'oracle_promoted':False}


def run(output, rom, baseline, reference, cached, pure, build):
    output,rom,baseline,reference,cached,pure,build = [p.resolve() for p in
        (output,rom,baseline,reference,cached,pure,build)]
    private = ROOT/'tools/private'
    if output.exists() or not output.is_relative_to(private) or any(
            not p.is_relative_to(private) for p in (rom,baseline,reference,cached,pure,build)):
        raise ValueError('link qualification requires private evidence and a new output')
    paths = [Path(__file__),ROOT/'scripts/phase9_cpu_links_trace.py',
             ROOT/'scripts/phase9_cpu_links_probe.lua',ROOT/'scripts/phase9_cpu_links_micro.S',
             ROOT/'scripts/oracle_guest_links.patch',rom,build,build.parent/'repair-build.guard.json',
             build.parent/'repair-build.stdout',build.parent/'repair-build.stderr']
    pins = {str(path):digest(path) for path in paths}
    receipts, payloads = [], []
    for directory,core,cpu in ((baseline,'Mupen64Plus',1),(reference,'Ares64',None),
                                (cached,'Mupen64Plus',1),(pure,'Mupen64Plus',0)):
        receipt,payload = check_capture(directory,rom,core,cpu,pins)
        receipts.append(receipt); payloads.append(payload)
    verdict = classify(*receipts)
    producer = json.loads(build.read_text())
    if (producer.get('kind') != 'jfg-oracle-guest-links-repair-build' or
            producer.get('complete') is not True or producer.get('exit_code') != 0 or
            producer.get('stop_reason') is not None or producer.get('observation_only') is not False or
            producer.get('runtime_sha256') != receipts[2]['runtime_sha256'] or
            json.loads(paths[7].read_text()).get('state') != 'finished' or
            {name.replace('\\','/') for name in producer.get('changed_source_files',[])} !=
                {'src/r4300/r4300.c','src/r4300/pure_interp.c'}):
        raise ValueError('link candidate build record differs')
    sources = producer.get('source_files',{})
    if not sources or any(digest(build.parent/'mupen64plus-core'/name) != sha for name,sha in sources.items()):
        raise ValueError('link candidate source changed')
    pins.update({str(build.parent/'mupen64plus-core'/name):sha for name,sha in sources.items()})
    libraries = list((build.parent/'emulator').rglob('mupen64plus.dll'))
    if (len(libraries) != 1 or digest(libraries[0]) != producer.get('dll_sha256') or
            runtime_digest(build.parent/'emulator') != producer['runtime_sha256']):
        raise ValueError('link candidate build runtime changed')
    if any(digest(Path(path)) != sha for path,sha in pins.items()):
        raise ValueError('link evidence changed during qualification')
    for directory, receipt in zip((baseline, reference, cached, pure), receipts):
        if runtime_digest(directory/'emulator') != receipt['runtime_sha256']:
            raise ValueError('link capture runtime changed during qualification')
    if runtime_digest(build.parent/'emulator') != producer['runtime_sha256']:
        raise ValueError('link build runtime changed during qualification')
    report = {'schema':1,'kind':'jfg-oracle-link-adjudication','passed':True,**verdict,
        'candidate_runtime_sha256':producer['runtime_sha256'],'payloads':payloads,
        'evidence':pins,'build_closure_verified':False,
        'manual_reference':'NEC U10504EJ7V0UM00 chapter 16, JAL/JALR and REGIMM link forms',
        'manual_url':'https://hack64.net/docs/VR43XX.pdf'}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    for key in ('rom','baseline','reference','cached','pure','build'):
        parser.add_argument('--'+key,type=Path,required=True)
    args = parser.parse_args()
    report = run(**vars(args))
    print(json.dumps({key:value for key,value in report.items() if key not in ('evidence','payloads')}))
