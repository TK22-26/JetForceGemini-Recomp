#!/usr/bin/env python3
"""Run a local, privacy-safe N64Recomp CPU metadata feasibility probe."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

try:
    from .public_safe import validate_canonical_json_numbers, validate_public_safe
    from .validate_elf import parse_header, parse_sections, parse_symbols, readelf
except ImportError:  # Direct script execution.
    from public_safe import validate_canonical_json_numbers, validate_public_safe
    from validate_elf import parse_header, parse_sections, parse_symbols, readelf


FAILED_FUNCTION_RE = re.compile(r"Error in recompiling ([^,\r\n]+)")
MISSING_STUB_RE = re.compile(r"Function ([^\r\n]+) is stubbed out .* does not exist!")
PLACEHOLDER_JAL = 0x0C000000
EXPECTED_ROM_SHA1 = "493ced9008dbe932d6e91179b68e8630cf23a023"
EXPECTED_ROM_SIZE = 33_554_432
EXPECTED_ELF_SHA256 = "ea06a1f7fd54454fbf65f9dbe0bb6d731d5a44f732c16c8d157b475cb8078f1b"
EXPECTED_N64RECOMP_COMMIT = "ffb39cdad1da5de07eaaa48bd1db4a89a7986771"
EXPECTED_N64RECOMP_SHA256 = "34958d6ae8c047adb772090c75fdcc051036646a1db58595694f814c3a4a09b6"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def digest(path: Path, algorithm: str = "sha256") -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def verify_file_identity(
    path: Path,
    *,
    expected_size: int | None = None,
    algorithm: str,
    expected_digest: str,
    label: str,
) -> str:
    if not path.is_file():
        raise ValueError(f"{label} is missing")
    if expected_size is not None and path.stat().st_size != expected_size:
        raise ValueError(f"{label} size does not match the supported input")
    actual = digest(path, algorithm)
    if actual != expected_digest.lower():
        raise ValueError(f"{label} digest does not match the supported input")
    return actual


def pinned_source_commit(source_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(source_root.resolve()), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip().lower()
    if result.returncode != 0 or commit != EXPECTED_N64RECOMP_COMMIT:
        raise ValueError("N64Recomp source root is not at the pinned commit")
    cleanliness = subprocess.run(
        ["git", "-C", str(source_root.resolve()), "diff", "--quiet", "HEAD", "--"],
        capture_output=True,
        text=True,
    )
    if cleanliness.returncode != 0:
        raise ValueError("N64Recomp source root has tracked changes from the pinned commit")
    return commit


def verify_probe_inputs(
    executable: Path,
    elf: Path,
    rom: Path,
    source_root: Path,
    expected_executable_sha256: str,
) -> dict[str, object]:
    verify_file_identity(
        rom,
        expected_size=EXPECTED_ROM_SIZE,
        algorithm="sha1",
        expected_digest=EXPECTED_ROM_SHA1,
        label="ROM",
    )
    verify_file_identity(
        elf,
        algorithm="sha256",
        expected_digest=EXPECTED_ELF_SHA256,
        label="Phase 1 ELF",
    )
    executable_sha256 = digest(executable)
    source_commit = pinned_source_commit(source_root)
    identity_methods = ["source-commit"]
    expected = expected_executable_sha256.lower()
    if SHA256_RE.fullmatch(expected) is None:
        raise ValueError("expected N64Recomp executable SHA-256 is malformed")
    if expected != EXPECTED_N64RECOMP_SHA256:
        raise ValueError("expected N64Recomp executable SHA-256 differs from the pinned build")
    if executable_sha256 != expected:
        raise ValueError("N64Recomp executable SHA-256 does not match")
    identity_methods.append("executable-sha256")
    return {
        "supported_rom_size": EXPECTED_ROM_SIZE,
        "supported_rom_sha1": EXPECTED_ROM_SHA1,
        "elf_sha256": EXPECTED_ELF_SHA256,
        "n64recomp_source_commit": source_commit,
        "n64recomp_executable_sha256": executable_sha256,
        "n64recomp_identity_methods": identity_methods,
    }


def verify_private_work_directory(work: Path) -> None:
    """Reject detailed probe output in a tracked or potentially trackable path."""
    repository = Path(__file__).resolve().parents[1]
    try:
        relative = work.resolve().relative_to(repository)
    except ValueError:
        return
    ignored = subprocess.run(
        ["git", "-C", str(repository), "check-ignore", "-q", "--", relative.as_posix()],
        capture_output=True,
        text=True,
    )
    if ignored.returncode != 0:
        raise ValueError("work directory inside the repository must be Git-ignored")


def canonical_hash(value: object) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def diagnostic_kind(diagnostic: str) -> str:
    if "No function found for jal target:" in diagnostic:
        return "missing-direct-call-target"
    if "Failed to determine size of jump table" in diagnostic:
        return "unbounded-jump-table"
    if "Unsupported reloc type" in diagnostic:
        return "unsupported-elf-relocation"
    if "Unhandled branch in" in diagnostic:
        return "out-of-range-branch"
    raise ValueError("unrecognized N64Recomp diagnostic class")


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def n64recomp_builtin_names(source_root: Path | None) -> set[str]:
    if source_root is None:
        return set()
    symbol_list = source_root.resolve() / "src" / "symbol_lists.cpp"
    if not symbol_list.is_file():
        raise ValueError("N64Recomp source root does not contain src/symbol_lists.cpp")
    return set(re.findall(r'^\s*"([^"\\]+)",?\s*$', symbol_list.read_text(encoding="utf-8"), re.MULTILINE))


def render_config(
    elf: Path,
    output: Path,
    *,
    entrypoint: int | None = None,
    manual_entry: tuple[str, str, int, int] | None = None,
    function_sizes: tuple[tuple[str, int], ...] | list[tuple[str, int]] = (),
    stubs: tuple[str, ...] | list[str] = (),
) -> str:
    lines = ["[input]"]
    if entrypoint is not None:
        lines.append(f"entrypoint = 0x{entrypoint:08X}")
    lines.extend(
        (
            f"elf_path = {toml_string(str(elf))}",
            f"output_func_path = {toml_string(str(output))}",
            "functions_per_output_file = 1",
            "single_file_output = false",
            "use_lookup_for_all_function_calls = true",
            "strict_patch_mode = true",
            "use_mdebug = false",
            "use_absolute_symbols = false",
            "unpaired_lo16_warnings = true",
            "allow_exports = false",
        )
    )
    if manual_entry is not None:
        name, section, vram, size = manual_entry
        lines.extend(
            (
                "manual_funcs = [",
                "  { "
                f"name = {toml_string(name)}, section = {toml_string(section)}, "
                f"vram = 0x{vram:08X}, size = 0x{size:X} "
                "},",
                "]",
            )
        )
    if function_sizes:
        lines.append("function_sizes = [")
        lines.extend(
            f"  {{ name = {toml_string(name)}, size = 0x{size:X} }},"
            for name, size in function_sizes
        )
        lines.append("]")
    lines.extend(("", "[patches]", "stubs = ["))
    lines.extend(f"  {toml_string(name)}," for name in stubs)
    lines.extend(("]", "ignored = []", ""))
    return "\n".join(lines)


def run_tool(executable: Path, config: Path, cwd: Path, *, dump: bool = False) -> subprocess.CompletedProcess[str]:
    command = [str(executable), str(config)]
    if dump:
        command.append("--dump-context")
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True)


def function_metadata(elf: Path) -> tuple[dict[str, int], list[tuple[str, str, int, int]], dict[str, int]]:
    sections = parse_sections(readelf(elf, "-SW"))
    symbols = parse_symbols(readelf(elf, "-sW"))
    section_by_index = {str(section.index): section for section in sections}
    executable = [
        symbol
        for symbol in symbols
        if symbol.symbol_type == "FUNC"
        and symbol.defined
        and symbol.section in section_by_index
        and "X" in section_by_index[symbol.section].flags
    ]
    positive = [symbol for symbol in executable if symbol.size > 0]
    zero = [symbol for symbol in executable if symbol.size == 0]
    covered = [
        symbol
        for symbol in zero
        if any(
            candidate.section == symbol.section
            and candidate.value <= symbol.value < candidate.value + candidate.size
            for candidate in positive
        )
    ]
    uncovered = [symbol for symbol in zero if symbol not in covered]
    starts_by_section: dict[str, list[int]] = {}
    for symbol in executable:
        starts_by_section.setdefault(symbol.section, []).append(symbol.value)
    for section_index, values in starts_by_section.items():
        section = section_by_index[section_index]
        values.append(section.address + section.size)
        starts_by_section[section_index] = sorted(set(values))

    inferred: list[tuple[str, str, int, int]] = []
    for symbol in uncovered:
        following = next(
            (value for value in starts_by_section[symbol.section] if value > symbol.value),
            None,
        )
        if following is None or (following - symbol.value) % 4:
            continue
        inferred.append((symbol.name, symbol.section, symbol.value, following - symbol.value))

    data_candidates = [
        symbol
        for symbol in symbols
        if symbol.symbol_type in {"OBJECT", "NOTYPE"} and symbol.defined
    ]
    valid_data = [symbol for symbol in data_candidates if symbol.section in section_by_index]
    invalid_data = [
        symbol
        for symbol in valid_data
        if not (
            section_by_index[symbol.section].address <= symbol.value
            and symbol.value + symbol.size
            <= section_by_index[symbol.section].address + section_by_index[symbol.section].size
        )
    ]
    data_locations: dict[str, set[tuple[str, int]]] = collections.defaultdict(set)
    for symbol in valid_data:
        data_locations[symbol.name].add((symbol.section, symbol.value))
    relocation_sections = [
        section for section in sections if section.section_type in {"REL", "RELA"}
    ]
    metadata = {
        "executable_function_symbol_count": len(executable),
        "sized_function_count": len(positive),
        "zero_size_function_symbol_count": len(zero),
        "covered_zero_size_alias_count": len(covered),
        "uncovered_zero_size_function_count": len(uncovered),
        "inferred_function_size_count": len(inferred),
        "unaligned_function_address_count": sum(symbol.value % 4 != 0 for symbol in executable),
        "unaligned_function_size_count": sum(symbol.size % 4 != 0 for symbol in executable),
        "candidate_data_symbol_count": len(data_candidates),
        "valid_section_data_symbol_count": len(valid_data),
        "invalid_section_range_data_symbol_count": len(invalid_data),
        "zero_size_data_symbol_count": sum(symbol.size == 0 for symbol in data_candidates),
        "conflicting_data_symbol_name_count": sum(
            len(locations) > 1 for locations in data_locations.values()
        ),
        "standard_elf_relocation_section_count": len(relocation_sections),
        "standard_elf_relocation_entry_count": sum(
            section.size // section.entry_size
            for section in relocation_sections
            if section.entry_size
        ),
    }
    data_detail = {
        "absolute_or_special_data_symbol_count": len(data_candidates) - len(valid_data),
        "invalid_data_all_zero_size": all(symbol.size == 0 for symbol in invalid_data),
    }
    return metadata, inferred, data_detail


def locate_transfer_functions(
    context: dict[str, Any], rom: bytes
) -> tuple[list[str], int, list[str], int, list[dict[str, object]]]:
    placeholder_names: list[str] = []
    placeholder_site_count = 0
    indirect_names: list[str] = []
    indirect_site_count = 0
    details: list[dict[str, object]] = []
    for section in context.get("section", []):
        section_rom = int(section["rom"])
        section_vram = int(section["vram"])
        section_name = str(section["name"])
        for function in section.get("functions", []):
            size = int(function["size"])
            vram = int(function["vram"])
            rom_offset = section_rom + vram - section_vram
            body = rom[rom_offset : rom_offset + size]
            if len(body) != size or size % 4:
                raise ValueError("function body is outside the supported ROM")
            words = struct.unpack(f">{size // 4}I", body)
            placeholders = words.count(PLACEHOLDER_JAL)
            indirects = sum(
                1
                for word in words
                if word >> 26 == 0
                and (
                    ((word & 0x3F) == 8 and ((word >> 21) & 0x1F) != 31)
                    or (word & 0x3F) == 9
                )
            )
            name = str(function["name"])
            if placeholders or indirects:
                if placeholders:
                    placeholder_names.append(name)
                    placeholder_site_count += placeholders
                if indirects:
                    indirect_names.append(name)
                    indirect_site_count += indirects
                details.append(
                    {
                        "name": name,
                        "section": section_name,
                        "vram": vram,
                        "placeholder_sites": placeholders,
                        "indirect_transfer_sites": indirects,
                    }
                )
    return (
        placeholder_names,
        placeholder_site_count,
        indirect_names,
        indirect_site_count,
        details,
    )


def select_manual_entry_section(
    context: dict[str, Any], entrypoint: int, entry_size: int
) -> dict[str, Any]:
    """Select the one executable section containing a private manual entry range."""
    sections = context.get("section")
    if not isinstance(sections, list):
        raise ValueError("N64Recomp context has no executable section inventory")
    for section in sections:
        if not isinstance(section, dict):
            continue
        try:
            section_start = int(section["vram"])
            section_size = int(section["size"])
        except (KeyError, TypeError, ValueError):
            continue
        if (
            section_start <= entrypoint
            and entrypoint + entry_size <= section_start + section_size
        ):
            return section
    raise ValueError("private manual entry range is outside every executable section")


def validate_public_cpu_aggregate(value: object) -> None:
    """Fail closed if the CPU probe grows an unreviewed public output field."""

    def exact(candidate: object, keys: set[str], location: str) -> dict[str, Any]:
        if not isinstance(candidate, dict) or set(candidate) != keys:
            raise ValueError(f"{location} has missing or unreviewed public fields")
        return candidate

    aggregate = exact(
        value,
        {
            "schema_version",
            "kind",
            "privacy",
            "input_verification",
            "elf_sha256",
            "boot_entry_probe",
            "metadata",
            "recompilation",
            "coverage_gate",
        },
        "$",
    )
    input_verification = exact(
        aggregate["input_verification"],
        {
            "supported_rom_size",
            "supported_rom_sha1",
            "elf_sha256",
            "n64recomp_source_commit",
            "n64recomp_executable_sha256",
            "n64recomp_identity_methods",
        },
        "$.input_verification",
    )
    boot = exact(
        aggregate["boot_entry_probe"],
        {
            "private_input_supplied",
            "elf_header_entry_present",
            "n64recomp_direct_probe_passed",
            "manual_fallback_generated",
        },
        "$.boot_entry_probe",
    )
    metadata = exact(
        aggregate["metadata"],
        {
            "executable_function_symbol_count",
            "sized_function_count",
            "zero_size_function_symbol_count",
            "covered_zero_size_alias_count",
            "uncovered_zero_size_function_count",
            "inferred_function_size_count",
            "unaligned_function_address_count",
            "unaligned_function_size_count",
            "candidate_data_symbol_count",
            "valid_section_data_symbol_count",
            "invalid_section_range_data_symbol_count",
            "zero_size_data_symbol_count",
            "conflicting_data_symbol_name_count",
            "standard_elf_relocation_section_count",
            "standard_elf_relocation_entry_count",
            "absolute_or_special_data_symbol_count",
            "invalid_data_all_zero_size",
            "dump_executable_section_count",
            "dump_function_count",
            "dump_data_section_count",
            "dump_data_symbol_count",
        },
        "$.metadata",
    )
    recompilation = exact(
        aggregate["recompilation"],
        {
            "placeholder_jal_site_count",
            "placeholder_function_count",
            "indirect_transfer_site_count",
            "indirect_transfer_function_count",
            "transfer_inventory_sha256",
            "additional_failed_function_count",
            "additional_failure_kind_counts",
            "unavailable_stub_count",
            "excluded_n64recomp_builtin_count",
            "total_stubbed_function_count",
            "final_probe_passed",
            "final_probe_returncode",
            "final_probe_crashed",
            "generated_c_file_count",
        },
        "$.recompilation",
    )
    failure_counts = exact(
        recompilation["additional_failure_kind_counts"],
        {"missing-direct-call-target", "out-of-range-branch"},
        "$.recompilation.additional_failure_kind_counts",
    )
    coverage = exact(
        aggregate["coverage_gate"],
        {
            "id",
            "context_executable_sections_inventoried",
            "all_executable_sections_individually_attempted",
            "all_candidate_functions_individually_classified",
            "status",
            "reason",
        },
        "$.coverage_gate",
    )
    if aggregate["schema_version"] != 1:
        raise ValueError("public CPU aggregate schema version is unsupported")
    if aggregate["kind"] != "jfg-phase3-cpu-probe-aggregate":
        raise ValueError("public CPU aggregate kind is unsupported")
    if aggregate["privacy"] != "public-safe-aggregate-only":
        raise ValueError("public CPU aggregate privacy marker is unsupported")
    if aggregate["elf_sha256"] != input_verification["elf_sha256"]:
        raise ValueError("public CPU aggregate ELF identities differ")
    expected_identities = {
        "supported_rom_size": EXPECTED_ROM_SIZE,
        "supported_rom_sha1": EXPECTED_ROM_SHA1,
        "elf_sha256": EXPECTED_ELF_SHA256,
        "n64recomp_executable_sha256": EXPECTED_N64RECOMP_SHA256,
    }
    for field, expected in expected_identities.items():
        if input_verification[field] != expected:
            raise ValueError(f"public CPU aggregate {field} differs from its pin")
    if input_verification["n64recomp_source_commit"] != EXPECTED_N64RECOMP_COMMIT:
        raise ValueError("public CPU aggregate source pin differs")
    if input_verification["n64recomp_identity_methods"] != [
        "source-commit",
        "executable-sha256",
    ]:
        raise ValueError("public CPU aggregate identity methods are incomplete")
    if sum(failure_counts.values()) != recompilation["additional_failed_function_count"]:
        raise ValueError("public CPU diagnostic counts are inconsistent")
    if coverage["status"] != "open":
        raise ValueError("public CPU coverage gate must remain open")
    if boot != {
        "private_input_supplied": True,
        "elf_header_entry_present": False,
        "n64recomp_direct_probe_passed": False,
        "manual_fallback_generated": True,
    }:
        raise ValueError("public CPU boot probe differs from the current-pin baseline")
    if coverage != {
        "id": "G2",
        "context_executable_sections_inventoried": metadata[
            "dump_executable_section_count"
        ],
        "all_executable_sections_individually_attempted": False,
        "all_candidate_functions_individually_classified": False,
        "status": "open",
        "reason": "conservative-prestub-partition-is-not-individual-coverage",
    }:
        raise ValueError("public CPU coverage gate differs from the conservative baseline")
    if SHA256_RE.fullmatch(str(recompilation["transfer_inventory_sha256"])) is None:
        raise ValueError("public CPU transfer inventory digest is malformed")
    for field, child in boot.items():
        if type(child) is not bool:
            raise ValueError(f"$.boot_entry_probe.{field} must be boolean")
    for field in (
        "all_executable_sections_individually_attempted",
        "all_candidate_functions_individually_classified",
    ):
        if type(coverage[field]) is not bool:
            raise ValueError(f"$.coverage_gate.{field} must be boolean")
    for field in ("final_probe_passed", "final_probe_crashed"):
        if type(recompilation[field]) is not bool:
            raise ValueError(f"$.recompilation.{field} must be boolean")
    if (
        recompilation["final_probe_passed"] is not True
        or recompilation["final_probe_returncode"] != 0
        or recompilation["final_probe_crashed"] is not False
    ):
        raise ValueError("public CPU conservative probe did not finish successfully")
    integer_groups = (
        (
            input_verification,
            {"supported_rom_size"},
            "$.input_verification",
        ),
        (
            metadata,
            set(metadata) - {"invalid_data_all_zero_size"},
            "$.metadata",
        ),
        (
            recompilation,
            set(recompilation)
            - {
                "transfer_inventory_sha256",
                "additional_failure_kind_counts",
                "final_probe_passed",
                "final_probe_crashed",
            },
            "$.recompilation",
        ),
        (
            failure_counts,
            set(failure_counts),
            "$.recompilation.additional_failure_kind_counts",
        ),
        (
            coverage,
            {"context_executable_sections_inventoried"},
            "$.coverage_gate",
        ),
    )
    for container, fields, location in integer_groups:
        for field in fields:
            child = container[field]
            if type(child) is not int:
                raise ValueError(f"{location}.{field} must be an integer")
            if field != "final_probe_returncode" and child < 0:
                raise ValueError(f"{location}.{field} must be non-negative")
            if field != "final_probe_returncode" and child > EXPECTED_ROM_SIZE:
                raise ValueError(f"{location}.{field} exceeds the public aggregate limit")
    if type(metadata["invalid_data_all_zero_size"]) is not bool:
        raise ValueError("public CPU data-range verdict must be boolean")
    number_errors = validate_canonical_json_numbers(aggregate)
    privacy_errors = validate_public_safe(aggregate, "public-cpu-aggregate")
    if number_errors or privacy_errors:
        raise ValueError("; ".join([*number_errors, *privacy_errors]))


def tracked_cpu_fragment(value: object) -> dict[str, object]:
    """Transform a closed CPU probe aggregate into its tracked evidence fields."""
    validate_public_cpu_aggregate(value)
    assert isinstance(value, dict)
    verification = value["input_verification"]
    boot = value["boot_entry_probe"]
    metadata = value["metadata"]
    recompilation = value["recompilation"]
    assert isinstance(verification, dict)
    assert isinstance(boot, dict)
    assert isinstance(metadata, dict)
    assert isinstance(recompilation, dict)
    failure_counts = recompilation["additional_failure_kind_counts"]
    assert isinstance(failure_counts, dict)
    return {
        "inputs": {
            "supported_rom_sha1": verification["supported_rom_sha1"],
            "supported_rom_size": verification["supported_rom_size"],
            "elf_sha256": verification["elf_sha256"],
            "n64recomp_executable_sha256": verification[
                "n64recomp_executable_sha256"
            ],
            "n64recomp_identity_methods": verification["n64recomp_identity_methods"],
        },
        "cpu": {
            "boot_entry_probe": {
                "private_input_supplied": boot["private_input_supplied"],
                "elf_header_entry_present": boot["elf_header_entry_present"],
                "direct_n64recomp_probe_passed": boot[
                    "n64recomp_direct_probe_passed"
                ],
                "manual_fallback_generated": boot["manual_fallback_generated"],
            },
            "functions": {
                "executable_symbol_count": metadata[
                    "executable_function_symbol_count"
                ],
                "sized_count": metadata["sized_function_count"],
                "zero_size_count": metadata["zero_size_function_symbol_count"],
                "covered_zero_size_alias_count": metadata[
                    "covered_zero_size_alias_count"
                ],
                "uncovered_zero_size_count": metadata[
                    "uncovered_zero_size_function_count"
                ],
                "inferred_size_override_count": metadata[
                    "inferred_function_size_count"
                ],
                "unaligned_address_count": metadata[
                    "unaligned_function_address_count"
                ],
                "unaligned_size_count": metadata["unaligned_function_size_count"],
            },
            "data": {
                "candidate_symbol_count": metadata["candidate_data_symbol_count"],
                "valid_section_symbol_count": metadata[
                    "valid_section_data_symbol_count"
                ],
                "absolute_or_special_symbol_count": metadata[
                    "absolute_or_special_data_symbol_count"
                ],
                "zero_size_symbol_count": metadata["zero_size_data_symbol_count"],
                "invalid_section_range_count": metadata[
                    "invalid_section_range_data_symbol_count"
                ],
                "invalid_ranges_all_zero_size": metadata[
                    "invalid_data_all_zero_size"
                ],
                "conflicting_name_count": metadata[
                    "conflicting_data_symbol_name_count"
                ],
                "standard_elf_relocation_section_count": metadata[
                    "standard_elf_relocation_section_count"
                ],
                "standard_elf_relocation_entry_count": metadata[
                    "standard_elf_relocation_entry_count"
                ],
            },
            "context_dump": {
                "executable_section_count": metadata[
                    "dump_executable_section_count"
                ],
                "function_count_after_size_overrides": metadata[
                    "dump_function_count"
                ],
                "data_section_count": metadata["dump_data_section_count"],
                "data_symbol_count_after_size_overrides": metadata[
                    "dump_data_symbol_count"
                ],
            },
            "coverage_gate": value["coverage_gate"],
            "conservative_generation_probe": {
                "placeholder_jal_site_count": recompilation[
                    "placeholder_jal_site_count"
                ],
                "placeholder_function_count": recompilation[
                    "placeholder_function_count"
                ],
                "indirect_transfer_candidate_site_count": recompilation[
                    "indirect_transfer_site_count"
                ],
                "indirect_transfer_candidate_function_count": recompilation[
                    "indirect_transfer_function_count"
                ],
                "additional_missing_direct_target_function_count": failure_counts[
                    "missing-direct-call-target"
                ],
                "additional_out_of_range_branch_function_count": failure_counts[
                    "out-of-range-branch"
                ],
                "unavailable_stub_count": recompilation["unavailable_stub_count"],
                "excluded_n64recomp_builtin_count": recompilation[
                    "excluded_n64recomp_builtin_count"
                ],
                "total_stubbed_function_count": recompilation[
                    "total_stubbed_function_count"
                ],
                "generated_c_file_count": recompilation["generated_c_file_count"],
                "final_probe_passed": recompilation["final_probe_passed"],
                "transfer_inventory_sha256": recompilation[
                    "transfer_inventory_sha256"
                ],
            },
        },
    }


def verify_tracked_cpu_fragment(value: object, evidence: object) -> None:
    """Require a private pinned CPU run to match its tracked aggregates exactly."""
    if not isinstance(evidence, dict):
        raise ValueError("tracked Phase 3 evidence is not an object")
    try:
        if __package__:
            from .analyze_phase3_overlays import validate_phase3_evidence
        else:
            from analyze_phase3_overlays import validate_phase3_evidence
        validate_phase3_evidence(evidence)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            "tracked Phase 3 evidence does not match the reviewed canonical lock"
        ) from error
    tracked_inputs = evidence.get("inputs")
    tracked_cpu = evidence.get("cpu")
    if not isinstance(tracked_inputs, dict) or not isinstance(tracked_cpu, dict):
        raise ValueError("tracked Phase 3 evidence has no CPU aggregate")
    inputs = dict(tracked_inputs)
    inputs.pop("initial_config_pinned_parse_passed", None)
    cpu = dict(tracked_cpu)
    cpu.pop("unbounded_jump_table_probe", None)
    if tracked_cpu_fragment(value) != {"inputs": inputs, "cpu": cpu}:
        raise ValueError("private CPU probe differs from tracked aggregate evidence")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n64recomp", required=True, type=Path)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--n64recomp-source-root", required=True, type=Path)
    parser.add_argument("--expected-n64recomp-sha256", required=True)
    parser.add_argument(
        "--entrypoint",
        required=True,
        type=lambda value: int(value, 0),
        help=(
            "private base-0 integer entrypoint; must be word-aligned and fit "
            "with --manual-entry-size in one executable section; never aggregated"
        ),
    )
    parser.add_argument(
        "--manual-entry-size",
        required=True,
        type=lambda value: int(value, 0),
        help=(
            "private base-0 positive byte extent; must be word-aligned and remain "
            "in the entrypoint section; never aggregated"
        ),
    )
    parser.add_argument("--max-additional-stubs", type=int, default=128)
    parser.add_argument(
        "--tracked-evidence",
        required=True,
        type=Path,
        help="fail if the private CPU aggregate differs from tracked Phase 3 evidence",
    )
    arguments = parser.parse_args()

    executable = arguments.n64recomp.resolve()
    elf = arguments.elf.resolve()
    rom_path = arguments.rom.resolve()
    work = arguments.work_dir.resolve()
    if (
        arguments.entrypoint < 0
        or arguments.entrypoint > 0xFFFFFFFF
        or arguments.entrypoint % 4
        or arguments.manual_entry_size <= 0
        or arguments.manual_entry_size % 4
        or arguments.entrypoint + arguments.manual_entry_size > 0x1_0000_0000
    ):
        print("Private entrypoint data is not a valid aligned 32-bit range.", file=sys.stderr)
        return 2
    if not executable.is_file() or not elf.is_file() or not rom_path.is_file():
        print("Phase 3 CPU probe input is missing.", file=sys.stderr)
        return 2
    try:
        input_verification = verify_probe_inputs(
            executable,
            elf,
            rom_path,
            arguments.n64recomp_source_root,
            arguments.expected_n64recomp_sha256,
        )
        verify_private_work_directory(work)
    except (OSError, ValueError) as error:
        print(f"Phase 3 CPU probe rejected its inputs: {error}", file=sys.stderr)
        return 2
    work.mkdir(parents=True, exist_ok=True)
    generated = work / "generated"
    config = work / "probe.toml"

    metadata, inferred, data_detail = function_metadata(elf)
    elf_header = parse_header(readelf(elf, "-h"))
    function_sizes = [(name, size) for name, _section, _vram, size in inferred]

    config.write_text(
        render_config(elf, generated, entrypoint=arguments.entrypoint),
        encoding="utf-8",
    )
    entry_probe = run_tool(executable, config, work, dump=True)

    config.write_text(
        render_config(elf, generated, function_sizes=function_sizes),
        encoding="utf-8",
    )
    dump_probe = run_tool(executable, config, work, dump=True)
    if dump_probe.returncode != 0:
        print("N64Recomp could not dump the ELF context.", file=sys.stderr)
        return 1
    context = tomllib.loads((work / "dump.toml").read_text(encoding="utf-8"))
    data_context = tomllib.loads((work / "data_dump.toml").read_text(encoding="utf-8"))
    rom = rom_path.read_bytes()
    (
        placeholder_names,
        placeholder_sites,
        indirect_names,
        indirect_sites,
        transfer_details,
    ) = locate_transfer_functions(context, rom)

    entry_size = arguments.manual_entry_size
    try:
        entry_section = select_manual_entry_section(
            context, arguments.entrypoint, entry_size
        )
    except ValueError as error:
        print(f"Phase 3 CPU probe rejected private entry data: {error}", file=sys.stderr)
        return 2
    manual_entry = (
        "jfg_boot_entry",
        str(entry_section["name"]),
        arguments.entrypoint,
        entry_size,
    )

    builtin_names = n64recomp_builtin_names(arguments.n64recomp_source_root)
    stub_names = [
        name
        for name in dict.fromkeys([*placeholder_names, *indirect_names])
        if name not in builtin_names
    ]
    additional: list[dict[str, str]] = []
    unavailable_stubs: list[str] = []
    final_probe: subprocess.CompletedProcess[str] | None = None
    for _attempt in range(arguments.max_additional_stubs + len(stub_names) + 1):
        if generated.exists():
            shutil.rmtree(generated)
        config.write_text(
            render_config(
                elf,
                generated,
                manual_entry=manual_entry,
                function_sizes=function_sizes,
                stubs=sorted(stub_names),
            ),
            encoding="utf-8",
        )
        final_probe = run_tool(executable, config, work)
        if final_probe.returncode == 0:
            break
        diagnostic = final_probe.stdout + final_probe.stderr
        missing_stub = MISSING_STUB_RE.search(diagnostic)
        if missing_stub is not None and missing_stub.group(1) in stub_names:
            unavailable_stubs.append(missing_stub.group(1))
            stub_names.remove(missing_stub.group(1))
            continue
        match = FAILED_FUNCTION_RE.search(diagnostic)
        if (
            match is None
            or match.group(1) in stub_names
            or len(additional) >= arguments.max_additional_stubs
        ):
            break
        failed_name = match.group(1)
        stub_names.append(failed_name)
        additional.append(
            {
                "name": failed_name,
                "kind": diagnostic_kind(diagnostic),
                "diagnostic_sha256": hashlib.sha256(diagnostic.encode("utf-8")).hexdigest(),
            }
        )
    assert final_probe is not None

    generated_sources = list(generated.glob("*.c")) if generated.exists() else []
    manual_generated = any(
        "jfg_boot_entry" in source.read_text(encoding="utf-8")
        for source in generated_sources
    )
    safe = {
        "schema_version": 1,
        "kind": "jfg-phase3-cpu-probe-aggregate",
        "privacy": "public-safe-aggregate-only",
        "input_verification": input_verification,
        "elf_sha256": digest(elf),
        "boot_entry_probe": {
            "private_input_supplied": True,
            "elf_header_entry_present": elf_header["entry_point"] != 0,
            "n64recomp_direct_probe_passed": entry_probe.returncode == 0,
            "manual_fallback_generated": manual_generated,
        },
        "metadata": {
            **metadata,
            **data_detail,
            "dump_executable_section_count": len(context.get("section", [])),
            "dump_function_count": sum(
                len(section.get("functions", [])) for section in context.get("section", [])
            ),
            "dump_data_section_count": len(data_context.get("section", [])),
            "dump_data_symbol_count": sum(
                len(section.get("symbols", []))
                for section in data_context.get("section", [])
            ),
        },
        "recompilation": {
            "placeholder_jal_site_count": placeholder_sites,
            "placeholder_function_count": len(placeholder_names),
            "indirect_transfer_site_count": indirect_sites,
            "indirect_transfer_function_count": len(indirect_names),
            "transfer_inventory_sha256": canonical_hash(transfer_details),
            "additional_failed_function_count": len(additional),
            "additional_failure_kind_counts": dict(
                sorted(collections.Counter(item["kind"] for item in additional).items())
            ),
            "unavailable_stub_count": len(unavailable_stubs),
            "excluded_n64recomp_builtin_count": len(
                set([*placeholder_names, *indirect_names]) & builtin_names
            ),
            "total_stubbed_function_count": len(stub_names),
            "final_probe_passed": final_probe.returncode == 0,
            "final_probe_returncode": final_probe.returncode,
            "final_probe_crashed": final_probe.returncode < 0,
            "generated_c_file_count": len(generated_sources),
        },
        "coverage_gate": {
            "id": "G2",
            "context_executable_sections_inventoried": len(context.get("section", [])),
            "all_executable_sections_individually_attempted": False,
            "all_candidate_functions_individually_classified": False,
            "status": "open",
            "reason": "conservative-prestub-partition-is-not-individual-coverage",
        },
    }
    try:
        validate_public_cpu_aggregate(safe)
        tracked_evidence = json.loads(
            arguments.tracked_evidence.read_text(encoding="utf-8")
        )
        verify_tracked_cpu_fragment(safe, tracked_evidence)
    except (OSError, ValueError) as error:
        print(f"Phase 3 CPU aggregate validation failed: {error}", file=sys.stderr)
        return 1
    detailed = {
        "safe": safe,
        "inferred_function_sizes": [
            {"name": name, "section": section, "vram": vram, "size": size}
            for name, section, vram, size in inferred
        ],
        "transfer_functions": transfer_details,
        "additional_failed_functions": additional,
        "unavailable_stubs": unavailable_stubs,
        "final_stdout": final_probe.stdout,
        "final_stderr": final_probe.stderr,
    }
    (work / "cpu-probe-detailed.json").write_text(
        json.dumps(detailed, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    rendered = json.dumps(safe, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if final_probe.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
