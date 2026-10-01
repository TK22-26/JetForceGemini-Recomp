#!/usr/bin/env python3
"""Validate the public-safe RSP task and execution-path manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

if __package__:
    from .check_repository_hygiene import (
        run_git,
        scan_blob,
        scan_index_entries,
        scan_relative_path,
    )
    from .public_safe import validate_canonical_json_numbers, validate_public_safe
else:
    from check_repository_hygiene import (
        run_git,
        scan_blob,
        scan_index_entries,
        scan_relative_path,
    )
    from public_safe import validate_canonical_json_numbers, validate_public_safe


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "config" / "rsp-task-manifest.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "rsp-task-manifest.schema.json"

REQUIRED_PROGRAMS = frozenset({"boot-loader", "audio-primary", "graphics-primary"})
REQUIRED_TASK_CLASSES = frozenset({"audio", "graphics"})
EXPECTED_CURRENT_PIN_MANIFEST_SHA256 = (
    "1d07ab9288d4876dd5a93b7029a962e1d53290677e8c17bb0146befc1b7492cc"
)


def canonical_hash(value: object) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()

def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def unique_records(records: object, field: str, label: str) -> tuple[dict[str, dict], list[str]]:
    indexed: dict[str, dict] = {}
    errors: list[str] = []
    if not isinstance(records, list):
        return indexed, [f"{label}: expected an array"]
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"{label}[{index}]: expected an object")
            continue
        record_id = record.get(field)
        if not isinstance(record_id, str):
            errors.append(f"{label}[{index}].{field}: expected a string")
        elif record_id in indexed:
            errors.append(f"{label}: duplicate {field}: {record_id}")
        else:
            indexed[record_id] = record
    return indexed, errors


def validate_manifest_document(document: object, schema: object) -> list[str]:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [
        f"schema {'.'.join(str(item) for item in error.path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    ]
    errors.extend(validate_public_safe(document))
    errors.extend(validate_canonical_json_numbers(document))
    if not isinstance(document, dict):
        return sorted(set(errors))

    programs, record_errors = unique_records(document.get("inventory"), "id", "inventory")
    errors.extend(record_errors)
    if set(programs) != REQUIRED_PROGRAMS:
        errors.append("program IDs differ from the required RSP inventory")

    for program_id, program in programs.items():
        container_bytes = program.get("container_bytes")
        active_bytes = program.get("captured_active_bytes")
        overlay = program.get("overlay")
        if (
            type(container_bytes) is int
            and type(active_bytes) is int
            and active_bytes > container_bytes
        ):
            errors.append(f"{program_id}: captured active bytes exceed the container")
        if type(container_bytes) is int and container_bytes > 4096:
            if not isinstance(overlay, dict) or overlay.get("status") == "none":
                errors.append(f"{program_id}: oversized program lacks an overlay disposition")
        if isinstance(overlay, dict):
            status = overlay.get("status")
            slot_count = overlay.get("slot_count")
            variant_count = overlay.get("variant_count")
            switch_execution = overlay.get("switch_execution")
            if status == "none" and (
                slot_count != 0
                or variant_count != 0
                or switch_execution != "not-applicable"
            ):
                errors.append(f"{program_id}: no-overlay disposition is inconsistent")
            if status == "confirmed" and (
                type(slot_count) is not int
                or slot_count < 1
                or type(variant_count) is not int
                or variant_count < 2
                or switch_execution == "not-applicable"
            ):
                errors.append(f"{program_id}: confirmed overlay disposition is incomplete")

    capture = document.get("capture_evidence")
    if isinstance(capture, dict):
        task_classes, record_errors = unique_records(
            capture.get("task_classes"), "task_class", "capture task classes"
        )
        errors.extend(record_errors)
        if set(task_classes) != REQUIRED_TASK_CLASSES:
            errors.append("capture task classes must contain audio and graphics")
        declared_total = sum(
            record.get("count", 0)
            for record in task_classes.values()
            if type(record.get("count")) is int
        )
        if declared_total != capture.get("unique_task_count"):
            errors.append("capture task-class counts do not equal unique_task_count")
        if (
            capture.get("verification") != "maintainer-attested"
            or capture.get("regeneration_script_tracked") is not False
        ):
            errors.append("private capture must remain explicitly maintainer-attested")
        for task_class, record in task_classes.items():
            count = record.get("count")
            first_frame = record.get("first_frame")
            last_frame = record.get("last_frame")
            if (
                type(first_frame) is int
                and type(last_frame) is int
                and first_frame > last_frame
            ):
                errors.append(f"{task_class}: first frame exceeds last frame")
            if type(count) is int:
                for field in (
                    "unique_task_data_count",
                    "unique_ucode_count",
                    "unique_ucode_data_count",
                ):
                    value = record.get(field)
                    if type(value) is int and value > count:
                        errors.append(f"{task_class}: {field} exceeds task count")
    else:
        task_classes = {}

    audio = document.get("audio_path")
    if isinstance(audio, dict):
        if (
            audio.get("verification") != "maintainer-attested"
            or audio.get("regeneration_harness_tracked") is not False
        ):
            errors.append(
                "audio path evidence must remain explicitly maintainer-attested "
                "without a tracked regeneration harness"
            )
        if audio.get("normal_exit_count") != audio.get("representative_task_count"):
            errors.append("audio representative tasks did not all exit normally")
        if audio.get("status") == "representative-control-flow-observed" and not (
            audio.get("generation_passed") and audio.get("compile_passed")
        ):
            errors.append("audio control flow was observed without generation and compilation")
        captured_audio = task_classes.get("audio")
        if isinstance(captured_audio, dict) and audio.get(
            "representative_task_count"
        ) != captured_audio.get("count"):
            errors.append("audio representative count differs from captured audio count")
        decision = document.get("decision")
        if (
            audio.get("output_validation") == "not-established"
            and isinstance(decision, dict)
            and decision.get("audio_gate") != "blocked-output-unvalidated"
        ):
            errors.append("audio gate must remain blocked without output validation")

    graphics = document.get("graphics_path")
    if isinstance(graphics, dict):
        primary = graphics.get("primary")
        fallback = graphics.get("tested_fallback")
        if not isinstance(primary, dict) or (
            primary.get("status") != "implementation-required"
            or primary.get("native_handler_present") is not False
        ):
            errors.append("graphics primary state differs from the pinned no-handler baseline")
        if not isinstance(fallback, dict) or fallback.get("status") != "task-path-progressed":
            errors.append("graphics native gap lacks a task-path-tested candidate")
        else:
            if fallback.get("render_output_validation") != "not-established":
                errors.append("graphics render-output evidence is overstated")
            captured_graphics = task_classes.get("graphics")
            if isinstance(captured_graphics, dict) and fallback.get(
                "representative_task_count"
            ) != captured_graphics.get("count"):
                errors.append("graphics fallback count differs from captured graphics count")

        decision = document.get("decision")
        if (
            isinstance(fallback, dict)
            and fallback.get("render_output_validation") == "not-established"
            and isinstance(decision, dict)
            and decision.get("graphics_gate") != "blocked-render-output-unvalidated"
        ):
            errors.append("graphics gate must remain blocked without render-output validation")

    if canonical_hash(document) != EXPECTED_CURRENT_PIN_MANIFEST_SHA256:
        errors.append("current-pin RSP manifest differs from the maintainer-reviewed lock")

    return sorted(set(errors))


def validate_pins(document: object, dependency_lock: object) -> list[str]:
    if not isinstance(document, dict) or not isinstance(dependency_lock, dict):
        return ["manifest or dependency lock is not an object"]
    repositories = dependency_lock.get("repositories")
    if not isinstance(repositories, list):
        return ["dependency lock has no repository list"]
    locked = {
        item.get("id"): item.get("commit")
        for item in repositories
        if isinstance(item, dict)
    }
    pins = document.get("pins")
    if not isinstance(pins, dict):
        return ["manifest pins are missing"]
    expected = {
        "jfg_decomp": locked.get("jfg-decomp"),
        "n64recomp": locked.get("n64recomp"),
        "n64modernruntime": locked.get("n64modernruntime"),
        "rt64": locked.get("rt64"),
        "bizhawk": locked.get("bizhawk"),
        "gliden64_executed": locked.get("gliden64-executed"),
        "gliden64_inspected": locked.get("gliden64-inspected"),
    }
    errors = [
        f"pin mismatch for {name}"
        for name, commit in expected.items()
        if pins.get(name) != commit
    ]
    capture = document.get("capture_evidence")
    graphics = document.get("graphics_path")
    repositories_by_id = {
        item.get("id"): item for item in repositories if isinstance(item, dict)
    }
    bizhawk = repositories_by_id.get("bizhawk", {})
    artifacts = bizhawk.get("artifacts", {}) if isinstance(bizhawk, dict) else {}
    if isinstance(capture, dict):
        if capture.get("emulator_package_sha256") != artifacts.get(
            "bizhawk-2.11.1-win-x64.zip"
        ):
            errors.append("BizHawk package hash differs from dependency lock")
        if capture.get("graphics_plugin_binary_sha256") != artifacts.get(
            "mupen64plus-video-gliden64.dll"
        ):
            errors.append("executed graphics plug-in hash differs from dependency lock")
    if isinstance(graphics, dict):
        fallback = graphics.get("tested_fallback")
        inspected = graphics.get("source_inspection_candidate")
        scope = graphics.get("clean_room_scope")
        if not isinstance(fallback, dict) or (
            fallback.get("bizhawk_commit") != expected["bizhawk"]
            or fallback.get("commit") != expected["gliden64_executed"]
        ):
            errors.append("executed graphics fallback provenance is inconsistent")
        if not isinstance(inspected, dict) or inspected.get("commit") != expected[
            "gliden64_inspected"
        ]:
            errors.append("graphics source-inspection provenance is inconsistent")
        if not isinstance(scope, dict) or scope.get("source_commit") != expected[
            "gliden64_inspected"
        ]:
            errors.append("graphics clean-room scope provenance is inconsistent")
    return errors


def validate_tracked_repository(root: Path) -> list[str]:
    """Derive the no-private-body claim from the Git index, not the manifest."""
    try:
        output = run_git(root, ["ls-files", "--cached", "-z"], text=False)
        assert isinstance(output, bytes)
        relative_paths = sorted(
            item.decode("utf-8", errors="strict")
            for item in output.split(b"\0")
            if item
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as error:
        return [f"tracked repository scan could not enumerate the Git index: {error}"]
    errors: list[str] = []
    for relative in relative_paths:
        errors.extend(scan_relative_path(relative))
        try:
            data = run_git(root, ["show", f":{relative}"], text=False)
            assert isinstance(data, bytes)
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(f"{relative}: could not read tracked Git blob: {error}")
            continue
        errors.extend(scan_blob(data, relative))
    errors.extend(scan_index_entries(root))
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    arguments = parser.parse_args()

    try:
        manifest = load_json(arguments.manifest)
        schema = load_json(arguments.schema)
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        errors = validate_manifest_document(manifest, schema)
        errors.extend(validate_pins(manifest, dependency_lock))
        errors.extend(validate_tracked_repository(ROOT))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"RSP task manifest validation failed: {error}", file=sys.stderr)
        return 1

    if errors:
        print("RSP task manifest validation failed:", file=sys.stderr)
        for error in sorted(set(errors)):
            print(f"- {error}", file=sys.stderr)
        return 1
    print("RSP task manifest validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
