"""Execute the native Count-accounting block against independent branch probes.

The instruction stream/control decisions come from the independently authored
branch microtest; the accounting statements are extracted unchanged from the
candidate native source. This tests the qualified Mupen profile, not hardware
timing or the cause of a game-state divergence. The checker belongs outside a
repair worker's writable scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.phase9_cpu_branch_trace import parse_trace


def extract(source: str) -> str:
    start = "const auto previous_primary = state.guest_last_word >> 26U;"
    stop = "mmio.guest_count = state.cpu_count;"
    if source.count(start) != 1 or source.count(stop) != 1:
        raise ValueError("native Count-accounting extraction anchors changed")
    block = source[source.index(start):source.index(stop)]
    if not 1 <= len(block) <= 3000 or "state.cpu_count" not in block:
        raise ValueError("native Count-accounting block is absent or excessive")
    return block


def program(block: str) -> str:
    return r'''
#include <cstdint>
#include <cstdio>
#include <initializer_list>
struct State {
    std::uint64_t cpu_count = 0;
    std::uint32_t guest_last_pc = 0, guest_last_word = 0;
};
static void tick(State &state, std::uint32_t pc, std::uint32_t word) {
''' + block + r'''
    state.guest_last_pc = pc;
    state.guest_last_word = word;
}
int main() {
    // BEQL, BNEL, BLEZL, BGTZL, BLTZL, BGEZL, BEQ. Branch target is PC+8.
    constexpr std::uint32_t branches[] = {
        0x51a00001U, 0x55a00001U, 0x59a00001U, 0x5da00001U,
        0x05a20001U, 0x05a30001U, 0x11a00001U
    };
    for (unsigned kind = 0; kind < 7; ++kind) {
        for (unsigned taken = 0; taken < 2; ++taken) {
            for (unsigned iterations : {16U, 128U}) {
                State state;
                tick(state, 0x1000U, 0x40094800U); // MFC0 Count
                const auto before = state.cpu_count;
                for (unsigned index = 0; index < iterations; ++index) {
                    tick(state, 0x1004U, branches[kind]);
                    if (taken || kind == 6)
                        tick(state, 0x1008U, 0x26310001U); // visible slot effect
                    tick(state, 0x100cU, 0x2508ffffU); // counter decrement
                    tick(state, 0x1010U, 0x1500fffcU); // ordinary loop branch
                    tick(state, 0x1014U, 0U);          // ordinary delay slot
                }
                tick(state, 0x1018U, 0x400c4800U); // MFC0 Count
                std::printf("%u\t%u\t%u\t%llu\n", kind, taken, iterations,
                            static_cast<unsigned long long>(state.cpu_count - before));
            }
        }
    }
}
'''


def compare_rows(output: str, reference: dict) -> list[dict]:
    lines = output.splitlines()
    if len(lines) != len(reference["cases"]):
        raise ValueError("native branch check produced incomplete cases")
    mismatches = []
    for line, case in zip(lines, reference["cases"]):
        parts = line.split("\t")
        if len(parts) != 4 or not all(part.isdecimal() for part in parts):
            raise ValueError("native branch check produced malformed cases")
        kind, taken, iterations, ticks = map(int, parts)
        if (kind, taken, iterations) != (case["kind"], case["taken"], case["iterations"]):
            raise ValueError("native branch check changed case order")
        if ticks != case["ticks"]:
            mismatches.append({"kind": kind, "taken": taken, "iterations": iterations,
                               "native_ticks": ticks, "oracle_ticks": case["ticks"]})
    return mismatches


def check(source_path: Path, oracle_trace: Path) -> dict:
    source = source_path.read_bytes()
    reference = parse_trace(oracle_trace)
    if reference["counts_annulled_slots_at_two_ticks"] is not True:
        raise ValueError("branch reference does not qualify this Count profile")
    block = extract(source.decode("utf-8"))
    with tempfile.TemporaryDirectory(prefix="jfg-branch-count-") as temporary:
        executable = Path(temporary) / "check"
        converted = subprocess.run(["wsl", "--exec", "wslpath", "-a", str(executable)],
                                   capture_output=True, text=True, timeout=15, check=True)
        target = converted.stdout.strip()
        compiled = subprocess.run(["wsl", "--exec", "g++", "-std=c++20", "-Wall", "-Wextra",
                                   "-Werror", "-x", "c++", "-", "-o", target],
                                  input=program(block), capture_output=True,
                                  text=True, timeout=60)
        if compiled.returncode:
            raise ValueError("native Count block failed to compile: " + compiled.stderr[:1500])
        ran = subprocess.run(["wsl", "--exec", target], capture_output=True, text=True,
                             timeout=15, check=True)
    mismatches = compare_rows(ran.stdout, reference)
    return {"kind": "jfg-native-branch-count-check", "schema": 1, "complete": True,
            "match": not mismatches, "cases": len(reference["cases"]),
            "hardware_qualified": False, "game_cause_proved": False,
            "source_sha256": hashlib.sha256(source).hexdigest(),
            "accounting_block_sha256": hashlib.sha256(block.encode()).hexdigest(),
            "oracle_trace_sha256": hashlib.sha256(oracle_trace.read_bytes()).hexdigest(),
            "mismatches": mismatches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("oracle_trace", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check(args.source, args.oracle_trace)
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
    print(encoded, end="")
    return 0 if result["match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
