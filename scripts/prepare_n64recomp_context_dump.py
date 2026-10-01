#!/usr/bin/env python3
"""Prepare the deterministic private ELF context-dump configuration.

This helper is intentionally narrow: it derives only the zero-size function
overrides needed for N64Recomp's ``--dump-context`` mode.  The resulting TOML
contains private symbol coordinates and must remain in an ignored work root.
Standard output contains aggregate counts only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from .probe_n64recomp_cpu import (
        function_metadata,
        render_config,
        verify_private_work_directory,
    )
    from .validate_elf import parse_header, readelf
except ImportError:  # Direct script execution.
    from probe_n64recomp_cpu import (
        function_metadata,
        render_config,
        verify_private_work_directory,
    )
    from validate_elf import parse_header, readelf


def _regular_file(path: Path, label: str) -> Path:
    if path.is_symlink():
        raise ValueError(f"{label} must be a regular non-symlink file")
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"{label} must be a regular non-symlink file")
    return resolved


def _new_private_output(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.exists() or resolved.is_symlink():
        raise ValueError("output config must be a new file")
    parent = resolved.parent
    if not parent.is_dir() or parent.is_symlink():
        raise ValueError("output config parent must be an existing regular directory")
    return resolved


def build_context_dump_config(elf: Path, generated_output: Path) -> tuple[str, dict[str, int]]:
    """Return the exact context-dump TOML and public-safe derivation counts."""
    header = parse_header(readelf(elf, "-h"))
    if (
        header.get("class") != "ELF32"
        or header.get("endianness") != "big"
        or header.get("machine") != "MIPS"
        or header.get("type") != "EXEC"
    ):
        raise ValueError("input is not the required ELF32 big-endian MIPS executable")

    metadata, inferred, _data_detail = function_metadata(elf)
    function_sizes = [(name, size) for name, _section, _vram, size in inferred]
    rendered = render_config(
        elf,
        generated_output.resolve(),
        function_sizes=function_sizes,
    )
    counts = {
        "executable_function_symbols": int(metadata["executable_function_symbol_count"]),
        "inferred_size_overrides": len(function_sizes),
        "uncovered_zero_size_functions": int(metadata["uncovered_zero_size_function_count"]),
    }
    if counts["inferred_size_overrides"] != counts["uncovered_zero_size_functions"]:
        raise ValueError("ELF zero-size function derivation did not close")
    return rendered, counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--generated-output", required=True, type=Path)
    parser.add_argument("--output-config", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        elf = _regular_file(arguments.elf, "input ELF")
        output = _new_private_output(arguments.output_config)
        verify_private_work_directory(output.parent)
        verify_private_work_directory(arguments.generated_output.resolve().parent)
        rendered, counts = build_context_dump_config(elf, arguments.generated_output)
        output.write_text(rendered, encoding="utf-8", newline="\n")
    except (KeyError, OSError, ValueError) as error:
        print(f"Context-dump preparation rejected its inputs: {error}", file=sys.stderr)
        return 2
    print(json.dumps(counts, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
