"""Compile exact private oracle Count/ERET bodies, controls and observer.

Surrounding jump/interrupt/device functions are controlled stubs. These tests
qualify hook ordering and arithmetic, not whole-core or game non-perturbation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from scripts import phase9_oracle_cpu_boundaries

ROOT = Path(__file__).resolve().parents[1]


def body(path, marker):
    source = path.read_text()
    if source.count(marker) != 1:
        raise ValueError("ambiguous source function")
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return source[start:end+1] + "\n"
    raise ValueError("unterminated source function")


def run(output, control, observed):
    output = output.resolve()
    control, observed = control.resolve(strict=True), observed.resolve(strict=True)
    if output.exists() or not output.is_relative_to(ROOT / "tools/private"):
        raise ValueError("use a new private output directory")
    output.mkdir()
    files = [ROOT / "tests/oracle_cpu_boundary_tests.c", ROOT / "scripts/oracle_cpu_boundaries.c",
             ROOT / "scripts/oracle_cpu_boundaries.h", ROOT / "include/jfg/boot/device_event_probe.h", Path(__file__),
             ROOT / "scripts/phase9_oracle_cpu_boundaries.py"]
    files += [root / "src/r4300" / name for root in (control, observed)
              for name in ("r4300.c", "interpreter_tlb.def")]
    def pins(): return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    before = pins()
    commands = []
    def command(argv):
        argv = list(map(str, argv))
        environment = {k:v for k,v in os.environ.items() if not k.upper().startswith("JFG_")}
        result = subprocess.run(argv, capture_output=True, text=True, timeout=180, env=environment)
        index = len(commands)
        (output / f"command-{index}.stdout").write_text(result.stdout)
        (output / f"command-{index}.stderr").write_text(result.stderr)
        commands.append({"argv": argv, "exit_code": result.returncode})
        if result.returncode: raise ValueError(f"command {index} failed: {result.stderr[-2000:]}")
        return result.stdout
    try:
        outputs = []
        for name, source, mode in (("baseline", control, "disabled"), ("control", observed, "disabled"),
                                   ("observed", observed, "observed")):
            generated = output / name; generated.mkdir()
            for filename, original, marker in (("oracle_count_body.inc", "r4300.c", "void update_count(void)"),
                    ("oracle_eret_body.inc", "interpreter_tlb.def", "DECLARE_INSTRUCTION(ERET)")):
                (generated / filename).write_text(body(source / "src/r4300" / original, marker))
            binary = generated / "test"
            command(["gcc", "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-O1", "-Wall", "-Wextra", "-Werror",
                     "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer",
                     "-I", ROOT / "include", "-I", ROOT / "scripts", "-I", generated,
                     ROOT / "tests/oracle_cpu_boundary_tests.c", "-o", binary])
            outputs.append(command([binary, generated, mode]))
        if len(set(outputs)) != 1 or not outputs[0].startswith("passed\t12\t"):
            raise ValueError("compiled controls and observer differ")
        roundtrip = phase9_oracle_cpu_boundaries.summary(output / "observed/cpu-boundaries.tsv", {"update": 1})
        if not roundtrip["complete"] or roundtrip["eret_events"] != 2 or set(roundtrip["count_reasons"]) != phase9_oracle_cpu_boundaries.REASONS:
            raise ValueError("compiled observer/reader roundtrip differs")
        for mode in ("unobserved", "budget", "bad-core", "bad-eret"):
            directory = output / mode; directory.mkdir()
            command([output / "observed/test", directory, mode])
            trace = directory / "cpu-boundaries.tsv"
            if trace.exists() and "result\ttrue\t" in trace.read_text():
                raise ValueError("failed observation has a complete footer")
        if before != pins(): raise ValueError("source changed during proof")
        report = {"kind": "jfg-oracle-cpu-boundary-proof", "complete": True, "passed": True,
                  "cases": 12, "rejections": 4, "sanitizers": ["address", "undefined"],
                  "roundtrip": roundtrip,
                  "inputs": before, "commands": commands, "game_nonperturbation_qualified": False,
                  "global_clock_alignment_validated": False, "retirement_validated": False}
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        return report
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        (output / "failure.json").write_text(json.dumps({"complete": False, "error": str(error),
                                                       "commands": commands}, indent=2) + "\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--observed", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output, args.control, args.observed)
    print(json.dumps({k:v for k,v in result.items() if k not in ("inputs", "commands")}))
