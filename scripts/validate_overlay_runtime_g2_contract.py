#!/usr/bin/env python3
"""Validate the public-safe overlay/runtime G2 no-go contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Iterable

from jsonschema import Draft202012Validator

if __package__:
    from .overlay_runtime_g2_models import (
        LIFECYCLE_EVENT_KINDS,
        RELOCATION_CLASSES,
        TRAP_DISPOSITIONS,
        TRAP_KINDS,
        TRAP_REACHABILITY,
    )
    from .public_safe import validate_public_safe
else:
    from overlay_runtime_g2_models import (
        LIFECYCLE_EVENT_KINDS,
        RELOCATION_CLASSES,
        TRAP_DISPOSITIONS,
        TRAP_KINDS,
        TRAP_REACHABILITY,
    )
    from public_safe import validate_public_safe


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config" / "overlay-runtime-g2-contract.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "overlay-runtime-g2-contract.schema.json"
EXPECTED_CONTRACT_SHA256 = (
    "b2b9fe7f7bd81d75fafa9ebebbac89a617862c597de8791c2321575291449c4d"
)
EXPECTED_BLOCKERS = (
    "most-complex-real-overlay-lifecycle",
    "generated-lookup-runtime-integration",
    "dynamic-runlink-private-trace",
    "reachable-trap-private-replay",
    "owned-non-stub-trap-mitigations",
)
FORBIDDEN_KEY = re.compile(
    r"(?:^|[-_])(?:rom|path|address|coordinate|symbol|payload|body|bytes|content)(?:$|[-_])",
    re.IGNORECASE,
)
class ContractLoadError(ValueError):
    """Expected strict JSON or canonical-input failure."""


def _reject_constant(_: str) -> object:
    raise ContractLoadError("nonstandard JSON number")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContractLoadError("duplicate JSON member")
        result[key] = value
    return result


def load_json(path: Path) -> object:
    if path.is_symlink() or not path.is_file():
        raise ContractLoadError("input is not a regular non-symlink file")
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
            parse_float=lambda _: (_ for _ in ()).throw(
                ContractLoadError("floating JSON number")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractLoadError("unreadable or invalid JSON") from error


def canonical_hash(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeError) as error:
        raise ContractLoadError("contract is not canonical JSON data") from error
    return hashlib.sha256(payload).hexdigest()


def _validate_json_shape(value: object) -> list[str]:
    errors: list[str] = []
    active: set[int] = set()

    def visit(item: object) -> None:
        if item is None or isinstance(item, (str, bool)):
            return
        if type(item) is int:
            return
        if isinstance(item, (list, dict)):
            identity = id(item)
            if identity in active:
                errors.append("contract contains a cyclic container")
                return
            active.add(identity)
            if isinstance(item, list):
                for child in item:
                    visit(child)
            else:
                for key, child in item.items():
                    if type(key) is not str:
                        errors.append("contract contains a non-string member name")
                    visit(child)
            active.remove(identity)
            return
        errors.append("contract contains a non-JSON value")

    visit(value)
    return errors


def _privacy_errors(value: object) -> list[str]:
    errors = [
        "contract contains private or ROM-derived detail"
        for _ in validate_public_safe(value)
    ]
    active: set[int] = set()

    def visit(item: object) -> None:
        if isinstance(item, (list, dict)):
            identity = id(item)
            if identity in active:
                return
            active.add(identity)
            if isinstance(item, list):
                for child in item:
                    visit(child)
            else:
                for key, child in item.items():
                    if isinstance(key, str) and key != "$schema" and FORBIDDEN_KEY.search(key):
                        errors.append("contract contains a forbidden private-detail field")
                    visit(child)
            active.remove(identity)

    visit(value)
    return errors


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def validate_contract(document: object, schema: object | None = None) -> list[str]:
    errors = _validate_json_shape(document)
    if errors:
        return sorted(set(errors))

    try:
        canonical_schema = load_json(DEFAULT_SCHEMA)
    except ContractLoadError:
        return ["repository-owned contract schema is unavailable"]
    if schema is not None:
        try:
            if canonical_hash(schema) != canonical_hash(canonical_schema):
                errors.append("supplied schema differs from the repository contract")
        except ContractLoadError:
            errors.append("supplied schema is not canonical JSON data")
    schema_to_use = canonical_schema
    try:
        validator = Draft202012Validator(schema_to_use)
        if not isinstance(document, dict) or any(validator.iter_errors(document)):
            errors.append("contract does not satisfy the repository schema")
    except Exception:
        errors.append("contract schema validation failed closed")
    errors.extend(_privacy_errors(document))
    if not isinstance(document, dict):
        return sorted(set(errors))

    overlay = _as_dict(document.get("overlay_lifecycle"))
    scheduler = _as_dict(document.get("scheduler_boundary"))
    traps = _as_dict(document.get("runtime_traps"))
    claims = _as_dict(document.get("claims"))
    gate = _as_dict(document.get("g2"))

    if tuple(overlay.get("required_events", ())) != LIFECYCLE_EVENT_KINDS:
        errors.append("overlay lifecycle event contract differs from the executable model")
    if tuple(overlay.get("relocation_classes", ())) != RELOCATION_CLASSES:
        errors.append("overlay relocation classes differ from the executable model")
    required_overlay_flags = (
        "requires_generated_lookup_integration",
        "requires_bss_clear",
        "requires_full_mapped_extent_validation",
        "requires_callback_reentry_rejection",
        "requires_reload_api_for_prior_lifetime",
        "requires_same_base_reload",
        "requires_semantic_state_match",
        "requires_stale_pointer_rejection",
        "requires_cross_overlay_invalidation",
        "requires_cross_overlay_rebind",
    )
    if any(overlay.get(flag) is not True for flag in required_overlay_flags):
        errors.append("overlay lifecycle requirement was weakened")
    if (
        overlay.get("real_overlay_execution_count") != 0
        or overlay.get("generated_lookup_integration_complete") is not False
        or overlay.get("status") != "synthetic-contract-only"
    ):
        errors.append("overlay contract overstates real or integrated progress")

    if (
        scheduler.get("mode") != "caller-ordered-synchronous"
        or scheduler.get("operation_token_required") is not True
        or scheduler.get("callback_completion") != "before-operation-return"
        or scheduler.get("wall_clock_used") is not False
        or scheduler.get("virtual_time_provided") is not False
        or scheduler.get("thread_scheduler_provided") is not False
        or scheduler.get("phase5_scheduler_claimed") is not False
    ):
        errors.append("scheduler boundary differs from the Phase 4 contract")

    if tuple(traps.get("required_kinds", ())) != TRAP_KINDS:
        errors.append("trap kinds differ from the executable model")
    if tuple(traps.get("allowed_dispositions", ())) != TRAP_DISPOSITIONS:
        errors.append("trap dispositions differ from the executable model")
    if tuple(traps.get("reachability_states", ())) != TRAP_REACHABILITY:
        errors.append("trap reachability states differ from the executable model")
    required_trap_flags = (
        "requires_closed_candidate_denominator",
        "requires_owned_mitigation",
        "requires_bounded_estimate",
        "requires_private_oracle_and_native_trace_for_reachable",
        "requires_private_review_for_unreachable",
        "unknown_or_duplicate_fails_closed",
    )
    if any(traps.get(flag) is not True for flag in required_trap_flags):
        errors.append("runtime trap requirement was weakened")
    if (
        traps.get("real_trace_count") != 0
        or traps.get("private_reachability_complete") is not False
        or traps.get("status") != "synthetic-contract-only"
    ):
        errors.append("trap contract overstates private or real progress")

    if claims != {
        "synthetic_only": True,
        "real_evidence_present": False,
        "phase5_scheduler_implemented": False,
        "g2_complete": False,
        "phase4_completion_authorized": False,
    }:
        errors.append("contract claims differ from the fail-closed no-go baseline")
    if (
        gate.get("id") != "G2"
        or gate.get("decision") != "no-go"
        or tuple(gate.get("blockers", ())) != EXPECTED_BLOCKERS
    ):
        errors.append("G2 decision or blocker set differs from the reviewed contract")

    try:
        if canonical_hash(document) != EXPECTED_CONTRACT_SHA256:
            errors.append("overlay/runtime contract differs from the reviewed lock")
    except ContractLoadError:
        errors.append("contract cannot be canonically hashed")
    return sorted(set(errors))


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        document = load_json(args.contract)
        schema = load_json(args.schema)
        errors = validate_contract(document, schema)
    except Exception:
        print("overlay-runtime-contract: validation failed", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(f"overlay-runtime-contract: {error}", file=sys.stderr)
        return 1
    print("overlay-runtime-contract: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
