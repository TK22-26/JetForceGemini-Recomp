#!/usr/bin/env python3
"""Validate public-safe graphics bridge evidence with private aggregate backing."""

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
DEFAULT_MANIFEST = ROOT / "config" / "graphics-task-bridge.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "graphics-task-bridge.schema.json"
EXPECTED_CURRENT_PIN_MANIFEST_SHA256 = (
    "5a79422f8240c2295f86f076e043e9468a0dde5e4ed278256ab1fcf597be7a73"
)
EXPECTED_CURRENT_SCHEMA_SHA256 = (
    "176f3731cb78df51556bd926a755ac9daabcabc648b24ead01864f36cc85ab58"
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

    bridge = document.get("bridge")
    family = document.get("family_surface")
    evidence = document.get("evidence")
    decision = document.get("decision")
    if isinstance(bridge, dict):
        if bridge.get("native_adapter_path") != "project-bounded-semantic":
            errors.append("G2 graphics path must remain project bounded semantic")
        if (
            bridge.get("bounded_custom_fallback_implemented") is not True
            or bridge.get("command_prefix_verified_through_broker") is not True
            or bridge.get("semantic_output_kind_distinct") is not True
            or bridge.get("semantic_output_payload_comparison") != "exact-bytes"
        ):
            errors.append("bounded semantic fallback proof cannot be weakened")
        if bridge.get("visual_output_produced") is not False:
            errors.append("semantic output cannot be relabeled as rendered pixels")
    if isinstance(family, dict):
        if (
            family.get("custom_handler_translation_implemented") is not True
            or family.get("semantic_renderer_implemented") is not True
        ):
            errors.append("bounded custom translation proof cannot be weakened")
        if (
            family.get("shared_base_visual_renderer_implemented") is not False
            or family.get("real_task_full_surface_coverage") is not False
        ):
            errors.append("visual renderer evidence remains unimplemented")
        if family.get("rt64_adapter_implemented") is not False:
            errors.append("RT64 adapter remains unimplemented")
    if isinstance(evidence, dict):
        if evidence.get("real_task_count") != 1:
            errors.append("reviewed graphics aggregate covers exactly one private task")
        if evidence.get("private_body_present") is not False:
            errors.append("tracked graphics bridge evidence cannot contain private bodies")
        if (
            evidence.get("referenced_memory_closure")
            != "established-for-one-private-task"
            or evidence.get("semantic_output_validation")
            != "exact-match-for-one-private-task"
            or evidence.get("completion_after_oracle") is not True
        ):
            errors.append("reviewed private aggregate differs from the locked evidence")
        if evidence.get("visual_output_validation") != "not-established":
            errors.append("visual output validation remains unestablished")
    if not isinstance(decision, dict) or decision.get("g2_gate") != "pass":
        errors.append("G2 graphics requires the proven bounded native fallback")

    if document_hash != EXPECTED_CURRENT_PIN_MANIFEST_SHA256:
        errors.append(
            "current-pin graphics bridge manifest differs from the reviewed lock"
        )
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
        "rt64": locked.get("rt64"),
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
            "Graphics task bridge validation failed: input could not be read",
            file=sys.stderr,
        )
        return 1

    if errors:
        print("Graphics task bridge validation failed:", file=sys.stderr)
        for error in sorted(set(errors)):
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Graphics task bridge validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
