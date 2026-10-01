"""Requalify paired instruction captures before admitting a bounded finding.

Builds remain experimental and clocks remain raw. This does not import an old
success flag, promote a runtime, or authorize a repair from a register mismatch.
"""
import json
from pathlib import Path
import tempfile

from scripts.autonomy import device_observation, source_build
from scripts.autonomy.point_plan import validate_probe
from scripts.autonomy.supervisor import file_sha256
from scripts.phase95_bridge import runtime_digest
from scripts.phase95_poll_compare import compare as compare_polls, native_polls
from scripts import phase9_instruction_effect_trace as native_effects
from scripts import phase9_oracle_instruction_effects as oracle_effects
from scripts import phase9_eret_transfers as erets, phase9_oracle_cpu_boundaries as boundaries
from scripts.phase9_instruction_effect_witnesses import bind as bind_native
from scripts.phase9_oracle_effect_witnesses import bind as bind_oracle
from scripts.phase9_instruction_correspondence import compare, qualify_vector_snapshots

FIELDS = {'schema', 'kind', 'native', 'native_control', 'oracle', 'oracle_control',
          'native_build', 'oracle_build', 'probe', 'window', 'update'}


def private_directory(repo, value):
    if not isinstance(value, str):
        raise ValueError('instruction evidence directory must be a path')
    path = Path(value).resolve(strict=True)
    if not path.is_dir() or not path.is_relative_to(repo.resolve() / 'tools/private'):
        raise ValueError('instruction evidence escaped private storage')
    return path


def validate_request(repo, request):
    if (not isinstance(request, dict) or set(request) != FIELDS or type(request['schema']) is not int or
            request['schema'] != 1 or request['kind'] != 'instruction-observation-request'):
        raise ValueError('instruction observation request schema differs')
    window, update = request['window'], request['update']
    if (not isinstance(window, list) or len(window) != 2 or any(type(u) is not int for u in window) or
            type(update) is not int or not 1 <= window[0] <= update <= window[1] <= 1000000 or
            window[1] - window[0] >= 16):
        raise ValueError('instruction observation window is invalid')
    validate_probe(request['probe'])
    directories = {key: private_directory(repo, request[key]) for key in
                   ('native', 'native_control', 'oracle', 'oracle_control')}
    if len(set(directories.values())) != 4:
        raise ValueError('instruction observations require distinct off/on captures')
    for key in ('native_build', 'oracle_build'):
        source_build.pinned_file(repo, request[key])
    return directories


def oracle_build(repo, binding):
    """Validate this local observer-build format, not older copied receipts."""
    path = source_build.pinned_file(repo, binding)
    report = json.loads(path.read_text())
    base, files = path.parent, report.get('source_files')
    if (type(report.get('schema')) is not int or report.get('schema') != 1 or
            report.get('kind') != 'jfg-oracle-instruction-effects-build' or
            report.get('complete') is not True or type(report.get('exit_code')) is not int or report.get('exit_code') != 0 or
            report.get('stop_reason') is not None or report.get('cached_interpreter_only') is not True or
            not isinstance(files, dict) or not files or len(files) > 4096):
        raise ValueError('oracle instruction-effect build is not complete')
    support = [base / ('effect-build' + suffix) for suffix in ('.guard.json', '.stdout', '.stderr')]
    if json.loads(support[0].read_text()).get('state') != 'finished':
        raise ValueError('oracle effect build has no completed process guard')
    core = (base / 'mupen64plus-core').resolve(strict=True)
    for name, sha in files.items():
        source = (core / name).resolve(strict=True)
        if not source.is_file() or not source.is_relative_to(core) or file_sha256(source) != sha:
            raise ValueError('oracle effect source changed')
        support.append(source)
    for name in ('oracle_instruction_effects.c', 'oracle_instruction_effects.h'):
        source = core / 'src/r4300' / name
        if source not in support or file_sha256(source) != file_sha256(repo / 'scripts' / name):
            raise ValueError('oracle effect observer differs from qualified reader producer')
    command = report.get('command', [])
    if (len(command) < 2 or Path(command[0]).name.lower() != 'msbuild.exe' or
            Path(command[1]).resolve() != core / 'projects/msvc/mupen64plus-core.vcxproj' or
            any(arg not in command for arg in ('/p:Configuration=Release', '/p:Platform=x64', '/t:Rebuild'))):
        raise ValueError('oracle effect build command differs')
    image = base / 'emulator'
    libraries = list(image.rglob('mupen64plus.dll'))
    if (len(libraries) != 1 or file_sha256(libraries[0]) != report.get('dll_sha256') or
            runtime_digest(image) != report.get('runtime_sha256')):
        raise ValueError('oracle effect runtime changed')
    return report, [path, *support]


def capture_files(directory, side, metadata, window):
    names = (['retrace-hashes.jsonl.updates.jsonl', 'retrace-hashes.jsonl', 'controller.input',
              'controller-polls.tsv', 'eret-transfers.tsv'] if side == 'native' else
             ['update-hashes.jsonl', 'retrace-hashes.jsonl', 'consumed-vi-hashes.jsonl',
              'checkpoints.tsv', 'cpu-boundaries.tsv'])
    names += ['point-probe.tsv', 'device-events.tsv']
    names += [f'focus-update-{u}.rdram' for u in range(window[0], window[1] + 1)]
    if side == 'oracle':
        checkpoints = metadata.get('checkpoints')
        if (not isinstance(checkpoints, list) or not 1 <= len(checkpoints) <= 16 or
                any(type(n) is not int or not 1 <= n <= 1000000 for n in checkpoints) or
                len(set(checkpoints)) != len(checkpoints)):
            raise ValueError('oracle checkpoint inventory is invalid')
        names += [f'checkpoint-{n:06d}.{suffix}' for n in checkpoints for suffix in ('rdram', 'png')]
    return [directory / name for name in names]


def load_evidence(correspondence, snapshots, update):
    """Explain a first LD/LW register mismatch using retained, not live, RAM."""
    mismatch = correspondence['first_difference']
    if mismatch['kind'] != 'shared-state' or set(mismatch.get('fields', {})) != {'gpr'}:
        return None
    a, b = mismatch['native'], mismatch['oracle']
    word = a['opcode']; op = word >> 26; rs = (word >> 21) & 31; rt = (word >> 16) & 31
    if op not in (35, 39, 55) or not rt or set(mismatch['fields']['gpr']) != {str(rt)}:
        return None
    context = correspondence['preceding_context']
    if not context:
        return None
    entries = context[-1]
    if (a['phase'] != 1 or b['phase'] != 'ordinary' or entries['native']['phase'] != 0 or
            entries['oracle']['phase'] != 'entry' or any(entries[side]['pc'] != a['pc'] or
            entries[side]['opcode'] != word for side in ('native', 'oracle'))):
        return None
    displacement = (word & 65535) - (65536 if word & 32768 else 0)
    bases = [entries[side]['gpr'][rs] for side in ('native', 'oracle')]
    if bases[0] != bases[1]:
        return None
    address = (bases[0] + displacement) & 0xffffffff
    width = 8 if op == 55 else 4
    if not 0x80000000 <= address <= 0x80400000 - width or address % width:
        return None
    observations = []
    for u in sorted(snapshots['native']):
        values = {}
        for side in ('native', 'oracle'):
            data = snapshots[side][u]
            offset = address - 0x80000000
            value = int.from_bytes(data[offset:offset + width], 'big', signed=op == 35)
            values[side] = value & ((1 << 64) - 1)
        observations.append({'update': u, **values, 'equal': values['native'] == values['oracle'],
                             'precedes_observed_update': u < update})
    earlier_difference = any(row['precedes_observed_update'] and not row['equal'] for row in observations)
    return {'opcode': word, 'pc': a['pc'], 'address': address, 'width': width, 'register': rt,
            'loaded_native': a['gpr'][rt], 'loaded_oracle': b['gpr'][rt], 'snapshots': observations,
            'live_memory_read_witness': False, 'earlier_store_identified': False,
            'next_question': ('Trace the earlier producer of differing saved bytes; do not force load values.'
                              if earlier_difference else
                              'Capture live load operands and memory; these snapshots do not locate an earlier divergence.')}


def measure(repo, request):
    directories = validate_request(repo, request)
    update, window = request['update'], request['window']
    evidence = {}
    def remember(paths):
        for path in paths:
            path = path.resolve(strict=True)
            sha = file_sha256(path)
            if str(path) in evidence and evidence[str(path)] != sha:
                raise ValueError('instruction evidence changed while being read')
            evidence[str(path)] = sha
    native_path = source_build.pinned_file(repo, request['native_build'])
    native = json.loads(native_path.read_text())
    native = source_build.validate(repo, request['native_build'], Path(native['executable']))
    oracle, support = oracle_build(repo, request['oracle_build'])
    remember([native_path, *support, *(source_build.pinned_file(repo, p) for p in native['evidence'])])
    metadata, devices, snapshots = {}, {}, {}
    for side in ('native', 'oracle'):
        observed, control = directories[side], directories[side + '_control']
        stream_name = 'instruction-effects.bin' if side == 'native' else 'oracle-effects.bin'
        if (control / stream_name).exists():
            raise ValueError('instruction observer-off control contains an effect stream')
        meta_paths = [d / f'{side}-result.json' for d in (observed, control)]
        remember(meta_paths)
        meta, off = [json.loads(path.read_text()) for path in meta_paths]
        metadata[side] = meta
        if off.get('instruction_effects') is not None:
            raise ValueError('observer-off manifest enabled instruction effects')
        for item in (meta, off):
            if side == 'native':
                if (item.get('executable_sha256') != native['executable_sha256'] or
                        item.get('native_runtime_sha256') != native['runtime_sha256']):
                    raise ValueError('native capture differs from source-bound build')
            elif (item.get('runtime_sha256') != oracle['runtime_sha256'] or
                  item.get('mupen_cpu_core_override') != 1):
                raise ValueError('oracle capture differs from cached observer build')
        if side == 'oracle':
            for directory in (observed, control):
                if runtime_digest(directory / 'emulator') != oracle['runtime_sha256']:
                    raise ValueError('oracle capture runtime image changed')
        files = capture_files(observed, side, meta, window)
        off_files = capture_files(control, side, off, window)
        if [p.name for p in files] != [p.name for p in off_files]:
            raise ValueError('off/on artifact inventory differs')
        remember([*files, *off_files, observed / stream_name])
        if any(evidence[str(a.resolve())] != evidence[str(b.resolve())] for a,b in zip(files, off_files)):
            raise ValueError('instruction observer changed a whole control artifact')
        _, devices[side], _ = device_observation.qualify_side(observed, control, request['probe'], window, side)
        snapshots[side] = {u: (observed / f'focus-update-{u}.rdram').read_bytes()
                           for u in range(window[0], window[1] + 1)}
        declaration = meta.get('instruction_effects', {})
        if (declaration.get('update') != update or declaration.get('complete') is not True or
                declaration.get('observation_only') is not True or
                declaration.get('sha256') != evidence[str((observed / stream_name).resolve())] or
                any(declaration.get(key) is not False for key in native_effects.LIMITS)):
            raise ValueError('instruction effect declaration is unqualified')
    if metadata['native']['rom_sha256'] != metadata['oracle']['rom_sha256']:
        raise ValueError('instruction captures use different ROMs')
    source = private_directory(repo, metadata['native']['source_export'])
    if source != private_directory(repo, metadata['oracle']['source_export']):
        raise ValueError('instruction captures use different input exports')
    remember([source / name for name in ('controller.input', 'export-manifest.json', 'initial.flash', 'initial.pak')])
    count = metadata['native']['observed_controller_polls']
    if len(native_polls(directories['native'] / 'controller-polls.tsv')) != count:
        raise ValueError('native delivered poll inventory differs from declared count')
    with tempfile.TemporaryDirectory(prefix='jfg-instruction-input-') as tmp:
        inputs = compare_polls(source, directories['oracle'], directories['native'], Path(tmp) / 'input.json', prefix_polls=count)
    if inputs['first_input_mismatch'] is not None:
        raise ValueError('instruction capture delivered inputs differ')
    native_spec = metadata['native']['eret_transfers']
    oracle_spec = metadata['oracle']['cpu_boundaries']
    for side, filename, spec in (('native','eret-transfers.tsv',native_spec), ('oracle','cpu-boundaries.tsv',oracle_spec)):
        if spec.get('complete') is not True or spec.get('sha256') != file_sha256(directories[side] / filename):
            raise ValueError('instruction effect boundary declaration differs')
    native_witness = bind_native(native_effects.records(directories['native'] / 'instruction-effects.bin', update),
        devices['native'], erets.read(directories['native'] / 'eret-transfers.tsv', native_spec['window'])['rows'], update)
    oracle_witness = bind_oracle(oracle_effects.records(directories['oracle'] / 'oracle-effects.bin', update),
        devices['oracle'], boundaries.read(directories['oracle'] / 'cpu-boundaries.tsv', update)['rows'], update)
    for side, witness in (('native',native_witness), ('oracle',oracle_witness)):
        if sum(witness['phase_counts'].values()) != metadata[side]['instruction_effects'].get('events'):
            raise ValueError('instruction effect row count differs from complete declaration')
    vector = qualify_vector_snapshots(snapshots['native'], snapshots['oracle'])
    comparison = compare(native_effects.records(directories['native'] / 'instruction-effects.bin', update),
        oracle_effects.records(directories['oracle'] / 'oracle-effects.bin', update), update, vector)
    source_build.validate(repo, request['native_build'], Path(native['executable']))
    oracle_build(repo, request['oracle_build'])
    for side in ('oracle','oracle_control'):
        if runtime_digest(directories[side] / 'emulator') != oracle['runtime_sha256']:
            raise ValueError('oracle runtime changed during comparison')
    if evidence != {path:file_sha256(Path(path)) for path in evidence}:
        raise ValueError('instruction observation evidence changed during measurement')
    return {'schema':1, 'kind':'jfg-qualified-instruction-observation', 'complete':True,
            'update':update, 'window':window, 'source_commit':native['source_commit'],
            'native_runtime_sha256':native['runtime_sha256'], 'oracle_runtime_sha256':oracle['runtime_sha256'],
            'rom_sha256':metadata['native']['rom_sha256'], 'input_prefix':{
                'polls':inputs['shared_prefix_polls'], 'initial_state':inputs['initial_state']},
            'qualification':{'passed':True, 'scope':'bounded-off-on-qualified-code-and-GPR-correspondence-not-causality'},
            'native_witnesses':native_witness, 'oracle_witnesses':oracle_witness,
            'correspondence':comparison, 'load_evidence':load_evidence(comparison, snapshots, update),
            'evidence':evidence, 'build_closure_verified':False, 'promoted':False, **native_effects.LIMITS}
