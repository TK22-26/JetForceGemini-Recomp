#!/usr/bin/env python3
"""Stage bounded Phase 4 products without creating completion claims.

The recipe may name only local files/directories and fixed derivations.  It
cannot contain commands, argument vectors, environment variables, pass flags,
or a private-evidence execution record.  Output is confined to an ignored
bundle root and consists of the production tree, one command-free audit plan
per evidence kind, and a digest index for a later evidence-body builder.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

if __package__:
    from .phase4_evidence_harness import (
        CANONICAL_JSON_PRODUCTS,
        MAX_ARCHIVE_ENTRIES,
        MAX_ARCHIVE_ENTRY_BYTES,
        MAX_ARCHIVE_EXPANDED_BYTES,
        MAX_ARTIFACT_BYTES,
        PRODUCT_KINDS,
        AuditError,
        _ar_members,
        _canonical_json_product,
        _file_inventory,
        _member_inventory,
        _zip_files,
    )
else:
    from phase4_evidence_harness import (
        CANONICAL_JSON_PRODUCTS,
        MAX_ARCHIVE_ENTRIES,
        MAX_ARCHIVE_ENTRY_BYTES,
        MAX_ARCHIVE_EXPANDED_BYTES,
        MAX_ARTIFACT_BYTES,
        PRODUCT_KINDS,
        AuditError,
        _ar_members,
        _canonical_json_product,
        _file_inventory,
        _member_inventory,
        _zip_files,
    )


ROOT = Path(__file__).resolve().parents[1]
MAX_RECIPE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_PRODUCT_BYTES = 1024 * 1024 * 1024
PRIVATE_PATH_TIMEOUT_SECONDS = 10
SOURCE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-._")


class PreparationError(RuntimeError):
    """A public-safe description of a rejected preparation input."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(
        "utf-8"
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PreparationError("preparation recipe is invalid")
        result[key] = value
    return result


def _load_json_bytes(payload: bytes) -> object:
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                PreparationError("preparation recipe is invalid")
            ),
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise PreparationError("preparation recipe is invalid") from error


def _is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse)


def _relative_path(value: object) -> PurePosixPath:
    if not isinstance(value, str):
        raise PreparationError("source path is invalid")
    parsed = PurePosixPath(value)
    if (
        not value
        or parsed.is_absolute()
        or parsed.as_posix() != value
        or any(part in {"", ".", ".."} for part in parsed.parts)
        or ":" in value
        or "\\" in value
    ):
        raise PreparationError("source path is invalid")
    return parsed


def _within(root: Path, relative: PurePosixPath, *, must_exist: bool) -> Path:
    candidate = root.joinpath(*relative.parts)
    try:
        resolved = candidate.resolve(strict=must_exist)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise PreparationError("source path escapes its root") from error
    return resolved


def _read_regular(path: Path, *, maximum: int = MAX_ARTIFACT_BYTES) -> bytes:
    if _is_reparse(path):
        raise PreparationError("source file boundary is invalid")
    try:
        before = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
            raise PreparationError("source file boundary is invalid")
        with path.open("rb") as stream:
            payload = stream.read(maximum + 1)
            after = os.fstat(stream.fileno())
    except OSError as error:
        raise PreparationError("source file could not be read") from error
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after or len(payload) > maximum:
        raise PreparationError("source file changed while it was read")
    return payload


def _directory_zip(source_root: Path, relative: PurePosixPath) -> bytes:
    directory = _within(source_root, relative, must_exist=True)
    if _is_reparse(directory) or not directory.is_dir():
        raise PreparationError("source directory boundary is invalid")
    rows: list[tuple[str, bytes]] = []
    total = 0
    for base, directory_names, file_names in os.walk(directory, followlinks=False):
        base_path = Path(base)
        for name in list(directory_names):
            if _is_reparse(base_path / name):
                raise PreparationError("source directory contains a link")
        for name in file_names:
            path = base_path / name
            if _is_reparse(path):
                raise PreparationError("source directory contains a link")
            try:
                path.resolve(strict=True).relative_to(directory.resolve(strict=True))
            except (OSError, ValueError) as error:
                raise PreparationError("source directory contains an escaped file") from error
            relative_name = path.relative_to(directory).as_posix()
            _relative_path(relative_name)
            payload = _read_regular(path, maximum=MAX_ARCHIVE_ENTRY_BYTES)
            total += len(payload)
            rows.append((relative_name, payload))
            if len(rows) > MAX_ARCHIVE_ENTRIES or total > MAX_ARCHIVE_EXPANDED_BYTES:
                raise PreparationError("source directory exceeds archive limits")
    rows.sort(key=lambda row: row[0])
    if not rows or len({row[0] for row in rows}) != len(rows):
        raise PreparationError("source directory inventory is invalid")
    destination = io.BytesIO()
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in rows:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, payload)
    result = destination.getvalue()
    if len(result) > MAX_ARTIFACT_BYTES:
        raise PreparationError("prepared archive exceeds artifact limit")
    return result


def _source_id(value: object) -> str:
    if (
        not isinstance(value, str)
        or not 2 <= len(value) <= 72
        or value[0] not in SOURCE_ID_CHARS - frozenset("-._")
        or value[-1] not in SOURCE_ID_CHARS - frozenset("-._")
        or any(character not in SOURCE_ID_CHARS for character in value)
    ):
        raise PreparationError("source identifier is invalid")
    return value


def _parse_sources(recipe: dict[str, object], source_root: Path) -> dict[str, bytes]:
    records = recipe.get("sources")
    if not isinstance(records, list) or not records:
        raise PreparationError("preparation sources are unavailable")
    result: dict[str, bytes] = {}
    derived: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            raise PreparationError("preparation source is invalid")
        identifier = _source_id(record.get("id"))
        if identifier in result or any(item.get("id") == identifier for item in derived):
            raise PreparationError("preparation source is duplicated")
        if set(record) == {"id", "path"}:
            path = _within(source_root, _relative_path(record["path"]), must_exist=True)
            result[identifier] = _read_regular(path)
        elif set(record) == {"id", "directory", "preparation"} and record.get(
            "preparation"
        ) == "deterministic-zip":
            result[identifier] = _directory_zip(
                source_root, _relative_path(record["directory"])
            )
        elif set(record) == {"id", "source", "preparation"} and record.get(
            "preparation"
        ) in {"zip-file-inventory", "archive-member-inventory"}:
            derived.append(record)
        else:
            raise PreparationError("preparation source contract differs")
    for record in derived:
        identifier = _source_id(record["id"])
        parent = _source_id(record["source"])
        payload = result.get(parent)
        if payload is None:
            raise PreparationError("derived source parent is unavailable")
        try:
            if record["preparation"] == "zip-file-inventory":
                rows, _contents = _zip_files(payload)
                document = {
                    "schema_version": 1,
                    "kind": "jfg-phase4-file-inventory",
                    "files": rows,
                }
            else:
                document = {
                    "schema_version": 1,
                    "kind": "jfg-phase4-archive-member-inventory",
                    "members": _ar_members(payload),
                }
        except AuditError as error:
            raise PreparationError("derived source input is invalid") from error
        result[identifier] = _canonical_bytes(document)
    return result


def _product_filename(product_kind: str, payload: bytes) -> str:
    if product_kind == "generated-source-archive":
        return "generated-source.zip"
    if product_kind == "generation-input-archive":
        return "generation-input.zip"
    if product_kind == "analysis-source-archive":
        return "analysis-source.zip"
    if product_kind in {"baseline-archive", "patch-archive"}:
        return product_kind + ".a"
    if product_kind == "smoke-executable":
        return "smoke-probe.exe" if payload.startswith(b"MZ") else "smoke-probe"
    if product_kind == "forced-link-executable":
        return "forced-link-probe.exe" if payload.startswith(b"MZ") else "forced-link-probe"
    if product_kind == "instrumented-executable":
        return "instrumented-probe.exe" if payload.startswith(b"MZ") else "instrumented-probe"
    return product_kind + ".json"


def _validate_product(product_kind: str, payload: bytes) -> None:
    try:
        if product_kind in CANONICAL_JSON_PRODUCTS:
            _canonical_json_product(payload)
        if product_kind in {
            "generated-source-archive",
            "generation-input-archive",
            "analysis-source-archive",
        }:
            _zip_files(payload)
        if product_kind in {"baseline-archive", "patch-archive"}:
            _ar_members(payload)
        if product_kind in {
            "source-file-inventory",
            "generation-input-inventory",
            "analysis-source-inventory",
        }:
            _file_inventory(payload, "jfg-phase4-file-inventory")
        if product_kind in {"baseline-member-inventory", "patch-member-inventory"}:
            _member_inventory(payload)
        if product_kind.endswith("executable") and not payload.startswith((b"MZ", b"\x7fELF")):
            raise AuditError("prepared executable format is invalid")
    except AuditError as error:
        raise PreparationError("prepared product is structurally invalid") from error


def _parse_execution_map(
    recipe: dict[str, object], sources: dict[str, bytes]
) -> list[tuple[str, dict[str, bytes]]]:
    executions = recipe.get("executions")
    if not isinstance(executions, list) or len(executions) != len(PRODUCT_KINDS):
        raise PreparationError("exact preparation execution matrix is required")
    result: list[tuple[str, dict[str, bytes]]] = []
    seen: set[str] = set()
    for execution in executions:
        if not isinstance(execution, dict) or set(execution) != {"evidence_kind", "products"}:
            raise PreparationError("preparation execution is invalid")
        evidence_kind = execution.get("evidence_kind")
        products = execution.get("products")
        if (
            not isinstance(evidence_kind, str)
            or evidence_kind in seen
            or evidence_kind not in PRODUCT_KINDS
            or not isinstance(products, dict)
            or frozenset(products) != PRODUCT_KINDS[evidence_kind]
        ):
            raise PreparationError("preparation product set is incomplete")
        prepared: dict[str, bytes] = {}
        for product_kind in sorted(products):
            identifier = _source_id(products[product_kind])
            if identifier not in sources:
                raise PreparationError("preparation product source is unavailable")
            payload = sources[identifier]
            _validate_product(product_kind, payload)
            prepared[product_kind] = payload
        seen.add(evidence_kind)
        result.append((evidence_kind, prepared))
    if seen != set(PRODUCT_KINDS):
        raise PreparationError("exact preparation execution matrix is required")
    return sorted(result)


def _is_ignored(path: Path) -> bool:
    try:
        relative = path.resolve(strict=False).relative_to(ROOT.resolve(strict=True))
        result = subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "-q", "--", relative.as_posix()],
            capture_output=True,
            check=False,
            timeout=PRIVATE_PATH_TIMEOUT_SECONDS,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def prepare(
    recipe: object,
    source_root: Path,
    bundle_root: Path,
    *,
    require_ignored_output: bool = True,
) -> dict[str, object]:
    if not isinstance(recipe, dict) or set(recipe) != {
        "schema_version",
        "kind",
        "sources",
        "executions",
    } or recipe.get("schema_version") != 1 or recipe.get("kind") != "jfg-phase4-product-preparation":
        raise PreparationError("preparation recipe contract differs")
    source_root = source_root.resolve(strict=True)
    if _is_reparse(source_root) or not source_root.is_dir():
        raise PreparationError("source root boundary is invalid")
    bundle_root = bundle_root.resolve(strict=False)
    if bundle_root.exists() or _is_reparse(bundle_root):
        raise PreparationError("bundle output must not already exist")
    try:
        bundle_root.relative_to(source_root)
        raise PreparationError("bundle output overlaps its source root")
    except ValueError:
        pass
    if require_ignored_output and not _is_ignored(bundle_root):
        raise PreparationError("bundle output must remain Git-ignored")
    sources = _parse_sources(recipe, source_root)
    matrix = _parse_execution_map(recipe, sources)
    total = sum(len(payload) for _kind, products in matrix for payload in products.values())
    if total > MAX_TOTAL_PRODUCT_BYTES:
        raise PreparationError("prepared product set exceeds its total limit")

    index_executions: list[dict[str, object]] = []
    try:
        bundle_root.mkdir(parents=True, exist_ok=False)
        for evidence_kind, products in matrix:
            relative_directory = PurePosixPath("production") / evidence_kind
            directory = bundle_root.joinpath(*relative_directory.parts)
            directory.mkdir(parents=True)
            product_rows: list[dict[str, str]] = []
            artifact_rows: list[dict[str, str]] = []
            plan_products: list[dict[str, str]] = []
            for product_kind, payload in sorted(products.items()):
                filename = _product_filename(product_kind, payload)
                relative_path = (relative_directory / filename).as_posix()
                destination = bundle_root.joinpath(*PurePosixPath(relative_path).parts)
                destination.write_bytes(payload)
                if product_kind.endswith("executable"):
                    os.chmod(
                        destination,
                        stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR,
                    )
                else:
                    os.chmod(destination, stat.S_IRUSR | stat.S_IWUSR)
                digest = _sha256(payload)
                product_rows.append(
                    {"product_kind": product_kind, "path": relative_path, "sha256": digest}
                )
                artifact_rows.append({"path": relative_path, "role": "output", "sha256": digest})
                plan_products.append(
                    {"product_kind": product_kind, "artifact_path": relative_path}
                )
            plan = {
                "schema_version": 1,
                "kind": "jfg-phase4-production-audit",
                "evidence_kind": evidence_kind,
                "products": plan_products,
            }
            plan_payload = _canonical_bytes(plan)
            plan_path = (relative_directory / "audit-plan.json").as_posix()
            bundle_root.joinpath(*PurePosixPath(plan_path).parts).write_bytes(plan_payload)
            artifact_rows.insert(
                0, {"path": plan_path, "role": "configuration", "sha256": _sha256(plan_payload)}
            )
            index_executions.append(
                {
                    "evidence_kind": evidence_kind,
                    "plan_path": plan_path,
                    "products": product_rows,
                    "artifacts": artifact_rows,
                }
            )
        index: dict[str, object] = {
            "schema_version": 1,
            "kind": "jfg-phase4-prepared-product-index",
            "executions": index_executions,
        }
        (bundle_root / "phase4-prepared-products.json").write_bytes(_canonical_bytes(index))
        return index
    except (OSError, ValueError, TypeError) as error:
        # Deliberately leave a partial ignored tree for forensic inspection.
        raise PreparationError("prepared product output could not be written") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--bundle-root", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        recipe = _load_json_bytes(_read_regular(arguments.recipe, maximum=MAX_RECIPE_BYTES))
        index = prepare(recipe, arguments.source_root, arguments.bundle_root)
    except (PreparationError, OSError, ValueError, TypeError):
        print("Phase 4 product preparation failed: input or boundary rejected", file=sys.stderr)
        return 1
    print(json.dumps({"execution_count": len(index["executions"]), "prepared": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
