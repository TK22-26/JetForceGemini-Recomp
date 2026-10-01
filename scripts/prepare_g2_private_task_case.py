#!/usr/bin/env python3
"""Pack bounded ignored graphics/audio task inputs for G2 producers."""

from __future__ import annotations

import argparse
import os
import stat
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = (ROOT / "tools").resolve()
MAGIC = b"JFG2PRD1"
VERSION = 3
FAMILY = {"graphics": 1, "audio": 2}
MAX_INPUT = 24 * 1024 * 1024


class PreparationError(RuntimeError):
    pass


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _regular(path: Path, maximum: int) -> bytes:
    resolved = path.resolve(strict=True)
    if _inside(resolved, ROOT.resolve()) and not _inside(resolved, TOOLS):
        raise PreparationError("private input is not ignored")
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise PreparationError("private input is not a regular file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_size <= 0 or opened.st_size > maximum:
            raise PreparationError("private input size is invalid")
        chunks: list[bytes] = []
        remaining = opened.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                raise PreparationError("private input changed during read")
            chunks.append(chunk)
            remaining -= len(chunk)
        closed = os.fstat(descriptor)
        identity = lambda value: (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_size,
            value.st_mtime_ns,
        )
        if identity(closed) != identity(opened):
            raise PreparationError("private input changed during read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _field(payload: bytes) -> bytes:
    if len(payload) > 0xFFFFFFFF:
        raise PreparationError("private field is too large")
    return struct.pack("<I", len(payload)) + payload


def _write_new(path: Path, payload: bytes) -> None:
    resolved_parent = path.parent.resolve(strict=True)
    if not _inside(resolved_parent, TOOLS):
        raise PreparationError("private output must remain beneath tools")
    if path.exists() or path.is_symlink():
        raise PreparationError("private output already exists")
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise PreparationError("private output write failed")
            view = view[written:]
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    finally:
        os.close(descriptor)


def _audio_output_shape(index: Path) -> tuple[int, int]:
    text = _regular(index, 1024 * 1024).decode("ascii", errors="strict")
    matches: list[tuple[int, int]] = []
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) == 4 and fields[0] == "output":
            try:
                matches.append((int(fields[2], 16), int(fields[3], 10)))
            except ValueError as error:
                raise PreparationError("audio output shape is invalid") from error
    if len(matches) != 1 or matches[0][1] <= 0:
        raise PreparationError("audio output shape is unavailable")
    return matches[0]


def _graphics(arguments: argparse.Namespace) -> bytes:
    descriptor = _regular(arguments.descriptor, 64)
    program = _regular(arguments.program, 4096)
    data = _regular(arguments.program_data, 4096)
    commands = _regular(arguments.commands, 1024 * 1024)
    chunks = [_regular(path, 2 * 1024 * 1024) for path in arguments.memory]
    if len(descriptor) != 64 or len(chunks) != 4 or any(
        len(chunk) != 2 * 1024 * 1024 for chunk in chunks
    ):
        raise PreparationError("graphics task shape is invalid")
    return b"".join(
        _field(value)
        for value in (descriptor, program, data, commands, b"".join(chunks))
    )


def _audio(arguments: argparse.Namespace) -> bytes:
    output_address, output_size = _audio_output_shape(arguments.index)
    descriptor = _regular(arguments.descriptor, 64)
    program = _regular(arguments.program, 4096)
    data = _regular(arguments.program_data, 4096)
    commands = _regular(arguments.commands, 1024 * 1024)
    memory = _regular(arguments.memory, 8 * 1024 * 1024)
    if len(descriptor) != 64 or output_size <= 0 or output_size > 1024 * 1024:
        raise PreparationError("audio task shape is invalid")
    return struct.pack("<II", output_address, output_size) + b"".join(
        _field(value)
        for value in (descriptor, program, data, commands, memory)
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="family", required=True)
    graphics = subparsers.add_parser("graphics")
    graphics.add_argument("--descriptor", type=Path, required=True)
    graphics.add_argument("--program", type=Path, required=True)
    graphics.add_argument("--program-data", type=Path, required=True)
    graphics.add_argument("--commands", type=Path, required=True)
    graphics.add_argument("--memory", type=Path, action="append", required=True)
    graphics.add_argument("--output", type=Path, required=True)
    audio = subparsers.add_parser("audio")
    audio.add_argument("--descriptor", type=Path, required=True)
    audio.add_argument("--program", type=Path, required=True)
    audio.add_argument("--program-data", type=Path, required=True)
    audio.add_argument("--commands", type=Path, required=True)
    audio.add_argument("--memory", type=Path, required=True)
    audio.add_argument("--index", type=Path, required=True)
    audio.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        body = _graphics(arguments) if arguments.family == "graphics" else _audio(arguments)
        payload = MAGIC + struct.pack("<III", VERSION, FAMILY[arguments.family], len(body)) + body
        if len(payload) > MAX_INPUT:
            raise PreparationError("private case exceeds the fixed bound")
        _write_new(arguments.output, payload)
    except (OSError, UnicodeError, PreparationError, ValueError):
        print("G2 private task case preparation failed", file=sys.stderr)
        return 1
    print("G2 private task case prepared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
