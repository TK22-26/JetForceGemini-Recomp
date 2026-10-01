"""Execute the private original empty receive, including its Status helpers."""
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
    sources = [root / f"baseline/fn_000_{index}_recomp.c" for index in (1526, 1600, 1601)]
    for source, pc in zip(sources, ("0x80096910", "0x80099d40", "0x80099d60")):
        body = source.read_text()
        if pc not in body or "jfg_phase9_execution_probe" not in body:
            raise ValueError("not the supported observed original routines")
    output.mkdir()
    flags = ["-O1", "-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    objects = []
    for index, source in enumerate(sources):
        obj = output / f"receive{index}.o"
        subprocess.run(list(map(str, ["gcc", "-std=c11", *flags, "-I", root / "include",
            "-I", root, "-c", source, "-o", obj])), check=True, timeout=120)
        objects.append(obj)
    subprocess.run(list(map(str, ["g++", "-std=c++20", *flags, "-I", root / "include",
        ROOT / "tests/generated_os_empty_receive.cpp", *objects,
        "-o", output / "receive-test"])), check=True, timeout=120)
    result = subprocess.run([str(output / "receive-test")], capture_output=True, text=True, timeout=120)
    (output / "stdout.log").write_text(result.stdout)
    (output / "stderr.log").write_text(result.stderr)
    result.check_returncode()
    if result.stdout != "passed\t32\ninstructions_per_empty_receive\t40\n":
        raise ValueError("incomplete original empty-receive coverage")
    inputs = [*sources, root / "include/recomp.h", root / "funcs.h",
              ROOT / "tests/generated_os_empty_receive.cpp", Path(__file__)]
    manifest = {"kind": "jfg-private-generated-os-empty-receive", "acceptance": False,
                "sanitizers": ["address", "undefined"], "cases": 32,
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
