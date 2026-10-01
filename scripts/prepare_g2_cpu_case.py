#!/usr/bin/env python3
"""Derive a bounded G2 CPU case from independently validated G3 products."""

from __future__ import annotations

import argparse
import os
import re
import stat
import struct
import sys
from pathlib import Path

if __package__:
    from .validate_g2_private_evidence import (
        _canonical_bytes,
        _private_path_is_allowed,
        cpu_g3_product_binding_sha256,
        phase4_symbol_denominators,
        phase4_cpu_section_inventory,
    )
    from .validate_phase4_private_evidence import (
        G3_PRODUCT_PROJECTION_KIND,
        _json_loads,
        g3_product_projection_errors,
        validate_private_file as validate_phase4_private_file,
    )
else:
    from validate_g2_private_evidence import (
        _canonical_bytes,
        _private_path_is_allowed,
        cpu_g3_product_binding_sha256,
        phase4_symbol_denominators,
        phase4_cpu_section_inventory,
    )
    from validate_phase4_private_evidence import (
        G3_PRODUCT_PROJECTION_KIND,
        _json_loads,
        g3_product_projection_errors,
        validate_private_file as validate_phase4_private_file,
    )


ROOT = Path(__file__).resolve().parents[1]
TOOLS = (ROOT / "tools").resolve()
MAGIC = b"JFGCPU02"
VERSION = 4
MAX_DOCUMENT = 8 * 1024 * 1024
MAX_CASE = 64 * 1024
MAX_SECTIONS = 1024
MAX_OVERLAY_SLOTS = 1024
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,70}[a-z0-9]$")


class PreparationError(RuntimeError):
    pass


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _metadata_is_reparse(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse)


def _regular(path: Path, *, private: bool) -> bytes:
    absolute = Path(os.path.abspath(path))
    try:
        resolved_before = absolute.resolve(strict=True)
        before = absolute.lstat()
        descriptor = os.open(
            absolute,
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as error:
        raise PreparationError("CPU case input boundary is invalid") from error
    try:
        opened = os.fstat(descriptor)
        after_open = absolute.lstat()
        resolved_after_open = absolute.resolve(strict=True)
        if (
            _metadata_is_reparse(before)
            or _metadata_is_reparse(after_open)
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_size <= 0
            or opened.st_size > MAX_DOCUMENT
            or not os.path.samestat(before, opened)
            or not os.path.samestat(after_open, opened)
            or resolved_before != resolved_after_open
            or (
                private
                and _inside(resolved_after_open, ROOT.resolve())
                and not _inside(resolved_after_open, TOOLS)
            )
        ):
            raise PreparationError("CPU case input boundary is invalid")
        chunks: list[bytes] = []
        remaining = opened.st_size
        while remaining:
            part = os.read(descriptor, min(remaining, 1024 * 1024))
            if not part:
                raise PreparationError("CPU case input changed during read")
            chunks.append(part)
            remaining -= len(part)
        after_read = os.fstat(descriptor)
        final = absolute.lstat()
        resolved_final = absolute.resolve(strict=True)
        if (
            _metadata_is_reparse(final)
            or not stat.S_ISREG(after_read.st_mode)
            or not os.path.samestat(opened, after_read)
            or not os.path.samestat(final, after_read)
            or opened.st_size != after_read.st_size
            or opened.st_mtime_ns != after_read.st_mtime_ns
            or resolved_after_open != resolved_final
        ):
            raise PreparationError("CPU case input changed during read")
        return b"".join(chunks)
    except OSError as error:
        raise PreparationError("CPU case input boundary is invalid") from error
    finally:
        os.close(descriptor)


def _integer(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise PreparationError("CPU inventory count is invalid")
    return value


def load_validated_g3_audit(
    projection_path: Path, private_audit_path: Path
) -> tuple[dict[str, object], dict[str, object]]:
    """Load the ignored pre-G2 projection only after full trusted validation."""
    projection_payload = _regular(projection_path, private=True)
    private_payload = _regular(private_audit_path, private=True)
    projection_absolute = projection_path.resolve(strict=True)
    private_absolute = private_audit_path.resolve(strict=True)
    if (
        not _inside(projection_absolute, TOOLS)
        or not _inside(private_absolute, TOOLS)
        or _private_path_is_allowed(Path(os.path.abspath(projection_path))) is not True
        or _private_path_is_allowed(Path(os.path.abspath(private_audit_path))) is not True
    ):
        raise PreparationError("G3 audit inputs must remain Git-ignored")
    projection = _json_loads(projection_payload)
    private = _json_loads(private_payload)
    errors = (
        validate_phase4_private_file(private_audit_path, projection)
        if isinstance(projection, dict)
        else ["projection unavailable"]
    )
    if (
        not isinstance(projection, dict)
        or projection.get("kind") != G3_PRODUCT_PROJECTION_KIND
        or not isinstance(private, dict)
        or projection_payload != _canonical_bytes(projection)
        or private_payload != _canonical_bytes(private)
        or g3_product_projection_errors(projection)
        or errors
        or _regular(projection_path, private=True) != projection_payload
        or _regular(private_audit_path, private=True) != private_payload
    ):
        raise PreparationError("G3 private products are not independently valid")
    return projection, private


def build_case(
    phase4_public: object,
    phase4_private: object,
    section_inventory: object,
) -> bytes:
    if not isinstance(phase4_public, dict) or not isinstance(section_inventory, dict):
        raise PreparationError("CPU inventory is unavailable")
    if set(section_inventory) != {
        "schema_version",
        "kind",
        "sections",
        "overlay_slots",
    } or (
        section_inventory.get("schema_version") != 2
        or section_inventory.get("kind") != "jfg-phase4-cpu-section-inventory"
    ):
        raise PreparationError("CPU section inventory is invalid")
    raw_sections = section_inventory.get("sections")
    raw_slots = section_inventory.get("overlay_slots")
    if not isinstance(raw_sections, list) or not 2 <= len(raw_sections) <= MAX_SECTIONS:
        raise PreparationError("CPU section inventory is invalid")
    if not isinstance(raw_slots, list) or not 1 <= len(raw_slots) <= MAX_OVERLAY_SLOTS:
        raise PreparationError("CPU overlay slot inventory is invalid")

    compilers = phase4_public.get("compilers")
    if not isinstance(compilers, list) or len(compilers) != 3:
        raise PreparationError("CPU compiler matrix is invalid")
    compiler_products: list[tuple[str, bytes]] = []
    families: set[str] = set()
    for compiler in compilers:
        if not isinstance(compiler, dict):
            raise PreparationError("CPU compiler matrix is invalid")
        family = compiler.get("family")
        identifier = compiler.get("compiler_id")
        digest = compiler.get("compiler_executable_sha256")
        if (
            family not in {"clang", "gcc", "msvc"}
            or family in families
            or not isinstance(identifier, str)
            or IDENTIFIER.fullmatch(identifier) is None
            or not isinstance(digest, str)
        ):
            raise PreparationError("CPU compiler matrix is invalid")
        try:
            digest_bytes = bytes.fromhex(digest)
        except ValueError as error:
            raise PreparationError("CPU compiler matrix is invalid") from error
        if len(digest_bytes) != 32:
            raise PreparationError("CPU compiler matrix is invalid")
        families.add(str(family))
        compiler_products.append((identifier, digest_bytes))
    compiler_products.sort()

    binding = cpu_g3_product_binding_sha256(phase4_private, phase4_public)
    if not isinstance(binding, str):
        raise PreparationError("CPU G3 product binding is unavailable")
    binding_bytes = bytes.fromhex(binding)

    encoded_sections: list[bytes] = []
    seen: set[str] = set()
    kinds: set[str] = set()
    totals = {key: 0 for key in ("expected", "generated", "excluded", "lookups", "relocations")}
    required = {
        "section_id",
        "kind",
        "expected",
        "generated",
        "excluded",
        "lookups",
        "lifecycle",
        "relocations",
    }
    for item in raw_sections:
        if not isinstance(item, dict) or set(item) != required:
            raise PreparationError("CPU section row is invalid")
        identifier = item.get("section_id")
        kind = item.get("kind")
        if (
            not isinstance(identifier, str)
            or IDENTIFIER.fullmatch(identifier) is None
            or identifier in seen
            or kind not in {"main", "overlay"}
        ):
            raise PreparationError("CPU section row is invalid")
        values = {field: _integer(item.get(field)) for field in required - {"section_id", "kind"}}
        if (
            values["expected"] == 0
            or values["generated"] + values["excluded"] != values["expected"]
            or values["lookups"] < values["generated"]
            or (kind == "overlay" and values["lifecycle"] == 0)
        ):
            raise PreparationError("CPU section row is invalid")
        seen.add(identifier)
        kinds.add(str(kind))
        for field in totals:
            totals[field] += values[field]
        encoded = identifier.encode("ascii")
        encoded_sections.append(
            bytes([len(encoded)])
            + encoded
            + bytes([0 if kind == "main" else 1])
            + struct.pack(
                "<8I",
                values["expected"],
                values["expected"],
                values["generated"],
                values["excluded"],
                0,
                values["lookups"],
                values["lifecycle"],
                values["relocations"],
            )
        )
    if kinds != {"main", "overlay"}:
        raise PreparationError("CPU section coverage is incomplete")

    encoded_slots: list[bytes] = []
    seen_slots: set[str] = set()
    populated_sections: set[str] = set()
    populated_slot_count = 0
    empty_slot_count = 0
    for index, item in enumerate(raw_slots, start=1):
        if not isinstance(item, dict) or set(item) != {
            "slot_id",
            "disposition",
            "section_id",
        }:
            raise PreparationError("CPU overlay slot row is invalid")
        slot_id = item.get("slot_id")
        disposition = item.get("disposition")
        section_id = item.get("section_id")
        if (
            slot_id != f"slot-{index:03d}"
            or not isinstance(slot_id, str)
            or slot_id in seen_slots
        ):
            raise PreparationError("CPU overlay slot row is invalid")
        slot_bytes = slot_id.encode("ascii")
        if disposition == "populated":
            if (
                not isinstance(section_id, str)
                or section_id not in seen
                or section_id == "section-000"
                or section_id in populated_sections
            ):
                raise PreparationError("CPU populated overlay slot row is invalid")
            section_bytes = section_id.encode("ascii")
            encoded_slots.append(
                bytes([len(slot_bytes)])
                + slot_bytes
                + b"\x00"
                + bytes([len(section_bytes)])
                + section_bytes
            )
            populated_sections.add(section_id)
            populated_slot_count += 1
        elif disposition == "empty-fail-closed" and section_id is None:
            encoded_slots.append(bytes([len(slot_bytes)]) + slot_bytes + b"\x01")
            empty_slot_count += 1
        else:
            raise PreparationError("CPU empty overlay slot row is invalid")
        seen_slots.add(slot_id)
    expected_overlay_sections = {
        str(item["section_id"])
        for item in raw_sections
        if isinstance(item, dict) and item.get("kind") == "overlay"
    }
    if populated_sections != expected_overlay_sections:
        raise PreparationError("CPU overlay slot coverage is incomplete")

    symbols = phase4_public.get("symbols")
    stubs = phase4_public.get("stubs")
    libraries = phase4_public.get("libraries")
    baseline = libraries.get("baseline") if isinstance(libraries, dict) else None
    runtime = libraries.get("minimal_runtime") if isinstance(libraries, dict) else None
    overlays = phase4_public.get("overlays")
    if not all(isinstance(value, dict) for value in (symbols, stubs, baseline, runtime, overlays)):
        raise PreparationError("CPU G3 denominators are unavailable")
    assert isinstance(symbols, dict) and isinstance(stubs, dict)
    assert isinstance(baseline, dict) and isinstance(runtime, dict)
    assert isinstance(overlays, dict)
    if not phase4_symbol_denominators(symbols):
        raise PreparationError("CPU G3 symbol denominator is incomplete")
    comparisons = (
        (totals["expected"], symbols.get("expected_count")),
        (totals["generated"], symbols.get("generated_count")),
        (totals["excluded"], symbols.get("excluded_count")),
        (totals["lookups"], symbols.get("replaceable_function_count")),
        (totals["relocations"], runtime.get("relocation_table_entry_count")),
        (len(raw_sections), overlays.get("executable_section_count")),
        (len(raw_sections), runtime.get("section_address_count")),
        (len(raw_slots), overlays.get("expected_slot_count")),
        (len(raw_slots), overlays.get("listed_slot_count")),
        (populated_slot_count, overlays.get("populated_slot_count")),
        (empty_slot_count, overlays.get("empty_slot_count")),
    )
    if any(left != _integer(right) for left, right in comparisons):
        raise PreparationError("CPU sections differ from G3 products")
    objects = _integer(baseline.get("unmodified_body_member_count"))
    stub_count = _integer(stubs.get("generated_game_function_stub_count"))
    bridges = _integer(runtime.get("handwritten_bridge_unit_count"))
    audit = (len(raw_sections), objects, objects, objects, 0, 0, stub_count, bridges, bridges)

    body: list[bytes] = [MAGIC, struct.pack("<HH", VERSION, len(compiler_products))]
    for identifier, digest in compiler_products:
        encoded = identifier.encode("ascii")
        body.extend((bytes([len(encoded)]), encoded, digest))
    body.extend((binding_bytes, struct.pack("<H", len(encoded_sections)), *encoded_sections))
    body.extend((struct.pack("<H", len(encoded_slots)), *encoded_slots))
    body.append(struct.pack("<9I", *audit))
    body.append(struct.pack("<H", 5))
    for tool_id in range(1, 6):
        body.append(struct.pack("<BII", tool_id, 0, 0))
    result = b"".join(body)
    if len(result) > MAX_CASE:
        raise PreparationError("CPU case exceeds the fixed bound")
    return result


def _write_new(path: Path, payload: bytes) -> None:
    if not _inside(path.parent.resolve(strict=True), TOOLS) or path.exists() or path.is_symlink():
        raise PreparationError("CPU case output boundary is invalid")
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
                raise PreparationError("CPU case output failed")
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
    parser.add_argument("--phase4-g3-product-projection", type=Path, required=True)
    parser.add_argument("--phase4-private-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        public, private = load_validated_g3_audit(
            arguments.phase4_g3_product_projection,
            arguments.phase4_private_audit,
        )
        sections = phase4_cpu_section_inventory(
            private, arguments.phase4_private_audit.parent
        )
        if sections is None:
            raise PreparationError("authenticated G3 CPU inventory is unavailable")
        _write_new(arguments.output, build_case(public, private, sections))
    except (OSError, UnicodeError, ValueError, PreparationError):
        print("G2 CPU case preparation failed", file=sys.stderr)
        return 1
    print("G2 CPU case prepared")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
