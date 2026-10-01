"""Validate private original cache routines against an independent micro-ROM.

Run under Linux/WSL. Does not publish original OS bytes or claim hardware cache timing.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess

from scripts.phase9_cpu_cache_trace import CASES, parse_trace

ROOT = Path(__file__).resolve().parents[1]


def compare_cases(text, oracle):
    lines = text.splitlines()
    if len(lines) != 195 or lines[0] != "function\talignment\tlength\tinstructions\tcache_operations" or \
            lines[-1] != "passed\t193":
        raise ValueError("generated cache coverage incomplete")
    rows = list(csv.DictReader(lines[:-1], delimiter="\t"))
    mismatches = []
    for expected, row, reference in zip(CASES, rows, oracle["calls"]):
        key = tuple(int(row[name]) for name in ("function", "alignment", "length"))
        if key != expected:
            raise ValueError("generated cache cases reordered")
        instructions = int(row["instructions"])
        if instructions <= 0 or int(row["cache_operations"]) < 0:
            raise ValueError("invalid instruction observation")
        # Boundary includes the measuring MFC0 plus JAL[R] and its delay slot.
        if reference["ticks_including_boundary"] != instructions * 2 + 6:
            mismatches.append({"case": key, "native_instructions": instructions,
                               "reference_ticks": reference["ticks_including_boundary"]})
    return mismatches


def run(output, root, oracle_trace):
    output, root = output.resolve(), root.resolve(strict=True)
    oracle_trace = oracle_trace.resolve(strict=True)
    oracle = parse_trace(oracle_trace)
    if not output.is_relative_to(ROOT / "tools/private") or output.exists():
        raise ValueError("use a new private output directory")
    sources = [root / f"baseline/fn_000_{index}_recomp.c" for index in (1558, 1559, 1561, 1566)]
    for source, pc in zip(sources, ("0x80098050", "0x800980d0", "0x800982b0", "0x80098a10")):
        text = source.read_text()
        if pc not in text or "jfg_phase9_execution_probe" not in text:
            raise ValueError("not an observed supported-ROM cache routine")
    output.mkdir()
    flags = ["-O1", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    objects = []
    for index, source in enumerate(sources):
        obj = output / f"cache{index}.o"
        subprocess.run(list(map(str, ["gcc", "-std=c11", *flags, "-I", root / "include",
            "-I", root, "-c", source, "-o", obj])), check=True, timeout=120)
        objects.append(obj)
    subprocess.run(list(map(str, ["g++", "-std=c++20", *flags, "-I", root / "include",
        "-I", ROOT / "include", ROOT / "tests/generated_os_cache.cpp", *objects,
        "-o", output / "cache-test"])), check=True, timeout=120)
    result = subprocess.run([str(output / "cache-test")], capture_output=True, text=True, timeout=120)
    (output / "cases.tsv").write_text(result.stdout)
    (output / "stderr.log").write_text(result.stderr)
    result.check_returncode()
    mismatches = compare_cases(result.stdout, oracle)
    inputs = [*sources, root / "include/recomp.h", root / "funcs.h", oracle_trace,
              ROOT / "tests/generated_os_cache.cpp", ROOT / "include/jfg/boot/reference_cache.hpp",
              ROOT / "scripts/phase9_cpu_cache_trace.py", Path(__file__)]
    manifest = {"kind": "jfg-private-generated-os-cache", "acceptance": False,
                "sanitizers": ["address", "undefined"], "cases": 193,
                "inputs": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in inputs}, "hardware_timing_qualified": False,
                "mismatches": mismatches,
                "reference_instruction_cost_agrees": not mismatches}
    (output / "result.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if mismatches:
        raise ValueError("cache reference timing disagrees; see result.json")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--oracle-trace", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.root, args.oracle_trace)))
