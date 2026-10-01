#!/usr/bin/env python3
"""Validate a generated source root and emit fast CMake list inputs.

Private v2/v3 roots carry a normalizer-revision digest used only to reject output
from an older normalizer. It is a freshness check, not an authenticity claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
NORMALIZER_PATH = ROOT / "scripts" / "build_private_generated_root.py"

MANIFEST_KEYS_V1 = {
    "version",
    "n64recomp_include",
    "baseline_body_sources",
    "normal_wrapper_sources",
    "patch_sources",
    "game_patch_function_count",
    "support_sources",
    "link_smoke_sources",
    "symbol_inventory",
    "symbol_inventory_sha256",
}
MANIFEST_KEYS_V2 = MANIFEST_KEYS_V1 | {"normalizer_revision_sha256"}
MANIFEST_KEYS_V3 = MANIFEST_KEYS_V2 | {
    "cpu_section_inventory",
    "cpu_section_inventory_sha256",
}
MANIFEST_KEYS_V4 = MANIFEST_KEYS_V3 | {
    "alternate_entry_thunk_sources",
    "table_support_sources",
}
SEMANTIC_PRODUCTS = {
    "generated_inventory": "jfg-phase4-generated-inventory",
    "generation_result": "jfg-phase4-generation-semantic-result",
    "alternate_entry_ledger": "jfg-phase4-alternate-entry-ledger",
    "exception_ledger": "jfg-phase4-approved-exception-ledger",
    "n64recomp_decision_sidecar": "n64recomp-indirect-decision-sidecar",
    "overlay_slot_inventory": "jfg-phase4-overlay-slot-inventory",
    "overlay_lookup_table": "jfg-phase4-generated-lookup-inventory",
    "overlay_lifecycle_table": "jfg-phase4-overlay-lifecycle-inventory",
    "relocation_table": "jfg-phase4-relocation-inventory",
    "report_set": "jfg-phase4-generation-report-set",
}
MANIFEST_KEYS_V5 = MANIFEST_KEYS_V4 | {
    member
    for product in SEMANTIC_PRODUCTS
    for member in (product, f"{product}_sha256")
}
SEMANTIC_PRODUCTS_V6 = {
    **SEMANTIC_PRODUCTS,
    "covered_alias_ledger": "jfg-phase4-covered-alias-ledger",
    "manual_size_recovery_ledger": "jfg-phase4-manual-size-recovery-ledger",
}
MANIFEST_KEYS_V6 = MANIFEST_KEYS_V4 | {
    member
    for product in SEMANTIC_PRODUCTS_V6
    for member in (product, f"{product}_sha256")
}
SOURCE_ROLES = {
    "baseline-body": ("baseline_body_sources", {".c"}, False),
    "normal-wrapper": ("normal_wrapper_sources", {".c"}, False),
    "patch": ("patch_sources", {".c"}, True),
    "support": ("support_sources", {".c"}, False),
    "link-smoke": ("link_smoke_sources", {".c", ".cc", ".cpp", ".cxx"}, False),
}
SAFE_RELATIVE_PATH = re.compile(r"^[A-Za-z0-9_.\-/]+$")


class PreparationFailure(Exception):
    """Expected public-safe validation failure."""


def _reject_duplicate_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PreparationFailure("source-manifest: duplicate-member")
        result[key] = value
    return result


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_members
        )
    except PreparationFailure:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PreparationFailure("source-manifest: unreadable-or-invalid-json") from error
    if not isinstance(document, dict) or type(document.get("version")) is not int:
        raise PreparationFailure("source-manifest: unsupported-version")
    expected_keys = {
        1: MANIFEST_KEYS_V1,
        2: MANIFEST_KEYS_V2,
        3: MANIFEST_KEYS_V3,
        4: MANIFEST_KEYS_V4,
        5: MANIFEST_KEYS_V5,
        6: MANIFEST_KEYS_V6,
    }.get(document["version"])
    if expected_keys is None:
        raise PreparationFailure("source-manifest: unsupported-version")
    if set(document) != expected_keys:
        raise PreparationFailure("source-manifest: invalid-member-set")
    if document["version"] in {4, 5, 6}:
        thunk = document.get("alternate_entry_thunk_sources")
        tables = document.get("table_support_sources")
        support = document.get("support_sources")
        if not all(isinstance(value, list) and all(isinstance(path, str) for path in value) for value in (thunk, tables, support)) or set(thunk) & set(tables) or set(support) != set(thunk) | set(tables):
            raise PreparationFailure("source-manifest: support-role-partition")
    return document


def _canonical_product(payload: bytes, expected_kind: str) -> None:
    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_members,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                PreparationFailure("semantic-product: invalid-json")
            ),
        )
        canonical = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except PreparationFailure:
        raise
    except (UnicodeError, ValueError, TypeError, OverflowError, RecursionError) as error:
        raise PreparationFailure("semantic-product: invalid-json") from error
    if (
        payload != canonical
        or not isinstance(document, dict)
        or type(document.get("schema_version")) is not int
        or document.get("schema_version") not in (
            (1, 2) if expected_kind == "n64recomp-indirect-decision-sidecar" else (1,))
        or document.get("kind") != expected_kind
    ):
        raise PreparationFailure("semantic-product: invalid-contract")


def _validate_normalizer_revision(document: dict[str, object]) -> None:
    expected_digest = document.get("normalizer_revision_sha256")
    if not isinstance(expected_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_digest
    ):
        raise PreparationFailure("normalizer-revision: invalid-digest")
    try:
        if NORMALIZER_PATH.is_symlink() or not NORMALIZER_PATH.is_file():
            raise OSError("normalizer is not a regular file")
        normalizer_bytes = NORMALIZER_PATH.read_bytes()
    except OSError as error:
        raise PreparationFailure("normalizer-revision: unavailable") from error
    if hashlib.sha256(normalizer_bytes).hexdigest() != expected_digest:
        raise PreparationFailure("normalizer-revision: digest-mismatch")


def _relative_parts(value: object, role: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value or not SAFE_RELATIVE_PATH.fullmatch(value):
        raise PreparationFailure(f"{role}: invalid-relative-path")
    path = PurePosixPath(value)
    if (
        value != path.as_posix()
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise PreparationFailure(f"{role}: noncanonical-relative-path")
    return path.parts


def _resolve_contained(
    root: Path,
    value: object,
    role: str,
    *,
    expect_directory: bool = False,
) -> Path:
    parts = _relative_parts(value, role)
    try:
        resolved = root.joinpath(*parts).resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise PreparationFailure(f"{role}: missing-or-unresolvable-input") from error
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise PreparationFailure(f"{role}: containment-escape") from error
    if expect_directory != resolved.is_dir():
        raise PreparationFailure(f"{role}: wrong-input-kind")
    return resolved


def _source_list(
    document: dict[str, object],
    root: Path,
    role: str,
    member: str,
    extensions: set[str],
    allow_empty: bool,
    directory_cache: dict[PurePosixPath, tuple[Path, dict[str, os.DirEntry[str]]]],
) -> list[Path]:
    values = document.get(member)
    if not isinstance(values, list) or any(type(value) is not str for value in values):
        raise PreparationFailure(f"{role}: invalid-source-list")
    if not values and not allow_empty:
        raise PreparationFailure(f"{role}: empty-source-list")
    if values != sorted(values) or len(values) != len(set(values)):
        raise PreparationFailure(f"{role}: noncanonical-source-list")

    resolved: list[Path] = []
    for value in values:
        relative = PurePosixPath(value)
        if relative.suffix not in extensions:
            raise PreparationFailure(f"{role}: unsupported-source-extension")
        parent = relative.parent
        if parent not in directory_cache:
            if parent == PurePosixPath("."):
                resolved_parent = root
            else:
                resolved_parent = _resolve_contained(
                    root,
                    parent.as_posix(),
                    role,
                    expect_directory=True,
                )
            try:
                entries = {entry.name: entry for entry in os.scandir(resolved_parent)}
            except OSError as error:
                raise PreparationFailure(f"{role}: source-directory-unreadable") from error
            directory_cache[parent] = (resolved_parent, entries)
        resolved_parent, entries = directory_cache[parent]
        entry = entries.get(relative.name)
        if entry is None or entry.is_symlink() or not entry.is_file(follow_symlinks=False):
            raise PreparationFailure(f"{role}: missing-or-nonregular-source")
        source = resolved_parent / relative.name
        resolved.append(source)
    if len(resolved) != len(set(resolved)):
        raise PreparationFailure(f"{role}: resolved-source-collision")
    return resolved


def _write_lines(path: Path, values: Sequence[Path]) -> None:
    text = "".join(f"{value.as_posix()}\n" for value in values)
    path.write_text(text, encoding="utf-8", newline="\n")


def prepare(
    root_argument: Path,
    output: Path,
    *,
    require_normalizer_revision: bool = False,
) -> None:
    try:
        root = root_argument.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise PreparationFailure("generated-root: missing-or-unresolvable") from error
    if not root.is_dir():
        raise PreparationFailure("generated-root: not-a-directory")

    unresolved_manifest = root / "sources.json"
    if unresolved_manifest.is_symlink():
        raise PreparationFailure("source-manifest: symbolic-link-not-allowed")
    try:
        manifest_path = unresolved_manifest.resolve(strict=True)
        manifest_path.relative_to(root)
    except (OSError, RuntimeError, ValueError) as error:
        raise PreparationFailure("source-manifest: missing-or-containment-escape") from error
    if not manifest_path.is_file():
        raise PreparationFailure("source-manifest: not-a-regular-file")
    document = _load_manifest(manifest_path)
    # CMake enables this for every private root. The only v1 consumer is the
    # exact tracked ROM-free fixture selected by CMake's separate root policy.
    if require_normalizer_revision and document["version"] not in {2, 3, 4, 5, 6}:
        raise PreparationFailure("normalizer-revision: required")
    if document["version"] in {2, 3, 4, 5, 6}:
        _validate_normalizer_revision(document)
    sources: dict[str, list[Path]] = {}
    all_sources: list[Path] = []
    directory_cache: dict[
        PurePosixPath, tuple[Path, dict[str, os.DirEntry[str]]]
    ] = {}
    for role, (member, extensions, allow_empty) in SOURCE_ROLES.items():
        role_sources = _source_list(
            document,
            root,
            role,
            member,
            extensions,
            allow_empty,
            directory_cache,
        )
        sources[role] = role_sources
        all_sources.extend(role_sources)
    if len(all_sources) != len(set(all_sources)):
        raise PreparationFailure("source-manifest: cross-role-source-collision")
    if len(sources["baseline-body"]) != len(sources["normal-wrapper"]):
        raise PreparationFailure("source-manifest: body-wrapper-count-mismatch")

    patch_count = document.get("game_patch_function_count")
    if type(patch_count) is not int or patch_count < 0:
        raise PreparationFailure("source-manifest: invalid-patch-count")
    if patch_count != len(sources["patch"]):
        raise PreparationFailure("source-manifest: patch-count-mismatch")

    recomp_include = _resolve_contained(
        root, document.get("n64recomp_include"), "n64recomp-include", expect_directory=True
    )
    recomp_header = (recomp_include / "recomp.h").resolve(strict=True)
    try:
        recomp_header.relative_to(root)
    except ValueError as error:
        raise PreparationFailure("n64recomp-include: header-containment-escape") from error
    if not recomp_header.is_file():
        raise PreparationFailure("n64recomp-include: missing-header")

    inventory_value = document.get("symbol_inventory")
    inventory = _resolve_contained(root, inventory_value, "symbol-inventory")
    if not inventory.is_file() or PurePosixPath(str(inventory_value)).suffix != ".json":
        raise PreparationFailure("symbol-inventory: invalid-input-kind")
    expected_digest = document.get("symbol_inventory_sha256")
    if not isinstance(expected_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", expected_digest
    ):
        raise PreparationFailure("symbol-inventory: invalid-digest")
    try:
        inventory_bytes = inventory.read_bytes()
    except OSError as error:
        raise PreparationFailure("symbol-inventory: unreadable") from error
    if hashlib.sha256(inventory_bytes).hexdigest() != expected_digest:
        raise PreparationFailure("symbol-inventory: digest-mismatch")

    cpu_inventory: Path | None = None
    cpu_inventory_bytes: bytes | None = None
    if document["version"] in {3, 4, 5, 6}:
        cpu_inventory_value = document.get("cpu_section_inventory")
        cpu_inventory = _resolve_contained(
            root, cpu_inventory_value, "cpu-section-inventory"
        )
        if (
            not cpu_inventory.is_file()
            or PurePosixPath(str(cpu_inventory_value)).suffix != ".json"
        ):
            raise PreparationFailure("cpu-section-inventory: invalid-input-kind")
        cpu_expected_digest = document.get("cpu_section_inventory_sha256")
        if not isinstance(cpu_expected_digest, str) or not re.fullmatch(
            r"[0-9a-f]{64}", cpu_expected_digest
        ):
            raise PreparationFailure("cpu-section-inventory: invalid-digest")
        try:
            cpu_inventory_bytes = cpu_inventory.read_bytes()
        except OSError as error:
            raise PreparationFailure("cpu-section-inventory: unreadable") from error
        if hashlib.sha256(cpu_inventory_bytes).hexdigest() != cpu_expected_digest:
            raise PreparationFailure("cpu-section-inventory: digest-mismatch")

    semantic_product_bytes: dict[str, bytes] = {}
    if document["version"] in {5, 6}:
        semantic_products = (
            SEMANTIC_PRODUCTS_V6
            if document["version"] == 6
            else SEMANTIC_PRODUCTS
        )
        for member, expected_kind in semantic_products.items():
            value = document.get(member)
            product_path = _resolve_contained(root, value, f"{member}")
            if (
                not product_path.is_file()
                or PurePosixPath(str(value)).suffix != ".json"
            ):
                raise PreparationFailure(f"{member}: invalid-input-kind")
            expected_digest = document.get(f"{member}_sha256")
            if not isinstance(expected_digest, str) or re.fullmatch(
                r"[0-9a-f]{64}", expected_digest
            ) is None:
                raise PreparationFailure(f"{member}: invalid-digest")
            try:
                payload = product_path.read_bytes()
            except OSError as error:
                raise PreparationFailure(f"{member}: unreadable") from error
            if hashlib.sha256(payload).hexdigest() != expected_digest:
                raise PreparationFailure(f"{member}: digest-mismatch")
            _canonical_product(payload, expected_kind)
            semantic_product_bytes[member] = payload

    output.mkdir(parents=True, exist_ok=True)
    for role, role_sources in sources.items():
        _write_lines(output / f"{role}.txt", role_sources)
    if document["version"] in {4, 5, 6}:
        support_values = document["support_sources"]
        assert isinstance(support_values, list)
        support_by_value = dict(zip(support_values, sources["support"]))
        for output_name, member in (
            ("alternate-entry-thunk", "alternate_entry_thunk_sources"),
            ("table-support", "table_support_sources"),
        ):
            values = document[member]
            assert isinstance(values, list)
            _write_lines(
                output / f"{output_name}.txt",
                [support_by_value[value] for value in values],
            )
    (output / "recomp-include.txt").write_text(
        f"{recomp_include.as_posix()}\n", encoding="utf-8", newline="\n"
    )
    (output / "inventory-source.txt").write_text(
        f"{inventory.as_posix()}\n", encoding="utf-8", newline="\n"
    )
    (output / "symbol-inventory.json").write_bytes(inventory_bytes)
    if cpu_inventory is not None and cpu_inventory_bytes is not None:
        (output / "cpu-inventory-source.txt").write_text(
            f"{cpu_inventory.as_posix()}\n", encoding="utf-8", newline="\n"
        )
        (output / "cpu-section-inventory.json").write_bytes(cpu_inventory_bytes)
    for member, payload in semantic_product_bytes.items():
        (output / f"{member.replace('_', '-')}.json").write_bytes(payload)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-normalizer-revision", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        prepare(
            args.root,
            args.output,
            require_normalizer_revision=args.require_normalizer_revision,
        )
    except PreparationFailure as error:
        print(f"generated-source-preparation: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
