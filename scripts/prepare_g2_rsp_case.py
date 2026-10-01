#!/usr/bin/env python3
"""Pack the fixed RSP inventory with real representative program bytes."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import struct
import sys
from pathlib import Path

if __package__:
    from . import validate_rsp_task_manifest as manifest_validator
else:
    import validate_rsp_task_manifest as manifest_validator


ROOT = Path(__file__).resolve().parents[1]
TOOLS = (ROOT / "tools").resolve()
MAGIC = b"JFGRSP01"


class PreparationError(RuntimeError):
    pass


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _private_program(path: Path) -> bytes:
    resolved = path.resolve(strict=True)
    metadata = path.lstat()
    if not _inside(resolved, TOOLS) or stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise PreparationError("RSP program is outside the ignored boundary")
    if metadata.st_size <= 0 or metadata.st_size > 4096:
        raise PreparationError("RSP program size is invalid")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        payload = b""
        while len(payload) < before.st_size:
            part = os.read(descriptor, before.st_size - len(payload))
            if not part:
                raise PreparationError("RSP program changed during read")
            payload += part
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise PreparationError("RSP program changed during read")
        return payload
    finally:
        os.close(descriptor)


def _manifest_commitment() -> bytes:
    manifest = manifest_validator.load_json(manifest_validator.DEFAULT_MANIFEST)
    schema = manifest_validator.load_json(manifest_validator.DEFAULT_SCHEMA)
    lock = manifest_validator.load_json(ROOT / "dependencies.lock.json")
    errors = manifest_validator.validate_manifest_document(manifest, schema)
    errors.extend(manifest_validator.validate_pins(manifest, lock))
    if errors or manifest_validator.canonical_hash(manifest) != (
        manifest_validator.EXPECTED_CURRENT_PIN_MANIFEST_SHA256
    ):
        raise PreparationError("RSP inventory manifest is not the reviewed document")
    rendered = manifest_validator.json.dumps(
        manifest, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(rendered).digest()


def _record(identifier: str, family: int, payload: bytes) -> bytes:
    encoded = identifier.encode("ascii")
    return bytes([len(encoded)]) + encoded + bytes([family]) + struct.pack(
        "<H", len(payload)
    ) + payload


def _write_new(path: Path, payload: bytes) -> None:
    if not _inside(path.parent.resolve(strict=True), TOOLS) or path.exists() or path.is_symlink():
        raise PreparationError("RSP case output boundary is invalid")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) |
        getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise PreparationError("RSP case output write failed")
            view = view[written:]
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graphics-program", type=Path, required=True)
    parser.add_argument("--audio-program", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        graphics = _private_program(arguments.graphics_program)
        audio = _private_program(arguments.audio_program)
        manifest = _manifest_commitment()
        records = (
            _record("graphics-representative", 0, graphics),
            _record("audio-primary", 1, audio),
            _record("audio-secondary", 2, audio),
            _record("boot-loader", 3, manifest),
        )
        payload = MAGIC + struct.pack("<HH", 1, len(records)) + b"".join(records)
        _write_new(arguments.output, payload)
    except (OSError, UnicodeError, ValueError, PreparationError):
        print("G2 RSP case preparation failed", file=sys.stderr)
        return 1
    print("G2 RSP case prepared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
