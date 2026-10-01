#!/usr/bin/env python3
"""Validate local-only, executed Phase 4 completion evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

if __package__:
    from .validate_g2_private_evidence import (
        EvidenceError,
        PinnedHarness,
        _artifact_path,
        _canonical_bytes,
        _checked_absolute,
        _is_placeholder,
        _private_path_is_allowed,
        _read_regular_bounded,
        _schema_errors,
        execute_pinned_harness,
    )
else:
    from validate_g2_private_evidence import (
        EvidenceError,
        PinnedHarness,
        _artifact_path,
        _canonical_bytes,
        _checked_absolute,
        _is_placeholder,
        _private_path_is_allowed,
        _read_regular_bounded,
        _schema_errors,
        execute_pinned_harness,
    )


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_SCHEMA = ROOT / "schemas" / "phase4-private-evidence.schema.json"

EVIDENCE_KINDS = (
    "generation",
    "compiler-clang",
    "compiler-gcc",
    "compiler-msvc",
    "forced-object-link-audit",
    "clang-static-analysis",
    "address-sanitizer",
    "undefined-behavior-sanitizer",
    "reproducibility-run-a",
    "reproducibility-run-b",
    "configuration-mutation",
)
G3_PRODUCT_CORE_FIELDS = (
    "pins",
    "symbols",
    "calls",
    "relocations",
    "overlays",
    "stubs",
    "compilers",
    "analysis",
    "libraries",
    "reproducibility",
    "config_diff",
)
G3_PRODUCT_PROJECTION_KIND = "jfg-phase4-g3-product-projection"
G3_PRODUCT_PROJECTION_KEYS = frozenset(
    {
        "schema_version",
        "kind",
        "completion",
        "private_evidence_sha256",
        *G3_PRODUCT_CORE_FIELDS,
    }
)
MAX_PRIVATE_BUNDLE_BYTES = 8 * 1024 * 1024
MAX_SCHEMA_BYTES = 2 * 1024 * 1024
# Must match the pinned production harness bound: the fixed generation product
# set includes the ROM-backed generation-input archive, which the harness
# accepts up to its own 128 MiB artifact limit.
MAX_ARTIFACT_BYTES = 128 * 1024 * 1024
MAX_RESULT_BYTES = 512 * 1024

_INPUT_ROLES = frozenset({"configuration", "input", "expectation"})
_OUTPUT_ROLES = frozenset({"output", "log"})
_RESULT_KEYS = frozenset(
    {
        "schema_version",
        "kind",
        "execution_id",
        "evidence_kind",
        "harness_id",
        "harness_sha256",
        "case_id",
        "public_claim_sha256",
        "public_record_sha256",
        "public_result_set_sha256",
        "subject_sha256",
        "source_input_sha256",
        "declaration_sha256",
        "pins_sha256",
        "environment_sha256",
        "input_set_sha256",
        "output_set_sha256",
        "observed_exit_code",
        "passed",
    }
)
_TRANSCRIPT_KEYS = frozenset(
    set(_RESULT_KEYS) | {"artifact_set_sha256", "result_sha256", "validated"}
)
ANALYSIS_SOURCE_POLICY_ID = "phase4-handwritten-bridges-analysis-v2"
ANALYSIS_BRIDGE_UNIT_COUNT = 3


# The single tracked verifier has an internal closed dispatch over EVIDENCE_KINDS.
# Private evidence selects neither its executable nor any child command.
_PRODUCTION_HARNESS = PinnedHarness(
    harness_id="phase4-production-audit-v1",
    script_path=ROOT / "scripts" / "phase4_evidence_harness.py",
    script_sha256="2d2b36ea71a829f2e095e3006dab216a4a29f87b07452eab185bbac7fe964563",
    timeout_seconds=1800.0,
)
PRODUCTION_HARNESS_PINS: Mapping[str, PinnedHarness] = MappingProxyType(
    {evidence_kind: _PRODUCTION_HARNESS for evidence_kind in EVIDENCE_KINDS}
)
_TRUSTED_HARNESS_PINS = PRODUCTION_HARNESS_PINS


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json_loads(payload: bytes) -> object:
    def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    return json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=reject_duplicates,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )


def _digest(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
        and not _is_placeholder(value)
    )


def _public_claim_projection(document: dict[str, object]) -> dict[str, object]:
    """Return the exact G3 product fields shared before and after G2.

    Completion metadata, the predecessor G2 digest, the private-body digest,
    and the signature are intentionally outside this projection.  The final
    completion validator authenticates those fields separately.
    """
    if any(field not in document for field in G3_PRODUCT_CORE_FIELDS):
        raise ValueError("G3 product projection is incomplete")
    return {
        field: copy.deepcopy(document[field]) for field in G3_PRODUCT_CORE_FIELDS
    }


def g3_product_projection(
    core: dict[str, object], private_evidence_sha256: str
) -> dict[str, object]:
    """Build the strict, explicitly non-completion pre-G2 public projection."""
    if set(core) != set(G3_PRODUCT_CORE_FIELDS) or not _digest(
        private_evidence_sha256
    ):
        raise ValueError("G3 product projection is invalid")
    return {
        "schema_version": 1,
        "kind": G3_PRODUCT_PROJECTION_KIND,
        "completion": False,
        "private_evidence_sha256": private_evidence_sha256,
        **copy.deepcopy(core),
    }


def g3_product_projection_errors(document: object) -> list[str]:
    error = "Phase 4 G3 product projection is invalid"
    if (
        not isinstance(document, dict)
        or set(document) != G3_PRODUCT_PROJECTION_KEYS
        or document.get("schema_version") != 1
        or document.get("kind") != G3_PRODUCT_PROJECTION_KIND
        or document.get("completion") is not False
        or not _digest(document.get("private_evidence_sha256"))
    ):
        return [error]
    try:
        projection = _public_claim_projection(document)
        if set(projection) != set(G3_PRODUCT_CORE_FIELDS):
            return [error]
        _canonical_bytes(projection)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return [error]
    # Imported lazily because the public manifest validator owns the pinned
    # Phase 4 schema and imports this module for private-body validation.
    if __package__:
        from .validate_phase4_manifest import validate_phase4_public_core
    else:
        from validate_phase4_manifest import validate_phase4_public_core
    if validate_phase4_public_core(projection):
        return [error]
    return []


def public_claim_sha256(document: dict[str, object]) -> str:
    return _sha256(_canonical_bytes(_public_claim_projection(document)))


def _digest_fields(value: object, path: str = "$") -> list[list[str]]:
    records: list[list[str]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            child = value[key]
            child_path = f"{path}.{key}"
            if (
                isinstance(child, str)
                and key.endswith("_sha256")
                and len(child) == 64
            ):
                records.append([child_path, child])
            records.extend(_digest_fields(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            records.extend(_digest_fields(child, f"{path}[{index}]"))
    return records


def _compiler(document: dict[str, object], family: str) -> dict[str, object] | None:
    compilers = document.get("compilers")
    if not isinstance(compilers, list):
        return None
    matches = [
        item
        for item in compilers
        if isinstance(item, dict) and item.get("family") == family
    ]
    return matches[0] if len(matches) == 1 else None


def _sanitizer(
    document: dict[str, object], sanitizer_id: str
) -> dict[str, object] | None:
    analysis = document.get("analysis")
    sanitizers = analysis.get("sanitizers") if isinstance(analysis, dict) else None
    if not isinstance(sanitizers, list):
        return None
    matches = [
        item
        for item in sanitizers
        if isinstance(item, dict) and item.get("sanitizer_id") == sanitizer_id
    ]
    return matches[0] if len(matches) == 1 else None


def _binding(
    document: dict[str, object], evidence_kind: str
) -> dict[str, object] | None:
    pins = document.get("pins")
    if not isinstance(pins, dict):
        return None

    record: object
    source_input: object
    subject: object
    declaration: object
    toolchain: object | None = None
    expected_products: dict[str, object]

    if evidence_kind == "generation":
        keys = ("symbols", "calls", "relocations", "overlays", "stubs")
        if any(key not in document for key in keys):
            return None
        record = {key: document[key] for key in keys}
        source_input = pins.get("input_elf_sha256")
        subject = source_input
        declaration = pins.get("config_sha256")
        toolchain = pins.get("generator_executable_sha256")
        reproducibility = document.get("reproducibility")
        if not isinstance(reproducibility, dict):
            return None
        expected_products = {
            "generated-inventory": reproducibility.get("generated_inventory_sha256"),
            "cpu-section-inventory": reproducibility.get(
                "cpu_section_inventory_sha256"
            ),
            "source-file-inventory": reproducibility.get("source_file_inventory_sha256"),
            "overlay-lookup-table": reproducibility.get("overlay_table_sha256"),
            "overlay-lifecycle-table": reproducibility.get("lifecycle_table_sha256"),
            "relocation-table": reproducibility.get("relocation_table_sha256"),
            "report-set": reproducibility.get("report_set_sha256"),
        }
    elif evidence_kind.startswith("compiler-"):
        family = evidence_kind.removeprefix("compiler-")
        compiler = _compiler(document, family)
        if compiler is None:
            return None
        record = compiler
        source_input = compiler.get("source_inventory_sha256")
        subject = source_input
        declaration = compiler.get("option_set_sha256")
        toolchain = compiler.get("compiler_executable_sha256")
        expected_products = {
            "compiler-result": compiler.get("result_sha256"),
            "source-file-inventory": compiler.get("source_inventory_sha256"),
        }
    elif evidence_kind == "forced-object-link-audit":
        compilers = document.get("compilers")
        overlays = document.get("overlays")
        libraries = document.get("libraries")
        if not isinstance(compilers, list) or not isinstance(overlays, dict) or not isinstance(libraries, dict):
            return None
        sources = {
            item.get("source_inventory_sha256")
            for item in compilers
            if isinstance(item, dict)
        }
        if len(sources) != 1:
            return None
        record = {
            "compilers": compilers,
            "overlays": overlays,
            "libraries": libraries,
        }
        source_input = next(iter(sources))
        subject = source_input
        declaration = pins.get("config_sha256")
        baseline = libraries.get("baseline")
        patch = libraries.get("patch")
        minimal = libraries.get("minimal_runtime")
        if not all(isinstance(value, dict) for value in (baseline, patch, minimal)):
            return None
        assert isinstance(baseline, dict)
        assert isinstance(patch, dict)
        assert isinstance(minimal, dict)
        expected_products = {
            "source-file-inventory": source_input,
            "baseline-archive": baseline.get("archive_sha256"),
            "baseline-member-inventory": baseline.get("member_inventory_sha256"),
            "baseline-result": baseline.get("result_sha256"),
            "patch-archive": patch.get("archive_sha256"),
            "patch-member-inventory": patch.get("member_inventory_sha256"),
            "patch-result": patch.get("result_sha256"),
            "minimal-runtime-result": minimal.get("result_sha256"),
            "host-function-inventory": minimal.get("host_function_inventory_sha256"),
            "host-data-inventory": minimal.get("host_data_inventory_sha256"),
            "overlay-lookup-table": overlays.get("lookup_table_sha256"),
            "overlay-lifecycle-table": overlays.get("lifecycle_table_sha256"),
            "relocation-table": overlays.get("relocation_table_sha256"),
        }
    elif evidence_kind == "clang-static-analysis":
        analysis = document.get("analysis")
        analyzer = analysis.get("clang_static_analysis") if isinstance(analysis, dict) else None
        if not isinstance(analysis, dict) or not isinstance(analyzer, dict):
            return None
        record = {
            "result": analyzer,
            "source_policy_id": ANALYSIS_SOURCE_POLICY_ID,
            "handwritten_bridge_unit_count": analysis.get("handwritten_bridge_unit_count"),
        }
        source_input = analysis.get("source_inventory_sha256")
        subject = source_input
        declaration = _sha256(_canonical_bytes({"tool_id": analyzer.get("tool_id")}))
        clang = _compiler(document, "clang")
        toolchain = clang.get("compiler_executable_sha256") if clang else None
        expected_products = {
            "analysis-source-inventory": analysis.get("source_inventory_sha256"),
            "analyzer-result": analyzer.get("result_sha256"),
        }
    elif evidence_kind in {"address-sanitizer", "undefined-behavior-sanitizer"}:
        sanitizer_id = (
            "address"
            if evidence_kind == "address-sanitizer"
            else "undefined-behavior"
        )
        sanitizer = _sanitizer(document, sanitizer_id)
        if sanitizer is None:
            return None
        analysis = document.get("analysis")
        if not isinstance(analysis, dict):
            return None
        record = {
            "result": sanitizer,
            "source_policy_id": ANALYSIS_SOURCE_POLICY_ID,
            "handwritten_bridge_unit_count": analysis.get("handwritten_bridge_unit_count"),
        }
        source_input = sanitizer.get("source_inventory_sha256")
        subject = source_input
        declaration = _sha256(
            _canonical_bytes(
                {
                    "sanitizer_id": sanitizer.get("sanitizer_id"),
                    "compiler_family": sanitizer.get("compiler_family"),
                    "target_id": sanitizer.get("target_id"),
                }
            )
        )
        compiler = _compiler(document, str(sanitizer.get("compiler_family")))
        toolchain = compiler.get("compiler_executable_sha256") if compiler else None
        expected_products = {
            "analysis-source-inventory": sanitizer.get("source_inventory_sha256"),
            "sanitizer-result": sanitizer.get("result_sha256"),
        }
    elif evidence_kind in {"reproducibility-run-a", "reproducibility-run-b"}:
        reproducibility = document.get("reproducibility")
        if not isinstance(reproducibility, dict):
            return None
        record = reproducibility
        source_input = pins.get("input_elf_sha256")
        subject = source_input
        declaration = _sha256(
            _canonical_bytes(
                {"normalization_policy_id": reproducibility.get("normalization_policy_id")}
            )
        )
        toolchain = pins.get("generator_executable_sha256")
        expected_products = {
            "normalized-run-payload": reproducibility.get("normalized_run_payload_sha256"),
            "generated-inventory": reproducibility.get("generated_inventory_sha256"),
            "cpu-section-inventory": reproducibility.get(
                "cpu_section_inventory_sha256"
            ),
            "overlay-lookup-table": reproducibility.get("overlay_table_sha256"),
            "overlay-lifecycle-table": reproducibility.get("lifecycle_table_sha256"),
            "relocation-table": reproducibility.get("relocation_table_sha256"),
            "report-set": reproducibility.get("report_set_sha256"),
            "source-file-inventory": reproducibility.get("source_file_inventory_sha256"),
            "baseline-member-inventory": reproducibility.get(
                "baseline_member_inventory_sha256"
            ),
            "patch-member-inventory": reproducibility.get("patch_member_inventory_sha256"),
        }
    elif evidence_kind == "configuration-mutation":
        config_diff = document.get("config_diff")
        if not isinstance(config_diff, dict):
            return None
        record = config_diff
        source_input = config_diff.get("base_config_sha256")
        subject = config_diff.get("mutated_config_set_sha256")
        declaration = config_diff.get("predeclared_expectation_sha256")
        toolchain = pins.get("generator_executable_sha256")
        expected_products = {
            "base-config": config_diff.get("base_config_sha256"),
            "mutated-config-set": config_diff.get("mutated_config_set_sha256"),
            "predeclared-expectation": config_diff.get(
                "predeclared_expectation_sha256"
            ),
            "config-diff-result": config_diff.get("result_sha256"),
        }
    else:
        return None

    values = (source_input, subject, declaration)
    if not all(isinstance(value, str) and len(value) == 64 for value in values):
        return None
    if not expected_products or not all(
        isinstance(value, str) and len(value) == 64
        for value in expected_products.values()
    ):
        return None
    record_sha256 = _sha256(_canonical_bytes(record))
    result_set_sha256 = _sha256(_canonical_bytes(_digest_fields(record)))
    return {
        "public_record_sha256": record_sha256,
        "public_result_set_sha256": result_set_sha256,
        "source_input_sha256": source_input,
        "subject_sha256": subject,
        "declaration_sha256": declaration,
        "toolchain_sha256": toolchain,
        "public_record": record,
        "expected_products": expected_products,
    }


def _result_expectation(
    document: dict[str, object], execution: dict[str, object]
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "jfg-phase4-execution-result",
        "execution_id": execution.get("id"),
        "evidence_kind": execution.get("evidence_kind"),
        "harness_id": execution.get("harness_id"),
        "harness_sha256": execution.get("harness_sha256"),
        "case_id": execution.get("case_id"),
        "public_claim_sha256": document.get("public_claim_sha256"),
        "public_record_sha256": execution.get("public_record_sha256"),
        "public_result_set_sha256": execution.get("public_result_set_sha256"),
        "subject_sha256": execution.get("subject_sha256"),
        "source_input_sha256": execution.get("source_input_sha256"),
        "declaration_sha256": execution.get("declaration_sha256"),
        "pins_sha256": execution.get("pins_sha256"),
        "environment_sha256": execution.get("environment_sha256"),
        "input_set_sha256": execution.get("input_set_sha256"),
        "output_set_sha256": execution.get("output_set_sha256"),
        "observed_exit_code": execution.get("observed_exit_code"),
        "passed": execution.get("passed"),
    }


def _transcript_expectation(
    document: dict[str, object], execution: dict[str, object]
) -> dict[str, object]:
    expected = _result_expectation(document, execution)
    expected.update(
        {
            "kind": "jfg-phase4-harness-transcript",
            "artifact_set_sha256": execution.get("artifact_set_sha256"),
            "result_sha256": execution.get("result_sha256"),
            "validated": True,
        }
    )
    return expected


def _execution_errors(
    private_document: dict[str, object],
    public_document: dict[str, object],
    execution: dict[str, object],
    bundle_root: Path,
    harness_pins: Mapping[str, PinnedHarness],
    *,
    require_tracked_harnesses: bool,
    all_paths: set[str],
) -> list[str]:
    errors: list[str] = []
    evidence_kind = execution.get("evidence_kind")
    try:
        binding = _binding(public_document, str(evidence_kind))
    except (KeyError, TypeError, ValueError, RecursionError):
        binding = None
    if binding is None:
        errors.append("Phase 4 private evidence: public binding is unavailable")
    else:
        for field in (
            "public_record_sha256",
            "public_result_set_sha256",
            "source_input_sha256",
            "subject_sha256",
            "declaration_sha256",
        ):
            if execution.get(field) != binding.get(field):
                errors.append("Phase 4 private evidence: public execution binding differs")
        environment = execution.get("environment")
        if (
            isinstance(environment, dict)
            and isinstance(binding.get("toolchain_sha256"), str)
            and environment.get("toolchain_sha256") != binding.get("toolchain_sha256")
        ):
            errors.append("Phase 4 private evidence: toolchain identity differs")

    artifacts = execution.get("artifacts")
    if not isinstance(artifacts, list):
        return errors + ["Phase 4 private evidence: artifacts are unavailable"]
    role_records: dict[str, list[dict[str, object]]] = {
        role: []
        for role in ("configuration", "input", "expectation", "output", "result", "log")
    }
    result_bytes: bytes | None = None
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        textual_path = artifact.get("path")
        role = artifact.get("role")
        expected_digest = artifact.get("sha256")
        if isinstance(textual_path, str):
            if textual_path in all_paths:
                errors.append("Phase 4 private evidence: artifact paths are not globally unique")
            all_paths.add(textual_path)
        try:
            artifact_path = _artifact_path(bundle_root, textual_path)
            privacy = _private_path_is_allowed(artifact_path)
            if privacy is None:
                errors.append("Phase 4 private evidence: artifact privacy could not be verified")
            elif not privacy:
                errors.append("Phase 4 private evidence: artifact must be external or ignored")
            limit = MAX_RESULT_BYTES if role == "result" else MAX_ARTIFACT_BYTES
            payload = _read_regular_bounded(
                artifact_path,
                max_bytes=limit,
                within=bundle_root,
            )
            actual_digest = _sha256(payload)
        except EvidenceError:
            payload = None
            actual_digest = None
            errors.append("Phase 4 private evidence: artifact boundary or bounded read failed")
        if actual_digest != expected_digest:
            errors.append("Phase 4 private evidence: artifact digest mismatch")
        record = {"path": textual_path, "role": role, "sha256": expected_digest}
        if isinstance(role, str) and role in role_records:
            role_records[role].append(record)
            if role == "result" and payload is not None:
                result_bytes = payload

    if not role_records["configuration"]:
        errors.append("Phase 4 private evidence: configuration artifact is absent")
    if not role_records["output"]:
        errors.append("Phase 4 private evidence: output artifact is absent")
    if len(role_records["result"]) != 1:
        errors.append("Phase 4 private evidence: exactly one result artifact is required")
        result_bytes = None
    if evidence_kind == "configuration-mutation":
        if len(role_records["expectation"]) != 1 or role_records["expectation"][0].get(
            "sha256"
        ) != execution.get("declaration_sha256"):
            errors.append("Phase 4 private evidence: predeclared mutation expectation is unbound")
    elif role_records["expectation"]:
        errors.append("Phase 4 private evidence: unexpected expectation artifact")

    input_records = [
        record
        for role in ("configuration", "input", "expectation")
        for record in role_records[role]
    ]
    output_records = role_records["output"] + role_records["log"]
    input_digests = {record.get("sha256") for record in input_records}
    if execution.get("source_input_sha256") not in input_digests:
        errors.append("Phase 4 private evidence: source input artifact is unbound")
    if execution.get("subject_sha256") not in input_digests:
        errors.append("Phase 4 private evidence: subject artifact is unbound")
    if execution.get("declaration_sha256") not in input_digests:
        errors.append("Phase 4 private evidence: declaration artifact is unbound")

    expected_values = {
        "pins_sha256": _sha256(_canonical_bytes(private_document.get("pins"))),
        "environment_sha256": _sha256(_canonical_bytes(execution.get("environment"))),
        "input_set_sha256": _sha256(_canonical_bytes(input_records)),
        "output_set_sha256": _sha256(_canonical_bytes(output_records)),
        "artifact_set_sha256": _sha256(_canonical_bytes(artifacts)),
    }
    for field, expected in expected_values.items():
        if execution.get(field) != expected:
            errors.append("Phase 4 private evidence: execution binding digest is invalid")

    if result_bytes is not None:
        result_digest = _sha256(result_bytes)
        try:
            result_document = _json_loads(result_bytes)
        except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
            result_document = None
            errors.append("Phase 4 private evidence: structured result is invalid")
        if not isinstance(result_document, dict) or set(result_document) != _RESULT_KEYS:
            errors.append("Phase 4 private evidence: structured result contract differs")
        else:
            try:
                bound = _canonical_bytes(result_document) == _canonical_bytes(
                    _result_expectation(private_document, execution)
                )
            except (TypeError, ValueError, RecursionError):
                bound = False
            if not bound:
                errors.append("Phase 4 private evidence: structured result is unbound")
        if execution.get("result_sha256") != result_digest:
            errors.append("Phase 4 private evidence: result digest is unbound")
    else:
        errors.append("Phase 4 private evidence: result digest is unbound")

    for field in (
        "harness_sha256",
        "public_record_sha256",
        "public_result_set_sha256",
        "subject_sha256",
        "source_input_sha256",
        "declaration_sha256",
        "pins_sha256",
        "environment_sha256",
        "input_set_sha256",
        "output_set_sha256",
        "artifact_set_sha256",
        "result_sha256",
    ):
        if _is_placeholder(execution.get(field)):
            errors.append("Phase 4 private evidence: placeholder identity is forbidden")

    pin = harness_pins.get(str(evidence_kind))
    if pin is None:
        errors.append("Phase 4 private evidence: pinned harness is unavailable")
    elif (
        execution.get("harness_id") != pin.harness_id
        or execution.get("harness_sha256") != pin.script_sha256
    ):
        errors.append("Phase 4 private evidence: execution does not use the pinned harness")
    elif not errors:
        request = {
            "schema_version": 1,
            "kind": "jfg-phase4-harness-request",
            "public_claim_sha256": private_document.get("public_claim_sha256"),
            "pins": private_document.get("pins"),
            "execution": execution,
            "public_binding": {
                "public_record": binding.get("public_record") if binding else None,
                "expected_products": binding.get("expected_products") if binding else None,
                "toolchain_sha256": binding.get("toolchain_sha256") if binding else None,
            },
        }
        transcript, harness_errors = execute_pinned_harness(
            pin,
            request,
            bundle_root,
            require_tracked=require_tracked_harnesses,
        )
        errors.extend(harness_errors)
        if not isinstance(transcript, dict) or set(transcript) != _TRANSCRIPT_KEYS:
            errors.append("Phase 4 private evidence: harness transcript contract differs")
        else:
            try:
                bound = _canonical_bytes(transcript) == _canonical_bytes(
                    _transcript_expectation(private_document, execution)
                )
            except (TypeError, ValueError, RecursionError):
                bound = False
            if not bound:
                errors.append("Phase 4 private evidence: harness transcript is unbound")
    return errors


def _validate_documents(
    private_document: object,
    public_document: object,
    private_schema: object,
    bundle_root: Path,
    harness_pins: Mapping[str, PinnedHarness],
    *,
    require_tracked_harnesses: bool,
) -> list[str]:
    errors = _schema_errors(private_document, private_schema)
    if errors or not isinstance(private_document, dict) or not isinstance(public_document, dict):
        return sorted(set(errors or ["Phase 4 private evidence: document is unavailable"]))

    try:
        expected_public_claim = public_claim_sha256(public_document)
    except (TypeError, ValueError, RecursionError):
        expected_public_claim = None
        errors.append("Phase 4 private evidence: public claim is not canonical")
    if private_document.get("public_claim_sha256") != expected_public_claim:
        errors.append("Phase 4 private evidence: public claim digest is unbound")
    if private_document.get("pins") != public_document.get("pins"):
        errors.append("Phase 4 private evidence: public and private pins differ")
    expected_pins = _sha256(_canonical_bytes(private_document.get("pins")))
    if private_document.get("pins_sha256") != expected_pins:
        errors.append("Phase 4 private evidence: pin-set digest is unbound")

    executions = private_document.get("executions")
    if not isinstance(executions, list):
        return sorted(set(errors + ["Phase 4 private evidence: executions are unavailable"]))
    expected_evidence_set = _sha256(_canonical_bytes(executions))
    if private_document.get("evidence_set_sha256") != expected_evidence_set:
        errors.append("Phase 4 private evidence: execution-set digest is unbound")

    records = [item for item in executions if isinstance(item, dict)]
    ids = [item.get("id") for item in records]
    kinds = [item.get("evidence_kind") for item in records]
    if len(ids) != len(set(ids)):
        errors.append("Phase 4 private evidence: execution IDs are not unique")
    if sorted(str(kind) for kind in kinds) != sorted(EVIDENCE_KINDS):
        errors.append("Phase 4 private evidence: exact execution matrix is incomplete")
    if any(item.get("pins_sha256") != expected_pins for item in records):
        errors.append("Phase 4 private evidence: execution pin binding differs")

    by_kind = {str(item.get("evidence_kind")): item for item in records}
    run_a = by_kind.get("reproducibility-run-a")
    run_b = by_kind.get("reproducibility-run-b")
    if run_a is not None and run_b is not None:
        for field in (
            "case_id",
            "public_record_sha256",
            "public_result_set_sha256",
            "subject_sha256",
            "source_input_sha256",
            "declaration_sha256",
            "pins_sha256",
            "environment_sha256",
        ):
            if run_a.get(field) != run_b.get(field):
                errors.append("Phase 4 private evidence: reproducibility runs are not paired")
                break
        if run_a.get("id") == run_b.get("id"):
            errors.append("Phase 4 private evidence: reproducibility executions are not distinct")

    compiler_environments: set[object] = set()
    for family in ("clang", "gcc", "msvc"):
        compiler_execution = by_kind.get(f"compiler-{family}")
        if compiler_execution is not None:
            compiler_environments.add(compiler_execution.get("environment_sha256"))
    if len(compiler_environments) != 3:
        errors.append("Phase 4 private evidence: compiler environments are not distinct")

    all_paths: set[str] = set()
    for execution in records:
        errors.extend(
            _execution_errors(
                private_document,
                public_document,
                execution,
                bundle_root,
                harness_pins,
                require_tracked_harnesses=require_tracked_harnesses,
                all_paths=all_paths,
            )
        )
    return sorted(set(errors))


def _validate_trusted_documents(
    private_document: object,
    public_document: object,
    private_schema: object,
    bundle_root: Path,
    harness_pins: Mapping[str, PinnedHarness] = _TRUSTED_HARNESS_PINS,
) -> list[str]:
    return _validate_documents(
        private_document,
        public_document,
        private_schema,
        bundle_root,
        harness_pins,
        require_tracked_harnesses=True,
    )


def validate_documents(
    private_document: object,
    public_document: object,
    private_schema: object,
    bundle_root: Path,
) -> list[str]:
    """Trusted in-memory validation; production harness selection is not injectable."""
    return _validate_trusted_documents(
        private_document,
        public_document,
        private_schema,
        bundle_root,
    )


def _validate_documents_for_tests(
    private_document: object,
    public_document: object,
    private_schema: object,
    bundle_root: Path,
    harness_pins: Mapping[str, PinnedHarness],
) -> list[str]:
    """Unit-test seam; trusted file validation never calls this function."""
    return _validate_documents(
        private_document,
        public_document,
        private_schema,
        bundle_root,
        harness_pins,
        require_tracked_harnesses=False,
    )


def validate_private_file(private_path: Path, public_document: object) -> list[str]:
    """Validate an ignored bundle using only repository-owned production pins."""
    try:
        lexical = Path(os.path.abspath(private_path))
        private_file = _checked_absolute(lexical, within=lexical.parent)
        privacy = _private_path_is_allowed(private_file)
        if privacy is None:
            return ["completion: private evidence privacy could not be verified"]
        if not privacy:
            return ["completion: private evidence body must be external or ignored"]
        private_bytes = _read_regular_bounded(
            private_file, max_bytes=MAX_PRIVATE_BUNDLE_BYTES
        )
        schema_bytes = _read_regular_bounded(
            PRIVATE_SCHEMA,
            max_bytes=MAX_SCHEMA_BYTES,
            within=ROOT,
        )
        private_document = _json_loads(private_bytes)
        private_schema = _json_loads(schema_bytes)
    except (EvidenceError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return ["completion: private evidence body could not be read"]

    errors: list[str] = []
    is_projection = (
        isinstance(public_document, dict)
        and public_document.get("kind") == G3_PRODUCT_PROJECTION_KIND
    )
    if is_projection:
        errors.extend(g3_product_projection_errors(public_document))
        recorded_digest = (
            public_document.get("private_evidence_sha256")
            if isinstance(public_document, dict)
            else None
        )
    else:
        attestation = (
            public_document.get("attestation")
            if isinstance(public_document, dict)
            else None
        )
        recorded_digest = (
            attestation.get("private_evidence_sha256")
            if isinstance(attestation, dict)
            else None
        )
    if recorded_digest != _sha256(private_bytes):
        errors.append("completion: private evidence digest does not match the local body")
    errors.extend(
        validate_documents(
            private_document,
            public_document,
            private_schema,
            private_file.parent,
        )
    )
    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-evidence", required=True, type=Path)
    parser.add_argument("--public-manifest", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        public_bytes = _read_regular_bounded(
            arguments.public_manifest,
            max_bytes=MAX_PRIVATE_BUNDLE_BYTES,
        )
        public_document = _json_loads(public_bytes)
    except (EvidenceError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        print("Phase 4 private evidence validation failed: input could not be read", file=sys.stderr)
        return 1
    errors = validate_private_file(arguments.private_evidence, public_document)
    if errors:
        print("Phase 4 private evidence validation failed: " + "; ".join(errors), file=sys.stderr)
        return 1
    print("Phase 4 private evidence validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
