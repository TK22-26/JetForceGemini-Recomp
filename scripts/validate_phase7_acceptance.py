#!/usr/bin/env python3
"""Validate the Phase 7/M3 contract without exposing private visual data."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

if __package__:
    from .public_safe import validate_canonical_json_numbers, validate_public_safe
else:
    from public_safe import validate_canonical_json_numbers, validate_public_safe


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config" / "phase7-acceptance.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "phase7-acceptance.schema.json"
DEFAULT_COMPLETION = ROOT / "evidence" / "phase7-completion.json"
SCENE_NAMES = ("boot-title", "representative-gameplay")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


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


def dependency_pins(dependency_lock: object) -> tuple[dict[str, object], list[str]]:
    if not isinstance(dependency_lock, dict):
        return {}, ["dependency lock is not an object"]
    repositories = dependency_lock.get("repositories")
    if not isinstance(repositories, list):
        return {}, ["dependency repositories are missing"]
    pins: dict[str, object] = {}
    errors: list[str] = []
    for record in repositories:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            errors.append("dependency lock contains an invalid repository record")
            continue
        identifier = record["id"]
        if identifier in pins:
            errors.append("dependency lock contains duplicate repository identifiers")
        pins[identifier] = record.get("commit")
    return pins, sorted(set(errors))


def validate_contract(
    contract: object,
    schema: object,
    dependency_lock: object,
    *,
    completion_summary_exists: bool,
) -> list[str]:
    errors: list[str] = []
    try:
        Draft202012Validator.check_schema(schema)
        if any(Draft202012Validator(schema).iter_errors(contract)):
            errors.append("schema: contract violation")
    except (SchemaError, TypeError, ValueError, OverflowError, RecursionError):
        errors.append("schema: invalid validation contract")
    if validate_public_safe(contract):
        errors.append("privacy: public-safe contract violation")
    if validate_canonical_json_numbers(contract):
        errors.append("numbers: canonical integer contract violation")
    if not isinstance(contract, dict):
        return sorted(set(errors))

    locked, lock_errors = dependency_pins(dependency_lock)
    errors.extend(lock_errors)
    pins = contract.get("pins")
    if not isinstance(pins, dict):
        errors.append("renderer pins are missing")
    else:
        for identifier in ("rt64", "n64modernruntime"):
            if pins.get(identifier) != locked.get(identifier):
                errors.append(f"pin mismatch for {identifier}")

    scope = contract.get("scope")
    evidence = contract.get("evidence_format")
    gates = contract.get("gates")
    if isinstance(scope, dict):
        if scope.get("required_scenes") != [
            "boot-title",
            "representative-gameplay",
        ]:
            errors.append("both required Phase 7 scenes must remain in scope")
        minimum_tasks = scope.get("minimum_real_task_count")
        if not isinstance(minimum_tasks, int) or minimum_tasks < 2:
            errors.append("Phase 7 requires real tasks from both scenes")
    if isinstance(evidence, dict):
        if evidence.get("private_artifact_policy") != "ignored-local-only":
            errors.append("visual bodies must remain ignored and local")
        if evidence.get("pixel_comparison") != "independent-emulator-oracle":
            errors.append("visual acceptance requires an independent emulator oracle")
        if evidence.get("pixel_comparator") != "scripts/compare_phase7_frames.py":
            errors.append("the pinned Phase 7 pixel comparator is required")
        if evidence.get("ssim_prefilter") != "gaussian-one-reference-pixel":
            errors.append("the structural SSIM prefilter policy is required")
        if (
            evidence.get("minimum_ssim_millionths") != 800000
            or evidence.get("minimum_foreground_iou_millionths") != 800000
            or evidence.get("maximum_mean_absolute_error_millionths") != 60000
        ):
            errors.append("visual comparison thresholds cannot be weakened")
        repeat_count = evidence.get("repeat_count")
        if not isinstance(repeat_count, int) or repeat_count < 3:
            errors.append("visual determinism requires at least three repetitions")

    status = contract.get("status")
    if status == "complete":
        if not isinstance(gates, dict) or not gates or not all(
            value is True for value in gates.values()
        ):
            errors.append("Phase 7 cannot be complete while an acceptance gate is open")
        if not completion_summary_exists:
            errors.append("Phase 7 completion summary is absent")
    elif completion_summary_exists:
        errors.append("completion summary cannot exist while Phase 7 is in progress")
    return sorted(set(errors))


def validate_completion(summary: object, contract: object) -> list[str]:
    errors: list[str] = []
    if validate_public_safe(summary):
        errors.append("completion privacy: public-safe violation")
    if validate_canonical_json_numbers(summary):
        errors.append("completion numbers: canonical integer violation")
    if not isinstance(summary, dict) or not isinstance(contract, dict):
        return sorted(set(errors + ["completion summary is not an object"]))
    if (
        summary.get("schema_version") != 1
        or summary.get("kind") != "jfg-phase7-completion"
        or summary.get("status") != "pass"
    ):
        errors.append("completion identity is invalid")
    if summary.get("pins") != contract.get("pins"):
        errors.append("completion renderer pins do not match the contract")

    evidence = contract.get("evidence_format")
    if not isinstance(evidence, dict):
        evidence = {}
    minimum_ssim = evidence.get("minimum_ssim_millionths")
    minimum_iou = evidence.get("minimum_foreground_iou_millionths")
    maximum_mae = evidence.get("maximum_mean_absolute_error_millionths")
    minimum_repeats = evidence.get("repeat_count")
    scenes = summary.get("scenes")
    seen: set[str] = set()
    task_count = 0
    if not isinstance(scenes, list) or len(scenes) != len(SCENE_NAMES):
        errors.append("completion must contain both required scene records")
        scenes = []
    for scene in scenes:
        if not isinstance(scene, dict) or scene.get("scene") not in SCENE_NAMES:
            errors.append("completion contains an invalid scene record")
            continue
        name = scene["scene"]
        if name in seen:
            errors.append("completion contains a duplicate scene record")
        seen.add(name)
        real_tasks = scene.get("real_task_count")
        if not isinstance(real_tasks, int) or real_tasks < 1:
            errors.append(f"{name}: real task proof is missing")
        else:
            task_count += real_tasks
        if (
            not isinstance(scene.get("parsed_command_count"), int)
            or scene.get("parsed_command_count", 0) <= 0
            or scene.get("unsupported_command_count") != 0
        ):
            errors.append(f"{name}: command acceptance is invalid")
        if (
            scene.get("independent_semantic_oracle_match") is not True
            or scene.get("completion_committed_after_oracle") is not True
        ):
            errors.append(f"{name}: independent boundary proof is missing")
        repeat_count = scene.get("repeat_count")
        if (
            not isinstance(repeat_count, int)
            or not isinstance(minimum_repeats, int)
            or repeat_count < minimum_repeats
            or scene.get("pixel_output_byte_identical") is not True
        ):
            errors.append(f"{name}: repeat determinism is invalid")
        dimensions = scene.get("dimensions")
        if (
            not isinstance(dimensions, dict)
            or any(
                not isinstance(dimensions.get(key), int)
                or dimensions.get(key, 0) <= 0
                for key in ("rt64_width", "rt64_height", "vi_width", "vi_height")
            )
        ):
            errors.append(f"{name}: framebuffer dimensions are invalid")
        metrics = scene.get("worst_case_metrics")
        if not isinstance(metrics, dict):
            errors.append(f"{name}: visual metrics are missing")
        elif (
            not isinstance(minimum_ssim, int)
            or not isinstance(minimum_iou, int)
            or not isinstance(maximum_mae, int)
            or metrics.get("ssim_millionths", -1) < minimum_ssim
            or metrics.get("foreground_iou_millionths", -1) < minimum_iou
            or metrics.get("mean_absolute_error_millionths", maximum_mae + 1)
            > maximum_mae
        ):
            errors.append(f"{name}: visual thresholds are not satisfied")
        if scene.get("ssim_prefilter") != "gaussian-one-reference-pixel":
            errors.append(f"{name}: structural SSIM policy is invalid")
    if seen != set(SCENE_NAMES):
        errors.append("completion scene set is incomplete")
    scope = contract.get("scope")
    minimum_tasks = scope.get("minimum_real_task_count") if isinstance(scope, dict) else None
    if not isinstance(minimum_tasks, int) or task_count < minimum_tasks:
        errors.append("completion real task count is below the contract")

    isolation = summary.get("simulation_isolation")
    if not isinstance(isolation, dict):
        errors.append("simulation isolation evidence is missing")
    else:
        if isolation.get("hash_schema") != "sha256-rdram-snapshot-v1":
            errors.append("simulation hash schema is invalid")
        if isolation.get("modes") != ["disabled", "bounded-semantic", "rt64"]:
            errors.append("simulation isolation modes are incomplete")
        if (
            isolation.get("renderer_disabled_hash_equal") is not True
            or isolation.get("backend_hash_equal") is not True
            or isolation.get("source_snapshots_unchanged") is not True
        ):
            errors.append("simulation isolation equality is unproven")
        hashes = isolation.get("scene_hashes")
        hash_scenes: set[str] = set()
        if not isinstance(hashes, list) or len(hashes) != len(SCENE_NAMES):
            errors.append("simulation isolation scene hashes are incomplete")
            hashes = []
        for record in hashes:
            if not isinstance(record, dict) or record.get("scene") not in SCENE_NAMES:
                errors.append("simulation isolation contains an invalid scene hash")
                continue
            hash_scenes.add(record["scene"])
            values = [
                record.get("disabled"),
                record.get("bounded_semantic"),
                record.get("rt64"),
            ]
            if (
                any(not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value)
                    for value in values)
                or len(set(values)) != 1
            ):
                errors.append(f"{record['scene']}: simulation hashes differ")
        if hash_scenes != set(SCENE_NAMES):
            errors.append("simulation isolation scene hash set is incomplete")

    gates = contract.get("gates")
    if summary.get("gates") != gates or not isinstance(gates, dict) or not all(
        value is True for value in gates.values()
    ):
        errors.append("completion gate claims do not match the closed contract")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    arguments = parser.parse_args()
    try:
        contract = load_json(arguments.contract)
        schema = load_json(arguments.schema)
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        completion_exists = DEFAULT_COMPLETION.is_file()
        errors = validate_contract(
            contract,
            schema,
            dependency_lock,
            completion_summary_exists=completion_exists,
        )
        if completion_exists and isinstance(contract, dict) and contract.get("status") == "complete":
            errors.extend(validate_completion(load_json(DEFAULT_COMPLETION), contract))
    except (
        OSError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
    ):
        print("Phase 7 acceptance validation failed: input could not be read", file=sys.stderr)
        return 1
    if errors:
        print("Phase 7 acceptance validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Phase 7 acceptance contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
