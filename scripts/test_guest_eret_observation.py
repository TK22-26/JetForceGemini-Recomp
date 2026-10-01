"""Compile transport/writer controls with fatal sanitizers, then read real output.

Run under Linux/WSL. Does not qualify guest-game non-perturbation or oracle ERET.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from scripts import phase9_eret_transfers

ROOT = Path(__file__).resolve().parents[1]


def run(output):
    output = output.resolve()
    if output.exists() or not output.is_relative_to(ROOT / "tools/private"):
        raise ValueError("use a new private output directory")
    output.mkdir()
    sources = [ROOT / path for path in (
        "tests/guest_thread_transport_tests.cpp", "tests/guest_eret_observation_tests.cpp",
        "tests/eret_transfer_probe_tests.cpp", "src/boot/executor.cpp",
        "include/jfg/boot/guest_thread_transport.hpp", "include/jfg/boot/executor.hpp",
        "include/jfg/boot/eret_transfer_probe.hpp", "scripts/phase9_eret_transfers.py",
        "scripts/test_guest_eret_observation.py")]
    def pins():
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    before = pins()
    commands = []
    def command(argv):
        argv = list(map(str, argv))
        result = subprocess.run(argv, capture_output=True, text=True, timeout=180)
        index = len(commands)
        (output / f"command-{index}.stdout").write_text(result.stdout)
        (output / f"command-{index}.stderr").write_text(result.stderr)
        commands.append({"argv": argv, "exit_code": result.returncode})
        if result.returncode:
            raise ValueError(f"command {index} failed: {result.stderr[-1000:]}")
    try:
        for name in ("guest_thread_transport", "guest_eret_observation", "eret_transfer_probe"):
            binary = output / name
            extra = [ROOT / "src/boot/executor.cpp"] if name != "eret_transfer_probe" else []
            command(["g++", "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror", "-pthread",
                     "-fsanitize=address,undefined", "-fno-sanitize-recover=all", "-fno-omit-frame-pointer",
                     "-I", ROOT / "include", ROOT / f"tests/{name}_tests.cpp", *extra, "-o", binary])
            command([binary, *([output / "eret-transfers.tsv"] if name == "eret_transfer_probe" else [])])
        trace = phase9_eret_transfers.read(output / "eret-transfers.tsv", [7, 8])
        if (len(trace["rows"]) != 2 or trace["rows"][0]["r31"] != 0xffffffff80000000 or
                [row["count"] for row in trace["rows"]] != [0xfffffff0, 2] or pins() != before):
            raise ValueError("writer/reader roundtrip or source identity differs")
        report = {"kind": "jfg-eret-transport-observation", "complete": True, "passed": True,
                  "inputs": before, "commands": commands, "roundtrip": trace,
                  "sanitizers": ["address", "undefined"], "observed_control_execution_equal": True,
                  "game_nonperturbation_qualified": False, "oracle_boundary_qualified": False}
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        return report
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        (output / "failure.json").write_text(json.dumps({"complete": False, "error": str(error),
                                                       "commands": commands}, indent=2) + "\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({key: value for key, value in result.items() if key not in ("inputs", "commands", "roundtrip")}))
