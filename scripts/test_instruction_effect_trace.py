"""Sanitized bounded writer and generated-hook roundtrip, not game acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from scripts import phase9_instruction_effect_trace as reader
from scripts import test_generated_instruction_effects as generated

ROOT = Path(__file__).resolve().parents[1]


def run(output, recompiler, control_recompiler, include):
    output = output.resolve()
    recompiler, control_recompiler, include = (p.resolve(strict=True) for p in (recompiler, control_recompiler, include))
    if output.exists() or not output.is_relative_to(ROOT / "tools/private"):
        raise ValueError("use a new private instruction-effect trace proof directory")
    output.mkdir()
    inputs = [ROOT / name for name in (
        "include/jfg/boot/instruction_effect_trace.hpp", "tests/instruction_effect_trace_tests.cpp",
        "tests/instruction_effect_trace_fixture.cpp", "tests/generated_instruction_effects.cpp",
        "tests/fixtures/instruction_effects.S", "scripts/test_generated_instruction_effects.py",
        "scripts/phase9_instruction_effect_trace.py", "scripts/test_instruction_effect_trace.py")]
    inputs += [recompiler, control_recompiler, include / "recomp.h"]
    def pins(): return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    before = pins()
    receipts = []

    def command(argv, *, trace_file=None):
        argv = list(map(str, argv))
        environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("JFG_")}
        if trace_file:
            environment["JFG_EFFECT_TRACE_FIXTURE"] = str(trace_file)
        result = subprocess.run(argv, cwd=output, capture_output=True, text=True, env=environment, timeout=180)
        number = len(receipts)
        (output / f"command-{number}.stdout").write_text(result.stdout)
        (output / f"command-{number}.stderr").write_text(result.stderr)
        receipts.append({"argv": argv, "exit_code": result.returncode,
                         "trace_file": str(trace_file) if trace_file else None})
        if result.returncode:
            raise ValueError(f"instruction effect trace command {number} failed: {result.stderr[-2000:]}")
        return result.stdout

    flags = ["-O1", "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer"]
    try:
        command(["g++", "-std=c++20", *flags, "-Wall", "-Wextra", "-Werror", "-I", ROOT / "include",
                 ROOT / "tests/instruction_effect_trace_tests.cpp", "-o", output / "unit-test"])
        if command([output / "unit-test", output / "unit.bin"]) != "passed\t4\t13\n":
            raise ValueError("writer unit or rejection cases differ")
        unit = reader.summary(output / "unit.bin", 7)
        if not unit["complete"] or (unit["entries"], unit["effects"], unit["eret_transfers"]) != (2, 1, 1):
            raise ValueError("actual C++ writer did not roundtrip through the strict reader")
        unit_rows = list(reader.records(output / "unit.bin", 7))
        expected_gpr = [0] + [(index << 32) | (0x80000000 + 3 * index) for index in range(1, 32)]
        expected_gpr[2], expected_gpr[31] = 0, 0xffffffff80004000
        if unit_rows[0]["gpr"] != tuple(expected_gpr):
            raise ValueError("C++ full-register snapshot bits or ordering changed")
        expected_gpr[2] = 7
        if any(row["gpr"] != tuple(expected_gpr) for row in unit_rows[1:]):
            raise ValueError("C++ delta reconstruction changed unchanged GPRs")
        generation = output / "generation"
        compiler_proof = generated.run(generation, recompiler, control_recompiler, include)
        command(["mips-linux-gnu-objcopy", "-O", "binary", "-j", ".text", generation / "test.elf", output / "code.bin"])
        code = (output / "code.bin").read_bytes()
        if not code or len(code) % 4:
            raise ValueError("effect fixture text bytes are invalid")
        table = "struct EffectOpcode { unsigned pc, word; };\nstatic constexpr EffectOpcode effect_opcodes[] = {\n"
        table += "".join(f"{{0x{0x80001000+offset:08x}U,0x{int.from_bytes(code[offset:offset+4], 'big'):08x}U}},\n"
                         for offset in range(0, len(code), 4)) + "};\n"
        (output / "effect_opcodes.h").write_text(table)
        objects = []
        for i, source in enumerate(sorted((generation / "observed").glob("*.c"))):
            obj = output / f"generated-{i}.o"
            command(["gcc", "-std=c11", *flags, "-I", include, "-c", source, "-o", obj])
            objects.append(obj)
        expected = output / "expected.o"
        command(["g++", "-std=c++20", *flags, "-DEFFECT_HOOKS=1", "-Deffect_observe=effect_fixture_expected",
                 "-I", include, "-I", generation, "-c", ROOT / "tests/generated_instruction_effects.cpp", "-o", expected])
        binary = output / "wrapped-test"
        command(["g++", "-std=c++20", *flags, "-Wall", "-Wextra", "-Werror", "-I", include,
                 "-I", ROOT / "include", "-I", output, ROOT / "tests/instruction_effect_trace_fixture.cpp",
                 expected, *objects, "-o", binary])
        control = command([binary])
        observed = command([binary], trace_file=output / "generated.bin")
        if control != observed or not observed.endswith("passed\t12\n"):
            raise ValueError("wrapped observation changed the independently checked generated results")
        result = reader.summary(output / "generated.bin", 7)
        if not result["complete"] or result["entries"] != 75 or result["effects"] != 75 or result["eret_transfers"]:
            raise ValueError("generated trace omitted or duplicated a checked instruction")
        rows = list(reader.records(output / "generated.bin", 7))
        # The independent fixture's first instruction is addiu v0, zero, 7.
        if rows[0]["gpr"][2] != 0 or rows[1]["gpr"][2] != 7 or rows[1]["gpr"][31] != 0xffffffff80200000:
            raise ValueError("effect operand or high register bits changed in roundtrip")
        if before != pins():
            raise ValueError("instruction effect trace proof inputs changed")
        report = {"kind": "jfg-instruction-effect-trace-proof", "complete": True, "passed": True,
            "unit": unit, "rejections": 13, "generated": result, "generated_cases": compiler_proof["cases"],
            "generated_proof_sha256": hashlib.sha256((generation / "result.json").read_bytes()).hexdigest(),
            "inputs": before, "commands": receipts, "control_observed_outputs_equal": True,
            "sanitizers": ["address", "undefined"], "game_capture_qualified": False,
            "full_cpu_state_observed": False, "retirement_validated": False, "parity_verified": False}
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        return report
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        (output / "failure.json").write_text(json.dumps({"complete": False, "error": str(error), "commands": receipts}, indent=2))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    for name in ("recompiler", "control-recompiler", "include"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    report = run(args.output, args.recompiler, args.control_recompiler, args.include)
    print(json.dumps({key: value for key, value in report.items() if key not in ("inputs", "commands")}))
