#!/usr/bin/env python3
"""Validate public-safe Phase 4 evidence and trusted completion claims."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

if __package__:
    from .public_safe import validate_canonical_json_numbers, validate_public_safe
    from .validate_g2_private_evidence import validate_private_file as validate_g2_private_file
    from .validate_g2_private_evidence import (
        EvidenceError,
        _read_regular_bounded,
        validate_cpu_g3_binding,
    )
    from .validate_phase4_private_evidence import (
        G3_PRODUCT_CORE_FIELDS,
        validate_private_file as validate_phase4_private_file,
    )
else:
    from public_safe import validate_canonical_json_numbers, validate_public_safe
    from validate_g2_private_evidence import validate_private_file as validate_g2_private_file
    from validate_g2_private_evidence import (
        EvidenceError,
        _read_regular_bounded,
        validate_cpu_g3_binding,
    )
    from validate_phase4_private_evidence import (
        G3_PRODUCT_CORE_FIELDS,
        validate_private_file as validate_phase4_private_file,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "examples" / "phase4-generated-manifest.example.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "phase4-generated-manifest.schema.json"
DEFAULT_G2_SCHEMA = ROOT / "schemas" / "g2-completion-evidence.schema.json"
ARCHITECTURE_DECISION = ROOT / "docs" / "adr" / "0003-phase4-dependency-architecture.md"
SIGNING_POLICY = ROOT / "config" / "phase4-completion-signing.json"
EXPECTED_KEY_ID = "jfg-phase4-completion-v1"
EXPECTED_SIGNATURE_NAMESPACE = "jfg-phase4-completion-v1"
EXPECTED_SIGNER_PRINCIPAL = "jfg-phase4-completion-v1"
SSH_KEYGEN_TIMEOUT_SECONDS = 15
MAX_SSH_KEYGEN_BYTES = 16 * 1024 * 1024
MAX_PRIVATE_BINDING_BYTES = 8 * 1024 * 1024
EXPECTED_STATIC_DIRECT_CALL_CANDIDATE_COUNT = 14038
EXPECTED_STATIC_LINKED_CALL_COUNT = 13949
EXPECTED_STATIC_DIRECT_TAIL_COUNT = 89
EXPECTED_STATIC_JAL_CALL_CANDIDATE_COUNT = 13948
EXPECTED_STATIC_BGEZAL_CALL_CANDIDATE_COUNT = 1
EXPECTED_STATIC_J_CALL_CANDIDATE_COUNT = 76
EXPECTED_STATIC_CONDITIONAL_BRANCH_CALL_CANDIDATE_COUNT = 13
EXPECTED_STATIC_INDIRECT_TRANSFER_COUNT = 3620
EXPECTED_NATIVE_RETURN_TRANSFER_COUNT = 3415
EXPECTED_DECISION_RANGE_TRANSFER_COUNT = 205
EXPECTED_EXECUTABLE_SYMBOL_COUNT = 3729
EXPECTED_GENERATED_BODY_COUNT = 2905
EXPECTED_COVERED_ALIAS_COUNT = 824
EXPECTED_EXECUTABLE_SECTION_COUNT = 156
EXPECTED_OVERLAY_SLOT_COUNT = 157
EXPECTED_POPULATED_OVERLAY_SLOT_COUNT = 155
EXPECTED_EMPTY_OVERLAY_SLOT_COUNT = 2
EXPECTED_R32_RELOCATION_COUNT = 2028


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_nonstandard_constant(_: str) -> object:
    raise ValueError("non-standard JSON number")


def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(
            stream,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonstandard_constant,
        )


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _authentication_record(document: object) -> dict[str, object] | None:
    if not isinstance(document, dict):
        return None
    attestation = document.get("attestation")
    if not isinstance(attestation, dict):
        return None
    authentication = attestation.get("authentication")
    return authentication if isinstance(authentication, dict) else None


def canonical_completion_payload(document: object) -> bytes:
    """Canonical signed payload, excluding only the two derived signature fields."""
    payload = copy.deepcopy(document)
    authentication = _authentication_record(payload)
    if authentication is None or authentication.get("algorithm") != "openssh-ed25519":
        raise ValueError("completion authentication is missing")
    authentication.pop("payload_sha256", None)
    authentication.pop("signature_hex_chunks", None)
    return _canonical_bytes(payload)


def _schema_errors(document: object, schema: object) -> list[str]:
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        if any(validator.iter_errors(document)):
            return ["schema: contract violation"]
    except (SchemaError, TypeError, ValueError):
        return ["schema: invalid validation contract"]
    return []


def _public_safety_errors(document: object) -> list[str]:
    errors: list[str] = []
    if validate_public_safe(document):
        errors.append("privacy: public-safe contract violation")
    if validate_canonical_json_numbers(document):
        errors.append("numbers: canonical integer contract violation")
    return errors


def _count_sum(value: object) -> int | None:
    if not isinstance(value, dict):
        return None
    counts = list(value.values())
    if not all(type(item) is int for item in counts):
        return None
    return sum(counts)


def _validate_closure(
    record: object,
    label: str,
    approved_field: str,
    category_field: str | None = None,
) -> list[str]:
    if not isinstance(record, dict):
        return []
    errors: list[str] = []
    expected = record.get("expected_count")
    resolved = record.get("resolved_count")
    approved = record.get(approved_field)
    if all(type(item) is int for item in (expected, resolved, approved)):
        if resolved + approved != expected:
            errors.append(f"{label}: resolved and approved counts do not reconcile")
    if category_field is not None:
        categories = _count_sum(record.get(category_field))
        if type(approved) is int and categories is not None and categories != approved:
            errors.append(f"{label}: approved exception categories do not reconcile")
    return errors


def _is_repeated_placeholder(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and len(set(value)) == 1
    )


def _validate_completion_identities_are_not_placeholders(
    document: object,
) -> list[str]:
    """Reject obvious placeholder commits and digests throughout trusted evidence."""

    def contains_placeholder(value: object) -> bool:
        if isinstance(value, dict):
            for key, child in value.items():
                if (
                    key.endswith("_sha1")
                    or key.endswith("_sha256")
                    or key in {"jfg_decomp_commit", "n64recomp_commit"}
                ) and (
                    _is_repeated_placeholder(child, 40)
                    or _is_repeated_placeholder(child, 64)
                ):
                    return True
                if contains_placeholder(child):
                    return True
        elif isinstance(value, list):
            return any(contains_placeholder(child) for child in value)
        return False

    if contains_placeholder(document):
        return ["completion: placeholder cryptographic identity is forbidden"]
    return []


def _validate_manifest_structure(
    document: object,
    schema: object,
    *,
    allow_completion: bool,
) -> list[str]:
    errors = _public_safety_errors(document)
    schema_errors = _schema_errors(document, schema)
    errors.extend(schema_errors)
    if schema_errors or not isinstance(document, dict):
        return sorted(set(errors))

    symbols = document.get("symbols")
    if isinstance(symbols, dict):
        expected = symbols.get("expected_count")
        generated = symbols.get("generated_count")
        replaceable = symbols.get("replaceable_function_count")
        excluded = symbols.get("excluded_count")
        if (
            expected != EXPECTED_EXECUTABLE_SYMBOL_COUNT
            or generated != EXPECTED_GENERATED_BODY_COUNT
            or excluded != EXPECTED_COVERED_ALIAS_COUNT
        ):
            errors.append(
                "symbols: exact executable/generated/covered-alias denominators are required"
            )
        if all(type(item) is int for item in (expected, generated, excluded)):
            if generated + excluded != expected:
                errors.append("symbols: generated and excluded counts do not reconcile")
        if type(replaceable) is int and type(generated) is int and replaceable != generated:
            errors.append("symbols: replaceable count does not cover every generated body")
        categories = _count_sum(symbols.get("exclusion_category_counts"))
        if type(excluded) is int and categories is not None and categories != excluded:
            errors.append("symbols: exclusion categories do not reconcile")
        exclusion_categories = symbols.get("exclusion_category_counts")
        if isinstance(exclusion_categories, dict) and exclusion_categories != {
            "covered-alias": EXPECTED_COVERED_ALIAS_COUNT,
            "validated-non-code": 0,
            "runtime-abi": 0,
        }:
            errors.append("symbols: covered aliases are the only approved exclusions")

    calls = document.get("calls")
    if isinstance(calls, dict):
        errors.extend(
            _validate_closure(
                calls.get("direct"),
                "direct calls",
                "approved_exception_count",
                "approved_exception_category_counts",
            )
        )
        direct = calls.get("direct")
        if isinstance(direct, dict):
            candidates = direct.get("candidate_count")
            expected = direct.get("expected_count")
            if (
                candidates != EXPECTED_STATIC_DIRECT_CALL_CANDIDATE_COUNT
                or expected != EXPECTED_STATIC_DIRECT_CALL_CANDIDATE_COUNT
                or direct.get("transfer_role_counts")
                != {
                    "linked-call": EXPECTED_STATIC_LINKED_CALL_COUNT,
                    "direct-tail": EXPECTED_STATIC_DIRECT_TAIL_COUNT,
                }
                or direct.get("instruction_class_counts")
                != {
                    "jal": EXPECTED_STATIC_JAL_CALL_CANDIDATE_COUNT,
                    "bgezal": EXPECTED_STATIC_BGEZAL_CALL_CANDIDATE_COUNT,
                    "j": EXPECTED_STATIC_J_CALL_CANDIDATE_COUNT,
                    "conditional-branch": EXPECTED_STATIC_CONDITIONAL_BRANCH_CALL_CANDIDATE_COUNT,
                }
            ):
                errors.append(
                    "direct calls: exact physical transfer denominator and partitions are required"
                )
            if type(candidates) is int and type(expected) is int and expected > candidates:
                errors.append("direct calls: classified calls exceed physical candidates")
        errors.extend(
            _validate_closure(
                calls.get("indirect_ranges"),
                "indirect ranges",
                "approved_exception_count",
                "approved_exception_category_counts",
            )
        )
        indirect = calls.get("indirect_ranges")
        if isinstance(indirect, dict):
            expected = indirect.get("expected_count")
            resolved = indirect.get("resolved_count")
            native_returns = indirect.get("native_return_count")
            decision_ranges = indirect.get("decision_range_count")
            if (
                expected != EXPECTED_STATIC_INDIRECT_TRANSFER_COUNT
                or resolved != EXPECTED_STATIC_INDIRECT_TRANSFER_COUNT
                or native_returns != EXPECTED_NATIVE_RETURN_TRANSFER_COUNT
                or decision_ranges != EXPECTED_DECISION_RANGE_TRANSFER_COUNT
            ):
                errors.append(
                    "indirect ranges: exact static transfer denominator is required"
                )
            if (
                type(native_returns) is int
                and type(decision_ranges) is int
                and type(expected) is int
                and native_returns + decision_ranges != expected
            ):
                errors.append(
                    "indirect ranges: native returns and decision ranges do not reconcile"
                )

    relocations = document.get("relocations")
    if isinstance(relocations, dict):
        instructions = relocations.get("instructions")
        data_r32 = relocations.get("data_r32")
        errors.extend(
            _validate_closure(
                instructions, "instruction relocations", "approved_fail_closed_count"
            )
        )
        errors.extend(
            _validate_closure(data_r32, "data relocations", "approved_fail_closed_count")
        )
        if isinstance(instructions, dict) and instructions.get(
            "hi_lo_pair_count"
        ) != instructions.get("atomic_hi_lo_pair_count"):
            errors.append("instruction relocations: HI/LO pairs are not atomic")
        if isinstance(instructions, dict):
            hi_lo_pairs = instructions.get("hi_lo_pair_count")
            instruction_count = instructions.get("expected_count")
            if (
                type(hi_lo_pairs) is int
                and type(instruction_count) is int
                and hi_lo_pairs * 2 > instruction_count
            ):
                errors.append(
                    "instruction relocations: HI/LO pair denominator exceeds relocation sites"
                )
        if isinstance(data_r32, dict) and data_r32.get("approved_fail_closed_count") != 0:
            errors.append("data relocations: every R32 record must resolve through the table")
        if isinstance(data_r32, dict) and (
            data_r32.get("expected_count") != EXPECTED_R32_RELOCATION_COUNT
            or data_r32.get("resolved_count") != EXPECTED_R32_RELOCATION_COUNT
        ):
            errors.append("data relocations: exact R32 denominator is required")

    overlays = document.get("overlays")
    if isinstance(overlays, dict):
        executable_sections = overlays.get("executable_section_count")
        populated_slots = overlays.get("populated_slot_count")
        if (
            executable_sections != EXPECTED_EXECUTABLE_SECTION_COUNT
            or overlays.get("expected_slot_count") != EXPECTED_OVERLAY_SLOT_COUNT
            or populated_slots != EXPECTED_POPULATED_OVERLAY_SLOT_COUNT
            or overlays.get("empty_slot_count") != EXPECTED_EMPTY_OVERLAY_SLOT_COUNT
        ):
            errors.append("overlays: exact section and slot denominators are required")
        if (
            type(executable_sections) is int
            and type(populated_slots) is int
            and executable_sections != populated_slots + 1
        ):
            errors.append(
                "overlays: executable sections do not reconcile with main plus populated slots"
            )
        expected = overlays.get("expected_slot_count")
        populated = overlays.get("populated_slot_count")
        empty = overlays.get("empty_slot_count")
        if all(type(item) is int for item in (expected, populated, empty)):
            if populated + empty != expected:
                errors.append("overlays: populated and empty slots do not reconcile")
        for field, label in (
            ("listed_slot_count", "listed slots"),
            ("lookup_table_slot_count", "lookup tables"),
            ("lifecycle_table_slot_count", "lifecycle tables"),
        ):
            if type(expected) is int and overlays.get(field) != expected:
                errors.append(f"overlays: {label} do not cover every slot")
        if overlays.get("generated_populated_module_count") != populated:
            errors.append("overlays: generated modules do not cover populated slots")
        if overlays.get("resolved_relocation_entry_count") != overlays.get(
            "relocation_table_entry_count"
        ):
            errors.append("overlays: relocation table entries do not reconcile")

    compilers = document.get("compilers")
    if isinstance(compilers, list):
        compiler_ids: list[str] = []
        families: set[str] = set()
        source_inventories: set[str] = set()
        for item in compilers:
            if not isinstance(item, dict):
                continue
            compiler_id = item.get("compiler_id")
            family = item.get("family")
            target = item.get("target_id")
            source_inventory = item.get("source_inventory_sha256")
            if isinstance(compiler_id, str):
                compiler_ids.append(compiler_id)
            if isinstance(family, str):
                families.add(family)
            if isinstance(source_inventory, str):
                source_inventories.add(source_inventory)
            if isinstance(compiler_id, str) and isinstance(family, str):
                if not compiler_id.startswith(f"{family}-"):
                    errors.append("compilers: compiler ID and family differ")
            if family == "gcc" and target != "linux-x64":
                errors.append("compilers: GCC result must target Linux x64")
            if family == "msvc" and target != "windows-x64":
                errors.append("compilers: MSVC result must target Windows x64")
            if family == "clang" and target not in {"linux-x64", "windows-x64"}:
                errors.append("compilers: Clang result has an unsupported target")
        if len(compiler_ids) != len(set(compiler_ids)):
            errors.append("compilers: compiler IDs must be unique")
        if families != {"clang", "gcc", "msvc"}:
            errors.append("compilers: exact Clang, GCC, and MSVC results are required")
        if len(source_inventories) != 1:
            errors.append("compilers: results do not use one generated source inventory")

    analysis = document.get("analysis")
    if isinstance(analysis, dict):
        analysis_source = analysis.get("source_inventory_sha256")
        sanitizers = analysis.get("sanitizers")
        sanitizer_ids: set[str] = set()
        sanitizer_keys: set[tuple[str, str, str]] = set()
        if isinstance(sanitizers, list):
            for item in sanitizers:
                if not isinstance(item, dict):
                    continue
                sanitizer_id = item.get("sanitizer_id")
                family = item.get("compiler_family")
                target = item.get("target_id")
                if all(isinstance(value, str) for value in (sanitizer_id, family, target)):
                    assert isinstance(sanitizer_id, str)
                    assert isinstance(family, str)
                    assert isinstance(target, str)
                    sanitizer_ids.add(sanitizer_id)
                    sanitizer_keys.add((sanitizer_id, family, target))
                if item.get("source_inventory_sha256") != analysis_source:
                    errors.append("analysis: sanitizer source inventory is unbound")
            if len(sanitizer_keys) != len(sanitizers):
                errors.append("analysis: sanitizer results must be unique")
        if sanitizer_ids != {"address", "undefined-behavior"}:
            errors.append("analysis: address and undefined-behavior sanitizers are required")
        pins = document.get("pins")
        if isinstance(pins, dict) and analysis_source != pins.get(
            "minimal_runtime_source_sha256"
        ):
            errors.append("analysis: handwritten source inventory is unbound")

    libraries = document.get("libraries")
    if isinstance(libraries, dict) and isinstance(symbols, dict):
        baseline = libraries.get("baseline")
        patch = libraries.get("patch")
        aliases = libraries.get("aliases")
        strict_patch = libraries.get("strict_patch_mode")
        minimal_runtime = libraries.get("minimal_runtime")
        if isinstance(baseline, dict):
            body_members = baseline.get("unmodified_body_member_count")
            wrapper_members = baseline.get("callable_wrapper_member_count")
            support_members = baseline.get("support_member_count")
            member_count = baseline.get("member_count")
            if all(
                type(item) is int
                for item in (body_members, wrapper_members, support_members, member_count)
            ) and body_members + wrapper_members + support_members != member_count:
                errors.append("libraries: baseline member counts do not reconcile")
            support_parts = (
                baseline.get("alternate_entry_thunk_member_count"),
                baseline.get("section_address_member_count"),
                baseline.get("lookup_table_member_count"),
                baseline.get("lifecycle_table_member_count"),
                baseline.get("relocation_table_member_count"),
                baseline.get("other_support_member_count"),
            )
            if all(type(item) is int for item in support_parts) and sum(
                support_parts
            ) != support_members:
                errors.append("libraries: baseline support members do not reconcile")
            if body_members != symbols.get("generated_count"):
                errors.append("libraries: baseline does not contain every generated body")
            if wrapper_members != symbols.get("replaceable_function_count"):
                errors.append("libraries: callable wrappers do not cover replaceable bodies")
            if baseline.get("alternate_entry_thunk_member_count") != symbols.get(
                "alternate_entry_thunk_count"
            ):
                errors.append("libraries: alternate-entry thunk denominator is unbound")
            if isinstance(overlays, dict):
                for baseline_field, overlay_field, label in (
                    ("lookup_table_member_count", "lookup_table_member_count", "lookup"),
                    (
                        "lifecycle_table_member_count",
                        "lifecycle_table_member_count",
                        "lifecycle",
                    ),
                    (
                        "relocation_table_member_count",
                        "relocation_table_member_count",
                        "relocation",
                    ),
                ):
                    if baseline.get(baseline_field) != overlays.get(overlay_field):
                        errors.append(
                            f"libraries: {label} table support denominator is unbound"
                        )
        if isinstance(patch, dict):
            replacement_members = patch.get("approved_replacement_member_count")
            wrapper_members = patch.get("callable_wrapper_member_count")
            support_members = patch.get("support_member_count")
            member_count = patch.get("member_count")
            if all(
                type(item) is int
                for item in (
                    replacement_members,
                    wrapper_members,
                    support_members,
                    member_count,
                )
            ) and replacement_members + wrapper_members + support_members != member_count:
                errors.append("libraries: patch member counts do not reconcile")
            support_parts = (
                patch.get("anchor_member_count"),
                patch.get("other_support_member_count"),
            )
            if all(type(item) is int for item in support_parts) and sum(
                support_parts
            ) != support_members:
                errors.append("libraries: patch support members do not reconcile")
        if isinstance(aliases, dict):
            replaceable = symbols.get("replaceable_function_count")
            if aliases.get("expected_count") != replaceable or aliases.get(
                "emitted_count"
            ) != replaceable:
                errors.append("libraries: callable aliases do not cover replaceable bodies")
        if isinstance(patch, dict) and isinstance(strict_patch, dict):
            if patch.get("approved_replacement_member_count") != strict_patch.get(
                "approved_patch_function_count"
            ):
                errors.append("libraries: patch members differ from the approved patch set")
        if isinstance(minimal_runtime, dict):
            runtime_exclusions = None
            categories = symbols.get("exclusion_category_counts")
            if isinstance(categories, dict):
                runtime_exclusions = categories.get("runtime-abi")
            if minimal_runtime.get(
                "target_runtime_abi_exclusion_count"
            ) != runtime_exclusions:
                errors.append("libraries: target runtime ABI exclusions are unbound")
            if isinstance(overlays, dict) and minimal_runtime.get(
                "section_address_count"
            ) != overlays.get("executable_section_count"):
                errors.append("libraries: executable section denominator is unbound")
            if minimal_runtime.get(
                "resolved_host_function_export_count"
            ) != minimal_runtime.get("required_host_function_export_count"):
                errors.append("libraries: host runtime function exports do not reconcile")
            if minimal_runtime.get(
                "resolved_host_data_export_count"
            ) != minimal_runtime.get("required_host_data_export_count"):
                errors.append("libraries: host runtime data exports do not reconcile")
            if minimal_runtime.get(
                "initialized_section_address_count"
            ) != minimal_runtime.get("section_address_count"):
                errors.append("libraries: section-address initialization is incomplete")
            section_count = minimal_runtime.get("section_address_count")
            section_capacity = minimal_runtime.get("section_address_capacity")
            if (
                type(section_count) is int
                and type(section_capacity) is int
                and section_count > section_capacity
            ):
                errors.append("libraries: section-address capacity is insufficient")
            if isinstance(baseline, dict) and baseline.get(
                "section_address_member_count"
            ) != minimal_runtime.get("section_address_support_member_count"):
                errors.append("libraries: section-address support members are unbound")
            if isinstance(analysis, dict) and minimal_runtime.get(
                "handwritten_bridge_unit_count"
            ) != analysis.get("handwritten_bridge_unit_count"):
                errors.append("libraries: handwritten bridge unit counts differ")
            if isinstance(overlays, dict) and minimal_runtime.get(
                "relocation_table_entry_count"
            ) != overlays.get("relocation_table_entry_count"):
                errors.append("libraries: runtime relocation table is unbound")

    if isinstance(overlays, dict) and isinstance(relocations, dict):
        data_r32 = relocations.get("data_r32")
        if isinstance(data_r32, dict):
            if overlays.get("relocation_table_entry_count") != data_r32.get(
                "expected_count"
            ):
                errors.append("overlays: R32 relocation denominator is unbound")
            if overlays.get("resolved_relocation_entry_count") != data_r32.get(
                "resolved_count"
            ):
                errors.append("overlays: resolved R32 relocations are unbound")

    reproducibility = document.get("reproducibility")
    if isinstance(reproducibility, dict):
        if isinstance(symbols, dict) and reproducibility.get(
            "generated_inventory_sha256"
        ) != symbols.get("inventory_sha256"):
            errors.append("reproducibility: generated inventory digest is unbound")
        if isinstance(overlays, dict):
            for repro_field, overlay_field, label in (
                ("overlay_table_sha256", "lookup_table_sha256", "overlay-table"),
                ("lifecycle_table_sha256", "lifecycle_table_sha256", "lifecycle-table"),
                ("relocation_table_sha256", "relocation_table_sha256", "relocation-table"),
            ):
                if reproducibility.get(repro_field) != overlays.get(overlay_field):
                    errors.append(f"reproducibility: {label} digest is unbound")
        if isinstance(compilers, list) and any(
            isinstance(item, dict)
            and item.get("source_inventory_sha256")
            != reproducibility.get("source_file_inventory_sha256")
            for item in compilers
        ):
            errors.append("reproducibility: compiler source inventory is unbound")
        if isinstance(libraries, dict):
            baseline = libraries.get("baseline")
            patch = libraries.get("patch")
            if isinstance(baseline, dict) and reproducibility.get(
                "baseline_member_inventory_sha256"
            ) != baseline.get("member_inventory_sha256"):
                errors.append("reproducibility: baseline member inventory is unbound")
            if isinstance(patch, dict) and reproducibility.get(
                "patch_member_inventory_sha256"
            ) != patch.get("member_inventory_sha256"):
                errors.append("reproducibility: patch member inventory is unbound")

    config_diff = document.get("config_diff")
    pins = document.get("pins")
    if isinstance(config_diff, dict):
        expected_categories = config_diff.get("expected_category_counts")
        observed_categories = config_diff.get("observed_category_counts")
        expected_total = _count_sum(expected_categories)
        observed_total = _count_sum(observed_categories)
        expected_declaration_digest = (
            hashlib.sha256(_canonical_bytes(expected_categories)).hexdigest()
            if isinstance(expected_categories, dict)
            else None
        )
        if config_diff.get("predeclared_expectation_sha256") != expected_declaration_digest:
            errors.append("config diff: predeclared expectation digest is unbound")
        if expected_categories != observed_categories:
            errors.append("config diff: observed categories differ from the declaration")
        if expected_total != config_diff.get("expected_change_count"):
            errors.append("config diff: expected categories do not reconcile")
        if observed_total != config_diff.get("observed_change_count"):
            errors.append("config diff: observed categories do not reconcile")
        unexpected_total = _count_sum(config_diff.get("unexpected_category_counts"))
        if unexpected_total != config_diff.get("unexpected_change_count"):
            errors.append("config diff: unexpected categories do not reconcile")
        if isinstance(pins, dict) and config_diff.get("base_config_sha256") != pins.get(
            "config_sha256"
        ):
            errors.append("config diff: base configuration digest is unbound")

    authentication = _authentication_record(document)
    if authentication is not None and authentication.get("algorithm") == "openssh-ed25519":
        try:
            payload_digest = hashlib.sha256(
                canonical_completion_payload(document)
            ).hexdigest()
        except (TypeError, ValueError):
            payload_digest = None
        if payload_digest != authentication.get("payload_sha256"):
            errors.append("attestation: payload digest does not bind the manifest")

    is_completion = document.get("record_class") == "maintainer-attested-public-aggregate"
    if is_completion:
        errors.extend(_validate_completion_identities_are_not_placeholders(document))
        if not allow_completion:
            errors.append("completion requires trusted signature and G2 evidence validation")

    return sorted(set(errors))


def validate_phase4_public_core(core: object) -> list[str]:
    """Validate the exact G3 product core with repository-owned contracts.

    The pre-G2 projection has no completion envelope of its own.  Wrap only
    its eleven product fields in a fixed, non-claiming envelope so the same
    pinned schema and semantic reconciliation rules used for final Phase 4
    validation also protect private-evidence preparation and G2 consumption.
    """
    if not isinstance(core, dict) or set(core) != set(G3_PRODUCT_CORE_FIELDS):
        return ["public core: exact G3 product fields are required"]
    try:
        pinned_schema = load_json(DEFAULT_SCHEMA)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return ["public core: pinned validation contract is unavailable"]
    try:
        document = {
            "$schema": "../schemas/phase4-generated-manifest.schema.json",
            "schema_version": 2,
            "kind": "jfg-phase4-generated-manifest",
            "privacy": "public-safe-aggregate-only",
            "record_class": "synthetic-example",
            **copy.deepcopy(core),
            "attestation": {
                "evidence_class": "synthetic-fixture",
                "body_policy": "local-only-not-exported",
                "authentication": {"algorithm": "none"},
            },
            "gate": {
                "id": "G3-M1",
                "scope": "whole-program",
                "claim": "not-evidence",
                "predecessor_g2_complete": False,
                "g3_complete": False,
                "all_required_checks_passed": False,
            },
        }
        return _validate_manifest_structure(
            document, pinned_schema, allow_completion=False
        )
    except (ValueError, TypeError, OverflowError, RecursionError):
        return ["public core: validation failed closed"]


def validate_manifest_document(document: object, schema: object) -> list[str]:
    """Validate non-claiming manifests; completion claims fail closed here."""
    return _validate_manifest_structure(document, schema, allow_completion=False)


def validate_g2_evidence_document(document: object, schema: object) -> list[str]:
    errors = _public_safety_errors(document)
    schema_errors = _schema_errors(document, schema)
    errors.extend(schema_errors)
    if schema_errors or not isinstance(document, dict):
        return sorted(set(errors))
    requirements = document.get("requirements")
    expected_digest = (
        hashlib.sha256(_canonical_bytes(requirements)).hexdigest()
        if isinstance(requirements, dict)
        else None
    )
    if document.get("evidence_set_sha256") != expected_digest:
        errors.append("G2 evidence: requirement-set digest is unbound")
    try:
        decision_path = ARCHITECTURE_DECISION.resolve(strict=True)
        if (
            decision_path.is_symlink()
            or not decision_path.is_file()
            or decision_path.parent != ARCHITECTURE_DECISION.parent.resolve(strict=True)
        ):
            raise OSError
        decision_digest = hashlib.sha256(decision_path.read_bytes()).hexdigest()
    except OSError:
        decision_digest = None
        errors.append("G2 evidence: architecture decision is unavailable")
    pins = document.get("pins")
    recorded_decision_digest = (
        pins.get("architecture_decision_sha256") if isinstance(pins, dict) else None
    )
    if recorded_decision_digest != decision_digest:
        errors.append("G2 evidence: architecture decision digest is unbound")
    if _is_repeated_placeholder(document.get("evidence_set_sha256"), 64):
        errors.append("G2 evidence: placeholder digest is forbidden")
    errors.extend(_validate_completion_identities_are_not_placeholders(document))
    return sorted(set(errors))


def _load_signing_policy() -> tuple[dict[str, object] | None, list[str]]:
    try:
        policy = load_json(SIGNING_POLICY)
    except (OSError, ValueError, json.JSONDecodeError):
        return None, ["attestation: trusted signing policy is unavailable"]
    if not isinstance(policy, dict) or set(policy) != {
        "schema_version",
        "kind",
        "algorithm",
        "key_id",
        "principal",
        "namespace",
        "public_key_file",
    }:
        return None, ["attestation: trusted signing policy is invalid"]
    expected = {
        "schema_version": 1,
        "kind": "jfg-phase4-completion-signing-policy",
        "algorithm": "openssh-ed25519",
        "key_id": EXPECTED_KEY_ID,
        "principal": EXPECTED_SIGNER_PRINCIPAL,
        "namespace": EXPECTED_SIGNATURE_NAMESPACE,
    }
    if any(policy.get(key) != value for key, value in expected.items()):
        return None, ["attestation: trusted signing policy is invalid"]
    return policy, []


def _trusted_public_key(policy: dict[str, object]) -> tuple[str | None, list[str]]:
    relative = policy.get("public_key_file")
    if not isinstance(relative, str):
        return None, ["attestation: trusted public key is unavailable"]
    config_root = SIGNING_POLICY.parent.resolve()
    public_key_path = (config_root / relative).resolve()
    try:
        public_key_path.relative_to(config_root)
        line = public_key_path.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None, ["attestation: trusted public key is unavailable"]
    fields = line.split()
    if (
        len(fields) != 3
        or fields[0] != "ssh-ed25519"
        or fields[2] != EXPECTED_KEY_ID
    ):
        return None, ["attestation: trusted public key is invalid"]
    return f"{fields[0]} {fields[1]}", []


def _signature_bytes(document: object) -> bytes | None:
    authentication = _authentication_record(document)
    if authentication is None:
        return None
    chunks = authentication.get("signature_hex_chunks")
    if not isinstance(chunks, list) or not all(isinstance(item, str) for item in chunks):
        return None
    try:
        return bytes.fromhex("".join(chunks))
    except ValueError:
        return None


def _ssh_keygen() -> Path | None:
    candidates = (
        Path("C:/Windows/System32/OpenSSH/ssh-keygen.exe"),
        Path("/usr/bin/ssh-keygen"),
    )
    for candidate in candidates:
        try:
            metadata = candidate.stat(follow_symlinks=False)
            attributes = getattr(metadata, "st_file_attributes", 0)
            reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            if (
                stat.S_ISREG(metadata.st_mode)
                and not stat.S_ISLNK(metadata.st_mode)
                and not (attributes & reparse)
            ):
                return candidate
        except OSError:
            continue
    return None


def _stage_ssh_keygen(executable: Path, directory: Path) -> tuple[Path, str]:
    try:
        payload = _read_regular_bounded(executable, max_bytes=MAX_SSH_KEYGEN_BYTES)
    except EvidenceError as error:
        raise ValueError("OpenSSH executable could not be verified") from error
    destination = directory / ("ssh-keygen.exe" if os.name == "nt" else "ssh-keygen")
    destination.write_bytes(payload)
    os.chmod(destination, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    digest = hashlib.sha256(payload).hexdigest()
    if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
        raise ValueError("OpenSSH executable copy differs")
    return destination, digest


def _verify_completion_signature(document: object) -> list[str]:
    policy, errors = _load_signing_policy()
    if errors or policy is None:
        return errors
    authentication = _authentication_record(document)
    if authentication is None or any(
        authentication.get(field) != expected
        for field, expected in (
            ("algorithm", "openssh-ed25519"),
            ("key_id", EXPECTED_KEY_ID),
            ("principal", EXPECTED_SIGNER_PRINCIPAL),
            ("namespace", EXPECTED_SIGNATURE_NAMESPACE),
        )
    ):
        return ["attestation: completion signer identity is invalid"]
    public_key, key_errors = _trusted_public_key(policy)
    signature = _signature_bytes(document)
    executable = _ssh_keygen()
    if key_errors or public_key is None:
        return key_errors
    if signature is None:
        return ["attestation: completion signature is invalid"]
    if executable is None:
        return ["attestation: OpenSSH signature verifier is unavailable"]
    try:
        payload = canonical_completion_payload(document)
    except (TypeError, ValueError):
        return ["attestation: completion payload is invalid"]
    tools_root = ROOT / "tools"
    tools_root.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="phase4-verify-", dir=tools_root) as temp:
            temp_root = Path(temp)
            staged_executable, executable_digest = _stage_ssh_keygen(executable, temp_root)
            allowed_signers = temp_root / "allowed_signers"
            signature_file = temp_root / "completion.sig"
            allowed_signers.write_text(
                f"{EXPECTED_SIGNER_PRINCIPAL} {public_key}\n", encoding="utf-8"
            )
            signature_file.write_bytes(signature)
            result = subprocess.run(
                [
                    str(staged_executable),
                    "-Y",
                    "verify",
                    "-f",
                    str(allowed_signers),
                    "-I",
                    EXPECTED_SIGNER_PRINCIPAL,
                    "-n",
                    EXPECTED_SIGNATURE_NAMESPACE,
                    "-s",
                    str(signature_file),
                ],
                input=payload,
                capture_output=True,
                check=False,
                timeout=SSH_KEYGEN_TIMEOUT_SECONDS,
            )
            if hashlib.sha256(staged_executable.read_bytes()).hexdigest() != executable_digest:
                return ["attestation: OpenSSH signature verifier changed during execution"]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return ["attestation: completion signature could not be verified"]
    if result.returncode != 0:
        return ["attestation: completion signature is invalid"]
    return []


def sign_completion_manifest(document: object, private_key_path: Path) -> object:
    """Sign a completion claim with the ignored local project key."""
    tools_root = (ROOT / "tools").resolve()
    resolved_private_key = private_key_path.resolve()
    try:
        resolved_private_key.relative_to(tools_root)
    except ValueError as error:
        raise ValueError("completion private key must remain under ignored tools") from error
    if not resolved_private_key.is_file() or resolved_private_key.is_symlink():
        raise ValueError("completion private key is unavailable")
    executable = _ssh_keygen()
    if executable is None:
        raise ValueError("OpenSSH signer is unavailable")
    policy, policy_errors = _load_signing_policy()
    if policy_errors or policy is None:
        raise ValueError("completion signing policy is unavailable")
    signed = copy.deepcopy(document)
    payload = canonical_completion_payload(signed)
    tools_root.mkdir(exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="phase4-sign-", dir=tools_root) as temp:
            temp_root = Path(temp)
            staged_executable, executable_digest = _stage_ssh_keygen(executable, temp_root)
            payload_path = temp_root / "completion.payload"
            payload_path.write_bytes(payload)
            result = subprocess.run(
                [
                    str(staged_executable),
                    "-Y",
                    "sign",
                    "-f",
                    str(resolved_private_key),
                    "-n",
                    EXPECTED_SIGNATURE_NAMESPACE,
                    str(payload_path),
                ],
                capture_output=True,
                check=False,
                timeout=SSH_KEYGEN_TIMEOUT_SECONDS,
            )
            signature_path = payload_path.with_suffix(payload_path.suffix + ".sig")
            if result.returncode != 0 or not signature_path.is_file():
                raise ValueError("completion signing failed")
            signature = signature_path.read_bytes()
            if hashlib.sha256(staged_executable.read_bytes()).hexdigest() != executable_digest:
                raise ValueError("OpenSSH signer changed during execution")
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("completion signing failed") from error
    authentication = _authentication_record(signed)
    if authentication is None:
        raise ValueError("completion authentication is missing")
    authentication["payload_sha256"] = hashlib.sha256(payload).hexdigest()
    encoded = signature.hex()
    authentication["signature_hex_chunks"] = [
        encoded[index : index + 64] for index in range(0, len(encoded), 64)
    ]
    return signed


def validate_trusted_completion(
    document: object,
    schema: object,
    g2_document: object | None,
    g2_schema: object,
    *,
    private_evidence_path: Path | None = None,
    g2_private_evidence_path: Path | None = None,
) -> list[str]:
    """Validate a completion using only repository-pinned trust contracts."""
    try:
        pinned_schema = load_json(DEFAULT_SCHEMA)
        pinned_g2_schema = load_json(DEFAULT_G2_SCHEMA)
    except (OSError, ValueError, json.JSONDecodeError):
        return ["completion: pinned validation contracts are unavailable"]

    errors: list[str] = []
    try:
        if _canonical_bytes(schema) != _canonical_bytes(pinned_schema):
            errors.append("completion: Phase 4 schema is not the pinned contract")
    except (TypeError, ValueError, OverflowError, RecursionError):
        errors.append("completion: Phase 4 schema is not the pinned contract")
    try:
        if _canonical_bytes(g2_schema) != _canonical_bytes(pinned_g2_schema):
            errors.append("completion: G2 schema is not the pinned contract")
    except (TypeError, ValueError, OverflowError, RecursionError):
        errors.append("completion: G2 schema is not the pinned contract")

    # Caller-provided contracts are compatibility inputs only. Trusted
    # validation always executes the repository-owned contracts above.
    errors.extend(
        _validate_manifest_structure(document, pinned_schema, allow_completion=True)
    )
    if isinstance(document, dict):
        core = {
            field: copy.deepcopy(document[field])
            for field in G3_PRODUCT_CORE_FIELDS
            if field in document
        }
        errors.extend(validate_phase4_public_core(core))
    else:
        errors.extend(validate_phase4_public_core(document))
    if not isinstance(document, dict) or document.get(
        "record_class"
    ) != "maintainer-attested-public-aggregate":
        errors.append("completion: maintainer aggregate record is required")
        return sorted(set(errors))
    if g2_document is None:
        errors.append("completion: G2 evidence body is required")
    else:
        errors.extend(validate_g2_evidence_document(g2_document, pinned_g2_schema))
        gate = document.get("gate")
        recorded_g2_digest = gate.get("predecessor_g2_evidence_sha256") if isinstance(gate, dict) else None
        try:
            actual_g2_digest = hashlib.sha256(_canonical_bytes(g2_document)).hexdigest()
        except (TypeError, ValueError):
            actual_g2_digest = None
            errors.append("completion: G2 evidence body is not canonical JSON")
        if recorded_g2_digest != actual_g2_digest:
            errors.append("completion: G2 evidence digest does not match the supplied body")
        manifest_pins = document.get("pins")
        g2_pins = g2_document.get("pins") if isinstance(g2_document, dict) else None
        if isinstance(manifest_pins, dict) and isinstance(g2_pins, dict):
            for field in (
                "jfg_decomp_commit",
                "n64recomp_commit",
                "supported_input_id",
                "dependency_lock_sha256",
            ):
                if manifest_pins.get(field) != g2_pins.get(field):
                    errors.append("completion: G2 and Phase 4 pins differ")
                    break
        if g2_private_evidence_path is None:
            errors.append("completion: local G2 executable evidence body is required")
        else:
            errors.extend(validate_g2_private_file(g2_private_evidence_path, g2_document))
    if private_evidence_path is None:
        errors.append("completion: local private evidence body is required")
    else:
        errors.extend(validate_phase4_private_file(private_evidence_path, document))
    if private_evidence_path is not None and g2_private_evidence_path is not None:
        try:
            g2_private_bytes = _read_regular_bounded(
                Path(os.path.abspath(g2_private_evidence_path)),
                max_bytes=MAX_PRIVATE_BINDING_BYTES,
            )
            phase4_private_bytes = _read_regular_bounded(
                Path(os.path.abspath(private_evidence_path)),
                max_bytes=MAX_PRIVATE_BINDING_BYTES,
            )
            g2_private_document = json.loads(
                g2_private_bytes.decode("utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_nonstandard_constant,
            )
            phase4_private_document = json.loads(
                phase4_private_bytes.decode("utf-8"),
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_nonstandard_constant,
            )
        except (
            EvidenceError,
            OSError,
            UnicodeDecodeError,
            ValueError,
            json.JSONDecodeError,
        ):
            errors.append(
                "private evidence: CPU records are not bound to independently executed G3 products"
            )
        else:
            errors.extend(
                validate_cpu_g3_binding(
                    g2_private_document,
                    Path(os.path.abspath(g2_private_evidence_path)).parent,
                    phase4_private_document,
                    document,
                    Path(os.path.abspath(private_evidence_path)).parent,
                )
            )
    errors.extend(_verify_completion_signature(document))
    return sorted(set(errors))


def validate_public_completion(document: object, schema: object) -> list[str]:
    """Validate the tracked signed aggregate without requiring private bodies.

    This is the CI-safe half of trusted validation. It verifies the pinned
    schema, complete public semantics, and maintainer signature. Local trusted
    validation remains stricter and additionally consumes both private bodies.
    """
    try:
        pinned_schema = load_json(DEFAULT_SCHEMA)
    except (OSError, ValueError, json.JSONDecodeError):
        return ["completion: pinned Phase 4 contract is unavailable"]
    errors: list[str] = []
    try:
        if _canonical_bytes(schema) != _canonical_bytes(pinned_schema):
            errors.append("completion: Phase 4 schema is not the pinned contract")
    except (TypeError, ValueError, OverflowError, RecursionError):
        errors.append("completion: Phase 4 schema is not the pinned contract")
    errors.extend(
        _validate_manifest_structure(document, pinned_schema, allow_completion=True)
    )
    if not isinstance(document, dict) or document.get(
        "record_class"
    ) != "maintainer-attested-public-aggregate":
        errors.append("completion: maintainer aggregate record is required")
    else:
        core = {
            field: copy.deepcopy(document[field])
            for field in G3_PRODUCT_CORE_FIELDS
            if field in document
        }
        errors.extend(validate_phase4_public_core(core))
    errors.extend(_verify_completion_signature(document))
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--g2-evidence", type=Path)
    parser.add_argument("--g2-private-evidence", type=Path)
    parser.add_argument("--g2-schema", type=Path, default=DEFAULT_G2_SCHEMA)
    parser.add_argument("--private-evidence", type=Path)
    arguments = parser.parse_args()

    try:
        manifest = load_json(arguments.manifest)
        schema = load_json(arguments.schema)
        g2_schema = load_json(arguments.g2_schema)
        g2_document = load_json(arguments.g2_evidence) if arguments.g2_evidence else None
    except (OSError, ValueError, json.JSONDecodeError):
        print("Phase 4 manifest validation failed: input could not be read", file=sys.stderr)
        return 1

    if isinstance(manifest, dict) and manifest.get(
        "record_class"
    ) == "maintainer-attested-public-aggregate":
        errors = validate_trusted_completion(
            manifest,
            schema,
            g2_document,
            g2_schema,
            private_evidence_path=arguments.private_evidence,
            g2_private_evidence_path=arguments.g2_private_evidence,
        )
    else:
        errors = validate_manifest_document(manifest, schema)

    if errors:
        print("Phase 4 manifest validation failed:", file=sys.stderr)
        for error in sorted(set(errors)):
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Phase 4 non-claiming manifest validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
