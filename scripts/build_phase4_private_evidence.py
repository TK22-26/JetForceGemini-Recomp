#!/usr/bin/env python3
"""Execute prepared Phase 4 audits and assemble the ignored private body.

The recipe supplies only identities, case IDs, fixed environment facts, and
additional input files.  It cannot supply commands, pass flags, result records,
or transcripts.  Those records are emitted only after the repository-pinned
production harness independently accepts each prepared product set.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping

if __package__:
    from .build_phase4_completion_manifest import (
        _prepared_products,
        derive_public_core,
    )
    from .prepare_phase4_products import (
        MAX_ARTIFACT_BYTES,
        PreparationError,
        _canonical_bytes,
        _is_ignored,
        _load_json_bytes,
        _read_regular,
        _relative_path,
        _sha256,
        _source_id,
        _within,
    )
    from .validate_phase4_private_evidence import (
        EVIDENCE_KINDS,
        PRIVATE_SCHEMA,
        PRODUCTION_HARNESS_PINS,
        _binding,
        _result_expectation,
        _schema_errors,
        _transcript_expectation,
        g3_product_projection,
        g3_product_projection_errors,
        public_claim_sha256,
        validate_documents as validate_phase4_documents,
    )
    from .validate_g2_private_evidence import PinnedHarness, execute_pinned_harness
else:
    from build_phase4_completion_manifest import (
        _prepared_products,
        derive_public_core,
    )
    from prepare_phase4_products import (
        MAX_ARTIFACT_BYTES,
        PreparationError,
        _canonical_bytes,
        _is_ignored,
        _load_json_bytes,
        _read_regular,
        _relative_path,
        _sha256,
        _source_id,
        _within,
    )
    from validate_phase4_private_evidence import (
        EVIDENCE_KINDS,
        PRIVATE_SCHEMA,
        PRODUCTION_HARNESS_PINS,
        _binding,
        _result_expectation,
        _schema_errors,
        _transcript_expectation,
        g3_product_projection,
        g3_product_projection_errors,
        public_claim_sha256,
        validate_documents as validate_phase4_documents,
    )
    from validate_g2_private_evidence import PinnedHarness, execute_pinned_harness


MAX_RECIPE_BYTES = 2 * 1024 * 1024
MAX_IDENTITY_SOURCE_COUNT = 128
MAX_IDENTITY_TOTAL_BYTES = 256 * 1024 * 1024


class PrivateBodyBuildError(RuntimeError):
    """A public-safe private evidence assembly failure."""


HarnessExecutor = Callable[[PinnedHarness, object, Path], tuple[object | None, list[str]]]


def _write_new(path: Path, payload: bytes) -> None:
    descriptor = None
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("short write")
            view = view[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _recipe(
    document: object,
) -> tuple[list[str], dict[str, dict[str, object]]]:
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "kind",
        "identity_sources",
        "executions",
    } or document.get("schema_version") != 1 or document.get(
        "kind"
    ) != "jfg-phase4-private-body-preparation":
        raise PrivateBodyBuildError("private body recipe contract differs")
    identity_sources = document.get("identity_sources")
    executions = document.get("executions")
    if (
        not isinstance(identity_sources, list)
        or len(identity_sources) > MAX_IDENTITY_SOURCE_COUNT
        or not isinstance(executions, list)
        or len(executions) != len(EVIDENCE_KINDS)
    ):
        raise PrivateBodyBuildError("private body recipe matrix is invalid")
    paths: list[str] = []
    for record in identity_sources:
        if not isinstance(record, dict) or set(record) != {"path"}:
            raise PrivateBodyBuildError("private identity source is invalid")
        parsed = _relative_path(record.get("path"))
        path = parsed.as_posix()
        if path in paths:
            raise PrivateBodyBuildError("private identity source is duplicated")
        paths.append(path)
    by_kind: dict[str, dict[str, object]] = {}
    ids: set[str] = set()
    for record in executions:
        if not isinstance(record, dict) or set(record) != {
            "evidence_kind",
            "id",
            "case_id",
            "environment",
        }:
            raise PrivateBodyBuildError("private execution recipe is invalid")
        evidence_kind = record.get("evidence_kind")
        execution_id = _source_id(record.get("id"))
        case_id = _source_id(record.get("case_id"))
        environment = record.get("environment")
        if (
            not isinstance(evidence_kind, str)
            or evidence_kind in by_kind
            or evidence_kind not in EVIDENCE_KINDS
            or execution_id in ids
            or not isinstance(environment, dict)
            or set(environment) != {
                "environment_id",
                "platform_id",
                "architecture_id",
                "toolchain_sha256",
            }
        ):
            raise PrivateBodyBuildError("private execution recipe is invalid")
        for field in ("environment_id", "platform_id", "architecture_id"):
            _source_id(environment.get(field))
        toolchain = environment.get("toolchain_sha256")
        if (
            not isinstance(toolchain, str)
            or len(toolchain) != 64
            or any(character not in "0123456789abcdef" for character in toolchain)
        ):
            raise PrivateBodyBuildError("private execution environment is invalid")
        ids.add(execution_id)
        by_kind[evidence_kind] = {
            "id": execution_id,
            "case_id": case_id,
            "environment": copy.deepcopy(environment),
        }
    if set(by_kind) != set(EVIDENCE_KINDS):
        raise PrivateBodyBuildError("private body recipe matrix is invalid")
    return paths, by_kind


def _identity_payloads(paths: list[str], source_root: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    total = 0
    source_root = source_root.resolve(strict=True)
    for textual in paths:
        payload = _read_regular(
            _within(source_root, _relative_path(textual), must_exist=True),
            maximum=MAX_ARTIFACT_BYTES,
        )
        total += len(payload)
        if total > MAX_IDENTITY_TOTAL_BYTES:
            raise PrivateBodyBuildError("private identity source set exceeds its limit")
        digest = _sha256(payload)
        existing = result.get(digest)
        if existing is not None and existing != payload:
            raise PrivateBodyBuildError("private identity digest collision")
        result[digest] = payload
    return result


def _product_payloads(
    index: dict[str, dict[str, tuple[str, str]]], bundle_root: Path
) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for products in index.values():
        for path, digest in products.values():
            payload = _read_regular(
                _within(bundle_root, _relative_path(path), must_exist=True),
                maximum=MAX_ARTIFACT_BYTES,
            )
            if _sha256(payload) != digest:
                raise PrivateBodyBuildError("prepared product digest differs")
            result[digest] = payload
    return result


def _execute_production(
    pin: PinnedHarness, request: object, bundle_root: Path
) -> tuple[object | None, list[str]]:
    return execute_pinned_harness(pin, request, bundle_root, require_tracked=True)


def assemble_private_body(
    recipe_document: object,
    identity_root: Path,
    index_document: object,
    bundle_root: Path,
    public_document: dict[str, object],
    *,
    harness_pins: Mapping[str, PinnedHarness] = PRODUCTION_HARNESS_PINS,
    executor: HarnessExecutor = _execute_production,
) -> dict[str, object]:
    """Assemble only after every selected pinned harness returns its exact transcript."""
    identity_paths, execution_recipe = _recipe(recipe_document)
    prepared = _prepared_products(index_document, bundle_root)
    available = _product_payloads(prepared, bundle_root)
    available.update(_identity_payloads(identity_paths, identity_root))
    pins = public_document.get("pins")
    if not isinstance(pins, dict):
        raise PrivateBodyBuildError("public Phase 4 pins are unavailable")
    private: dict[str, object] = {
        "$schema": "../../../schemas/phase4-private-evidence.schema.json",
        "schema_version": 2,
        "kind": "jfg-phase4-private-executable-evidence",
        "public_claim_sha256": public_claim_sha256(public_document),
        "pins": copy.deepcopy(pins),
        "pins_sha256": _sha256(_canonical_bytes(pins)),
        "executions": [],
        "evidence_set_sha256": "",
    }
    executions: list[dict[str, object]] = []
    private_directory = bundle_root / "private"
    if private_directory.exists():
        raise PrivateBodyBuildError("private assembly output already exists")
    private_directory.mkdir()

    for evidence_kind in EVIDENCE_KINDS:
        binding = _binding(public_document, evidence_kind)
        pin = harness_pins.get(evidence_kind)
        if binding is None or pin is None:
            raise PrivateBodyBuildError("public binding or pinned harness is unavailable")
        recipe_row = execution_recipe[evidence_kind]
        environment = recipe_row["environment"]
        assert isinstance(environment, dict)
        bound_toolchain = binding.get("toolchain_sha256")
        if isinstance(bound_toolchain, str) and environment.get("toolchain_sha256") != bound_toolchain:
            raise PrivateBodyBuildError("private environment toolchain differs from public binding")

        index_row = next(
            row
            for row in index_document["executions"]  # type: ignore[index]
            if row["evidence_kind"] == evidence_kind
        )
        artifacts = copy.deepcopy(index_row["artifacts"])
        if not isinstance(artifacts, list):
            raise PrivateBodyBuildError("prepared artifact descriptors are unavailable")
        required_digests: list[str] = []
        for field in ("source_input_sha256", "subject_sha256", "declaration_sha256"):
            digest = binding.get(field)
            if not isinstance(digest, str):
                raise PrivateBodyBuildError("public identity binding is unavailable")
            if digest not in required_digests:
                required_digests.append(digest)
        execution_directory = private_directory / evidence_kind
        execution_directory.mkdir()
        for index, digest in enumerate(required_digests):
            payload = available.get(digest)
            if payload is None:
                raise PrivateBodyBuildError("required private identity source is unavailable")
            role = (
                "expectation"
                if evidence_kind == "configuration-mutation"
                and digest == binding.get("declaration_sha256")
                else "input"
            )
            relative_path = PurePosixPath("private") / evidence_kind / f"identity-{index:02d}.bin"
            bundle_root.joinpath(*relative_path.parts).write_bytes(payload)
            artifacts.append({"path": relative_path.as_posix(), "role": role, "sha256": digest})

        input_records = [
            row for row in artifacts if row.get("role") in {"configuration", "input", "expectation"}
        ]
        output_records = [
            row for row in artifacts if row.get("role") in {"output", "log"}
        ]
        execution: dict[str, object] = {
            "id": recipe_row["id"],
            "evidence_kind": evidence_kind,
            "harness_id": pin.harness_id,
            "harness_sha256": pin.script_sha256,
            "case_id": recipe_row["case_id"],
            "public_record_sha256": binding["public_record_sha256"],
            "public_result_set_sha256": binding["public_result_set_sha256"],
            "subject_sha256": binding["subject_sha256"],
            "source_input_sha256": binding["source_input_sha256"],
            "declaration_sha256": binding["declaration_sha256"],
            "pins_sha256": private["pins_sha256"],
            "environment": copy.deepcopy(environment),
            "environment_sha256": _sha256(_canonical_bytes(environment)),
            "input_set_sha256": _sha256(_canonical_bytes(input_records)),
            "output_set_sha256": _sha256(_canonical_bytes(output_records)),
            "artifact_set_sha256": "",
            "result_sha256": "",
            "observed_exit_code": 0,
            "passed": True,
            "artifacts": artifacts,
        }
        result_payload = _canonical_bytes(_result_expectation(private, execution))
        result_relative = PurePosixPath("private") / evidence_kind / "execution-result.json"
        bundle_root.joinpath(*result_relative.parts).write_bytes(result_payload)
        execution["result_sha256"] = _sha256(result_payload)
        artifacts.append(
            {
                "path": result_relative.as_posix(),
                "role": "result",
                "sha256": execution["result_sha256"],
            }
        )
        execution["artifact_set_sha256"] = _sha256(_canonical_bytes(artifacts))
        request = {
            "schema_version": 1,
            "kind": "jfg-phase4-harness-request",
            "public_claim_sha256": private["public_claim_sha256"],
            "pins": private["pins"],
            "execution": execution,
            "public_binding": {
                "public_record": binding["public_record"],
                "expected_products": binding["expected_products"],
                "toolchain_sha256": binding["toolchain_sha256"],
            },
        }
        transcript, errors = executor(pin, request, bundle_root)
        if errors or transcript != _transcript_expectation(private, execution):
            raise PrivateBodyBuildError("pinned production harness rejected prepared products")
        executions.append(execution)

    private["executions"] = executions
    private["evidence_set_sha256"] = _sha256(_canonical_bytes(executions))
    try:
        schema = _load_json_bytes(_read_regular(PRIVATE_SCHEMA, maximum=2 * 1024 * 1024))
    except PreparationError as error:
        raise PrivateBodyBuildError("private evidence schema is unavailable") from error
    if _schema_errors(private, schema):
        raise PrivateBodyBuildError("assembled private body violates its schema")
    return private


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipe", required=True, type=Path)
    parser.add_argument("--identity-root", required=True, type=Path)
    parser.add_argument("--prepared-index", required=True, type=Path)
    parser.add_argument("--patch-provenance", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        if not _is_ignored(arguments.prepared_index) or not _is_ignored(
            arguments.patch_provenance
        ):
            raise PrivateBodyBuildError("private product inputs must remain Git-ignored")
        index_path = arguments.prepared_index.resolve(strict=True)
        bundle_root = index_path.parent
        output = bundle_root / "phase4-private.json"
        projection_output = bundle_root / "phase4-g3-product-projection.json"
        if output.exists() or projection_output.exists():
            raise PrivateBodyBuildError("private evidence output already exists")
        recipe = _load_json_bytes(_read_regular(arguments.recipe, maximum=MAX_RECIPE_BYTES))
        patch_provenance = _load_json_bytes(
            _read_regular(arguments.patch_provenance, maximum=2 * 1024 * 1024)
        )
        index_document = _load_json_bytes(
            _read_regular(index_path, maximum=4 * 1024 * 1024)
        )
        derived_core = derive_public_core(
            index_document, bundle_root, patch_provenance
        )
        body = assemble_private_body(
            recipe,
            arguments.identity_root,
            index_document,
            bundle_root,
            derived_core,
        )
        body_bytes = _canonical_bytes(body)
        projection = g3_product_projection(derived_core, _sha256(body_bytes))
        projection_bytes = _canonical_bytes(projection)
        private_schema = _load_json_bytes(
            _read_regular(PRIVATE_SCHEMA, maximum=2 * 1024 * 1024)
        )
        if g3_product_projection_errors(projection) or validate_phase4_documents(
            body, projection, private_schema, bundle_root
        ):
            raise PrivateBodyBuildError("pre-G2 private product audit is invalid")
        _write_new(output, body_bytes)
        try:
            _write_new(projection_output, projection_bytes)
        except BaseException:
            try:
                output.unlink()
            except OSError:
                pass
            raise
    except (
        PrivateBodyBuildError,
        PreparationError,
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        print("Phase 4 private body build failed: products or prerequisites rejected", file=sys.stderr)
        return 1
    print(
        "Phase 4 pre-G2 product projection and private body built after eleven pinned production audits"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
