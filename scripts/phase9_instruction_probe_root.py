#!/usr/bin/env python3
"""Create a private, non-acceptance generated root with three guest-PC probes.

The source root is never modified. This diagnostic copy is not a normalized
product and must not be used for an acceptance or production build.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


BODY = Path("baseline/fn_000_1213_recomp.c")
PCS = (0x80074434, 0x80074440, 0x800744C8, 0x800744D4)
DECLARATION = (
    "extern void jfg_phase9_instruction_probe(uint32_t pc, uint8_t *rdram, "
    "recomp_context *ctx);\n"
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create(source: Path, output: Path) -> dict:
    source = source.resolve(strict=True)
    output = output.parent.resolve(strict=True) / output.name
    if not source.is_dir() or not (source / "sources.json").is_file() or \
            not (source / BODY).is_file():
        raise ValueError("source must be a generated root with the target body")
    if output.exists() or output.is_symlink() or source == output or source in output.parents or \
            output in source.parents:
        raise ValueError("output must be a new separate directory")
    if not output.parent.is_dir():
        raise ValueError("output parent does not exist")
    if any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("source root contains a symlink")
    original = (source / BODY).read_text(encoding="utf-8")
    if original.count('#include "funcs.h"\n') != 1 or \
            "jfg_phase9_instruction_probe" in original:
        raise ValueError("target body does not match expected uninstrumented form")
    instrumented = original.replace('#include "funcs.h"\n',
                                    '#include "funcs.h"\n' + DECLARATION, 1)
    for pc in PCS:
        marker = f"    // 0x{pc:08X}:"
        if instrumented.count(marker) != 1:
            raise ValueError(f"guest PC marker is absent or ambiguous: 0x{pc:08x}")
        instrumented = instrumented.replace(
            marker,
            f"    jfg_phase9_instruction_probe(0x{pc:08X}U, rdram, ctx);\n" + marker,
            1,
        )
    source_sha = digest(source / BODY)
    manifest_sha = digest(source / "sources.json")
    shutil.copytree(source, output)
    target = output / BODY
    target.write_text(instrumented, encoding="utf-8", newline="")
    result = {
        "kind": "jfg-phase9-diagnostic-instruction-probe-root",
        "schema": 1,
        "acceptance": False,
        "source_root": str(source),
        "source_manifest_sha256": manifest_sha,
        "source_body_sha256": source_sha,
        "instrumented_body_sha256": digest(target),
        "instrumented_guest_pcs": [f"0x{pc:08x}" for pc in PCS],
        "warning": "diagnostic only; not a normalized or parity-acceptance root",
    }
    (output / "instruction-probe-manifest.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(create(args.source, args.output), indent=2))


if __name__ == "__main__":
    main()
