#!/usr/bin/env python3
"""Build and sign the canonical public Phase 4 completion manifest.

This is intentionally a finalization tool, not a claim generator.  It derives
all product-backed records and digests from a prepared private product index,
then requires the Phase 4 and G2 private validators to execute successfully
before the anonymous project key may sign the public aggregate.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import stat
import sys
from pathlib import Path, PurePosixPath

if __package__:
    from .apply_n64recomp_patchset import PatchsetError, _validated_series
    from .g2_decision_policy import accepted_architecture_decision
    from .phase4_evidence_harness import (
        ANALYSIS_BRIDGE_UNIT_COUNT,
        BODY_RE,
        GENERATION_RECOMPILER_RELATIVE,
        PRODUCT_KINDS,
        WRAPPER_RE,
        AuditError,
        _generated_source_contents,
        _generation_input_contents,
        _member_inventory,
        _verify_archive_pair,
        _verify_config_mutation,
        _verify_cpu_section_inventory,
        _verify_forced_object_semantics,
        _verify_generation_semantics,
    )
    from .prepare_phase4_products import (
        MAX_ARTIFACT_BYTES,
        PreparationError,
        _canonical_bytes,
        _is_ignored,
        _is_reparse,
        _load_json_bytes,
        _read_regular,
        _relative_path,
        _sha256,
        _within,
    )
    from .prepare_generated_sources import (
        MANIFEST_KEYS_V6,
        NORMALIZER_PATH,
        SEMANTIC_PRODUCTS_V6,
    )
    from .validate_g2_private_evidence import validate_private_file as validate_g2_private_file
    from .validate_phase4_manifest import (
        DEFAULT_G2_SCHEMA,
        DEFAULT_SCHEMA,
        EXPECTED_KEY_ID,
        EXPECTED_COVERED_ALIAS_COUNT,
        EXPECTED_DECISION_RANGE_TRANSFER_COUNT,
        EXPECTED_EMPTY_OVERLAY_SLOT_COUNT,
        EXPECTED_EXECUTABLE_SYMBOL_COUNT,
        EXPECTED_EXECUTABLE_SECTION_COUNT,
        EXPECTED_GENERATED_BODY_COUNT,
        EXPECTED_NATIVE_RETURN_TRANSFER_COUNT,
        EXPECTED_SIGNATURE_NAMESPACE,
        EXPECTED_SIGNER_PRINCIPAL,
        EXPECTED_STATIC_DIRECT_CALL_CANDIDATE_COUNT,
        EXPECTED_STATIC_BGEZAL_CALL_CANDIDATE_COUNT,
        EXPECTED_STATIC_CONDITIONAL_BRANCH_CALL_CANDIDATE_COUNT,
        EXPECTED_STATIC_DIRECT_TAIL_COUNT,
        EXPECTED_STATIC_J_CALL_CANDIDATE_COUNT,
        EXPECTED_STATIC_JAL_CALL_CANDIDATE_COUNT,
        EXPECTED_STATIC_LINKED_CALL_COUNT,
        EXPECTED_STATIC_INDIRECT_TRANSFER_COUNT,
        EXPECTED_OVERLAY_SLOT_COUNT,
        EXPECTED_POPULATED_OVERLAY_SLOT_COUNT,
        EXPECTED_R32_RELOCATION_COUNT,
        load_json,
        sign_completion_manifest,
        validate_g2_evidence_document,
        validate_phase4_public_core,
        validate_trusted_completion,
    )
    from .validate_phase4_private_evidence import validate_private_file as validate_phase4_private_file
else:
    from apply_n64recomp_patchset import PatchsetError, _validated_series
    from g2_decision_policy import accepted_architecture_decision
    from phase4_evidence_harness import (
        ANALYSIS_BRIDGE_UNIT_COUNT,
        BODY_RE,
        GENERATION_RECOMPILER_RELATIVE,
        PRODUCT_KINDS,
        WRAPPER_RE,
        AuditError,
        _generated_source_contents,
        _generation_input_contents,
        _member_inventory,
        _verify_archive_pair,
        _verify_config_mutation,
        _verify_cpu_section_inventory,
        _verify_forced_object_semantics,
        _verify_generation_semantics,
    )
    from prepare_phase4_products import (
        MAX_ARTIFACT_BYTES,
        PreparationError,
        _canonical_bytes,
        _is_ignored,
        _is_reparse,
        _load_json_bytes,
        _read_regular,
        _relative_path,
        _sha256,
        _within,
    )
    from prepare_generated_sources import (
        MANIFEST_KEYS_V6,
        NORMALIZER_PATH,
        SEMANTIC_PRODUCTS_V6,
    )
    from validate_g2_private_evidence import validate_private_file as validate_g2_private_file
    from validate_phase4_manifest import (
        DEFAULT_G2_SCHEMA,
        DEFAULT_SCHEMA,
        EXPECTED_KEY_ID,
        EXPECTED_COVERED_ALIAS_COUNT,
        EXPECTED_DECISION_RANGE_TRANSFER_COUNT,
        EXPECTED_EMPTY_OVERLAY_SLOT_COUNT,
        EXPECTED_EXECUTABLE_SYMBOL_COUNT,
        EXPECTED_EXECUTABLE_SECTION_COUNT,
        EXPECTED_GENERATED_BODY_COUNT,
        EXPECTED_NATIVE_RETURN_TRANSFER_COUNT,
        EXPECTED_SIGNATURE_NAMESPACE,
        EXPECTED_SIGNER_PRINCIPAL,
        EXPECTED_STATIC_DIRECT_CALL_CANDIDATE_COUNT,
        EXPECTED_STATIC_BGEZAL_CALL_CANDIDATE_COUNT,
        EXPECTED_STATIC_CONDITIONAL_BRANCH_CALL_CANDIDATE_COUNT,
        EXPECTED_STATIC_DIRECT_TAIL_COUNT,
        EXPECTED_STATIC_J_CALL_CANDIDATE_COUNT,
        EXPECTED_STATIC_JAL_CALL_CANDIDATE_COUNT,
        EXPECTED_STATIC_LINKED_CALL_COUNT,
        EXPECTED_STATIC_INDIRECT_TRANSFER_COUNT,
        EXPECTED_OVERLAY_SLOT_COUNT,
        EXPECTED_POPULATED_OVERLAY_SLOT_COUNT,
        EXPECTED_R32_RELOCATION_COUNT,
        load_json,
        sign_completion_manifest,
        validate_g2_evidence_document,
        validate_phase4_public_core,
        validate_trusted_completion,
    )
    from validate_phase4_private_evidence import validate_private_file as validate_phase4_private_file


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_COMPLETION_MANIFEST = ROOT / "evidence" / "phase4-completion.json"
ARCHITECTURE_DECISION = ROOT / "docs" / "adr" / "0003-phase4-dependency-architecture.md"
MAX_CORE_BYTES = 2 * 1024 * 1024
MAX_INDEX_BYTES = 4 * 1024 * 1024
SUPPORTED_INPUT_ID = "jfg-us-retail"
SECTION_ADDRESS_CAPACITY = 4096
OBJECT_ROLE_KEYS = frozenset(
    {
        "baseline-body",
        "normal-wrapper",
        "patch",
        "alternate-entry-thunk",
        "section-address-support",
        "lookup-support",
        "lifecycle-support",
        "relocation-support",
        "runtime-function",
        "runtime-data",
    }
)


class CompletionBuildError(RuntimeError):
    """A public-safe finalization failure."""


def _prepared_products(
    index_document: object, bundle_root: Path
) -> dict[str, dict[str, tuple[str, str]]]:
    if not isinstance(index_document, dict) or set(index_document) != {
        "schema_version",
        "kind",
        "executions",
    } or index_document.get("schema_version") != 1 or index_document.get(
        "kind"
    ) != "jfg-phase4-prepared-product-index":
        raise CompletionBuildError("prepared product index contract differs")
    executions = index_document.get("executions")
    if not isinstance(executions, list) or len(executions) != len(PRODUCT_KINDS):
        raise CompletionBuildError("prepared product execution matrix is incomplete")
    result: dict[str, dict[str, tuple[str, str]]] = {}
    all_paths: set[str] = set()
    for execution in executions:
        if not isinstance(execution, dict) or set(execution) != {
            "evidence_kind",
            "plan_path",
            "products",
            "artifacts",
        }:
            raise CompletionBuildError("prepared product execution is invalid")
        evidence_kind = execution.get("evidence_kind")
        products = execution.get("products")
        artifacts = execution.get("artifacts")
        plan_path = execution.get("plan_path")
        if (
            not isinstance(evidence_kind, str)
            or evidence_kind in result
            or evidence_kind not in PRODUCT_KINDS
            or not isinstance(products, list)
            or not isinstance(artifacts, list)
            or not isinstance(plan_path, str)
        ):
            raise CompletionBuildError("prepared product execution is invalid")
        by_kind: dict[str, tuple[str, str]] = {}
        for row in products:
            if not isinstance(row, dict) or set(row) != {"product_kind", "path", "sha256"}:
                raise CompletionBuildError("prepared product row is invalid")
            product_kind = row.get("product_kind")
            path = row.get("path")
            digest = row.get("sha256")
            if (
                not isinstance(product_kind, str)
                or product_kind in by_kind
                or not isinstance(path, str)
                or not path.startswith(f"production/{evidence_kind}/")
                or path in all_paths
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise CompletionBuildError("prepared product row is invalid")
            payload = _read_regular(
                _within(bundle_root, _relative_path(path), must_exist=True),
                maximum=MAX_ARTIFACT_BYTES,
            )
            if _sha256(payload) != digest:
                raise CompletionBuildError("prepared product digest differs")
            by_kind[product_kind] = (path, digest)
            all_paths.add(path)
        if frozenset(by_kind) != PRODUCT_KINDS[evidence_kind]:
            raise CompletionBuildError("prepared product set is incomplete")
        expected_artifacts = [
            {
                "path": plan_path,
                "role": "configuration",
                "sha256": _sha256(
                    _read_regular(
                        _within(bundle_root, _relative_path(plan_path), must_exist=True),
                        maximum=MAX_ARTIFACT_BYTES,
                    )
                ),
            }
        ] + [
            {"path": path, "role": "output", "sha256": digest}
            for _kind, (path, digest) in sorted(by_kind.items())
        ]
        if artifacts != expected_artifacts:
            raise CompletionBuildError("prepared artifact descriptor set differs")
        result[evidence_kind] = by_kind
    if set(result) != set(PRODUCT_KINDS):
        raise CompletionBuildError("prepared product execution matrix is incomplete")
    return result


def _product_bytes(
    products: dict[str, dict[str, tuple[str, str]]],
    bundle_root: Path,
    evidence_kind: str,
    product_kind: str,
) -> bytes:
    path, digest = products[evidence_kind][product_kind]
    payload = _read_regular(
        _within(bundle_root, _relative_path(path), must_exist=True),
        maximum=MAX_ARTIFACT_BYTES,
    )
    if _sha256(payload) != digest:
        raise CompletionBuildError("prepared product changed during finalization")
    return payload


def _public_result(
    products: dict[str, dict[str, tuple[str, str]]],
    bundle_root: Path,
    evidence_kind: str,
    product_kind: str,
) -> dict[str, object]:
    payload = _product_bytes(products, bundle_root, evidence_kind, product_kind)
    try:
        document = _load_json_bytes(payload)
    except PreparationError as error:
        raise CompletionBuildError("prepared public result is invalid") from error
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "kind", "product_kind", "observed"}
        or document.get("schema_version") != 1
        or document.get("kind") != "jfg-phase4-public-result"
        or document.get("product_kind") != product_kind
        or not isinstance(document.get("observed"), dict)
        or _canonical_bytes(document) != payload
    ):
        raise CompletionBuildError("prepared public result is invalid")
    observed = copy.deepcopy(document["observed"])
    assert isinstance(observed, dict)
    if "result_sha256" in observed:
        raise CompletionBuildError("prepared public result is self-referential")
    observed["result_sha256"] = _sha256(payload)
    return observed


def _digest(
    products: dict[str, dict[str, tuple[str, str]]], evidence_kind: str, product_kind: str
) -> str:
    return products[evidence_kind][product_kind][1]


def _execution_product_bytes(
    products: dict[str, dict[str, tuple[str, str]]],
    bundle_root: Path,
    evidence_kind: str,
) -> dict[str, bytes]:
    return {
        product_kind: _product_bytes(
            products, bundle_root, evidence_kind, product_kind
        )
        for product_kind in PRODUCT_KINDS[evidence_kind]
    }


def _json_product(payload: bytes, expected_kind: str) -> dict[str, object]:
    try:
        document = _load_json_bytes(payload)
    except PreparationError as error:
        raise CompletionBuildError("semantic product is invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != 1
        or document.get("kind") != expected_kind
        or _canonical_bytes(document) != payload
    ):
        raise CompletionBuildError("semantic product is invalid")
    return document


def _derived_result(record: dict[str, object]) -> dict[str, object]:
    result = copy.deepcopy(record)
    result["result_sha256"] = _sha256(_canonical_bytes(record))
    return result


def _require_observed_result(
    result: dict[str, object], expected: dict[str, object], label: str
) -> dict[str, object]:
    observed = copy.deepcopy(result)
    digest = observed.pop("result_sha256", None)
    if observed != expected or not isinstance(digest, str):
        raise CompletionBuildError(f"{label} result differs from derived products")
    return result


def _dependency_pins(
    generation_products: dict[str, bytes],
    analysis_inventory_sha256: str,
    config_sha256: str,
    patch_provenance: object,
) -> dict[str, object]:
    lock_bytes = _read_regular(ROOT / "dependencies.lock.json", maximum=MAX_CORE_BYTES)
    lock = _load_json_bytes(lock_bytes)
    repositories = lock.get("repositories") if isinstance(lock, dict) else None
    if not isinstance(repositories, list):
        raise CompletionBuildError("dependency lock is invalid")
    commits: dict[str, str] = {}
    for repository in repositories:
        if not isinstance(repository, dict):
            raise CompletionBuildError("dependency lock is invalid")
        identifier = repository.get("id")
        commit = repository.get("commit")
        if identifier in {"jfg-decomp", "n64recomp"}:
            if (
                not isinstance(identifier, str)
                or identifier in commits
                or not isinstance(commit, str)
                or len(commit) != 40
            ):
                raise CompletionBuildError("dependency lock is invalid")
            commits[identifier] = commit
    if set(commits) != {"jfg-decomp", "n64recomp"}:
        raise CompletionBuildError("dependency lock is incomplete")

    try:
        patch_paths, patch_digest, _patch_bytes = _validated_series(ROOT)
    except PatchsetError as error:
        raise CompletionBuildError("tracked N64Recomp patch series is invalid") from error
    if (
        not isinstance(patch_provenance, dict)
        or set(patch_provenance) != {"status", "patch_count", "patchset_sha256"}
        or patch_provenance.get("status") != "applied"
        or patch_provenance.get("patch_count") != len(patch_paths)
        or patch_provenance.get("patchset_sha256") != patch_digest
    ):
        raise CompletionBuildError("N64Recomp patch provenance is unavailable")

    try:
        inputs = _generation_input_contents(generation_products)
    except AuditError as error:
        raise CompletionBuildError("generation input closure is invalid") from error
    generator = ROOT.joinpath(*GENERATION_RECOMPILER_RELATIVE.parts)
    generator_bytes = _read_regular(generator, maximum=MAX_ARTIFACT_BYTES)
    if not generator_bytes.startswith(b"\x7fELF"):
        raise CompletionBuildError("pinned generation executable is invalid")
    return {
        "jfg_decomp_commit": commits["jfg-decomp"],
        "n64recomp_commit": commits["n64recomp"],
        "minimal_runtime_source_sha256": analysis_inventory_sha256,
        "n64recomp_patch_set_sha256": patch_digest,
        "supported_input_id": SUPPORTED_INPUT_ID,
        "dependency_lock_sha256": _sha256(lock_bytes),
        "config_sha256": config_sha256,
        "input_elf_sha256": _sha256(inputs["input.elf"]),
        "generator_executable_sha256": _sha256(generator_bytes),
    }


def _object_role_counts(payload: bytes) -> dict[str, int]:
    document = _json_product(payload, "jfg-phase4-generated-object-role-inventory")
    counts = document.get("role_counts")
    if (
        set(document)
        != {
            "schema_version",
            "kind",
            "role_counts",
            "one_external_function_per_generated_object",
            "object_symbol_ownership_verified",
        }
        or not isinstance(counts, dict)
        or set(counts) != OBJECT_ROLE_KEYS
        or any(type(value) is not int or value < 0 for value in counts.values())
        or document.get("one_external_function_per_generated_object") is not True
        or document.get("object_symbol_ownership_verified") is not True
    ):
        raise CompletionBuildError("generated object role inventory is invalid")
    return {key: int(counts[key]) for key in OBJECT_ROLE_KEYS}


def _host_inventory_count(payload: bytes, role: str) -> int:
    document = _json_product(payload, f"jfg-phase4-host-{role}-inventory")
    records = document.get("records")
    if (
        set(document) != {"schema_version", "kind", "record_count", "records"}
        or not isinstance(records, list)
        or not records
        or document.get("record_count") != len(records)
    ):
        raise CompletionBuildError("host symbol ownership inventory is invalid")
    identities: set[str] = set()
    for row in records:
        if (
            not isinstance(row, dict)
            or set(row) != {"symbol_sha256", "owner_role"}
            or row.get("owner_role") != "minimal-runtime"
            or not isinstance(row.get("symbol_sha256"), str)
            or len(str(row["symbol_sha256"])) != 64
            or any(
                character not in "0123456789abcdef"
                for character in str(row["symbol_sha256"])
            )
            or row["symbol_sha256"] in identities
        ):
            raise CompletionBuildError("host symbol ownership inventory is invalid")
        identities.add(str(row["symbol_sha256"]))
    return len(records)


def _source_role_facts(contents: dict[str, bytes]) -> tuple[int, str]:
    manifest = _load_json_bytes(contents["sources.json"])
    if (
        not isinstance(manifest, dict)
        or set(manifest) != MANIFEST_KEYS_V6
        or manifest.get("version") != 6
    ):
        raise CompletionBuildError("generated source manifest is invalid")
    normalizer_revision = manifest.get("normalizer_revision_sha256")
    if (
        not isinstance(normalizer_revision, str)
        or len(normalizer_revision) != 64
        or any(character not in "0123456789abcdef" for character in normalizer_revision)
    ):
        raise CompletionBuildError("generated source manifest is invalid")
    try:
        if NORMALIZER_PATH.is_symlink() or not NORMALIZER_PATH.is_file():
            raise OSError("normalizer is not a regular file")
        expected_normalizer_revision = _sha256(NORMALIZER_PATH.read_bytes())
    except OSError as error:
        raise CompletionBuildError("generated source normalizer is unavailable") from error
    if normalizer_revision != expected_normalizer_revision:
        raise CompletionBuildError("generated source normalizer revision is stale")
    for member in SEMANTIC_PRODUCTS_V6:
        path = manifest.get(member)
        digest = manifest.get(f"{member}_sha256")
        if (
            not isinstance(path, str)
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or path not in contents
            or _sha256(contents[path]) != digest
        ):
            raise CompletionBuildError("generated source semantic binding is invalid")
    patch_sources = manifest.get("patch_sources")
    body_sources = manifest.get("baseline_body_sources")
    wrapper_sources = manifest.get("normal_wrapper_sources")
    support_sources = manifest.get("support_sources")
    alternate_sources = manifest.get("alternate_entry_thunk_sources")
    table_sources = manifest.get("table_support_sources")
    source_lists = (
        patch_sources,
        body_sources,
        wrapper_sources,
        support_sources,
        alternate_sources,
        table_sources,
        manifest.get("link_smoke_sources"),
    )
    if (
        not all(
            isinstance(value, list)
            and all(isinstance(path, str) for path in value)
            and value == sorted(value)
            and len(value) == len(set(value))
            for value in source_lists
        )
        or not isinstance(support_sources, list)
        or not isinstance(alternate_sources, list)
        or not isinstance(table_sources, list)
        or set(alternate_sources) & set(table_sources)
        or set(support_sources) != set(alternate_sources) | set(table_sources)
    ):
        raise CompletionBuildError("generated source roles are invalid")
    assert isinstance(patch_sources, list)
    assert isinstance(body_sources, list)
    assert isinstance(wrapper_sources, list)
    bodies: set[bytes] = set()
    wrappers: set[bytes] = set()
    for path in body_sources:
        if not isinstance(path, str) or path not in contents:
            raise CompletionBuildError("generated source roles are invalid")
        bodies.update(BODY_RE.findall(contents[path]))
    for path in wrapper_sources:
        if not isinstance(path, str) or path not in contents:
            raise CompletionBuildError("generated source roles are invalid")
        wrappers.update(WRAPPER_RE.findall(contents[path]))
    if bodies != wrappers or len(bodies) != len(body_sources) or len(wrappers) != len(wrapper_sources):
        raise CompletionBuildError("generated callable aliases do not reconcile")
    opaque_aliases = sorted(_sha256(name) for name in bodies)
    return len(patch_sources), _sha256(_canonical_bytes(opaque_aliases))


def derive_public_core(
    index_document: object,
    bundle_root: Path,
    patch_provenance: object,
) -> dict[str, object]:
    """Derive the entire public G3 core; no aggregate values are accepted."""
    products = _prepared_products(index_document, bundle_root)
    generation_products = _execution_product_bytes(products, bundle_root, "generation")
    try:
        generated_contents = _generated_source_contents(generation_products)
    except AuditError as error:
        raise CompletionBuildError("generated source closure is invalid") from error
    generation = _json_product(
        generation_products["generation-result"],
        "jfg-phase4-generation-semantic-result",
    )
    if set(generation) != {
        "schema_version",
        "kind",
        "symbols",
        "calls",
        "relocations",
        "overlays",
        "stubs",
        "semantic_bindings",
    }:
        raise CompletionBuildError("generation semantic result is invalid")
    for field in ("symbols", "calls", "relocations", "overlays", "stubs"):
        if not isinstance(generation.get(field), dict):
            raise CompletionBuildError("generation semantic result is invalid")
    generation_public = {
        field: copy.deepcopy(generation[field])
        for field in ("symbols", "calls", "relocations", "overlays", "stubs")
    }
    try:
        _verify_generation_semantics(
            generation_products, generated_contents, generation_public
        )
    except AuditError as error:
        raise CompletionBuildError("generation semantic products do not close") from error

    forced = _execution_product_bytes(
        products, bundle_root, "forced-object-link-audit"
    )
    roles = _object_role_counts(forced["object-role-inventory"])
    patch_source_count, alias_ledger_sha256 = _source_role_facts(generated_contents)
    symbols = copy.deepcopy(generation["symbols"])
    calls = copy.deepcopy(generation["calls"])
    relocations = copy.deepcopy(generation["relocations"])
    stubs = copy.deepcopy(generation["stubs"])
    generation_overlays = copy.deepcopy(generation["overlays"])
    assert isinstance(symbols, dict)
    assert isinstance(calls, dict)
    assert isinstance(relocations, dict)
    assert isinstance(stubs, dict)
    assert isinstance(generation_overlays, dict)
    symbol_exclusions = symbols.get("exclusion_category_counts")
    if (
        symbols.get("expected_count") != EXPECTED_EXECUTABLE_SYMBOL_COUNT
        or symbols.get("generated_count") != EXPECTED_GENERATED_BODY_COUNT
        or symbols.get("replaceable_function_count") != EXPECTED_GENERATED_BODY_COUNT
        or symbols.get("excluded_count") != EXPECTED_COVERED_ALIAS_COUNT
        or symbol_exclusions
        != {
            "covered-alias": EXPECTED_COVERED_ALIAS_COUNT,
            "validated-non-code": 0,
            "runtime-abi": 0,
        }
    ):
        raise CompletionBuildError("executable symbol denominator is incomplete")
    direct_calls = calls.get("direct")
    if (
        not isinstance(direct_calls, dict)
        or direct_calls.get("candidate_count")
        != EXPECTED_STATIC_DIRECT_CALL_CANDIDATE_COUNT
        or direct_calls.get("expected_count")
        != EXPECTED_STATIC_DIRECT_CALL_CANDIDATE_COUNT
        or direct_calls.get("transfer_role_counts")
        != {
            "linked-call": EXPECTED_STATIC_LINKED_CALL_COUNT,
            "direct-tail": EXPECTED_STATIC_DIRECT_TAIL_COUNT,
        }
        or direct_calls.get("instruction_class_counts")
        != {
            "jal": EXPECTED_STATIC_JAL_CALL_CANDIDATE_COUNT,
            "bgezal": EXPECTED_STATIC_BGEZAL_CALL_CANDIDATE_COUNT,
            "j": EXPECTED_STATIC_J_CALL_CANDIDATE_COUNT,
            "conditional-branch": EXPECTED_STATIC_CONDITIONAL_BRANCH_CALL_CANDIDATE_COUNT,
        }
    ):
        raise CompletionBuildError("static direct-call candidate denominator is incomplete")
    indirect_ranges = calls.get("indirect_ranges")
    if (
        not isinstance(indirect_ranges, dict)
        or indirect_ranges.get("expected_count")
        != EXPECTED_STATIC_INDIRECT_TRANSFER_COUNT
        or indirect_ranges.get("resolved_count")
        != EXPECTED_STATIC_INDIRECT_TRANSFER_COUNT
        or indirect_ranges.get("native_return_count")
        != EXPECTED_NATIVE_RETURN_TRANSFER_COUNT
        or indirect_ranges.get("decision_range_count")
        != EXPECTED_DECISION_RANGE_TRANSFER_COUNT
    ):
        raise CompletionBuildError("static indirect transfer denominator is incomplete")
    data_r32 = relocations.get("data_r32")
    if (
        not isinstance(data_r32, dict)
        or data_r32.get("expected_count") != EXPECTED_R32_RELOCATION_COUNT
        or data_r32.get("resolved_count") != EXPECTED_R32_RELOCATION_COUNT
        or data_r32.get("approved_fail_closed_count") != 0
    ):
        raise CompletionBuildError("R32 relocation denominator is incomplete")
    if (
        generation_overlays.get("executable_section_count")
        != EXPECTED_EXECUTABLE_SECTION_COUNT
        or generation_overlays.get("expected_slot_count")
        != EXPECTED_OVERLAY_SLOT_COUNT
        or generation_overlays.get("listed_slot_count")
        != EXPECTED_OVERLAY_SLOT_COUNT
        or generation_overlays.get("lookup_table_slot_count")
        != EXPECTED_OVERLAY_SLOT_COUNT
        or generation_overlays.get("lifecycle_table_slot_count")
        != EXPECTED_OVERLAY_SLOT_COUNT
        or generation_overlays.get("populated_slot_count")
        != EXPECTED_POPULATED_OVERLAY_SLOT_COUNT
        or generation_overlays.get("generated_populated_module_count")
        != EXPECTED_POPULATED_OVERLAY_SLOT_COUNT
        or generation_overlays.get("empty_slot_count")
        != EXPECTED_EMPTY_OVERLAY_SLOT_COUNT
    ):
        raise CompletionBuildError("overlay section/slot denominator is incomplete")
    if (
        roles["baseline-body"] != symbols.get("generated_count")
        or roles["normal-wrapper"] != symbols.get("replaceable_function_count")
        or roles["patch"] != patch_source_count
        or roles["alternate-entry-thunk"]
        != symbols.get("alternate_entry_thunk_count")
        or (
            roles["section-address-support"]
            + roles["lookup-support"]
            + roles["lifecycle-support"]
            + roles["relocation-support"]
        )
        != 11
    ):
        raise CompletionBuildError("generated object roles do not reconcile")
    overlays = copy.deepcopy(generation_overlays)
    overlays.update(
        {
            "lookup_table_member_count": roles["lookup-support"],
            "lifecycle_table_member_count": roles["lifecycle-support"],
            "relocation_table_member_count": roles["relocation-support"],
            "forced_object_link_passed": True,
        }
    )
    generation_public["overlays"] = overlays
    try:
        _verify_cpu_section_inventory(
            generation_products["cpu-section-inventory"],
            generated_contents,
            generation_public,
        )
    except AuditError as error:
        raise CompletionBuildError("CPU inventory does not close public denominators") from error

    source_inventory_sha256 = _digest(products, "generation", "source-file-inventory")
    compilers: list[dict[str, object]] = []
    for family in ("clang", "gcc", "msvc"):
        evidence_kind = f"compiler-{family}"
        compiler_products = _execution_product_bytes(products, bundle_root, evidence_kind)
        if (
            compiler_products["generated-source-archive"]
            != generation_products["generated-source-archive"]
            or compiler_products["source-file-inventory"]
            != generation_products["source-file-inventory"]
        ):
            raise CompletionBuildError("compiler source closure differs")
        result = _public_result(
            products, bundle_root, evidence_kind, "compiler-result"
        )
        if result.get("family") != family or result.get(
            "source_inventory_sha256"
        ) != source_inventory_sha256:
            raise CompletionBuildError("compiler result identity differs")
        compilers.append(result)

    if (
        forced["generated-source-archive"]
        != generation_products["generated-source-archive"]
        or forced["source-file-inventory"]
        != generation_products["source-file-inventory"]
        or forced["overlay-lookup-table"]
        != generation_products["overlay-lookup-table"]
        or forced["overlay-lifecycle-table"]
        != generation_products["overlay-lifecycle-table"]
        or forced["relocation-table"] != generation_products["relocation-table"]
    ):
        raise CompletionBuildError("forced-link source closure differs")
    try:
        _verify_archive_pair(forced, "baseline-archive", "baseline-member-inventory")
        _verify_archive_pair(forced, "patch-archive", "patch-member-inventory")
        baseline_members = _member_inventory(forced["baseline-member-inventory"])
        patch_members = _member_inventory(forced["patch-member-inventory"])
    except AuditError as error:
        raise CompletionBuildError("forced-link member inventories are invalid") from error
    host_function_count = _host_inventory_count(
        forced["host-function-inventory"], "function"
    )
    host_data_count = _host_inventory_count(forced["host-data-inventory"], "data")
    if (
        host_function_count != roles["runtime-function"]
        or host_data_count != roles["runtime-data"]
    ):
        raise CompletionBuildError("host ownership inventories do not reconcile")

    baseline_expected = {
        "unmodified_body_member_count": roles["baseline-body"],
        "callable_wrapper_member_count": roles["normal-wrapper"],
        "alternate_entry_thunk_member_count": roles["alternate-entry-thunk"],
        "section_address_member_count": roles["section-address-support"],
        "lookup_table_member_count": roles["lookup-support"],
        "lifecycle_table_member_count": roles["lifecycle-support"],
        "relocation_table_member_count": roles["relocation-support"],
        "other_support_member_count": 0,
        "support_member_count": (
            roles["alternate-entry-thunk"]
            + roles["section-address-support"]
            + roles["lookup-support"]
            + roles["lifecycle-support"]
            + roles["relocation-support"]
        ),
        "member_count": len(baseline_members),
        "one_function_per_body_member_verified": True,
        "wrapper_to_body_mapping_verified": True,
        "alternate_entry_mapping_verified": True,
        "forced_object_link_passed": True,
        "compile_passed": True,
        "link_passed": True,
        "archive_sha256": _digest(products, "forced-object-link-audit", "baseline-archive"),
        "member_inventory_sha256": _digest(
            products, "forced-object-link-audit", "baseline-member-inventory"
        ),
    }
    if baseline_expected["member_count"] != (
        baseline_expected["unmodified_body_member_count"]
        + baseline_expected["callable_wrapper_member_count"]
        + baseline_expected["support_member_count"]
    ):
        raise CompletionBuildError("baseline member inventory does not reconcile")
    baseline = _require_observed_result(
        _public_result(
            products, bundle_root, "forced-object-link-audit", "baseline-result"
        ),
        baseline_expected,
        "baseline library",
    )

    patch_expected = {
        "approved_replacement_member_count": roles["patch"],
        "callable_wrapper_member_count": 0,
        "anchor_member_count": 1,
        "other_support_member_count": 0,
        "support_member_count": 1,
        "member_count": len(patch_members),
        "one_function_per_replacement_member_verified": True,
        "forced_object_link_passed": True,
        "compile_passed": True,
        "link_passed": True,
        "archive_sha256": _digest(products, "forced-object-link-audit", "patch-archive"),
        "member_inventory_sha256": _digest(
            products, "forced-object-link-audit", "patch-member-inventory"
        ),
    }
    if patch_expected["member_count"] != roles["patch"] + 1:
        raise CompletionBuildError("patch member inventory does not reconcile")
    patch = _require_observed_result(
        _public_result(products, bundle_root, "forced-object-link-audit", "patch-result"),
        patch_expected,
        "patch library",
    )

    runtime_abi_exclusions = symbols.get("exclusion_category_counts")
    runtime_abi_count = (
        runtime_abi_exclusions.get("runtime-abi")
        if isinstance(runtime_abi_exclusions, dict)
        else None
    )
    section_count = generation_overlays.get("executable_section_count")
    relocation_count = data_r32.get("expected_count") if isinstance(data_r32, dict) else None
    minimal_expected = {
        "target_runtime_abi_exclusion_count": runtime_abi_count,
        "required_host_function_export_count": host_function_count,
        "resolved_host_function_export_count": host_function_count,
        "required_host_data_export_count": host_data_count,
        "resolved_host_data_export_count": host_data_count,
        "unresolved_host_export_count": 0,
        "handwritten_bridge_unit_count": ANALYSIS_BRIDGE_UNIT_COUNT,
        "section_address_count": section_count,
        "section_address_capacity": SECTION_ADDRESS_CAPACITY,
        "initialized_section_address_count": section_count,
        "section_address_support_member_count": roles["section-address-support"],
        "section_initialization_passed": True,
        "section_exact_capacity_test_passed": True,
        "section_over_capacity_rejection_passed": True,
        "object_symbol_ownership_verified": True,
        "host_function_inventory_sha256": _digest(
            products, "forced-object-link-audit", "host-function-inventory"
        ),
        "host_data_inventory_sha256": _digest(
            products, "forced-object-link-audit", "host-data-inventory"
        ),
        "relocation_table_entry_count": relocation_count,
        "forced_object_link_passed": True,
    }
    minimal_runtime = _require_observed_result(
        _public_result(
            products,
            bundle_root,
            "forced-object-link-audit",
            "minimal-runtime-result",
        ),
        minimal_expected,
        "minimal runtime",
    )
    aliases = {
        "expected_count": roles["normal-wrapper"],
        "emitted_count": roles["normal-wrapper"],
        "duplicate_count": 0,
        "baseline_callable_test_passed": True,
        "ledger_sha256": alias_ledger_sha256,
    }
    strict_patch_mode = _derived_result(
        {
            "enabled": True,
            "approved_patch_function_count": roles["patch"],
            "unapproved_patch_rejection_passed": True,
            "duplicate_override_rejection_passed": True,
            "missing_baseline_alias_rejection_passed": True,
            "unsupported_instruction_patch_rejection_passed": True,
        }
    )
    language_contract = _derived_result(
        {
            "generated_language": "c",
            "bridge_linkage": "c-abi",
            "abi_audit_passed": True,
        }
    )
    libraries = {
        "baseline": baseline,
        "patch": patch,
        "aliases": aliases,
        "strict_patch_mode": strict_patch_mode,
        "minimal_runtime": minimal_runtime,
        "language_contract": language_contract,
    }
    try:
        _verify_forced_object_semantics(forced, generated_contents, libraries)
    except AuditError as error:
        raise CompletionBuildError("forced-link semantic products do not close") from error

    analysis_products = _execution_product_bytes(
        products, bundle_root, "clang-static-analysis"
    )
    analysis_inventory_sha256 = _digest(
        products, "clang-static-analysis", "analysis-source-inventory"
    )
    analyzer = _public_result(
        products, bundle_root, "clang-static-analysis", "analyzer-result"
    )
    sanitizers: list[dict[str, object]] = []
    for evidence_kind in ("address-sanitizer", "undefined-behavior-sanitizer"):
        sanitizer_products = _execution_product_bytes(
            products, bundle_root, evidence_kind
        )
        if (
            sanitizer_products["analysis-source-archive"]
            != analysis_products["analysis-source-archive"]
            or sanitizer_products["analysis-source-inventory"]
            != analysis_products["analysis-source-inventory"]
        ):
            raise CompletionBuildError("analysis source closure differs")
        result = _public_result(
            products, bundle_root, evidence_kind, "sanitizer-result"
        )
        if (
            result.get("run_count") != 1
            or result.get("issue_count") != 0
            or result.get("passed") is not True
            or result.get("source_inventory_sha256")
            != analysis_inventory_sha256
        ):
            raise CompletionBuildError("sanitizer result differs from executed policy")
        sanitizers.append(result)
    matrix = sorted(
        [
            {
                "sanitizer_id": result.get("sanitizer_id"),
                "compiler_family": result.get("compiler_family"),
                "target_id": result.get("target_id"),
            }
            for result in sanitizers
        ],
        key=lambda value: str(value["sanitizer_id"]),
    )
    analysis = {
        "source_inventory_sha256": analysis_inventory_sha256,
        "handwritten_bridge_unit_count": ANALYSIS_BRIDGE_UNIT_COUNT,
        "clang_static_analysis": analyzer,
        "sanitizers": sanitizers,
        "available_sanitizer_matrix_sha256": _sha256(_canonical_bytes(matrix)),
        "all_available_sanitizers_passed": True,
    }

    repro_a = _execution_product_bytes(products, bundle_root, "reproducibility-run-a")
    repro_b = _execution_product_bytes(products, bundle_root, "reproducibility-run-b")
    if set(repro_a) != set(repro_b) or any(
        repro_a[kind] != repro_b[kind] for kind in repro_a
    ):
        raise CompletionBuildError("reproducibility products differ")
    for kind in set(generation_products) & set(repro_a):
        if generation_products[kind] != repro_a[kind]:
            raise CompletionBuildError("generation and reproducibility products differ")
    for kind in ("baseline-member-inventory", "patch-member-inventory"):
        if forced[kind] != repro_a[kind]:
            raise CompletionBuildError("forced-link and reproducibility inventories differ")
    normalized = _load_json_bytes(repro_a["normalized-run-payload"])
    if (
        not isinstance(normalized, dict)
        or _canonical_bytes(normalized) != repro_a["normalized-run-payload"]
        or normalized.get("normalization_policy_id") != "phase4-run-payload-v1"
    ):
        raise CompletionBuildError("reproducibility normalization policy differs")
    reproducibility = {
        "normalization_policy_id": "phase4-run-payload-v1",
        "generation_run_count": 2,
        "distinct_normalized_run_digest_count": 1,
        "normalized_run_payload_sha256": _digest(
            products, "reproducibility-run-a", "normalized-run-payload"
        ),
        "generated_inventory_sha256": _digest(
            products, "generation", "generated-inventory"
        ),
        "cpu_section_inventory_sha256": _digest(
            products, "generation", "cpu-section-inventory"
        ),
        "overlay_table_sha256": _digest(
            products, "generation", "overlay-lookup-table"
        ),
        "lifecycle_table_sha256": _digest(
            products, "generation", "overlay-lifecycle-table"
        ),
        "relocation_table_sha256": _digest(
            products, "generation", "relocation-table"
        ),
        "report_set_sha256": _digest(products, "generation", "report-set"),
        "source_file_inventory_sha256": source_inventory_sha256,
        "baseline_member_inventory_sha256": _digest(
            products, "forced-object-link-audit", "baseline-member-inventory"
        ),
        "patch_member_inventory_sha256": _digest(
            products, "forced-object-link-audit", "patch-member-inventory"
        ),
        "all_artifact_classes_match": True,
        "byte_equivalent_inventory": True,
        "passed": True,
    }

    config_products = _execution_product_bytes(
        products, bundle_root, "configuration-mutation"
    )
    expectation = _load_json_bytes(config_products["predeclared-expectation"])
    mutated_set = _load_json_bytes(config_products["mutated-config-set"])
    mutation_ids = mutated_set.get("mutation_ids") if isinstance(mutated_set, dict) else None
    if (
        not isinstance(expectation, dict)
        or not isinstance(mutation_ids, list)
        or not mutation_ids
        or not all(isinstance(value, str) and value for value in mutation_ids)
        or len(mutation_ids) != len(set(mutation_ids))
        or not all(type(value) is int and value >= 0 for value in expectation.values())
    ):
        raise CompletionBuildError("configuration mutation declaration is invalid")
    zero_categories = {key: 0 for key in expectation}
    config_expected = {
        "mutation_case_count": len(mutation_ids),
        "base_config_sha256": _digest(
            products, "configuration-mutation", "base-config"
        ),
        "mutated_config_set_sha256": _digest(
            products, "configuration-mutation", "mutated-config-set"
        ),
        "predeclared_expectation_sha256": _digest(
            products, "configuration-mutation", "predeclared-expectation"
        ),
        "expected_change_count": sum(expectation.values()),
        "observed_change_count": sum(expectation.values()),
        "expected_category_counts": expectation,
        "observed_category_counts": copy.deepcopy(expectation),
        "unexpected_change_count": 0,
        "unexpected_category_counts": zero_categories,
        "containment_passed": True,
    }
    config_diff = _require_observed_result(
        _public_result(
            products, bundle_root, "configuration-mutation", "config-diff-result"
        ),
        config_expected,
        "configuration mutation",
    )
    try:
        _verify_config_mutation(config_products, config_diff)
    except AuditError as error:
        raise CompletionBuildError("configuration mutation products do not reconcile") from error

    pins = _dependency_pins(
        generation_products,
        analysis_inventory_sha256,
        config_expected["base_config_sha256"],
        patch_provenance,
    )
    core = {
        "pins": pins,
        "symbols": symbols,
        "calls": calls,
        "relocations": relocations,
        "overlays": overlays,
        "stubs": stubs,
        "compilers": compilers,
        "analysis": analysis,
        "libraries": libraries,
        "reproducibility": reproducibility,
        "config_diff": config_diff,
    }
    errors = validate_phase4_public_core(core)
    if errors:
        raise CompletionBuildError("derived public aggregate core is invalid")
    return core


def unsigned_completion(
    core: dict[str, object], private_evidence_bytes: bytes, g2_document: object
) -> dict[str, object]:
    if not isinstance(g2_document, dict):
        raise CompletionBuildError("G2 public evidence is unavailable")
    return {
        "$schema": "../schemas/phase4-generated-manifest.schema.json",
        "schema_version": 2,
        "kind": "jfg-phase4-generated-manifest",
        "privacy": "public-safe-aggregate-only",
        "record_class": "maintainer-attested-public-aggregate",
        **copy.deepcopy(core),
        "attestation": {
            "evidence_class": "private-regenerable-aggregate",
            "body_policy": "local-only-not-exported",
            "private_evidence_sha256": _sha256(private_evidence_bytes),
            "authentication": {
                "algorithm": "openssh-ed25519",
                "key_id": EXPECTED_KEY_ID,
                "principal": EXPECTED_SIGNER_PRINCIPAL,
                "namespace": EXPECTED_SIGNATURE_NAMESPACE,
            },
        },
        "gate": {
            "id": "G3-M1",
            "scope": "whole-program",
            "claim": "phase4-complete",
            "predecessor_g2_complete": True,
            "predecessor_g2_evidence_sha256": _sha256(_canonical_bytes(g2_document)),
            "g3_complete": True,
            "all_required_checks_passed": True,
        },
    }


def _adr_is_accepted() -> bool:
    try:
        payload = _read_regular(ARCHITECTURE_DECISION, maximum=MAX_CORE_BYTES)
        text = payload.decode("utf-8")
    except (PreparationError, UnicodeDecodeError):
        return False
    return accepted_architecture_decision(text)


def finalize(
    index_document: object,
    bundle_root: Path,
    patch_provenance: object,
    private_evidence_path: Path,
    g2_document: object,
    g2_private_evidence_path: Path,
    private_key_path: Path,
) -> dict[str, object]:
    if not _adr_is_accepted():
        raise CompletionBuildError("dependency architecture ADR has not been explicitly accepted")
    private_bytes = _read_regular(private_evidence_path, maximum=8 * 1024 * 1024)
    core = derive_public_core(index_document, bundle_root, patch_provenance)
    candidate = unsigned_completion(core, private_bytes, g2_document)

    errors = validate_g2_evidence_document(g2_document, load_json(DEFAULT_G2_SCHEMA))
    errors.extend(validate_g2_private_file(g2_private_evidence_path, g2_document))
    errors.extend(validate_phase4_private_file(private_evidence_path, candidate))
    pins = candidate.get("pins")
    g2_pins = g2_document.get("pins") if isinstance(g2_document, dict) else None
    if isinstance(pins, dict) and isinstance(g2_pins, dict):
        for field in (
            "jfg_decomp_commit",
            "n64recomp_commit",
            "supported_input_id",
            "dependency_lock_sha256",
        ):
            if pins.get(field) != g2_pins.get(field):
                errors.append("G2 and Phase 4 pins differ")
                break
    else:
        errors.append("G2 and Phase 4 pins are unavailable")
    if errors:
        raise CompletionBuildError("private product or G2 verification failed")

    signed = sign_completion_manifest(candidate, private_key_path)
    final_errors = validate_trusted_completion(
        signed,
        load_json(DEFAULT_SCHEMA),
        g2_document,
        load_json(DEFAULT_G2_SCHEMA),
        private_evidence_path=private_evidence_path,
        g2_private_evidence_path=g2_private_evidence_path,
    )
    if final_errors:
        raise CompletionBuildError("signed completion did not pass trusted validation")
    assert isinstance(signed, dict)
    return signed


def _write_canonical_output(document: dict[str, object]) -> None:
    destination = CANONICAL_COMPLETION_MANIFEST
    if destination.exists() or _is_reparse(destination) or _is_reparse(destination.parent):
        raise CompletionBuildError("canonical completion output already exists or is unsafe")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    if temporary.exists() or _is_reparse(temporary):
        raise CompletionBuildError("canonical completion temporary output is unavailable")
    payload = json.dumps(document, indent=2, ensure_ascii=True, allow_nan=False).encode("utf-8") + b"\n"
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, destination)
    except OSError as error:
        raise CompletionBuildError("canonical completion output could not be written") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared-index", required=True, type=Path)
    parser.add_argument("--patch-provenance", required=True, type=Path)
    parser.add_argument("--private-evidence", required=True, type=Path)
    parser.add_argument("--g2-evidence", required=True, type=Path)
    parser.add_argument("--g2-private-evidence", required=True, type=Path)
    parser.add_argument("--private-key", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        if not _is_ignored(arguments.prepared_index) or not _is_ignored(
            arguments.patch_provenance
        ):
            raise CompletionBuildError("private product inputs must remain Git-ignored")
        index_path = arguments.prepared_index.resolve(strict=True)
        bundle_root = index_path.parent
        index = _load_json_bytes(_read_regular(index_path, maximum=MAX_INDEX_BYTES))
        patch_provenance = _load_json_bytes(
            _read_regular(arguments.patch_provenance, maximum=MAX_CORE_BYTES)
        )
        g2_document = load_json(arguments.g2_evidence)
        signed = finalize(
            index,
            bundle_root,
            patch_provenance,
            arguments.private_evidence,
            g2_document,
            arguments.g2_private_evidence,
            arguments.private_key,
        )
        _write_canonical_output(signed)
    except (CompletionBuildError, PreparationError, OSError, ValueError, TypeError, json.JSONDecodeError):
        print("Phase 4 completion finalization failed: prerequisites are not closed", file=sys.stderr)
        return 1
    print("Phase 4 completion manifest finalized at evidence/phase4-completion.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
