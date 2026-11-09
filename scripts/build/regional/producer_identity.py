"""Freshness identity of the shared generator's local source and template closure.

Imports are parsed, never executed. Compiler bytes and external source pins are
recorded separately by the generation orchestrator.
"""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOMAINS = ('build', 'release', 'validation', 'evidence', 'diagnostics', 'exploration', 'verification')


def module_path(root, name):
    parts = name.split('.')
    if parts[0] != 'scripts':
        return None
    if len(parts) == 1:
        return root / 'scripts/__init__.py'
    tail = Path(*parts[1:])
    # Match scripts.__path__ ordering. Root CLI shims intentionally have the
    # same names as their domain implementations; imports select the domain.
    for base in [root / 'scripts' / domain for domain in DOMAINS] + [root / 'scripts']:
        for candidate in (base / tail / '__init__.py', base / tail.with_suffix('.py')):
            if candidate.is_file():
                return candidate
    return None


def python_closure(root, seeds):
    pending = list(seeds)
    seen = {}
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        path = module_path(root, module)
        if path is None:
            raise ValueError('Missing local producer module: ' + module)
        seen[module] = path
        package = module if path.name == '__init__.py' else module.rpartition('.')[0]
        for size in range(1, len(module.split('.'))):
            parent = '.'.join(module.split('.')[:size])
            parent_path = module_path(root, parent)
            if parent_path is not None:
                pending.append(parent)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))):
            names = []
            if isinstance(node, ast.Import):
                names = [entry.name for entry in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parent = package.split('.')
                    if node.level > len(parent):
                        raise ValueError('Producer import escapes package')
                    base = '.'.join(parent[:len(parent)-node.level+1])
                    if node.module:
                        base += '.' + node.module
                else:
                    base = node.module or ''
                names = [base]
                names += [base + '.' + entry.name for entry in node.names if entry.name != '*'
                          and module_path(root, base + '.' + entry.name) is not None]
            for name in names:
                if name == 'scripts' or name.startswith('scripts.'):
                    pending.append(name)
    return set(seen.values())


def source_paths(root=None):
    root = ROOT if root is None else Path(root)
    # Include all regional contracts, including CLI entry points reached through
    # subprocess rather than a Python import.
    seeds = ['scripts.regional.' + path.stem
             for path in (root / 'scripts/build/regional').glob('*.py') if path.stem != '__init__']
    seeds += ['scripts.generate_from_rom', 'scripts.prepare_regional_metadata',
              'scripts.apply_n64recomp_patchset']
    paths = python_closure(root, seeds)
    paths.update((root / 'config/roms').glob('*.json'))
    paths.update(path for path in (root / 'patches/n64recomp').rglob('*') if path.is_file())
    paths.update(root / name for name in ('dependencies.lock.json',
        'src/bootstrap/brokered-rsp.hpp', 'src/bootstrap/production-audio-adapter.cpp',
        'include/jfg/boot/original_timing_fast.h'))
    if any(not path.is_file() for path in paths):
        raise ValueError('Incomplete producer template closure')
    return tuple(sorted(paths, key=lambda path: path.relative_to(root).as_posix()))


def fingerprint():
    records = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in source_paths()}
    return hashlib.sha256(json.dumps(records, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
