#!/usr/bin/env python3
"""Validate the public-safe audio task bridge aggregate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

if __package__:
    from .public_safe import validate_canonical_json_numbers, validate_public_safe
else:
    from public_safe import validate_canonical_json_numbers, validate_public_safe


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config" / "audio-task-bridge.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "audio-task-bridge.schema.json"
EXPECTED_CURRENT_PIN_MANIFEST_SHA256 = (
    "7a9e463dbd629740cd30f07dbef077af60532b193a47292c74fea1bdbe9ab007"
)
EXPECTED_CURRENT_SCHEMA_SHA256 = (
    "0a1adfc6da84e9ffc9cb3c1dba41198b21361810b58f709da2a63225cd6e6bac"
)


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


def canonical_hash(value: object) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def validate_manifest_document(document: object, schema: object) -> list[str]:
    errors: list[str] = []
    try:
        document_hash = canonical_hash(document)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return ["document: non-JSON value"]

    try:
        schema_hash = canonical_hash(schema)
    except (TypeError, ValueError, OverflowError, RecursionError):
        schema_hash = None
        errors.append("schema: invalid validation contract")
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        if any(validator.iter_errors(document)):
            errors.append("schema: contract violation")
    except (SchemaError, TypeError, ValueError, OverflowError, RecursionError):
        errors.append("schema: invalid validation contract")
    if schema_hash != EXPECTED_CURRENT_SCHEMA_SHA256:
        errors.append("schema: reviewed validation contract differs from lock")
    if validate_public_safe(document):
        errors.append("privacy: public-safe contract violation")
    if validate_canonical_json_numbers(document):
        errors.append("numbers: canonical integer contract violation")
    if not isinstance(document, dict):
        return sorted(set(errors))

    upstream = document.get("upstream_contract")
    variants = document.get("variant_surface")
    evidence = document.get("evidence")
    decision = document.get("decision")
    if not isinstance(upstream, dict) or upstream.get(
        "real_second_variant_executed"
    ) is not False:
        errors.append("real second audio variant remains unexecuted")
    if not isinstance(upstream, dict) or upstream.get(
        "generated_secondary_fallback_executed"
    ) is not True:
        errors.append("generated secondary fallback evidence is absent")
    if not isinstance(variants, dict) or (
        variants.get("rsp_adapter_implemented") is not True
        or variants.get("primary_real_execution_passed") is not True
        or variants.get("secondary_real_execution_passed") is not False
        or variants.get(
            "secondary_generated_fail_closed_execution_passed"
        ) is not True
    ):
        errors.append("audio variant aggregate differs from reviewed evidence")
    if isinstance(evidence, dict):
        if evidence.get("real_task_count") != 1:
            errors.append("primary real audio task aggregate differs from review")
        if evidence.get("private_body_present") is not False:
            errors.append("tracked audio bridge evidence cannot contain private bodies")
        if (
            evidence.get("real_referenced_memory_closure")
            != "bounded-broker-contract-established"
            or evidence.get("real_output_validation")
            != "exact-private-oracle-established"
            or evidence.get("private_output_oracle_compared") is not True
            or evidence.get("real_scheduler_completion_order")
            != "validated-output-before-single-signal"
            or evidence.get("real_installed_worker_execution_passed") is not True
            or evidence.get("secondary_search_task_count") != 2984
            or evidence.get("secondary_search_overlay_swap_task_count") != 0
        ):
            errors.append("primary real audio proof aggregate differs from review")
        if (
            evidence.get("secondary_fallback_probe_count") != 1
            or evidence.get("secondary_fallback_brokered_write_count") != 1
            or evidence.get("secondary_fallback_completion_count") != 0
            or evidence.get(
                "secondary_fallback_transactional_rollback"
            ) is not True
        ):
            errors.append("secondary generated fallback aggregate differs from review")
    if not isinstance(decision, dict) or (
        decision.get("status") != "g2-audio-native-path-proven"
        or decision.get("g2_gate") != "pass"
        or decision.get("remaining_blocker_count") != 0
    ):
        errors.append("G2 audio requirement decision differs from reviewed evidence")

    if document_hash != EXPECTED_CURRENT_PIN_MANIFEST_SHA256:
        errors.append("current-pin audio bridge manifest differs from the reviewed lock")
    return sorted(set(errors))


def validate_pins(document: object, dependency_lock: object) -> list[str]:
    if not isinstance(document, dict) or not isinstance(dependency_lock, dict):
        return ["manifest or dependency lock is not an object"]
    repositories = dependency_lock.get("repositories")
    pins = document.get("pins")
    if not isinstance(repositories, list) or not isinstance(pins, dict):
        return ["manifest pins or dependency repositories are missing"]
    locked: dict[str, object] = {}
    duplicate_ids: set[str] = set()
    invalid_record = False
    for item in repositories:
        if not isinstance(item, dict):
            invalid_record = True
            continue
        identifier = item.get("id")
        if not isinstance(identifier, str):
            invalid_record = True
            continue
        if identifier in locked:
            duplicate_ids.add(identifier)
        locked[identifier] = item.get("commit")
    expected = {
        "n64recomp": locked.get("n64recomp"),
        "n64modernruntime": locked.get("n64modernruntime"),
    }
    errors: list[str] = []
    if invalid_record:
        errors.append("dependency lock contains an invalid repository record")
    if duplicate_ids:
        errors.append("dependency lock contains duplicate repository identifiers")
    errors.extend(
        f"pin mismatch for {name}"
        for name, commit in expected.items()
        if pins.get(name) != commit
    )
    return sorted(errors)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    arguments = parser.parse_args()

    try:
        document = load_json(arguments.manifest)
        schema = load_json(arguments.schema)
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        errors = validate_manifest_document(document, schema)
        errors.extend(validate_pins(document, dependency_lock))
    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
    ):
        print(
            "Audio task bridge validation failed: input could not be read",
            file=sys.stderr,
        )
        return 1

    if errors:
        print("Audio task bridge validation failed:", file=sys.stderr)
        for error in sorted(set(errors)):
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Audio task bridge validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
