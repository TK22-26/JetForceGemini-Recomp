"""Build ROM-free MIPS timing fixtures through N64Recomp; run on Linux/WSL.

Uses the generator's instruction hooks, not text rewriting of generated C.
Output is a new isolated directory; no signed game root is changed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def call(*args):
    return subprocess.run(list(map(str, args)), check=True, text=True,
                          capture_output=True, timeout=120).stdout


def run(output, recompiler, include, sanitize=False):
    output = output.resolve()
    recompiler, include = recompiler.resolve(strict=True), include.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=False)
    fixture = ROOT / "tests/fixtures/execution_clock.S"
    call("mips-linux-gnu-as", "-march=vr4300", "-32", "-o", output / "test.o", fixture)
    call("mips-linux-gnu-ld", "-T", ROOT / "tests/fixtures/execution_clock.ld",
         "-o", output / "test.elf", output / "test.o")
    disassembly = call("mips-linux-gnu-objdump", "-dz", output / "test.elf")
    functions = []
    for line in call("mips-linux-gnu-nm", "-S", output / "test.elf").splitlines():
        match = re.fullmatch(r"([0-9a-f]+) ([0-9a-f]+) T (clock_loop|clock_caller)", line)
        if match:
            functions.append((int(match[1], 16), int(match[2], 16), match[3]))
    if len(functions) != 2:
        raise ValueError("fixture symbols missing")
    config = ['[input]', 'elf_path = "test.elf"', 'output_func_path = "generated"',
              'use_mdebug = false', '[patches]']
    pcs = set()
    for start, size, name in functions:
        delay = False
        for line in disassembly.splitlines():
            match = re.match(r"\s*([0-9a-f]+):\s+([0-9a-f]{8})\s", line)
            if not match or not start <= int(match[1], 16) < start + size:
                continue
            pc, word = int(match[1], 16), int(match[2], 16)
            pcs.add(pc)
            text = ("extern void jfg_clock_before(unsigned, unsigned); "
                    f"jfg_clock_before(0x{pc:08x}U, {int(delay)}U);")
            config += ['[[patches.hook]]', f'func = "{name}"',
                       f'before_vram = 0x{pc:08x}', f'text = {json.dumps(text)}']
            opcode = word >> 26
            delay = opcode in (1, 2, 3, 4, 5, 6, 7, 20, 21, 22, 23) or \
                (opcode == 0 and word & 63 in (8, 9))
    if len(pcs) != sum(size // 4 for _, size, _ in functions):
        raise ValueError("incomplete instruction hook coverage")
    (output / "test.toml").write_text("\n".join(config) + "\n")
    call(recompiler, output / "test.toml")
    sources = [path for path in (output / "generated").glob("*.c")
               if "jfg_clock_before" in path.read_text()]
    if not sources:
        raise ValueError("generator emitted no instruction hooks")
    flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if sanitize else []
    objects = []
    for i, source in enumerate(sources):
        obj = output / f"generated-{i}.o"
        call("gcc", "-std=c11", "-O1", *flags, "-I", include, "-c", source, "-o", obj)
        objects.append(obj)
    binary = output / "clock-test"
    call("g++", "-std=c++20", "-O1", *flags, "-pthread", "-I", ROOT / "include",
         "-I", include, ROOT / "tests/generated_execution_clock.cpp",
         ROOT / "src/boot/executor.cpp", ROOT / "src/boot/thread_scheduler.cpp",
         ROOT / "src/boot/hle.cpp", *objects, "-o", binary)
    result = call(binary)
    manifest = {"kind": "jfg-generated-execution-clock-test", "acceptance": False,
                "profile": "synthetic-one-tick-per-instruction-not-hardware",
                "recompiler_sha256": hashlib.sha256(recompiler.read_bytes()).hexdigest(),
                "sanitizers": sanitize, "instruction_sites": len(pcs), "result": result.strip()}
    (output / "result.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--recompiler", type=Path, required=True)
    parser.add_argument("--include", type=Path, required=True)
    parser.add_argument("--sanitize", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.output, args.recompiler, args.include, args.sanitize)))
    except subprocess.CalledProcessError as error:
        print(error.stdout, error.stderr)
        raise
