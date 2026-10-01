#!/usr/bin/env python3
"""Pack a bounded private overlay case for the tracked G2 native producer.

The JSON recipe and referenced initialized section images must remain beneath
the ignored tools tree or outside the repository. The packed case contains no
expected observation and is accepted only when the native producer derives all
required results by executing the generated table and overlay runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
MAGIC = b"JFG2OVL1"
MAX_DOCUMENT_BYTES = 1024 * 1024
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_GUEST_BYTES = 64 * 1024 * 1024
MAX_PROBES = 4096
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{1,70}[a-z0-9]$")
RELOCATION_CLASSES = {
    "full-word": 0,
    "jump-target": 1,
    "hi16": 2,
    "lo16": 3,
}
TOP_KEYS = {
    "schema_version",
    "case_id",
    "guest_memory_size",
    "target",
    "dependent",
    "reference_id",
    "copy_check",
    "relocation_probes",
}
MODULE_KEYS = {
    "module_id",
    "section_index",
    "guest_base",
    "function_offset",
    "initialized_image",
}


class CaseError(Exception):
    pass


def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CaseError("invalid recipe")
        result[key] = value
    return result


def load_json(path: Path) -> object:
    payload = read_regular(path, MAX_DOCUMENT_BYTES)
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(CaseError()),
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise CaseError("invalid recipe") from error


def read_regular(path: Path, maximum: int) -> bytes:
    try:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
            raise CaseError("input is not a regular file")
        if metadata.st_size <= 0 or metadata.st_size > maximum:
            raise CaseError("input size is outside the bounded range")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if not os.path.samestat(metadata, opened) or not stat.S_ISREG(opened.st_mode):
                raise CaseError("input identity changed")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > maximum:
                    raise CaseError("input exceeded the bounded range")
                chunks.append(chunk)
        finally:
            os.close(descriptor)
    except OSError as error:
        raise CaseError("input could not be read") from error
    return b"".join(chunks)


def exact_dict(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise CaseError("invalid recipe")
    return value


def integer(value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise CaseError("invalid recipe")
    return value


def private_path(recipe_path: Path, textual: object) -> Path:
    if not isinstance(textual, str) or not textual or "\x00" in textual:
        raise CaseError("invalid recipe")
    candidate = Path(textual)
    if not candidate.is_absolute():
        candidate = recipe_path.parent / candidate
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(ROOT)
    except ValueError:
        return resolved
    except OSError as error:
        raise CaseError("input could not be resolved") from error
    if not relative.parts or relative.parts[0].casefold() != "tools":
        raise CaseError("repository inputs must remain beneath tools")
    return resolved


def module_record(recipe_path: Path, value: object) -> tuple[int, int, int, int, bytes]:
    module = exact_dict(value, MODULE_KEYS)
    module_id = integer(module["module_id"], 1, 2**64 - 1)
    section = integer(module["section_index"], 0, 65_499)
    base = integer(module["guest_base"], 0, 2**32 - 1)
    function_offset = integer(module["function_offset"], 0, 2**32 - 1)
    image = read_regular(
        private_path(recipe_path, module["initialized_image"]),
        MAX_IMAGE_BYTES,
    )
    if base < 0x80000000 or base % 4 != 0 or function_offset % 4 != 0 or len(image) % 4 != 0:
        raise CaseError("invalid recipe")
    return module_id, section, base, function_offset, image


def module_bytes(record: tuple[int, int, int, int, bytes]) -> bytes:
    module_id, section, base, function_offset, image = record
    return struct.pack("<QIIII", module_id, section, base, function_offset, len(image)) + image


def build_case(recipe_path: Path) -> bytes:
    document = exact_dict(load_json(recipe_path), TOP_KEYS)
    if document["schema_version"] != 1:
        raise CaseError("invalid recipe")
    case_id = document["case_id"]
    if not isinstance(case_id, str) or IDENTIFIER.fullmatch(case_id) is None:
        raise CaseError("invalid recipe")
    encoded_case_id = case_id.encode("ascii")
    guest_size = integer(document["guest_memory_size"], 1, MAX_GUEST_BYTES)
    reference_id = integer(document["reference_id"], 1, 2**64 - 1)
    target = module_record(recipe_path, document["target"])
    dependent = module_record(recipe_path, document["dependent"])
    if any(target[index] == dependent[index] for index in range(3)):
        raise CaseError("invalid recipe")
    target_start = target[2] - 0x80000000
    dependent_start = dependent[2] - 0x80000000
    target_end = target_start + len(target[4])
    dependent_end = dependent_start + len(dependent[4])
    if (
        target_end > guest_size
        or dependent_end > guest_size
        or not (target_end <= dependent_start or dependent_end <= target_start)
    ):
        raise CaseError("invalid recipe")
    copy_check = exact_dict(document["copy_check"], {"offset", "byte_count"})
    copy_offset = integer(copy_check["offset"], 0, 2**32 - 1)
    copy_size = integer(copy_check["byte_count"], 1, 2**32 - 1)
    copy_end = copy_offset + copy_size
    if copy_end > len(dependent[4]):
        raise CaseError("invalid recipe")
    raw_probes = document["relocation_probes"]
    if not isinstance(raw_probes, list) or not 4 <= len(raw_probes) <= MAX_PROBES:
        raise CaseError("invalid recipe")
    probes = bytearray()
    offsets: set[int] = set()
    classes: set[str] = set()
    for raw in raw_probes:
        probe = exact_dict(raw, {"offset", "class"})
        offset = integer(probe["offset"], 0, 2**32 - 1)
        kind = probe["class"]
        if (
            not isinstance(kind, str)
            or kind not in RELOCATION_CLASSES
            or offset in offsets
            or offset % 4 != 0
            or offset + 4 > len(dependent[4])
            or not (offset + 4 <= copy_offset or offset >= copy_end)
        ):
            raise CaseError("invalid recipe")
        offsets.add(offset)
        classes.add(kind)
        probes.extend(struct.pack("<IB3x", offset, RELOCATION_CLASSES[kind]))
    if classes != set(RELOCATION_CLASSES):
        raise CaseError("invalid recipe")
    return b"".join(
        (
            MAGIC,
            struct.pack("<IH", 1, len(encoded_case_id)),
            encoded_case_id,
            struct.pack("<I", guest_size),
            module_bytes(target),
            module_bytes(dependent),
            struct.pack("<QIII", reference_id, copy_offset, copy_size, len(raw_probes)),
            bytes(probes),
        )
    )


def output_path(textual: str) -> Path:
    candidate = Path(textual)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    resolved_parent = candidate.parent.resolve(strict=True)
    try:
        resolved_parent.relative_to(TOOLS.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise CaseError("output must remain beneath tools") from error
    return resolved_parent / candidate.name


def write_new(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
        try:
            view = memoryview(payload)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError("short write")
                view = view[written:]
        finally:
            os.close(descriptor)
    except OSError as error:
        raise CaseError("output could not be created") from error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    try:
        recipe = private_path(ROOT / "recipe-anchor.json", arguments.recipe)
        payload = build_case(recipe)
        destination = output_path(arguments.output)
        write_new(destination, payload)
    except CaseError as error:
        print(f"G2 overlay case preparation failed: {error}", file=sys.stderr)
        return 1
    print("G2 overlay case prepared")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
