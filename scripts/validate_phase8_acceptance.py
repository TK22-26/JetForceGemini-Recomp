#!/usr/bin/env python3
"""Validate the Phase 8/M4 interactive-build contract."""

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
DEFAULT_CONTRACT = ROOT / "config" / "phase8-acceptance.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "phase8-acceptance.schema.json"
DEFAULT_COMPLETION = ROOT / "evidence" / "phase8-completion.json"
SCENARIOS = (
    "launch-to-title",
    "title-menu-new-game",
    "first-gameplay-input",
    "save-exit-relaunch-resume",
)
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


def validate_contract(
    contract: object,
    schema: object,
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

    scope = contract.get("scope")
    evidence = contract.get("evidence_format")
    gates = contract.get("gates")
    if not isinstance(scope, dict):
        errors.append("Phase 8 scope is missing")
    else:
        if scope.get("required_scenarios") != list(SCENARIOS):
            errors.append("all four Phase 8 scenarios must remain in order")
        if scope.get("required_input_replays", 0) < 3:
            errors.append("Phase 8 requires at least three input replays")
        if scope.get("minimum_audio_seconds", 0) < 60:
            errors.append("Phase 8 requires at least sixty seconds of audio")
        if scope.get("maximum_unsupported_runtime_boundaries") != 0:
            errors.append("Phase 8 permits no unsupported runtime boundary")
    if not isinstance(evidence, dict):
        errors.append("Phase 8 evidence policy is missing")
    else:
        expected = {
            "private_artifact_policy": "ignored-local-only",
            "oracle": "independent-emulator-record-and-replay",
            "checkpoint_policy": "event-and-state-hash",
            "input_policy": "timestamped-deterministic-replay",
            "save_policy": "fresh-profile-process-restart",
            "audio_policy": "decoded-pcm-and-device-consumption",
        }
        for key, value in expected.items():
            if evidence.get(key) != value:
                errors.append(f"Phase 8 evidence policy changed: {key}")

    status = contract.get("status")
    if status == "complete":
        if not isinstance(gates, dict) or not gates or not all(
            value is True for value in gates.values()
        ):
            errors.append("Phase 8 cannot be complete while an acceptance gate is open")
        if not completion_summary_exists:
            errors.append("Phase 8 completion summary is absent")
    elif completion_summary_exists:
        errors.append("completion summary cannot exist while Phase 8 is in progress")
    return sorted(set(errors))


def _positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


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
        or summary.get("kind") != "jfg-phase8-completion"
        or summary.get("status") != "pass"
    ):
        errors.append("completion identity is invalid")

    scope = contract.get("scope")
    scope = scope if isinstance(scope, dict) else {}
    scenarios = summary.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != len(SCENARIOS):
        errors.append("completion must contain all four Phase 8 scenarios")
        scenarios = []
    for expected, record in zip(SCENARIOS, scenarios, strict=False):
        if not isinstance(record, dict) or record.get("scenario") != expected:
            errors.append("completion scenarios are missing or out of order")
            continue
        if record.get("oracle_checkpoint_match") is not True:
            errors.append(f"{expected}: independent checkpoint does not match")
        hashes = record.get("repeat_state_hashes")
        journal_hashes = record.get("repeat_journal_hashes")
        repeats = scope.get("required_input_replays")
        if (
            not isinstance(hashes, list)
            or not isinstance(repeats, int)
            or len(hashes) < repeats
            or any(
                not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None
                for value in hashes
            )
            or len(set(hashes)) != 1
        ):
            errors.append(f"{expected}: deterministic state hashes are invalid")
        if (
            not isinstance(journal_hashes, list)
            or not isinstance(repeats, int)
            or len(journal_hashes) < repeats
            or any(
                not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None
                for value in journal_hashes
            )
            or len(set(journal_hashes)) != 1
        ):
            errors.append(f"{expected}: deterministic journal hashes are invalid")

    runtime = summary.get("runtime")
    if not isinstance(runtime, dict):
        errors.append("live runtime evidence is missing")
    elif (
        runtime.get("generated_cpu") is not True
        or runtime.get("continuous_rt64") is not True
        or not _positive_integer(runtime.get("presented_frames"))
        or runtime.get("unsupported_boundaries") != 0
    ):
        errors.append("live runtime evidence is incomplete")

    input_record = summary.get("input")
    if not isinstance(input_record, dict):
        errors.append("input evidence is missing")
    elif (
        not _positive_integer(input_record.get("sample_count"))
        or input_record.get("timestamped") is not True
        or input_record.get("disconnect_reconnect") is not True
        or input_record.get("controlled_gameplay_response") is not True
    ):
        errors.append("input evidence is incomplete")

    audio = summary.get("audio")
    minimum_audio = scope.get("minimum_audio_seconds")
    if not isinstance(audio, dict):
        errors.append("audio evidence is missing")
    elif (
        not _positive_integer(audio.get("decoded_task_count"))
        or not isinstance(minimum_audio, int)
        or audio.get("device_consumed_seconds", 0) < minimum_audio
        or audio.get("underrun_count") != 0
        or audio.get("overrun_count") != 0
        or audio.get("unsupported_command_count") != 0
    ):
        errors.append("audio evidence is incomplete")

    persistence = summary.get("persistence")
    if not isinstance(persistence, dict):
        errors.append("persistence evidence is missing")
    elif (
        persistence.get("fresh_profile") is not True
        or persistence.get("save_committed") is not True
        or persistence.get("process_count", 0) < 2
        or persistence.get("save_reloaded") is not True
        or persistence.get("configuration_reloaded") is not True
        or persistence.get("controller_pak_exercised") is not True
    ):
        errors.append("persistence evidence is incomplete")

    if summary.get("gates") != contract.get("gates"):
        errors.append("completion gates do not match the contract")
    gates = contract.get("gates")
    if not isinstance(gates, dict) or not all(value is True for value in gates.values()):
        errors.append("completion cannot reconcile against open gates")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    arguments = parser.parse_args()
    try:
        contract = load_json(arguments.contract)
        schema = load_json(arguments.schema)
        completion_exists = DEFAULT_COMPLETION.is_file()
        errors = validate_contract(
            contract,
            schema,
            completion_summary_exists=completion_exists,
        )
        if completion_exists and isinstance(contract, dict) and contract.get("status") == "complete":
            errors.extend(validate_completion(load_json(DEFAULT_COMPLETION), contract))
    except (OSError, json.JSONDecodeError, TypeError, ValueError, OverflowError, RecursionError):
        print("Phase 8 acceptance validation failed: input could not be read", file=sys.stderr)
        return 1
    if errors:
        print("Phase 8 acceptance validation failed:", file=sys.stderr)
        for error in sorted(set(errors)):
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Phase 8 acceptance contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
