"""Resolve game frames from a support ZIP against an exact local Windows build."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import re
import zipfile
from runtime_identity import sha256, codeview


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--executable', type=Path, required=True)
    parser.add_argument('--symbols', type=Path, required=True)
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Symbol resolution requires Windows x64 with the matching local build.')
    with zipfile.ZipFile(args.report) as package:
        def text(name: str) -> str:
            item = package.getinfo(name)
            if item.file_size > 65536:
                raise ValueError('Oversized report member')
            return package.read(item).decode('ascii')
        build = dict(line.split('=', 1) for line in text('build.log').splitlines() if '=' in line)
        frames = []
        for name in ('crash.log', 'hang.log'):
            if name in package.namelist():
                for line in text(name).splitlines():
                    match = re.fullmatch(r'frame=(\d+)/(\d+)/([a-z0-9_.-]{1,96})/([0-9a-f]{8})/([0-9a-f]{8})/([0-9a-f]{8,16})', line)
                    if match and match[3] == args.executable.name.lower():
                        frames.append((name, match[1], match[2], int(match[6], 16)))
    if (build.get('build_runtime_sha256') != sha256(args.executable) or
            build.get('build_symbols_sha256') != sha256(args.symbols) or
            build.get('build_symbols_id') != codeview(args.executable)):
        raise ValueError('Executable/symbol identity mismatch; frames remain unresolved.')
    if not frames:
        raise ValueError('No frames for this executable were captured.')
    # A fresh process owns DbgHelp. Only the explicitly selected local symbol
    # directory is searched; the global symbol-server environment is ignored.
    dbg = ctypes.WinDLL('dbghelp', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    handle = kernel.GetCurrentProcess()
    dbg.SymSetOptions.argtypes = [wintypes.DWORD]
    dbg.SymSetOptions(0x400 | 0x1000 | 0x80000 | 0x200)
    dbg.SymInitializeW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.BOOL]
    dbg.SymInitializeW.restype = wintypes.BOOL
    dbg.SymLoadModuleExW.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_uint64, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    dbg.SymLoadModuleExW.restype = ctypes.c_uint64
    dbg.SymFromAddr.argtypes = [wintypes.HANDLE, ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64), ctypes.c_void_p]
    dbg.SymFromAddr.restype = wintypes.BOOL
    dbg.SymCleanup.argtypes = [wintypes.HANDLE]
    class Symbol(ctypes.Structure):
        _fields_ = [('size', wintypes.ULONG), ('type', wintypes.ULONG), ('reserved', ctypes.c_uint64 * 2),
                    ('index', wintypes.ULONG), ('symbol_size', wintypes.ULONG), ('module', ctypes.c_uint64),
                    ('flags', wintypes.ULONG), ('value', ctypes.c_uint64), ('address', ctypes.c_uint64),
                    ('register', wintypes.ULONG), ('scope', wintypes.ULONG), ('tag', wintypes.ULONG),
                    ('length', wintypes.ULONG), ('maximum', wintypes.ULONG), ('name', ctypes.c_char * 1)]
    if not dbg.SymInitializeW(handle, str(args.symbols.resolve().parent), False):
        raise OSError('Cannot initialize the local symbol reader')
    resolved = 0
    try:
        base = dbg.SymLoadModuleExW(handle, None, str(args.executable.resolve()), None, 0x180000000, 0, None, 0)
        if not base:
            raise OSError('Cannot load the matching local executable')
        for source, thread, index, rva in frames:
            buffer = ctypes.create_string_buffer(ctypes.sizeof(Symbol) + 1024)
            symbol = Symbol.from_buffer(buffer); symbol.size = ctypes.sizeof(Symbol); symbol.maximum = 1024
            displacement = ctypes.c_uint64()
            if dbg.SymFromAddr(handle, base + rva, ctypes.byref(displacement), buffer):
                name = ctypes.string_at(ctypes.addressof(buffer) + Symbol.name.offset, min(symbol.length, 1023)).decode('ascii', errors='replace')
                # Local function names only. Never append these to the public ZIP.
                print(f'{source} thread={thread} frame={index} rva={rva:08x} {name}+0x{displacement.value:x}')
                resolved += 1
            else:
                print(f'{source} thread={thread} frame={index} rva={rva:08x} unresolved')
    finally:
        dbg.SymCleanup(handle)
    return 0 if resolved else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        raise SystemExit(str(error))
