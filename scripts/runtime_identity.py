"""Write path-free identity for a locally built executable and its matching symbols."""
from __future__ import annotations
import hashlib
from pathlib import Path
import struct
import subprocess


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def codeview(path: Path) -> str | None:
    """Read just the bounded PE debug directory; never return the embedded path."""
    with path.open('rb') as stream:
        size = path.stat().st_size
        def read(offset: int, count: int) -> bytes:
            if offset < 0 or count < 0 or offset + count > size:
                raise ValueError('Truncated PE identity')
            stream.seek(offset)
            data = stream.read(count)
            if len(data) != count:
                raise ValueError('Truncated PE identity')
            return data
        if read(0, 2) != b'MZ':
            raise ValueError('Invalid PE identity')
        pe = struct.unpack('<I', read(60, 4))[0]
        if read(pe, 4) != b'PE\0\0':
            raise ValueError('Invalid PE identity')
        machine, sections = struct.unpack('<HH', read(pe + 4, 4))
        optional_size = struct.unpack('<H', read(pe + 20, 2))[0]
        if machine != 0x8664 or sections > 96 or optional_size < 168 or struct.unpack('<H', read(pe + 24, 2))[0] != 0x20b:
            raise ValueError('Expected Windows x64 PE')
        debug_rva, debug_size = struct.unpack('<II', read(pe + 24 + 112 + 6 * 8, 8))
        if debug_size == 0:
            return None
        if debug_size > 28 * 64 or debug_size % 28:
            raise ValueError('Invalid PE debug directory')
        for index in range(sections):
            header = read(pe + 24 + optional_size + index * 40, 40)
            _, rva, raw_size, raw = struct.unpack_from('<IIII', header, 8)
            if rva <= debug_rva and debug_rva - rva + debug_size <= raw_size:
                for offset in range(0, debug_size, 28):
                    entry = read(raw + debug_rva - rva + offset, 28)
                    kind, length, _, pointer = struct.unpack_from('<IIII', entry, 12)
                    if kind == 2 and 24 <= length <= 32768:
                        data = read(pointer, 24)
                        if data[:4] == b'RSDS':
                            return data[4:20].hex() + '-' + format(struct.unpack_from('<I', data, 20)[0], '08x')
                return None
        raise ValueError('Unmapped PE debug directory')


def write_identity(executable: Path, root: Path) -> None:
    def git(*args: str) -> bytes:
        return subprocess.check_output(['git', '-C', str(root), *args])
    source = git('rev-parse', 'HEAD').decode().strip()
    dirty = bool(git('status', '--porcelain'))
    # Hash the actual source inputs as well as HEAD: an edited checkout is not
    # falsely identified as the clean commit it started from.
    tree = hashlib.sha256()
    for item in sorted(set(git('ls-files', '-c', '-o', '--exclude-standard', '-z').split(b'\0'))):
        if not item:
            continue
        path = root / item.decode('utf-8')
        if path.is_file() and not path.is_symlink():
            tree.update(item + b'\0' + bytes.fromhex(sha256(path)))
    lines = ['build_source=' + source, 'build_dirty=' + str(int(dirty)),
             'build_tree_sha256=' + tree.hexdigest(), 'build_runtime_sha256=' + sha256(executable),
             'build_dependencies_sha256=' + sha256(root / 'dependencies.lock.json'), 'build_configuration=release']
    symbol_id = codeview(executable)
    symbols = executable.with_suffix('.pdb')
    if symbol_id and symbols.is_file():
        lines.extend(['build_symbols_id=' + symbol_id, 'build_symbols_sha256=' + sha256(symbols)])
    else:
        lines.append('build_symbols=unavailable')
    helper = executable.with_name('jfg-support-capture.exe')
    if helper.is_file():
        lines.append('build_capture_sha256=' + sha256(helper))
    executable.with_suffix(executable.suffix + '.support').write_text('\n'.join(lines) + '\n', encoding='ascii')
