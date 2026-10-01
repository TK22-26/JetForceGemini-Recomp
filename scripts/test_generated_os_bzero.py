"""Validate the original OS zeroing routine from a private observed US root.

Runs under Linux/WSL; publishes no original game code or ROM bytes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(output, root):
    output, root = output.resolve(), root.resolve(strict=True)
    if not output.is_relative_to(ROOT / "tools/private") or output.exists():
        raise ValueError("use a new private output directory")
    source = root / "baseline/fn_000_1562_recomp.c"
    if "0x80098360" not in source.read_text() or "jfg_phase9_execution_probe" not in source.read_text():
        raise ValueError("not the observed supported-ROM bzero routine")
    output.mkdir()
    flags = ["-O1", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    commands = [
        ["gcc", "-std=c11", *flags, "-I", root / "include", "-I", root,
         "-c", source, "-o", output / "bzero.o"],
        ["g++", "-std=c++20", *flags, "-I", root / "include",
         ROOT / "tests/generated_os_bzero.cpp", output / "bzero.o", "-o", output / "bzero-test"],
    ]
    for command in commands:
        subprocess.run(list(map(str, command)), check=True, timeout=120)
    result = subprocess.run([str(output / "bzero-test")], check=True, capture_output=True,
                            text=True, timeout=120)
    (output / "cases.tsv").write_text(result.stdout)
    if result.stdout.splitlines()[-1] != "passed\t128":
        raise ValueError("generated bzero coverage incomplete")
    inputs = [source, root / "include/recomp.h", root / "funcs.h",
              ROOT / "tests/generated_os_bzero.cpp", Path(__file__)]
    manifest = {"kind": "jfg-private-generated-os-bzero", "acceptance": False,
                "sanitizers": ["address", "undefined"], "cases": 128,
                "inputs": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in inputs}, "hardware_timing_qualified": False}
    (output / "result.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.root)))
