#!/usr/bin/env python3
"""Compare exactly two Phase 1 environment results and emit safe evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ENVIRONMENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,63}$")
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EXPECTED_ROM_SHA1 = "493ced9008dbe932d6e91179b68e8630cf23a023"
EXPECTED_ROM_SIZE = 33_554_432
NONDETERMINISTIC_RUN_FIELDS = {
    "run",
    "duration_seconds",
    "started_at_utc",
    "finished_at_utc",
}


def canonical_hash(value: object) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def load_evidence(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"evidence could not be read: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("evidence must be an object")
    return value


def normalized_run(run: Any) -> dict[str, Any]:
    if not isinstance(run, dict):
        raise ValueError("each run must be an object")
    normalized = {
        key: value
        for key, value in run.items()
        if key not in NONDETERMINISTIC_RUN_FIELDS
    }
    if not normalized:
        raise ValueError("run contains no comparable build output")
    return normalized


def _validate_legacy_range(
    value: object,
    label: str,
    *,
    maximum: int | None = None,
) -> None:
    if not isinstance(value, dict) or set(value) != {"start", "end"}:
        raise ValueError(f"{label} is invalid")
    start, end = value.get("start"), value.get("end")
    if (
        isinstance(start, bool)
        or not isinstance(start, int)
        or isinstance(end, bool)
        or not isinstance(end, int)
        or start < 0
        or end <= start
        or (maximum is not None and end > maximum)
    ):
        raise ValueError(f"{label} is invalid")


def remove_private_overlay_coordinates(run: dict[str, Any]) -> None:
    """Normalize legacy private ranges to public validation predicates in-place."""
    overlays = run.get("overlays")
    if not isinstance(overlays, dict):
        raise ValueError("overlay evidence is missing")
    rom_table = overlays.get("rom_table")
    splat = overlays.get("splat_layout")
    if not isinstance(rom_table, dict) or not isinstance(splat, dict):
        raise ValueError("overlay summaries are invalid")

    legacy_min = rom_table.pop("rom_range_min", None)
    legacy_max = rom_table.pop("rom_range_max", None)
    has_legacy_rom_range = legacy_min is not None or legacy_max is not None
    if has_legacy_rom_range:
        if (
            isinstance(legacy_min, bool)
            or not isinstance(legacy_min, int)
            or isinstance(legacy_max, bool)
            or not isinstance(legacy_max, int)
            or legacy_min < 0
            or legacy_max <= legacy_min
            or legacy_max > EXPECTED_ROM_SIZE
        ):
            raise ValueError("legacy overlay ROM range is invalid")
        rom_table.setdefault("all_rom_ranges_in_bounds", True)
    if rom_table.get("all_rom_ranges_in_bounds") is not True:
        raise ValueError("overlay ROM bounds verdict is invalid")

    legacy_rom_range = splat.pop("rom_range", None)
    if legacy_rom_range is not None:
        _validate_legacy_range(
            legacy_rom_range,
            "legacy splat ROM range",
            maximum=EXPECTED_ROM_SIZE,
        )
        splat.setdefault("all_rom_ranges_well_formed", True)
    if splat.get("all_rom_ranges_well_formed") is not True:
        raise ValueError("splat ROM range verdict is invalid")

    legacy_vram_range = splat.pop("synthetic_vram_range", None)
    if legacy_vram_range is not None:
        _validate_legacy_range(legacy_vram_range, "legacy splat VRAM range")
        splat.setdefault("all_synthetic_vram_ranges_nonoverlapping", True)
    if splat.get("all_synthetic_vram_ranges_nonoverlapping") is not True:
        raise ValueError("splat VRAM range verdict is invalid")


def normalized_cross_environment_run(run: dict[str, Any]) -> dict[str, Any]:
    """Remove toolchain-formatting hashes while retaining semantic checks."""
    normalized = copy.deepcopy(run)
    elf = normalized.get("elf")
    if isinstance(elf, dict):
        linker_map = elf.get("map")
        if isinstance(linker_map, dict):
            linker_map.pop("sha256", None)
    return normalized


def validate_symbol_category_counts(elf: dict[str, Any], environment_id: str) -> None:
    symbol_count = elf.get("symbol_count")
    if (
        isinstance(symbol_count, bool)
        or not isinstance(symbol_count, int)
        or symbol_count < 1
    ):
        raise ValueError(f"{environment_id}: ELF symbol count is invalid")
    for label, counts in (
        ("symbol type", elf.get("symbol_types")),
        ("symbol binding", elf.get("symbol_bindings")),
    ):
        if (
            not isinstance(counts, dict)
            or not counts
            or any(
                not isinstance(name, str)
                or not name
                or isinstance(count, bool)
                or not isinstance(count, int)
                or count < 0
                for name, count in counts.items()
            )
            or sum(counts.values()) != symbol_count
        ):
            raise ValueError(f"{environment_id}: ELF {label} counts are invalid")
    relocation_count = elf.get("relocation_count")
    if (
        isinstance(relocation_count, bool)
        or not isinstance(relocation_count, int)
        or relocation_count < 0
    ):
        raise ValueError(f"{environment_id}: ELF relocation count is invalid")


def normalize_map_coverage(elf: dict[str, Any], environment_id: str) -> None:
    linker_map = elf.get("map")
    if not isinstance(linker_map, dict):
        raise ValueError(f"{environment_id}: ELF linker-map summary is missing")
    counts: dict[str, int] = {}
    for name in (
        "section_checked_count",
        "section_missing_count",
        "section_mismatch_count",
        "symbol_checked_count",
        "symbol_missing_count",
        "symbol_mismatch_count",
    ):
        value = linker_map.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{environment_id}: linker-map {name} is invalid")
        counts[name] = value
    section_candidates = counts["section_checked_count"] + counts["section_missing_count"]
    symbol_candidates = counts["symbol_checked_count"] + counts["symbol_missing_count"]
    for key, derived in (
        ("section_candidate_count", section_candidates),
        ("symbol_candidate_count", symbol_candidates),
    ):
        supplied = linker_map.get(key)
        if supplied is not None and supplied != derived:
            raise ValueError(f"{environment_id}: linker-map {key} is inconsistent")
        linker_map[key] = derived
    checked_consistent = (
        counts["section_mismatch_count"] == 0
        and counts["symbol_mismatch_count"] == 0
    )
    has_coverage = counts["section_checked_count"] > 0 and counts["symbol_checked_count"] > 0
    coverage_complete = (
        counts["section_missing_count"] == 0
        and counts["symbol_missing_count"] == 0
    )
    if not checked_consistent:
        verdict = "inconsistent"
    elif not has_coverage:
        verdict = "insufficient"
    elif coverage_complete:
        verdict = "complete"
    else:
        verdict = "partial"
    expected_consistent = checked_consistent and has_coverage
    supplied_consistent = linker_map.get("consistent")
    if supplied_consistent is not None and supplied_consistent is not expected_consistent:
        raise ValueError(f"{environment_id}: linker-map consistency verdict is inconsistent")
    for key, derived in (
        ("consistent", expected_consistent),
        ("coverage_complete", coverage_complete),
        ("coverage_verdict", verdict),
    ):
        supplied = linker_map.get(key)
        if supplied is not None and supplied != derived:
            raise ValueError(f"{environment_id}: linker-map {key} is inconsistent")
        linker_map[key] = derived


def validate_environment_evidence(
    value: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], bool]:
    if value.get("schema_version") != 1:
        raise ValueError("unsupported environment evidence schema")
    environment_id = value.get("environment_id")
    if not isinstance(environment_id, str) or not ENVIRONMENT_ID_RE.fullmatch(environment_id):
        raise ValueError("environment_id is invalid")
    declared_equivalent = value.get("builds_equivalent")
    if not isinstance(declared_equivalent, bool):
        raise ValueError(f"{environment_id}: builds_equivalent must be boolean")
    environment = value.get("environment")
    if (
        not isinstance(environment, dict)
        or not isinstance(environment.get("distribution"), str)
        or not environment["distribution"]
    ):
        raise ValueError(f"{environment_id}: environment description is invalid")

    decomp_commit = value.get("decomp_commit")
    rom_sha1 = value.get("input_rom_sha1")
    if not isinstance(decomp_commit, str) or not SHA1_RE.fullmatch(decomp_commit):
        raise ValueError(f"{environment_id}: decomp_commit is invalid")
    if rom_sha1 != EXPECTED_ROM_SHA1:
        raise ValueError(f"{environment_id}: input_rom_sha1 is not the supported US ROM")

    runs = value.get("runs")
    if not isinstance(runs, list) or len(runs) != 2:
        raise ValueError(f"{environment_id}: exactly two repeated builds are required")
    normalized = [normalized_run(run) for run in runs]
    for run in normalized:
        remove_private_overlay_coordinates(run)
        if run.get("rom_sha1") != rom_sha1:
            raise ValueError(f"{environment_id}: output ROM hash differs from input hash")
        elf = run.get("elf")
        if not isinstance(elf, dict) or not SHA256_RE.fullmatch(str(elf.get("sha256", ""))):
            raise ValueError(f"{environment_id}: ELF summary is missing a SHA-256")
        validate_symbol_category_counts(elf, environment_id)
        normalize_map_coverage(elf, environment_id)
    repeated_equivalent = normalized[0] == normalized[1]
    if declared_equivalent != repeated_equivalent:
        raise ValueError(
            f"{environment_id}: builds_equivalent disagrees with repeated build outputs"
        )
    return environment_id, normalized, repeated_equivalent


def compare_evidence(first: dict[str, Any], second: dict[str, Any]) -> dict[str, object]:
    first_id, first_runs, first_repeated = validate_environment_evidence(first)
    second_id, second_runs, second_repeated = validate_environment_evidence(second)
    if first_id == second_id:
        raise ValueError("two distinct environment IDs are required")
    if first["decomp_commit"] != second["decomp_commit"]:
        raise ValueError("decomp commits differ across environments")
    if first["input_rom_sha1"] != second["input_rom_sha1"]:
        raise ValueError("input ROM hashes differ across environments")
    first_source = first.get("source")
    second_source = second.get("source")
    if not isinstance(first_source, dict) or first_source != second_source:
        raise ValueError("source trees or submodule pins differ across environments")
    first_tools = first.get("tools")
    second_tools = second.get("tools")
    if not isinstance(first_tools, dict) or not isinstance(second_tools, dict):
        raise ValueError("tool evidence is missing")
    first_artifacts = first_tools.get("artifacts")
    second_artifacts = second_tools.get("artifacts")
    if not isinstance(first_artifacts, dict) or not isinstance(second_artifacts, dict):
        raise ValueError("downloaded tool artifact evidence is missing")
    common_artifact_names = ("ido_recomp_manifest_sha256", "objdiff_cli_sha256")
    first_common_artifacts = {
        name: first_artifacts.get(name) for name in common_artifact_names
    }
    second_common_artifacts = {
        name: second_artifacts.get(name) for name in common_artifact_names
    }
    if first_common_artifacts != second_common_artifacts:
        raise ValueError("downloaded tool artifacts differ across environments")
    first_run = first_runs[0]
    second_run = second_runs[0]
    first_cross_run = normalized_cross_environment_run(first_run)
    second_cross_run = normalized_cross_environment_run(second_run)
    divergence_reasons: list[str] = []
    if not first_repeated:
        divergence_reasons.append(f"{first_id}:repeated-build-output")
    if not second_repeated:
        divergence_reasons.append(f"{second_id}:repeated-build-output")
    if first_cross_run != second_cross_run:
        divergence_reasons.append("cross-environment-build-output")
    equivalent = not divergence_reasons

    elf = first_run["elf"]
    assert isinstance(elf, dict)
    section_table_hash = elf.get("section_table_sha256", elf.get("section_shape_sha256"))
    if not isinstance(section_table_hash, str) or not SHA256_RE.fullmatch(section_table_hash):
        raise ValueError("ELF summary is missing a section-table SHA-256")
    section_count = elf.get("section_count")
    symbol_count = elf.get("symbol_count")
    symbol_types = elf.get("symbol_types")
    symbol_bindings = elf.get("symbol_bindings")
    relocation_count = elf.get("relocation_count")
    if (
        isinstance(section_count, bool)
        or not isinstance(section_count, int)
        or section_count < 1
        or isinstance(symbol_count, bool)
        or not isinstance(symbol_count, int)
        or symbol_count < 1
    ):
        raise ValueError("ELF section/symbol counts are invalid")
    summary: dict[str, object] = {
        "$schema": "../../schemas/phase1-build-evidence.schema.json",
        "schema_version": 1,
        "kind": "phase1-cross-environment-equivalence",
        "environment_ids": sorted((first_id, second_id)),
        "decomp_commit": first["decomp_commit"],
        "input_rom_sha1": first["input_rom_sha1"],
        "equivalent": equivalent,
        "verdict": "equivalent" if equivalent else "divergent",
        "divergence_reasons": sorted(divergence_reasons),
        "build_summary_sha256_by_environment": {
            first_id: canonical_hash(
                [normalized_cross_environment_run(run) for run in first_runs]
            ),
            second_id: canonical_hash(
                [normalized_cross_environment_run(run) for run in second_runs]
            ),
        },
        "source": {
            "decomp_tree": first_source.get("decomp_tree"),
            "requirements_sha256": first_source.get("requirements_sha256"),
            "submodule_pins_sha256": canonical_hash(first_source.get("submodules")),
        },
        "tool_artifacts_sha256": canonical_hash(first_common_artifacts),
        "environment_toolchains": [
            {
                "environment_id": value["environment_id"],
                "distribution": value["environment"]["distribution"],
                "versions": value["tools"]["versions"],
                "artifacts": value["tools"]["artifacts"],
            }
            for value in sorted((first, second), key=lambda item: item["environment_id"])
        ],
        "verification": {
            "ci_verifiable": {
                "schema_validation": True,
                "semantic_invariants": True,
                "environment_correspondence": True,
                "rebuilds_private_artifacts": False,
            },
            "maintainer_attestation": {
                "status": "passed" if equivalent else "failed",
                "private_rom_required": True,
                "environment_record_count": 2,
                "clean_build_count": 4,
            },
        },
    }
    if not equivalent:
        validate_aggregate_evidence(summary)
        return summary
    summary.update({
        "build_summary_sha256": canonical_hash(first_cross_run),
        "elf": {
            "sha256": elf["sha256"],
            "section_table_sha256": section_table_hash,
            "section_count": section_count,
            "allocated_section_count": elf.get("allocated_section_count"),
            "symbol_count": symbol_count,
            "symbol_types": symbol_types,
            "symbol_bindings": symbol_bindings,
            "relocation_count": relocation_count,
            "unexpected_section_overlap_count": elf.get(
                "unexpected_section_overlap_count"
            ),
            "conflicting_export_name_count": elf.get(
                "conflicting_export_name_count"
            ),
            "map": {
                **{
                    key: value
                    for key, value in elf.get("map", {}).items()
                    if key != "sha256"
                },
                "sha256_by_environment": {
                    first_id: first_run["elf"]["map"]["sha256"],
                    second_id: second_run["elf"]["map"]["sha256"],
                },
            },
        },
        "report": first_run.get("report"),
        "overlays": first_run.get("overlays"),
    })
    validate_aggregate_evidence(summary, require_success=True)
    return summary


def _require_nonnegative(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"aggregate {label} is invalid")
    return value


def validate_aggregate_evidence(
    value: dict[str, Any], *, require_success: bool = False
) -> None:
    environment_ids = value.get("environment_ids")
    if (
        not isinstance(environment_ids, list)
        or len(environment_ids) != 2
        or len(set(environment_ids)) != 2
        or environment_ids != sorted(environment_ids)
        or any(not isinstance(item, str) or not ENVIRONMENT_ID_RE.fullmatch(item) for item in environment_ids)
    ):
        raise ValueError("aggregate environment_ids are invalid")
    toolchains = value.get("environment_toolchains")
    if not isinstance(toolchains, list) or len(toolchains) != 2:
        raise ValueError("aggregate environment toolchains are invalid")
    toolchain_ids = [item.get("environment_id") for item in toolchains if isinstance(item, dict)]
    if sorted(toolchain_ids) != environment_ids or len(set(toolchain_ids)) != 2:
        raise ValueError("aggregate environment/toolchain IDs do not correspond")
    build_hashes = value.get("build_summary_sha256_by_environment")
    if (
        not isinstance(build_hashes, dict)
        or sorted(build_hashes) != environment_ids
        or any(not isinstance(item, str) or not SHA256_RE.fullmatch(item) for item in build_hashes.values())
    ):
        raise ValueError("aggregate build-summary environment IDs do not correspond")

    equivalent = value.get("equivalent")
    reasons = value.get("divergence_reasons")
    if not isinstance(equivalent, bool) or not isinstance(reasons, list):
        raise ValueError("aggregate equivalence verdict is invalid")
    expected_verdict = "equivalent" if equivalent else "divergent"
    if value.get("verdict") != expected_verdict:
        raise ValueError("aggregate verdict disagrees with equivalent")
    if equivalent and reasons:
        raise ValueError("equivalent evidence cannot contain divergence reasons")
    if not equivalent and not reasons:
        raise ValueError("divergent evidence must contain a reason")
    if require_success and not equivalent:
        raise ValueError("tracked Phase 1 evidence must record a successful equivalence verdict")
    verification = value.get("verification")
    if not isinstance(verification, dict):
        raise ValueError("aggregate verification scope is missing")
    ci_scope = verification.get("ci_verifiable")
    attestation = verification.get("maintainer_attestation")
    if (
        not isinstance(ci_scope, dict)
        or ci_scope.get("schema_validation") is not True
        or ci_scope.get("semantic_invariants") is not True
        or ci_scope.get("environment_correspondence") is not True
        or ci_scope.get("rebuilds_private_artifacts") is not False
    ):
        raise ValueError("aggregate CI-verifiable scope is invalid")
    if (
        not isinstance(attestation, dict)
        or attestation.get("status") != ("passed" if equivalent else "failed")
        or attestation.get("private_rom_required") is not True
        or attestation.get("environment_record_count") != 2
        or attestation.get("clean_build_count") != 4
    ):
        raise ValueError("aggregate maintainer-attestation scope is invalid")
    if not equivalent:
        return

    elf = value.get("elf")
    if not isinstance(elf, dict):
        raise ValueError("equivalent aggregate is missing ELF evidence")
    symbol_count = _require_nonnegative(elf.get("symbol_count"), "ELF symbol_count")
    for label in ("symbol_types", "symbol_bindings"):
        counts = elf.get(label)
        if not isinstance(counts, dict) or sum(
            _require_nonnegative(item, f"ELF {label}") for item in counts.values()
        ) != symbol_count:
            raise ValueError(f"aggregate ELF {label} do not sum to symbol_count")
    section_count = _require_nonnegative(elf.get("section_count"), "ELF section_count")
    allocated = _require_nonnegative(
        elf.get("allocated_section_count"), "ELF allocated_section_count"
    )
    if allocated > section_count:
        raise ValueError("aggregate allocated sections exceed total sections")
    if _require_nonnegative(elf.get("unexpected_section_overlap_count"), "ELF overlaps"):
        raise ValueError("equivalent aggregate contains unexpected section overlaps")
    if _require_nonnegative(elf.get("conflicting_export_name_count"), "ELF exports"):
        raise ValueError("equivalent aggregate contains conflicting exports")

    linker_map = elf.get("map")
    if not isinstance(linker_map, dict):
        raise ValueError("equivalent aggregate is missing map evidence")
    section_checked = _require_nonnegative(linker_map.get("section_checked_count"), "map sections checked")
    section_missing = _require_nonnegative(linker_map.get("section_missing_count"), "map sections missing")
    symbol_checked = _require_nonnegative(linker_map.get("symbol_checked_count"), "map symbols checked")
    symbol_missing = _require_nonnegative(linker_map.get("symbol_missing_count"), "map symbols missing")
    if linker_map.get("section_candidate_count") != section_checked + section_missing:
        raise ValueError("aggregate map section coverage arithmetic is invalid")
    if linker_map.get("symbol_candidate_count") != symbol_checked + symbol_missing:
        raise ValueError("aggregate map symbol coverage arithmetic is invalid")
    section_mismatches = _require_nonnegative(linker_map.get("section_mismatch_count"), "map section mismatches")
    symbol_mismatches = _require_nonnegative(linker_map.get("symbol_mismatch_count"), "map symbol mismatches")
    expected_consistent = (
        section_checked > 0
        and symbol_checked > 0
        and section_mismatches == 0
        and symbol_mismatches == 0
    )
    if linker_map.get("consistent") is not expected_consistent:
        raise ValueError("aggregate map consistency verdict is invalid")
    complete = section_missing == 0 and symbol_missing == 0
    expected_coverage = "complete" if complete else "partial"
    if linker_map.get("coverage_complete") is not complete or linker_map.get("coverage_verdict") != expected_coverage:
        raise ValueError("aggregate map coverage verdict is invalid")
    map_hashes = linker_map.get("sha256_by_environment")
    if not isinstance(map_hashes, dict) or sorted(map_hashes) != environment_ids:
        raise ValueError("aggregate map hash environment IDs do not correspond")

    overlays = value.get("overlays")
    if not isinstance(overlays, dict):
        raise ValueError("equivalent aggregate is missing overlay evidence")
    rom_table = overlays.get("rom_table")
    splat = overlays.get("splat_layout")
    if not isinstance(rom_table, dict) or not isinstance(splat, dict):
        raise ValueError("aggregate overlay summaries are invalid")
    populated = _require_nonnegative(rom_table.get("populated_overlay_count"), "populated overlays")
    empty = _require_nonnegative(rom_table.get("empty_overlay_count"), "empty overlays")
    slots = _require_nonnegative(rom_table.get("table_slot_count"), "overlay slots")
    if populated + empty != slots:
        raise ValueError("aggregate overlay population arithmetic is invalid")
    if (
        _require_nonnegative(rom_table.get("dynamic_vram_overlay_count"), "dynamic overlays")
        + _require_nonnegative(rom_table.get("fixed_vram_overlay_count"), "fixed overlays")
        != populated
    ):
        raise ValueError("aggregate overlay VRAM classification arithmetic is invalid")
    if rom_table.get("all_rom_ranges_in_bounds") is not True:
        raise ValueError("aggregate overlay ROM bounds verdict is invalid")
    for byte_key, count_key in (
        ("primary_relocation_bytes", "relocation_entry_count"),
        ("secondary_relocation_bytes", "secondary_relocation_entry_count"),
    ):
        byte_count = _require_nonnegative(rom_table.get(byte_key), byte_key)
        entry_count = _require_nonnegative(rom_table.get(count_key), count_key)
        if byte_count % 8 or byte_count // 8 != entry_count:
            raise ValueError("aggregate overlay relocation byte/count arithmetic is invalid")
    if splat.get("overlay_count") != populated or splat.get("empty_slot_count") != empty:
        raise ValueError("aggregate ROM/splat overlay populations differ")
    if (
        splat.get("all_rom_ranges_well_formed") is not True
        or splat.get("all_synthetic_vram_ranges_nonoverlapping") is not True
    ):
        raise ValueError("aggregate splat overlay range verdict is invalid")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("first", nargs="?", type=Path)
    parser.add_argument("second", nargs="?", type=Path)
    parser.add_argument(
        "--validate-aggregate",
        type=Path,
        help="validate an already aggregated, successful tracked evidence document",
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        if arguments.validate_aggregate is not None:
            if arguments.first is not None or arguments.second is not None or arguments.output:
                parser.error("--validate-aggregate cannot be combined with comparison inputs")
            summary = load_evidence(arguments.validate_aggregate)
            validate_aggregate_evidence(summary, require_success=True)
        else:
            if arguments.first is None or arguments.second is None:
                parser.error("two environment evidence paths are required")
            summary = compare_evidence(
                load_evidence(arguments.first),
                load_evidence(arguments.second),
            )
    except ValueError as error:
        print(f"Phase 1 evidence comparison failed: {error}", file=sys.stderr)
        return 1

    if arguments.validate_aggregate is not None:
        print("Phase 1 aggregate evidence validation passed.")
        return 0

    rendered = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if summary.get("equivalent") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
